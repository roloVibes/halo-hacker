#!/usr/bin/env python3
"""CVSS 3.1 scoring module (FIRST CVSS v3.1 spec).

Implements the CVSS v3.1 base score calculation according to the FIRST
specification (https://www.first.org/cvss/v3.1/spec), stdlib-only by pack
convention.
"""

from __future__ import annotations

import re
from typing import Dict, List


def parse_vector(vector: str) -> dict:
    """Parse a CVSS 3.1 vector string and validate all metrics.
    
    Args:
        vector: CVSS 3.1 vector string (e.g. "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
        
    Returns:
        dict with all parsed metrics
        
    Raises:
        ValueError: If any metric is invalid or missing
    """
    if not vector.startswith("CVSS:3.1/"):
        raise ValueError("Invalid CVSS vector format")
    
    # Parse the vector into components
    components = vector[8:].split("/")
    metrics = {}
    
    for component in components:
        if not component:  # Skip empty components
            continue
        if ":" not in component:
            raise ValueError(f"Invalid metric format: {component}")
        key, value = component.split(":", 1)
        metrics[key] = value
    
    # Validate all required metrics
    required_metrics = ["AV", "AC", "PR", "UI", "S", "C", "I", "A"]
    for metric in required_metrics:
        if metric not in metrics:
            raise ValueError(f"Missing required metric: {metric}")
    
    # Validate each metric value
    av_values = {"N": 1.0, "A": 0.62, "L": 0.68, "P": 0.35}
    ac_values = {"L": 0.77, "H": 0.44}
    pr_values = {"N": 0.85, "L": 0.62, "H": 0.27}
    ui_values = {"N": 0.85, "R": 0.62}
    s_values = {"U": 1.0, "C": 1.0}  # Scope unchanged or changed
    c_values = {"N": 0.0, "L": 0.22, "H": 0.56}
    i_values = {"N": 0.0, "L": 0.22, "H": 0.56}
    a_values = {"N": 0.0, "L": 0.22, "H": 0.56}
    
    # Validate AV (Attack Vector)
    av = metrics["AV"]
    if av not in av_values:
        raise ValueError(f"Invalid AV value: {av}")
    
    # Validate AC (Attack Complexity)
    ac = metrics["AC"]
    if ac not in ac_values:
        raise ValueError(f"Invalid AC value: {ac}")
    
    # Validate PR (Privileges Required)
    pr = metrics["PR"]
    if pr not in pr_values:
        raise ValueError(f"Invalid PR value: {pr}")
    
    # Validate UI (User Interaction)
    ui = metrics["UI"]
    if ui not in ui_values:
        raise ValueError(f"Invalid UI value: {ui}")
    
    # Validate S (Scope)
    s = metrics["S"]
    if s not in s_values:
        raise ValueError(f"Invalid S value: {s}")
    
    # Validate C (Confidentiality)
    c = metrics["C"]
    if c not in c_values:
        raise ValueError(f"Invalid C value: {c}")
    
    # Validate I (Integrity)
    i = metrics["I"]
    if i not in i_values:
        raise ValueError(f"Invalid I value: {i}")
    
    # Validate A (Availability)
    a = metrics["A"]
    if a not in a_values:
        raise ValueError(f"Invalid A value: {a}")
    
    return {
        "AV": av,
        "AC": ac,
        "PR": pr,
        "UI": ui,
        "S": s,
        "C": c,
        "I": i,
        "A": a
    }



# --- FIRST CVSS v3.1 Specification constants (section 7.1 / Appendix A) ---
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
_AC = {"L": 0.77, "H": 0.44}
_PR_UNCHANGED = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_CHANGED = {"N": 0.85, "L": 0.68, "H": 0.5}
_UI = {"N": 0.85, "R": 0.62}
_CIA = {"H": 0.56, "L": 0.22, "N": 0.0}


def _roundup(value: float) -> float:
    """The spec's Roundup: smallest 1-decimal number >= value, with the
    spec's floating-point guard (spec section 7.1)."""
    int_input = round(value * 100000)
    if int_input % 10000 == 0:
        return int_input / 100000.0
    import math
    return (math.floor(int_input / 10000) + 1) / 10.0


def _scores(parsed: dict) -> "tuple[float, float, float]":
    """(exploitability, impact, base) per the spec formulas."""
    scope_changed = parsed["S"] == "C"
    pr = (_PR_CHANGED if scope_changed else _PR_UNCHANGED)[parsed["PR"]]
    exploitability = 8.22 * _AV[parsed["AV"]] * _AC[parsed["AC"]] * pr * _UI[parsed["UI"]]
    isc = 1 - ((1 - _CIA[parsed["C"]]) * (1 - _CIA[parsed["I"]]) * (1 - _CIA[parsed["A"]]))
    if scope_changed:
        impact = 7.52 * (isc - 0.029) - 3.25 * (isc - 0.02) ** 15  # v3.1's ^15 curve (3.0 was linear)
    else:
        impact = 6.42 * isc
    if impact <= 0:
        return exploitability, impact, 0.0
    total = impact + exploitability
    if scope_changed:
        total = 1.08 * total
    return exploitability, impact, _roundup(min(total, 10.0))


def base_score(vector: str) -> float:
    """Calculate the CVSS 3.1 base score for a vector.
    
    Args:
        vector: CVSS 3.1 vector string
        
    Returns:
        Base score as float rounded to one decimal place
    """
    parsed = parse_vector(vector)
    _e, _i, base = _scores(parsed)
    return base


def severity(score: float) -> str:
    """Convert a CVSS score to its severity level.
    
    Args:
        score: CVSS base score
        
    Returns:
        Severity level (None, Low, Medium, High, Critical)
    """
    if score == 0.0:
        return "None"
    elif 0.1 <= score <= 3.9:
        return "Low"
    elif 4.0 <= score <= 6.9:
        return "Medium"
    elif 7.0 <= score <= 8.9:
        return "High"
    elif 9.0 <= score <= 10.0:
        return "Critical"
    else:
        raise ValueError(f"Invalid CVSS score: {score}")


def score_vector(vector: str) -> dict:
    """Calculate all scores and metrics for a vector in one call.
    
    Args:
        vector: CVSS 3.1 vector string
        
    Returns:
        dict with score, severity, exploitability, impact, and metrics
    """
    parsed = parse_vector(vector)
    
    # Get metric values
    av = parsed["AV"]
    ac = parsed["AC"]
    pr = parsed["PR"]
    ui = parsed["UI"]
    s = parsed["S"]
    c = parsed["C"]
    i = parsed["I"]
    a = parsed["A"]
    
    # Base scores (from CVSS v3.1 specification)
    av_values = {"N": 1.0, "A": 0.62, "L": 0.68, "P": 0.35}
    ac_values = {"L": 0.77, "H": 0.44}
    pr_values = {"N": 0.85, "L": 0.62, "H": 0.27}
    ui_values = {"N": 0.85, "R": 0.62}
    c_values = {"N": 0.0, "L": 0.22, "H": 0.56}
    i_values = {"N": 0.0, "L": 0.22, "H": 0.56}
    a_values = {"N": 0.0, "L": 0.22, "H": 0.56}
    
    _e, _i, base = _scores(parsed)
    return {
        "score": base,
        "severity": severity(base),
        "exploitability": round(_e, 1),
        "impact": round(_i, 1),
        "metrics": parsed
    }


if __name__ == "__main__":
    import sys
    import json
    
    for vector in sys.argv[1:]:
        try:
            result = score_vector(vector)
            print(json.dumps(result))
        except Exception as e:
            print(json.dumps({"error": str(e), "vector": vector}))
    sys.exit(0)