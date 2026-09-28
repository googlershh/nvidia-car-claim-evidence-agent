#!/usr/bin/env bash
# Deploy the VSS base profile: Cosmos3 Nano Reasoner served locally on the GPU, LLM from build.nvidia.com.
# Run ON THE INSTANCE after ~/.nvidia_keys exists. The NVIDIA API key also logs in to nvcr.io (NGC).
#   bash scripts/brev/02_deploy_vss.sh        # deploy
#   bash scripts/brev/02_deploy_vss.sh -d     # dry run (prints the compose command and images)
set -uo pipefail
source ~/.nvidia_keys
REPO="$HOME/video-search-and-summarization"
[[ -d "$REPO" ]] || git clone --depth 1 https://github.com/NVIDIA-AI-Blueprints/video-search-and-summarization.git "$REPO"

export NGC_CLI_API_KEY="$NVIDIA_API_KEY"
# No trailing /v1: the VSS agent config appends it (…/v1/v1 returns 404 "page not found").
export LLM_ENDPOINT_URL="https://integrate.api.nvidia.com"

cd "$REPO/deploy/docker"
# -H OTHER: the RTX A6000 is not in VSS's hardware list; OTHER skips the GPU match.
bash scripts/dev-profile.sh up -p base -H OTHER \
    --use-remote-llm --llm nvidia/nemotron-3.5-lightning-30b-a3b --llm-model-type nim \
    --vlm nvidia/cosmos3-reasoner "$@" 2>&1 | sed -E 's/nvapi-[A-Za-z0-9_-]+/nvapi-***/g' | tail -40

docker ps --format '{{.Names}}\t{{.Status}}' | grep -v openshell
