"""Tests for linkjumper.server — HTTP handler and config reload."""

import http.client
from urllib.parse import urlencode

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
# POST tests (add / remove via web UI)
# ---------------------------------------------------------------------------


def test_post_add_shortcut(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    body = urlencode({"action": "add", "key": "test", "url": "https://example.com"})
    conn.request("POST", "/", body, {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    assert resp.status == 303
    assert resp.getheader("Location") == "/"
    assert server_mod.redirects["test"] == "https://example.com"
    conn.close()


def test_post_add_prepends_https(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    body = urlencode({"action": "add", "key": "ex", "url": "example.com"})
    conn.request("POST", "/", body, {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    resp.read()
    assert server_mod.redirects["ex"] == "https://example.com"
    conn.close()


def test_post_add_preserves_http(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    body = urlencode({"action": "add", "key": "ex", "url": "http://example.com"})
    conn.request("POST", "/", body, {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    resp.read()
    assert server_mod.redirects["ex"] == "http://example.com"
    conn.close()


def test_post_remove_shortcut(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    body = urlencode({"action": "remove", "key": "gh"})
    conn.request("POST", "/", body, {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    assert resp.status == 303
    assert "gh" not in server_mod.redirects
    conn.close()


def test_post_remove_missing_key_is_noop(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    before = dict(server_mod.redirects)
    body = urlencode({"action": "remove", "key": "nonexistent"})
    conn.request("POST", "/", body, {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    assert resp.status == 303
    assert server_mod.redirects == before
    conn.close()


def test_index_has_add_form(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/")
    resp = conn.getresponse()
    body = resp.read().decode()
    assert 'name="action" value="add"' in body
    assert 'name="key"' in body
    assert 'name="url"' in body
    conn.close()


def test_index_has_remove_buttons(http_server):
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/")
    resp = conn.getresponse()
    body = resp.read().decode()
    assert 'value="remove"' in body
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
