"""Tests for the ARTEX-derived additions (G1–G5, _research/ARTEX-REVIEW.md).

G1 asset + coverage ledger, G4 traffic snapshots, G2 quote verification,
G3 retest schema block, G5 chain-candidate persistence. All offline.
Each test PROVES its filter/dedupe fired (N-before -> M-after), per the
pack's own rule that a silently-matching-nothing filter is indistinguishable
from an empty corpus.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pytest

PACK_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACK_ROOT / "tools"))

import assets as assets_mod  # noqa: E402
from assets import AssetStore, AssetStoreError, derive_asset_id  # noqa: E402
from caido_adapter import normalize_exchange  # noqa: E402
from traffic_snapshot import SnapshotStore, SnapshotError  # noqa: E402
import quote_verify  # noqa: E402
import attack_path_graph  # noqa: E402

jsonschema = pytest.importorskip("jsonschema")
FIXTURES = PACK_ROOT / "examples" / "fixtures" / "valid"


# --- G1: asset identity, dedupe, containment -------------------------------

def test_asset_id_derived_per_type():
    assert derive_asset_id("root_domain", {"domain": "Example.COM"}) == "root_domain:example.com"
    assert derive_asset_id("endpoint", {"method": "get", "url": "HTTPS://a.com/x"}) == "endpoint:GET https://a.com/x"
    assert derive_asset_id("service", {"host": "A.com", "port": 443, "scheme": "https"}) == "service:a.com:443:https"


def test_asset_id_refuses_missing_key():
    with pytest.raises(AssetStoreError):
        derive_asset_id("root_domain", {})


def test_observation_dedupes_and_computes_parent(tmp_path):
    store = AssetStore(tmp_path / "eng")
    r1 = store.record_observation("subdomain", {"domain": "api.example.com"},
                                  engagement_id="e1", attributes={"status_code": 200})
    n_after_first = len(store.list_assets())
    r2 = store.record_observation("subdomain", {"domain": "API.example.com"},
                                  engagement_id="e1", attributes={"page_title": "t"})
    n_after_second = len(store.list_assets())
    # Prove the dedupe fired: two observations, one asset.
    assert n_after_first == 1 and n_after_second == 1
    assert r1["asset_id"] == r2["asset_id"] == "subdomain:api.example.com"
    # Containment computed by the program, never the agent.
    assert r2["parent_ref"] == "root_domain:example.com"
    # Attributes merged across observations.
    assert store.list_assets()[0]["attributes"]["page_title"] == "t"


def test_endpoint_parents_to_service(tmp_path):
    store = AssetStore(tmp_path / "eng")
    rec = store.record_observation(
        "endpoint", {"method": "GET", "url": "https://api.example.com:8443/v1/u"},
        engagement_id="e1")
    assert rec["parent_ref"] == "service:api.example.com:8443:https"


# --- G1: coverage ledger proves its gaps -----------------------------------

def test_coverage_negative_without_evidence_is_a_named_gap(tmp_path):
    store = AssetStore(tmp_path / "eng")
    store.record_coverage({"engagement_id": "e1", "surface": "/login",
                           "risk_area": "sqli", "outcome": "no_issue_found"})
    store.record_coverage({"engagement_id": "e1", "surface": "/u",
                           "risk_area": "idor", "outcome": "ruled_out"})
    ledger = store.build_ledger()
    # N entries -> M gaps, both gaps NAMED (evidence-less + reason-less).
    assert ledger["entry_count"] == 2
    assert ledger["gap_count"] == 2
    kinds = {g["kind"] for g in ledger["gaps"]}
    assert "no_issue_found_without_evidence" in kinds
    assert "ruled_out_without_reason" in kinds


def test_coverage_evidenced_negative_is_clean(tmp_path):
    store = AssetStore(tmp_path / "eng")
    store.record_coverage({"engagement_id": "e1", "surface": "/login",
                           "risk_area": "sqli", "outcome": "no_issue_found",
                           "evidence_ref": "eng/evidence/ledger.jsonl#3"})
    ledger = store.build_ledger()
    assert ledger["entry_count"] == 1 and ledger["gap_count"] == 0


# --- G4: traffic snapshots -------------------------------------------------

def _exchange(body_resp: str, encoding: str = None):
    resp_headers = {"Content-Type": "text/html"}
    if encoding:
        resp_headers["Content-Encoding"] = encoding
    return {
        "id": "x1",
        "request": {"method": "GET", "scheme": "https", "host": "api.example.com",
                    "path": "/u/1", "headers": {"Authorization": "Bearer x" * 40}, "body": ""},
        "response": {"status": 200, "headers": resp_headers, "body": body_resp},
    }


def test_snapshot_pins_hashes_and_redacts(tmp_path):
    ex = normalize_exchange(_exchange("hello body"))
    assert ex["sanitized"] is True  # redaction ran (Authorization header)
    store = SnapshotStore(tmp_path / "eng")
    snap = store.pin(ex)
    assert snap["snapshot_id"].startswith("snap-")
    assert store.verify_integrity(snap["snapshot_id"]) == []
    # The credential never reaches the pinned evidence (redaction fired).
    assert "Bearer" not in snap["req_head"]
    assert "Authorization" in snap["redactions"] or any("authorization" in r for r in snap["redactions"])


def test_snapshot_refuses_unsanitized(tmp_path):
    store = SnapshotStore(tmp_path / "eng")
    with pytest.raises(SnapshotError):
        store.pin({"sanitized": False, "request": {}, "response": {}})


def test_snapshot_tamper_detected(tmp_path):
    import base64
    store = SnapshotStore(tmp_path / "eng")
    snap = store.pin(normalize_exchange(_exchange("original")))
    p = store.dir / f"{snap['snapshot_id']}.json"
    data = json.loads(p.read_text())
    # Tamper with the stored body but leave the pinned hash — integrity fails.
    data["resp_body_b64"] = base64.b64encode(b"tampered").decode()
    p.write_text(json.dumps(data))
    assert store.verify_integrity(snap["snapshot_id"]) != []


# --- G2: quote verification -------------------------------------------------

def test_quotes_verified_verbatim(tmp_path):
    store = SnapshotStore(tmp_path / "eng")
    snap = store.pin(normalize_exchange(_exchange('{"id":1,"role":"admin"}')))
    rep = quote_verify.verify_quotes(tmp_path / "eng", snap["snapshot_id"],
                                     ['"role":"admin"', '"role":"superadmin"'])
    assert rep["quote_count"] == 2 and rep["verified_count"] == 1
    assert rep["all_verified"] is False


def test_quotes_gzip_decoded_before_check(tmp_path):
    body = '{"msg":"this compresses well, this compresses well"}'
    gz = gzip.compress(body.encode())
    # Emulate a captured gzip body: pin, then swap in the compressed bytes
    # base64-encoded (the store's real form), re-pinning the hash to match.
    store = SnapshotStore(tmp_path / "eng")
    snap = store.pin(normalize_exchange(_exchange("placeholder", encoding="gzip")))
    p = store.dir / f"{snap['snapshot_id']}.json"
    data = json.loads(p.read_text())
    import base64, hashlib
    data["resp_body_b64"] = base64.b64encode(gz).decode()
    data["resp_hash"] = hashlib.sha256(gz).hexdigest()
    p.write_text(json.dumps(data))
    # A quote present only in the DECODED body verifies (gzip decoded first).
    rep = quote_verify.verify_quotes(tmp_path / "eng", snap["snapshot_id"],
                                     ["this compresses well"])
    assert rep["content_encoding"] == "gzip"
    assert rep["verified_count"] == 1


def test_quotes_missing_snapshot_raises(tmp_path):
    with pytest.raises(SnapshotError):
        quote_verify.verify_quotes(tmp_path / "eng", "snap-nope", ["x"])


# --- G3: retest block validates against the finding schema -----------------

def test_retest_block_schema_roundtrip():
    schema = json.loads((PACK_ROOT / "schemas" / "finding.schema.json").read_text())
    base = json.loads((FIXTURES / "finding-candidate.json").read_text()) \
        if (FIXTURES / "finding-candidate.json").exists() else None
    # Build a minimal valid finding inline (schema requires these keys).
    finding = {
        "finding_id": "rt-01-retest",
        "engagement_id": "demo-lab-01",
        "title": "Retest schema roundtrip",
        "category": "owasp-wstg:authz",
        "status": "candidate",
        "description": "x",
        "evidence": [{"ledger_ref": "eng/evidence/ledger.jsonl#0"}],
        "audit_history": [],
        "retest": {
            "verdict": "reproduced",
            "evidence_refs": ["snap-abc123"],
            "counterargument": "reachability ok; preconditions met; ...",
            "tested_at": "2026-11-16T00:00:00Z",
            "tester_ref": "hh-validator",
        },
        "counterevidence": "tried x, did not work",
        "confidence_rationale": "holds because y",
        "asset_refs": ["endpoint:GET https://api.example.com/u"],
    }
    jsonschema.validate(finding, schema)  # must not raise
    # A bad verdict is refused by the schema.
    finding["retest"]["verdict"] = "maybe"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(finding, schema)


# --- G5: chain candidates persist, path stays a projection ------------------

def test_chain_candidates_persist_labels(tmp_path):
    findings = [
        {"finding_id": "a-01-x", "title": "A", "status": "confirmed",
         "grants": ["creds"], "requires": []},
        {"finding_id": "b-02-y", "title": "B", "status": "candidate",
         "grants": [], "requires": ["creds"]},
    ]
    graph = attack_path_graph.build(findings)
    # One edge a->b on 'creds'; b unconfirmed so NOT demonstrated.
    assert len(graph["edges"]) == 1
    assert graph["edges"][0]["demonstrated"] is False
    rec = attack_path_graph.persist_chain_candidates(graph, tmp_path / "eng")
    assert rec["count"] == 1 and rec["projected"] == 1 and rec["demonstrated"] == 0
    # Persisted, and the record insists the PATH is never stored.
    saved = json.loads((tmp_path / "eng" / "context" / "chain-candidates.json").read_text())
    assert saved["candidates"][0]["state"] == "projected"
    assert "projection" in saved["note"]
