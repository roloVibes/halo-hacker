# Halo Hacker: what a part needs

One line per part of the pack, and what it needs to run. A harness that does not have a line's requirements skips
that part; nothing here installs anything.

- `mcp:ingest` (knowledge ingestion) -- python; a vault path in the pack's config (`packs.settings.halo-hacker.vault`)
  or the `HALO_HACKER_VAULT` env var. Refuses every tool when the vault is unset.
- `mcp:cve` (CVE enrichment) -- python; outbound HTTPS to the NVD 2.0, CISA KEV and FIRST EPSS endpoints. Read-only,
  fail-never; a lookup that cannot reach the network says so instead of inventing a score.
- the eight bios and five lineups -- nothing beyond a model. Every bio is `default` (model-agnostic) on purpose: a
  pack never pins a vendor.
- `hooks/hooks.json` (the scope guard) -- python; `bash` and `hooks` grants. Classifies a Bash command against the
  active engagement's scope and refuses outside it.
- `tools/` (findings store, engage, reporting, normalizers, MITRE) -- python standard library only.
- `studio/findings.js` (the findings browser) -- the `studio-script` grant.
- `schemas/`, `playbooks/` -- data files, read by the tools and the bios. Nothing to install.
