import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import orchestrate


def _mock_completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


@patch("orchestrate.run")
@patch("orchestrate.docker_compose")
@patch("orchestrate.wait_for_health", return_value=True)
def test_deploy_success(mock_health, mock_dc, mock_run, tmp_path):
    orchestrate.STATE_DIR = tmp_path
    orchestrate.ACTIVE_COLOR_FILE = tmp_path / "active_color"
    orchestrate.LAST_SWITCH_FILE = tmp_path / "last_switch"
    orchestrate.NGINX_CONF_FILE = tmp_path / "nginx.conf"
    orchestrate.ensure_state()

    orchestrate.deploy()

    dc_calls = [str(c) for c in mock_dc.call_args_list]
    assert any("up" in c and "green-backend" in c for c in dc_calls)
    assert any("up" in c and "green-frontend" in c for c in dc_calls)
    assert any("restart" in c and "nginx" in c for c in dc_calls)
    assert orchestrate.ACTIVE_COLOR_FILE.read_text().strip() == "green"


@patch("orchestrate.run")
@patch("orchestrate.docker_compose")
@patch("orchestrate.wait_for_health", return_value=False)
def test_rollback_on_failure(mock_health, mock_dc, mock_run, tmp_path):
    orchestrate.STATE_DIR = tmp_path
    orchestrate.ACTIVE_COLOR_FILE = tmp_path / "active_color"
    orchestrate.LAST_SWITCH_FILE = tmp_path / "last_switch"
    orchestrate.NGINX_CONF_FILE = tmp_path / "nginx.conf"
    orchestrate.ensure_state()

    try:
        orchestrate.deploy()
    except SystemExit:
        pass

    dc_calls = [str(c) for c in mock_dc.call_args_list]
    rollback_switches = [c for c in dc_calls if "restart" in c and "nginx" in c]
    assert len(rollback_switches) >= 1
    assert orchestrate.ACTIVE_COLOR_FILE.read_text().strip() == "blue"


@patch("orchestrate.docker_compose")
def test_status(mock_dc, tmp_path, capsys):
    orchestrate.STATE_DIR = tmp_path
    orchestrate.ACTIVE_COLOR_FILE = tmp_path / "active_color"
    orchestrate.LAST_SWITCH_FILE = tmp_path / "last_switch"
    orchestrate.NGINX_CONF_FILE = tmp_path / "nginx.conf"
    orchestrate.ensure_state()

    orchestrate.status()

    captured = capsys.readouterr()
    assert "Active environment:" in captured.out
    assert "blue" in captured.out or "green" in captured.out
