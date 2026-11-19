"""The agentic-AI attack technique library (resources/payloads/agentic-ai.json).

The library is reference data the AI testing agents and the LLM playbooks point
at. These tests pin its structure (every technique complete, classes consistent,
ids unique), its provenance (SOURCES file present and naming it), and its wiring
(the agents and playbooks that should reference it actually do).
"""
import json
from pathlib import Path

_PACK = Path(__file__).resolve().parent.parent
_LIB = _PACK / "resources" / "payloads" / "agentic-ai.json"
_SOURCES = _PACK / "resources" / "SOURCES-agentic-ai.md"

_REQUIRED_TECHNIQUE_FIELDS = {"id", "class", "name", "summary", "payloads", "success_signal", "refs"}
# The classes the tool-boundaries playbook and tool-abuse agent lean on; if one
# disappears, that wiring silently degrades.
_AGENTIC_CLASSES = {"tool-boundary-escape", "approval-manipulation", "confirmation-reuse", "cross-agent-trust", "memory-poisoning"}


def _load():
    return json.loads(_LIB.read_text(encoding="utf-8"))


def test_library_loads_and_declares_schema():
    d = _load()
    assert d["schema_version"] == 1
    assert d["id"] == "agentic-ai-attack-library"
    assert d["classes"] and d["techniques"]


def test_every_technique_is_complete():
    d = _load()
    for t in d["techniques"]:
        missing = _REQUIRED_TECHNIQUE_FIELDS - set(t)
        assert not missing, f"{t.get('id', '?')}: missing fields {missing}"
        assert isinstance(t["payloads"], list) and t["payloads"], f"{t['id']}: no payloads"
        assert all(isinstance(p, str) and p.strip() for p in t["payloads"]), f"{t['id']}: empty payload string"
        assert t["refs"], f"{t['id']}: no methodology refs"


def test_classes_and_techniques_are_consistent():
    d = _load()
    class_ids = {c["id"] for c in d["classes"]}
    for c in d["classes"]:
        assert c.get("name") and c.get("summary"), f"class {c.get('id')}: needs name and summary"
    used = {t["class"] for t in d["techniques"]}
    assert used <= class_ids, f"techniques reference unknown classes: {used - class_ids}"
    empty = class_ids - used
    assert not empty, f"classes with no techniques: {empty}"
    assert _AGENTIC_CLASSES <= class_ids, f"agentic trust-plane classes missing: {_AGENTIC_CLASSES - class_ids}"


def test_technique_ids_unique_and_namespaced_by_class():
    d = _load()
    ids = [t["id"] for t in d["techniques"]]
    assert len(ids) == len(set(ids)), "duplicate technique ids"
    for t in d["techniques"]:
        assert t["id"].startswith(t["class"] + "."), f"{t['id']}: id must be namespaced by its class"


def test_provenance_file_present_and_names_the_library():
    assert _SOURCES.exists(), "resources/SOURCES-agentic-ai.md is missing"
    text = _SOURCES.read_text(encoding="utf-8")
    assert "agentic-ai.json" in text
    # The pack rule: original prose only, sources named.
    assert "Original" in text or "original prose" in text.lower()


def test_agents_and_playbooks_reference_the_library():
    refs = [
        _PACK / "agents" / "hh-prompt-injection.yaml",
        _PACK / "agents" / "hh-tool-abuse.yaml",
        _PACK / "playbooks" / "discovery.llm-prompt-injection.yaml",
        _PACK / "playbooks" / "discovery.llm-tool-boundaries.yaml",
    ]
    for f in refs:
        text = f.read_text(encoding="utf-8")
        assert "resources/payloads/agentic-ai.json" in text, f"{f.name}: does not reference the technique library"
