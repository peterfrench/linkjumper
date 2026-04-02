"""LinkJumper: Local URL shortener service for macOS.

Binds to 127.0.0.2 on ports 80 (HTTP) and 443 (HTTPS).
Reads redirect mappings from redirects.json in the same directory.
Send SIGHUP to reload configuration without restart.
"""

import html as html_module
import http.server
import json
import re
import signal
import ssl
import sys
import threading
import time
from urllib.parse import parse_qs, unquote

from linkjumper.config import (
    BIND_ADDR, CERT_DIR, REDIRECTS_PATH, SETTINGS_PATH,
    load_settings as _config_load_settings,
    save_redirects as _save_redirects,
)
from linkjumper.webloc import create_webloc, delete_webloc

_lock = threading.Lock()
prefix = "go"
redirects = {}

MAX_POST_BYTES = 16 * 1024
KEY_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$')


def load_settings():
    global prefix
    settings = _config_load_settings()
    with _lock:
        prefix = settings.get("prefix", "go")


def load_redirects(signum=None, frame=None):
    global redirects
    try:
        with open(REDIRECTS_PATH) as f:
            loaded = json.load(f)
        with _lock:
            redirects = loaded
        print(f"Loaded {len(loaded)} redirects from {REDIRECTS_PATH}", flush=True)
    except FileNotFoundError:
        print(f"Config not found at {REDIRECTS_PATH}, starting with empty redirects", flush=True)
        with _lock:
            redirects = {}
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in {REDIRECTS_PATH}: {e}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr, flush=True)


def reload_all(signum=None, frame=None):
    load_settings()
    load_redirects()


