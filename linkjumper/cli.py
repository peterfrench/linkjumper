"""LinkJumper CLI — manage your local link shortcuts."""

import argparse
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

from linkjumper.browsers import print_browser_instructions
from linkjumper.certs import generate_certs, has_ca_trust, remove_ca_trust, sign_server_cert, trust_ca
from linkjumper.config import (
    BIND_ADDR, CERT_DIR, DEFAULT_REDIRECTS, PLIST_LABEL, PLIST_PATH,
    REDIRECTS_PATH, SETTINGS_PATH, WEBLOC_DIR,
    ensure_data_dir, get_prefix, load_redirects, load_settings,
    save_redirects, save_settings,
)
from linkjumper.system import (
    add_hosts_entry, add_loopback_alias, cleanup_dotgo_artifacts, flush_dns,
    install_launchd, remove_hosts_entry, remove_launchd, remove_loopback_alias,
)
from linkjumper.webloc import (
    create_webloc, delete_webloc, remove_all_weblocs, sync_weblocs,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _signal_server_reload():
    """Send SIGHUP to the running server so it reloads redirects immediately."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "linkjumper.server"],
            capture_output=True, text=True,
        )
        for pid in result.stdout.strip().splitlines():
            os.kill(int(pid), signal.SIGHUP)
    except (ProcessLookupError, ValueError, OSError):
        pass


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_setup(args):
    ensure_data_dir()
    prefix = get_prefix()
    print("=== LinkJumper — Setup ===")
    print(f"  Prefix: {prefix}")
    print()

    # 0. Clean up *.go artifacts if present
    cleanup_dotgo_artifacts()

    # 1. /etc/hosts
    if add_hosts_entry(prefix):
        print(f"[1/6] Added '{BIND_ADDR}\t{prefix}' to /etc/hosts")
    else:
        print(f"[1/6] /etc/hosts already has '{prefix}' entry.")
    flush_dns()
    print("      DNS cache flushed.")

    # 2. Loopback alias
    if add_loopback_alias():
        print(f"[2/6] Added loopback alias {BIND_ADDR}")
    else:
        print(f"[2/6] Loopback alias {BIND_ADDR} already active.")

    # 3. SSL certificates
    print(f"[3/6] Generating SSL certificate for '{prefix}' ...")
    generate_certs(prefix)
    print(f"      Certificates written to {CERT_DIR}/")

    # 4. Trust CA (skip if already trusted)
    if has_ca_trust():
        print("[4/6] CA certificate already trusted in System keychain.")
    else:
        print("[4/6] Trusting CA certificate (you may be prompted for your password) ...")
        remove_ca_trust()
        trust_ca()
        print("      CA trusted in System keychain.")

    # 5. launchd
    print("[5/6] Installing launchd daemon ...")
    install_launchd()
    print("      Service started.")

    # 6. Seed default redirects if redirects.json is missing, then sync weblocs
    if not REDIRECTS_PATH.exists():
        save_redirects(DEFAULT_REDIRECTS)
        print(f"[6/6] Created redirects.json with {len(DEFAULT_REDIRECTS)} default shortcut(s)")
    redirects = load_redirects()
    sync_weblocs(prefix, redirects)
    print(f"      Synced {len(redirects)} Spotlight webloc file(s) to {WEBLOC_DIR}/")

    print()
    print("=== Done! ===")
    print()
    print(f"  Open in browser:  http://{prefix}/")
    print(f"  Example:          http://{prefix}/gh  ->  https://github.com")
    print(f"  Spotlight:        Cmd+Space, type '{prefix} gh', press Enter")
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
        print("[1/5] Stopping and removing service ...")
        remove_launchd()
        print("      Done.")
    else:
        print("[1/5] No launchd service found — skipping.")

    # 2. CA trust
    if (CERT_DIR / "ca.pem").exists():
        print("[2/5] Removing CA certificate from System keychain ...")
        remove_ca_trust()
        print("      Done.")
    else:
        print("[2/5] No CA certificate found — skipping.")

    # 3. /etc/hosts
    if remove_hosts_entry(prefix):
        print(f"[3/5] Removed '{prefix}' from /etc/hosts")
        flush_dns()
        print("      DNS cache flushed.")
    else:
        print(f"[3/5] No '{prefix}' entry in /etc/hosts — skipping.")

    # 4. Loopback alias
    if remove_loopback_alias():
        print(f"[4/5] Removed loopback alias {BIND_ADDR}")
    else:
        print("[4/5] No loopback alias found — skipping.")

    # 5. Remove Spotlight webloc files
    remove_all_weblocs(prefix)
    print("[5/5] Removed Spotlight webloc files.")

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
    if "://" not in url:
        url = "https://" + url

    if key in redirects:
        old = redirects[key]
        redirects[key] = url
        save_redirects(redirects)
        print(f"Updated: {pfx}/{key}  ->  {url}  (was: {old})")
    else:
        redirects[key] = url
        save_redirects(redirects)
        print(f"Added: {pfx}/{key}  ->  {url}")

    shortcut_url = f"http://{pfx}/{key}/"
    print(f"  {shortcut_url}")

    create_webloc(pfx, key, url)

    settings = load_settings()
    if settings.get("auto_open", False):
        _signal_server_reload()
        subprocess.run(["open", shortcut_url])
    else:
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
    delete_webloc(pfx, key)
    print(f"Removed: {pfx}/{key}  ->  {url}")
    print("Server will pick up the change automatically.")


def cmd_config(args):
    if args.prefix is None and args.auto_open is None:
        settings = load_settings()
        print("LinkJumper configuration:")
        print(f"  prefix:     {settings.get('prefix', 'go')}")
        print(f"  auto_open:  {settings.get('auto_open', False)}")
        print(f"  config:     {SETTINGS_PATH}")
        return

    settings = load_settings()

    if args.auto_open is not None:
        val = args.auto_open.lower()
        if val in ("true", "1", "yes", "on"):
            settings["auto_open"] = True
        elif val in ("false", "0", "no", "off"):
            settings["auto_open"] = False
        else:
            print("Error: --auto-open must be true/false, yes/no, on/off, or 1/0.")
            sys.exit(1)
        save_settings(settings)
        print(f"auto_open set to {settings['auto_open']}")

    if args.prefix is None:
        return

    new_prefix = args.prefix.strip().lower()

    if not re.match(r'^[a-z][a-z0-9-]*$', new_prefix):
        print("Error: prefix must start with a letter and contain only "
              "lowercase letters, numbers, and hyphens.")
        sys.exit(1)

    old_prefix = settings.get("prefix", "go")

    if new_prefix == old_prefix:
        print(f"Prefix is already '{old_prefix}'.")
        return

    if not (CERT_DIR / "ca.pem").exists():
        print("Error: SSL CA not found. Run `linkjumper setup` first.")
        sys.exit(1)

    print(f"Changing prefix: {old_prefix} -> {new_prefix}")

    # Update /etc/hosts
    print("  Updating /etc/hosts ...")
    remove_hosts_entry(old_prefix)
    add_hosts_entry(new_prefix)
    flush_dns()

    # Regenerate server cert with new hostname
    print("  Regenerating SSL certificate ...")
    sign_server_cert(new_prefix)

    # Rename webloc files from old prefix to new
    print("  Updating Spotlight webloc files ...")
    remove_all_weblocs(old_prefix)
    sync_weblocs(new_prefix, load_redirects())

    # Save
    settings["prefix"] = new_prefix
    save_settings(settings)

    # Restart service to pick up new cert
    print("  Restarting service ...")
    subprocess.run(["sudo", "launchctl", "bootout", f"system/{PLIST_LABEL}"],
                   capture_output=True)
    subprocess.run(["sudo", "launchctl", "bootstrap", "system", PLIST_PATH],
                   capture_output=True)

    print(f"\nDone! Shortcuts are now at: {new_prefix}/")
    print(f"  Example: {new_prefix}/gh  ->  https://github.com")


def cmd_go(args):
    prefix = get_prefix()
    key = args.key.strip("/")
    url = f"http://{prefix}/{key}/"
    subprocess.run(["open", url])


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


def cmd_browser(args):
    print_browser_instructions(get_prefix())


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
    p_cfg.add_argument("--auto-open", dest="auto_open", default=None,
                       help="Auto-open links in browser when added (true/false)")

    p_go = subs.add_parser("go", help="Open a shortcut in the default browser")
    p_go.add_argument("key", help="Short name to open (e.g. 'gh')")

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
        "go": cmd_go,
        "start": cmd_start,
        "stop": cmd_stop,
        "browser": cmd_browser,
    }

    NEEDS_ROOT = {"setup", "teardown", "start", "stop"}

    if args.command in handlers:
        if args.command in NEEDS_ROOT and os.geteuid() != 0:
            print(f"Error: 'linkjumper {args.command}' must be run as root.")
            print(f"  Try: sudo linkj {args.command}")
            sys.exit(1)
        if args.command == "config" and args.prefix is not None and os.geteuid() != 0:
            print("Error: 'linkjumper config --prefix' must be run as root.")
            print("  Try: sudo linkj config --prefix <name>")
            sys.exit(1)
        handlers[args.command](args)
    else:
        parser.print_help()
