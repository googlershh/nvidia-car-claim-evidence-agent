#!/usr/bin/env bash
# Install the `claim-evidence` skill and the tool code it calls into the NemoClaw sandbox.
# Run ON THE INSTANCE from the synced repo root, after 02_connect_nemoclaw_vss.sh.
# Uploads only code, reference tables and the small run-time files (no photos/videos: video goes through VSS).
set -euo pipefail
SANDBOX="${1:-demo}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export XDG_RUNTIME_DIR="/run/user/$(id -u)" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"
export NVM_DIR="$HOME/.nvm"; [[ -s "$NVM_DIR/nvm.sh" ]] && source "$NVM_DIR/nvm.sh" >/dev/null
export PATH="$HOME/.local/bin:$PATH"
X=(openshell sandbox exec --name "$SANDBOX" --timeout 120 --)

STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
cd "$ROOT"
tar -cf "$STAGE/claim.tar" --exclude='__pycache__' --exclude='*.pyc' agent aihub data/reference \
    data/interim/accident_codes.csv data/interim/eval_fault_reviewed.csv data/interim/synth_cases.jsonl \
    data/interim/statements.jsonl data/interim/knia/charts.json skills/claim-evidence
echo "bundle $(du -h "$STAGE/claim.tar" | cut -f1)"

# openshell exec reads stdin; always detach it inside scripts (P8)
openshell sandbox upload "$SANDBOX" "$STAGE/claim.tar" /tmp/ </dev/null
"${X[@]}" sh -lc 'set -e; mkdir -p /sandbox/claim && tar -xf /tmp/claim.tar -C /sandbox/claim && rm /tmp/claim.tar
  mkdir -p /sandbox/.openclaw/workspace/skills/claim-evidence
  cp /sandbox/claim/skills/claim-evidence/SKILL.md /sandbox/.openclaw/workspace/skills/claim-evidence/SKILL.md
  cd /sandbox/claim && python3 -m agent.cli cases | head -12' </dev/null
"${X[@]}" sh -lc 'openclaw skills list 2>&1 | grep -i -E "claim-evidence|vss-ask" | head -5' </dev/null
