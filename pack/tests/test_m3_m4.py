"""Milestone 3+4 tests: normalizers, Caido sanitization, findings store,
report generation. All offline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PACK_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACK_ROOT / "tools"))

from findings_store import FindingStore, FindingStoreError  # noqa: E402
import report as report_mod  # noqa: E402
import normalizers  # noqa: E402
from caido_adapter import sanitize_headers, normalize_exchange, CaidoClient, CaidoUnavailable  # noqa: E402

FIXTURES = PACK_ROOT / "examples" / "fixtures" / "valid"
jsonschema = pytest.importorskip("jsonschema")


@pytest.fixture()
def store(tmp_path):
    eng = json.loads((FIXTURES / "engagement.json").read_text())
    return FindingStore.create(tmp_path / "eng", eng)


# --- M4: findings store ------------------------------------------------------

def test_create_requires_valid_engagement(tmp_path):
    bad = json.loads((PACK_ROOT / "examples/fixtures/invalid"
                      / "engagement-bogus-activity.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        FindingStore.create(tmp_path / "bad", bad)


def test_evidence_chain_and_dedupe(store):
    r1 = store.add_evidence(b"GET /api/notes/1 ...", actor="hh-validator",
                            action="capture", finding_id="f-01")
    r2 = store.add_evidence(b"GET /api/notes/1 ...", actor="hh-validator",
                            action="capture", finding_id="f-01")
    assert r1["artifact_sha256"] == r2["artifact_sha256"]  # content dedupe
    assert r2["prev_hash"] == r1["hash"]
    assert store.verify_chain() == []
    assert len(store.evidence_rows()) == 2


def test_chain_tamper_detected(store):
    store.add_evidence(b"a", actor="x", action="y")
    store.add_evidence(b"b", actor="x", action="y")
    # Tamper with row 0's content.
    rows = store.ledger.read_text().splitlines()
    row = json.loads(rows[0])
    row["action"] = "never-happened"
    rows[0] = json.dumps(row)
    store.ledger.write_text("\n".join(rows) + "\n")
    problems = store.verify_chain()
    assert any("row 0" in p for x in [problems] for p in x), problems


def test_row_removal_detected(store):
    store.add_evidence(b"a", actor="x", action="y")
    store.add_evidence(b"b", actor="x", action="y")
    store.add_evidence(b"c", actor="x", action="y")
    lines = store.ledger.read_text().splitlines()
    del lines[1]  # remove the middle row
    store.ledger.write_text("\n".join(lines) + "\n")
    assert store.verify_chain() != []


def test_artifact_corruption_detected(store):
    sha_row = store.add_evidence(b"original", actor="x", action="y")
    p = store.artifacts / sha_row["artifact_sha256"] / "artifact.bin"
    p.write_bytes(b"tampered")
    problems = store.verify_chain()
    assert any("hash mismatch" in x for x in problems)


def test_finding_must_pass_schema(store):
    bad = json.loads((PACK_ROOT / "examples/fixtures/invalid"
                      / "finding-asserted-confirmed.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        store.put_finding(bad)


def test_finding_roundtrip_and_no_delete(store):
    f = json.loads((FIXTURES / "finding.json").read_text())
    store.put_finding(f)
    assert store.get_finding(f["finding_id"])["status"] == "confirmed"
    with pytest.raises(FindingStoreError):
        store.delete_finding(f["finding_id"])


def test_duplicate_marking(store):
    store.put_finding(json.loads((FIXTURES / "finding.json").read_text()))
    f = json.loads((FIXTURES / "finding.json").read_text())
    f["finding_id"] = "dl-02-second-instance"
    f["title"] = "Second instance of the same authz gap"
    store.put_finding(f)
    out = store.mark_duplicate("dl-02-second-instance",
                               "dl-01-object-level-authz", actor="hh-judge")
    assert out["status"] == "duplicate"
    assert out["duplicate_of"] == "dl-01-object-level-authz"
    with pytest.raises(FindingStoreError):
        store.mark_duplicate("dl-02-second-instance", "dl-02-second-instance",
                             actor="hh-judge")


def test_findings_persist_across_instances(store, tmp_path):
    f = json.loads((FIXTURES / "finding.json").read_text())
    store.put_finding(f)
    # A NEW store over the same tree sees it — persistence across
    # sessions and model changes.
    assert FindingStore(tmp_path / "eng").list_findings()


# --- M4: report generation ---------------------------------------------------

def test_report_from_confirmed_only(store):
    confirmed = json.loads((FIXTURES / "finding.json").read_text())
    store.put_finding(confirmed)
    cand = json.loads((FIXTURES / "finding.json").read_text())
    cand["finding_id"] = "dl-03-unvalidated"
    cand["status"] = "candidate"
    cand.pop("validation"); cand.pop("reviewer_decision")
    store.put_finding(cand)
    out = report_mod.generate_report(store)
    text = out.read_text()
    assert "dl-01-object-level-authz" in text            # confirmed: detailed
    assert "### dl-03-unvalidated" not in text           # candidate: NOT detailed
    assert "dl-03-unvalidated | candidate" in text       # but listed in coverage
    assert "ledger row" in text                          # evidence trace present
    assert out == store.report_dir / "report.md"


def test_report_refuses_broken_chain(store):
    store.put_finding(json.loads((FIXTURES / "finding.json").read_text()))
    store.add_evidence(b"x", actor="a", action="b")
    p = store.ledger
    lines = p.read_text().splitlines()
    row = json.loads(lines[0]); row["actor"] = "evil"; lines[0] = json.dumps(row)
    p.write_text("\n".join(lines) + "\n")
    with pytest.raises(report_mod.ReportError):
        report_mod.generate_report(store)


# --- M3: scanner normalizers --------------------------------------------------

NUCLEI_FIXTURE = """{"template-id":"CVE-2026-9999","info":{"name":"Test Injection","description":"A test template","severity":"high"},"type":"http","host":"https://vuln-app.test.lab","matched-at":"https://vuln-app.test.lab:8080/search?q="}
{"template-id":"CVE-2026-9999","info":{"name":"Test Injection","description":"A test template","severity":"high"},"type":"http","host":"https://vuln-app.test.lab","matched-at":"https://vuln-app.test.lab:8080/search?q="}
{"template-id":"tech-detect","info":{"name":"Tech detect","severity":"info"},"type":"http","host":"https://vuln-app.test.lab","matched-at":"https://vuln-app.test.lab:8080/"}
"""

SEMGREP_FIXTURE = json.dumps({
    "results": [
        {"check_id": "python.lang.security.audit.dangerous-system_call",
         "path": "app/run.py", "start": {"line": 42},
         "extra": {"message": "os.system with user input", "severity": "WARNING"}},
    ]})


def test_nuclei_normalizer(store, tmp_path):
    f = tmp_path / "nuclei.jsonl"
    f.write_text(NUCLEI_FIXTURE)
    cands = normalizers.normalize_nuclei(f, "demo-lab-01")
    assert len(cands) == 2                      # duplicate template match deduped
    assert all(c["status"] == "candidate" for c in cands)
    assert "never confirmation" in cands[0]["description"]
    for c in cands:                             # every candidate passes the schema
        store.put_finding(c)


def test_semgrep_normalizer(store, tmp_path):
    f = tmp_path / "semgrep.json"
    f.write_text(SEMGREP_FIXTURE)
    cands = normalizers.normalize_semgrep(f, "demo-lab-01")
    assert len(cands) == 1
    assert "app/run.py" in cands[0]["title"]
    store.put_finding(cands[0])                 # schema-valid


# --- M3: Caido adapter --------------------------------------------------------

def test_caido_header_sanitization():
    out = sanitize_headers({"Authorization": "Bearer secret",
                            "Cookie": "session=x",
                            "Content-Type": "application/json",
                            "X-Api-Key": "k"})
    assert out["Authorization"] == "[REDACTED]"
    assert out["Cookie"] == "[REDACTED]"
    assert out["X-Api-Key"] == "[REDACTED]"
    assert out["Content-Type"] == "application/json"


def test_caido_normalize_exchange():
    ex = {"id": "ex-1",
          "request": {"method": "GET", "host": "vuln-app.test.lab",
                      "path": "/api/notes/1", "scheme": "https",
                      "headers": {"Authorization": "Bearer secret"},
                      "body": ""},
          "response": {"status": 200,
                       "headers": {"Set-Cookie": "sid=x"},
                       "body": '{"note": "alice data"}'}}
    obs = normalize_exchange(ex)
    assert obs["sanitized"] is True
    assert obs["request"]["headers"]["Authorization"] == "[REDACTED]"
    assert obs["response"]["headers"]["Set-Cookie"] == "[REDACTED]"
    assert obs["request"]["url"] == "https://vuln-app.test.lab/api/notes/1"
    assert obs["source_exchange_id"] == "ex-1"


def test_caido_client_refuses_unverified_live_use():
    with pytest.raises(CaidoUnavailable):
        CaidoClient().list_exchanges()   # draft guard: no silent guessing
