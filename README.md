# behavior-data-visualizer

The Training Village Behavior Explorer: a web dashboard to look at the
behavior of the mice of a project, day by day. It reads the same data as the
daily reports
([village-report-generator](https://github.com/LearningCircuitsLab/village-report-generator)),
with [lecilab-behavior-analysis](https://github.com/LearningCircuitsLab/lecilab-behavior-analysis).

- A calendar of the days with trials of a mouse: click a day to see it.
- For that day: a summary, the performance through its trials (click a
  point to watch the video of that trial) and the psychometric curves, one
  per stimulus modality.
- Trial by trial: stimulus and correct side, outcome and early pokeouts of
  each trial (click a trial to watch its video).
- Zooming on some trials in the performance or the trial-by-trial figure
  zooms the other one, and the psychometric curves use only those trials.
- Buttons to draw the figures of the daily report: the session report of the
  day and the training history up to it.

## Running it

Python 3.11 or newer, with this package and lecilab-behavior-analysis
installed (`pip install -e .` in each repository):

```bash
python behavior_data_visualizer/main.py
```

Then open <http://127.0.0.1:8050>. The data folder is the one of
lecilab-behavior-analysis (the `LECILAB_DATA_PATH` environment variable, or
the folder of the computer). To try it on the small sample dataset of the
tests:

```bash
LECILAB_DATA_PATH=tests/data/sample_data python behavior_data_visualizer/main.py
```

See `docs/source/getting_started.md` for the details.

## Development

```bash
pip install -e ".[dev]"
pytest
pre-commit run --all-files
```

The code is in `behavior_data_visualizer/`: `data.py` reads the data,
`figures.py` makes the figures and `main.py` is the app (layout and
callbacks).
