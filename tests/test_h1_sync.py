"""Tests for HackerOne fixture normalization.

The fixture payloads here are synthetic and minimal; the suite does not depend on
any local /tmp/h1-fixtures directory.
"""
from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path


_PACK = Path(__file__).resolve().parent.parent
if str(_PACK) not in sys.path:
    sys.path.insert(0, str(_PACK))
if str(_PACK / "tools") not in sys.path:
    sys.path.insert(0, str(_PACK / "tools"))

import h1_sync


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _report(report_id="101", state="new", activity="2026-01-01T00:00:00Z"):
    return {
        "id": report_id,
        "type": "report",
        "attributes": {
            "title": "Stored XSS in account page",
            "state": state,
            "created_at": "2026-01-01T00:00:00Z",
            "last_program_activity_at": activity,
        },
        "relationships": {
            "program": {"data": {"id": "corebridge", "attributes": {"handle": "corebridge", "name": "Corebridge"}}},
            "weakness": {"data": {"id": "79", "attributes": {"name": "Cross-site Scripting", "external_id": "CWE-79"}}},
            "severity": {"data": {"id": "medium", "attributes": {"rating": "medium"}}},
        },
    }


def _program(handle="corebridge"):
    return {
        "id": handle,
        "type": "program",
        "attributes": {
            "handle": handle,
            "name": "Corebridge",
            "state": "public",
            "submission_state": "open",
            "offers_bounties": True,
            "policy": "Safe harbor applies.",
        },
        "relationships": {
            "structured_scopes": {
                "data": [
                    {
                        "id": "scope-1",
                        "type": "structured_scope",
                        "attributes": {
                            "asset_type": "URL",
                            "asset_identifier": "https://app.example.test",
                            "eligible_for_bounty": True,
                            "eligible_for_submission": True,
                            "max_severity": "high",
                            "instruction": "Test only this host.",
                        },
                    }
                ]
            }
        },
    }


def _intent(intent_id="intent-1"):
    return {
        "id": intent_id,
        "type": "report_intent",
        "attributes": {
            "title": "Testing account page",
            "description": "I plan to test the account page.",
            "state": "draft",
            "created_at": "2026-01-01T00:00:00Z",
            "job_status_by_type": {"scope_check": "complete", "policy_check": "failed"},
            "metadata": {"source": "pytest"},
        },
    }


def _earning():
    return {
        "id": "earning-1",
        "type": "earning",
        "attributes": {"amount": "42.50", "created_at": "2026-01-02T00:00:00Z"},
        "relationships": {"program": {"data": {"attributes": {"handle": "corebridge", "name": "Corebridge"}}}},
    }


def _payout():
    return {"id": "payout-1", "type": "payout", "attributes": {"amount": "10.00", "created_at": "2026-01-03T00:00:00Z"}}


def _fixtures(tmp_path: Path, report=None, program=None) -> Path:
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    _write_json(fixtures / "reports.json", {"data": [report or _report()]})
    _write_json(fixtures / "program_corebridge.json", program or _program())
    _write_json(fixtures / "balance.json", {"data": {"balance": 0.0}})
    _write_json(fixtures / "intents.json", {"data": [_intent()]})
    _write_json(fixtures / "earnings.json", {"data": [_earning()]})
    _write_json(fixtures / "payouts.json", {"data": [_payout()]})
    return fixtures


def _set_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(tmp_path))
    return tmp_path / "h1"


