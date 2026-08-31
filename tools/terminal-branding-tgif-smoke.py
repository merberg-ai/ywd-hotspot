#!/usr/bin/env python3
"""Source-only regression for RC4 terminal branding and TGIF setup parity."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORDMARK = (
    "__   __ __        __ ____        _   _  ___  _____ ____  ____   ___  _____",
    "\\ \\ / / \\ \\      / /|  _ \\ ___ | | | |/ _ \\|_   _/ ___||  _ \\ / _ \\|_   _|",
    " \\ V /   \\ \\ /\\ / / | | | |___|| |_| | | | | | | \\___ \\| |_) | | | | | |",
    "  | |     \\ V  V /  | |_| |    |  _  | |_| | | |  ___) |  __/| |_| | | |",
    "  |_|      \\_/\\_/   |____/     |_| |_|\\___/  |_| |____/|_|    \\___/  |_|",