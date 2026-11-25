"""The settings history: settings of each session and the training matrix (data, figures and app)."""

import os
import time

import pytest
from dash.exceptions import PreventUpdate

from behavior_data_visualizer import data, figures, main
from tests.conftest import VISUAL_COT
from tests.test_unit.test_app import callback

SHOWN = {"display": "block"}


@pytest.fixture
def table():
    return data.load_session_settings(*VISUAL_COT)


def test_load_session_settings(table, visual_cot):
    # one row per session of the mouse (not the other mouse, not the row without settings)
    assert len(table) == visual_cot["session"].nunique() == 11
    assert set(table["subject"]) == {"ACV008"}
    assert table["date"].is_monotonic_increasing
    assert data.load_session_settings("visual_and_COT_data", "nobody").empty


def test_session_settings_are_cached_and_read_again_when_the_file_changes(tmp_path, monkeypatch):
    project = tmp_path / "project"
    (project / "sessions").mkdir(parents=True)
    (project / "village01").mkdir()
    summary = project / "village01" / "sessions_summary.csv"
    summary.write_text('date;subject;task;settings\n2026-01-01 10:00:00;M1;TwoAFC;"{""punishment"": false}"\n')
    monkeypatch.setenv("LECILAB_DATA_PATH", str(tmp_path))
    data.clear_cache()
    assert data.load_session_settings("project", "M1")["punishment"].tolist() == [False]
    assert data.load_session_settings("project", "M1") is not None and data.SETTINGS.loads == 1
    summary.write_text(summary.read_text() + '2026-01-02 10:00:00;M1;TwoAFC;"{""punishment"": true}"\n')
    os.utime(summary, (time.time() + 5, time.time() + 5))
    assert data.load_session_settings("project", "M1")["punishment"].tolist() == [False, True]
    assert data.SETTINGS.loads == 2


def test_no_summaries(tmp_path, monkeypatch):
    (tmp_path / "project" / "sessions").mkdir(parents=True)
    monkeypatch.setenv("LECILAB_DATA_PATH", str(tmp_path))
    data.clear_cache()
    assert data.load_session_settings("project", "M1").empty


def test_training_matrix_figure(visual_cot, table):
    names = ["current_training_stage", "punishment", "reward_amount_ul"]
    fig = figures.training_matrix_figure(visual_cot, table, names, selected_day="2025-06-02")
    heatmaps = [trace for trace in fig.data if trace.type == "heatmap"]
    # the settings: one heatmap (plotly draws one heatmap per category axis), a row per setting
    assert len(heatmaps) == 2 and list(heatmaps[0].y) == names
    assert all(len(row) == len(heatmaps[0].x) for row in heatmaps[0].z)
    # True and False of punishment have different colours (different steps of the colour scale)
    punishment = heatmaps[0].z[1]
    assert len(set(punishment)) == 2
    matrix = heatmaps[-1]
    assert list(matrix.y) == ["left easy", "left medium", "left hard", "right hard", "right medium", "right easy"]
    assert len(matrix.x) == visual_cot["session"].nunique()
    # clicking a cell gives its session date
    assert matrix.customdata[0][0].startswith("2025-03-15")
    # the selected day is framed (its sessions) and labelled
    (frame,) = fig.layout.shapes
    sessions_on_day = visual_cot[visual_cot["year_month_day"] == "2025-06-02"]["session"].nunique()
    assert frame.x1 - frame.x0 == sessions_on_day
    assert fig.layout.annotations[-1].text == "2025-06-02"
    # the value of a setting is written where it changes
    stage_text = [t for t in fig.data if t.type == "scatter" and t.y and t.y[0] == "current_training_stage"][0]
    assert stage_text.text[0] == "Habituation"


def test_training_matrix_figure_without_settings_or_day(visual_cot):
    fig = figures.training_matrix_figure(visual_cot, None, [], selected_day="1999-01-01")
    assert [t.type for t in fig.data] == ["heatmap"] and not fig.layout.shapes
    assert figures.training_matrix_figure(visual_cot.iloc[0:0]).layout.annotations[0].text == "No trials"


def test_settings_options(table):
    options, default = main.settings_options(table)
    values = [o["value"] for o in options]
    assert values[0] == "current_training_stage" and options[0]["label"] == "current_training_stage (changes)"
    assert "trial_sides" in values and "date" not in values
    assert default == [
        "current_training_stage",
        "punishment",
        "hard_trials_on",
        "reward_amount_ul",
        "holding_response_time",
    ]
    assert main.settings_options(table.iloc[0:0]) == ([], [])


def test_day_settings_text(table):
    blocks = main.day_settings_text(table, "ACV008", "2025-06-02")
    sessions_on_day = (table["date"].dt.strftime("%Y-%m-%d") == "2025-06-02").sum()
    assert len(blocks) == sessions_on_day
    assert blocks[0].children.startswith("ACV008, session of 2025-06-02")
    assert "changed since the previous session" in blocks[0].children
    assert "No settings saved" in main.day_settings_text(table, "ACV008", "1999-01-01").children
    assert "No settings saved" in main.day_settings_text(table.iloc[0:0], "ACV008", "2025-06-02").children


@pytest.fixture
def app():
    return main.app_builder()


def test_settings_section_is_shown_with_its_button(app):
    toggle = callback(app, "settings-section.style")
    assert toggle(1) == SHOWN and toggle(2) == {"display": "none"}


def test_settings_history_callback(app):
    loaded = {"project": VISUAL_COT[0], "mouse": VISUAL_COT[1]}
    options, value = callback(app, "settings-dropdown.options")(loaded)
    assert "current_training_stage" in value
    update = callback(app, "settings-matrix.figure")
    with pytest.raises(PreventUpdate):  # hidden: not drawn
        update("2025-06-02", value, {"display": "none"}, loaded)
    figure, text = update("2025-06-02", value, SHOWN, loaded)
    assert len(figure.layout.shapes) == 1 and len(text) >= 1


def test_clicking_the_matrix_selects_the_day(app, monkeypatch):
    loaded = {"project": VISUAL_COT[0], "mouse": VISUAL_COT[1]}
    monkeypatch.setattr(main, "triggered_id", lambda: "settings-matrix")
    select = callback(app, "selected-day.data")
    assert select(loaded, None, {"points": [{"customdata": "2025-06-02 10:00"}]}) == "2025-06-02"
    with pytest.raises(PreventUpdate):  # a day without trials
        select(loaded, None, {"points": [{"customdata": "1999-01-01 10:00"}]})
