"""
Interactive (plotly) figures of the dashboard, and the figures of the daily
report (matplotlib, from lecilab_behavior_analysis) as images.
"""

import base64
import io
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from lecilab_behavior_analysis.data_format_changes import correct_as_number
from lecilab_behavior_analysis.figures.layouts import session_modalities
from lecilab_behavior_analysis.metrics.choices import (
    add_sound_location_level,
    get_performance_by_difficulty_ratio,
    two_sided_bin_edges,
)
from lecilab_behavior_analysis.metrics.performance import get_performance_through_trials
from lecilab_behavior_analysis.metrics.trial_events import (
    side_and_difficulty_to_numeric,
    transform_side_choice_to_numeric,
)
from lecilab_behavior_analysis.models.psychometric import fit_lapse_logistic_independent
from plotly.subplots import make_subplots

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
CALENDAR_COLORS = [[0, "#e8f5e9"], [1, "#1b5e20"]]
SELECTED_COLOR = "#d62728"


def empty_figure(message: str = "") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        xaxis={"visible": False},
        yaxis={"visible": False},
        plot_bgcolor="white",
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        annotations=[{"text": message, "showarrow": False, "font": {"size": 14, "color": "grey"}}] if message else [],
    )
    return fig


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------
def calendar_figure(trials_per_day: pd.Series, selected: Optional[str] = None) -> go.Figure:
    """
    Days with trials, one column per week (Monday to Sunday from top to
    bottom), coloured by the number of trials. Clicking a day gives its date
    (YYYY-MM-DD) in clickData["points"][0]["customdata"]. The selected day
    is framed in red.
    """
    if trials_per_day.empty:
        return empty_figure("No trials")
    days = pd.to_datetime(trials_per_day.index)
    first = days.min() - pd.Timedelta(days=days.min().weekday())  # Monday
    n_weeks = (days.max() - first).days // 7 + 1
    z = np.full((7, n_weeks), np.nan)
    dates = np.full((7, n_weeks), "", dtype=object)
    for day, n in zip(days, trials_per_day.values):
        week, weekday = (day - first).days // 7, day.weekday()
        z[weekday, week] = n
        dates[weekday, week] = day.strftime("%Y-%m-%d")
    # empty cells also get their date, so that they show it on hover
    for week in range(n_weeks):
        for weekday in range(7):
            if not dates[weekday, week]:
                dates[weekday, week] = (first + pd.Timedelta(days=7 * week + weekday)).strftime("%Y-%m-%d")
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=list(range(n_weeks)),
            y=WEEKDAYS,
            customdata=dates,
            colorscale=CALENDAR_COLORS,
            xgap=2,
            ygap=2,
            hoverongaps=True,
            hovertemplate="%{customdata}<br>%{z} trials<extra></extra>",
            colorbar={"title": "trials", "thickness": 10},
        )
    )
    # a label at the first week of each month
    month_starts = pd.date_range(first, days.max(), freq="MS")
    ticks = [
        ((m - first).days // 7, m.strftime("%b %Y" if m.month == 1 or i == 0 else "%b"))
        for i, m in enumerate(month_starts)
    ]
    if not ticks or ticks[0][0] != 0:
        ticks.insert(0, (0, first.strftime("%b %Y")))
    if selected:
        day = pd.Timestamp(selected)
        if first <= day <= days.max():
            week, weekday = (day - first).days // 7, day.weekday()
            fig.add_shape(
                type="rect",
                x0=week - 0.5,
                x1=week + 0.5,
                y0=weekday - 0.5,
                y1=weekday + 0.5,
                line={"color": SELECTED_COLOR, "width": 3},
            )
    fig.update_layout(
        xaxis={
            "tickvals": [t for t, _ in ticks],
            "ticktext": [label for _, label in ticks],
            "showgrid": False,
            "zeroline": False,
        },
        yaxis={"autorange": "reversed", "showgrid": False, "zeroline": False},
        plot_bgcolor="white",
        margin={"l": 40, "r": 10, "t": 10, "b": 30},
        height=230,
    )
    return fig


# ---------------------------------------------------------------------------
# One day
# ---------------------------------------------------------------------------
def performance_figure(day_df: pd.DataFrame, window: int = 50) -> go.Figure:
    """
    Performance of a day through its trials (rolling window), coloured by
    modality, with a dashed line at each new session. Clicking a point gives
    (subject, task, session date, trial) in its customdata (to open the video).
    """
    if day_df.empty:
        return empty_figure("No trials on this day")
    df = get_performance_through_trials(day_df.copy(), window=window)
    df["session_date"] = df["date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    modality = df["stimulus_modality"].fillna("unknown") if "stimulus_modality" in df else "unknown"
    df["modality"] = modality
    fig = go.Figure()
    for name, group in df.groupby("modality", sort=True):
        fig.add_trace(
            go.Scattergl(
                x=group["total_trial"],
                y=group["performance_w"],
                mode="markers",
                marker={"size": 5},
                name=str(name),
                customdata=group[["subject", "task", "session_date", "trial"]].to_numpy(),
                hovertemplate="trial %{x}<br>performance %{y:.0f}%<br>session %{customdata[2]}"
                "<br>click: video of this trial<extra></extra>",
            )
        )
    for _, start in df[df["session"] != df["session"].shift(1)].iloc[1:].iterrows():
        fig.add_vline(x=start["total_trial"], line_width=1, line_dash="dash", line_color="grey")
    fig.update_layout(
        title=f"Performance (window of {window} trials)",
        xaxis_title="trial",
        yaxis={"title": "% correct", "range": [0, 100], "fixedrange": True},  # zoom only on the trials
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        margin={"l": 50, "r": 10, "t": 70, "b": 40},
        plot_bgcolor="white",
    )
    fig.update_xaxes(gridcolor="#eee")
    fig.update_yaxes(gridcolor="#eee")
    return fig


# colours of the trial-by-trial figure
MODALITY_COLORS = {"visual": "#e0a100", "auditory-cot": "#7b3fbf", "auditory-local-wn": "#1f9e89"}
OTHER_MODALITY_COLOR = "#8c8c8c"
# correct trials light, so that errors stand out
OUTCOME_COLORS = {"correct": "#a5d6a7", "incorrect": "#d32f2f", "miss": "#616161"}
EARLY_POKEOUT_COLOR = "#ef6c00"
PERFORMANCE_COLOR = "#1f77b4"
# easier trials are drawn darker
DIFFICULTY_OPACITY = {"easy": 1.0, "medium": 0.6, "hard": 0.3}

# rows of the lower panel, from top to bottom: (y, label)
STIMULUS_LEFT, STIMULUS_RIGHT, OUTCOME, EARLY_POKEOUT = 3, 2, 1, 0
LANE_LABELS = {
    STIMULUS_LEFT: "stimulus left",
    STIMULUS_RIGHT: "stimulus right",
    OUTCOME: "outcome",
    EARLY_POKEOUT: "early pokeout",
}


def _trial_info(df: pd.DataFrame) -> pd.DataFrame:
    """One row per trial with what the trial-by-trial figure shows."""
    info = pd.DataFrame(index=df.index)
    info["x"] = df["total_trial"]
    info["modality"] = df["stimulus_modality"].fillna("not saved").astype(str)
    info["side"] = df["correct_side"].fillna("not saved").astype(str)
    info["difficulty"] = df["difficulty"].fillna("not saved").astype(str)
    correct = df["correct"].apply(correct_as_number)
    miss = df["miss_trial"].fillna(False).astype(bool) if "miss_trial" in df else pd.Series(False, index=df.index)
    info["outcome"] = np.where(miss, "miss", np.where(correct == 1, "correct", "incorrect"))
    info["early_pokeout"] = df["early_pokeout"].map({True: True, False: False}) if "early_pokeout" in df else None
    info["choice"] = df["first_choice"].fillna("none").astype(str)
    info["reaction_time"] = pd.to_numeric(df.get("reaction_time"), errors="coerce")
    info["session"] = df["session"]
    info["trial"] = df["trial"]
    # (subject, task, session date, trial): clicking a trial opens its video
    info["subject"] = df["subject"]
    info["task"] = df["task"]
    info["session_date"] = df["date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    info["hover"] = [
        f"trial {int(t)} of session {int(s) if pd.notna(s) else s}<br>{m}, {d}, correct side {side}<br>"
        f"choice {c}: <b>{o}</b>{', early pokeout' if e is True else ''}"
        + (f"<br>reaction time {rt:.2f} s" if pd.notna(rt) else "")
        for t, s, m, d, side, c, o, e, rt in zip(
            info["trial"],
            info["session"],
            info["modality"],
            info["difficulty"],
            info["side"],
            info["choice"],
            info["outcome"],
            info["early_pokeout"],
            info["reaction_time"],
        )
    ]
    return info


def _lane(
    info: pd.DataFrame, lane: int, color, name: str, legendgroup: str, showlegend: bool = True, opacity=1.0
) -> go.Bar:
    """One tick per trial (a bar of width 1) in a row of the lower panel."""
    return go.Bar(
        x=info["x"],
        y=np.full(len(info), 0.8),
        base=np.full(len(info), lane - 0.4),
        width=1,
        marker={"color": color, "opacity": opacity, "line": {"width": 0}},
        name=name,
        legendgroup=legendgroup,
        showlegend=showlegend,
        customdata=info[["subject", "task", "session_date", "trial"]].to_numpy(),
        hovertext=info["hover"],
        hovertemplate="%{hovertext}<extra></extra>",
    )


def trial_by_trial_figure(day_df: pd.DataFrame, window: int = 20) -> go.Figure:
    """
    What happened on each trial of a day, as a barcode (one tick per trial):

    - stimulus left / right: the correct side, coloured by modality (darker
      for easier trials),
    - outcome: correct, incorrect or miss,
    - early pokeout: trials where the mouse left the center port too early.

    Above, the performance and the early pokeouts (% of the last `window`
    trials). Dashed lines mark new sessions. Clicking a trial gives (subject,
    task, session date, trial) in its customdata (to open the video).
    """
    if day_df.empty:
        return empty_figure("No trials on this day")
    df = day_df.sort_values(["session", "trial"])
    info = _trial_info(df)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.35, 0.65], vertical_spacing=0.04)

    # rolling rates
    rolling = {
        "performance": (df["correct"].apply(correct_as_number), PERFORMANCE_COLOR),
        "early pokeouts": (info["early_pokeout"].astype(float), EARLY_POKEOUT_COLOR),
    }
    for name, (values, color) in rolling.items():
        if values.notna().sum() == 0:
            continue
        rate = values.rolling(window, min_periods=min(5, window)).mean() * 100
        fig.add_trace(
            go.Scatter(
                x=info["x"],
                y=rate,
                mode="lines",
                line={"color": color, "width": 2},
                name=f"{name} (%)",
                legendgroup="rates",
                customdata=info[["subject", "task", "session_date", "trial"]].to_numpy(),
                hovertemplate=f"{name}: %{{y:.0f}}%<extra></extra>",
            ),
            row=1,
            col=1,
        )

    # stimulus: one trace per modality, left and right rows
    for modality, group in info.groupby("modality", sort=False):
        color = MODALITY_COLORS.get(modality, OTHER_MODALITY_COLOR)
        first = True
        for side, lane in (("left", STIMULUS_LEFT), ("right", STIMULUS_RIGHT)):
            trials = group[group["side"] == side]
            if trials.empty:
                continue
            opacity = trials["difficulty"].map(DIFFICULTY_OPACITY).fillna(1.0).to_numpy()
            fig.add_trace(_lane(trials, lane, color, modality, f"modality {modality}", first, opacity), row=2, col=1)
            first = False
    for outcome, color in OUTCOME_COLORS.items():
        trials = info[info["outcome"] == outcome]
        if len(trials):
            fig.add_trace(_lane(trials, OUTCOME, color, outcome, f"outcome {outcome}"), row=2, col=1)
    early = info[info["early_pokeout"].eq(True)]
    if len(early):
        fig.add_trace(_lane(early, EARLY_POKEOUT, EARLY_POKEOUT_COLOR, "early pokeout", "early"), row=2, col=1)

    for x in info["x"][info["session"] != info["session"].shift(1)].iloc[1:]:
        fig.add_vline(x=x - 0.5, line_width=1, line_dash="dash", line_color="grey")
    # zoom only on the trials
    fig.update_yaxes(title_text="% of last trials", range=[0, 100], gridcolor="#eee", fixedrange=True, row=1, col=1)
    fig.update_yaxes(
        fixedrange=True,
        tickvals=list(LANE_LABELS),
        ticktext=list(LANE_LABELS.values()),
        range=[-0.6, 3.6],
        showgrid=False,
        zeroline=False,
        row=2,
        col=1,
    )
    fig.update_xaxes(title_text="trial", row=2, col=1)
    fig.update_layout(
        title=f"Trial by trial (rates: window of {window} trials; stimulus: darker = easier)",
        barmode="overlay",
        bargap=0,
        plot_bgcolor="white",
        hovermode="closest",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        margin={"l": 110, "r": 10, "t": 80, "b": 40},
        height=420,
    )
    return fig


