# INTEGRATION_STATUS.md

No external tool integrations ship at 0.1.0 (Milestone 3+). Planned,
in priority order per the pack spec:

| Tool | Kind | Status | Notes |
|---|---|---|---|
| Caido | HTTP history / site map / evidence | DRAFT (M3) | read-only adapter + sanitization fixture-pinned; LIVE transport not yet verified (no instance reachable at build time); documented MCP interface preferred (CORE_REQUESTS CR-6) |
| Nuclei | template scanning | SHIPPED (M3) | ingest + normalize results; no engine re-creation |
| Semgrep | static analysis | SHIPPED (M3) | same |
| Garak / PyRIT | AI security evaluation | planned (M3+) | authorized test environments only |
| Obsidian knowledge | methodology retrieval | planned (M3) | BRIDGES the existing halo-hacker ingestion engine (`ingest/` in this repo) — no second pipeline; unverified notes are leads, never findings |
| PlexTrac / HackerOne / Jira | report destinations | planned (M4+) | external publishing behind explicit human review, always |

Rule: every integration is optional — a missing tool never blocks
unrelated workflows.
