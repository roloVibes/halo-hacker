#!/usr/bin/env bash
# TEMPORARY COMPATIBILITY ADAPTER (pre-3.2.0.0) -- removes exactly the
# hh-* files the install adapter owns. User-modified copies are still
# hh-* files (same names), so --keep-modified compares content first:
# an unmodified pack file is removed, a modified one is kept and reported.
set -euo pipefail

PACK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS_DIR="${HOME}/.halo/agents"
TEAMS_DIR="${HOME}/.halo/teams"
KEEP_MODIFIED=1
[[ "${1:-}" == "--purge" ]] && KEEP_MODIFIED=0

removed=0
kept=0
for dir in "${AGENTS_DIR}" "${TEAMS_DIR}"; do
  subdir="$([[ "$dir" == *agents* ]] && echo agents || echo teams)"
  for f in "${dir}"/hh-*.yaml; do
    [[ -e "$f" ]] || continue
    src="${PACK_ROOT}/${subdir}/${f##*/}"
    if [[ ${KEEP_MODIFIED} -eq 1 && -f "${src}" ]] && ! cmp -s "$f" "${src}"; then
      echo "KEPT (modified by you): $f"
      kept=$((kept+1))
    else
      rm "$f"
      echo "removed: $f"
      removed=$((removed+1))
    fi
  done
done
echo "done: ${removed} removed, ${kept} kept. If a removed team was active, run: halo teams use standard"
