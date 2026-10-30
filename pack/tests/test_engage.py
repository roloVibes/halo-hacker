"""Engage-mode engine tests.

Covers the engage/disengage lifecycle, window enforcement, double-engage
refusal, expiry, and the scope guard's host classification.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import engage  # noqa: E402

_VALID = Path(__file__).resolve().parent.parent / "examples" / "fixtures" / "valid"


def _engagement(window_start: str = "2026-10-20T09:00:00Z",
                window_expires: str = "2026-11-04T18:00:00Z",
                status: str = "active") -> dict:
    eng = json.loads((_VALID / "engagement.json").read_text())
    eng["engagement_id"] = "eng-test-001"
    eng["window"] = {"start": window_start, "expires": window_expires}
    eng["status"] = status
    return eng


def _write_engagement(tmp_path: Path, engagement: dict, targets: dict | None = None) -> Path:
    root = tmp_path / "engagement"
    root.mkdir(parents=True, exist_ok=True)
    (root / "engagement.json").write_text(json.dumps(engagement), encoding="utf-8")
    scope_dir = root / "scope"
    scope_dir.mkdir(exist_ok=True)
    (scope_dir / "targets.json").write_text(
        json.dumps(targets or {"schema_version": 1, "includes": [{"hostname": "app.example.com"}], "exclusions": []}),
        encoding="utf-8",
    )
    return root


def test_engage_lifecycle(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(data_dir))

    root = _write_engagement(tmp_path, _engagement())
    result = engage.engage(root)
    assert result["ok"] is True
    assert result["engagement_id"] == "eng-test-001"
    assert result["targets_n"] == 1
    assert "window_end" in result

    state_path = data_dir / "engage-state.json"
    assert state_path.is_file()
    state = json.loads(state_path.read_text())
    assert state["active"] is True
    assert state["engagement_root"] == str(root.resolve())

    status = engage.status()
    assert status["ok"] is True
    assert status["active"] is True
    assert status["engagement_id"] == "eng-test-001"
    assert status["window_remaining_seconds"] > 0

    dis = engage.disengage()
    assert dis["ok"] is True
    assert dis["active"] is False
    assert not state_path.exists()

    history = list((data_dir / "engage-history.jsonl").read_text().splitlines())
    assert len(history) == 1
    entry = json.loads(history[0])
    assert entry["engagement_id"] == "eng-test-001"
    assert "engaged_at" in entry
    assert "disengaged_at" in entry


def test_engage_window_fail_closed(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(data_dir))

    root = _write_engagement(
        tmp_path,
        _engagement(window_start="2026-09-01T00:00:00Z", window_expires="2026-09-02T00:00:00Z"),
    )
    result = engage.engage(root)
    assert result["ok"] is False
    assert "expired" in result["error"]
    assert not (data_dir / "engage-state.json").exists()


def test_engage_double_refused(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(data_dir))

    root = _write_engagement(tmp_path, _engagement())
    assert engage.engage(root)["ok"] is True

    second = engage.engage(root, lineup="hh-web-app-assessment")
    assert second["ok"] is False
    assert "already engaged" in second["error"]
    assert "eng-test-001" in second["error"]


def test_status_remaining_seconds(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(data_dir))

    root = _write_engagement(
        tmp_path,
        _engagement(window_start="2026-10-28T00:00:00Z", window_expires="3026-10-30T00:00:00Z"),
    )
    engage.engage(root)
    status = engage.status()
    assert status["ok"] is True
    assert status["active"] is True
    # Roughly a century remaining (in seconds).
    assert status["window_remaining_seconds"] > 3_000_000_000


def test_expiry_flips_is_engaged(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(data_dir))

    root = _write_engagement(
        tmp_path,
        _engagement(window_start="2026-10-01T00:00:00Z", window_expires="2026-10-02T00:00:00Z"),
    )
    # Simulate a stale active state file left behind after the window expired.
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "engage-state.json").write_text(json.dumps({
        "engagement_id": "eng-test-001",
        "engagement_root": str(root.resolve()),
        "engaged_at": "2026-10-01T12:00:00Z",
        "lineup": None,
        "active": True,
    }), encoding="utf-8")

    # State file exists, but window is expired.
    assert engage.current() is None
    assert engage.is_engaged() is False

    status = engage.status()
    assert status["ok"] is True
    assert status["active"] is False
    assert status["expired"] is True


def test_scope_guard_not_engaged_allows(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(data_dir))
    # No state file → not engaged → guard allows regardless of command.
    payload = {"tool_name": "Bash", "tool_input": {"command": "curl http://evil.com"}}
    assert _run_guard(payload)["decision"] == "allow"


def test_scope_guard_non_bash_allows(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(data_dir))
    root = _write_engagement(tmp_path, _engagement())
    engage.engage(root)
    payload = {"tool_name": "Read", "tool_input": {"file_path": "/etc/passwd"}}
    assert _run_guard(payload)["decision"] == "allow"


def test_scope_guard_in_scope_allows(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(data_dir))
    root = _write_engagement(tmp_path, _engagement())
    engage.engage(root)
    payload = {"tool_name": "Bash", "tool_input": {"command": "curl https://app.example.com/path"}}
    assert _run_guard(payload)["decision"] == "allow"


def test_scope_guard_out_of_scope_blocks_and_logs(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(data_dir))
    root = _write_engagement(tmp_path, _engagement())
    engage.engage(root)
    payload = {"tool_name": "Bash", "tool_input": {"command": "curl http://evil.com"}}

    decision = _run_guard(payload)
    assert decision["decision"] == "block"
    assert "evil.com" in decision["reason"]
    assert decision["engagement_id"] == "eng-test-001"

    log_lines = list((data_dir / "gate-log.jsonl").read_text().splitlines())
    assert len(log_lines) == 1
    entry = json.loads(log_lines[0])
    assert entry["engagement_id"] == "eng-test-001"
    assert "evil.com" in entry["reason"]
    assert "curl http://evil.com" == entry["command"]


def test_classify_unit():
    targets = {
        "includes": [
            {"hostname": "app.example.com"},
            {"hostname": "*.api.example.com"},
            {"cidr": "10.0.0.0/24"},
            {"ip_range": {"from": "192.168.1.1", "to": "192.168.1.10"}},
        ],
        "exclusions": [
            {"hostname": "admin.example.com"},
            {"cidr": "10.0.0.1/32"},
        ],
    }
    assert engage.classify("curl https://app.example.com", targets)["decision"] == "allow"
    assert engage.classify("curl https://sub.api.example.com", targets)["decision"] == "allow"
    assert engage.classify("curl http://evil.com", targets)["decision"] == "block"
    assert engage.classify("ping 10.0.0.5", targets)["decision"] == "allow"
    assert engage.classify("ping 10.0.0.1", targets)["decision"] == "block"
    assert engage.classify("ping 192.168.1.5", targets)["decision"] == "allow"
    assert engage.classify("ls -la", targets)["decision"] == "allow"


def _run_guard(payload: dict) -> dict:
    guard = Path(__file__).resolve().parent.parent / "hooks" / "scope_guard.py"
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, str(guard)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    if result.stdout.strip():
        return json.loads(result.stdout)
    return {"decision": "allow"}
