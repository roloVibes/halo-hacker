"""Offline tests — no network, no model. classify_fn/distill_fn are fakes.

Each test maps to a guard named in PLAN.md.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from ingest import adapters, pipeline
from ingest.store import Store, UpsertRefused


def fake_classify(doc):
    return {"domain": "Web", "title": "SQLi via decoded path",
            "confidence": 0.9}


def fake_distill(doc):
    return ("Technique: header injection via percent-decoded path. "
            "Command: `curl -H 'X: y' --path-as-is https://t/%0d%0a`. "
            "## Gotchas\n- send_header does no CR/LF filtering.") * 2


def doc(text, ref="note.md", tier="first-party"):
    return {"source_type": "notes", "source_ref": ref, "content": text,
            "sha256": adapters.hashlib.sha256(text.encode()).hexdigest(),
            "fetched_at": "2026-10-04T00:00:00+00:00", "trust_tier": tier}


CYBER = "Enumerated the API; found stored XSS in the jwt handling; nmap sweep clean."
NOT_CYBER = "Grocery list: eggs, flour, milk. Also the paint samples for the hallway."
PERSONAL = "My password hint is our anniversary date. Anyway, the sqli payload was '."

# ------------------------------------------------------------------ privacy filter

def test_filter_proves_it_dropped():
    kept, dropped = pipeline.privacy_filter([doc(CYBER), doc(NOT_CYBER)])
    assert len(kept) == 1 and len(dropped) == 1
    assert dropped[0]["reason"] == "no-cyber-signal"


def test_personal_signal_excluded_even_when_cyber():
    kept, dropped = pipeline.privacy_filter([doc(PERSONAL)])
    assert kept == [] and dropped[0]["reason"] == "personal-signal"


def test_empty_filter_reports_not_silently_passes(tmp_path):
    # a corpus with nothing cyber must report n_dropped, not pretend success
    report = pipeline.run([doc(NOT_CYBER)], Store(str(tmp_path)),
                          fake_classify, fake_distill)
    assert report["n_in"] == 1 and report["n_kept"] == 0 and report["n_dropped"] == 1


# ------------------------------------------------------------------ store guards

def test_no_delete_function_exists():
    # THE no-delete rule: the store must not expose any removal API
    assert not hasattr(Store, "delete") and not hasattr(Store, "remove")


def test_thin_content_refused(tmp_path):
    store = Store(str(tmp_path))
    with pytest.raises(UpsertRefused):
        store.upsert(dest_dir="KB/Web", title="t", content="too short",
                     source=doc(CYBER), confidence=0.9)


def test_dest_escape_refused(tmp_path):
    store = Store(str(tmp_path))
    with pytest.raises(UpsertRefused):
        store.upsert(dest_dir="../outside", title="t", content=fake_distill(None),
                     source=doc(CYBER), confidence=0.9)


def test_pure_duplicate_detected(tmp_path):
    store = Store(str(tmp_path))
    d = doc(CYBER)
    r1 = store.upsert(dest_dir="KB/Web", title="SQLi via decoded path",
                      content=fake_distill(d), source=d, confidence=0.9)
    r2 = store.upsert(dest_dir="KB/Web", title="SQLi via decoded path",
                      content=fake_distill(d), source=d, confidence=0.9)
    assert r1["status"] == "filed" and r2["status"] == "duplicate"


def test_provenance_in_ledger_and_entry():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        store = Store(td)
        d = doc(CYBER, ref="/users/notes/sqli.md")
        r = store.upsert(dest_dir="KB/Web", title="SQLi via decoded path",
                         content=fake_distill(d), source=d, confidence=0.9)
        row = store.rows()[-1]
        assert row["source"] == "/users/notes/sqli.md"
        assert row["trust_tier"] == "first-party"
        assert row["replaces"] is None
        with open(r["dest"], encoding="utf-8") as f:
            body = f.read()
        assert "provenance" in body and "/users/notes/sqli.md" in body


def test_third_party_tier_gets_warning_note():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        store = Store(td)
        d = doc(CYBER, ref="https://example.com/post", tier="third-party")
        r = store.upsert(dest_dir="KB/Web", title="SQLi via decoded path",
                         content=fake_distill(d), source=d, confidence=0.9)
        with open(r["dest"], encoding="utf-8") as f:
            assert "corroborate" in f.read()
        assert store.rows()[-1]["trust_tier"] == "third-party"


def test_different_source_not_longer_refused():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        store = Store(td)
        c1 = fake_distill(None)
        store.upsert(dest_dir="KB/Web", title="SQLi via decoded path",
                     content=c1, source=doc(CYBER + " alpha", ref="a.md"), confidence=0.9)
        with pytest.raises(UpsertRefused):
            store.upsert(dest_dir="KB/Web", title="SQLi via decoded path",
                         content=c1[:-5], source=doc(CYBER + " beta", ref="b.md"),
                         confidence=0.9)


# ------------------------------------------------------------------ adapters

def test_vtt_cleanup_dedupes_rolling_lines():
    vtt = ("WEBVTT\nKind: captions\nLanguage: en\n\n"
           "00:00:01.000 --> 00:00:03.000\nhello everyone\n\n"
           "00:00:03.000 --> 00:00:05.000\nhello everyone today we\n\n"
           "00:00:05.000 --> 00:00:07.000\ntoday we cover sqli\n")
    out = adapters._vtt_to_text(vtt)
    # cumulative cue extends; window-reset cue overlaps on "today we" and merges
    assert out == "hello everyone today we cover sqli"


def test_scan_tree_skips_and_keeps(tmp_path):
    (tmp_path / "note.md").write_text(CYBER)
    (tmp_path / "list.txt").write_text(NOT_CYBER)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x")
    (tmp_path / "img.png").write_bytes(b"\x89PNG")
    docs, skipped = adapters.scan_tree(str(tmp_path))
    refs = {os.path.basename(d["source_ref"]) for d in docs}
    assert refs == {"note.md", "list.txt"}
    assert any("img.png" in p for p, _ in skipped)
    assert all(d["trust_tier"] == "first-party" for d in docs)


# ------------------------------------------------------------------ model client guards

def test_openrouter_filter_detected_not_returned():
    from ingest.model_client import OpenRouterClient, ModelError
    c = OpenRouterClient.__new__(OpenRouterClient)  # skip key check
    c.model = "test/model"; c.api_key = "k"; c.base_url = "http://x"
    import urllib.request
    orig = urllib.request.urlopen

    class FakeResp:
        def read(self):
            return json.dumps({"choices": [{"finish_reason": "content_filter",
                                            "message": {"content": None}}]}).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    urllib.request.urlopen = lambda *a, **k: FakeResp()
    try:
        with pytest.raises(ModelError, match="FILTERED"):
            c.chat("anything")
    finally:
        urllib.request.urlopen = orig


def test_ollama_empty_content_refused():
    from ingest.model_client import OllamaClient, ModelError
    c = OllamaClient(model="x")
    import urllib.request
    orig = urllib.request.urlopen

    class FakeResp:
        def read(self):
            return json.dumps({"message": {"content": ""},
                               "prompt_eval_count": 10}).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    urllib.request.urlopen = lambda *a, **k: FakeResp()
    try:
        with pytest.raises(ModelError):
            c.chat("anything")
    finally:
        urllib.request.urlopen = orig


# ------------------------------------------------------------------ pipeline end-to-end (offline)

def test_pipeline_report_shape(tmp_path):
    store = Store(str(tmp_path))
    report = pipeline.run([doc(CYBER, "a.md"), doc(NOT_CYBER, "b.md")],
                          store, fake_classify, fake_distill)
    assert report["n_in"] == 2 and report["n_kept"] == 1
    assert len(report["filed"]) == 1 and report["refused"] == []
    assert report["dropped"][0]["source"].endswith("b.md")
    assert os.path.exists(report["filed"][0]["dest"])


def test_pipeline_dry_run_writes_nothing(tmp_path):
    store = Store(str(tmp_path))
    report = pipeline.run([doc(CYBER)], store, fake_classify, fake_distill,
                          dry_run=True)
    assert store.rows() == [] and report["filed"][0]["would_file"]["domain"] == "Web"
