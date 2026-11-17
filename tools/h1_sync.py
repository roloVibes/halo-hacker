#!/usr/bin/env python3
"""Normalize captured HackerOne Hacker API v1 JSON into Halo pack data files.

This tool intentionally performs no HTTP requests.  It consumes raw JSON files
already fetched by h1_server, curl, or another client, writes dashboard-ready
JSON under the halo-hacker pack data directory, detects report changes against
prior sync state, and emits one best-effort pack event per sync.

Public functions return ``{"ok": True, ...}`` on success or
``{"ok": False, "error": "..."}`` on failure.  Standalone CLI:

    python -m tools.h1_sync <fixtures_dir>
    python -m tools.h1_sync status

Stdlib-only by pack convention.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_PACK_NAME = "halo-hacker"
_EVENT_TYPE = "hh.h1.update"


# ---------------------------------------------------------------------------
# Data-directory resolver
# ---------------------------------------------------------------------------


def _ext_data_dir() -> Path | None:
    """Return the harness data dir for this pack, when available."""
    try:
        from halo_harness.ext import data_dir as _harness_data_dir  # type: ignore[import-untyped]

        return Path(_harness_data_dir(_PACK_NAME))
    except Exception:
        return None


def _data_dir() -> Path:
    """Resolve the pack data directory.

    Precedence:
    1. HALO_HACKER_DATA_DIR (tests/headless runs)
    2. halo_harness.ext.data_dir("halo-hacker")
    3. ~/.halo/halo-hacker-data (standalone fallback)
    """
    d = (
        Path(os.environ["HALO_HACKER_DATA_DIR"])
        if "HALO_HACKER_DATA_DIR" in os.environ
        else (_ext_data_dir() or Path.home() / ".halo" / "halo-hacker-data")
    )
    d.mkdir(parents=True, exist_ok=True)
    return d


def _h1_dir() -> Path:
    d = _data_dir() / "h1"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_write_json(path: Path, data: Any) -> None:
    """Atomically write JSON using a same-directory temp file + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, default=str))
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def _read_json_file(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text()), None
    except Exception as exc:
        return None, f"{path.name}: {exc}"


def _read_existing_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text())
    except Exception:
        return default


def _jsonapi_data(raw: Any) -> Any:
    """Return the JSON:API data member, or the object itself for bare payloads."""
    if isinstance(raw, dict) and "data" in raw:
        return raw.get("data")
    return raw


def _as_list(value: Any) -> list[Any]:
    value = _jsonapi_data(value)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _attrs(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict) and isinstance(obj.get("attributes"), dict):
        return obj["attributes"]
    return {}


def _relationships(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict) and isinstance(obj.get("relationships"), dict):
        return obj["relationships"]
    return {}


def _rel_data(obj: Any, name: str) -> Any:
    rel = _relationships(obj).get(name)
    if isinstance(rel, dict):
        return rel.get("data")
    return None


def _rel_attrs(obj: Any, name: str) -> dict[str, Any]:
    data = _rel_data(obj, name)
    if isinstance(data, dict):
        return _attrs(data)
    return {}


def _clean_dict(values: dict[str, Any], required: set[str] | None = None) -> dict[str, Any]:
    """Drop None-valued optional keys while preserving required keys."""
    required = required or set()
    return {k: v for k, v in values.items() if k in required or v is not None}


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _amount_to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(str(value).replace(",", ""))
    except Exception:
        return 0.0


def _iso_gt(left: Any, right: Any) -> bool:
    """Return True when ISO-ish timestamp left is later than right."""
    if not left or not right:
        return bool(left and not right)
    try:
        ldt = datetime.fromisoformat(str(left).replace("Z", "+00:00"))
        rdt = datetime.fromisoformat(str(right).replace("Z", "+00:00"))
        return ldt > rdt
    except Exception:
        return str(left) > str(right)


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------


