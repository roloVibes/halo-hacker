"""Halo Hacker's own test. Run it from the pack's folder:

    python -m tests.pack_test

It runs `halo_harness.ext.testing` -- the same checks `halo pack test .` makes, in a scratch home and project, never a
model call, never the network -- and then the pack's own checks in `own_checks` below. Add yours there: each is one
`report.add(file, what, ok, fix)`, and a failed one prints `<file>: <what> -- <fix>` like every other.
"""

import sys
from pathlib import Path

PACK = Path(__file__).resolve().parent.parent

try:
    from halo_harness.ext import testing
except ImportError:  # the harness is not importable on this interpreter
    testing = None

#: The `hh:` block every bio in this pack must carry (the security-role contract; tools/validate_pack.py).
HH_REQUIRED = ("responsibility", "boundaries", "inputs", "outputs", "evidence_requirements", "completion_criteria")


def _listed(kind: str) -> set:
    contributes = (testing.manifest(PACK).get("contributes") or {})
    return {Path(str(rel)).name for rel in contributes.get(kind) or []}


def _on_disk(folder: str) -> set:
    return {p.name for p in (PACK / folder).glob("*.yaml")}


def own_checks(report) -> None:
    """The pack's own checks, after the standard ones."""
    import yaml

    report.add("pack.yaml", "the pack's id is halo-hacker", testing.manifest(PACK).get("id") == "halo-hacker",
               "the id in pack.yaml is the pack's name everywhere: keep it as the folder's name")

    for kind, folder in (("agents", "agents"), ("teams", "teams")):
        listed, disk = _listed(kind), _on_disk(folder)
        report.add("pack.yaml", f"every {folder}/*.yaml is listed in contributes.{kind}", listed == disk,
                   f"contributes.{kind} and {folder}/ disagree: only listed {sorted(listed - disk)}, "
                   f"only on disk {sorted(disk - listed)}")

    missing = []
    for path in sorted((PACK / "agents").glob("*.yaml")):
        hh = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("hh") or {}
        missing += [f"{path.name}: hh.{key}" for key in HH_REQUIRED if key not in hh]
    report.add("agents/", "every bio declares the full hh: security-role contract", not missing,
               "; ".join(missing) or "each bio carries hh.responsibility, hh.boundaries, hh.inputs, hh.outputs, "
                                     "hh.evidence_requirements and hh.completion_criteria")

    models = [p.name for p in (PACK / "agents").glob("*.yaml")
              if ((yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("models") or {}).get("preference")
              not in (None, "default")]
    report.add("agents/", "no bio pins a model", not models,
               f"these bios name a model: {models} -- a pack stays model-agnostic (models.preference: default)")


def main() -> int:
    if testing is None:
        # Visible, never silent: `halo pack test .` is the same check with the
        # harness in place, and it is what CI runs.
        print("SKIPPED -- halo_harness is not importable on this interpreter "
              "(pip install git+https://github.com/roloVibes/Halo-Harness, or run `halo pack test .`)")
        return 0
    report = testing.run(PACK)
    own_checks(report)
    print(report.text())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
