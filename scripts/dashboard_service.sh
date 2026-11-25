#!/usr/bin/env bash
# Keeps one shared Behavior Explorer running on this computer, for everyone.
#
#   scripts/dashboard_service.sh start     start it (if it is not running)
#   scripts/dashboard_service.sh stop      stop it
#   scripts/dashboard_service.sh restart   stop it and start it again
#   scripts/dashboard_service.sh status    is it running, and with which code
#   scripts/dashboard_service.sh ensure    start it if it is not running (for cron)
#   scripts/dashboard_service.sh update    pull main of this repository and of
#                                          lecilab-behavior-analysis, and restart
#                                          if the code changed
#   scripts/dashboard_service.sh nightly   pull main of both and restart, always
#                                          (for cron, at night: it also frees the
#                                          memory of the mice opened that day)
#
# It runs in the background (it keeps running after logging out), with the
# code of this folder. Settings (environment variables):
#
#   BDV_PYTHON     python with the dependencies installed. It is remembered:
#                  without it, the python of the last start is used (or
#                  "python" the first time)
#   BDV_PORT       port (default: 8055; 8050 is left for personal dashboards)
#   BDV_STATE_DIR  where the log and the process id are kept
#                  (default: ~/.local/state/behavior-explorer)
#
# See docs/source/shared_dashboard.md.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${BDV_PORT:-8055}"
STATE_DIR="${BDV_STATE_DIR:-$HOME/.local/state/behavior-explorer}"
PID_FILE="$STATE_DIR/dashboard.pid"
LOG_FILE="$STATE_DIR/dashboard.log"
VERSIONS_FILE="$STATE_DIR/versions"
PYTHON_FILE="$STATE_DIR/python"

mkdir -p "$STATE_DIR"

# the python: BDV_PYTHON, or the one of the last start (so that running the
# script from another environment, e.g. conda's base, does not change it)
if [ -n "${BDV_PYTHON:-}" ]; then
    PYTHON="$BDV_PYTHON"
elif [ -s "$PYTHON_FILE" ]; then
    PYTHON="$(cat "$PYTHON_FILE")"
else
    PYTHON="python"
fi

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG_FILE"; }

running_pid() {
    # the process id of the dashboard, if it is running
    [ -f "$PID_FILE" ] || return 1
    local pid
    pid="$(cat "$PID_FILE")"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null || return 1
    ps -p "$pid" -o args= 2>/dev/null | grep -q "behavior_data_visualizer" || return 1
    echo "$pid"
}

lecilab_folder() {
    # the git clone of lecilab-behavior-analysis used by this python (if it is one)
    local package
    package="$("$PYTHON" -c 'import lecilab_behavior_analysis, os; print(os.path.dirname(lecilab_behavior_analysis.__file__))' 2>/dev/null)" || return 1
    git -C "$package/.." rev-parse --show-toplevel 2>/dev/null
}

versions() {
    # commits of the code the dashboard runs: this repository and lecilab-behavior-analysis
    echo "behavior-data-visualizer $(git -C "$REPO" rev-parse HEAD 2>/dev/null)"
    local lecilab
    if lecilab="$(lecilab_folder)"; then
        echo "lecilab-behavior-analysis $(git -C "$lecilab" rev-parse HEAD 2>/dev/null)"
    fi
}

