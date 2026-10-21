# INTEGRATION_STATUS.md

No external tool integrations ship at 0.1.0 (Milestone 3+). Planned,
in priority order per the pack spec:

| Tool | Kind | Status | Notes |
|---|---|---|---|
| Caido | HTTP history / site map / evidence | planned (M3) | prefer a documented MCP; custom adapter only for missing functionality; this Mac runs Caido (Burp is on the work computer) |
| Nuclei | template scanning | planned (M3) | ingest + normalize results; no engine re-creation |
| Semgrep | static analysis | planned (M3) | same |
| Garak / PyRIT | AI security evaluation | planned (M3+) | authorized test environments only |
| Obsidian knowledge | methodology retrieval | planned (M3) | BRIDGES the existing halo-hacker ingestion engine (`ingest/` in this repo) — no second pipeline; unverified notes are leads, never findings |
| PlexTrac / HackerOne / Jira | report destinations | planned (M4+) | external publishing behind explicit human review, always |

Rule: every integration is optional — a missing tool never blocks
unrelated workflows.
