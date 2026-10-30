#!/usr/bin/env python3
"""Engage-mode engine — scope as data, not location.

A single active-engagement state file in the pack's data folder gates every
subsequent `/hh` command and the PreToolUse hook. Fail-closed: no valid,
in-window engagement record, no engagement.

Stdlib-only by pack convention.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _data_dir() -> Path:
    """The pack's OWN data folder. Env override for tests."""
    d = Path(os.environ.get("HALO_HACKER_DATA_DIR")
             or (Path(__file__).resolve().parent.parent / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_path() -> Path:
    return _data_dir() / "engage-state.json"


def _history_path() -> Path:
    return _data_dir() / "engage-history.jsonl"


def _gate_log_path() -> Path:
    return _data_dir() / "gate-log.jsonl"


def _parse_window_ts(ts: str) -> float:
    """ISO-8601 (Z-suffixed in our fixtures); tolerant parse, never guesses."""
    t = str(ts).replace("Z", "+00:00")
    return datetime.fromisoformat(t).timestamp() if t else 0.0


def _now_ts() -> float:
    return time.time()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, separators=(",", ":")) + "\n")


def load_engagement(engagement_root: Path) -> dict:
    """Read the engagement record from an engagement tree."""
    path = Path(engagement_root) / "engagement.json"
    if not path.is_file():
        raise ValueError(f"engagement record not found: {path}")
    return _load_json(path)


def check_window(engagement: dict) -> tuple[bool, str]:
    """Return (ok, error_message). Fail-closed."""
    window = engagement.get("window") or {}
    start = window.get("start")
    expires = window.get("expires")
    if not start or not expires:
        return False, "engagement window missing start or expires"
    now = _now_ts()
    try:
        start_ts = _parse_window_ts(start)
        expires_ts = _parse_window_ts(expires)
    except Exception as e:
        return False, f"engagement window unparsable: {e}"
    if now < start_ts:
        return False, f"engagement window opens {start}; too early"
    if now > expires_ts:
        return False, f"engagement window expired {expires}; refusing"
    return True, ""


def _count_targets(engagement_root: Path, engagement: dict) -> int:
    """Count included scope targets from the engagement's targets file."""
    targets_file = engagement.get("targets_file", "scope/targets.json")
    path = Path(engagement_root) / targets_file
    if not path.is_file():
        return 0
    try:
        targets = _load_json(path)
        return len(targets.get("includes", []))
    except Exception:
        return 0


def state() -> dict | None:
    """Raw state file contents, or None if no state file. Does NOT check
    window expiry — callers that need runtime enforcement use current()."""
    path = _state_path()
    if not path.is_file():
        return None
    try:
        return _load_json(path)
    except Exception:
        return None


def current() -> dict | None:
    """The active engagement state, or None if none/expired."""
    s = state()
    if not s or not s.get("active"):
        return None
    try:
        engagement = load_engagement(Path(s["engagement_root"]))
    except Exception:
        return None
    ok, error = check_window(engagement)
    if not ok:
        return None
    return s


def is_engaged() -> bool:
    return current() is not None


def engage(engagement_root: Path, *, lineup: str | None = None) -> dict:
    """Validate engagement window and write active state. Fail-closed."""
    root = Path(engagement_root)
    engagement = load_engagement(root)

    ok, error = check_window(engagement)
    if not ok:
        return {"ok": False, "error": error}

    existing = state()
    if existing and existing.get("active"):
        return {
            "ok": False,
            "error": f"already engaged: {existing.get('engagement_id')} — disengage first",
        }

    s = {
        "engagement_id": engagement["engagement_id"],
        "engagement_root": str(root.resolve()),
        "engaged_at": _utc_now(),
        "lineup": lineup,
        "active": True,
    }
    _write_json(_state_path(), s)

    return {
        "ok": True,
        "engagement_id": s["engagement_id"],
        "window_end": engagement["window"]["expires"],
        "targets_n": _count_targets(root, engagement),
    }


def status() -> dict:
    """Current engagement status, including remaining window seconds."""
    s = state()
    if not s or not s.get("active"):
        return {"ok": True, "active": False}

    try:
        engagement = load_engagement(Path(s["engagement_root"]))
    except Exception as e:
        return {"ok": False, "active": False, "error": f"cannot load engagement: {e}"}

    ok, error = check_window(engagement)
    if not ok:
        return {
            "ok": True,
            "active": False,
            "expired": True,
            "engagement_id": s.get("engagement_id"),
            "error": error,
        }

    expires_ts = _parse_window_ts(engagement["window"]["expires"])
    remaining = int(expires_ts - _now_ts())
    return {
        "ok": True,
        "active": True,
        "engagement_id": s.get("engagement_id"),
        "engagement_root": s.get("engagement_root"),
        "lineup": s.get("lineup"),
        "window_end": engagement["window"]["expires"],
        "window_remaining_seconds": remaining,
    }


