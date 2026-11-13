import shutil
import stat

import dash
import pytest

from behavior_data_visualizer import data, main
from tests.conftest import LOCATION, SAMPLE_DATA, VISUAL_COT


@pytest.fixture
def app():
    return main.app_builder()


def callback(app, output):
    """The function of the callback that writes output (without dash's wrapper)."""
    return next(v["callback"].__wrapped__ for k, v in app.callback_map.items() if output in k)


def test_app_lists_projects(app):
    dropdown = app.layout["projects-dropdown"]
    assert [o["value"] for o in dropdown.options] == data.get_list_of_projects()


def test_mice_of_project(app):
    options, value = callback(app, "single-mouse-dropdown.options")("visual_and_COT_data")
    assert options == [{"label": "ACV008", "value": "ACV008"}] and value is None
    assert callback(app, "single-mouse-dropdown.options")(None) == ([], None)


def test_load_mouse(app):
    loaded, status = callback(app, "mouse-data-loaded.data")(*VISUAL_COT)
    assert loaded == {"project": VISUAL_COT[0], "mouse": VISUAL_COT[1]}
    assert status == "2500 trials in 4 days"
    assert callback(app, "mouse-data-loaded.data")(VISUAL_COT[0], None) == (None, "")
    assert callback(app, "mouse-data-loaded.data")(VISUAL_COT[0], "nobody") == (None, "No trials")


def test_day_view(app):
    loaded = {"project": LOCATION[0], "mouse": LOCATION[1]}
    calendar, text, performance, psychometric, trials, session_button, history_button = callback(
        app, "reactive-calendar.figure"
    )("2026-11-09", loaded)
    assert text.startswith("NUO077, 2026-11-09")
    assert len(calendar.layout.shapes) == 1
    assert len(performance.data) == 1 and len(psychometric.data) == 2
    assert trials.layout.title.text.startswith("Trial by trial")
    assert session_button == "Session report of 2026-11-09"
    assert history_button == "Training history up to 2026-11-09"
    assert callback(app, "reactive-calendar.figure")(None, None)[1] == ""


def test_video_not_found(app):
    click = {"points": [{"customdata": ["ACV008", "TwoAFC", "2025-06-02 10:00:00", 3]}]}
    message, start = callback(app, "single-mouse-video.children")(click, None, VISUAL_COT[0])
    assert "No video of this session" in message.children
    assert start is dash.no_update


@pytest.fixture
def data_with_video(tmp_path, monkeypatch):
    """A data folder with ACV008 and a (fake) video of its session of 2025-06-02, read-only."""
    sessions = tmp_path / VISUAL_COT[0] / "sessions" / "ACV008"
    sessions.mkdir(parents=True)
    shutil.copy(SAMPLE_DATA / VISUAL_COT[0] / "sessions" / "ACV008" / "ACV008.csv.gz", sessions)
    monkeypatch.setenv("LECILAB_DATA_PATH", str(tmp_path))
    data._load_mouse_data.cache_clear()
    df = data.load_mouse_data(*VISUAL_COT)
    session = df[df["year_month_day"] == "2025-06-02"]
    session_date = str(session["date"].iloc[0])
    video = data.video_path(VISUAL_COT[0], "ACV008", "TwoAFC", session_date)
    video.parent.mkdir(parents=True)
    video.write_bytes(b"0123456789" * 100)
    # the user running the dashboard may only be able to read the data
    for path in (video, video.parent):
        path.chmod(stat.S_IREAD | stat.S_IEXEC if path.is_dir() else stat.S_IREAD)
    yield df, session_date, int(session["trial"].iloc[4]), video
    video.parent.chmod(stat.S_IRWXU)
    video.chmod(stat.S_IRWXU)


def test_video_is_served_from_the_data_folder(data_with_video):
    df, session_date, trial, video = data_with_video
    app = main.app_builder()
    click = {"points": [{"customdata": ["ACV008", "TwoAFC", session_date, trial]}]}
    player, start = callback(app, "single-mouse-video.children")(click, None, VISUAL_COT[0])
    assert player.src == f"/videos/{VISUAL_COT[0]}/ACV008/{video.name}"
    assert start == {"time": data.seconds_of_trial(df, session_date, trial)}
    client = app.server.test_client()
    response = client.get(player.src)
    assert response.status_code == 200 and response.data == video.read_bytes()
    response.close()
    partial = client.get(player.src, headers={"Range": "bytes=0-9"})  # the player asks for parts
    assert partial.status_code == 206 and partial.data == b"0123456789"
    partial.close()


def test_only_videos_of_the_data_folder_are_served(data_with_video):
    client = main.app_builder().server.test_client()
    video = data_with_video[3]
    for url in (
        f"/videos/not_a_project/ACV008/{video.name}",
        f"/videos/{VISUAL_COT[0]}/nobody/{video.name}",
        f"/videos/{VISUAL_COT[0]}/ACV008/missing.mp4",
        f"/videos/{VISUAL_COT[0]}/..%2Fsessions/ACV008.csv.gz",
        "/videos/../sessions/ACV008/ACV008.csv.gz",
        f"/videos/{VISUAL_COT[0]}/ACV008/..%2F..%2Fsessions%2FACV008%2FACV008.csv.gz",
    ):
        response = client.get(url)
        # not found, or (an address that is not a video) the page of the dashboard
        assert response.status_code == 404 or response.mimetype == "text/html", url
        response.close()


def test_report_images(visual_cot):
    day = data.day_trials(visual_cot, "2025-06-02")
    report = main.report_image("ACV008: session report", "session_summary_figure", day, width=15, height=10)
    title, image = report.children[:2]
    assert title.children == "ACV008: session report"
    assert image.src.startswith("data:image/png;base64,")
    history = main.report_image("history", "subject_progress_figure", data.trials_up_to(visual_cot, "2025-06-18"))
    assert history.children[1].src.startswith("data:image/png;base64,")
    assert main.report_image("empty", "session_summary_figure", day.iloc[0:0]).children == "empty: no trials"


def _patched(patch):
    """{path: value} of the changes of a dash.Patch."""
    return {".".join(map(str, op["location"])): op["params"]["value"] for op in patch.to_plotly_json()["operations"]}


def test_zoom_on_performance_zooms_trial_by_trial_and_psychometric(location):
    day = data.day_trials(location, "2026-11-09")
    first = day["total_trial"].min()
    zoom = (first - 0.5, first + 199.5)
    performance, trials, psychometric = main.zoom_outputs("single-mouse-performance", zoom, day)
    assert performance is dash.no_update  # the figure that was zoomed
    assert _patched(trials) == {
        "layout.xaxis.range": list(zoom),
        "layout.xaxis.autorange": False,
        "layout.xaxis2.range": list(zoom),
        "layout.xaxis2.autorange": False,
    }
    assert psychometric.layout.title.text == f"trials {first} to {first + 199} (200 trials)"
    n = sum(psychometric.data[0].customdata)  # trials of each point
    assert n == 200


def test_zoom_on_trial_by_trial_and_reset(location):
    day = data.day_trials(location, "2026-11-09")
    performance, trials, psychometric = main.zoom_outputs("trial-by-trial", (100, 200), day)
    assert trials is dash.no_update
    assert _patched(performance) == {"layout.xaxis.range": [100, 200], "layout.xaxis.autorange": False}
    performance, trials, psychometric = main.zoom_outputs("trial-by-trial", "reset", day)
    assert _patched(performance) == {"layout.xaxis.autorange": True}
    assert psychometric.layout.title.text is None
    assert sum(psychometric.data[0].customdata) == len(day)
