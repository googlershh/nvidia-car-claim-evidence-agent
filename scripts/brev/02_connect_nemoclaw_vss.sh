#!/usr/bin/env bash
# Install NemoClaw and connect it to the running VSS deployment, then repair what that step disturbs.
# Run ON THE INSTANCE from the synced repo root, after 00_prereqs.sh and 01_deploy_vss.sh.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source ~/.nvidia_keys
export NVIDIA_API_KEY
export XDG_RUNTIME_DIR="/run/user/$(id -u)" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"
export NVM_DIR="$HOME/.nvm"; [[ -s "$NVM_DIR/nvm.sh" ]] && source "$NVM_DIR/nvm.sh" >/dev/null
export PATH="$HOME/.local/bin:$PATH"
redact() { sed -E 's/nvapi-[A-Za-z0-9_-]+/nvapi-***/g; s/(token[=:] ?)[A-Za-z0-9._-]{12,}/\1***/g'; }
VSS_DOCKER="$HOME/video-search-and-summarization/deploy/docker"
compose() {
    (cd "$VSS_DOCKER" && docker compose -f compose.yml --env-file containers.env \
        --env-file developer-profiles/dev-profile-base/.env --env-file developer-profiles/dev-profile-base/generated.env "$@")
}

# 1. VSS's own NemoClaw notebook, headless. It pins NemoClaw, builds the `demo` sandbox from the VSS
#    skills image and applies the VSS policy. Do NOT run a separate NemoClaw install before this: a
#    second sandbox made the notebook's pre-upgrade backup fail (P5).
echo "== notebook (full)"
~/nbenv/bin/python "$ROOT/scripts/brev/run_nemoclaw_notebook.py" 2>&1 | redact | tee ~/nemoclaw-vss.log | grep -E '^##########'
if grep -q "FAILED at cell 21" ~/nemoclaw-vss.log; then
    # P6. Onboarding can stop at its last check ("bounded CLI scope warm-up") while the sandbox is
    #     already Ready. The remaining steps (policy, vss configure, webhooks) still apply.
    echo "== onboard check failed; running the remaining notebook steps"
    ~/nbenv/bin/python "$ROOT/scripts/brev/run_nemoclaw_notebook.py" --after-onboard 2>&1 | redact | tee ~/nemoclaw-vss-after.log | grep -E '^##########'
fi

# 2. P7. The notebook's Docker pinning restarted the Docker daemon, which left VSS's VST services
#    stopped (vss-vios-sensor exited, vss-vios-ingress restart loop -> /vst 503 behind port 7777).
echo "== restore VSS services"
compose up -d --no-build --pull never 2>&1 | tail -3
for _ in $(seq 1 30); do docker ps --format '{{.Names}} {{.Status}}' | grep -q "vss-vios-ingress.*healthy" && break; sleep 5; done
printf 'VST via 7777: '; curl -s -o /dev/null -w '%{http_code}\n' --max-time 8 http://localhost:7777/vst/api/v1/sensor/list

# 3. Re-record the deployment inside the sandbox so `vst` is listed (it was absent while VST was down).
#    openshell exec reads stdin: always give it </dev/null inside scripts (P8).
echo "== vss configure in sandbox"
openshell sandbox exec --name demo --timeout 120 -- sh -lc 'vss configure --base-url http://host.openshell.internal:7777 2>&1 | tail -12' </dev/null

echo "== status"
nemoclaw demo status 2>&1 | redact | sed -n 1,16p
printf 'dashboard health (18789): '; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://127.0.0.1:18789/health
