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


def seed_confirmed(store, finding):
    """Give a confirmed finding resolvable evidence (a real ledger row)."""
    row = store.add_evidence(
        ("evidence for " + finding["finding_id"]).encode(),
        actor="hh-validator", action="capture")
    finding["evidence"][0]["ledger_ref"] = f"eng/evidence/ledger.jsonl#{row['seq']}"
    finding["evidence"][0]["artifact_sha256"] = row["artifact_sha256"]
    return finding

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
    f = seed_confirmed(store, json.loads((FIXTURES / "finding.json").read_text()))
    store.put_finding(f)
    assert store.get_finding(f["finding_id"])["status"] == "confirmed"
    with pytest.raises(FindingStoreError):
        store.delete_finding(f["finding_id"])


def test_duplicate_marking(store):
    store.put_finding(seed_confirmed(store, json.loads((FIXTURES / "finding.json").read_text())))
    f = seed_confirmed(store, json.loads((FIXTURES / "finding.json").read_text()))
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
    store.put_finding(seed_confirmed(store, json.loads((FIXTURES / "finding.json").read_text())))
    # A NEW store over the same tree sees it — persistence across
    # sessions and model changes.
    assert FindingStore(tmp_path / "eng").list_findings()


# --- M4: report generation ---------------------------------------------------

def test_report_from_confirmed_only(store):
    confirmed = seed_confirmed(store, json.loads((FIXTURES / "finding.json").read_text()))
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
    store.put_finding(seed_confirmed(store, json.loads((FIXTURES / "finding.json").read_text())))
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
    out, fired = sanitize_headers({"Authorization": "Bearer secret",
                                   "Cookie": "session=x",
                                   "Content-Type": "application/json",
                                   "X-Api-Key": "k"})
    assert out["Authorization"] == "[REDACTED]"
    assert out["Cookie"] == "[REDACTED]"
    assert out["X-Api-Key"] == "[REDACTED]"
    assert out["Content-Type"] == "application/json"
    assert sorted(fired) == ["header:authorization", "header:cookie", "header:x-api-key"]


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


# --- P0 hardening (2026-10-21 external review) --------------------------------

def test_confirmed_requires_independent_validation_schema():
    # Non-empty evidence, but no validation/reviewer_decision: the schema's
    # allOf conditional must reject it (this is what the reviewer showed
    # could slip through before).
    f = json.loads((FIXTURES / "finding.json").read_text())
    f.pop("validation"); f.pop("reviewer_decision")
    f["status"] = "confirmed"
    import jsonschema as js
    schema = json.loads((PACK_ROOT / "schemas" / "finding.schema.json").read_text())
    with pytest.raises(js.ValidationError):
        js.validate(f, schema)


def test_confirmed_with_nonindependent_validation_rejected():
    f = json.loads((FIXTURES / "finding.json").read_text())
    f["validation"]["independent"] = False   # shared the tester's session
    import jsonschema as js
    schema = json.loads((PACK_ROOT / "schemas" / "finding.schema.json").read_text())
    with pytest.raises(js.ValidationError):
        js.validate(f, schema)


def test_store_resolves_confirmed_evidence_refs(store):
    # A confirmed finding whose ledger_ref does NOT resolve is refused by
    # the store even though the schema passed.
    f = json.loads((FIXTURES / "finding.json").read_text())
    f["evidence"][0]["ledger_ref"] = "nowhere#9999"
    with pytest.raises((FindingStoreError,)):
        store.put_finding(f)


def test_store_accepts_confirmed_with_resolved_refs(store):
    row = store.add_evidence(b"GET /api/notes/1 -> 200 alice data",
                             actor="hh-validator", action="capture")
    f = json.loads((FIXTURES / "finding.json").read_text())
    f["evidence"][0]["ledger_ref"] = f"eng/evidence/ledger.jsonl#{row['seq']}"
    f["evidence"][0]["artifact_sha256"] = row["artifact_sha256"]
    store.put_finding(f)
    assert store.get_finding(f["finding_id"])["status"] == "confirmed"


def test_store_refuses_mismatched_artifact_hash(store):
    row = store.add_evidence(b"real evidence", actor="a", action="b")
    f = json.loads((FIXTURES / "finding.json").read_text())
    f["evidence"][0]["ledger_ref"] = f"x#{row['seq']}"
    f["evidence"][0]["artifact_sha256"] = "f" * 64  # wrong hash
    with pytest.raises(FindingStoreError):
        store.put_finding(f)


