#!/usr/bin/env python3
"""LinkJumper CLI — manage your local link shortcuts."""

import argparse
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent
REDIRECTS_PATH = PROJECT_DIR / "redirects.json"
SETTINGS_PATH = PROJECT_DIR / "config.json"
PLIST_LABEL = "com.linkjumper.redirect"
PLIST_PATH = f"/Library/LaunchDaemons/{PLIST_LABEL}.plist"
BIND_ADDR = "127.0.0.2"
LOG_PATH = "/var/log/link-jumper.log"
ERR_PATH = "/var/log/link-jumper.err"

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_settings():
    try:
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"prefix": "go"}


def save_settings(settings):
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")


def get_prefix():
    return load_settings().get("prefix", "go")


def load_redirects():
    try:
        with open(REDIRECTS_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_redirects(redirects):
    with open(REDIRECTS_PATH, "w") as f:
        json.dump(redirects, f, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# System helpers (used by setup, teardown, config --prefix)
# ---------------------------------------------------------------------------

def has_hosts_entry(prefix):
    hosts = Path("/etc/hosts").read_text()
    return bool(re.search(rf"^{re.escape(BIND_ADDR)}\s+{re.escape(prefix)}$",
                           hosts, re.MULTILINE))


def add_hosts_entry(prefix):
    if has_hosts_entry(prefix):
        return False
    subprocess.run(
        f'echo "{BIND_ADDR}\t{prefix}" | sudo tee -a /etc/hosts >/dev/null',
        shell=True, check=True,
    )
    return True


def remove_hosts_entry(prefix):
    if not has_hosts_entry(prefix):
        return False
    subprocess.run(
        ["sudo", "sed", "-i", "",
         f"/^{re.escape(BIND_ADDR)}[[:space:]].*{re.escape(prefix)}$/d",
         "/etc/hosts"],
        check=True,
    )
    return True


def flush_dns():
    subprocess.run(["sudo", "dscacheutil", "-flushcache"], check=True)
    subprocess.run(["sudo", "killall", "-HUP", "mDNSResponder"],
                   capture_output=True)


def has_loopback_alias():
    r = subprocess.run(["ifconfig", "lo0"], capture_output=True, text=True)
    return BIND_ADDR in r.stdout


def add_loopback_alias():
    if has_loopback_alias():
        return False
    subprocess.run(["sudo", "ifconfig", "lo0", "alias", BIND_ADDR, "up"],
                   check=True)
    return True


def remove_loopback_alias():
    if not has_loopback_alias():
        return False
    subprocess.run(["sudo", "ifconfig", "lo0", "-alias", BIND_ADDR], check=True)
    return True


def cleanup_dotgo_artifacts():
    """Remove artifacts from the *.go DNS/HTTPS experiment if present."""
    resolver = Path("/etc/resolver/go")
    cert_dir = PROJECT_DIR / "certs"
    changed = False

    if resolver.exists():
        subprocess.run(["sudo", "rm", "-f", str(resolver)], check=True)
        print("      Cleaned up /etc/resolver/go")
        changed = True

    if (cert_dir / "ca.pem").exists():
        subprocess.run(
            ["sudo", "security", "remove-trusted-cert", "-d",
             str(cert_dir / "ca.pem")],
            capture_output=True,
        )
        print("      Removed old CA from keychain")
        changed = True

    if changed:
        flush_dns()


def build_plist():
    start_sh = PROJECT_DIR / "start.sh"
    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
          "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{PLIST_LABEL}</string>

            <key>ProgramArguments</key>
            <array>
                <string>/bin/bash</string>
                <string>{start_sh}</string>
            </array>

            <key>RunAtLoad</key>
            <true/>

            <key>KeepAlive</key>
            <true/>

            <key>StandardOutPath</key>
            <string>{LOG_PATH}</string>

            <key>StandardErrorPath</key>
            <string>{ERR_PATH}</string>

            <key>WorkingDirectory</key>
            <string>{PROJECT_DIR}</string>
        </dict>
        </plist>
    """)


def install_launchd():
    subprocess.run(
        ["sudo", "tee", PLIST_PATH],
        input=build_plist(), text=True,
        stdout=subprocess.DEVNULL, check=True,
    )
    subprocess.run(
        ["sudo", "launchctl", "bootout", f"system/{PLIST_LABEL}"],
        capture_output=True,
    )
    subprocess.run(
        ["sudo", "launchctl", "bootstrap", "system", PLIST_PATH],
        check=True,
    )


def remove_launchd():
    subprocess.run(
        ["sudo", "launchctl", "bootout", f"system/{PLIST_LABEL}"],
        capture_output=True,
    )
    subprocess.run(["sudo", "rm", "-f", PLIST_PATH], check=True)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_setup(args):
    prefix = get_prefix()
    print("=== LinkJumper — Setup ===")
    print(f"  Prefix: {prefix}")
    print()

    # 0. Clean up *.go artifacts if present
    cleanup_dotgo_artifacts()

    # 1. /etc/hosts
    if add_hosts_entry(prefix):
        print(f"[1/3] Added '{BIND_ADDR}\t{prefix}' to /etc/hosts")
    else:
        print(f"[1/3] /etc/hosts already has '{prefix}' entry.")
    flush_dns()
    print("      DNS cache flushed.")

    # 2. Loopback alias
    if add_loopback_alias():
        print(f"[2/3] Added loopback alias {BIND_ADDR}")
    else:
        print(f"[2/3] Loopback alias {BIND_ADDR} already active.")

    # 3. launchd
    print("[3/3] Installing launchd daemon ...")
    install_launchd()
    print("      Service started.")

    print()
    print("=== Done! ===")
    print()
    print(f"  Open in browser:  http://{prefix}/")
    print(f"  Example:          http://{prefix}/gh  ->  https://github.com")
    print()
    print(f"  Safari tip:       {prefix}/gh/ (trailing slash) navigates directly.")
    print(f"  Run `linkjumper browser` for browser-specific setup tips.")


def cmd_teardown(args):
    prefix = get_prefix()
    print("=== LinkJumper — Teardown ===")
    print()

    # 0. Clean up *.go artifacts if present
    cleanup_dotgo_artifacts()

    # 1. launchd
    if Path(PLIST_PATH).exists():
        print("[1/3] Stopping and removing service ...")
        remove_launchd()
        print("      Done.")
    else:
        print("[1/3] No launchd service found — skipping.")

    # 2. /etc/hosts
    if remove_hosts_entry(prefix):
        print(f"[2/3] Removed '{prefix}' from /etc/hosts")
        flush_dns()
        print("      DNS cache flushed.")
    else:
        print(f"[2/3] No '{prefix}' entry in /etc/hosts — skipping.")

    # 3. Loopback alias
    if remove_loopback_alias():
        print(f"[3/3] Removed loopback alias {BIND_ADDR}")
    else:
        print("[3/3] No loopback alias found — skipping.")

    print()
    print("=== Teardown complete ===")
    print()
    print("Your redirects.json and config.json were preserved.")
    print("To re-enable: linkjumper setup")


def cmd_list(args):
    pfx = get_prefix()
    redirects = load_redirects()
    if not redirects:
        print("No redirects configured.")
        return

    max_key = max(len(k) for k in redirects)
    for key in sorted(redirects):
        print(f"  {pfx}/{key:<{max_key}}  ->  {redirects[key]}")
    print(f"\n{len(redirects)} shortcut(s)")


def cmd_add(args):
    pfx = get_prefix()
    redirects = load_redirects()
    key = args.key.strip("/")
    url = args.url

    if key in redirects:
        old = redirects[key]
        redirects[key] = url
        save_redirects(redirects)
        print(f"Updated: {pfx}/{key}  ->  {url}  (was: {old})")
    else:
        redirects[key] = url
        save_redirects(redirects)
        print(f"Added: {pfx}/{key}  ->  {url}")

    print("Server will pick up the change automatically.")


def cmd_remove(args):
    pfx = get_prefix()
    redirects = load_redirects()
    key = args.key.strip("/")

    if key not in redirects:
        print(f"No redirect found for '{pfx}/{key}'")
        sys.exit(1)

    url = redirects.pop(key)
    save_redirects(redirects)
    print(f"Removed: {pfx}/{key}  ->  {url}")
    print("Server will pick up the change automatically.")


def cmd_config(args):
    if args.prefix is None:
        settings = load_settings()
        print("LinkJumper configuration:")
        print(f"  prefix:  {settings.get('prefix', 'go')}")
        print(f"  config:  {SETTINGS_PATH}")
        return

    new_prefix = args.prefix.strip().lower()

    if not re.match(r'^[a-z][a-z0-9-]*$', new_prefix):
        print("Error: prefix must start with a letter and contain only "
              "lowercase letters, numbers, and hyphens.")
        sys.exit(1)

    settings = load_settings()
    old_prefix = settings.get("prefix", "go")

    if new_prefix == old_prefix:
        print(f"Prefix is already '{old_prefix}'.")
        return

    print(f"Changing prefix: {old_prefix} -> {new_prefix}")

    # Update /etc/hosts
    print("  Updating /etc/hosts ...")
    remove_hosts_entry(old_prefix)
    add_hosts_entry(new_prefix)
    flush_dns()

    # Save
    settings["prefix"] = new_prefix
    save_settings(settings)

    # Restart service
    print("  Restarting service ...")
    subprocess.run(["sudo", "launchctl", "bootout", f"system/{PLIST_LABEL}"],
                   capture_output=True)
    subprocess.run(["sudo", "launchctl", "bootstrap", "system", PLIST_PATH],
                   capture_output=True)

    print(f"\nDone! Shortcuts are now at: {new_prefix}/")
    print(f"  Example: {new_prefix}/gh  ->  https://github.com")


def cmd_start(args):
    result = subprocess.run(
        ["sudo", "launchctl", "bootstrap", "system", PLIST_PATH],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("LinkJumper started.")
    elif "already loaded" in result.stderr.lower() or result.returncode == 37:
        print("LinkJumper is already running.")
    else:
        print(f"Failed to start: {result.stderr.strip()}")
        sys.exit(1)


def cmd_stop(args):
    result = subprocess.run(
        ["sudo", "launchctl", "bootout", f"system/{PLIST_LABEL}"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("LinkJumper stopped.")
    elif "could not find service" in result.stderr.lower() or result.returncode == 113:
        print("LinkJumper is not running.")
    else:
        print(f"Failed to stop: {result.stderr.strip()}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Browser detection and setup instructions
# ---------------------------------------------------------------------------

BROWSERS = [
    {
        "name": "Google Chrome",
        "path": "/Applications/Google Chrome.app",
        "instructions": """\
  1. Open Chrome and go to: chrome://settings/searchEngines
  2. Under "Site search", click "Add"
  3. Fill in:
       Name:     LinkJumper
       Shortcut: {prefix}
       URL:      http://{prefix}/%s
  4. Type '{prefix}' in the address bar, press Space, then type your shortcut.
     Example: {prefix}<Space>gh  ->  https://github.com""",
    },
    {
        "name": "Firefox",
        "path": "/Applications/Firefox.app",
        "instructions": """\
  1. Open Firefox and go to: about:config
  2. Search for: browser.fixup.domainwhitelist.{prefix}
  3. If it doesn't exist, click the + button to create it as a Boolean, set to true.
  4. Now you can type '{prefix}/gh' directly in the address bar and it will navigate
     instead of searching.""",
    },
    {
        "name": "Safari",
        "path": None,  # Always installed
        "instructions": """\
  Safari does not support custom keywords in the address bar.
  However, adding a trailing slash works: {prefix}/gh/ will navigate instead of searching.
  Alternatively, type the full URL: http://{prefix}/gh
  Tip: Bookmark http://{prefix}/ for quick access to the index page.""",
    },
    {
        "name": "Arc",
        "path": "/Applications/Arc.app",
        "instructions": """\
  Arc uses Chromium's search engine system:
  1. Open Arc and go to: arc://settings/searchEngines
  2. Under "Site search", click "Add"
  3. Fill in:
       Name:     LinkJumper
       Shortcut: {prefix}
       URL:      http://{prefix}/%s
  4. Type '{prefix}' in the address bar, press Space, then type your shortcut.
     Example: {prefix}<Space>gh  ->  https://github.com""",
    },
    {
        "name": "Microsoft Edge",
        "path": "/Applications/Microsoft Edge.app",
        "instructions": """\
  1. Open Edge and go to: edge://settings/searchEngines
  2. Click "Add"
  3. Fill in:
       Name:     LinkJumper
       Shortcut: {prefix}
       URL:      http://{prefix}/%s
  4. Type '{prefix}' in the address bar, press Space, then type your shortcut.
     Example: {prefix}<Space>gh  ->  https://github.com""",
    },
    {
        "name": "Brave",
        "path": "/Applications/Brave Browser.app",
        "instructions": """\
  Brave uses Chromium's search engine system:
  1. Open Brave and go to: brave://settings/searchEngines
  2. Under "Site search", click "Add"
  3. Fill in:
       Name:     LinkJumper
       Shortcut: {prefix}
       URL:      http://{prefix}/%s
  4. Type '{prefix}' in the address bar, press Space, then type your shortcut.
     Example: {prefix}<Space>gh  ->  https://github.com""",
    },
    {
        "name": "Vivaldi",
        "path": "/Applications/Vivaldi.app",
        "instructions": """\
  1. Open Vivaldi and go to: vivaldi://settings/search
  2. Click "Add Search Engine"
  3. Fill in:
       Name:     LinkJumper
       Nickname: {prefix}
       URL:      http://{prefix}/%s
  4. Type '{prefix}' in the address bar, press Space, then type your shortcut.
     Example: {prefix}<Space>gh  ->  https://github.com""",
    },
    {
        "name": "Opera",
        "path": "/Applications/Opera.app",
        "instructions": """\
  1. Open Opera and go to: opera://settings/searchEngines
  2. Click "Add"
  3. Fill in:
       Name:     LinkJumper
       Shortcut: {prefix}
       URL:      http://{prefix}/%s
  4. Type '{prefix}' in the address bar, press Space, then type your shortcut.
     Example: {prefix}<Space>gh  ->  https://github.com""",
    },
]


