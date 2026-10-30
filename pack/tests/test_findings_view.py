"""findings_view tests — the Studio panel data layer.

Builds a real FindingStore in a tmp dir, puts findings in every state
(confirmed ones with a real ledger row so evidence refs resolve), and
asserts the display mapping, counts strip, row ordering, and event
payloads.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from findings_store import FindingStore  # noqa: E402
import findings_view  # noqa: E402

_VALID = Path(__file__).resolve().parent.parent / "examples" / "fixtures" / "valid"


def _engagement() -> dict:
    eng = json.loads((_VALID / "engagement.json").read_text())
    eng["engagement_id"] = "eng-test-001"
    return eng


def _store(tmp_path: Path) -> FindingStore:
    return FindingStore.create(tmp_path / "engagement", _engagement())


def _finding(fid: str, status: str, store: FindingStore | None = None, **over) -> dict:
    """A schema-valid finding from the valid fixture, status overridden.
    Confirmed findings get a REAL ledger row so evidence refs resolve."""
    f = json.loads((_VALID / "finding.json").read_text())
    f["finding_id"] = fid
    f["engagement_id"] = "eng-test-001"
    f["status"] = status
    f["audit_history"] = [{"timestamp": "2026-10-29T00:00:00Z", "actor": "t", "action": "created"}]
    if status == "confirmed" and store is not None:
        row = store.add_evidence(b"proof-" + fid.encode(), actor="tester",
                                 action="captured", finding_id=fid)
        f["evidence"] = [{
            "ledger_ref": f"evidence/ledger.jsonl#{row['seq']:04d}",
            "artifact_sha256": row["artifact_sha256"],
            "kind": "request-response",
            "sanitized": True,
        }]
    else:
        # candidates still carry >=1 evidence entry (schema minItems: 1) —
        # a shape-valid placeholder; refs only resolve for confirmed.
        f["evidence"] = [{
            "ledger_ref": "evidence/ledger.jsonl#0000",
            "artifact_sha256": "0" * 64,
            "kind": "request-response",
            "sanitized": True,
        }]
        f.pop("reviewer_decision", None)
        f.pop("validation", None)
    f.update(over)
    return f


def test_display_state_mapping_and_counts(tmp_path):
    store = _store(tmp_path)
    store.put_finding(_finding("dl-01-1", "candidate", source="passive-traffic"))
    store.put_finding(_finding("dl-01-2", "needs_validation", validation={"status": "reproduced", "validator_ref": "hh-validator", "independent": True}))
    store.put_finding(_finding("dl-01-3", "confirmed", store=store,
                               severity="high"))
    store.put_finding(_finding("dl-01-4", "rejected"))

    result = findings_view.write_summary(tmp_path / "engagement",
                                         out_dir=tmp_path / "data" / "findings")
    assert result["rows"] == 4

    summary = json.loads((tmp_path / "data" / "findings" / "summary.json").read_text())
    assert summary["engagement_id"] == "eng-test-001"
    states = {r["finding_id"]: r["state"] for r in summary["rows"]}
    assert states == {"dl-01-1": "identified", "dl-01-2": "reviewed",
                      "dl-01-3": "confirmed", "dl-01-4": "rejected"}

    counts = (tmp_path / "data" / "findings" / "counts.md").read_text()
    assert "1 identified" in counts and "1 reviewed" in counts and "1 confirmed" in counts
    assert "rejected" not in counts  # terminal states stay off the strip


def test_confirmed_sort_first(tmp_path):
    store = _store(tmp_path)
    store.put_finding(_finding("dl-01-a", "candidate"))
    store.put_finding(_finding("dl-01-b", "confirmed", store=store))
    rows = findings_view.summary_rows(store)
    assert rows[0]["finding_id"] == "dl-01-b"


def test_finding_event_payload():
    f = _finding("dl-01-9", "candidate", source="import",
                 target_ref="api.example.com")
    ev = findings_view.finding_event(f, actor="validator")
    assert ev["state"] == "identified"
    assert ev["source"] == "import"
    assert ev["target_ref"] == "api.example.com"
    assert ev["actor"] == "validator"


def test_empty_store(tmp_path):
    _store(tmp_path)
    result = findings_view.write_summary(tmp_path / "engagement",
                                         out_dir=tmp_path / "d" / "findings")
    assert result["rows"] == 0
    counts = (tmp_path / "d" / "findings" / "counts.md").read_text()
    assert "0 identified · 0 reviewed · 0 confirmed" in counts
