# The shared dashboard on the cluster

One Behavior Explorer runs all the time on minibaps2, for everyone. It is
installed once, by the `training_village` user, and kept running and up to
date by a script and two cron jobs. Nobody else needs to install or start
anything.

## Using it

The dashboard runs on minibaps2, on port **8055** (a port used only by it).
You reach it through an SSH tunnel from your computer.

### Once: add an entry to your SSH configuration

On your computer, add this to `~/.ssh/config`, with the same address, user
and jump host that you use to log in to minibaps2 (look at your existing
entry for it):

```text
Host explorer
    HostName <address of minibaps2>
    User <your user on the cluster>
    ProxyJump <your entry for the cluster>
    LocalForward 8055 127.0.0.1:8055
```

`LocalForward` connects port 8055 of your computer to port 8055 of
minibaps2, where the dashboard is. Nothing else should use port 8055 on your
computer (your other entries may forward 8050: that is fine).

### Every time

```bash
ssh -N explorer
```

(`-N`: only the tunnel, no shell: the terminal seems to hang, which is
normal; leave it open, stop it with Ctrl+C) and open
<http://localhost:8055>.

### A shortcut: the `explorer` command

Add this to the `~/.bashrc` of your computer (or `~/.zshrc` on a Mac), then
open a new terminal:

```bash
# Behavior Explorer: opens the tunnel to the shared dashboard and prints its address
explorer() {
    local url="http://localhost:8055"
    if (exec 3<>/dev/tcp/127.0.0.1/8055) 2>/dev/null; then
        echo "The tunnel is already open: $url"
        return 0
    fi
    echo "Behavior Explorer: $url   (status: $url/status)"
    echo "Keep this terminal open; Ctrl+C closes the tunnel."
    ssh -N explorer
}
```

Then type `explorer`: it prints the address and opens the tunnel (or, if a
tunnel is already open, only prints the address).

Several people can use it at the same time: each browser has its own
choices (project, mouse, day, zoom, video). The trials of a mouse are read
once and shared, so a mouse someone opened before is fast for everyone.
<http://localhost:8055/status> shows the code it runs (the commit), since
when, and the mice in memory.

If the page does not load:

- the tunnel must be open (`ssh -N explorer`, in a terminal that stays
  open); if ssh says `bind: Address already in use`, something on your
  computer already uses port 8055 (often another `explorer` tunnel that is
  still open: close it),
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
