#!/usr/bin/env bash
# Host prerequisites for VSS + NemoClaw on a fresh Brev/Linux GPU instance. Run ON THE INSTANCE first.
# Every item below fixes a failure hit on 2026-09-28 (see scripts/brev/README.md "Pitfalls").
set -euo pipefail

# API key file, written by a person (never by a script or chat)
[[ -s ~/.nvidia_keys ]] || { echo "missing ~/.nvidia_keys (see README step 1)"; exit 1; }
source ~/.nvidia_keys
[[ -n "${NVIDIA_API_KEY:-}" ]] || { echo "NVIDIA_API_KEY empty in ~/.nvidia_keys"; exit 1; }

# P1. A non-login SSH session has no systemd user bus and no /run/user/<uid>. NemoClaw then runs the
#     OpenShell gateway in a fallback mode and cannot keep its launch-readiness authority, which later
#     quarantines the sandbox (dashboard forward and CLI scope pairing fail). Enable it BEFORE NemoClaw.
sudo loginctl enable-linger "$USER"
for _ in $(seq 1 20); do [[ -S "/run/user/$(id -u)/bus" ]] && break; sleep 1; done
[[ -S "/run/user/$(id -u)/bus" ]] || { echo "user systemd bus did not come up"; exit 1; }
grep -q XDG_RUNTIME_DIR ~/.bashrc || cat >> ~/.bashrc <<'EOF'
export XDG_RUNTIME_DIR=/run/user/$(id -u) DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus
EOF

# P2. ufw hosts: sandbox containers must reach the OpenShell gateway on the Docker bridge.
if sudo ufw status | grep -q "Status: active"; then
    sudo ufw allow from 172.18.0.0/16 to 172.18.0.1 port 8080 proto tcp >/dev/null
fi

# P3. VSS's NemoClaw notebook helpers need Python >= 3.11 (Ubuntu 22.04 ships 3.10): uv + IPython venv.
[[ -x ~/.local/bin/uv ]] || curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
if ! ~/nbenv/bin/python -c 'import sys, IPython; assert sys.version_info >= (3, 11)' 2>/dev/null; then
    rm -rf ~/nbenv
    ~/.local/bin/uv venv -q --python 3.12 ~/nbenv
    ~/.local/bin/uv pip install -q --python ~/nbenv/bin/python ipython
fi

# P4. ffmpeg for transcoding clips to H.264 (VST rejects the dataset's mpeg4)
command -v ffmpeg >/dev/null || sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg >/dev/null

echo "prereqs ok: user bus $(systemctl --user is-system-running 2>/dev/null), $(~/nbenv/bin/python -V), ffmpeg $(ffmpeg -version | head -1 | cut -d' ' -f3)"
