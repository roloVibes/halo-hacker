#!/usr/bin/env python3
"""Halo Hacker tool-result normalizers (Milestone 3).

External security tools are NOT re-implemented — their structured output
is normalized into candidate finding records (finding.schema.json shape,
status: candidate) that enter the standard validation -> judge -> report
pipeline. Every normalized record is a CANDIDATE; a scanner saying so is
never confirmation.

Supported inputs:
- Nuclei JSON output (one JSON object per line, -jsonl flag)
- Semgrep JSON output (--json)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SEV_MAP_NUCLEI = {"critical": "high", "high": "high", "medium": "medium",
                  "low": "low", "info": "info", "unknown": "info"}


def _slug(s: str) -> str:
    """finding_id fragments must match [a-z0-9-]."""
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-") or "unknown"


def _candidate(finding_id: str, engagement_id: str, title: str, category: str,
               description: str, evidence_ref: str, source: str,
               severity_rationale: str, repro_steps: list[str]) -> dict:
    import time as _t
    return {
        "finding_id": finding_id,
        "engagement_id": engagement_id,
        "title": title,
        "category": category,
        "description": f"{description} (source: {source} — scanner output is "
                       "a candidate, never confirmation)",
        "expected_behavior": "No exploitable condition at this location.",
        "observed_behavior": "Scanner reported a match; not yet validated.",
        "reproduction": {"steps": repro_steps},
        "evidence": [{"ledger_ref": evidence_ref}],
        "status": "candidate",
        "audit_history": [{
            "timestamp": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime()),
            "actor": "normalizer",
            "action": "candidate-created",
            "detail": f"{source}; {severity_rationale}",
        }],
    }


def normalize_nuclei(path: Path, engagement_id: str,
                     evidence_ref: str = "pending-ingest") -> list[dict]:
    """Nuclei -jsonl output -> candidate findings. One per matched template
    instance; deduped by (template-id, host, matched-at)."""
    seen: set[tuple] = set()
    out: list[dict] = []
    seq = 0
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        key = (r.get("template-id"), r.get("host"), r.get("matched-at"))
        if key in seen:
            continue
        seen.add(key)
        seq += 1
        sev = SEV_MAP_NUCLEI.get(str(r.get("info", {}).get("severity", "info")).lower(), "info")
        out.append(_candidate(
            finding_id=f"nu-{seq:02d}-{_slug((r.get('template-id') or 'unknown').split('-')[0])}",
            engagement_id=engagement_id,
            title=f"{r.get('info', {}).get('name', 'Nuclei match')} at {r.get('matched-at', r.get('host', '?'))}",
            category=f"nuclei:{r.get('template-id', 'unknown')}",
            description=str(r.get('info', {}).get('description', 'Nuclei template match')),
            evidence_ref=evidence_ref,
            source=f"Nuclei {r.get('template-id')} ({r.get('type', 'n/a')})",
            severity_rationale=f"Scanner severity {sev}; pending independent validation.",
            repro_steps=[
                f"Re-run nuclei with template {r.get('template-id')} against "
                f"{r.get('host')} and compare the matched location "
                f"{r.get('matched-at')} manually.",
            ],
        ))
    return out


def normalize_semgrep(path: Path, engagement_id: str,
                      evidence_ref: str = "pending-ingest") -> list[dict]:
    """Semgrep --json output -> candidate findings (code-level)."""
    data = json.loads(Path(path).read_text())
    out: list[dict] = []
    for seq, r in enumerate(data.get("results", []), 1):
        check_id = r.get("check_id", "unknown")
        path_str = r.get("path", "?")
        start = r.get("start", {})
        out.append(_candidate(
            finding_id=f"sg-{seq:02d}-{_slug(check_id.split('.')[-1])}",
            engagement_id=engagement_id,
            title=f"{check_id} in {path_str}:{start.get('line', '?')}",
            category=f"semgrep:{check_id}",
            description=(r.get("extra", {}).get("message")
                         or "Semgrep rule match"),
            evidence_ref=evidence_ref,
            source=f"Semgrep {check_id}",
            severity_rationale=(r.get("extra", {}).get("severity")
                                or "unknown scanner severity; pending validation."),
            repro_steps=[
                f"Review {path_str} line {start.get('line', '?')} and confirm "
                "the pattern is reachable with attacker-controlled input.",
            ],
        ))
    return out
