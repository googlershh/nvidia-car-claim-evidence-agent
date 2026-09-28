#!/usr/bin/env bash
# Switch the NemoClaw agent and the VSS agent's LLM from build.nvidia.com (free, often "overloaded")
# to OpenRouter (paid). Run ON THE INSTANCE after 02/03. Needs `export OPENROUTER_API_KEY=sk-or-...` in
# ~/.nvidia_keys, added by a person:
#   read -rsp "OpenRouter key: " K && printf 'export OPENROUTER_API_KEY=%s\n' "$K" >> ~/.nvidia_keys && unset K
# Prices checked 2026-09-28: nemotron-3-super-120b-a12b $0.08 in / $0.45 out per 1M tokens.
set -euo pipefail
SANDBOX="${1:-demo}"
AGENT_MODEL="${AGENT_MODEL:-nvidia/nemotron-3-super-120b-a12b}"
VSS_LLM="${VSS_LLM:-nvidia/nemotron-3.5-lightning}"
source ~/.nvidia_keys
[[ "${OPENROUTER_API_KEY:-}" == sk-or-* ]] || { echo "OPENROUTER_API_KEY missing in ~/.nvidia_keys"; exit 1; }
export XDG_RUNTIME_DIR="/run/user/$(id -u)" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"
export NVM_DIR="$HOME/.nvm"; [[ -s "$NVM_DIR/nvm.sh" ]] && source "$NVM_DIR/nvm.sh" >/dev/null
export PATH="$HOME/.local/bin:$PATH"

# 1. NemoClaw agent. `nemoclaw inference set --provider openrouter` needs a provider that only the
#    onboarding wizard registers, so register an OpenAI-type provider on OpenShell directly
#    (credential by env lookup: the key never appears on a command line) and route the sandbox to it.
if ! openshell provider get openrouter-api >/dev/null 2>&1; then
    OPENAI_API_KEY="$OPENROUTER_API_KEY" openshell provider create --name openrouter-api --type openai \
        --credential OPENAI_API_KEY --config OPENAI_BASE_URL=https://openrouter.ai/api/v1
fi
nemoclaw inference set --provider openrouter-api --model "$AGENT_MODEL" --sandbox "$SANDBOX" 2>&1 | tail -3

# 2. VSS agent LLM: OpenAI-compatible profile. No /v1 in the base URL (the agent config appends it, P4).
cd ~/video-search-and-summarization/deploy/docker
G=developer-profiles/dev-profile-base/generated.env
set_env() { if grep -q "^$1=" "$G"; then sed -i "s|^$1=.*|$1=$2|" "$G"; else echo "$1=$2" >> "$G"; fi; }
set_env LLM_BASE_URL https://openrouter.ai/api
set_env LLM_MODEL_TYPE openai
set_env LLM_NAME "$VSS_LLM"
set_env LLM_ENABLE_THINKING false
set_env OPENAI_API_KEY "$OPENROUTER_API_KEY"
chmod 600 "$G"
docker compose -f compose.yml --env-file containers.env --env-file developer-profiles/dev-profile-base/.env \
    --env-file "$G" up -d --no-deps --force-recreate vss-agent 2>&1 | tail -1
for _ in $(seq 1 40); do docker ps --format '{{.Names}} {{.Status}}' | grep -q "^vss-agent .*healthy" && break; sleep 5; done
nemoclaw "$SANDBOX" status 2>&1 | sed -n 3,6p
