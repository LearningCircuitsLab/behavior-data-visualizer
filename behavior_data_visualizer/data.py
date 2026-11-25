"""
Reading the data of the Training Village projects for the dashboard.

The data folder has one folder per project, with the trials of each subject
in <project>/sessions/<subject>/<subject>.csv (or .csv.gz), the logs of
each setup in <project>/<setup>/ and the videos in
<project>/videos/<subject>/. It is read with lecilab_behavior_analysis, as
the daily reports (village-report-generator) do.

The trials of the last subjects opened are kept in memory, shared by everyone
using the dashboard (up to CACHE_GB, see cache.py), and read again when their
file changes.
"""

import os
from pathlib import Path
from typing import List, Optional

import pandas as pd
from lecilab_behavior_analysis.io.loading import load_project_logs, load_project_trials
from lecilab_behavior_analysis.io.server import get_outpath

from behavior_data_visualizer.cache import SharedCache

# folders tried, in order, when the one of lecilab_behavior_analysis (the
# LECILAB_DATA_PATH environment variable or the folder of this computer)
# does not exist
FALLBACK_DATA_PATHS = ("/storage/training_village", "/archive/training_village")

# memory for the trials kept in memory (all users together), in GB: the
# BDV_CACHE_GB environment variable, or 4
CACHE_GB = float(os.environ.get("BDV_CACHE_GB", 4))

MICE = SharedCache(int(CACHE_GB * 1e9), name="trials")
EVENTS = SharedCache(int(1e9), name="events")  # the events of a project or two
SETTINGS = SharedCache(int(5e8), name="settings")  # the settings of the sessions of a few projects

PERFORMANCE_WINDOW = 50


def get_data_path() -> Optional[Path]:
    """Folder with the data of every project, or None if there is none."""
    for path in (get_outpath(), *FALLBACK_DATA_PATHS):
        if path and Path(path).is_dir():
            return Path(path)
    return None


def get_list_of_projects() -> List[str]:
    """Projects of the data folder: its folders with a sessions folder."""
    root = get_data_path()
    if root is None:
        return []
    return sorted(p.name for p in root.iterdir() if (p / "sessions").is_dir())


def get_list_of_mice(project_name: str) -> List[str]:
    root = get_data_path()
    if root is None or not project_name:
        return []
    sessions = root / project_name / "sessions"
    if not sessions.is_dir():
        return []
    return sorted(p.name for p in sessions.iterdir() if p.is_dir())


def trials_file(project_name: str, mouse_name: str) -> Optional[Path]:
    """<subject>.csv of a subject, or <subject>.csv.gz if there is no .csv."""
    root = get_data_path()
    if root is None:
        return None
    path = root / project_name / "sessions" / mouse_name / f"{mouse_name}.csv"
    for candidate in (path, path.with_suffix(".csv.gz")):
        if candidate.exists():
            return candidate
    return None


def _modified(path: Optional[Path]) -> float:
    return path.stat().st_mtime if path is not None and path.exists() else 0.0


def load_mouse_data(project_name: str, mouse_name: str) -> pd.DataFrame:
    """
    Trials of a subject, prepared for analysis (preprocessing.prepare, with
    year_month_day, total_trial...), and its performance through trials
    (performance_w). Empty if there are none. Do not modify it: it is shared
    by every callback (copy it first).
    """
    path = trials_file(project_name, mouse_name)
    if path is None:
        return pd.DataFrame()
    root = get_data_path()
    return MICE.get(
        (project_name, mouse_name),
        _modified(path),
        lambda: load_project_trials(project_name, [mouse_name], root=root, window=PERFORMANCE_WINDOW),
    )


def load_events(project_name: str) -> Optional[pd.DataFrame]:
    """Events of every setup of a project (None if there are none). Do not modify it."""
    root = get_data_path()
    if root is None:
        return None
    folder = root / project_name
    files = sorted(folder.glob("*/events.csv")) + sorted(folder.glob("events.csv"))

    def read() -> Optional[pd.DataFrame]:
        events, _, _ = load_project_logs(project_name, root=root)
        return events

    return EVENTS.get(project_name, tuple(_modified(f) for f in files), read)


