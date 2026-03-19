"""LinkJumper: Local URL shortener service for macOS.

Binds to 127.0.0.2 on ports 80 (HTTP) and 443 (HTTPS).
Reads redirect mappings from redirects.json in the same directory.
Send SIGHUP to reload configuration without restart.
"""

import html as html_module
import http.server
import json
import signal
import ssl
import sys
import threading
import time
from urllib.parse import unquote

from linkjumper.config import BIND_ADDR, CERT_DIR, REDIRECTS_PATH, SETTINGS_PATH

prefix = "go"
redirects = {}


def load_settings():
    global prefix
    try:
        with open(SETTINGS_PATH) as f:
            settings = json.load(f)
        prefix = settings.get("prefix", "go")
    except (FileNotFoundError, json.JSONDecodeError):
        prefix = "go"


def load_redirects(signum=None, frame=None):
    global redirects
    try:
        with open(REDIRECTS_PATH) as f:
            redirects = json.load(f)
        print(f"Loaded {len(redirects)} redirects from {REDIRECTS_PATH}", flush=True)
    except FileNotFoundError:
        print(f"Config not found at {REDIRECTS_PATH}, starting with empty redirects", flush=True)
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

        if key in redirects:
            target = redirects[key].rstrip("/")
            if remainder:
                target += "/" + remainder
            target += query

            self.send_response(302)
            self.send_header("Location", target)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
        else:
            self.send_not_found(key)

    def do_HEAD(self):
        self.do_GET()

    def send_index(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        pfx = html_module.escape(prefix)
        rows = ""
        for key in sorted(redirects):
            escaped_url = html_module.escape(redirects[key])
            escaped_key = html_module.escape(key)
            rows += (
                f"<tr>"
                f'<td><a href="/{escaped_key}">{pfx}/{escaped_key}</a></td>'
                f"<td><code>{escaped_url}</code></td>"
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
  a {{ color: #0066cc; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  code {{ background: #f5f5f7; padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
</style>
</head>
<body>
<h1>LinkJumper</h1>
<p>{len(redirects)} shortcut{"s" if len(redirects) != 1 else ""} configured.
   Manage with: <code>linkjumper add &lt;key&gt; &lt;url&gt;</code></p>
<table>
<tr><th>Shortcut</th><th>Destination</th></tr>
{rows}</table>
</body>
</html>"""
        self.wfile.write(page.encode())

    def send_not_found(self, key):
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
<p>No link found for <strong>{html_module.escape(prefix)}/{safe_key}</strong></p>
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
    ctx.load_cert_chain(str(cert_file), str(key_file))

    server = http.server.ThreadingHTTPServer((BIND_ADDR, 443), LinkJumperHandler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print(f"HTTPS listening on {BIND_ADDR}:443", flush=True)
    server.serve_forever()


def main():
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