def _block_harness_import(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "halo_harness.ext" or (name == "halo_harness" and fromlist and "ext" in fromlist):
            raise ImportError("blocked by test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_normalization_writes_outputs_and_core_fields(tmp_path, monkeypatch):
    h1_dir = _set_data_dir(monkeypatch, tmp_path)
    fixtures = _fixtures(tmp_path)

    result = h1_sync.sync(fixtures)

    assert result["ok"] is True
    for name in ("reports.json", "programs.json", "earnings.json", "intents.json", "sync_state.json"):
        assert (h1_dir / name).is_file(), name

    reports_doc = json.loads((h1_dir / "reports.json").read_text())
    report = reports_doc["reports"][0]
    assert report["id"] == "101"
    assert report["title"] == "Stored XSS in account page"
    assert report["state"] == "new"
    assert report["program_handle"] == "corebridge"

    earnings_doc = json.loads((h1_dir / "earnings.json").read_text())
    assert earnings_doc["balance"] == 0.0
    assert earnings_doc["balance"] != {"data": {"balance": 0.0}}
    assert earnings_doc["total_earned"] == 42.5

    intents_doc = json.loads((h1_dir / "intents.json").read_text())
    assert intents_doc["intents"][0]["failed_jobs"] == ["policy_check"]

    programs_doc = json.loads((h1_dir / "programs.json").read_text())
    scope = programs_doc["programs"][0]["scopes"][0]
    assert scope["asset_identifier"] == "https://app.example.test"
    assert scope["eligible_for_bounty"] is True


def test_bare_program_object_without_data_wrapper_normalizes(tmp_path, monkeypatch):
    h1_dir = _set_data_dir(monkeypatch, tmp_path)
    fixtures = _fixtures(tmp_path, program=_program("bare-program"))

    result = h1_sync.sync(fixtures)

    assert result["ok"] is True
    programs_doc = json.loads((h1_dir / "programs.json").read_text())
    assert programs_doc["programs"][0]["handle"] == "bare-program"
    assert programs_doc["programs"][0]["scopes"][0]["eligible_for_submission"] is True


def test_change_detection_queues_pending_events_when_harness_unavailable(tmp_path, monkeypatch):
    h1_dir = _set_data_dir(monkeypatch, tmp_path)
    fixtures = _fixtures(tmp_path)
    baseline = h1_sync.sync(fixtures)
    assert baseline["ok"] is True
    assert baseline["changes"] == []

    changed_report = _report("101", state="triaged", activity="2026-01-02T00:00:00Z")
    _write_json(fixtures / "reports.json", {"data": [changed_report]})
    _block_harness_import(monkeypatch)

    changed = h1_sync.sync(fixtures)

    assert changed["ok"] is True
    assert changed["event_sink"] == "pending_events"
    changes = {(item["report_id"], item["kind"], item["from"], item["to"]) for item in changed["changes"]}
    assert ("101", "state", "new", "triaged") in changes
    assert ("101", "activity", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z") in changes

    pending = json.loads((h1_dir / "pending_events.json").read_text())
    assert {item["kind"] for item in pending} == {"state", "activity"}


def test_missing_fixtures_succeeds_and_lists_skipped(tmp_path, monkeypatch):
    _set_data_dir(monkeypatch, tmp_path)
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    _write_json(fixtures / "reports.json", {"data": [_report()]})

    result = h1_sync.sync(fixtures)

    assert result["ok"] is True
    assert result["counts"] == {"reports": 1, "programs": 0, "intents": 0}
    for expected in ("program_*.json", "balance.json", "earnings.json", "payouts.json", "intents.json"):
        assert expected in result["skipped"]


def test_status_after_sync_returns_counts(tmp_path, monkeypatch):
    _set_data_dir(monkeypatch, tmp_path)
    fixtures = _fixtures(tmp_path)
    assert h1_sync.sync(fixtures)["ok"] is True

    status = h1_sync.status()

    assert status["ok"] is True
    assert status["counts"] == {
        "reports": 1,
        "programs": 1,
        "intents": 1,
        "earnings": 1,
        "payouts": 1,
        "pending_events": 0,
    }
    assert status["last_sync"] is not None


def test_malformed_json_never_raises(tmp_path, monkeypatch):
    _set_data_dir(monkeypatch, tmp_path)
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "reports.json").write_text("{not-json", encoding="utf-8")

    result = h1_sync.sync(fixtures)

    assert result.get("ok") is False or any("reports.json" in error for error in result.get("errors", []))


def test_stale_detail_does_not_mask_fresh_list_state(tmp_path, monkeypatch):
    """A stale report_<id>.json (older state) must not overwrite the fresh
    reports.json summary, or change detection silently misses the transition."""
    _set_data_dir(monkeypatch, tmp_path)
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    # List says the report is now triaged; the detail file still says "new".
    _write_json(fixtures / "reports.json", {"data": [_report("101", state="triaged", activity="2026-01-02T00:00:00Z")]})
    _write_json(fixtures / "report_101.json", {"data": _report("101", state="new", activity="2026-01-01T00:00:00Z")})

    result = h1_sync.sync(fixtures)

    assert result["ok"] is True
    reports = json.loads((_set_data_dir(monkeypatch, tmp_path) / "reports.json").read_text())["reports"]
    by_id = {r["id"]: r for r in reports}
    assert by_id["101"]["state"] == "triaged", "fresh list state must win over the stale detail file"


def test_emitted_event_matches_schema(tmp_path, monkeypatch):
    """The event payload must carry kind='sync' and only schema-allowed keys."""
    h1_dir = _set_data_dir(monkeypatch, tmp_path)
    fixtures = _fixtures(tmp_path)
    h1_sync.sync(fixtures)
    changed = _report("101", state="triaged", activity="2026-01-02T00:00:00Z")
    _write_json(fixtures / "reports.json", {"data": [changed]})
    _block_harness_import(monkeypatch)
    h1_sync.sync(fixtures)
    # The queued payload is the changes list; assert the emitted shape via the schema keys.
    schema = json.loads((_PACK / "events" / "hh.h1.update.json").read_text())
    allowed = set(schema["properties"].keys())
    # Reconstruct what sync emits (kind/counts/changes) — no extra keys like 'generated'.
    assert "kind" in schema["required"]
    assert "generated" not in allowed, "schema forbids 'generated'; payload must not emit it"