def summary_files(project_name: str) -> List[Path]:
    """The sessions_summary.csv of every setup of a project (lecilab_behavior_analysis.io.loading.find_setups)."""
    from lecilab_behavior_analysis.io.loading import find_setups

    root = get_data_path()
    if root is None:
        return []
    return [root / project_name / setup / "sessions_summary.csv" for setup in find_setups(project_name, root)]


def load_session_settings(project_name: str, mouse_name: str) -> pd.DataFrame:
    """
    The settings of every session of a mouse: one row per session (date,
    subject, task and one column per setting), read from the sessions
    summaries of the project (lecilab_behavior_analysis.io.settings). Empty
    if there are none. Do not modify it.
    """
    from lecilab_behavior_analysis.io.settings import session_settings_table

    files = [f for f in summary_files(project_name) if f.exists()]

    def read() -> pd.DataFrame:
        frames = []
        for path in files:
            try:
                frames.append(pd.read_csv(path, sep=";"))
            except Exception:  # a summary that cannot be read: the others are still used
                continue
        summary = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        return session_settings_table(summary)

    table = SETTINGS.get(project_name, tuple((str(f), _modified(f)) for f in files), read)
    if table.empty:
        return table
    return table[table["subject"] == mouse_name].reset_index(drop=True)


def clear_cache() -> None:
    """Forgets the data in memory (it is read again when needed)."""
    MICE.clear()
    EVENTS.clear()
    SETTINGS.clear()


def day_trials(df: pd.DataFrame, day: str) -> pd.DataFrame:
    """Trials of one day (YYYY-MM-DD)."""
    if df.empty or not day:
        return df.iloc[0:0]
    return df[df["year_month_day"] == day]


def trials_up_to(df: pd.DataFrame, day: str) -> pd.DataFrame:
    """Trials up to the end of a day (YYYY-MM-DD)."""
    if df.empty or not day:
        return df
    return df[df["date"] < pd.Timestamp(day) + pd.Timedelta(days=1)]


def trials_per_day(df: pd.DataFrame) -> pd.Series:
    """Number of trials of each day (index: YYYY-MM-DD)."""
    if df.empty:
        return pd.Series(dtype=int)
    return df.groupby("year_month_day").size()


def last_day(df: pd.DataFrame) -> Optional[str]:
    return None if df.empty else str(df["year_month_day"].max())


def video_path(project_name: str, mouse_name: str, task: str, session_date: str) -> Optional[Path]:
    """
    Video of a session: <project>/videos/<subject>/<subject>_<task>_<YYYYMMDD_HHMMSS>.mp4.
    session_date is the date of the session (YYYY-MM-DD HH:MM:SS).
    """
    root = get_data_path()
    if root is None:
        return None
    stamp = pd.Timestamp(session_date).strftime("%Y%m%d_%H%M%S")
    return root / project_name / "videos" / mouse_name / f"{mouse_name}_{task}_{stamp}.mp4"


def video_folder(project_name: str, mouse_name: str) -> Optional[Path]:
    """
    Folder with the videos of a mouse (<project>/videos/<mouse>), or None if
    the project or the mouse is not one of the data folder (so that only
    videos of the data folder can be sent).
    """
    root = get_data_path()
    if root is None or project_name not in get_list_of_projects() or mouse_name not in get_list_of_mice(project_name):
        return None
    folder = root / project_name / "videos" / mouse_name
    return folder if folder.is_dir() else None


def seconds_of_trial(df: pd.DataFrame, session_date: str, trial_number: int) -> Optional[float]:
    """Seconds from the start of the first trial of a session to the start of one of its trials."""
    if df.empty:
        return None
    session = df[df["date"] == pd.Timestamp(session_date)]
    trial = session[session["trial"] == trial_number]
    if session.empty or trial.empty:
        return None
    return float(trial["TRIAL_START"].iloc[0] - session["TRIAL_START"].iloc[0])