def _normalize_report_summary(report: dict[str, Any]) -> dict[str, Any]:
    attrs = _attrs(report)
    weakness_attrs = _rel_attrs(report, "weakness")
    severity_attrs = _rel_attrs(report, "severity")
    program_attrs = _rel_attrs(report, "program")

    rid = str(report.get("id") or attrs.get("id") or "")
    title = attrs.get("title") or report.get("title") or rid
    state = attrs.get("state") or report.get("state") or "unknown"

    return _clean_dict(
        {
            "id": rid,
            "title": title,
            "state": state,
            "program_handle": program_attrs.get("handle"),
            "weakness_name": weakness_attrs.get("name"),
            "weakness_external_id": weakness_attrs.get("external_id"),
            "severity_rating": _first_present(severity_attrs.get("rating"), attrs.get("severity_rating")),
            "created_at": attrs.get("created_at"),
            "triaged_at": attrs.get("triaged_at"),
            "closed_at": attrs.get("closed_at"),
            "bounty_awarded_at": attrs.get("bounty_awarded_at"),
            "last_program_activity_at": attrs.get("last_program_activity_at"),
            "last_reporter_activity_at": attrs.get("last_reporter_activity_at"),
            "cve_ids": attrs.get("cve_ids") or [],
        },
        required={"id", "title", "state"},
    )


def _normalize_activity(activity: dict[str, Any]) -> dict[str, Any]:
    attrs = _attrs(activity)
    actor_attrs = _rel_attrs(activity, "actor")
    bounty_attrs = _rel_attrs(activity, "bounty")
    amount = _first_present(
        attrs.get("bounty_amount"),
        attrs.get("amount"),
        attrs.get("awarded_amount"),
        bounty_attrs.get("awarded_amount"),
        bounty_attrs.get("amount"),
    )
    return _clean_dict(
        {
            "type": activity.get("type"),
            "created_at": attrs.get("created_at"),
            "actor_username": actor_attrs.get("username"),
            "message": attrs.get("message"),
            "internal": attrs.get("internal"),
            "bounty_amount": amount,
        },
        required={"type", "created_at", "actor_username", "message", "internal", "bounty_amount"},
    )


def _normalize_bounty(bounty: dict[str, Any]) -> dict[str, Any]:
    attrs = _attrs(bounty)
    awarded_user_attrs = _rel_attrs(bounty, "awarded_user")
    return _clean_dict(
        {
            "id": str(bounty.get("id")) if bounty.get("id") is not None else None,
            "amount": attrs.get("amount"),
            "bonus_amount": attrs.get("bonus_amount"),
            "awarded_amount": attrs.get("awarded_amount"),
            "awarded_bonus_amount": attrs.get("awarded_bonus_amount"),
            "awarded_currency": attrs.get("awarded_currency"),
            "created_at": attrs.get("created_at"),
            "awarded_user_username": awarded_user_attrs.get("username"),
        }
    )


def _normalize_report_detail(report: dict[str, Any], generated: str) -> dict[str, Any]:
    attrs = _attrs(report)
    activities = _rel_data(report, "activities")
    bounties = _rel_data(report, "bounties")
    timeline = [_normalize_activity(a) for a in activities if isinstance(a, dict)] if isinstance(activities, list) else []
    normalized_bounties = [_normalize_bounty(b) for b in bounties if isinstance(b, dict)] if isinstance(bounties, list) else []

    detail = _normalize_report_summary(report)
    detail.update(
        _clean_dict(
            {
                "generated": generated,
                "submitted_at": attrs.get("submitted_at"),
                "vulnerability_information": attrs.get("vulnerability_information"),
                "first_program_activity_at": attrs.get("first_program_activity_at"),
                "last_public_activity_at": attrs.get("last_public_activity_at"),
                "last_activity_at": attrs.get("last_activity_at"),
                "disclosed_at": attrs.get("disclosed_at"),
                "reporter_agreed_on_going_public_at": attrs.get("reporter_agreed_on_going_public_at"),
                "timeline": timeline,
                "bounties": normalized_bounties,
                "raw": report,
            },
            required={"generated", "timeline", "bounties", "raw"},
        )
    )
    return detail


def _normalize_scope(scope: dict[str, Any]) -> dict[str, Any]:
    attrs = _attrs(scope)
    return _clean_dict(
        {
            "asset_type": attrs.get("asset_type"),
            "asset_identifier": attrs.get("asset_identifier"),
            "eligible_for_bounty": attrs.get("eligible_for_bounty"),
            "eligible_for_submission": attrs.get("eligible_for_submission"),
            "max_severity": attrs.get("max_severity"),
            "instruction": attrs.get("instruction"),
        },
        required={"asset_type", "asset_identifier", "eligible_for_bounty", "eligible_for_submission", "max_severity", "instruction"},
    )


