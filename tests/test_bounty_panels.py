"""Studio bug-bounty panels (bounty.js, bounty-programs.js) — CSP hygiene and syntax.

The bounty panels render HackerOne data files from the pack data dir. They are
bundle modules (sync mount, cleanup function) subject to the Studio CSP: no
inline styles, no <style> elements, no style= attributes, no innerHTML with
markup, no external *resources*. External navigation links (target=_blank to
hackerone.com) are allowed — they are anchors, not fetched resources.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_PACK = Path(__file__).resolve().parent.parent
# The bounty programs view is merged into bounty.js as a tab (tab-overflow fix);
# only the single tabbed bundle ships.
_PANELS = [_PACK / "studio" / "bounty.js"]


def test_panels_exist():
    for p in _PANELS:
        assert p.exists(), f"missing panel {p.name}"


def test_panels_export_sync_mount():
    for p in _PANELS:
        js = p.read_text(encoding="utf-8")
        assert "export function mount" in js, f"{p.name}: must export mount"
        # mount must NOT be async (the Studio contract: return value is cleanup)
        assert "export async function mount" not in js, f"{p.name}: async mount breaks the contract"


def test_panels_csp_hygiene():
    for p in _PANELS:
        js = p.read_text(encoding="utf-8")
        assert "innerHTML" not in js, f"{p.name}: no innerHTML"
        assert "<style" not in js, f"{p.name}: no <style> elements"
        assert 'style="' not in js, f"{p.name}: no style= attributes"
        assert 'createElement("script")' not in js and "createElement('script')" not in js
        # No external *resources* (src=, fetch/import to a remote). Anchors to
        # hackerone.com (target=_blank navigation) are fine.
        assert re.search(r'\bsrc\s*=\s*["\']https?://', js) is None, f"{p.name}: external src="
        assert re.search(r'fetch\(\s*["\']https?://', js) is None, f"{p.name}: fetch to external URL"
        assert re.search(r'import\(?\s*["\']https?://', js) is None, f"{p.name}: import of external URL"


def test_panels_use_pack_data_route():
    """Panels must read pack data via api/pack/<id>/data/ (singular), not /api/packs/."""
    for p in _PANELS:
        js = p.read_text(encoding="utf-8")
        assert "/api/pack/halo-hacker/data/" in js, f"{p.name}: wrong data route (must be singular 'pack')"
        assert "/api/packs/" not in js, f"{p.name}: /api/packs/ is not a real route"


def test_panels_node_syntax_check():
    node = shutil.which("node")
    if not node:
        pytest.skip("SKIPPED -- node not on PATH (ES module syntax check)")
    import tempfile
    for p in _PANELS:
        with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as fh:
            fh.write(p.read_text(encoding="utf-8"))
            path = fh.name
        r = subprocess.run([node, "--check", path], capture_output=True, text=True)
        assert r.returncode == 0, f"node --check failed for {p.name}:\n{r.stderr}"
