# Running the shared dashboard (cluster)

One Behavior Explorer runs all the time on minibaps2, port 8055, for
everyone. It is installed once, by the `training_village` user, and kept
running and up to date by a script and cron jobs. This page is for whoever
looks after it; to use it, see [use it from your computer](connect.md).

## Looking after it (as `training_village`)

### Install it once

```bash
cd ~/Github
git clone https://github.com/LearningCircuitsLab/behavior-data-visualizer.git
```

The python is the one of the `report` conda environment,
`/home/training_village/miniconda3/envs/report/bin/python`. It is used by its
full path, so the environment does not need to be activated (neither here nor
in cron). Find it with `conda activate report; which python`. It runs with
lecilab-behavior-analysis installed from its clone in `~/Github` (editable,
so that it is updated by pulling it). Install the dashboard without its
dependencies (otherwise pip would replace that lecilab-behavior-analysis with
a copy from GitHub), and then its other dependencies:

```bash
PY=/home/training_village/miniconda3/envs/report/bin/python
$PY -m pip install -e ~/Github/lecilab-behavior-analysis
$PY -m pip install -e ~/Github/behavior-data-visualizer --no-deps
$PY -m pip install dash flask matplotlib numpy pandas plotly waitress
$PY -c "import dash, waitress, lecilab_behavior_analysis; print('ok')"
```

The two clones must be on `main` to be updated automatically.

Check which lecilab-behavior-analysis the python uses **from your home folder**
(inside the clone's folder, python finds the clone even if it is not the one
installed). It must print a path in `~/Github/lecilab-behavior-analysis`:

```bash
cd ~ && $PY -c "import lecilab_behavior_analysis as l; print(l.__file__)"
```

### Start, stop, check

```bash
export BDV_PYTHON=/home/training_village/miniconda3/envs/report/bin/python
~/Github/behavior-data-visualizer/scripts/dashboard_service.sh start
~/Github/behavior-data-visualizer/scripts/dashboard_service.sh status
~/Github/behavior-data-visualizer/scripts/dashboard_service.sh stop
~/Github/behavior-data-visualizer/scripts/dashboard_service.sh restart
```

It runs in the background (it keeps running after logging out), with the
code of `~/Github/behavior-data-visualizer`. Its log is
`~/.local/state/behavior-explorer/dashboard.log`.

### Keep it running and up to date (cron)

Add these lines with `crontab -e` (as `training_village`):

```text
BDV_PYTHON=/home/training_village/miniconda3/envs/report/bin/python
# start it if it is not running (after a crash or a reboot)
*/5 * * * * /home/training_village/Github/behavior-data-visualizer/scripts/dashboard_service.sh ensure
@reboot /home/training_village/Github/behavior-data-visualizer/scripts/dashboard_service.sh ensure
# every night at 4: pull main of both repositories and restart (frees the memory)
0 4 * * * /home/training_village/Github/behavior-data-visualizer/scripts/dashboard_service.sh nightly
```

`nightly` pulls `main` of behavior-data-visualizer and of the clone of
lecilab-behavior-analysis that the python uses (only if they are on `main`
and have no changes) and restarts the dashboard: it runs the latest code, and
the memory taken by the mice opened during the day is freed (python does not
always give memory back to the system while it runs). Anyone using it at 4 am
loses the page for a few seconds (reload it).

To update it right away, run `dashboard_service.sh update` by hand: it
pulls and restarts only if the code changed.

### What it costs

Without anyone using it, the dashboard takes about 220 MB of memory and
almost no processor (about 0.01 s of CPU per minute): it only waits for
connections. When people open mice, their trials stay in memory (up to
`BDV_CACHE_GB`, 4 GB by default, all users together) until the nightly
restart. The cron job that checks it every 5 minutes takes a fraction of a
second.

### Settings

Environment variables (in the crontab, or exported before running the
script):

- `BDV_PYTHON`: the python (default: `python`),
- `BDV_PORT`: the port (default: 8055; personal dashboards use 8050),
- `BDV_CACHE_GB`: memory for the trials of the mice opened, all users together,
  in GB (default: 4; the trials of a mouse with a long history can take close
  to 1 GB),
- `BDV_STATE_DIR`: where the log and the process id are kept.

### Trying a branch

Anyone can run their own dashboard (from their own clone) without stopping the
shared one: it uses port 8050 by default (`--port` for another one):

```bash
python behavior_data_visualizer/main.py
```

and open a tunnel to that port (e.g. `ssh -N -L 8050:127.0.0.1:8050 <your
entry for minibaps2>`).
