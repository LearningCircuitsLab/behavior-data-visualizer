import numpy as np
import pandas as pd

from behavior_data_visualizer import data, figures


def test_calendar_days_and_click_data(visual_cot):
    per_day = data.trials_per_day(visual_cot)
    fig = figures.calendar_figure(per_day, selected="2025-06-02")
    heatmap = fig.data[0]
    z, dates = np.array(heatmap.z, dtype=float), np.array(heatmap.customdata)
    # each day with trials is in the cell whose click gives its date
    for day, n in per_day.items():
        assert z[dates == day].tolist() == [n]
    assert np.nansum(z) == per_day.sum()
    # rows are Monday to Sunday
    assert z[0, dates[0].tolist().index("2025-06-02")] == 496  # a Monday
    assert len(fig.layout.shapes) == 1  # the selected day


def test_calendar_without_trials():
    fig = figures.calendar_figure(pd.Series(dtype=int))
    assert fig.layout.annotations[0].text == "No trials"


def test_performance_click_data(visual_cot):
    day = data.day_trials(visual_cot, "2025-06-02")
    fig = figures.performance_figure(day)
    customdata = np.concatenate([np.array(trace.customdata) for trace in fig.data])
    assert len(customdata) == len(day)
    subject, task, session_date, trial = customdata[0]
    assert subject == "ACV008" and task == "TwoAFC"
    assert pd.Timestamp(session_date) in set(day["date"])
    n_sessions = day["session"].nunique()
    assert len(fig.layout.shapes) == n_sessions - 1  # a line at each new session


def _points(df, day, modality):
    trials, title, fit = figures.psychometric_trials(data.day_trials(df, day), modality)
    return figures.psychometric_points(trials), title, fit


def test_sound_location_psychometric_has_three_points_per_side(location):
    points, title, fit = _points(location, "2026-11-09", "auditory-local-wn")
    assert title.startswith("sound level")
    assert (points["x"] < 0).sum() == 3 and (points["x"] > 0).sum() == 3
    assert fit


def test_visual_and_cot_psychometric(visual_cot):
    points, title, _ = _points(visual_cot, "2025-06-02", "visual")
    assert title.startswith("brightness ratio") and len(points) > 2
    points, title, _ = _points(visual_cot, "2025-06-18", "auditory-cot")
    assert title.startswith("evidence strength") and 2 < len(points) <= 6


def test_only_easy_trials_by_side_and_difficulty(visual_cot):
    points, title, fit = _points(visual_cot, "2025-09-09", "visual")
    assert title.startswith("side and difficulty") and not fit
    assert sorted(points["x"]) == [-1, 1]


def test_psychometric_figure_one_plot_per_modality(visual_cot, location):
    multisensory = figures.psychometric_figure(data.day_trials(visual_cot, "2025-09-09"))
    assert [a.text for a in multisensory.layout.annotations] == ["visual", "auditory-cot"]
    sound = figures.psychometric_figure(data.day_trials(location, "2026-11-09"))
    assert [a.text for a in sound.layout.annotations] == ["auditory-local-wn"]
    assert [trace.mode for trace in sound.data] == ["markers", "lines"]  # points and fitted curve
    habituation = figures.psychometric_figure(data.day_trials(visual_cot, "2025-03-15"))
    assert habituation.layout.annotations[0].text.startswith("Habituation")


def _lane_trials(fig, lane):
    """Trials (x) drawn in a row of the lower panel of the trial-by-trial figure."""
    return sorted(x for trace in fig.data if trace.type == "bar" and trace.base[0] == lane - 0.4 for x in trace.x)


def test_trial_by_trial(visual_cot):
    day = data.day_trials(visual_cot, "2025-06-02")
    fig = figures.trial_by_trial_figure(day)
    left = day[day["correct_side"] == "left"]["total_trial"]
    right = day[day["correct_side"] == "right"]["total_trial"]
    assert _lane_trials(fig, figures.STIMULUS_LEFT) == sorted(left)
    assert _lane_trials(fig, figures.STIMULUS_RIGHT) == sorted(right)
    assert _lane_trials(fig, figures.OUTCOME) == sorted(day["total_trial"])
    assert _lane_trials(fig, figures.EARLY_POKEOUT) == sorted(day[day["early_pokeout"] == True]["total_trial"])  # noqa: E712
    outcomes = {trace.name: len(trace.x) for trace in fig.data if trace.name in figures.OUTCOME_COLORS}
    assert outcomes == {"correct": (day["correct"] == True).sum(), "incorrect": (day["correct"] == False).sum()}  # noqa: E712
    # harder trials are lighter
    visual_left = next(t for t in fig.data if t.name == "visual" and t.base[0] == figures.STIMULUS_LEFT - 0.4)
    assert set(np.round(visual_left.marker.opacity, 2)) == set(figures.DIFFICULTY_OPACITY.values())
    # every trial can be clicked to open its video
    subject, task, session_date, trial = fig.data[-1].customdata[0]
    assert subject == "ACV008" and pd.Timestamp(session_date) in set(day["date"])


def test_trial_by_trial_multisensory_and_habituation(visual_cot):
    multisensory = figures.trial_by_trial_figure(data.day_trials(visual_cot, "2025-09-09"))
    legend = {t.name for t in multisensory.data if t.showlegend is not False}
    assert {"visual", "auditory-cot", "correct", "incorrect", "early pokeout"} <= legend
    habituation = figures.trial_by_trial_figure(data.day_trials(visual_cot, "2025-03-15"))
    assert _lane_trials(habituation, figures.STIMULUS_LEFT) == []  # no stimulus side saved
    assert figures.trial_by_trial_figure(visual_cot.iloc[0:0]).layout.annotations[0].text == "No trials on this day"


def test_zoom_range():
    assert figures.zoom_range(None) is None
    assert figures.zoom_range({"autosize": True}) is None
    assert figures.zoom_range({"xaxis.range[0]": 10, "xaxis.range[1]": 20.5}) == (10, 20.5)
    assert figures.zoom_range({"xaxis2.range[0]": 3, "xaxis2.range[1]": 7}) == (3, 7)
    assert figures.zoom_range({"xaxis.range": [1, 2]}) == (1, 2)
    assert figures.zoom_range({"xaxis.autorange": True}) == figures.ZOOM_RESET
    assert figures.zoom_range({"xaxis2.autorange": True, "xaxis.autorange": True}) == figures.ZOOM_RESET


def test_trials_in_view(visual_cot):
    day = data.day_trials(visual_cot, "2025-06-02")
    first = day["total_trial"].min()
    assert len(figures.trials_in_view(day, (first + 9.5, first + 19.5))) == 10
    assert len(figures.trials_in_view(day, (first + 19.5, first + 9.5))) == 10  # either order
    assert figures.trials_in_view(day, figures.ZOOM_RESET) is day
    assert figures.trials_in_view(day, None) is day


def test_zoom_only_on_trials(visual_cot):
    day = data.day_trials(visual_cot, "2025-06-02")
    assert figures.performance_figure(day).layout.yaxis.fixedrange
    trials = figures.trial_by_trial_figure(day)
    assert trials.layout.yaxis.fixedrange and trials.layout.yaxis2.fixedrange