def psychometric_trials(df: pd.DataFrame, modality: str) -> Tuple[pd.DataFrame, str, bool]:
    """
    Choices on the trials of one modality, as in the daily report (see
    lecilab_behavior_analysis.figures.panels.psychometric):

    - visual: by brightness ratio (+ left brighter),
    - auditory-cot: by evidence strength (6 bins),
    - auditory-local-wn: by sound level (+ left), 3 bins per side,
    - otherwise, or with only easy trials: by side and difficulty.

    Returns (one row per trial, with x (the mean of its bin when binned) and
    choice (1 left, 0 right); x axis title; whether a logistic curve can be
    fitted). The trials are those of the modality that are not habituation
    and have a first choice.
    """
    trials = df[(df["task"] != "Habituation") & (df["stimulus_modality"] == modality)].copy()
    trials["first_choice_numeric"] = trials["first_choice"].apply(transform_side_choice_to_numeric)
    only_easy = trials["difficulty"].nunique() == 1 and trials["difficulty"].iloc[0] == "easy"
    levels = None
    if modality == "auditory-local-wn" and not only_easy:
        levels = add_sound_location_level(trials).dropna(subset=["sound_location_db"])
    fit = True
    if modality in ("visual", "auditory-cot") and not only_easy:
        values = get_performance_by_difficulty_ratio(trials)
        if modality == "visual":
            x, title = values["visual_stimulus_ratio"], "brightness ratio (+ left brighter)"
        else:
            x = _bin_means(values["total_evidence_strength"], 6)
            title = "evidence strength (binned)"
        choices = values["first_choice_numeric"]
    elif levels is not None and len(levels):
        db = levels["sound_location_db"]
        x = _bin_means(db, two_sided_bin_edges(db, per_side=3))
        choices, title = levels["first_choice_numeric"], "sound level (dB SPL, + left / - right)"
    else:
        x = trials.apply(side_and_difficulty_to_numeric, axis=1) if len(trials) else pd.Series(dtype=float)
        choices, title, fit = trials["first_choice_numeric"], "side and difficulty (+ left)", False
    result = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "choice": pd.to_numeric(choices, errors="coerce")})
    return result.dropna(), title, fit


