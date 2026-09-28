#!/usr/bin/env bash
# Ask the VSS agent one question about an evaluation clip (the vss-ask-video flow).
# Run ON THE INSTANCE from the synced repo root:  bash scripts/brev/vss_ask_clip.sh F016 "question"
# VST rejects the dataset's mpeg4 codec, so the clip is transcoded to H.264 first.
set -uo pipefail
EVAL_ID="${1:-F016}"
QUESTION="${2:-This is a dashcam clip. Describe what the camera car and the other car do before the collision, whether either changes lanes, and at what second they collide.}"

NAME=$(python3 -c "import csv,sys;print(next(r['video_name'] for r in csv.DictReader(open('data/interim/eval_fault_reviewed.csv',encoding='utf-8-sig')) if r['eval_id']==sys.argv[1]))" "$EVAL_ID")
SRC="data/interim/media/videos/$NAME.mp4"
OUT="data/interim/media/videos_h264/$NAME.mp4"
mkdir -p "$(dirname "$OUT")"
[[ -f "$OUT" ]] || ffmpeg -nostdin -v error -y -i "$SRC" -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -an "$OUT"

if ! curl -sf http://localhost:30888/vst/api/v1/sensor/list | grep -q "\"$NAME\""; then
    curl -s -X PUT "http://localhost:30888/vst/api/v1/storage/file/$NAME.mp4?timestamp=2025-01-01T00:00:00.000Z" \
        -H "Content-Type: application/octet-stream" -H "Content-Length: $(stat -c %s "$OUT")" --upload-file "$OUT" >/dev/null
fi

MSG="Call video_understanding tool to answer the following question about $NAME: $QUESTION"
curl -s --max-time 600 -X POST http://localhost:8000/generate -H "Content-Type: application/json" \
    -d "$(python3 -c "import json,sys;print(json.dumps({'input_message':sys.argv[1]}))" "$MSG")" \
  | python3 -c "import json,re,sys;v=json.load(sys.stdin).get('value','');print(re.sub(r'<agent-think>.*?</agent-think>\s*','',v,flags=re.S).strip())"
