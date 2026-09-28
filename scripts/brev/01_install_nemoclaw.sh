#!/usr/bin/env bash
# Install NemoClaw (OpenClaw harness + OpenShell) non-interactively on a Brev/Linux GPU host.
# Run ON THE INSTANCE. Needs ~/.nvidia_keys with `export NVIDIA_API_KEY=...` (create it yourself,
# see scripts/brev/README.md); the key is never printed.
set -uo pipefail
SANDBOX="${1:-claim-agent}"

[[ -s ~/.nvidia_keys ]] || { echo "missing ~/.nvidia_keys"; exit 1; }
source ~/.nvidia_keys
[[ -n "${NVIDIA_API_KEY:-}" ]] || { echo "NVIDIA_API_KEY empty"; exit 1; }

# OpenShell's gateway runs as a systemd user service; a non-login SSH session has no user bus.
sudo loginctl enable-linger "$USER"
export XDG_RUNTIME_DIR="/run/user/$(id -u)" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"

# Sandbox containers must reach the gateway on the Docker bridge (installer hint on ufw hosts).
if sudo ufw status | grep -q "Status: active"; then
    sudo ufw allow from 172.18.0.0/16 to 172.18.0.1 port 8080 proto tcp
fi

export NEMOCLAW_NON_INTERACTIVE=1 NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE=1 NEMOCLAW_PROVIDER=build \
       NEMOCLAW_SANDBOX_NAME="$SANDBOX" NEMOCLAW_POLICY_MODE=suggested
curl -fsSL https://www.nvidia.com/nemoclaw.sh -o ~/nemoclaw-install.sh
bash ~/nemoclaw-install.sh 2>&1 | tee ~/nemoclaw-install.log | sed -E 's/nvapi-[A-Za-z0-9_-]+/nvapi-***/g'

export NVM_DIR="$HOME/.nvm"; source "$NVM_DIR/nvm.sh" >/dev/null; export PATH="$HOME/.local/bin:$PATH"
nemoclaw "$SANDBOX" status | head -20
