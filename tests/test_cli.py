"""Tests for linkjumper.cli — command handlers."""

import argparse

import pytest

from linkjumper import config
from linkjumper.cli import cmd_add, cmd_config, cmd_list, cmd_remove


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