def disengage() -> dict:
    """Write end-state to history and remove the active state file."""
    s = state()
    if not s:
        return {"ok": True, "active": False, "note": "no active engagement"}

    _append_jsonl(_history_path(), {
        "engagement_id": s.get("engagement_id"),
        "engaged_at": s.get("engaged_at"),
        "disengaged_at": _utc_now(),
    })

    _state_path().unlink(missing_ok=True)
    return {"ok": True, "active": False, "engagement_id": s.get("engagement_id")}


# ---------------------------------------------------------------------------
# Scope-guard helpers (used by hooks/scope_guard.py)
# ---------------------------------------------------------------------------

_HOSTNAME_RE = re.compile(
    r"(?:(?<=://)|(?<=@)|\b)"
    r"((?:\d{1,3}\.){3}\d{1,3}|(?:[a-z0-9_-]+\.)+[a-z]{2,}|localhost)"
    r"(?::\d+)?(?:/|$|\s)",
    re.IGNORECASE,
)

# File extensions that commonly appear in CLI args and should not be treated
# as network hosts.
_FILE_EXTS = {
    "txt", "md", "py", "sh", "json", "yaml", "yml", "js", "ts", "html", "htm",
    "php", "log", "csv", "xml", "conf", "cfg", "ini", "env", "db", "sqlite",
    "sql", "png", "jpg", "jpeg", "gif", "pdf", "zip", "tar", "gz", "tgz", "bak",
    "pem", "key", "crt", "lst", "dic", "out", "tmp", "bin", "exe", "dll", "so",
}


def _looks_like_filename(token: str) -> bool:
    if "." not in token:
        return False
    ext = token.rsplit(".", 1)[-1].lower()
    return ext in _FILE_EXTS


def extract_hosts(command: str) -> set[str]:
    """Extract hostnames and IPv4 addresses from a shell command."""
    found: set[str] = set()
    for m in _HOSTNAME_RE.finditer(command):
        token = m.group(1).lower()
        if _looks_like_filename(token):
            continue
        found.add(token)
    return found


def _match_hostname(host: str, pattern: str) -> bool:
    """Exact match or wildcard *.suffix."""
    host = host.lower().strip()
    pattern = pattern.lower().strip()
    if pattern.startswith("*."):
        suffix = pattern[1:]  # .example.com
        return host == pattern[2:] or host.endswith(suffix)
    return host == pattern


def _match_ipv4_to_target(ip: ipaddress.IPv4Address, target: dict) -> bool:
    if "cidr" in target:
        try:
            network = ipaddress.ip_network(target["cidr"], strict=False)
            return ip in network
        except ValueError:
            return False
    if "ip_range" in target:
        rng = target["ip_range"]
        try:
            lo = ipaddress.ip_address(rng.get("from", ""))
            hi = ipaddress.ip_address(rng.get("to", ""))
        except ValueError:
            return False
        if isinstance(lo, ipaddress.IPv4Address) and isinstance(hi, ipaddress.IPv4Address):
            return lo <= ip <= hi
    if "hostname" in target:
        # An IP can only match a hostname target if the pattern is not a CIDR/range.
        return False
    return False


def _match_host_to_target(host: str, target: dict) -> bool:
    try:
        ip = ipaddress.ip_address(host)
        if isinstance(ip, ipaddress.IPv4Address):
            return _match_ipv4_to_target(ip, target)
        return False
    except ValueError:
        pass

    if "hostname" in target:
        return _match_hostname(host, target["hostname"])
    return False


def _host_in_targets(host: str, targets: list[dict]) -> bool:
    return any(_match_host_to_target(host, t) for t in targets)


def classify(command: str, targets: dict) -> dict:
    """Pure classification used by the scope guard and its tests.

    Returns {"decision": "allow"} or {"decision": "block", "reason": ...}.
    """
    includes = list(targets.get("includes", []))
    exclusions = list(targets.get("exclusions", []))
    hosts = extract_hosts(command)

    if not hosts:
        return {"decision": "allow"}

    for host in hosts:
        if _host_in_targets(host, exclusions):
            return {"decision": "block", "reason": f"excluded host: {host}"}
        if not _host_in_targets(host, includes):
            return {"decision": "block", "reason": f"out of scope: {host}"}

    return {"decision": "allow"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    args = sys.argv[1:]
    if not args:
        print(json.dumps({"ok": False, "error": "usage: engage.py engage <root> [--lineup X] | status | disengage"}))
        sys.exit(2)

    cmd = args[0]
    if cmd == "engage":
        if len(args) < 2:
            print(json.dumps({"ok": False, "error": "engage requires an engagement root"}))
            sys.exit(2)
        root = Path(args[1])
        lineup = None
        if "--lineup" in args:
            idx = args.index("--lineup")
            if idx + 1 < len(args):
                lineup = args[idx + 1]
        print(json.dumps(engage(root, lineup=lineup)))
    elif cmd == "status":
        print(json.dumps(status()))
    elif cmd == "disengage":
        print(json.dumps(disengage()))
    else:
        print(json.dumps({"ok": False, "error": f"unknown command: {cmd}"}))
        sys.exit(2)


if __name__ == "__main__":
    _cli()
