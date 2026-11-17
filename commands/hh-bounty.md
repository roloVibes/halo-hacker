---
description: "Bug bounty operations: sync HackerOne data, review AI-vetted report intents, submit confirmed findings, retest resolved reports"
argument-hint: "sync | intents | submit <finding_id> <program_handle> | retest <report_id> | status"
---

# /hh-bounty -- bug bounty operations (HackerOne)

One-stop shop for tracking, testing, analyzing, and submitting HackerOne reports.
Syncs your live H1 data into the pack data dir, surfaces what changed, and
drives the AI-reviewed submission pipeline.

Run the subcommand in `$ARGUMENTS`. The sync and status subcommands call the
pack's own tools; submit/retest route to the hh-bounty-submit agent.

- `sync` -- pull fresh data from the HackerOne API (reports, programs, earnings,
  intents) and write normalized files under the pack data dir `h1/`. Detects
  state/activity changes and emits an `hh.h1.update` event.
- `intents` -- list your report intents with AI job status; flag any with failed
  jobs or `ready_to_submit` state.
- `submit <finding_id> <program_handle>` -- run the hh-bounty-submit agent on a
  confirmed finding: draft -> AI review (report intent) -> your approval -> submit.
- `retest <report_id>` -- pull the report, extract the reproduction steps, and
  re-run them against the same scope; record the outcome in the evidence ledger.
- `status` -- summary counts (reports by state, programs, earnings, intents) and
  the last sync time.

Commands:

```
python "${CLAUDE_PLUGIN_ROOT}/tools/h1_sync.py" sync
python "${CLAUDE_PLUGIN_ROOT}/tools/h1_sync.py" status
```

For `submit` and `retest`, use the hh-bounty-submit agent (it has the h1 MCP
tools and the communicate-findings skill).

Print the tool's JSON output as-is (it is the evidence). When no subcommand is
given, default to `status`. Never submit a report without showing the human the
AI analysis and getting an explicit "submit".
