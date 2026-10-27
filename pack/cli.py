"""halo-hacker CLI — the headless/degraded mode.

Same library as the MCP server, same guards. What it LACKS is halo's pillar-1
rerouting: if the local model filters or fails, this refuses and reports rather
than rerouting and filing. That asymmetry is deliberate — see PLAN.md.

Usage:
  python pack/cli.py notes  <dir>   [--dry-run] [--vault <path>]
  python pack/cli.py pdf    <file>  [--vault <path>]
  python pack/cli.py github <url>   [--vault <path>]
  python pack/cli.py youtube <url>  [--vault <path>]
  python pack/cli.py status         [--vault <path>]
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingest import tools


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    vault = None
    if "--vault" in args:
        i = args.index("--vault")
        vault = args[i + 1]
        del args[i:i + 2]
    if vault:
        os.environ["HALO_HACKER_VAULT"] = vault
    if os.environ.get("HALO_HACKER_HOSTED") == "1":
        print("WARNING: hosted distillation — user content will leave this machine.",
              file=sys.stderr)

    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    if cmd == "notes":
        if not args:
            print("notes needs a directory", file=sys.stderr)
            return 2
        report = tools.ingest_notes(args[0], dry_run=dry_run)
    elif cmd == "pdf":
        report = tools.ingest_pdf(args[0])
    elif cmd == "github":
        report = tools.ingest_github(args[0])
    elif cmd == "youtube":
        report = tools.ingest_youtube(args[0])
    elif cmd == "status":
        report = tools.ingest_status()
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        return 2

    print(json.dumps(report, indent=2))
    if not report.get("ok"):
        return 1
    # exit-code gate: errors mean non-zero even when other items filed
    return 1 if report.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())
