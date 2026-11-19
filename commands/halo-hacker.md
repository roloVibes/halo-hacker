---
description: "Halo Hacker: what the pack is, its commands and lineups -- and its default action"
argument-hint: "[what to do]"
---
This is the Halo Hacker pack (halo-hacker 1.0.0): Authorized security assessment -- 40 single-responsibility
methodology agent templates you compose into a testing team, pre-built workflows, live proxy traffic analysis,
multi-project tracking, attack-path mapping, and an evidence-driven finding lifecycle with independent validation
and judging.

What it brings:
- command /halo-hacker:hh -- Engage, check status, or disengage the active assessment (scope as data: one state file, fail-closed inside the test window)
- command /halo-hacker:hh-report -- Generate a leadership email or full report from confirmed findings
- command /halo-hacker:hh-bounty -- Bug bounty operations: sync HackerOne data, review AI-vetted intents, submit confirmed findings, retest resolved reports
- command /halo-hacker:projects -- List, create, switch, or archive bug bounty programs (multi-project tracking)
- command /halo-hacker:communicate -- Turn a confirmed finding into stakeholder-ready communication (SANS reader-model)
- command /halo-hacker:hh-export -- Export the engagement's evidence ledger as a portable telemetry bundle (actions, sessions, manifest, verification recipe)
- workflow halo-hacker/hh-web-app-assessment -- recon → discovery → auth → injection → logic → validate → judge
- workflow halo-hacker/hh-api-security-review -- discovery → auth → API testing → advanced → validate → judge
- workflow halo-hacker/hh-ai-security-review -- discovery → four AI lanes → validate → judge
- workflow halo-hacker/hh-bug-bounty-hunt -- lightweight recon + high-ROI tests + always-on traffic analysis
- workflow halo-hacker/hh-pack-dev -- research → code → triple review → validate → final judge
- 40 methodology agent templates -- single-responsibility testers (recon/auth/injection/logic/API/AI/infra/review), compose them with the Builder
- lineup halo-hacker--hh-web-app-assessment -- Orchestrator, recon, web tester, validator, judge and reporter for a web application assessment
- lineup halo-hacker--hh-api-security-review -- The same shape for an API surface
- lineup halo-hacker--hh-ai-security-review -- AI/LLM surface review (prompt injection, tool abuse, data exposure)
- lineup halo-hacker--hh-cloud-config-assessment -- Cloud configuration and posture review
- lineup halo-hacker--hh-finding-validation-reporting -- Independent validation and reporting only, over findings another lineup produced
- skill halo-hacker:communicate-findings -- The baked-in reporting doctrine: reader model, ten rules, the four questions, the leadership-email and full-report shapes
- skill halo-hacker:attack-flow -- Per-finding ATT&CK/ATLAS mapping, the engagement narrative and a Navigator layer
- MCP server ingest -- knowledge ingestion into the provenance-ledger KB (local notes, PDFs, GitHub files, YouTube subtitles)
- MCP server cve -- NVD 2.0 lookup, CISA KEV checks and FIRST EPSS scores
- MCP server traffic -- real-time proxy traffic analysis (Caido/Burp) with correlation suggestions

If the request below is empty, show the user the list above, one line each, and stop. Otherwise: engage the
assessment first (the `/halo-hacker:hh` command, which needs the engagement root and refuses outside its window),
then run the lineup that matches the surface named in the request -- tell the user which lineup you picked, why,
and stop for their confirmation before anything active runs. A finding is never `confirmed` without independent
reproduction and a reviewer decision citing evidence.

Request: $ARGUMENTS
