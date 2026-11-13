import dash
import pytest

from behavior_data_visualizer import data, main
from tests.conftest import LOCATION, VISUAL_COT


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


def test_video_is_linked_and_served(app, tmp_path, monkeypatch, visual_cot):
    session = visual_cot[visual_cot["year_month_day"] == "2025-06-02"]
    session_date, trial = str(session["date"].iloc[0]), int(session["trial"].iloc[4])
    video = data.video_path(VISUAL_COT[0], "ACV008", "TwoAFC", session_date)
    copy = tmp_path / "videos" / video.name
    copy.parent.mkdir()
    copy.write_bytes(b"0" * 1000)
    monkeypatch.setattr(data, "video_path", lambda *args: copy)
    monkeypatch.setattr(main, "STATIC_PATH", tmp_path / "static")
    (tmp_path / "static").mkdir()
    click = {"points": [{"customdata": ["ACV008", "TwoAFC", session_date, trial]}]}
    children, start = callback(app, "single-mouse-video.children")(click, None, VISUAL_COT[0])
    assert children.src == f"/videos/{video.name}"
    assert start == {"time": data.seconds_of_trial(visual_cot, session_date, trial)}
    assert (tmp_path / "static" / video.name).resolve() == copy


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
