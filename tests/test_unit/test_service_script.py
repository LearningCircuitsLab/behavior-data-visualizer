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
    assert result.returncode == 2 and "start" in result.stdout and "update" in result.stdout


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