start() {
    local pid
    if pid="$(running_pid)"; then
        echo "Already running (process $pid): http://127.0.0.1:$PORT"
        return 0
    fi
    if ! (cd "$REPO" && "$PYTHON" -c 'import dash, waitress, lecilab_behavior_analysis') 2>/dev/null; then
        log "Cannot start: $PYTHON does not have the dependencies (dash, waitress, lecilab_behavior_analysis)."
        return 1
    fi
    # the version of lecilab_behavior_analysis this code needs (its session settings)
    # (from the folder the dashboard runs in: a clone in the current folder would hide the installed copy)
    if ! (cd "$REPO" && "$PYTHON" -c 'import lecilab_behavior_analysis.io.settings') 2>/dev/null; then
        log "Cannot start: the lecilab_behavior_analysis of $PYTHON is too old (pull its main and install it" \
            "with this python), or this is not the right python (set BDV_PYTHON)."
        return 1
    fi
    echo "$PYTHON" > "$PYTHON_FILE"
    log "Starting on port $PORT with $PYTHON"
    # -m from this folder: the code of this folder, whatever copy is installed
    # (nohup: it keeps running after logging out)
    (
        cd "$REPO" || exit 1
        nohup "$PYTHON" -m behavior_data_visualizer --port "$PORT" >>"$LOG_FILE" 2>&1 < /dev/null &
        echo $! > "$PID_FILE"
    )
    versions > "$VERSIONS_FILE"
    # loading the code takes a few seconds: wait until it answers (or stops)
    for _ in $(seq 90); do
        sleep 1
        if ! pid="$(running_pid)"; then
            log "It stopped right after starting: see the end of $LOG_FILE"
            tail -n 5 "$LOG_FILE"
            return 1
        fi
        if answers; then
            echo "Running (process $pid): http://127.0.0.1:$PORT"
            return 0
        fi
    done
    log "Started (process $pid) but not answering yet on port $PORT: see $LOG_FILE"
    return 1
}

answers() {
    # whether the dashboard answers on its status page
    if command -v curl >/dev/null; then
        curl -s -o /dev/null --max-time 3 "http://127.0.0.1:$PORT/status"
    else
        "$PYTHON" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$PORT/status', timeout=3)" 2>/dev/null
    fi
}

stop() {
    local pid
    if ! pid="$(running_pid)"; then
        echo "Not running."
        rm -f "$PID_FILE"
        return 0
    fi
    log "Stopping process $pid"
    kill "$pid"
    for _ in $(seq 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
    done
    if kill -0 "$pid" 2>/dev/null; then
        log "Still running: forcing it to stop"
        kill -9 "$pid"
    fi
    rm -f "$PID_FILE"
}

status() {
    local pid
    if pid="$(running_pid)"; then
        echo "Running (process $pid): http://127.0.0.1:$PORT"
        echo "python of the next start: $PYTHON"
        if command -v curl >/dev/null; then
            curl -s --max-time 5 "http://127.0.0.1:$PORT/status" || echo "(no answer from /status)"
        fi
    else
        echo "Not running."
        return 1
    fi
}

pull_main() {
    # fast-forwards a clone to origin/main, if it is on main and has no changes
    local folder="$1"
    local branch
    branch="$(git -C "$folder" rev-parse --abbrev-ref HEAD 2>/dev/null)" || return 0
    if [ "$branch" != "main" ]; then
        log "Not updating $folder: it is on branch $branch, not main"
        return 0
    fi
    if [ -n "$(git -C "$folder" status --porcelain --untracked-files=no)" ]; then
        log "Not updating $folder: it has changes that are not committed"
        return 0
    fi
    git -C "$folder" pull --ff-only --quiet origin main >>"$LOG_FILE" 2>&1 || log "Could not update $folder (see the log)"
}

update() {
    pull_main "$REPO"
    local lecilab
    if lecilab="$(lecilab_folder)"; then
        pull_main "$lecilab"
    fi
    if ! running_pid >/dev/null; then
        start
    elif [ "$(versions)" != "$(cat "$VERSIONS_FILE" 2>/dev/null)" ]; then
        log "The code changed: restarting"
        stop
        start
    fi
}

nightly() {
    pull_main "$REPO"
    local lecilab
    if lecilab="$(lecilab_folder)"; then
        pull_main "$lecilab"
    fi
    log "Nightly restart"
    stop
    start
}

case "${1:-}" in
    start) start ;;
    stop) stop ;;
    restart) stop; start ;;
    status) status ;;
    ensure) running_pid >/dev/null || { log "Not running: starting it"; start; } ;;
    update) update ;;
    nightly) nightly ;;
    *)
        sed -n '2,/^# It runs in the background/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
        exit 2
        ;;
esac
