# studio/

The pack's Studio contribution is declared in `pack.yaml` under
`contributes.studio` (stable since Halo 3.2.0.0 R3 — the pack contribution
registry):

- **`findings.js`** — the findings browser, a `bundle` panel (an ES module
  exporting `mount(el, api)`) that runs in the Studio page once the
  `studio-script` permission is granted
  (`halo pack enable halo-hacker --grant studio-script`, or the Grant
  toggle in Studio's Packs section). It renders the findings list with
  filters/search, and every finding is clickable — full detail view with
  evidence ledger rows, validation, reviewer decision, remediation and
  audit history, plus copy-as-markdown and open-raw-JSON. It refreshes on
  `hh.finding` events (SSE `/api/events`) and every 15 s.

  Constraints it lives within (the shell's CSP): no inline styles (all
  styling via CSSOM `el.style.*`), no `innerHTML` with markup, no external
  resources, untrusted finding fields only ever flow into `textContent`.
  The token comes from `sessionStorage["halo-studio-token"]` (bearer
  header); header-less `EventSource` uses `?t=`.

- The **counts / table / feed** panels are declared in `pack.yaml` too and
  drawn by Studio's own components; they read the pack data folder
  (`~/.halo/packs/.data/halo-hacker/findings/`), written by
  `tools/findings_view.py` — on every store change (attach hook), or on
  demand: `python tools/findings_view.py auto`.

Before Halo 3.2.0.0 R3 this folder was empty by design (the contribution
registry did not exist); that note is obsolete.
