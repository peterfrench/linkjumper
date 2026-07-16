"""Tests for linkjumper.cli — command handlers."""

import argparse
from pathlib import Path

import pytest

from linkjumper import config
from linkjumper.cli import (
    cmd_add, cmd_config, cmd_list, cmd_remove, cmd_restart, cmd_start,
    cmd_stop,
)


def _proc(returncode, stdout="", stderr=""):
    return type("R", (), {
        "returncode": returncode, "stdout": stdout, "stderr": stderr,
    })()


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------


def test_cmd_list_shows_redirects(tmp_project_dir, tmp_webloc_dir, sample_redirects, capsys):
    config.save_redirects(sample_redirects)
    args = argparse.Namespace()
    cmd_list(args)
    out = capsys.readouterr().out
    assert "gh" in out
    assert "mail" in out
    assert "github.com" in out


def test_cmd_list_empty(tmp_project_dir, tmp_webloc_dir, capsys):
    config.save_redirects({})
    args = argparse.Namespace()
    cmd_list(args)
    out = capsys.readouterr().out
    assert "No redirects configured" in out


# ---------------------------------------------------------------------------
# cmd_add
# ---------------------------------------------------------------------------


def test_cmd_add_new_key(tmp_project_dir, tmp_webloc_dir, capsys):
    config.save_redirects({})
    args = argparse.Namespace(key="gh", url="https://github.com")
    cmd_add(args)

    redirects = config.load_redirects()
    assert redirects["gh"] == "https://github.com"

    out = capsys.readouterr().out
    assert "Added" in out

    # webloc file should be created
    assert (tmp_webloc_dir / "go gh.webloc").exists()


def test_cmd_add_updates_existing(tmp_project_dir, tmp_webloc_dir, capsys):
    config.save_redirects({"gh": "https://old.example.com"})
    args = argparse.Namespace(key="gh", url="https://github.com")
    cmd_add(args)

    redirects = config.load_redirects()
    assert redirects["gh"] == "https://github.com"

    out = capsys.readouterr().out
    assert "Updated" in out
    assert "old.example.com" in out


# ---------------------------------------------------------------------------
# cmd_remove
# ---------------------------------------------------------------------------


def test_cmd_remove_deletes_key(tmp_project_dir, tmp_webloc_dir, capsys):
    config.save_redirects({"gh": "https://github.com"})
    # Pre-create the webloc file
    from linkjumper.webloc import create_webloc
    create_webloc("go", "gh", "https://github.com")

    args = argparse.Namespace(key="gh")
    cmd_remove(args)

    assert "gh" not in config.load_redirects()
    assert not (tmp_webloc_dir / "go gh.webloc").exists()


def test_cmd_remove_missing_key_exits(tmp_project_dir, tmp_webloc_dir):
    config.save_redirects({})
    args = argparse.Namespace(key="missing")
    with pytest.raises(SystemExit):
        cmd_remove(args)


# ---------------------------------------------------------------------------
# cmd_config
# ---------------------------------------------------------------------------


def test_cmd_config_shows_current(tmp_project_dir, capsys):
    config.save_settings({"prefix": "go"})
    args = argparse.Namespace(prefix=None, auto_open=None)
    cmd_config(args)
    out = capsys.readouterr().out
    assert "go" in out


def test_cmd_config_validates_prefix(tmp_project_dir):
    args = argparse.Namespace(prefix="123bad!", auto_open=None)
    with pytest.raises(SystemExit):
        cmd_config(args)


def test_cmd_config_changes_prefix(
    tmp_project_dir, tmp_webloc_dir, sample_redirects, monkeypatch, capsys
):
    config.save_settings({"prefix": "go"})
    config.save_redirects(sample_redirects)
    # cmd_config checks for ca.pem
    (tmp_project_dir / "certs" / "ca.pem").write_text("fake-ca")

    # Mock system/cert functions that are imported by name into cli
    monkeypatch.setattr("linkjumper.cli.remove_hosts_entry", lambda p: True)
    monkeypatch.setattr("linkjumper.cli.add_hosts_entry", lambda p: True)
    monkeypatch.setattr("linkjumper.cli.flush_dns", lambda: None)
    monkeypatch.setattr("linkjumper.cli.sign_server_cert", lambda p: None)
    # Mock the direct subprocess calls (launchctl restart)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
    )

    args = argparse.Namespace(prefix="mylinks", auto_open=None)
    cmd_config(args)

    # settings.json should reflect the new prefix
    settings = config.load_settings()
    assert settings["prefix"] == "mylinks"


