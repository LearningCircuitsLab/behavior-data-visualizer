# Getting started

The Behavior Explorer is a web dashboard ([Dash](https://dash.plotly.com/))
to look at the behavior of the mice of the Training Village, day by day. It
reads the same data as the daily reports
([village-report-generator](https://github.com/LearningCircuitsLab/village-report-generator)),
with [lecilab-behavior-analysis](https://github.com/LearningCircuitsLab/lecilab-behavior-analysis).

## Running it

```bash
python behavior_data_visualizer/main.py
```

and open <http://127.0.0.1:8050>. It needs Python 3.11 or newer, with this
package and lecilab-behavior-analysis installed (`pip install -e .` in each
repository).

## The data

The data folder has one folder per project:

- `<project>/sessions/<mouse>/<mouse>.csv` (or `.csv.gz`): the trials of each mouse,
- `<project>/<setup>/events.csv`: the events of each setup (box),
- `<project>/videos/<mouse>/<mouse>_<task>_<YYYYMMDD_HHMMSS>.mp4`: the video of each session.

The dashboard only reads this folder (the videos are sent from it), so any
user who can read the data can run it, even from someone else's copy of the
code.

It is the folder of lecilab-behavior-analysis: the `LECILAB_DATA_PATH`
environment variable if it is set, otherwise the folder of the computer
(`lecilab_behavior_analysis.io.server.get_outpath`), otherwise
`/storage/training_village` or `/archive/training_village`. The folder in use
is shown under the dropdowns. For example, to look at a sample dataset:

```bash
LECILAB_DATA_PATH=tests/data/sample_data python behavior_data_visualizer/main.py
```

## What it shows

1. Choose a project and a mouse. Its trials are read (a few seconds for a
   long history; the last mice opened are kept in memory and read again
   when their file changes).
2. The calendar shows the days with trials (darker: more trials). The last
   day is selected; click another day to see it (framed in red).
3. For the selected day:
   - a summary (sessions, training stages, trials, performance, water),
   - the performance through its trials, with a dashed line at each new
     session. Click a point to watch the video of the session from that trial,
   - the psychometric curves, one per stimulus modality (two in
     multisensory sessions), as in the daily report: by brightness ratio
     (visual), by evidence strength (cloud of tones), by sound level, 3 bins
     per side (sound location), or by side and difficulty when there are only
     easy trials.
   - trial by trial, as a barcode (one tick per trial): the correct side of
     the stimulus (coloured by modality, darker for easier trials), the
     outcome (correct, incorrect, miss) and the early pokeouts, with the
     performance and the early pokeouts of the last 20 trials above. Click a
     trial to watch the video from that trial.
   Zoom on some trials (drag across the performance or the trial-by-trial
   figure) and the other figure shows the same trials, and the
   psychometric curves are made with those trials only (their range is
   shown above them). Double click to see the whole day again.
4. The buttons draw the figures of the daily report: the session report of
   the day and the training history up to the day.
