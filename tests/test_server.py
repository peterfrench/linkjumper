"""Tests for linkjumper.server — HTTP handler and config reload."""

import http.client

from linkjumper import server as server_mod


# ---------------------------------------------------------------------------
# HTTP-level tests (real server on a random port)
# ---------------------------------------------------------------------------


def test_root_returns_200(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/")
    resp = conn.getresponse()
    body = resp.read().decode()
    assert resp.status == 200
    assert "gh" in body
    conn.close()


def test_redirect_returns_302(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/gh")
    resp = conn.getresponse()
    assert resp.status == 302
    assert resp.getheader("Location") == "https://github.com"
    conn.close()


def test_redirect_strips_trailing_slash(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/gh/")
    resp = conn.getresponse()
    assert resp.status == 302
    assert resp.getheader("Location") == "https://github.com"
    conn.close()


def test_redirect_with_subpath(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/gh/user/repo")
    resp = conn.getresponse()
    assert resp.status == 302
    assert resp.getheader("Location") == "https://github.com/user/repo"
    conn.close()


def test_redirect_with_query_string(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/gh?tab=repos")
    resp = conn.getresponse()
    assert resp.status == 302
    assert resp.getheader("Location") == "https://github.com?tab=repos"
    conn.close()


def test_redirect_with_subpath_and_query(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/gh/user/repo?tab=repos")
    resp = conn.getresponse()
    assert resp.status == 302
    assert resp.getheader("Location") == "https://github.com/user/repo?tab=repos"
    conn.close()


def test_unknown_key_returns_404(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/nope")
    resp = conn.getresponse()
    body = resp.read().decode()
    assert resp.status == 404
    assert "nope" in body
    conn.close()


def test_head_request(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("HEAD", "/gh")
    resp = conn.getresponse()
    assert resp.status == 302
    conn.close()


# ---------------------------------------------------------------------------
# Config reload tests (no HTTP server, just module functions + tmp files)
# ---------------------------------------------------------------------------


def test_server_load_settings_sets_prefix(tmp_project_dir, monkeypatch):
    monkeypatch.setattr(server_mod, "prefix", "go")
    (tmp_project_dir / "config.json").write_text('{"prefix": "links"}')
    server_mod.load_settings()
    assert server_mod.prefix == "links"


def test_server_load_redirects_bad_json(tmp_project_dir, monkeypatch):
    """Preserves existing data on parse error."""
    existing = {"keep": "http://example.com"}
    monkeypatch.setattr(server_mod, "redirects", existing.copy())
    (tmp_project_dir / "redirects.json").write_text("{bad json")
    server_mod.load_redirects()
    assert server_mod.redirects == existing
