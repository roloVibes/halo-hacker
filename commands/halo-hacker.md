---
description: "Halo Hacker: what the pack is, its commands and lineups -- and its default action"
argument-hint: "[what to do]"
---
This is the Halo Hacker pack (halo-hacker 0.9.0): Authorized security assessment -- specialized agent roles,
assessment team lineups, structured playbooks, engagement scope policy, finding schemas, and evidence-driven
reporting.

What it brings:
- command /halo-hacker:hh -- Engage, check status, or disengage the active assessment (scope as data: one state file, fail-closed inside the test window)
- command /halo-hacker:hh-report -- Generate a leadership email or full report from confirmed findings
- lineup halo-hacker--hh-web-app-assessment -- Orchestrator, recon, web tester, validator, judge and reporter for a web application assessment
- lineup halo-hacker--hh-api-security-review -- The same shape for an API surface
- lineup halo-hacker--hh-ai-security-review -- AI/LLM surface review (prompt injection, tool abuse, data exposure)
- lineup halo-hacker--hh-cloud-config-assessment -- Cloud configuration and posture review
- lineup halo-hacker--hh-finding-validation-reporting -- Independent validation and reporting only, over findings another lineup produced
- skill halo-hacker:communicate-findings -- The baked-in reporting doctrine: reader model, ten rules, the four questions, the leadership-email and full-report shapes
- skill halo-hacker:attack-flow -- Per-finding ATT&CK/ATLAS mapping, the engagement narrative and a Navigator layer
- MCP server ingest -- knowledge ingestion into the provenance-ledger KB (local notes, PDFs, GitHub files, YouTube subtitles)
- MCP server cve -- NVD 2.0 lookup, CISA KEV checks and FIRST EPSS scores

If the request below is empty, show the user the list above, one line each, and stop. Otherwise: engage the
assessment first (the `/halo-hacker:hh` command, which needs the engagement root and refuses outside its window),
then run the lineup that matches the surface named in the request -- tell the user which lineup you picked, why,
and stop for their confirmation before anything active runs. A finding is never `confirmed` without independent
reproduction and a reviewer decision citing evidence.

Request: $ARGUMENTS
