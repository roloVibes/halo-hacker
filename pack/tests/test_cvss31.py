"""CVSS 3.1 scoring tests.

Tests the cvss31 module against official CVSS v3.1 specification ground truth values.
"""
import pytest
from pack.tools.cvss31 import parse_vector, base_score, severity, score_vector


def test_parse_vector_valid():
    """Test parsing valid vectors."""
    vector = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    result = parse_vector(vector)
    assert result["AV"] == "N"
    assert result["AC"] == "L"
    assert result["PR"] == "N"
    assert result["UI"] == "N"
    assert result["S"] == "U"
    assert result["C"] == "H"
    assert result["I"] == "H"
    assert result["A"] == "H"


def test_parse_vector_invalid_format():
    """Test parsing invalid vector format."""
    with pytest.raises(ValueError, match="Invalid CVSS vector format"):
        parse_vector("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")


def test_parse_vector_missing_metrics():
    """Test parsing vector with missing metrics."""
    with pytest.raises(ValueError, match="Missing required metric"):
        parse_vector("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H")


def test_parse_vector_invalid_metric_values():
    """Test parsing vector with invalid metric values."""
    with pytest.raises(ValueError, match="Invalid AV value"):
        parse_vector("CVSS:3.1/AV:X/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
    
    with pytest.raises(ValueError, match="Invalid AC value"):
        parse_vector("CVSS:3.1/AV:N/AC:X/PR:N/UI:N/S:U/C:H/I:H/A:H")


def test_base_score_official_ground_truth():
    """Test against official CVSS v3.1 specification ground truth values."""
    # Test case 1: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H → 9.8
    assert base_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == 9.8
    
    # Test case 2: CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H → 8.8
    assert base_score("CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H") == 8.8
    
    # Test case 3: scope changed branch. Authoritative value 7.2 — verified
    # against the `cvss` reference package (the earlier 7.1 expectation was
    # wrong; 7.1 belongs to AV:N/AC:H/PR:L/UI:R/S:C/C:L/I:L/A:H).
    assert base_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:L/I:L/A:N") == 7.2
    
    # Test case 4: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L → 5.3
    assert base_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L") == 5.3
    
    # Test case 5: authoritative value 1.8 (verified against the `cvss`
    # reference package).
    assert base_score("CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N") == 1.8


def test_severity_boundaries():
    """Test severity boundaries."""
    assert severity(0.0) == "None"
    assert severity(0.1) == "Low"
    assert severity(3.9) == "Low"
    assert severity(4.0) == "Medium"
    assert severity(6.9) == "Medium"
    assert severity(7.0) == "High"
    assert severity(8.9) == "High"
    assert severity(9.0) == "Critical"
    assert severity(10.0) == "Critical"


def test_score_vector():
    """Test score_vector function with ground truth."""
    # Test the first official case
    result = score_vector("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
    assert result["score"] == 9.8
    assert result["severity"] == "Critical"
    
    # Test the scope changed case
    result = score_vector("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:L/I:L/A:N")
    assert result["score"] == 7.2
    assert result["severity"] == "High"


def test_roundtrip_parse():
    """Test that parse and score work together."""
    vector = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    parsed = parse_vector(vector)
    scored = base_score(vector)
    
    # Basic sanity check
    assert 0.0 <= scored <= 10.0
    assert isinstance(scored, float)
    assert isinstance(parsed, dict)