---
description: "Turn a confirmed finding into stakeholder-ready communication (SANS reader-model)"
argument-hint: "<finding-id> [audience: leadership|technical|client|hackerone]"
---

# /communicate -- SANS-trained finding communication

A finding is only worth communicating once it is **confirmed** (independent reproduction + judge decision). This
command turns one confirmed finding into the right communication for its audience, using the pack's baked-in
reporting doctrine (`skills/communicate-findings.md`): the reader model, the ten rules, and the four questions.

Run the subcommand in `$ARGUMENTS` through the pack's own tool (never reimplement its checks in prose):

- `<finding-id>` -- the confirmed finding to communicate. Read its full document from the findings store first;
  refuse with the reason if it is not confirmed.
- `audience` (optional) -- one of:
  - `leadership` -- executive summary + business impact in the 5-part email shape (bottom line, impact, what we
    found, what they should do, next steps).
  - `technical` -- full reproduction, evidence ledger refs, and remediation.
  - `client` -- third-party vendor/engagement format.
  - `hackerone` -- a disclosure draft ready for the HackerOne API (JSON), with the finding's title, weakness,
    severity, and reproduction.

Command:

```
python "${CLAUDE_PLUGIN_ROOT}/reporting/leadership_email.py" <finding-id> <audience>
```

If `audience` is `full` or `technical`, use `reporting/full_report.py` instead. Print the rendered output to the
user as-is (it is the evidence), and never fabricate a finding that is not in the store. When the tool refuses (not
confirmed, unknown audience, or the finding is missing), say why and stop.