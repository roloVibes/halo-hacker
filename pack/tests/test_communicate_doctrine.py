"""Compliance tests for the communicate-findings doctrine.

The skill at pack/skills/communicate-findings/SKILL.md mandates hard rules
for leadership emails and full reports. This suite asserts that the renderers
actually enforce those rules in their outputs.
"""
import json
import re
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reporting"))

from findings_store import FindingStore  # noqa: E402
import leadership_email  # noqa: E402
import full_report  # noqa: E402

_VALID = Path(__file__).resolve().parent.parent / "examples" / "fixtures" / "valid"

BANNED_FUD = ("catastrophic", "nightmare", "doomed", "hackers are coming", "under constant attack")
DECISION_WORDS = frozenset(
    (
        "decide", "schedule", "approve", "patch", "review", "assign", "need",
        "require", "choose", "act", "fix", "remediate", "prioritize",
    )
)
BULLET_STARTER_BLACKLIST = frozenset(
    ("the", "a", "an", "this", "it", "there", "that", "these", "those", "one", "some", "no", "in")
)
LABEL_RE = re.compile(r"^(Assessment update|Status update|Weekly update|Report|Update)\b", re.IGNORECASE)
PASSIVE_RE = re.compile(r"\bit\s+was\s+\w+ed\b|\bit\s+has\s+been\s+\w+ed\b|\bwas\s+independently\s+\w+ed\b", re.IGNORECASE)


def _engagement() -> dict:
    eng = json.loads((_VALID / "engagement.json").read_text())
    eng["engagement_id"] = "eng-test-001"
    return eng


def _store(tmp_path: Path) -> FindingStore:
    return FindingStore.create(tmp_path / "engagement", _engagement())


def _finding(fid: str, status: str, store: FindingStore | None = None, **over) -> dict:
    f = json.loads((_VALID / "finding.json").read_text())
    f["finding_id"] = fid
    f["engagement_id"] = "eng-test-001"
    f["status"] = status
    f["audit_history"] = [
        {"timestamp": "2026-10-29T00:00:00Z", "actor": "t", "action": "created"}
    ]
    if status == "confirmed" and store is not None:
        row = store.add_evidence(
            b"proof-" + fid.encode(), actor="tester", action="captured", finding_id=fid
        )
        f["evidence"] = [
            {
                "ledger_ref": f"evidence/ledger.jsonl#{row['seq']:04d}",
                "artifact_sha256": row["artifact_sha256"],
                "kind": "request-response",
                "sanitized": True,
            }
        ]
    else:
        f["evidence"] = [
            {
                "ledger_ref": "evidence/ledger.jsonl#0000",
                "artifact_sha256": "0" * 64,
                "kind": "request-response",
                "sanitized": True,
            }
        ]
        f.pop("reviewer_decision", None)
        f.pop("validation", None)
    f.update(over)
    return f


def _bullet_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip().startswith("- ")]


def _assert_no_fud(text: str) -> None:
    lowered = text.lower()
    for phrase in BANNED_FUD:
        assert phrase not in lowered, f"banned FUD phrase found: {phrase!r}"


def _assert_verb_first_bullets(text: str) -> None:
    for line in _bullet_lines(text):
        content = line.lstrip("- ").strip()
        match = re.match(r"^([A-Za-z]+)", content)
        assert match, f"bullet does not start with a word: {line!r}"
        first = match.group(1).lower()
        assert first not in BULLET_STARTER_BLACKLIST, (
            f"bullet appears to start with a non-verb: {line!r}"
        )


def _assert_named_actor(text: str) -> None:
    assert not PASSIVE_RE.search(text), (
        f"actor-hiding passive voice found: {text!r}"
    )


def test_leadership_email_follows_doctrine(tmp_path):
    store = _store(tmp_path)
    f1 = _finding(
        "xx-01-authz",
        "confirmed",
        store=store,
        severity="high",
        target_ref="api.example.com",
        impact="Cross-user data exposure with a single request.",
    )
    f2 = _finding(
        "xx-02-inject",
        "confirmed",
        store=store,
        severity="medium",
        target_ref="api.example.com",
        title="SQL injection in /api/search",
        impact="Database read access via the search endpoint.",
    )
    store.put_finding(f1)
    store.put_finding(f2)

    email = leadership_email.render_leadership_email([f1, f2], store.engagement())
    assert set(email) == {"subject", "body", "mailto_url"}

    subject = email["subject"]
    body = email["body"]

    # Subject is a takeaway, not a status label.
    assert not LABEL_RE.search(subject), f"subject looks like a label: {subject!r}"
    has_number = bool(re.search(r"\d", subject))
    has_decision = any(word in subject.lower() for word in DECISION_WORDS)
    assert has_number or has_decision, f"subject lacks a number or decision word: {subject!r}"

    # Body has exactly the four load-bearing blocks (subject is the fifth part).
    blocks = body.strip().split("\n\n")
    assert len(blocks) == 4, f"expected 4 body blocks, got {len(blocks)}"
    opening, impact_block, ask_block, pointer = blocks

    # Opening states who found what and what is being asked.
    assert "confirmed" in opening.lower()
    assert "api.example.com" in opening
    assert opening.endswith(".")

    # Impact block is verb-first bullets, one per finding.
    impact_bullets = _bullet_lines(impact_block)
    assert len(impact_bullets) == 2
    for b in impact_bullets:
        assert b.lstrip("- ").lower().startswith("expose "), f"impact bullet not verb-first: {b!r}"

    # Ask block is verb-first bullets with bounded recommendations.
    ask_bullets = _bullet_lines(ask_block)
    assert len(ask_bullets) >= 1
    for b in ask_bullets:
        first = re.match(r"^([A-Za-z]+)", b.lstrip("- ").strip()).group(1).lower()
        assert first in DECISION_WORDS, f"ask bullet lacks decision verb: {b!r}"

    # Pointer offers the full report and a walkthrough.
    assert "report" in pointer.lower()
    assert "walk" in pointer.lower() or "walkthrough" in pointer.lower()

    _assert_no_fud(subject)
    _assert_no_fud(body)
    _assert_verb_first_bullets(body)
    _assert_named_actor(body)

    # Readable in under a minute: body under ~180 words.
    word_count = len(body.split())
    assert word_count <= 180, f"leadership email body is {word_count} words"

    # mailto URL round-trips.
    query = email["mailto_url"].split("?", 1)[1]
    params = urllib.parse.parse_qs(query)
    assert urllib.parse.unquote(params["subject"][0]) == subject
    assert urllib.parse.unquote(params["body"][0]) == body


