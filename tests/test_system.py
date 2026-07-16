"""Tests for linkjumper.system — /etc/hosts, loopback, launchd."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

from linkjumper.system import add_hosts_entry, build_plist, has_hosts_entry


# ---------------------------------------------------------------------------
# has_hosts_entry (regex matching against /etc/hosts content)
# ---------------------------------------------------------------------------


def test_has_hosts_entry_true(monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda self: "127.0.0.2\tgo\n")
    assert has_hosts_entry("go") is True


def test_has_hosts_entry_false(monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda self: "127.0.0.1\tlocalhost\n")
    assert has_hosts_entry("go") is False


def test_has_hosts_entry_partial_no_match(monkeypatch):
    """'goat' must NOT match the prefix 'go' — the regex anchors with $."""
    monkeypatch.setattr(Path, "read_text", lambda self: "127.0.0.2\tgoat\n")
    assert has_hosts_entry("go") is False


# ---------------------------------------------------------------------------
# add_hosts_entry (delegates to has_hosts_entry + subprocess)
# ---------------------------------------------------------------------------


def test_add_hosts_entry_when_missing(monkeypatch):
    monkeypatch.setattr("linkjumper.system.has_hosts_entry", lambda p: False)
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("subprocess.run", mock_run)

    result = add_hosts_entry("go")

    assert result is True
    mock_run.assert_called_once()


def test_add_hosts_entry_when_present(monkeypatch):
    monkeypatch.setattr("linkjumper.system.has_hosts_entry", lambda p: True)
    mock_run = MagicMock()
    monkeypatch.setattr("subprocess.run", mock_run)

    result = add_hosts_entry("go")

    assert result is False
    mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# build_plist
# ---------------------------------------------------------------------------


def test_build_plist_contains_label():
    xml = build_plist()
    assert "com.linkjumper.redirect" in xml
    assert "linkjumper.server" in xml
    assert "PYTHONPATH" in xml


def test_build_plist_defaults_to_sys_executable(monkeypatch):
    monkeypatch.delenv("LINKJUMPER_PYTHON", raising=False)
    xml = build_plist()
    assert sys.executable in xml


def test_build_plist_prefers_linkjumper_python_env(monkeypatch):
    """The brew wrapper sets LINKJUMPER_PYTHON to the stable opt/python@3
    alias path; the plist must use it instead of the resolved interpreter."""
    monkeypatch.setenv("LINKJUMPER_PYTHON", "/opt/homebrew/opt/python@3/bin/python3")
    xml = build_plist()
    assert "/opt/homebrew/opt/python@3/bin/python3" in xml
    assert sys.executable not in xml