class LinkJumperHandler(http.server.BaseHTTPRequestHandler):
    server_version = "LinkJumper/1.0"

    def do_GET(self):
        path = unquote(self.path).lstrip("/")

        # Separate path and query string
        query = ""
        if "?" in path:
            path, query = path.split("?", 1)
            query = "?" + query

        # Strip trailing slash
        path = path.rstrip("/")

        # Root — show index page
        if not path:
            self.send_index()
            return

        # Look up the first path segment as the redirect key
        parts = path.split("/", 1)
        key = parts[0]
        remainder = parts[1] if len(parts) > 1 else ""

        with _lock:
            target_url = redirects.get(key)

        if target_url is not None:
            target = target_url.rstrip("/")
            if remainder:
                target += "/" + remainder
            target += query

            self.send_response(302)
            self.send_header("Location", target)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
        else:
            self.send_not_found(key)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self.send_error(400, "Invalid Content-Length")
            return

        if length > MAX_POST_BYTES:
            self.send_error(413, "Request body too large")
            return

        try:
            body = self.rfile.read(length).decode("utf-8")
        except UnicodeDecodeError:
            self.send_error(400, "Invalid encoding")
            return

        params = parse_qs(body)
        action = params.get("action", [""])[0]

        if action == "add":
            key = params.get("key", [""])[0].strip().strip("/")
            url = params.get("url", [""])[0].strip()
            if key and url and KEY_PATTERN.match(key):
                if "://" not in url:
                    url = "https://" + url
                with _lock:
                    redirects[key] = url
                    _save_redirects(redirects)
                    pfx = prefix
                create_webloc(pfx, key, url)

        elif action == "remove":
            key = params.get("key", [""])[0].strip()
            if key:
                with _lock:
                    removed = key in redirects
                    if removed:
                        del redirects[key]
                        _save_redirects(redirects)
                    pfx = prefix
                if removed:
                    delete_webloc(pfx, key)

        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def send_index(self):
        with _lock:
            pfx = prefix
            reds = dict(redirects)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        escaped_pfx = html_module.escape(pfx)
        rows = ""
        for i, key in enumerate(sorted(reds)):
            escaped_url = html_module.escape(reds[key])
            escaped_key = html_module.escape(key)
            tab = i + 4
            rows += (
                f"<tr>"
                f'<td><a href="/{escaped_key}" tabindex="{tab}">{escaped_pfx}/{escaped_key}</a></td>'
                f"<td><code>{escaped_url}</code></td>"
                f'<td><form method="POST" style="margin:0">'
                f'<input type="hidden" name="action" value="remove">'
                f'<input type="hidden" name="key" value="{escaped_key}">'
                f'<button type="submit" class="rm">&times;</button>'
                f"</form></td>"
                f"</tr>\n"
            )

        page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>LinkJumper</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif;
         max-width: 720px; margin: 48px auto; padding: 0 24px; color: #1d1d1f; }}
  h1 {{ font-size: 28px; font-weight: 600; }}
  p {{ color: #6e6e73; font-size: 14px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 24px; }}
  th, td {{ text-align: left; padding: 10px 14px; border-bottom: 1px solid #e5e5e7; }}
  th {{ background: #f5f5f7; font-size: 13px; text-transform: uppercase;
       letter-spacing: 0.5px; color: #86868b; }}
  td:last-child {{ width: 1%; white-space: nowrap; }}
  a {{ color: #0066cc; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  code {{ background: #f5f5f7; padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
  .add-form {{ display: flex; gap: 8px; margin-top: 24px; }}
  .add-form input {{ padding: 8px 12px; border: 1px solid #d2d2d7; border-radius: 8px;
                     font-size: 14px; font-family: inherit; }}
  .add-form input[name="key"] {{ width: 120px; }}
  .add-form input[name="url"] {{ flex: 1; }}
  .add-form button {{ padding: 8px 16px; background: #0066cc; color: white;
                      border: none; border-radius: 8px; font-size: 14px;
                      cursor: pointer; font-family: inherit; }}
  .add-form button:hover {{ background: #0055b3; }}
  .rm {{ background: none; border: none; color: #86868b; cursor: pointer;
         font-size: 18px; padding: 0 4px; line-height: 1; }}
  .rm:hover {{ color: #ff3b30; }}
</style>
</head>
<body>
<h1>LinkJumper</h1>
<p>{len(reds)} shortcut{"s" if len(reds) != 1 else ""} configured.</p>
<form method="POST" class="add-form">
  <input type="hidden" name="action" value="add">
  <input type="text" name="key" placeholder="key" required autofocus tabindex="1">
  <input type="text" name="url" placeholder="https://example.com" required tabindex="2">
  <button type="submit" tabindex="3">Add</button>
</form>
<table>
<tr><th>Shortcut</th><th>Destination</th><th></th></tr>
{rows}</table>
</body>
</html>"""
        self.wfile.write(page.encode())

    def send_not_found(self, key):
        with _lock:
            pfx = prefix

        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        safe_key = html_module.escape(key)
        page = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Not Found</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 480px;
         margin: 120px auto; text-align: center; color: #1d1d1f; }}
  a {{ color: #0066cc; text-decoration: none; }}
</style>
</head>
<body>
<h1>404</h1>
<p>No link found for <strong>{html_module.escape(pfx)}/{safe_key}</strong></p>
<p><a href="/">View all shortcuts</a></p>
</body>
</html>"""
        self.wfile.write(page.encode())

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {self.client_address[0]} {fmt % args}",
              flush=True)


def watch_config():
    """Watch config files for changes and auto-reload."""
    last_mtimes = {}
    while True:
        for path in (REDIRECTS_PATH, SETTINGS_PATH):
            try:
                mtime = path.stat().st_mtime
                prev = last_mtimes.get(path, mtime)
                if mtime != prev:
                    reload_all()
                last_mtimes[path] = mtime
            except FileNotFoundError:
                pass
        time.sleep(2)


def run_https():
    cert_file = CERT_DIR / "server.pem"
    key_file = CERT_DIR / "server-key.pem"

    if not cert_file.exists() or not key_file.exists():
        print("No SSL certs found — HTTPS disabled. Run `linkjumper setup`.",
              flush=True)
        return

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(cert_file), str(key_file))

    server = http.server.ThreadingHTTPServer((BIND_ADDR, 443), LinkJumperHandler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print(f"HTTPS listening on {BIND_ADDR}:443", flush=True)
    server.serve_forever()


def main():
    from linkjumper.config import ensure_data_dir
    from linkjumper.system import add_loopback_alias

    ensure_data_dir()

    # Ensure loopback alias exists (needed after reboot)
    try:
        add_loopback_alias()
    except Exception as e:
        print(f"Warning: could not add loopback alias: {e}", flush=True)

    reload_all()
    signal.signal(signal.SIGHUP, reload_all)

    # Start HTTPS on port 443
    threading.Thread(target=run_https, daemon=True).start()

    # Watch config files for changes (enables sudo-free reload via CLI)
    threading.Thread(target=watch_config, daemon=True).start()

    # Run HTTP on port 80 (main thread)
    server = http.server.ThreadingHTTPServer((BIND_ADDR, 80), LinkJumperHandler)
    print(f"HTTP  listening on {BIND_ADDR}:80", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
        sys.exit(0)


if __name__ == "__main__":
    main()
