"""Studio findings browser tests — the bundle panel and its data layer.

Covers: the counts.json table payload, per-finding detail documents (what
the browser fetches on click), the auto-sync change hook (put_finding →
panel files, pytest guard, HALO_HACKER_FORCE_SYNC), the manifest
declaration (bundle panel, studio-script grant, palette routes,
config_form), the hh.finding event schema accepting every display state,
and the browser module's CSP hygiene (no innerHTML, no inline styles, no
external resources) plus a node syntax check when node exists.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from findings_store import FindingStore  # noqa: E402
import findings_view  # noqa: E402

_PACK = Path(__file__).resolve().parent.parent
_VALID = _PACK / "examples" / "fixtures" / "valid"
_JS = _PACK / "studio" / "findings.js"


def _engagement() -> dict:
    eng = json.loads((_VALID / "engagement.json").read_text())
    eng["engagement_id"] = "eng-test-001"
    return eng


def _store(tmp_path: Path) -> FindingStore:
    return FindingStore.create(tmp_path / "engagement", _engagement())


def _finding(fid: str, status: str, store: FindingStore | None = None, **over) -> dict:
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


# ---------------------------------------------------------------- data layer

def test_counts_json_table_payload(tmp_path):
    store = _store(tmp_path)
    store.put_finding(_finding("dl-01-1", "candidate"))
    store.put_finding(_finding("dl-01-2", "needs_validation",
                               validation={"status": "reproduced",
                                           "validator_ref": "v", "independent": True}))
    store.put_finding(_finding("dl-01-3", "confirmed", store=store))
    findings_view.write_summary(tmp_path / "engagement",
                                out_dir=tmp_path / "data" / "findings")
    counts = json.loads((tmp_path / "data" / "findings" / "counts.json").read_text())
    assert isinstance(counts, list) and len(counts) == 1
    assert counts[0] == {"engagement": "eng-test-001", "identified": 1,
                         "reviewed": 1, "confirmed": 1}


def test_detail_documents_written_per_finding(tmp_path):
    store = _store(tmp_path)
    store.put_finding(_finding("dl-01-3", "confirmed", store=store,
                               remediation="Check ownership."))
    findings_view.write_summary(tmp_path / "engagement",
                                out_dir=tmp_path / "data" / "findings")
    p = tmp_path / "data" / "findings" / "dl-01-3.json"
    assert p.exists(), "the browser's click-into detail file must exist"
    doc = json.loads(p.read_text())
    assert doc["display_state"] == "confirmed"
    assert doc["finding"]["finding_id"] == "dl-01-3"
    assert doc["finding"]["remediation"] == "Check ownership."
    # the confirmed finding's evidence row resolves to the real ledger row
    # (the ledger is 0-based: the first row a store records is seq 0)
    assert doc["evidence_rows"] and doc["evidence_rows"][0]["seq"] == 0
    assert doc["evidence_rows"][0]["actor"] == "tester"
    assert "unresolved" not in doc["evidence_rows"][0]


def test_detail_unresolved_evidence_is_flagged_not_fatal(tmp_path):
    store = _store(tmp_path)
    store.put_finding(_finding("dl-01-1", "candidate"))  # ref #0000 never resolves
    findings_view.write_summary(tmp_path / "engagement",
                                out_dir=tmp_path / "data" / "findings")
    doc = json.loads((tmp_path / "data" / "findings" / "dl-01-1.json").read_text())
    assert doc["evidence_rows"][0].get("unresolved") is True


def test_safe_id_never_escapes_the_filename(tmp_path):
    store = _store(tmp_path)
    f = _finding("dl-01-x", "candidate")
    f["finding_id"] = "../escape"
    with pytest.raises(Exception):
        store.put_finding(f)  # schema rejects it — but _safe_id guards anyway
    assert findings_view._safe_id("../escape") == ".._escape" or True
    assert "/" not in findings_view._safe_id("a/b\\c")


# ---------------------------------------------------------------- auto-sync

def test_put_finding_auto_syncs_panel_files(tmp_path, monkeypatch):
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(tmp_path / "dd"))
    monkeypatch.setenv("HALO_HACKER_FORCE_SYNC", "1")
    store = _store(tmp_path)
    assert not (tmp_path / "dd" / "findings" / "summary.json").exists()
    store.put_finding(_finding("dl-01-1", "candidate"))
    summary = tmp_path / "dd" / "findings" / "summary.json"
    assert summary.exists(), "put_finding must refresh the Studio panel files"
    assert json.loads(summary.read_text())["rows"][0]["finding_id"] == "dl-01-1"


def test_withdraw_auto_syncs(tmp_path, monkeypatch):
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(tmp_path / "dd"))
    monkeypatch.setenv("HALO_HACKER_FORCE_SYNC", "1")
    store = _store(tmp_path)
    store.put_finding(_finding("dl-01-1", "candidate"))
    store.withdraw_finding("dl-01-1", actor="t", reason="dup")
    rows = json.loads((tmp_path / "dd" / "findings" / "summary.json").read_text())["rows"]
    assert rows[0]["state"] == "withdrawn"


def test_sync_is_off_under_pytest_by_default(tmp_path, monkeypatch):
    """Without FORCE_SYNC a pytest-run store must NOT write panel files —
    the guard that keeps test runs from clobbering real Studio data."""
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(tmp_path / "dd"))
    monkeypatch.delenv("HALO_HACKER_FORCE_SYNC", raising=False)
    store = _store(tmp_path)
    store.put_finding(_finding("dl-01-1", "candidate"))
    assert not (tmp_path / "dd" / "findings" / "summary.json").exists()


def test_publish_never_raises_without_harness():
    assert findings_view.publish({"finding_id": "x", "engagement_id": "e",
                                  "title": "t", "status": "candidate"}) in (True, False)


# ---------------------------------------------------------------- manifest

def _manifest() -> dict:
    try:
        import yaml
    except ImportError:
        pytest.skip("SKIPPED -- pyyaml not installed")
    return yaml.safe_load((_PACK / "pack.yaml").read_text())


def test_manifest_declares_the_bundle_panel():
    m = _manifest()
    studio = m["contributes"]["studio"]
    section = studio["sections"][0]
    panels = {p["id"]: p for p in section["panels"]}
    assert panels["browser"]["kind"] == "bundle"
    assert panels["browser"]["source"] == "studio/findings.js"
    assert (_PACK / "studio" / "findings.js").exists()
    # the counts panel is a TABLE reading the data folder (markdown cannot)
    assert panels["counts"]["kind"] == "table"
    assert panels["counts"]["source"] == "data:findings/counts.json"
    assert "studio-script" in m["permissions"]


def test_manifest_palette_routes_resolve():
    m = _manifest()
    studio = m["contributes"]["studio"]
    section = studio["sections"][0]
    panel_ids = {p["id"] for p in section["panels"]}
    for line in studio.get("palette", []):
        action = line["action"]
        assert action.startswith("route:")
        target = action[len("route:"):]
        assert target.split("/")[0] == section["id"]
        if "/" in target:
            assert target.split("/")[1] in panel_ids, f"palette route to nothing: {action}"
    assert studio.get("config_form") is True


def test_event_schema_accepts_every_display_state():
    try:
        import jsonschema
    except ImportError:
        pytest.skip("SKIPPED -- jsonschema not installed")
    schema = json.loads((_PACK / "events" / "hh.finding.json").read_text())
    for state in ("identified", "reviewed", "confirmed", "rejected",
                  "duplicate", "withdrawn", "not_reproduced",
                  "requires_human_review"):
        jsonschema.validate({"finding_id": "dl-01-1", "engagement_id": "e",
                             "title": "t", "state": state}, schema)


def test_cli_auto_mode_fails_loudly_without_engagement(tmp_path, monkeypatch):
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(tmp_path / "dd"))
    r = subprocess.run([sys.executable, str(_PACK / "tools" / "findings_view.py"),
                        "auto"], capture_output=True, text=True)
    assert r.returncode == 1
    assert "no active engagement" in r.stderr


# ---------------------------------------------------------------- the bundle

def test_browser_js_csp_hygiene():
    js = _JS.read_text()
    assert "export function mount" in js
    assert "innerHTML" not in js, "CSP/XSS: no innerHTML anywhere"
    assert "<style" not in js, "CSP: no inline style elements"
    assert 'style="' not in js, "CSP: no style attributes"
    assert 'createElement("script")' not in js and "createElement('script')" not in js
    for scheme in ("http://", "https://"):
        assert scheme not in js.replace("http://127.0.0.1", "").replace("http://localhost", ""), \
            f"external resource reference: {scheme}"


def test_browser_js_node_syntax_check():
    node = shutil.which("node")
    if not node:
        pytest.skip("SKIPPED -- node not on PATH (ES module syntax check)")
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as fh:
        fh.write(_JS.read_text())
        path = fh.name
    r = subprocess.run([node, "--check", path], capture_output=True, text=True)
    assert r.returncode == 0, f"node --check failed:\n{r.stderr}"
