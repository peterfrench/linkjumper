#!/usr/bin/env python3
"""LinkJumper CLI entry point."""

import os
import sys

# Ensure the package is importable when invoked via symlink
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from linkjumper.cli import main

main()
