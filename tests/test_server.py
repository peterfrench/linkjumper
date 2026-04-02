"""Tests for linkjumper.server — HTTP handler and config reload."""

import concurrent.futures
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


def test_server_load_settings_bad_json(tmp_project_dir, monkeypatch):
    """Falls back to 'go' on corrupt settings file."""
    monkeypatch.setattr(server_mod, "prefix", "custom")
    (tmp_project_dir / "config.json").write_text("{corrupt!!!")
    server_mod.load_settings()
    assert server_mod.prefix == "go"


# ---------------------------------------------------------------------------
# POST error-handling tests
# ---------------------------------------------------------------------------


def test_post_invalid_content_length(http_server):
    """Non-numeric Content-Length returns 400."""
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("POST", "/", "", {"Content-Length": "abc"})
    resp = conn.getresponse()
    resp.read()
    assert resp.status == 400
    conn.close()


def test_post_oversized_body(http_server):
    """Body exceeding MAX_POST_BYTES returns 413."""
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("POST", "/", "", {"Content-Length": str(1024 * 1024)})
    resp = conn.getresponse()
    resp.read()
    assert resp.status == 413
    conn.close()


def test_post_empty_body_is_noop(http_server):
    """POST with empty body still returns 303."""
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("POST", "/", "")
    resp = conn.getresponse()
    resp.read()
    assert resp.status == 303
    conn.close()


def test_post_unknown_action_is_noop(http_server):
    """POST with unknown action still returns 303."""
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    body = urlencode({"action": "bogus"})
    conn.request("POST", "/", body, {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    resp.read()
    assert resp.status == 303
    conn.close()


# ---------------------------------------------------------------------------
# Key validation tests (POST)
# ---------------------------------------------------------------------------


def test_post_add_rejects_path_traversal_key(http_server):
    """Keys with path traversal characters are rejected."""
    host, port = http_server
    before = dict(server_mod.redirects)
    conn = http.client.HTTPConnection(host, port)
    body = urlencode({"action": "add", "key": "../etc", "url": "https://evil.com"})
    conn.request("POST", "/", body, {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    resp.read()
    assert resp.status == 303
    assert server_mod.redirects == before
    conn.close()


def test_post_add_rejects_empty_key(http_server):
    """Empty key is rejected."""
    host, port = http_server
    before = dict(server_mod.redirects)
    conn = http.client.HTTPConnection(host, port)
    body = urlencode({"action": "add", "key": "", "url": "https://example.com"})
    conn.request("POST", "/", body, {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    resp.read()
    assert server_mod.redirects == before
    conn.close()


def test_post_add_rejects_key_with_spaces(http_server):
    """Keys with spaces are rejected."""
    host, port = http_server
    before = dict(server_mod.redirects)
    conn = http.client.HTTPConnection(host, port)
    body = urlencode({"action": "add", "key": "my key", "url": "https://example.com"})
    conn.request("POST", "/", body, {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    resp.read()
    assert server_mod.redirects == before
    conn.close()


def test_post_add_accepts_key_with_dots_and_dashes(http_server):
    """Keys with dots and dashes are accepted."""
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    body = urlencode({"action": "add", "key": "my-app.dev", "url": "https://example.com"})
    conn.request("POST", "/", body, {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    resp.read()
    assert resp.status == 303
    assert server_mod.redirects["my-app.dev"] == "https://example.com"
    conn.close()


# ---------------------------------------------------------------------------
# HTML escaping / XSS tests
# ---------------------------------------------------------------------------


def test_index_escapes_html_in_keys(http_server, monkeypatch):
    """Redirect keys with HTML chars are escaped in the index page."""
    monkeypatch.setattr(
        server_mod, "redirects",
        {"<script>alert(1)</script>": "https://evil.com"},
    )
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/")
    resp = conn.getresponse()
    body = resp.read().decode()
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body
    conn.close()


def test_index_escapes_html_in_urls(http_server, monkeypatch):
    """Redirect URLs with HTML chars are escaped in the index page."""
    monkeypatch.setattr(
        server_mod, "redirects",
        {"xss": 'https://x.com/"><script>alert(1)</script>'},
    )
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/")
    resp = conn.getresponse()
    body = resp.read().decode()
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body
    conn.close()


def test_404_escapes_html_in_key(http_server):
    """404 page escapes the key to prevent reflected XSS."""
    host, port = http_server
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/<script>alert(1)</script>")
    resp = conn.getresponse()
    body = resp.read().decode()
    assert resp.status == 404
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body
    conn.close()


# ---------------------------------------------------------------------------
# Concurrent access tests
# ---------------------------------------------------------------------------


def _fetch(host, port, path):
    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", path)
    resp = conn.getresponse()
    resp.read()
    status = resp.status
    conn.close()
    return status


def _post_add(host, port, key, url):
    conn = http.client.HTTPConnection(host, port)
    body = urlencode({"action": "add", "key": key, "url": url})
    conn.request("POST", "/", body, {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    resp.read()
    status = resp.status
    conn.close()
    return status


def test_concurrent_reads(http_server):
    """Multiple concurrent GET requests don't crash."""
    host, port = http_server

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        paths = ["/", "/gh", "/mail", "/nope"] * 10
        results = list(pool.map(lambda p: _fetch(host, port, p), paths))

    assert all(s in (200, 302, 404) for s in results)


def test_concurrent_writes(http_server):
    """Multiple concurrent POST requests don't corrupt state."""
    host, port = http_server

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(
            pool.map(
                lambda i: _post_add(host, port, f"t{i}", f"https://e{i}.com"),
                range(20),
            )
        )

    assert all(s == 303 for s in results)
    for i in range(20):
        assert server_mod.redirects[f"t{i}"] == f"https://e{i}.com"


def test_concurrent_read_write_mix(http_server):
    """Mixed concurrent GET and POST requests don't crash."""
    host, port = http_server

    def task(i):
        if i % 2 == 0:
            return ("read", _fetch(host, port, "/"))
        else:
            return ("write", _post_add(host, port, f"m{i}", f"https://m{i}.com"))

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(task, range(30)))

    reads = [s for op, s in results if op == "read"]
    writes = [s for op, s in results if op == "write"]
    assert all(s == 200 for s in reads)
    assert all(s == 303 for s in writes)
