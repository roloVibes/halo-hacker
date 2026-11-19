---
description: Export the active engagement's evidence ledger as a portable telemetry bundle (actions, sessions, manifest, verification recipe).
argument-hint: "<engagement-root> [--out DIR] [--zip] [--run-id ID]"
---

# /hh telemetry-export

Render the engagement's hash-chained evidence ledger as a portable telemetry
bundle — for programs and competitions that ask for the full record of what
the tester did, not just the findings.

Run the pack's own tool (never reassemble the bundle by hand — the manifest's
file hashes and chain verification must match the bytes on disk):

```
python "${CLAUDE_PLUGIN_ROOT}/tools/telemetry_export.py" <engagement-root> [--out DIR] [--zip] [--run-id ID]
```

The bundle under the output directory:

- `manifest.json` — run id, counts, ledger head hash, chain-verification result, sha256 of every bundle file
- `actions.jsonl` — one row per ledger row: UTC timestamp, per-run correlation id, actor, action, artifact hash, chain hashes
- `sessions.jsonl` — contiguous same-actor runs grouped as sessions
- `summary.md` — the human-readable one-pager
- `capture-setup.md` — the capture model and the third-party verification recipe

`--zip` also writes `<out>.zip` and prints its sha256. The chain is verified
at export time and the result is written into the manifest — a bundle that
reports a broken chain is valid output; never edit bundle files after export,
and never present a bundle whose `chain_intact` is false as clean. Print the
tool's JSON output to the user as-is.
