# behavior-data-visualizer

> **To use the Behavior Explorer from your computer, follow
> [Use it from your computer](https://learningcircuitslab.github.io/behavior-data-visualizer/connect.html)**
> (set up once, then type `explorer` and open <http://localhost:8055>).

Documentation: <https://learningcircuitslab.github.io/behavior-data-visualizer/>

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

## Running the shared dashboard (cluster)

Installed once by `training_village` and kept running by cron:
[running the shared dashboard](https://learningcircuitslab.github.io/behavior-data-visualizer/shared_dashboard.html).

## Running it yourself

Python 3.11 or newer, with this package and lecilab-behavior-analysis
installed (`pip install -e .` in each repository):

```bash
behavior-explorer
```

(or `python behavior_data_visualizer/main.py`), then open
<http://127.0.0.1:8050>; `--port` to use another port. The data folder is the one of
lecilab-behavior-analysis (the `LECILAB_DATA_PATH` environment variable, or
the folder of the computer). To try it on the small sample dataset of the
tests:

```bash
LECILAB_DATA_PATH=tests/data/sample_data python behavior_data_visualizer/main.py
```

See [getting started](https://learningcircuitslab.github.io/behavior-data-visualizer/getting_started.html) for the details.

## Development

```bash
pip install -e ".[dev]"
pytest
pre-commit run --all-files
```

The code is in `behavior_data_visualizer/`: `data.py` reads the data,
`figures.py` makes the figures and `main.py` is the app (layout and
callbacks).
