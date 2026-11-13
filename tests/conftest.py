"""
The tests read tests/data/sample_data, a data folder with two projects:

- visual_and_COT_data, mouse ACV008: a habituation day (2025-03-15), a
  visual day (2025-06-02), a cloud-of-tones day (2025-06-18) and a
  multisensory day (2025-09-09), all with easy, medium and hard trials
  except habituation and the multisensory day (easy only);
- frequency_vs_locationPureTone_data, mouse NUO077: two days of sound
  location (2026-11-09 and 2026-11-10), with the loudness of each sound.
"""

import matplotlib

matplotlib.use("Agg")

from pathlib import Path

import pytest

SAMPLE_DATA = Path(__file__).parent / "data" / "sample_data"
VISUAL_COT = ("visual_and_COT_data", "ACV008")
LOCATION = ("frequency_vs_locationPureTone_data", "NUO077")


@pytest.fixture(autouse=True)
def sample_data(monkeypatch):
    """Read the sample data folder, with an empty cache."""
    from behavior_data_visualizer import data

    monkeypatch.setenv("LECILAB_DATA_PATH", str(SAMPLE_DATA))
    data._load_mouse_data.cache_clear()
    data._load_events.cache_clear()
    yield SAMPLE_DATA


@pytest.fixture
def visual_cot():
    from behavior_data_visualizer import data

    return data.load_mouse_data(*VISUAL_COT)


@pytest.fixture
def location():
    from behavior_data_visualizer import data

    return data.load_mouse_data(*LOCATION)