def _bin_means(values: pd.Series, bins) -> pd.Series:
    """Each value replaced by the mean of its bin (bins: a number or the edges)."""
    return values.groupby(pd.cut(values, bins=bins), observed=True).transform("mean").astype(float)


def psychometric_points(trials: pd.DataFrame) -> pd.DataFrame:
    """Proportion of left choices (p_left) and number of trials (n) at each x."""
    return trials.groupby("x")["choice"].agg(p_left="mean", n="size").reset_index()


def logistic_curve(trials: pd.DataFrame) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Lapse logistic fitted to the trials: (x, P(left)) on 100 points, or None."""
    if trials["x"].nunique() < 3:
        return None
    try:
        p_left, _ = fit_lapse_logistic_independent(trials["x"], trials["choice"])
    except Exception:
        return None
    return np.linspace(trials["x"].min(), trials["x"].max(), 100), np.asarray(p_left).ravel()


def psychometric_figure(day_df: pd.DataFrame, title: Optional[str] = None) -> go.Figure:
    """
    One psychometric plot per modality of the trials (two in multisensory
    sessions). title: shown above (e.g. the trials used).
    """
    if day_df.empty:
        return empty_figure("No trials" + (f" ({title})" if title else ""))
    modalities = session_modalities(day_df)
    if not modalities:
        return empty_figure("Habituation: no choices")
    fig = make_subplots(rows=1, cols=len(modalities), subplot_titles=modalities, shared_yaxes=True)
    for col, modality in enumerate(modalities, start=1):
        try:
            trials, axis_title, fit = psychometric_trials(day_df, modality)
        except Exception as error:  # a modality whose stimulus could not be read
            fig.add_annotation(
                text=f"Could not compute: {type(error).__name__}",
                showarrow=False,
                xref=f"x{col} domain",
                yref=f"y{col} domain",
                x=0.5,
                y=0.5,
            )
            continue
        points = psychometric_points(trials)
        fig.add_trace(
            go.Scatter(
                x=points["x"],
                y=points["p_left"],
                mode="markers",
                marker={"size": 9, "color": "cornflowerblue"},
                customdata=points["n"],
                showlegend=False,
                hovertemplate="%{x:.3g}<br>P(left) %{y:.2f}<br>%{customdata} trials<extra></extra>",
            ),
            row=1,
            col=col,
        )
        curve = logistic_curve(trials) if fit else None
        if curve is not None:
            fig.add_trace(
                go.Scatter(
                    x=curve[0],
                    y=curve[1],
                    mode="lines",
                    line={"color": "lightcoral"},
                    hoverinfo="skip",
                    showlegend=False,
                ),
                row=1,
                col=col,
            )
        fig.update_xaxes(title_text=axis_title, row=1, col=col, gridcolor="#eee", zeroline=True, zerolinecolor="#ccc")
    fig.update_yaxes(range=[-0.02, 1.02], gridcolor="#eee")
    fig.update_yaxes(title_text="P(left choice)", row=1, col=1)
    fig.update_layout(
        plot_bgcolor="white",
        margin={"l": 50, "r": 10, "t": 70 if title else 40, "b": 50},
        title={"text": title, "font": {"size": 13}} if title else None,
    )
    return fig


# ---------------------------------------------------------------------------
# Figures of the daily report, as images
# ---------------------------------------------------------------------------
def matplotlib_to_uri(fig) -> str:
    """A matplotlib figure as a PNG data URI (for an html.Img), closing the figure."""
    from matplotlib import pyplot as plt

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=90, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buffer.getbuffer()).decode("ascii")


def report_problems(fig) -> List[str]:
    """Panels of a report figure that could not be drawn."""
    return [str(problem) for problem in getattr(fig, "panel_problems", [])]


# ---------------------------------------------------------------------------
# Zoom on some trials
# ---------------------------------------------------------------------------
ZOOM_RESET = "reset"


def zoom_range(relayout: Optional[dict]):
    """
    The trials shown after a zoom on a figure whose x axis is the trial
    (relayoutData of a dcc.Graph): (first, last), ZOOM_RESET when it goes back
    to all the trials (double click, autoscale), or None if the x axis did
    not change (e.g. only the size of the figure).
    """
    if not relayout:
        return None
    for axis in ("xaxis", "xaxis2"):
        if relayout.get(f"{axis}.autorange"):
            return ZOOM_RESET
        if f"{axis}.range[0]" in relayout and f"{axis}.range[1]" in relayout:
            return float(relayout[f"{axis}.range[0]"]), float(relayout[f"{axis}.range[1]"])
        if isinstance(relayout.get(f"{axis}.range"), (list, tuple)) and len(relayout[f"{axis}.range"]) == 2:
            first, last = relayout[f"{axis}.range"]
            return float(first), float(last)
    return None


def trials_in_view(day_df: pd.DataFrame, zoom) -> pd.DataFrame:
    """Trials of the day whose total_trial is in the zoom range (all of them without zoom)."""
    if zoom is None or zoom == ZOOM_RESET:
        return day_df
    first, last = sorted(zoom)
    return day_df[day_df["total_trial"].between(first, last)]
