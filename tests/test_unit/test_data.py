import pandas as pd

from behavior_data_visualizer import data
from tests.conftest import LOCATION, SAMPLE_DATA, VISUAL_COT


def test_data_path_from_environment():
    assert data.get_data_path() == SAMPLE_DATA


def test_no_data_path(monkeypatch, tmp_path):
    monkeypatch.setenv("LECILAB_DATA_PATH", str(tmp_path / "missing"))
    monkeypatch.setattr(data, "FALLBACK_DATA_PATHS", ())
    assert data.get_data_path() is None
    assert data.get_list_of_projects() == []
    assert data.get_list_of_mice("visual_and_COT_data") == []
    assert data.load_mouse_data(*VISUAL_COT).empty


def test_projects_and_mice():
    assert data.get_list_of_projects() == ["frequency_vs_locationPureTone_data", "visual_and_COT_data"]
    assert data.get_list_of_mice("visual_and_COT_data") == ["ACV008"]
    assert data.get_list_of_mice("not_a_project") == []
    assert data.get_list_of_mice(None) == []


def test_load_mouse_data_reads_csv_gz_and_prepares(visual_cot):
    assert data.trials_file(*VISUAL_COT).name == "ACV008.csv.gz"
    assert len(visual_cot) == 2500
    for column in ("year_month_day", "total_trial", "first_choice", "performance_w"):
        assert column in visual_cot.columns
    assert pd.api.types.is_datetime64_any_dtype(visual_cot["date"])


def test_load_mouse_data_is_cached():
    assert data.load_mouse_data(*LOCATION) is data.load_mouse_data(*LOCATION)


def test_missing_mouse_is_empty():
    assert data.load_mouse_data("visual_and_COT_data", "nobody").empty


def test_days(visual_cot):
    per_day = data.trials_per_day(visual_cot)
    assert per_day.to_dict() == {"2025-03-15": 205, "2025-06-02": 496, "2025-06-18": 994, "2025-09-09": 805}
    assert data.last_day(visual_cot) == "2025-09-09"
    assert len(data.day_trials(visual_cot, "2025-06-02")) == 496
    assert data.day_trials(visual_cot, None).empty
    assert len(data.trials_up_to(visual_cot, "2025-06-02")) == 205 + 496
    assert data.last_day(pd.DataFrame()) is None


def test_video_path():
    path = data.video_path("visual_and_COT_data", "ACV008", "TwoAFC", "2025-04-01 16:07:25")
    assert path == SAMPLE_DATA / "visual_and_COT_data" / "videos" / "ACV008" / "ACV008_TwoAFC_20250401_160725.mp4"


def test_seconds_of_trial(visual_cot):
    session = visual_cot[visual_cot["year_month_day"] == "2025-06-02"]
    start = str(session["date"].iloc[0])
    first, tenth = session["trial"].iloc[0], session["trial"].iloc[9]
    assert data.seconds_of_trial(visual_cot, start, first) == 0
    expected = session["TRIAL_START"].iloc[9] - session["TRIAL_START"].iloc[0]
    assert data.seconds_of_trial(visual_cot, start, tenth) == expected > 0
    assert data.seconds_of_trial(visual_cot, start, -1) is None
    assert data.seconds_of_trial(pd.DataFrame(), start, first) is None
