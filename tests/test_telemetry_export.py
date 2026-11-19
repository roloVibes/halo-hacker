"""Telemetry export (tools/telemetry_export.py).

The bundle is only worth anything if it is complete (every ledger row
exported), honest (chain problems reported, not hidden), and verifiable
(file hashes in the manifest match the bytes on disk). These tests pin all
three, plus the refusal path and the optional zip.
"""
import json
import zipfile
from pathlib import Path

import pytest

from tools import telemetry_export
from tools.findings_store import FindingStore

_VALID = Path(__file__).resolve().parent.parent / "examples" / "fixtures" / "valid"


def _engagement() -> dict:
    eng = json.loads((_VALID / "engagement.json").read_text())
    eng["engagement_id"] = "eng-telemetry-test"
    return eng


def _store_with_rows(tmp_path: Path) -> FindingStore:
    store = FindingStore.create(tmp_path / "engagement", _engagement())
    store.add_evidence(b"transcript of probe one", actor="hh-prompt-injection",
                       action="direct-injection-probe", finding_id="f-001",
                       meta={"payload_class": "direct-override"})
    store.add_evidence(b"transcript of probe two", actor="hh-prompt-injection",
                       action="direct-injection-probe-retry", finding_id="f-001")
    store.add_evidence(b"validator reproduction log", actor="hh-validator",
                       action="independent-reproduction", finding_id="f-001")
    return store


def _export(tmp_path: Path) -> tuple[Path, dict]:
    out = tmp_path / "bundle"
    manifest = telemetry_export.export_bundle(tmp_path / "engagement", out, "run-test")
    return out, manifest


def test_bundle_contains_all_five_files(tmp_path: Path):
    _store_with_rows(tmp_path)
    out, _ = _export(tmp_path)
    for name in ("manifest.json", "actions.jsonl", "sessions.jsonl", "summary.md", "capture-setup.md"):
        assert (out / name).exists(), f"missing {name}"


def test_every_ledger_row_is_exported_with_correlation_id(tmp_path: Path):
    store = _store_with_rows(tmp_path)
    out, manifest = _export(tmp_path)
    rows = store._read_rows()
    actions = [json.loads(l) for l in (out / "actions.jsonl").read_text().splitlines() if l.strip()]
    assert len(actions) == len(rows) == manifest["counts"]["actions"]
    for action, row in zip(actions, rows):
        assert action["hash"] == row["hash"]
        assert action["prev_hash"] == row["prev_hash"]
        assert action["correlation_id"] == f"run-test:{row['seq']:06d}"
        assert action["artifact_sha256"] == row["artifact_sha256"]
    ids = [a["correlation_id"] for a in actions]
    assert len(ids) == len(set(ids)), "correlation ids must be unique"


def test_sessions_group_contiguous_same_actor_runs(tmp_path: Path):
    _store_with_rows(tmp_path)
    out, manifest = _export(tmp_path)
    sessions = [json.loads(l) for l in (out / "sessions.jsonl").read_text().splitlines() if l.strip()]
    # probe, probe (same actor) then validator: two sessions
    assert len(sessions) == 2
    assert sessions[0]["actor"] == "hh-prompt-injection" and sessions[0]["actions"] == 2
    assert sessions[1]["actor"] == "hh-validator" and sessions[1]["actions"] == 1
    assert manifest["counts"]["sessions"] == 2


def test_manifest_file_hashes_match_disk(tmp_path: Path):
    _store_with_rows(tmp_path)
    out, manifest = _export(tmp_path)
    for name, digest in manifest["files"].items():
        assert telemetry_export._sha256((out / name).read_bytes()) == digest, f"{name} hash mismatch"
    assert manifest["ledger"]["head_hash"] == [json.loads(l) for l in (out / "actions.jsonl").read_text().splitlines()][-1]["hash"]


def test_intact_chain_is_reported_intact(tmp_path: Path):
    _store_with_rows(tmp_path)
    _, manifest = _export(tmp_path)
    assert manifest["ledger"]["chain_intact"] is True
    assert manifest["ledger"]["chain_problems"] == []


def test_tampered_chain_is_reported_not_hidden(tmp_path: Path):
    store = _store_with_rows(tmp_path)
    # Rewrite row 0's actor in place — the classic silent-edit attempt.
    lines = store.ledger.read_text().splitlines()
    row0 = json.loads(lines[0])
    row0["actor"] = "mallory"
    lines[0] = json.dumps(row0)
    store.ledger.write_text("\n".join(lines) + "\n")
    _, manifest = _export(tmp_path)
    assert manifest["ledger"]["chain_intact"] is False
    assert manifest["ledger"]["chain_problems"], "tamper must produce named problems"


def test_capture_setup_documents_the_verification_recipe(tmp_path: Path):
    _store_with_rows(tmp_path)
    out, _ = _export(tmp_path)
    text = (out / "capture-setup.md").read_text()
    # A third party must be able to recompute the chain from this file alone.
    assert "sort_keys=True" in text and "prev_hash" in text and "artifact_sha256" in text.lower() or "artifact" in text


def test_cli_refuses_a_non_engagement(tmp_path: Path, capsys):
    rc = telemetry_export.main([str(tmp_path / "nope")])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False


def test_cli_zip_writes_all_members(tmp_path: Path, capsys):
    _store_with_rows(tmp_path)
    rc = telemetry_export.main([str(tmp_path / "engagement"), "--out", str(tmp_path / "b"), "--zip"])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    zf = zipfile.ZipFile(result["zip"])
    assert sorted(zf.namelist()) == ["actions.jsonl", "capture-setup.md", "manifest.json", "sessions.jsonl", "summary.md"]
    assert result["chain_intact"] is True