def test_leadership_email_rejects_fud_language(tmp_path):
    store = _store(tmp_path)
    f = _finding(
        "xx-03-fud",
        "confirmed",
        store=store,
        severity="high",
        target_ref="api.example.com",
        impact="A catastrophic data breach is possible.",
    )
    store.put_finding(f)
    with pytest.raises(ValueError, match=r"FUD"):
        leadership_email.render_leadership_email([f], store.engagement())


def test_leadership_email_rejects_candidate():
    f = _finding("xx-01-candidate", "candidate")
    with pytest.raises(ValueError, match=r"xx-01-candidate"):
        leadership_email.render_leadership_email([f], _engagement())


def test_leadership_email_rejects_empty():
    with pytest.raises(ValueError, match=r"no confirmed findings"):
        leadership_email.render_leadership_email([], _engagement())


def test_full_report_follows_doctrine(tmp_path):
    store = _store(tmp_path)
    f1 = _finding(
        "xx-01-authz",
        "confirmed",
        store=store,
        severity="high",
        target_ref="api.example.com",
        impact="Cross-user data exposure with a single request.",
        remediation="Enforce object-level authorization checks on every note request.",
    )
    f2 = _finding(
        "xx-02-inject",
        "confirmed",
        store=store,
        severity="medium",
        target_ref="api.example.com",
        title="SQL injection in /api/search",
        impact="Database read access via the search endpoint.",
        remediation="Parameterize the search query and disable stacked queries.",
    )
    store.put_finding(f1)
    store.put_finding(f2)

    report = full_report.render_full_report([f1, f2], store.engagement())
    assert set(report) == {"title", "markdown"}
    md = report["markdown"]

    # Title states the strongest finding.
    assert md.startswith(f"# {report['title']}")
    assert "Object-level authorization missing" in report["title"]

    # Executive summary precedes the first finding section.
    exec_idx = md.index("## Executive summary")
    first_finding_idx = md.index("## Finding xx-01-authz")
    assert exec_idx < first_finding_idx

    # Headings are complete sentences and parallel in form.
    headings = [h.lstrip("# ") for h in re.findall(r"^## Finding .+$", md, re.MULTILINE)]
    assert len(headings) == 2
    for h in headings:
        assert h.startswith("Finding ")
        assert h.endswith(".")

    # Per-finding template order: Summary -> Impact -> Conditions -> Remediation -> References -> Evidence.
    section_pattern = re.compile(r"^### (Summary|Impact|Conditions|Remediation|References|Evidence)$", re.MULTILINE)
    heading_matches = list(re.finditer(r"^## Finding .+$", md, re.MULTILINE))
    assert len(heading_matches) == 2
    for i, m in enumerate(heading_matches):
        start = m.start()
        end = heading_matches[i + 1].start() if i + 1 < len(heading_matches) else len(md)
        chunk = md[start:end]
        found = [s.group(1) for s in section_pattern.finditer(chunk)]
        assert found == ["Summary", "Impact", "Conditions", "Remediation", "References", "Evidence"], (
            f"section order in chunk {i}: {found}"
        )

    # Every finding points to the evidence appendix.
    assert md.count("See Appendix A for the complete evidence ledger references.") == 2

    # Appendix exists and lists a ledger ref for every finding.
    assert "## Appendix A: Evidence ledger references" in md
    for f in (f1, f2):
        assert f"**{f['finding_id']}**" in md
        assert f["evidence"][0]["ledger_ref"] in md

    _assert_no_fud(md)
    _assert_named_actor(md)


def test_full_report_rejects_candidate():
    f = _finding("xx-01-candidate", "candidate")
    with pytest.raises(ValueError, match=r"xx-01-candidate"):
        full_report.render_full_report([f], _engagement())


def test_full_report_rejects_empty():
    with pytest.raises(ValueError, match=r"no confirmed findings"):
        full_report.render_full_report([], _engagement())
