"""Tests for linkjumper.browsers — detection and instruction formatting."""

from pathlib import Path

from linkjumper.browsers import get_installed_browsers, print_browser_instructions


def test_get_installed_browsers_includes_safari(monkeypatch):
    """Safari (path=None) is always in the result, even if no apps exist."""
    monkeypatch.setattr(Path, "exists", lambda self: False)
    browsers = get_installed_browsers()
    names = [b["name"] for b in browsers]
    assert "Safari" in names


def test_print_browser_instructions_formats_prefix(monkeypatch, capsys):
    """No crash, and the prefix appears in the output."""
    monkeypatch.setattr(Path, "exists", lambda self: False)
    print_browser_instructions("myprefix")
    out = capsys.readouterr().out
    assert "myprefix" in out