# ---------------------------------------------------------------------------
# cmd_start / cmd_stop
# ---------------------------------------------------------------------------


def test_cmd_start_success(monkeypatch, capsys):
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: _proc(0))
    cmd_start(argparse.Namespace())
    assert "started" in capsys.readouterr().out


def test_cmd_start_no_plist_suggests_setup(monkeypatch, capsys):
    monkeypatch.setattr(Path, "exists", lambda self: False)
    with pytest.raises(SystemExit):
        cmd_start(argparse.Namespace())
    assert "sudo linkjumper setup" in capsys.readouterr().out


def test_cmd_start_already_loaded_eio_and_running(monkeypatch, capsys):
    """Newer macOS reports an already-loaded service as EIO (5)."""
    monkeypatch.setattr(Path, "exists", lambda self: True)

    def fake_run(cmd, **kw):
        if "bootstrap" in cmd:
            return _proc(5, stderr="Bootstrap failed: 5: Input/output error")
        return _proc(0, stdout="\tpid = 1234\n")  # launchctl print

    monkeypatch.setattr("subprocess.run", fake_run)
    cmd_start(argparse.Namespace())
    assert "already running (pid 1234)" in capsys.readouterr().out


def test_cmd_start_loaded_but_dead_suggests_setup(monkeypatch, capsys):
    """Loaded but crash-looping (e.g. stale interpreter path in the plist)."""
    monkeypatch.setattr(Path, "exists", lambda self: True)

    def fake_run(cmd, **kw):
        if "bootstrap" in cmd:
            return _proc(5, stderr="Bootstrap failed: 5: Input/output error")
        return _proc(0, stdout="\tstate = not running\n")  # no pid line

    monkeypatch.setattr("subprocess.run", fake_run)
    with pytest.raises(SystemExit):
        cmd_start(argparse.Namespace())
    assert "sudo linkjumper setup" in capsys.readouterr().out


def test_cmd_start_already_loaded_old_macos(monkeypatch, capsys):
    monkeypatch.setattr(Path, "exists", lambda self: True)

    def fake_run(cmd, **kw):
        if "bootstrap" in cmd:
            return _proc(37, stderr="service already loaded")
        return _proc(0, stdout="\tpid = 99\n")

    monkeypatch.setattr("subprocess.run", fake_run)
    cmd_start(argparse.Namespace())
    assert "already running" in capsys.readouterr().out


def test_cmd_stop_success(monkeypatch, capsys):
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: _proc(0))
    cmd_stop(argparse.Namespace())
    assert "stopped" in capsys.readouterr().out


def test_cmd_stop_not_running_esrch(monkeypatch, capsys):
    """Newer macOS reports a not-loaded service as ESRCH (3)."""
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: _proc(3, stderr="Boot-out failed: 3: No such process"),
    )
    cmd_stop(argparse.Namespace())
    assert "not running" in capsys.readouterr().out


def test_cmd_stop_not_running_old_macos(monkeypatch, capsys):
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: _proc(113, stderr="Could not find service"),
    )
    cmd_stop(argparse.Namespace())
    assert "not running" in capsys.readouterr().out


def test_cmd_restart_stops_then_starts(monkeypatch, capsys):
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr("linkjumper.cli.time.sleep", lambda s: None)
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return _proc(0)

    monkeypatch.setattr("subprocess.run", fake_run)
    cmd_restart(argparse.Namespace())
    out = capsys.readouterr().out
    assert "stopped" in out
    assert "started" in out
    assert any("bootout" in c for c in calls)
    assert any("bootstrap" in c for c in calls)


def test_cmd_restart_when_not_running_still_starts(monkeypatch, capsys):
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr("linkjumper.cli.time.sleep", lambda s: None)

    def fake_run(cmd, **kw):
        if "bootout" in cmd:
            return _proc(3, stderr="Boot-out failed: 3: No such process")
        return _proc(0)

    monkeypatch.setattr("subprocess.run", fake_run)
    cmd_restart(argparse.Namespace())
    out = capsys.readouterr().out
    assert "not running" in out
    assert "started" in out


def test_cmd_stop_other_failure_exits(monkeypatch, capsys):
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: _proc(1, stderr="Boot-out failed: 150: whatever"),
    )
    with pytest.raises(SystemExit):
        cmd_stop(argparse.Namespace())
    assert "Failed to stop" in capsys.readouterr().out
