"""Passive observer tests — no network, real store, mocked proxy traffic."""
import base64
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from passive_checks import CHECKS, SEVERITIES, run_checks
from findings_store import FindingStore  # noqa: E402
import traffic_observer as observer  # noqa: E402

_VALID = Path(__file__).resolve().parent.parent / "examples" / "fixtures" / "valid"


def _engagement() -> dict:
    eng = json.loads((_VALID / "engagement.json").read_text())
    eng["engagement_id"] = "eng-passive-001"
    # Keep tests valid regardless of when they run.
    eng["window"] = {
        "start": "2020-01-01T00:00:00Z",
        "expires": "2099-12-31T23:59:59Z",
    }
    return eng


def _store(tmp_path: Path) -> FindingStore:
    # Keep observer state inside the per-test tmp dir so dedup does not leak.
    os.environ["HALO_HACKER_DATA_DIR"] = str(tmp_path / "data")
    root = tmp_path / "engagement"
    store = FindingStore.create(root, _engagement())
    targets = {
        "schema_version": 1,
        "includes": [{"hostname": "vuln-app.test.lab"}],
        "exclusions": [],
    }
    (root / "scope").mkdir(parents=True, exist_ok=True)
    (root / "scope" / "targets.json").write_text(json.dumps(targets))
    return store


def _pair(**over) -> dict:
    base = {
        "method": "GET",
        "url": "https://vuln-app.test.lab/",
        "host": "vuln-app.test.lab",
        "status": 200,
        "response_headers": {"Content-Type": "text/html; charset=utf-8"},
        "response_body": "<html><body>ok</body></html>",
    }
    base.update(over)
    return base


def test_each_check_fires():
    cases = [
        ("missing-security-headers", _pair()),
        ("verbose-server-banner", _pair(response_headers={
            "Content-Type": "text/html",
            "Server": "nginx/1.18.0",
        })),
        ("stack-trace-disclosure", _pair(response_body="Traceback (most recent call last):\n  File \"app.py\"")),
        ("internal-ip-disclosure", _pair(response_body="backend is 10.0.0.1")),
        ("insecure-set-cookie", _pair(response_headers={
            "Content-Type": "text/html",
            "Set-Cookie": "session=abc123; Path=/",
        })),
        ("reflected-query-value", _pair(
            url="https://vuln-app.test.lab/search?q=abcdefgh1234",
            response_body="<div>abcdefgh1234</div>",
        )),
    ]
    for expected_id, pair in cases:
        hits = run_checks(pair)
        assert any(h["check_id"] == expected_id for h in hits), f"{expected_id} did not fire"


def test_clean_pair_fires_nothing():
    pair = _pair(
        response_headers={
            "Content-Type": "text/html",
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self'",
            "X-Content-Type-Options": "nosniff",
        },
        response_body="<html><body>hello world</body></html>",
    )
    assert run_checks(pair) == []


def test_scope_gate_counts_out_of_scope(tmp_path, monkeypatch):
    store = _store(tmp_path)

    def _fake_fetch(since):
        return [
            _pair(host="vuln-app.test.lab", url="https://vuln-app.test.lab/"),
            _pair(host="other.example.com", url="https://other.example.com/"),
        ], {"offset": 2}

    monkeypatch.setattr(observer, "_fetch_caido", _fake_fetch)
    result = observer.observe_once(store.root, proxy="caido", since={})
    assert result["ok"] is True
    assert result["out_of_scope"] == 1
    assert result["new"] == 1
    findings = store.list_findings()
    assert len(findings) == 1
    assert "vuln-app.test.lab" in findings[0]["target_ref"]
    assert not any("other.example.com" in f["target_ref"] for f in findings)


def test_redaction_hides_credentials_in_evidence(tmp_path, monkeypatch):
    store = _store(tmp_path)

    def _fake_fetch(since):
        return [_pair(
            url="https://vuln-app.test.lab/api/user",
            response_headers={
                "Content-Type": "text/html",
                "Strict-Transport-Security": "max-age=31536000",
                "Authorization": "Bearer super-secret-token-12345",
            },
            response_body='{"token":"sk-live-1234567890abcdef"}',
        )], {"offset": 1}

    monkeypatch.setattr(observer, "_fetch_caido", _fake_fetch)
    result = observer.observe_once(store.root, proxy="caido", since={})
    assert result["ok"] is True
    assert result["new"] == 1

    finding = store.list_findings()[0]
    row = store.resolve_ledger_ref(finding["evidence"][0]["ledger_ref"])
    artifact = (store.artifacts / row["artifact_sha256"] / "artifact.bin").read_bytes()
    text = artifact.decode()
    assert "super-secret-token-12345" not in text
    assert "sk-live-1234567890abcdef" not in text
    assert "[REDACTED" in text

    finding_json = json.dumps(finding)
    assert "super-secret-token-12345" not in finding_json
    assert "sk-live-1234567890abcdef" not in finding_json


