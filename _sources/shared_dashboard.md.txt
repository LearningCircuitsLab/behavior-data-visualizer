# The shared dashboard on the cluster

One Behavior Explorer runs all the time on minibaps2, for everyone. It is
installed once, by the `training_village` user, and kept running and up to
date by a script and two cron jobs. Nobody else needs to install or start
anything.

## Using it

From your computer, open a tunnel to the cluster (with your own user, any
user of the cluster can use it):

```bash
ssh -L 8050:localhost:8050 <your user>@minibaps2
```

and open <http://localhost:8050>. Several people can use it at the same
time: each browser has its own choices (project, mouse, day, zoom, video).
The trials of a mouse are read once and shared, so a mouse someone opened
before is fast for everyone.

<http://localhost:8050/status> shows the code it runs (the commit), since
when, and the mice in memory.

If the page does not load:

- the tunnel must be open (the `ssh -L` command above, in a terminal that
  stays open),
- if something else on your computer uses port 8050, use another local port:
  `ssh -L 8060:localhost:8050 <your user>@minibaps2` and open
  <http://localhost:8060>,
- the dashboard may be restarting (after an update, for a few seconds), or
  stopped: the cron job starts it again within 5 minutes.

It is only reachable from the cluster (it listens on localhost) and has no
password: anyone who can log in to the cluster can use it.

## Looking after it (as `training_village`)

### Install it once

```bash
cd ~/Github
git clone https://github.com/LearningCircuitsLab/behavior-data-visualizer.git
```

The python is `/home/training_village/miniconda3/bin/python`, with
lecilab-behavior-analysis installed from its clone in `~/Github` (editable,
so that it is updated by pulling it). Install the dashboard without its
dependencies (otherwise pip would replace that lecilab-behavior-analysis with
a copy from GitHub), and then its other dependencies:

```bash
PY=/home/training_village/miniconda3/bin/python
$PY -m pip install -e ~/Github/lecilab-behavior-analysis
$PY -m pip install -e ~/Github/behavior-data-visualizer --no-deps
$PY -m pip install dash flask matplotlib numpy pandas plotly waitress
$PY -c "import dash, waitress, lecilab_behavior_analysis; print('ok')"
```

The two clones must be on `main` to be updated automatically.

### Start, stop, check

```bash
export BDV_PYTHON=/home/training_village/miniconda3/bin/python
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
BDV_PYTHON=/home/training_village/miniconda3/bin/python
# start it if it is not running (after a crash or a reboot)
*/5 * * * * /home/training_village/Github/behavior-data-visualizer/scripts/dashboard_service.sh ensure
@reboot /home/training_village/Github/behavior-data-visualizer/scripts/dashboard_service.sh ensure
# pull main of both repositories, and restart if the code changed
30 7 * * * /home/training_village/Github/behavior-data-visualizer/scripts/dashboard_service.sh update
```

`update` pulls `main` of behavior-data-visualizer and of the clone of
lecilab-behavior-analysis that the python uses (only if they are on `main`
and have no changes) and restarts the dashboard if either changed. To update
it right away, run `dashboard_service.sh update` by hand.

### Settings

Environment variables (in the crontab, or exported before running the
script):

- `BDV_PYTHON`: the python (default: `python`),
- `BDV_PORT`: the port (default: 8050),
- `BDV_CACHE_GB`: memory for the trials of the mice opened, all users together,
  in GB (default: 4; the trials of a mouse with a long history can take close
  to 1 GB),
- `BDV_STATE_DIR`: where the log and the process id are kept.

### Trying a branch

Anyone can run their own dashboard (from their own clone) on another port,
without stopping the shared one:

```bash
python behavior_data_visualizer/main.py --port 8060
```

and open a tunnel to that port.
