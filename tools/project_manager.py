#!/usr/bin/env python3
"""Halo Hacker project registry — multi-program / bug-bounty tracking.

A project corresponds to one program (HackerOne, Bugcrowd, Intigriti,
or custom engagement) with a single active engagement at a time.

Reads/writes ``data/projects.json`` in the pack's data folder
(``~/.halo/packs/.data/halo-hacker/``).  ``switch_project`` and
``get_active_project`` additionally read/write the ``active_project``
config key via ``halo_harness.ext`` so the rest of the pack (Studio
panels, agents) can discover what is currently being worked on.

All public functions return ``{"ok": True, "project": {...}}`` on
success or ``{"ok": False, "error": "..."}`` on failure.  Standalone
CLI via ``python -m tools.project_manager <command>`` prints JSON
to stdout.

Imports ``halo_harness.ext`` only (stable extension API).  Graceful
degradation when the harness is unavailable — only ``switch_project``
and ``get_active_project`` fail in that case; the data-file functions
work standalone.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# -------------------------------------------------------------------
# Data-directory resolver (same pattern as engage.py, findings_view.py)
# -------------------------------------------------------------------

_PACK_NAME = "halo-hacker"


def _ext_data_dir() -> Path | None:
    """The harness's data-dir resolver, when halo_harness is importable."""
    try:
        from halo_harness.ext import data_dir as _harness_data_dir
        return Path(_harness_data_dir(_PACK_NAME))
    except Exception:
        return None


def _data_dir() -> Path:
    """The pack's DATA folder — where projects.json lives.

    Precedence:
    1. ``HALO_HACKER_DATA_DIR`` (tests, headless runs)
    2. ``halo_harness.ext.data_dir("halo-hacker")``
    3. ``~/.halo/packs/.data/halo-hacker/`` (convention fallback)
    """
    d = (Path(os.environ["HALO_HACKER_DATA_DIR"])
         if "HALO_HACKER_DATA_DIR" in os.environ
         else (_ext_data_dir()
               or Path.home() / ".halo" / "packs" / ".data" / _PACK_NAME))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _projects_path() -> Path:
    return _data_dir() / "projects.json"


# -------------------------------------------------------------------
# Config helpers (halo_harness.ext — best-effort)
# -------------------------------------------------------------------

def _get_config(key: str, default: str = "") -> str:
    """Read a pack config key through the harness extension API.

    Returns the default when the harness is unavailable or the key is
    not set.
    """
    try:
        from halo_harness.ext import get_config  # type: ignore[import-untyped]
        value = get_config(_PACK_NAME, key, default)
        return str(value) if value is not None else default
    except Exception:
        return default


def _set_config(key: str, value: str) -> bool:
    """Write a pack config key through the harness extension API.

    Returns True on success, False when the harness is unavailable
    or the write fails.
    """
    try:
        from halo_harness.ext import set_config  # type: ignore[import-untyped]
        set_config(_PACK_NAME, key, value)
        return True
    except Exception:
        return False


# -------------------------------------------------------------------
# JSON file helpers
# -------------------------------------------------------------------

def _read_projects() -> list[dict]:
    """Read the projects file; returns an empty list on first use / corruption."""
    path = _projects_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError):
        return []


def _write_projects(projects: list[dict]) -> None:
    """Atomically write the projects list to disk."""
    path = _projects_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(projects, indent=2, default=str))
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


# -------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------

def list_projects() -> list[dict]:
    """Return all projects sorted by ``created`` descending."""
    projects = _read_projects()
    projects.sort(key=lambda p: str(p.get("created", "")), reverse=True)
    return projects


def get_project(program_id: str) -> dict | None:
    """Return one project by ``program_id``, or ``None``."""
    for p in _read_projects():
        if p.get("program_id") == program_id:
            return p
    return None


def create_project(
    program_id: str,
    program_name: str,
    platform: str,
    engagement_id: str = "",
    targets_file: str = "",
) -> dict:
    """Create a new project entry and persist to ``projects.json``.

    Returns ``{"ok": True, "project": <entry>}`` on success or
    ``{"ok": False, "error": "..."}`` on failure.
    """
    valid_platforms = {"hackerone", "bugcrowd", "intigriti", "custom"}
    if platform not in valid_platforms:
        return {
            "ok": False,
            "error": f"Invalid platform '{platform}'. "
                     f"Must be one of: {', '.join(sorted(valid_platforms))}",
        }

    if not program_id or not program_name:
        return {
            "ok": False,
            "error": "program_id and program_name are required.",
        }

    # Reject duplicates
    existing = get_project(program_id)
    if existing is not None:
        return {"ok": False, "error": f"Project '{program_id}' already exists."}

    project: dict[str, Any] = {
        "program_id": program_id,
        "program_name": program_name,
        "platform": platform,
        "engagement_id": engagement_id,
        "state": "active",
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "targets_file": targets_file,
    }

    projects = _read_projects()
    projects.append(project)
    _write_projects(projects)

    return {"ok": True, "project": project}