def test_dedup_same_check_location_once(tmp_path, monkeypatch):
    store = _store(tmp_path)

    def _pair_dedup(**over):
        return _pair(
            url="https://vuln-app.test.lab/page",
            response_headers={
                "Content-Type": "text/html",
                "Strict-Transport-Security": "max-age=31536000",
                "Content-Security-Policy": "default-src 'self'",
                "X-Content-Type-Options": "nosniff",
            },
            response_body="backend is 192.168.1.1",
            **over,
        )

    def _fake_fetch(since):
        return [
            _pair_dedup(),
            _pair_dedup(),
        ], {"offset": 2}

    monkeypatch.setattr(observer, "_fetch_caido", _fake_fetch)
    r1 = observer.observe_once(store.root, proxy="caido", since={})
    r2 = observer.observe_once(store.root, proxy="caido", since=r1["since"])
    assert r1["new"] == 1
    assert r2["new"] == 0
    assert r2["deduped"] >= 1
    assert len(store.list_findings()) == 1


def test_candidate_finding_resolves_ledger(tmp_path, monkeypatch):
    store = _store(tmp_path)

    def _fake_fetch(since):
        return [_pair(
            url="https://vuln-app.test.lab/admin",
            response_headers={"Content-Type": "text/html", "Server": "Apache/2.4.41"},
        )], {"offset": 1}

    monkeypatch.setattr(observer, "_fetch_caido", _fake_fetch)
    result = observer.observe_once(store.root, proxy="caido", since={})
    assert result["ok"] is True
    assert result["new"] == 2  # verbose banner + missing headers

    findings = store.list_findings()
    assert all(f["status"] == "candidate" for f in findings)
    assert all(f["source"] == "passive-traffic" for f in findings)
    for f in findings:
        row = store.resolve_ledger_ref(f["evidence"][0]["ledger_ref"])
        assert row["finding_id"] == f["finding_id"]


def test_finding_event_state_is_identified(tmp_path, monkeypatch):
    store = _store(tmp_path)

    def _fake_fetch(since):
        return [_pair(
            url="https://vuln-app.test.lab/xss?q=reflectme1234",
            response_headers={
                "Content-Type": "text/html",
                "Strict-Transport-Security": "max-age=31536000",
                "Content-Security-Policy": "default-src 'self'",
                "X-Content-Type-Options": "nosniff",
            },
            response_body="<div>reflectme1234</div>",
        )], {"offset": 1}

    monkeypatch.setattr(observer, "_fetch_caido", _fake_fetch)
    result = observer.observe_once(store.root, proxy="caido", since={})
    assert result["ok"] is True
    assert len(result["events"]) == 1
    ev = result["events"][0]
    assert ev["state"] == "identified"
    assert ev["source"] == "passive-traffic"
    assert ev["finding_id"].startswith("pas-01-")


def test_network_failure_returns_error(tmp_path, monkeypatch):
    store = _store(tmp_path)

    def _boom(since):
        raise observer.urllib.error.URLError("connection refused")

    monkeypatch.setattr(observer, "_fetch_caido", _boom)
    result = observer.observe_once(store.root, proxy="caido", since={})
    assert result["ok"] is False
    assert result["error"] == "network"


def test_burp_fetch_parses_raw_http(monkeypatch):
    raw_resp = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/html\r\n"
        b"Set-Cookie: session=abc; Path=/\r\n"
        b"\r\n"
        b"<html></html>"
    )
    items = [{
        "host": "vuln-app.test.lab",
        "port": 443,
        "protocol": "https",
        "request": base64.b64encode(b"GET /admin HTTP/1.1\r\nHost: vuln-app.test.lab\r\n\r\n").decode(),
        "response": base64.b64encode(raw_resp).decode(),
    }]

    class _Resp:
        def read(self):
            return json.dumps(items).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(observer.urllib.request, "urlopen", lambda req, timeout=15: _Resp())
    events, since = observer._fetch_burp({"offset": 0})
    assert len(events) == 1
    assert events[0]["status"] == 200
    assert events[0]["method"] == "GET"
    assert events[0]["url"] == "https://vuln-app.test.lab/admin"
    assert "Set-Cookie" in events[0]["response_headers"]


def test_unexpected_failure_is_caught(tmp_path, monkeypatch):
    store = _store(tmp_path)

    def _boom(since):
        raise ValueError("unexpected internal error")

    monkeypatch.setattr(observer, "_fetch_caido", _boom)
    result = observer.observe_once(store.root, proxy="caido", since={})
    assert result["ok"] is False
    assert "unexpected internal error" in result["error"]


def test_reflected_value_noise_guard_ignored():
    pair = _pair(
        url="https://vuln-app.test.lab/search?q=short",
        response_headers={
            "Content-Type": "text/html",
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self'",
            "X-Content-Type-Options": "nosniff",
        },
        response_body="<div>short</div>",
    )
    assert not any(h["check_id"] == "reflected-query-value" for h in run_checks(pair))


def test_severity_hints_are_sane():
    for c in CHECKS:
        assert c["severity_hint"] in SEVERITIES
        assert "{host}" in c["title"]
    missing = next(c for c in CHECKS if c["check_id"] == "missing-security-headers")
    assert missing["severity_hint"] != "critical"