def _normalize_program(program: dict[str, Any], scopes_by_handle: dict[str, list[dict[str, Any]]], weaknesses_by_handle: dict[str, int]) -> dict[str, Any]:
    attrs = _attrs(program)
    handle = attrs.get("handle") or str(program.get("id") or "")
    rel_scopes = _rel_data(program, "structured_scopes")
    scopes = [_normalize_scope(s) for s in rel_scopes if isinstance(s, dict)] if isinstance(rel_scopes, list) else []
    if not scopes and handle in scopes_by_handle:
        scopes = [_normalize_scope(s) for s in scopes_by_handle.get(handle, [])]

    rel_weaknesses = _rel_data(program, "weaknesses")
    weakness_count = None
    if isinstance(rel_weaknesses, list):
        weakness_count = len(rel_weaknesses)
    elif handle in weaknesses_by_handle:
        weakness_count = weaknesses_by_handle[handle]
    else:
        weakness_count = attrs.get("weaknesses_count")

    return _clean_dict(
        {
            "handle": handle,
            "name": attrs.get("name"),
            "state": attrs.get("state"),
            "submission_state": attrs.get("submission_state"),
            "offers_bounties": attrs.get("offers_bounties"),
            "number_of_reports_for_user": attrs.get("number_of_reports_for_user"),
            "number_of_valid_reports_for_user": attrs.get("number_of_valid_reports_for_user"),
            "bounty_earned_for_user": attrs.get("bounty_earned_for_user"),
            "last_invitation_accepted_at_for_user": attrs.get("last_invitation_accepted_at_for_user"),
            "policy": attrs.get("policy"),
            "scopes": scopes,
            "weaknesses_count": weakness_count,
        },
        required={
            "handle",
            "name",
            "state",
            "submission_state",
            "offers_bounties",
            "number_of_reports_for_user",
            "number_of_valid_reports_for_user",
            "bounty_earned_for_user",
            "last_invitation_accepted_at_for_user",
            "policy",
            "scopes",
            "weaknesses_count",
        },
    )


def _normalize_earning(earning: Any) -> dict[str, Any]:
    if not isinstance(earning, dict) or "attributes" not in earning:
        return earning if isinstance(earning, dict) else {"value": earning}
    attrs = _attrs(earning)
    program_attrs = _rel_attrs(earning, "program")
    bounty_attrs = _rel_attrs(earning, "bounty")
    return _clean_dict(
        {
            "id": str(earning.get("id")) if earning.get("id") is not None else None,
            "type": earning.get("type"),
            "amount": attrs.get("amount"),
            "awarded_by_name": attrs.get("awarded_by_name"),
            "created_at": attrs.get("created_at"),
            "program_handle": program_attrs.get("handle"),
            "program_name": program_attrs.get("name"),
            "bounty_id": str(_rel_data(earning, "bounty").get("id")) if isinstance(_rel_data(earning, "bounty"), dict) and _rel_data(earning, "bounty").get("id") is not None else None,
            "bounty_amount": bounty_attrs.get("awarded_amount") or bounty_attrs.get("amount"),
            "raw": earning,
        }
    )


def _normalize_payout(payout: Any) -> dict[str, Any]:
    if not isinstance(payout, dict):
        return {"value": payout}
    if "attributes" in payout:
        attrs = _attrs(payout)
        base = {"id": str(payout.get("id")) if payout.get("id") is not None else None, "type": payout.get("type")}
        base.update(attrs)
        return _clean_dict(base)
    return payout


def _normalize_intent(intent: dict[str, Any]) -> dict[str, Any]:
    attrs = _attrs(intent)
    job_status = attrs.get("job_status_by_type") or {}
    failed_jobs: list[str] = []
    if isinstance(job_status, dict):
        failed_jobs = [str(name) for name, status in job_status.items() if status == "failed"]
    created_or_updated = _first_present(attrs.get("updated_at"), attrs.get("created_at"), attrs.get("created_or_updated"))
    return _clean_dict(
        {
            "id": str(intent.get("id") or attrs.get("id") or ""),
            "title": attrs.get("title"),
            "description": attrs.get("description"),
            "state": attrs.get("state"),
            "job_status_by_type": job_status,
            "failed_jobs": failed_jobs,
            "metadata": attrs.get("metadata") or {},
            "created_or_updated": created_or_updated,
        },
        required={"id", "title", "description", "state", "job_status_by_type", "failed_jobs", "metadata", "created_or_updated"},
    )


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------


