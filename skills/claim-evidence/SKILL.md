---
name: claim-evidence
description: Use when a property-damage (대물) claims handler asks for negotiation evidence on a car-to-car accident case — fault ratio against the other insurer, repair cost against the body shop, or SIU referral. Builds a Korean fault evidence letter from the dashcam video (via VSS), the KNIA fault standard (10th edition), the parties' statements, photos and the repair estimate. Never sends anything; the handler approves.
---

# Claim evidence (대물 협의 근거)

You help a Korean auto insurer's property-damage claims handler. The goal they give is usually
"이 건 상대 보험사와 정비공장에 보낼 근거를 만들어줘" for a case id such as `C006`.
You produce drafts only. **Never send, email or post anything**; say the draft needs the handler's approval.

All tools are one command: `cd /sandbox/claim && python3 -m agent.cli <command>` (JSON output).

| command | what it gives |
|---|---|
| `cases` | case ids |
| `case <id>` | VST sensor name of the dashcam clip, damaged photo parts, estimate lines, the two statements |
| `candidates --place <직선도로\|사거리교차로(신호등있음)\|T자형교차로>` | accident types with English descriptions of vehicle A and B |
| `fault <code>` | fault standard chart, base fault A:B, the chart's modifiers |
| `compare <id> --code N --role A\|B` | statements vs the chart you judged: consistent / contradicts / needs_video |
| `estimate <id>` | estimate lines whose part faces no photographed direction |
| `anomaly <id> --code N --role A\|B` | impact-direction contradiction (SIU signal) |
| `letter <id> --code N --role A\|B --evidence "..." [--modifier-check JSON]...` | writes the negotiation letter and report to `outputs/<id>/` |

## Plan (adapt it to the case; skip what is not needed, repeat what is unclear)

1. `case <id>` to see what you have.
2. Watch the video with the VSS skills (`vss-ask-video`): ask what the camera car and the other car do,
   lane changes, signals, and the collision time, for the case's `vst_sensor`.
   The camera car is the claimant (the other insurer's customer); our insured is the other car.
3. `candidates --place ...` and pick the accident type code whose vehicle A/B descriptions match the video,
   and whether the camera car is A or B. If nothing matches well, say so and stop for the handler.
4. `fault <code>` and `compare <id> --code --role`.
5. For every modifier that decides the ratio — the ones the counterparty claims (`needs_video`) and the ones
   that would help our insured — ask VSS a targeted question about the time window (e.g. "Between 3 s and
   6 s, does the grey sedan turn on its left turn signal before changing lanes?"). Record each as
   `{"name": <modifier name exactly as in fault>, "verdict": "confirmed|not_seen|unclear", "evidence": "<what and when>"}`.
   If an answer is vague, ask once more with a narrower window before marking `unclear`.
6. `estimate <id>` and `anomaly <id> --code --role`.
7. `letter ...` with the video evidence (timestamps) and every modifier check.
8. Reply in Korean: chart and base fault (our insured : claimant), what the counterparty claimed and why it
   holds or not, modifier checks with times, repair-cost adjustments, SIU flag if any, dispute likelihood,
   and the file paths. End with "담당자 승인 전 초안입니다."

## Rules

- Quote the chart as "과실비율 인정기준 제10차 개정 차XX-X". Do not invent chart numbers or ratios; use `fault`.
- Do not quote our insured's statement in the letter when it contradicts the video (the tool keeps it internal).
- Personal data in video (plates, faces) stays out of your reply.
