"""mitre_view tests — ATLAS (shipped data) + ATT&CK (offline behavior).

No network: ATT&CK paths exercise the not-cached/offline answers.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import mitre_view  # noqa: E402


def test_atlas_loads():
    atlas = mitre_view.load_atlas()
    assert atlas["source"] == "MITRE ATLAS"
    assert len(atlas["techniques"]) > 200
    assert len(atlas["tactics"]) >= 14


def test_lookup_atlas_technique():
    out = mitre_view.lookup("AML.T0000")
    assert out["ok"] is True
    assert out["framework"] == "ATLAS"
    assert out["name"]


def test_lookup_rejects_non_ids():
    for bad in ("SQLI", "t1234", "AML.X0001", "../../etc/passwd"):
        out = mitre_view.lookup(bad)
        assert out["ok"] is False, bad


def test_lookup_attack_offline_is_graceful(tmp_path, monkeypatch):
    monkeypatch.setenv("HALO_HACKER_DATA_DIR", str(tmp_path))
    out = mitre_view.lookup("T1059")
    # offline + uncached → a clear error, never a raise
    assert out["ok"] is False
    assert "not cached" in out["error"]


def test_search_atlas():
    out = mitre_view.search("model", framework="atlas")
    assert out["ok"] is True and out["hits"]


def test_tactics_atlas():
    out = mitre_view.list_tactics("atlas")
    assert out["ok"] is True
    assert any("access" in name.lower() for name in out["tactics"].values())
