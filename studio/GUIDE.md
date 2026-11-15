# How Halo Hacker works

A step-by-step walkthrough of this section. Do these in order the first time.

## 1. Turn the pack on and grant its script

The pack installs **disabled**. The interactive panels on this page (the
findings browser, live dashboard, projects, ingest, attack paths) are the
pack's own scripts and only run once you grant `studio-script`:

```sh
halo pack enable halo-hacker --grant mcp:ingest --grant mcp:cve --grant bash --grant hooks --grant studio-script
```

Then **start a new Halo session** — packs load when a session starts, never
mid-session. Reopen this Studio section afterward.

## 2. Point the pack at a knowledge-base vault

Open **Settings & engagement** (the second panel). The first field, **vault**,
is the folder the pack writes its provenance ledger and distilled knowledge
into. **When it is empty the server refuses every tool** — set it first, e.g.
`/Users/you/halo-hacker-kb`. This folder is yours and lives outside the pack.

## 3. Describe the engagement

Further down the same form are the engagement fields: **objective**, **scope**
(in-scope targets and exclusions), **test_type**, **rules** of engagement,
**x_header** for traffic marking, and your **tester_name** / **tester_email**.
Fill these before you test — they stamp every finding and report.

## 4. Watch the work in Live

The **Live** panel shows every running agent session with status and working
directory, the live-lines feed, and traffic-watch status. If it says "Harness
not connected," no session is running yet.

## 5. Review what comes in

Findings land in the **Findings browser** — click any finding for its full
detail: description, evidence ledger rows, validation, reviewer decision,
remediation and audit history. **Counts**, **Findings table** and
**Lifecycle** summarize the same store. The review pipeline is: identified →
validated → reviewed → confirmed.

## 6. Juggle programs in Projects

Doing bug bounty across programs? **Projects** lists each program with
platform, finding count and state. Click one to switch — the whole cockpit
refreshes for that project. A fresh install shows "No projects yet"; that is
normal, not an error.

## 7. Read the attack surface

**Ingest** shows what you've fed the knowledge base (source types, trust
tiers, topic routing). **Attack paths** connects findings by the capabilities
they require and grant — demonstrated paths solid, projected dashed — mapped
to MITRE ATT&CK/ATLAS.

---

**Stuck?** Every panel's `?` (or the `...` menu → Help) explains that panel.
The full reference is in the pack's `README.md` and `HALO-PACK.md`.
