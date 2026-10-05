"""The store: provenance ledger + gated upsert. THE NO-DELETE RULE LIVES HERE.

Layout under the user's vault:
  <vault>/ingest/ledger.jsonl        append-only, one JSON object per line
  <vault>/KB/<domain>/<slug>.md      distilled entries

Every ledger row: id, sha256 (of distilled content), source, source_sha256,
dest, trust_tier, first_seen, updated, confidence, replaces (prior row id or null).

There is no remove() function. That is the design. Removal is a human action
performed in the editor; the ledger records what the machine did, and the
machine never destroyed anything.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re


class UpsertRefused(Exception):
    """Raised when a write is ambiguous or unsafe. Refusal is the safe outcome."""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class Store:
    def __init__(self, vault: str):
        self.vault = os.path.abspath(vault)
        self.ledger_path = os.path.join(self.vault, "ingest", "ledger.jsonl")
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        self._rows = self._load()

    # ------------------------------------------------------------- reading

    def _load(self) -> list[dict]:
        rows = []
        if os.path.exists(self.ledger_path):
            with open(self.ledger_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        return rows

    def rows(self) -> list[dict]:
        return list(self._rows)

    def by_dest(self) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for r in self._rows:
            out.setdefault(r["dest"], []).append(r)
        return out

    # ------------------------------------------------------------- writing

    @staticmethod
    def _slug(text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return slug[:60] or "untitled"

    def upsert(self, *, dest_dir: str, title: str, content: str, source: dict,
               confidence: float) -> dict:
        """Append a distilled entry. Refuses (raises UpsertRefused) when:
        - dest escapes the vault            (containment)
        - content is empty/too thin         (a filtered response is not an entry)
        - an existing entry at the same dest is from a DIFFERENT source and the
          new one is not a superset                         (ambiguous overwrite)
        - the same source_sha256 already filed unchanged     (pure duplicate)
        """
        dest_dir = os.path.abspath(os.path.join(self.vault, dest_dir))
        if not dest_dir.startswith(self.vault + os.sep):
            raise UpsertRefused(f"dest escapes vault: {dest_dir}")

        content = (content or "").strip()
        if len(content) < 80:
            raise UpsertRefused(
                f"content too thin ({len(content)} chars) — refusing; "
                "a filtered or empty model response must never be filed"
            )
        if not 0.0 <= confidence <= 1.0:
            raise UpsertRefused(f"confidence out of range: {confidence}")

        dest = os.path.join(dest_dir, self._slug(title) + ".md")
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()

        prior = [r for r in self._rows if r["dest"] == dest]
        if prior:
            top = prior[-1]
            if top["sha256"] == sha:
                return {"status": "duplicate", "dest": dest, "row": top}
            if (top["source_sha256"] != source["sha256"]
                    and len(content) <= top.get("content_len", 0)):
                raise UpsertRefused(
                    f"ambiguous upsert at {dest}: different source, not longer — "
                    "human review required"
                )

        os.makedirs(dest_dir, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(self._render(title, content, source, confidence))

        row = {
            "id": f"{len(self._rows) + 1:06d}-{sha[:12]}",
            "sha256": sha,
            "content_len": len(content),
            "source": source["source_ref"],
            "source_type": source["source_type"],
            "source_sha256": source["sha256"],
            "dest": dest,
            "trust_tier": source["trust_tier"],
            "confidence": confidence,
            "first_seen": _now(),
            "updated": _now(),
            "replaces": prior[-1]["id"] if prior else None,
        }
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        self._rows.append(row)
        return {"status": "filed", "dest": dest, "row": row}

    # ------------------------------------------------------------- helpers

    @staticmethod
    def _render(title: str, content: str, source: dict, confidence: float) -> str:
        prov = (
            f"> [!provenance] source: `{source['source_ref']}` · type: {source['source_type']} "
            f"· tier: **{source['trust_tier']}** · fetched: {source['fetched_at'][:10]} "
            f"· confidence: {confidence:.2f}\n"
        )
        tier_note = (
            "\n> [!warning] Third-party lead — corroborate before relying on this in a report.\n"
            if source["trust_tier"] == "third-party" else ""
        )
        return f"# {title}\n\n{prov}{tier_note}\n{content}\n"
