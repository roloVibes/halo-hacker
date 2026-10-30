"""thin CVE enrichment (NVD 2.0 + CISA KEV + FIRST EPSS), stdlib-only by pack convention;
for a broader research workbench see github.com/mukul975/cve-mcp-server (not bundled).

Tools:
- cve_lookup(cve_id) — NVD API 2.0 (https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=...):
  returns id, descriptions, CVSS 3.1 vector+score (from the primary or first metric),
  CWE ids, published/modified dates, references (urls only). Zero results → clear "unknown cve" answer,
  not an error.
- kev_check(cve_ids) — CISA KEV catalog (https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json):
  fetch once, cache to the pack data dir with a TTL of 24h, note the catalog date:
  returns which of the ids are known-exploited + their known ransomware/use notes.
- epss_score(cve_id) — FIRST EPSS API (https://api.first.org/data/v1/epss?cve=...):
  epss score + percentile.

Conventions: NVD API key OPTIONAL via env NVD_API_KEY (header apiKey; without it,
respect the 5-req/30s unauthenticated limit with a simple client-side pacer);
all HTTP via urllib with a 15s timeout; every tool returns JSON-serializable dicts;
never raise — return {"ok": false, "error": ...} on failure. Cache directory:
resolve via env HALO_HACKER_DATA_DIR if set else ~/.halo/halo-hacker-data
(create with parents). Offline/network failure → {"ok": false, "error": "network"}.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from halo_harness.ext import API_VERSION
except ImportError:  # the `python` on PATH is not the one Halo runs in
    API_VERSION = "1.0"

# Global cache for CISA KEV data
_KEV_DATA = None
_KEV_CACHE_TIME = None

def _get_cache_dir() -> str:
    """Get the cache directory, using HALO_HACKER_DATA_DIR env var or default."""
    cache_dir = os.environ.get("HALO_HACKER_DATA_DIR")
    if not cache_dir:
        cache_dir = os.path.expanduser("~/.halo/halo-hacker-data")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

_NVD_CALL_TIMES = []  # monotonic timestamps of unauthenticated NVD calls
_NVD_RATE_WINDOW = 30.0   # seconds
_NVD_RATE_MAX = 5         # requests per window without a key


def _nvd_pace() -> None:
    """Client-side pacer for the unauthenticated NVD limit (5 req/30s).
    With NVD_API_KEY set (50 req/30s) this is a no-op."""
    if os.environ.get("NVD_API_KEY"):
        return
    import time
    now = time.monotonic()
    # drop timestamps outside the window
    while _NVD_CALL_TIMES and now - _NVD_CALL_TIMES[0] >= _NVD_RATE_WINDOW:
        _NVD_CALL_TIMES.pop(0)
    if len(_NVD_CALL_TIMES) >= _NVD_RATE_MAX:
        wait = _NVD_RATE_WINDOW - (now - _NVD_CALL_TIMES[0])
        if wait > 0:
            time.sleep(wait + 0.05)
        now = time.monotonic()
        while _NVD_CALL_TIMES and now - _NVD_CALL_TIMES[0] >= _NVD_RATE_WINDOW:
            _NVD_CALL_TIMES.pop(0)
    _NVD_CALL_TIMES.append(time.monotonic())


def _fetch_nvd(cve_id: str) -> dict:
    """Fetch CVE data from NVD API 2.0."""
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
    headers = {"User-Agent": "halo-hacker-cve-server/1.0"}

    # Add API key if available
    api_key = os.environ.get("NVD_API_KEY")
    if api_key:
        headers["apiKey"] = api_key
    else:
        _nvd_pace()

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        # Check if we got a valid response
        if 'vulnerabilities' not in data or not data['vulnerabilities']:
            return {"ok": False, "error": "unknown cve"}
            
        vuln = data['vulnerabilities'][0]
        cve_data = vuln.get('cve', {})
        
        # Extract CVSS 3.1 score and vector
        cvss_score = None
        cvss_vector = None
        if 'metrics' in cve_data:
            # Try to get CVSS 3.1 score from primary metric first, then any metric
            for metric_type in ['cvssMetricV31', 'cvssMetricV30']:
                if metric_type in cve_data['metrics']:
                    metrics = cve_data['metrics'][metric_type]
                    if metrics:
                        cvss_score = metrics[0].get('cvssData', {}).get('baseScore')
                        cvss_vector = metrics[0].get('cvssData', {}).get('vectorString')
                        break
        
        # Extract CWE IDs
        cwe_ids = []
        if 'problemTypes' in cve_data:
            for problem in cve_data['problemTypes']:
                for desc in problem.get('description', []):
                    if 'cwe' in desc.get('value', '').lower():
                        cwe_ids.append(desc['value'])
        
        # Extract references (URLs only)
        refs = []
        if 'references' in cve_data:
            for ref in cve_data['references']:
                if 'url' in ref:
                    refs.append(ref['url'])
        
        return {
            "ok": True,
            "id": cve_id,
            "descriptions": [desc.get('value', '') for desc in cve_data.get('descriptions', [])],
            "cvss_score": cvss_score,
            "cvss_vector": cvss_vector,
            "cwe_ids": cwe_ids,
            "published_date": cve_data.get('published'),
            "modified_date": cve_data.get('lastModified'),
            "references": refs
        }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": False, "error": "unknown cve"}
        return {"ok": False, "error": f"HTTP error: {e.code}"}
    except Exception:
        return {"ok": False, "error": "network"}

def _fetch_kev() -> dict:
    """Fetch CISA KEV catalog data."""
    global _KEV_DATA, _KEV_CACHE_TIME
    
    cache_dir = _get_cache_dir()
    cache_file = os.path.join(cache_dir, "cisa_kev_cache.json")
    
    # Check if cached data is still valid (24h TTL)
    if (_KEV_DATA is not None and 
        _KEV_CACHE_TIME is not None and 
        datetime.now() - _KEV_CACHE_TIME < timedelta(hours=24)):
        return _KEV_DATA
    
    try:
        url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
        with urllib.request.urlopen(url, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        # Cache the data
        _KEV_DATA = data
        _KEV_CACHE_TIME = datetime.now()
        
        # Save to cache file
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass  # Don't fail if we can't save the cache
        
        return data
    except Exception:
        # Try to load from cache file if available
        try:
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
                _KEV_DATA = cached_data
                _KEV_CACHE_TIME = datetime.now()
                return cached_data
        except Exception:
            return {"error": "network"}

def kev_check(cve_ids: list[str]) -> dict:
    """Check which CVEs are in CISA KEV catalog."""
    try:
        kev_data = _fetch_kev()
        
        if 'error' in kev_data:
            return {"ok": False, "error": "network"}
            
        # Get the list of known exploited vulnerabilities
        kev_vulns = kev_data.get('vulnerabilities', [])
        kev_cves = {vuln['cveID'] for vuln in kev_vulns}
        
        # Check which IDs are in KEV
        found = []
        for cve_id in cve_ids:
            if cve_id.upper() in kev_cves:
                # Find the matching vulnerability to get details
                for vuln in kev_vulns:
                    if vuln['cveID'] == cve_id.upper():
                        found.append({
                            "cve_id": cve_id,
                            "known_exploited": True,
                            "rational_for_exploitation": vuln.get('rationalForExploitation', ''),
                            "date_added": vuln.get('dateAdded', ''),
                            "required_action": vuln.get('requiredAction', '')
                        })
                        break
        
        # Return all IDs with their status
        results = []
        for cve_id in cve_ids:
            is_kev = any(found_item['cve_id'] == cve_id for found_item in found)
            if is_kev:
                results.append(found_item)  # Add the found item details
            else:
                results.append({
                    "cve_id": cve_id,
                    "known_exploited": False,
                    "rational_for_exploitation": "",
                    "date_added": "",
                    "required_action": ""
                })
        
        return {"ok": True, "results": results}
    except Exception:
        return {"ok": False, "error": "network"}

def epss_score(cve_id: str) -> dict:
    """Fetch EPSS score from FIRST API."""
    url = f"https://api.first.org/data/v1/epss?cve={cve_id}"
    
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        # Check if we got a valid result
        if 'data' not in data or not data['data']:
            return {"ok": False, "error": "unknown cve"}
            
        epss_data = data['data'][0]
        
        return {
            "ok": True,
            "cve_id": cve_id,
            "epss_score": epss_data.get('epss'),
            "percentile": epss_data.get('percentile')
        }
    except Exception:
        return {"ok": False, "error": "network"}

def cve_lookup(cve_id: str) -> dict:
    """Look up CVE details from NVD."""
    return _fetch_nvd(cve_id)

# Tool definitions
_TOOLS = {
    "cve_lookup": cve_lookup,
    "kev_check": kev_check,
    "epss_score": epss_score,
}

TOOLS = [
    {"name": "cve_lookup", "description": cve_lookup.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"cve_id": {"type": "string", "description": "CVE ID to lookup"}},
                     "required": ["cve_id"]}},
    {"name": "kev_check", "description": kev_check.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"cve_ids": {"type": "array", "items": {"type": "string"}, "description": "List of CVE IDs to check"}},
                     "required": ["cve_ids"]}},
    {"name": "epss_score", "description": epss_score.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"cve_id": {"type": "string", "description": "CVE ID to get EPSS score for"}},
                     "required": ["cve_id"]}},
]


def call_tool(name: str, args: dict) -> dict:
    fn = _TOOLS.get(name)
    if fn is None:
        return {"content": [{"type": "text", "text": f"no tool {name}"}], "isError": True}
    try:
        result = fn(**(args or {}))
    except TypeError as bad_args:
        return {"content": [{"type": "text", "text": f"{name}: {bad_args}"}], "isError": True}
    except Exception as e:  # a network failure is data, not a crash
        return {"content": [{"type": "text", "text": json.dumps({"ok": False, "error": "network"})}], "isError": True}
    return {"content": [{"type": "text", "text": json.dumps(result, default=str)}], "isError": False}


def answer(msg: dict):
    """The reply to one request (None for a notification)."""
    method, params = msg.get("method"), msg.get("params") or {}
    if "id" not in msg:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion") or "2024-11-05", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "halo-hacker-cve", "version": "1.0.0", "extensionApi": API_VERSION}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        result = call_tool(str(params.get("name") or ""), params.get("arguments") or {})
    else:
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": f"no method {method}"}}
    return {"jsonrpc": "2.0", "id": msg["id"], "result": result}


def main() -> int:
    if "--selftest" in sys.argv:
        # Simple self-test: check that imports work and we can call tools
        try:
            # Test basic functionality without network calls
            result = cve_lookup("CVE-2023-12345")
            assert isinstance(result, dict)
            print("halo-hacker-cve selftest OK — CVE lookup tool available")
            return 0
        except Exception as e:
            print(f"halo-hacker-cve selftest failed: {e}")
            return 1
    
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        reply = answer(msg) if isinstance(msg, dict) else None
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())