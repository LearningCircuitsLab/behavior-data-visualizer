"""The script that keeps the shared dashboard running (scripts/dashboard_service.sh)."""

import os
import shutil
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

from tests.conftest import SAMPLE_DATA

SCRIPT = Path(__file__).parents[2] / "scripts" / "dashboard_service.sh"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None, reason="the script runs on the cluster (bash)"
)


def free_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]


@pytest.fixture
def service(tmp_path):
    env = {
        **os.environ,
        "BDV_PYTHON": sys.executable,
        "BDV_PORT": str(free_port()),
        "BDV_STATE_DIR": str(tmp_path / "state"),
        "LECILAB_DATA_PATH": str(SAMPLE_DATA),
    }

    def run(command: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(SCRIPT), command], env=env, capture_output=True, text=True, timeout=120)

    yield run, tmp_path / "state"
    run("stop")


def test_start_status_stop(service):
    run, state = service
    started = run("start")
    assert started.returncode == 0, started.stdout + started.stderr + (state / "dashboard.log").read_text()
    assert "Running (process" in started.stdout
    assert "Already running" in run("start").stdout
    status = run("status")
    assert status.returncode == 0 and "Running (process" in status.stdout
    stopped = run("stop")
    assert stopped.returncode == 0
    assert run("status").returncode == 1


def test_ensure_starts_it_again_after_a_crash(service):
    run, state = service
    assert run("start").returncode == 0
    os.kill(int((state / "dashboard.pid").read_text()), 9)
    ensured = run("ensure")
    assert "Not running: starting it" in ensured.stdout and "Running (process" in ensured.stdout
    assert run("ensure").stdout == ""  # running: nothing to do


def test_usage():
    result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 2
    for command in ("start", "stop", "restart", "status", "ensure", "update", "nightly"):
        assert f"dashboard_service.sh {command}" in result.stdout
    assert "It runs in the background" not in result.stdout


def test_nightly_restarts_it(service):
    """Every night: a new process (the memory of the mice opened that day is freed)."""
    run, state = service
    assert run("start").returncode == 0
    before = (state / "dashboard.pid").read_text()
    nightly = run("nightly")
    assert "Nightly restart" in nightly.stdout and "Running (process" in nightly.stdout, nightly.stdout
    assert (state / "dashboard.pid").read_text() != before


def test_start_fails_when_the_port_is_in_use(service):
    """It says so (instead of "Running") when the dashboard stops after loading."""
    run, state = service
    port = int(run("start").stdout.split("http://127.0.0.1:")[1].split()[0])
    run("stop")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", port))
        listener.listen()
        started = run("start")
    assert started.returncode == 1 and "Running" not in started.stdout
    assert "is in use" in started.stdout


def test_restart_right_after_serving_pages(service):
    """Closed connections keep the port for a while: the dashboard must still start again."""
    run, state = service
    assert run("start").returncode == 0
    status = run("status").stdout
    port = status.split("http://127.0.0.1:")[1].split()[0]
    for _ in range(3):
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=10) as page:
            assert page.read().startswith(b"Behavior Explorer")
    restarted = run("restart")
    assert "Running (process" in restarted.stdout, restarted.stdout + (state / "dashboard.log").read_text()


def test_python_is_remembered(service, tmp_path):
    """Restarting without BDV_PYTHON (e.g. from conda's base) keeps the python of the last start."""
    run, state = service
    assert run("start").returncode == 0
    assert (state / "python").read_text().strip() == sys.executable
    env_without_python = {k: v for k, v in os.environ.items() if k != "BDV_PYTHON"}
    env_without_python.update(BDV_STATE_DIR=str(state), LECILAB_DATA_PATH=str(SAMPLE_DATA))
    port = run("status").stdout.split("http://127.0.0.1:")[1].split()[0]
    env_without_python["BDV_PORT"] = port
    status = subprocess.run(
        ["bash", str(SCRIPT), "status"], env=env_without_python, capture_output=True, text=True, timeout=60
    )
    assert f"python of the next start: {sys.executable}" in status.stdout
    restarted = subprocess.run(
        ["bash", str(SCRIPT), "restart"], env=env_without_python, capture_output=True, text=True, timeout=120
    )
    assert "Running (process" in restarted.stdout
    assert f"with {sys.executable}" in (state / "dashboard.log").read_text().splitlines()[-2]


def test_a_python_without_the_settings_of_lecilab_is_refused(service, tmp_path):
    """e.g. the python of conda's base with an old lecilab_behavior_analysis."""
    run, state = service
    fake = tmp_path / "old_python"
    fake.write_text(f'#!/bin/bash\ncase "$*" in *io.settings*) exit 1;; esac\nexec {sys.executable} "$@"\n')
    fake.chmod(0o755)
    env = {**os.environ, "BDV_PYTHON": str(fake), "BDV_STATE_DIR": str(state), "LECILAB_DATA_PATH": str(SAMPLE_DATA)}
    result = subprocess.run(["bash", str(SCRIPT), "start"], env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 1 and "too old" in result.stdout
