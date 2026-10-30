"""import_findings tests — field-user intake for the findings pipeline.

Builds a real FindingStore in a tmp dir and exercises the three import paths
(manual, JSON batch, scanner normalizer). Confirms that every written finding
is a candidate with source=import|scanner, has a real evidence ledger row, and
never smuggles in a confirmed status or judge decision.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from findings_store import FindingStore, FindingStoreError  # noqa: E402
import import_findings  # noqa: E402

_VALID = Path(__file__).resolve().parent.parent / "examples" / "fixtures" / "valid"


def _engagement() -> dict:
    eng = json.loads((_VALID / "engagement.json").read_text())
    eng["engagement_id"] = "eng-test-001"
    return eng


def _store(tmp_path: Path) -> FindingStore:
    return FindingStore.create(tmp_path / "engagement", _engagement())


def _base_finding(fid: str, title: str, description: str) -> dict:
    """A minimal schema-valid finding dict for JSON import tests."""
    return {
        "finding_id": fid,
        "engagement_id": "eng-test-001",
        "title": title,
        "category": "import:test",
        "description": description,
        "status": "candidate",
        "evidence": [{"ledger_ref": "x"}],
        "audit_history": [
            {"timestamp": "2026-10-29T00:00:00Z", "actor": "t", "action": "created"}
        ],
    }


def test_manual_import_creates_candidate_with_real_ledger_row(tmp_path: Path):
    store = _store(tmp_path)
    f = import_findings.import_manual(
        store,
        title="Missing rate limit on login",
        description="No rate limiting observed on /login.",
        target_ref="auth.example.com",
        severity="high",
        actor="field-user",
        evidence_note="Burp repeater sequence showing repeated 200 responses.",
    )
    assert f["status"] == "candidate"
    assert f["source"] == "import"
    assert f["finding_id"].startswith("imp-")
    assert f["finding_id"].endswith("missing-rate-limit-on-login")

    row = store.resolve_ledger_ref(f["evidence"][0]["ledger_ref"])
    assert row["artifact_sha256"] == f["evidence"][0]["artifact_sha256"]
    artifact = store.artifacts / row["artifact_sha256"] / "artifact.bin"
    assert artifact.exists()
    assert b"Burp repeater sequence" in artifact.read_bytes()


def test_json_import_imports_valid_and_reports_invalid(tmp_path: Path):
    store = _store(tmp_path)
    payload = [
        _base_finding("xx-01-one", "First imported finding", "Desc one"),
        {"finding_id": "bad", "title": "bad"},  # title too short, missing required fields
        _base_finding("xx-02-two", "Second imported finding", "Desc two"),
    ]
    result = import_findings.import_json(store, payload, actor="field-user")

    assert result["imported"] == 2
    assert len(result["finding_ids"]) == 2
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["index"] == 1
    assert "schema validation failed" in result["rejected"][0]["reason"]

    for fid in result["finding_ids"]:
        assert fid.startswith("imp-")
        stored = store.get_finding(fid)
        assert stored["status"] == "candidate"
        assert stored["source"] == "import"
        # evidence was replaced with a real ledger row
        assert stored["evidence"][0]["ledger_ref"].startswith("evidence/ledger.jsonl#")
        assert len(stored["evidence"][0]["artifact_sha256"]) == 64


def test_json_import_confirmed_claim_is_forced_to_candidate(tmp_path: Path):
    store = _store(tmp_path)
    payload = {
        **_base_finding("xx-01-conf", "Confirmed claim", "Claims to be confirmed"),
        "status": "confirmed",
        "validation": {"status": "reproduced", "validator_ref": "x", "independent": True},
        "reviewer_decision": {
            "decision": "confirmed",
            "rationale": "x",
            "confidence": "high",
            "evidence_refs": ["x"],
        },
    }
    result = import_findings.import_json(store, payload, actor="field-user")

    # Implementation choice: force to candidate rather than rejecting.
    assert result["imported"] == 1
    assert result["rejected"] == []
    f = store.get_finding(result["finding_ids"][0])
    assert f["status"] == "candidate"
    assert "validation" not in f
    assert "reviewer_decision" not in f
    assert f["source"] == "import"


def test_scanner_import_nuclei(tmp_path: Path):
    store = _store(tmp_path)
    raw = json.dumps({
        "template-id": "cve-2021-44228",
        "host": "https://target.lab",
        "matched-at": "https://target.lab/api/search",
        "type": "http",
        "info": {
            "name": "Log4j JNDI RCE",
            "description": "Remote code execution via JNDI injection",
            "severity": "critical",
        },
    })
    result = import_findings.import_scanner_output(store, "nuclei", raw, actor="scanner-pipe")

    assert result["imported"] == 1
    fid = result["finding_ids"][0]
    f = store.get_finding(fid)
    assert f["status"] == "candidate"
    assert f["source"] == "scanner"
    assert f["finding_id"].startswith("nu-")
    assert "scanner import by scanner-pipe" in f["audit_history"][-1]["detail"]

    row = store.resolve_ledger_ref(f["evidence"][0]["ledger_ref"])
    assert row["finding_id"] == fid


def test_collision_safe_ids(tmp_path: Path):
    store = _store(tmp_path)
    # Seed an existing import id that would collide by title slug.
    store.put_finding({
        "finding_id": "imp-01-missing-rate-limit-on-login",
        "engagement_id": "eng-test-001",
        "title": "Existing finding",
        "category": "import:test",
        "description": "Existing",
        "status": "candidate",
        "source": "import",
        "evidence": [{
            "ledger_ref": "evidence/ledger.jsonl#0000",
            "artifact_sha256": "0" * 64,
            "kind": "note",
            "sanitized": True,
        }],
        "audit_history": [
            {"timestamp": "2026-10-29T00:00:00Z", "actor": "t", "action": "created"}
        ],
    })

    f = import_findings.import_manual(
        store,
        title="Missing rate limit on login",
        description="Second one",
        target_ref="auth.example.com",
        severity="medium",
        actor="field-user",
        evidence_note="note",
    )
    assert f["finding_id"] == "imp-02-missing-rate-limit-on-login"


def test_cli_json_import(tmp_path: Path):
    store = _store(tmp_path)
    payload = [_base_finding("xx-01-cli", "CLI imported finding", "From CLI")]
    in_file = tmp_path / "in.json"
    in_file.write_text(json.dumps(payload))

    import_findings.main([
        str(tmp_path / "engagement"),
        "--json", str(in_file),
        "--actor", "cli-user",
    ])
    # main() prints to stdout; no exception means success.
    f = store.list_findings(status="candidate")[0]
    assert f["title"] == "CLI imported finding"
    assert f["source"] == "import"


def test_cli_refuses_missing_engagement(tmp_path: Path, capsys):
    with pytest.raises(SystemExit) as excinfo:
        import_findings.main([
            str(tmp_path / "nonexistent-engagement"),
            "--manual", "title=Something bad;description=x;target_ref=y;severity=info;evidence_note=z",
            "--actor", "cli-user",
        ])
    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "engagement-not-found" in captured.out
