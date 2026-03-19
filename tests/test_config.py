"""Tests for linkjumper.config — JSON I/O, defaults, roundtrips."""

import json

from linkjumper.config import (
    get_prefix,
    load_redirects,
    load_settings,
    save_redirects,
    save_settings,
)


def test_load_settings_default(tmp_project_dir):
    """Returns {"prefix": "go"} when the file is missing."""
    assert load_settings() == {"prefix": "go"}


def test_load_settings_reads_json(tmp_project_dir):
    """Reads a custom prefix from disk."""
    (tmp_project_dir / "config.json").write_text('{"prefix": "links"}')
    assert load_settings() == {"prefix": "links"}


def test_load_settings_invalid_json(tmp_project_dir):
    """Returns default on malformed JSON."""
    (tmp_project_dir / "config.json").write_text("{not valid json!!!")
    assert load_settings() == {"prefix": "go"}


def test_save_settings_roundtrip(tmp_project_dir):
    """save then load returns same data."""
    data = {"prefix": "mylinks", "extra": 42}
    save_settings(data)
    assert load_settings() == data


def test_load_redirects_empty(tmp_project_dir):
    """Returns {} when the file is missing."""
    assert load_redirects() == {}


def test_load_redirects_reads_json(tmp_project_dir):
    """Reads redirects from disk."""
    data = {"gh": "https://github.com"}
    (tmp_project_dir / "redirects.json").write_text(json.dumps(data))
    assert load_redirects() == data


def test_save_redirects_roundtrip(tmp_project_dir):
    data = {"gh": "https://github.com", "mail": "https://mail.google.com"}
    save_redirects(data)
    assert load_redirects() == data


def test_get_prefix_default(tmp_project_dir):
    assert get_prefix() == "go"


def test_get_prefix_custom(tmp_project_dir):
    save_settings({"prefix": "links"})
    assert get_prefix() == "links"