def test_store_fails_closed_without_jsonschema(store):
    # jsonschema is now a hard import; simulate absence by nulling it in
    # the module — create() must refuse, not degrade.
    import findings_store as fs
    real = fs.jsonschema
    fs.jsonschema = None
    try:
        with pytest.raises(Exception):
            fs.FindingStore.create(store.root.parent / "eng2",
                                   json.loads((FIXTURES / "engagement.json").read_text()))
    finally:
        fs.jsonschema = real


def test_authorization_window_enforced(tmp_path):
    eng = json.loads((FIXTURES / "engagement.json").read_text())
    eng["engagement_id"] = "expired-01"
    eng["window"] = {"start": "2020-01-01T00:00:00Z",
                     "expires": "2020-02-01T00:00:00Z"}
    st = FindingStore.create(tmp_path / "expired", eng)
    with pytest.raises(FindingStoreError, match="expired"):
        st.add_evidence(b"x", actor="a", action="b")


def test_authorization_status_enforced(tmp_path):
    eng = json.loads((FIXTURES / "engagement.json").read_text())
    eng["status"] = "paused"
    st = FindingStore.create(tmp_path / "paused", eng)
    with pytest.raises(FindingStoreError, match="paused"):
        st.put_finding(json.loads((FIXTURES / "finding.json").read_text()))


def test_checkpoint_detects_truncation(store):
    for i in range(3):
        store.add_evidence(f"evidence {i}".encode(), actor="a", action="b")
    cp = store.checkpoint(label="off-box copy")   # copy this dict off-box
    assert store.verify_against_checkpoint(cp["count"], cp["head"]) == []
    # Truncate the ledger locally (rewrite + recompute is possible with
    # filesystem access) — the EXTERNAL checkpoint still catches it.
    lines = store.ledger.read_text().splitlines()
    store.ledger.write_text("\n".join(lines[:2]) + "\n")
    assert store.verify_against_checkpoint(cp["count"], cp["head"]) != []
    # And the on-box checkpoint copy catches it too.
    assert any("checkpoint" in x for x in store.verify_chain())


def test_withdraw_preserves_audit_and_removes_content(store):
    store.put_finding(seed_confirmed(store, json.loads((FIXTURES / "finding.json").read_text())))
    tomb = store.withdraw_finding("dl-01-object-level-authz", actor="human",
                                  reason="client PII in the record")
    assert tomb["status"] == "withdrawn"
    assert "Original record sha256:" in tomb["description"]
    got = store.get_finding("dl-01-object-level-authz")
    assert got["title"] == "[WITHDRAWN]"
    assert got["description"].startswith("Withdrawn by human")
    with pytest.raises(FindingStoreError):
        store.withdraw_finding("dl-01-object-level-authz", actor="h", reason="again")


def test_purge_artifact_keeps_chain_verifiable(store):
    row = store.add_evidence(b"sensitive artifact bytes", actor="a", action="b")
    assert store.verify_chain() == []
    store.purge_artifact(row["artifact_sha256"], actor="human",
                         reason="retention policy")
    # Bytes gone, marker present, chain still verifies (recorded purge).
    assert not (store.artifacts / row["artifact_sha256"] / "artifact.bin").exists()
    assert (store.artifacts / row["artifact_sha256"] / "PURGED").exists()
    assert store.verify_chain() == []


def test_caido_body_redaction():
    from caido_adapter import SanitizationPolicy, normalize_exchange
    ex = {"id": "ex-2",
          "request": {"method": "POST", "host": "t.lab", "path": "/login",
                      "scheme": "https", "headers": {"Content-Type": "application/json"},
                      "body": '{"username": "a", "password": "SuperSecret123!", "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"}'},
          "response": {"status": 200, "headers": {}, "body": "ok sk-abcdefghijklmnopqrstuvwx"}}
    obs = normalize_exchange(ex)
    assert obs["sanitized"] is True
    assert "SuperSecret123!" not in obs["request"]["body"]
    assert "eyJhbGci" not in obs["request"]["body"]
    assert "sk-abcdefghijklmnopqrstuvwx" not in obs["response"]["body"]
    assert "credential" in obs["redactions"]
    assert "jwt" in obs["redactions"]
    assert "openai-key" in obs["redactions"]


def test_caido_policy_extension():
    from caido_adapter import SanitizationPolicy
    pol = SanitizationPolicy().extend("internal-id", r"INT-\d{6}", "[REDACTED-INT]")
    body, fired = pol.sanitize_body("customer INT-445566 called")
    assert body == "customer [REDACTED-INT] called"
    assert "internal-id" in fired
    import re
    with pytest.raises(Exception):
        SanitizationPolicy(rules=[("bad", "not-a-pattern", "x")])