def _load_fixture(path: Path, skipped: list[str], errors: list[str]) -> Any | None:
    if not path.exists():
        skipped.append(path.name)
        return None
    data, error = _read_json_file(path)
    if error:
        errors.append(error)
        return None
    return data


def _load_glob(fixtures_dir: Path, pattern: str, errors: list[str]) -> list[tuple[Path, Any]]:
    loaded: list[tuple[Path, Any]] = []
    for path in sorted(fixtures_dir.glob(pattern)):
        if not path.is_file():
            continue
        data, error = _read_json_file(path)
        if error:
            errors.append(error)
            continue
        loaded.append((path, data))
    return loaded


def _suffix_key(path: Path, prefix: str) -> str:
    stem = path.stem
    if stem.startswith(prefix):
        return stem[len(prefix) :]
    return stem


# ---------------------------------------------------------------------------
# Change detection / events
# ---------------------------------------------------------------------------


def _detect_changes(reports: list[dict[str, Any]], previous: dict[str, Any]) -> list[dict[str, Any]]:
    prev_states = previous.get("report_states") if isinstance(previous.get("report_states"), dict) else {}
    prev_activity = previous.get("report_activity") if isinstance(previous.get("report_activity"), dict) else {}
    changes: list[dict[str, Any]] = []
    for report in reports:
        rid = str(report.get("id", ""))
        if not rid:
            continue
        state = report.get("state")
        old_state = prev_states.get(rid)
        if old_state is not None and state != old_state:
            changes.append(
                {
                    "report_id": rid,
                    "program_handle": report.get("program_handle"),
                    "kind": "state",
                    "from": old_state,
                    "to": state,
                }
            )
        activity = report.get("last_program_activity_at")
        old_activity = prev_activity.get(rid)
        if old_activity is not None and _iso_gt(activity, old_activity):
            changes.append(
                {
                    "report_id": rid,
                    "program_handle": report.get("program_handle"),
                    "kind": "activity",
                    "from": old_activity,
                    "to": activity,
                }
            )
    return changes


def _emit_or_queue_event(h1_dir: Path, payload: dict[str, Any], changes: list[dict[str, Any]]) -> str:
    """Emit a pack event if the harness supports it; otherwise queue changes."""
    if not changes:
        return "none"

    try:
        import halo_harness.ext as ext  # type: ignore[import-untyped]

        emit = getattr(ext, "emit_event", None)
        if callable(emit):
            emit(_PACK_NAME, _EVENT_TYPE, payload)
            return "emit_event"
        publish = getattr(ext, "publish_pack_event", None)
        if callable(publish):
            publish(_PACK_NAME, _EVENT_TYPE, payload)
            return "publish_pack_event"
    except Exception:
        pass

    pending_path = h1_dir / "pending_events.json"
    pending = _read_existing_json(pending_path, [])
    if not isinstance(pending, list):
        pending = []
    pending.extend(changes)
    _atomic_write_json(pending_path, pending)
    return "pending_events"


