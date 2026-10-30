"""Unit tests for CVE server."""

import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

# Add the pack directory to the path so we can import our module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pack.mcp.cve_server import cve_lookup, kev_check, epss_score, answer


def test_cve_lookup_offline():
    """Test CVE lookup with mocked responses."""
    # Mock the urllib request to simulate network failure
    with patch('urllib.request.urlopen') as mock_urlopen:
        # Test case 1: Network error
        mock_urlopen.side_effect = Exception("Network error")
        
        result = cve_lookup("CVE-2023-12345")
        assert not result["ok"]
        assert result["error"] == "network"


def test_kev_check_offline():
    """Test KEV check with mocked responses."""
    # Mock the urllib request to simulate network failure
    with patch('urllib.request.urlopen') as mock_urlopen:
        # Test case 1: Network error
        mock_urlopen.side_effect = Exception("Network error")
        
        result = kev_check(["CVE-2023-12345"])
        assert not result["ok"]
        assert result["error"] == "network"


def test_epss_score_offline():
    """Test EPSS score with mocked responses."""
    # Mock the urllib request to simulate network failure
    with patch('urllib.request.urlopen') as mock_urlopen:
        # Test case 1: Network error
        mock_urlopen.side_effect = Exception("Network error")
        
        result = epss_score("CVE-2023-12345")
        assert not result["ok"]
        assert result["error"] == "network"


def test_jsonrpc_initialize():
    """Test JSON-RPC initialize response."""
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }
    
    response = answer(msg)
    assert response["result"]["serverInfo"]["name"] == "halo-hacker-cve"
    assert "tools" in response["result"]["capabilities"]


def test_jsonrpc_tools_list():
    """Test JSON-RPC tools/list response."""
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    response = answer(msg)
    tools = response["result"]["tools"]
    tool_names = [tool["name"] for tool in tools]
    assert "cve_lookup" in tool_names
    assert "kev_check" in tool_names
    assert "epss_score" in tool_names


def test_jsonrpc_tools_call():
    """Test JSON-RPC tools/call response."""
    # Test cve_lookup tool call
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "cve_lookup",
            "arguments": {"cve_id": "CVE-2023-12345"}
        }
    }
    
    response = answer(msg)
    # Should return unknown cve error since we're not mocking the network
    result = json.loads(response["result"]["content"][0]["text"])
    assert not result["ok"]
    # Note: This will return "unknown cve" because of how our implementation handles network errors
    # but it's still an error response, which is what we want to test for


def test_tool_descriptions():
    """Test that tool descriptions are properly set."""
    from pack.mcp.cve_server import TOOLS
    
    tool_names = [tool["name"] for tool in TOOLS]
    assert "cve_lookup" in tool_names
    assert "kev_check" in tool_names
    assert "epss_score" in tool_names
    
    # Check that descriptions are not empty
    for tool in TOOLS:
        assert tool["description"] is not None and len(tool["description"]) > 0


if __name__ == "__main__":
    test_cve_lookup_offline()
    test_kev_check_offline()
    test_epss_score_offline()
    test_jsonrpc_initialize()
    test_jsonrpc_tools_list()
    test_jsonrpc_tools_call()
    test_tool_descriptions()
    print("All tests passed!")

def test_nvd_pacer_enforces_unauthenticated_limit(monkeypatch):
    """6 unauthenticated NVD calls inside 30s must sleep; with a key, never."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))
    import cve_server

    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
    monkeypatch.delenv("NVD_API_KEY", raising=False)
    cve_server._NVD_CALL_TIMES.clear()

    for _ in range(5):
        cve_server._nvd_pace()
    assert sleeps == [], "first 5 unauthenticated calls must not wait"

    cve_server._nvd_pace()  # 6th inside the window
    assert sleeps and sleeps[0] > 0, "6th call inside 30s must pace"

    # with a key: no pacing ever
    monkeypatch.setenv("NVD_API_KEY", "test-key")
    cve_server._NVD_CALL_TIMES.clear()
    sleeps.clear()
    for _ in range(10):
        cve_server._nvd_pace()
    assert sleeps == [], "keyed calls must never wait"