def switch_project(program_id: str) -> dict:
    """Set ``active_project`` in the pack config and return the project.

    Requires the harness extension API (``halo_harness.ext.set_config``).
    Returns ``{"ok": False, "error": "..."}`` when the harness is
    unavailable or the project does not exist.
    """
    project = get_project(program_id)
    if project is None:
        return {"ok": False, "error": f"Project '{program_id}' not found."}

    if not _set_config("active_project", program_id):
        return {
            "ok": False,
            "error": "Could not write active_project config. "
                     "The harness extension API (halo_harness.ext.set_config) "
                     "may be unavailable.",
        }

    return {"ok": True, "project": project}


def get_active_project() -> dict | None:
    """Read ``active_project`` from the pack config and return the full project.

    Returns ``None`` when no active project is set, the project no longer
    exists, or the harness extension API is unavailable.
    """
    program_id = _get_config("active_project", "")
    if not program_id:
        return None
    return get_project(program_id)


def archive_project(program_id: str) -> dict:
    """Set a project's state to ``archived``.

    Returns ``{"ok": True, "project": <updated entry>}`` on success or
    ``{"ok": False, "error": "..."}`` on failure.
    """
    projects = _read_projects()
    for p in projects:
        if p.get("program_id") == program_id:
            p["state"] = "archived"
            _write_projects(projects)
            return {"ok": True, "project": p}
    return {"ok": False, "error": f"Project '{program_id}' not found."}


def delete_project(program_id: str) -> dict:
    """Remove a project from ``projects.json`` (does not delete data).

    Returns ``{"ok": True, "project": <removed entry>}`` or
    ``{"ok": False, "error": "..."}``.
    """
    projects = _read_projects()
    removed = None
    remaining: list[dict] = []
    for p in projects:
        if p.get("program_id") == program_id:
            removed = p
        else:
            remaining.append(p)
    if removed is None:
        return {"ok": False, "error": f"Project '{program_id}' not found."}
    _write_projects(remaining)
    return {"ok": True, "project": removed}


# -------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------

def _cli() -> None:
    args = sys.argv[1:]
    if not args:
        print(json.dumps({"ok": False, "error": "Usage: project_manager.py list | create <id> <name> <platform> | switch <id> | active | archive <id> | delete <id>"}))
        sys.exit(1)

    command = args[0]

    if command == "list":
        projects = list_projects()
        print(json.dumps({"ok": True, "projects": projects}, indent=2, default=str))
        sys.exit(0)

    if command == "create":
        if len(args) < 4:
            print(json.dumps({"ok": False, "error": "Usage: project_manager.py create <program_id> <program_name> <platform> [targets_file]"}))
            sys.exit(1)
        program_id = args[1]
        program_name = args[2]
        platform = args[3]
        targets_file = args[4] if len(args) > 4 else ""
        result = create_project(program_id, program_name, platform, "", targets_file)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result.get("ok") else 1)

    if command == "switch":
        if len(args) < 2:
            print(json.dumps({"ok": False, "error": "Usage: project_manager.py switch <program_id>"}))
            sys.exit(1)
        result = switch_project(args[1])
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result.get("ok") else 1)

    if command == "active":
        project = get_active_project()
        if project is None:
            # Could be no project or no harness — check harness separately
            print(json.dumps({"ok": True, "project": None, "note": "No active project set or harness unavailable."}))
        else:
            print(json.dumps({"ok": True, "project": project}, indent=2, default=str))
        sys.exit(0)

    if command == "archive":
        if len(args) < 2:
            print(json.dumps({"ok": False, "error": "Usage: project_manager.py archive <program_id>"}))
            sys.exit(1)
        result = archive_project(args[1])
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result.get("ok") else 1)

    if command == "delete":
        if len(args) < 2:
            print(json.dumps({"ok": False, "error": "Usage: project_manager.py delete <program_id>"}))
            sys.exit(1)
        result = delete_project(args[1])
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result.get("ok") else 1)

    print(json.dumps({"ok": False, "error": f"Unknown command: {command}. Commands: list, create, switch, active, archive, delete"}))
    sys.exit(1)


if __name__ == "__main__":
    _cli()