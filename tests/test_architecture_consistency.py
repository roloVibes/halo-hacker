"""Consistency tests for the 1.0.0 architecture: agent templates, workflows,
and builder hints must stay mutually consistent.

This is the "pairs with Halo seamlessly" gate: every workflow role names a
shipped bio, every builder-hints template/workflow resolves to something the
pack ships, and no template pins a model.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

_PACK = Path(__file__).resolve().parent.parent
if str(_PACK) not in sys.path:
    sys.path.insert(0, str(_PACK))


def _load_yaml(path):
    return yaml.safe_load((_PACK / path).read_text())


def _template_names():
    return {p.stem for p in (_PACK / "agents").glob("hh-*.yaml")}


def test_every_template_is_template_and_unpinned():
    names = _template_names()
    assert len(names) >= 40, names
    for p in sorted((_PACK / "agents").glob("hh-*.yaml")):
        doc = yaml.safe_load(p.read_text())
        hh = doc.get("hh", {})
        # Built-in agents (hh-orchestrator, hh-recon, etc.) predate templates
        # and lack the hh.is_template flag; templates must set it True.
        if hh.get("is_template") is True:
            assert doc.get("models", {}).get("preference") == "default", \
                f"{p.name}: template must not pin a model"
            assert hh.get("category"), f"{p.name}: template must declare a category"


def test_workflows_reference_shipped_bios():
    names = _template_names()
    for p in sorted((_PACK / "workflows").glob("*.yaml")):
        doc = yaml.safe_load(p.read_text())
        assert "stages" in doc, f"{p.name}: workflow needs stages"
        for stage in doc["stages"]:
            role = stage.get("role")
            assert role, f"{p.name}: stage {stage.get('id')} needs a role"
            assert role in names, f"{p.name}: role '{role}' is not a shipped bio"
            assert stage.get("id"), f"{p.name}: stage needs an id"


def test_builder_hints_resolve():
    doc = _load_yaml("builder-hints.yaml")
    names = _template_names()
    workflow_names = {p.stem for p in (_PACK / "workflows").glob("*.yaml")}

    for entry in doc.get("hints", []):
        tpl = entry.get("template")
        assert tpl, f"hint entry missing template: {entry}"
        assert tpl in names, f"hint template '{tpl}' is not a shipped bio"

    for entry in doc.get("workflows", []):
        wf = entry.get("workflow")
        assert wf, f"workflow hint missing workflow: {entry}"
        assert wf in workflow_names, f"hint workflow '{wf}' is not shipped"


def test_every_template_is_declared_in_pack_yaml():
    names = _template_names()
    manifest = _load_yaml("pack.yaml")
    declared = set()
    for path in manifest["contributes"]["agents"]:
        declared.add(Path(path).stem)
    assert names <= declared, f"templates not declared in pack.yaml: {names - declared}"
