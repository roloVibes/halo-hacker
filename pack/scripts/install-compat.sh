#!/usr/bin/env bash
# TEMPORARY COMPATIBILITY ADAPTER (pre-3.2.0.0) -- see CORE_REQUESTS.md CR-1.
#
# The Halo pack registry (`halo pack install`) does not exist in any
# released Halo yet. Until it does, this adapter installs the Halo Hacker
# pack's bios and team templates through the STABLE, documented user
# directories (~/.halo/agents/, ~/.halo/teams/), which `halo agents`,
# `halo teams`, the wizard's Team step and Studio Roles all read natively.
# It patches nothing in Halo and writes only hh-* files it owns.
set -euo pipefail

PACK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS_DIR="${HOME}/.halo/agents"
TEAMS_DIR="${HOME}/.halo/teams"
FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

echo "Halo Hacker pack -- compatibility install (pre-3.2.0.0 adapter)"
echo "pack root: ${PACK_ROOT}"

# Validate first: a broken pack never installs.
run_validator() {
  if command -v uv >/dev/null 2>&1; then
    uv run --python 3.12 --with pyyaml --with jsonschema python "${PACK_ROOT}/tools/validate_pack.py"
  else
    python3 "${PACK_ROOT}/tools/validate_pack.py"
  fi
}
run_validator || {
  echo "REFUSED: pack failed validation (needs python3+PyYAML, or uv on PATH)"; exit 1; }

installed=0
refused=0
mkdir -p "${AGENTS_DIR}" "${TEAMS_DIR}"

for f in "${PACK_ROOT}"/agents/*.yaml; do
  dest="${AGENTS_DIR}/$(basename "$f")"
  if [[ -e "${dest}" && ${FORCE} -ne 1 ]]; then
    echo "SKIP (exists, user-modified?): ${dest}  (--force to overwrite)"
    refused=$((refused+1))
  else
    cp "$f" "${dest}"
    echo "installed bio:  ${dest}"
    installed=$((installed+1))
  fi
done
for f in "${PACK_ROOT}"/teams/*.yaml; do
  dest="${TEAMS_DIR}/$(basename "$f")"
  if [[ -e "${dest}" && ${FORCE} -ne 1 ]]; then
    echo "SKIP (exists, user-modified?): ${dest}  (--force to overwrite)"
    refused=$((refused+1))
  else
    cp "$f" "${dest}"
    echo "installed team: ${dest}"
    installed=$((installed+1))
  fi
done

echo
echo "done: ${installed} installed, ${refused} skipped."
echo "activate a lineup with:  halo teams use hh-web-app-assessment"
echo "remove everything with:  ${PACK_ROOT}/scripts/uninstall-compat.sh"
