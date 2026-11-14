"""Shared pytest hooks for the halo-hacker behaviour suite.

Windows note (2026-11-14): the suite failed on windows-latest because
cp1252 is the default text encoding on Windows, so:
- reading `studio/findings.js` (which contains UTF-8 em-dashes / arrows)
  via `read_text()` raised `UnicodeDecodeError` (byte 0x90 / 0x97 in
  cp1252), and
- `tools/report.py` printing a `→` raised `UnicodeEncodeError`.

The pack's source files are UTF-8. This hook reconfigures the test
process's stdio to UTF-8 so tests exercise the pack's logic, not the OS's
legacy codepage. It runs before any test module imports. The pack's own
runtime output is also kept ASCII-safe (see tools/report.py,
tools/findings_view.py) so real users on Windows don't hit it either.
"""
from __future__ import annotations

import io
import sys


def pytest_configure(config):  # noqa: ARG001
    """Reconfigure this process's stdio to UTF-8 (Python 3.7+, best-effort)."""
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError, io.UnsupportedOperation):
                pass
