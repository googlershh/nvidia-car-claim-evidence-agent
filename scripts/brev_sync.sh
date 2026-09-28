#!/usr/bin/env bash
# Copy the code and the run-time data to a Brev instance (run inside WSL after `brev login`).
#   bash scripts/brev_sync.sh [instance]          push this repo -> ~/car-accident-model on the instance
#   bash scripts/brev_sync.sh [instance] --pull   bring back eval results (data/interim/eval/)
# The instance name is an SSH host alias written by `brev refresh`.
set -euo pipefail

INSTANCE="${1:-claim-agent-a6000}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="car-accident-model"

"$HOME/.local/bin/brev" refresh >/dev/null

if [[ "${2:-}" == "--pull" ]]; then
    rsync -az --info=stats1 -e "ssh -F $HOME/.brev/ssh_config" "$INSTANCE:$REMOTE/data/interim/eval/" "$ROOT/data/interim/eval/remote/"
    exit 0
fi

LIST="$(mktemp)"
trap 'rm -f "$LIST"' EXIT
python3 "$ROOT/scripts/brev_files.py" > "$LIST"
echo "files: $(wc -l < "$LIST")"
rsync -az --info=stats1 -e "ssh -F $HOME/.brev/ssh_config" --files-from="$LIST" "$ROOT/" "$INSTANCE:$REMOTE/"