def cmd_browser(args):
    prefix = get_prefix()

    # Detect installed browsers
    installed = []
    for browser in BROWSERS:
        if browser["path"] is None or Path(browser["path"]).exists():
            installed.append(browser)

    if not installed:
        print("No supported browsers detected.")
        return

    print(f"Detected {len(installed)} browser(s). Setup instructions for '{prefix}/' links:\n")

    for i, browser in enumerate(installed):
        if i > 0:
            print()
        print(f"--- {browser['name']} ---")
        print(browser["instructions"].format(prefix=prefix))

    print()
    print("Note: http://{0}/<shortcut> always works in any browser.".format(prefix))
    print("The instructions above let you skip the 'http://' prefix.")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="linkjumper",
        description="LinkJumper — manage your local link shortcuts",
    )
    subs = parser.add_subparsers(dest="command")

    subs.add_parser("setup", help="Configure the system (hosts, loopback, launchd)")
    subs.add_parser("teardown", help="Reverse all system configuration")

    subs.add_parser("list", aliases=["ls"], help="List all redirects")

    p_add = subs.add_parser("add", help="Add or update a redirect")
    p_add.add_argument("key", help="Short name (e.g. 'gh')")
    p_add.add_argument("url", help="Destination URL (e.g. 'https://github.com')")

    p_rm = subs.add_parser("remove", aliases=["rm"], help="Remove a redirect")
    p_rm.add_argument("key", help="Short name to remove")

    p_cfg = subs.add_parser("config", help="View or change LinkJumper settings")
    p_cfg.add_argument("--prefix", help="Set the URL prefix (default: go)",
                       default=None)

    subs.add_parser("start", help="Start the LinkJumper service")
    subs.add_parser("stop", help="Stop the LinkJumper service")
    subs.add_parser("browser", help="Show browser setup instructions")

    args = parser.parse_args()

    handlers = {
        "setup": cmd_setup,
        "teardown": cmd_teardown,
        "list": cmd_list, "ls": cmd_list,
        "add": cmd_add,
        "remove": cmd_remove, "rm": cmd_remove,
        "config": cmd_config,
        "start": cmd_start,
        "stop": cmd_stop,
        "browser": cmd_browser,
    }

    if args.command in handlers:
        handlers[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
