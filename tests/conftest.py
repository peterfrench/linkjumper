"""Shared fixtures for LinkJumper tests."""

import http.server
import threading

import pytest

from linkjumper import config
from linkjumper import certs
from linkjumper import cli
from linkjumper import server as server_mod
from linkjumper import system
from linkjumper import webloc


@pytest.fixture
def tmp_project_dir(tmp_path, monkeypatch):
    """Temp directory with config.json, redirects.json, and certs/.

    Monkeypatches PROJECT_DIR, REDIRECTS_PATH, SETTINGS_PATH, CERT_DIR
    in every module that imported them by name.
    """
    redirects_path = tmp_path / "redirects.json"
    settings_path = tmp_path / "config.json"
    cert_dir = tmp_path / "certs"
    cert_dir.mkdir()

    # config module (source of truth)
    monkeypatch.setattr(config, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(config, "REDIRECTS_PATH", redirects_path)
    monkeypatch.setattr(config, "SETTINGS_PATH", settings_path)
    monkeypatch.setattr(config, "CERT_DIR", cert_dir)

    # modules that did `from linkjumper.config import ...`
    monkeypatch.setattr(server_mod, "REDIRECTS_PATH", redirects_path)
    monkeypatch.setattr(server_mod, "SETTINGS_PATH", settings_path)
    monkeypatch.setattr(certs, "CERT_DIR", cert_dir)
    monkeypatch.setattr(system, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(cli, "CERT_DIR", cert_dir)

    return tmp_path


@pytest.fixture
def tmp_webloc_dir(tmp_path, monkeypatch):
    """Create and monkeypatch WEBLOC_DIR."""
    webloc_dir = tmp_path / "LinkJumper"
    monkeypatch.setattr(config, "WEBLOC_DIR", webloc_dir)
    monkeypatch.setattr(webloc, "WEBLOC_DIR", webloc_dir)
    monkeypatch.setattr(cli, "WEBLOC_DIR", webloc_dir)
    return webloc_dir


@pytest.fixture
def sample_redirects():
    return {"gh": "https://github.com", "mail": "https://mail.google.com"}


@pytest.fixture
def http_server(monkeypatch):
    """Start a real HTTP server on a random port.

    Yields (host, port).  Use http.client.HTTPConnection to avoid
    following redirects automatically.
    """
    from linkjumper.server import LinkJumperHandler

    monkeypatch.setattr(server_mod, "prefix", "go")
    monkeypatch.setattr(
        server_mod,
        "redirects",
        {"gh": "https://github.com", "mail": "https://mail.google.com"},
    )

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), LinkJumperHandler)
    host, port = httpd.server_address
    t = threading.Thread(target=httpd.serve_forever)
    t.daemon = True
    t.start()
    yield host, port
    httpd.shutdown()