def _write_sync_state(h1_dir: Path, generated: str, reports: list[dict[str, Any]], programs: list[dict[str, Any]], intents: list[dict[str, Any]]) -> dict[str, Any]:
    state = {
        "last_sync": generated,
        "counts": {"reports": len(reports), "programs": len(programs), "intents": len(intents)},
        "previous": {
            "report_states": {str(r.get("id")): r.get("state") for r in reports if r.get("id") is not None},
            "report_activity": {
                str(r.get("id")): r.get("last_program_activity_at")
                for r in reports
                if r.get("id") is not None and r.get("last_program_activity_at") is not None
            },
        },
    }
    _atomic_write_json(h1_dir / "sync_state.json", state)
    return state


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sync(fixtures_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Normalize raw HackerOne fixture files into the pack data dir."""
    try:
        fixtures = Path(fixtures_dir).expanduser()
        if not fixtures.exists() or not fixtures.is_dir():
            return {"ok": False, "error": f"fixtures_dir not found or not a directory: {fixtures}"}

        generated = _now_iso()
        h1_dir = _h1_dir()
        skipped: list[str] = []
        errors: list[str] = []

        # Reports: list endpoint plus individual detail files.
        reports_by_id: dict[str, dict[str, Any]] = {}
        raw_reports = _load_fixture(fixtures / "reports.json", skipped, errors)
        if raw_reports is not None:
            for report in _as_list(raw_reports):
                if isinstance(report, dict):
                    summary = _normalize_report_summary(report)
                    if summary.get("id"):
                        reports_by_id[str(summary["id"])] = summary

        detail_dir = h1_dir / "report_details"
        detail_dir.mkdir(parents=True, exist_ok=True)
        for path, raw_detail in _load_glob(fixtures, "report_*.json", errors):
            detail_obj = _jsonapi_data(raw_detail)
            if not isinstance(detail_obj, dict):
                errors.append(f"{path.name}: report detail is not an object")
                continue
            detail = _normalize_report_detail(detail_obj, generated)
            rid = str(detail.get("id") or _suffix_key(path, "report_"))
            if not rid:
                errors.append(f"{path.name}: report detail missing id")
                continue
            # Merge: the fresh list summary (from reports.json, fetched this run)
            # wins on state/activity fields so change detection isn't masked by a
            # stale detail file; the detail fills in everything the list lacks.
            detail_summary = _normalize_report_summary(detail_obj)
            existing = reports_by_id.get(rid)
            reports_by_id[rid] = {**detail_summary, **(existing or {})}
            _atomic_write_json(detail_dir / f"{rid}.json", detail)

        reports = sorted(reports_by_id.values(), key=lambda r: (str(r.get("created_at") or ""), str(r.get("id") or "")), reverse=True)

        # Programs, with optional standalone scopes_*.json and weaknesses_*.json helpers.
        scopes_by_handle: dict[str, list[dict[str, Any]]] = {}
        for path, raw_scopes in _load_glob(fixtures, "scopes_*.json", errors):
            scopes_by_handle[_suffix_key(path, "scopes_")] = [s for s in _as_list(raw_scopes) if isinstance(s, dict)]

        weaknesses_by_handle: dict[str, int] = {}
        for path, raw_weaknesses in _load_glob(fixtures, "weaknesses_*.json", errors):
            weaknesses_by_handle[_suffix_key(path, "weaknesses_")] = len([w for w in _as_list(raw_weaknesses) if isinstance(w, dict)])

        programs: list[dict[str, Any]] = []
        program_files = _load_glob(fixtures, "program_*.json", errors)
        if not program_files:
            skipped.append("program_*.json")
        for _path, raw_program in program_files:
            for program in _as_list(raw_program):
                if isinstance(program, dict):
                    programs.append(_normalize_program(program, scopes_by_handle, weaknesses_by_handle))
        programs.sort(key=lambda p: str(p.get("handle") or ""))

        # Earnings, balance, payouts.
        balance_raw = _load_fixture(fixtures / "balance.json", skipped, errors)
        earnings_raw = _load_fixture(fixtures / "earnings.json", skipped, errors)
        payouts_raw = _load_fixture(fixtures / "payouts.json", skipped, errors)

        balance: Any = None
        balance_data = _jsonapi_data(balance_raw)
        if isinstance(balance_data, dict):
            balance = balance_data.get("balance", balance_data)
        elif balance_data is not None:
            balance = balance_data

        earnings = [_normalize_earning(e) for e in _as_list(earnings_raw)] if earnings_raw is not None else []
        payouts = [_normalize_payout(p) for p in _as_list(payouts_raw)] if payouts_raw is not None else []
        total_earned = 0.0
        for earning in earnings:
            if isinstance(earning, dict):
                total_earned += _amount_to_float(earning.get("amount") or earning.get("bounty_amount"))

        # Intents: list endpoint plus individual intent files; individual wins by id.
        intents_by_id: dict[str, dict[str, Any]] = {}
        intents_raw = _load_fixture(fixtures / "intents.json", skipped, errors)
        if intents_raw is not None:
            for intent in _as_list(intents_raw):
                if isinstance(intent, dict):
                    normalized = _normalize_intent(intent)
                    if normalized.get("id"):
                        intents_by_id[str(normalized["id"])] = normalized

        for path, raw_intent in _load_glob(fixtures, "intent_*.json", errors):
            intent_obj = _jsonapi_data(raw_intent)
            if not isinstance(intent_obj, dict):
                errors.append(f"{path.name}: intent detail is not an object")
                continue
            normalized = _normalize_intent(intent_obj)
            iid = str(normalized.get("id") or _suffix_key(path, "intent_"))
            if iid:
                normalized["id"] = iid
                intents_by_id[iid] = normalized

        intents = sorted(intents_by_id.values(), key=lambda i: str(i.get("created_or_updated") or i.get("id") or ""), reverse=True)

        # Change detection against previous sync state before overwriting it.
        old_state = _read_existing_json(h1_dir / "sync_state.json", {})
        previous = old_state.get("previous", {}) if isinstance(old_state, dict) else {}
        changes = _detect_changes(reports, previous if isinstance(previous, dict) else {})

        counts = {"reports": len(reports), "programs": len(programs), "intents": len(intents)}

        # Normalized outputs.
        _atomic_write_json(h1_dir / "reports.json", {"generated": generated, "reports": reports})
        _atomic_write_json(h1_dir / "programs.json", {"generated": generated, "programs": programs})
        _atomic_write_json(
            h1_dir / "earnings.json",
            {
                "generated": generated,
                "balance": balance,
                "earnings": earnings,
                "payouts": payouts,
                "total_earned": total_earned,
            },
        )
        _atomic_write_json(h1_dir / "intents.json", {"generated": generated, "intents": intents})
        _write_sync_state(h1_dir, generated, reports, programs, intents)

        event_payload = {"kind": "sync", "counts": counts, "changes": changes}
        event_sink = _emit_or_queue_event(h1_dir, event_payload, changes)

        result: dict[str, Any] = {
            "ok": True,
            "counts": counts,
            "changes": changes,
            "skipped": skipped,
            "event_sink": event_sink,
            "data_dir": str(_data_dir()),
        }
        if errors:
            result["errors"] = errors
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def status() -> dict[str, Any]:
    """Read existing normalized H1 data and return summary counts."""
    try:
        h1_dir = _h1_dir()
        reports_doc = _read_existing_json(h1_dir / "reports.json", {})
        programs_doc = _read_existing_json(h1_dir / "programs.json", {})
        intents_doc = _read_existing_json(h1_dir / "intents.json", {})
        earnings_doc = _read_existing_json(h1_dir / "earnings.json", {})
        sync_state = _read_existing_json(h1_dir / "sync_state.json", {})
        pending_events = _read_existing_json(h1_dir / "pending_events.json", [])

        reports = reports_doc.get("reports", []) if isinstance(reports_doc, dict) else []
        programs = programs_doc.get("programs", []) if isinstance(programs_doc, dict) else []
        intents = intents_doc.get("intents", []) if isinstance(intents_doc, dict) else []
        earnings = earnings_doc.get("earnings", []) if isinstance(earnings_doc, dict) else []
        payouts = earnings_doc.get("payouts", []) if isinstance(earnings_doc, dict) else []

        return {
            "ok": True,
            "data_dir": str(_data_dir()),
            "h1_dir": str(h1_dir),
            "last_sync": sync_state.get("last_sync") if isinstance(sync_state, dict) else None,
            "counts": {
                "reports": len(reports) if isinstance(reports, list) else 0,
                "programs": len(programs) if isinstance(programs, list) else 0,
                "intents": len(intents) if isinstance(intents, list) else 0,
                "earnings": len(earnings) if isinstance(earnings, list) else 0,
                "payouts": len(payouts) if isinstance(payouts, list) else 0,
                "pending_events": len(pending_events) if isinstance(pending_events, list) else 0,
            },
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli() -> None:
    args = sys.argv[1:]
    if not args:
        result = {"ok": False, "error": "Usage: python -m tools.h1_sync <fixtures_dir>|status"}
        print(json.dumps(result, indent=2, default=str))
        sys.exit(1)

    if args[0] == "status":
        result = status()
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result.get("ok") else 1)

    result = sync(args[0])
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    _cli()
