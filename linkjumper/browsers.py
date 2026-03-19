"""Browser detection and setup instructions."""

from pathlib import Path

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


def get_installed_browsers():
    """Return list of browsers that are installed on this system."""
    return [b for b in BROWSERS if b["path"] is None or Path(b["path"]).exists()]


def print_browser_instructions(prefix):
    """Print setup instructions for all installed browsers."""
    installed = get_installed_browsers()

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
