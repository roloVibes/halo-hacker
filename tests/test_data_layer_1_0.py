"""Tests for the 1.0.0 data-layer tools: project manager, ingest view,
attack-path graph, and live view.

Every test is hermetic: they point HALO_HACKER_DATA_DIR (and the vault)
at a tmp dir and never touch the real pack data folder or the harness.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_PACK = Path(__file__).resolve().parent.parent
if str(_PACK) not in sys.path:
    sys.path.insert(0, str(_PACK))
if str(_PACK / "tools") not in sys.path:
    sys.path.insert(0, str(_PACK / "tools"))


def _tmp(monkeypatch, tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(data))
    monkeypatch.setenv("HALO_HACKER_VAULT", str(tmp_path / "vault"))
    return data


# --- project_manager -------------------------------------------------------

def test_project_create_list_get_archive_delete(tmp_path, monkeypatch):
    _tmp(monkeypatch, tmp_path)
    import project_manager as pm

    r = pm.create_project("ukg", "UKG Program", "hackerone", "eng-1")
    assert r["ok"] is True
    assert r["project"]["program_name"] == "UKG Program"
    assert r["project"]["state"] == "active"

    r2 = pm.create_project("do", "DO Disclosure", "bugcrowd")
    assert r2["ok"] is True

    projects = pm.list_projects()
    assert len(projects) == 2
    assert {p["program_id"] for p in projects} == {"ukg", "do"}

    assert pm.get_project("ukg")["platform"] == "hackerone"
    assert pm.get_project("nope") is None

    assert pm.archive_project("ukg")["project"]["state"] == "archived"
    assert pm.delete_project("ukg")["ok"] is True
    assert len(pm.list_projects()) == 1


def test_project_create_rejects_duplicate_and_bad_platform(tmp_path, monkeypatch):
    _tmp(monkeypatch, tmp_path)
    import project_manager as pm

    pm.create_project("ukg", "UKG", "hackerone")
    dup = pm.create_project("ukg", "UKG Again", "custom")
    assert dup["ok"] is False
    assert "already exists" in dup["error"]

    bad = pm.create_project("x", "X", "not-a-platform")
    assert bad["ok"] is False
    assert "Invalid platform" in bad["error"]


# --- ingest_view -----------------------------------------------------------

def test_ingest_view_summary(tmp_path, monkeypatch):
    data = _tmp(monkeypatch, tmp_path)
    import ingest_view as iv

    # Write a fake ledger
    vault = tmp_path / "vault"
    ledger_dir = vault / "ingest"
    ledger_dir.mkdir(parents=True)
    rows = [
        {"id": "a", "source_type": "pdf", "source_ref": "doc.pdf", "topic": "jwt", "trust_tier": "first-party"},
        {"id": "b", "source_type": "notes", "source_ref": "n.md", "topic": "subdomain-enum", "trust_tier": "first-party"},
        {"id": "c", "source_type": "github", "source_ref": "g.py", "topic": "graphql", "trust_tier": "third-party"},
        {"id": "d", "source_type": "youtube", "source_ref": "v.mp4", "topic": "prompt-injection", "trust_tier": "third-party"},
    ]
    with open(ledger_dir / "ledger.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    summary = iv.collect(vault)
    assert summary["total_items"] == 4
    assert summary["ledger_exists"] is True
    assert summary["source_types"]["pdf"] == 1
    assert summary["source_types"]["notes"] == 1
    assert summary["trust_tiers"]["first-party"] == 2
    # routing: jwt -> api, subdomain-enum -> recon, graphql -> api, prompt-injection -> ai
    assert summary["routing"]["api"] == 2
    assert summary["routing"]["recon"] == 1
    assert summary["routing"]["ai"] == 1


def test_ingest_view_empty(tmp_path, monkeypatch):
    _tmp(monkeypatch, tmp_path)
    import ingest_view as iv
    summary = iv.collect(tmp_path / "vault")
    assert summary["total_items"] == 0
    assert summary["ledger_exists"] is False


# --- attack_path_graph -----------------------------------------------------

def test_attack_path_graph_projection():
    import attack_path_graph as apg
    findings = [
        {"finding_id": "f1", "title": "SQLi", "severity": "high", "status": "confirmed",
         "requires": ["session"], "grants": ["db-access"], "technique_ids": ["T1190"]},
        {"finding_id": "f2", "title": "Weak session", "severity": "medium", "status": "confirmed",
         "requires": [], "grants": ["session"], "technique_ids": ["T1539"]},
        {"finding_id": "f3", "title": "SSRF", "severity": "high", "status": "candidate",
         "requires": ["db-access"], "grants": ["internal-access"], "technique_ids": ["T1071"]},
    ]
    g = apg.build(findings)
    assert len(g["nodes"]) == 3
    # f1 requires "session", which f2 grants -> edge f2 -> f1
    # f3 requires "db-access", which f1 grants -> edge f1 -> f3
    edge_tokens = {(e["from"], e["to"]) for e in g["edges"]}
    assert ("f2", "f1") in edge_tokens
    assert ("f1", "f3") in edge_tokens
    # f2->f1 both confirmed -> demonstrated; f1->f3 has a candidate end -> projected
    by_edge = {(e["from"], e["to"]): e for e in g["edges"]}
    assert by_edge[("f2", "f1")]["demonstrated"] is True
    assert by_edge[("f1", "f3")]["demonstrated"] is False
    assert len(g["techniques"]) == 3


def test_attack_path_graph_empty():
    import attack_path_graph as apg
    g = apg.build([])
    assert g["nodes"] == [] and g["edges"] == [] and g["techniques"] == []


# --- live_view -------------------------------------------------------------

def test_live_view_empty_snapshot(tmp_path, monkeypatch):
    data = _tmp(monkeypatch, tmp_path)
    import live_view as lv
    snap = lv.collect()
    assert snap["harness"] is False
    assert snap["sessions"] == []
    assert "generated" in snap


def test_live_view_writes_file(tmp_path, monkeypatch):
    data = _tmp(monkeypatch, tmp_path)
    import live_view as lv
    assert lv.main() == 0
    assert (data / "live.json").is_file()
    doc = json.loads((data / "live.json").read_text())
    assert "sessions" in doc and "lines" in doc
