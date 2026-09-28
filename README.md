# 협의 근거 에이전트 (Claim Evidence Agent)

자동차보험 **대물보상 담당자**가 상대 보험사(과실)와 정비공장(수리비)에 보낼 **협의 근거 묶음**을 만드는 에이전트입니다.
블랙박스 영상, 파손 사진, 정비공장 견적서, 당사자 진술을 받아 과실비율 인정기준 도표와 현행 기본과실, 진술과 영상의 차이, 인정 수리비, 이상 징후(SIU 이관)를 근거와 함께 정리하고, **담당자가 승인한 뒤에만** 밖으로 내보냅니다.

NVIDIA Agentic AI Hackathon, Creative Use-case 트랙 출품작.

![스택 다이어그램](docs/assets/stack.svg)

## 왜 만들었나

- 대물보상 담당자는 사고 한 건을 끝내려면 상대 보험사와 과실, 정비공장과 수리비를 모두 합의해야 합니다.
- 합의가 안 되면 보험사가 과실비율 분쟁심의를 청구합니다. 2024년 약 15.7만 건이고, 소심의에 평균 61일이 걸립니다. 그런데 심의 결정의 95%가 그대로 받아들여집니다(2018).
- 결론은 인정기준으로 예측할 수 있는데, 상대가 받아들일 근거를 갖추지 못해 두 달을 기다리는 셈입니다. 이 에이전트는 그 근거를 처음부터 갖춥니다.

근거 자료는 [docs/ROI_EVIDENCE.md](docs/ROI_EVIDENCE.md), 방향 결정은 [docs/DIRECTION.md](docs/DIRECTION.md).

## 무엇을 하나

| 단계 | 하는 일 | 코드 |
|---|---|---|
| 영상 분석 | 사고유형 후보, 두 차의 진행, 촬영 차량이 A인지 B인지, 시각 근거 | `agent/backends/nim.py`, VSS(Cosmos3) |
| 인정기준 조회 | 사고유형 → 과실비율 인정기준 제10차 도표와 현행 기본과실, 도표별 수정요소 | `agent/tools/fault.py`, `data/reference/code_to_chart.csv` |
| 진술 대조 | 피보험자 진술·상대 보험사 주장을 영상 판단과 비교 → 일치 / 영상과 다름 / 수정요소 영상 확인 필요 | `agent/tools/statements.py` |
| 손해액 검증 | 사진의 손상 방향 ↔ 견적 항목 대조, 사진에 없는 부위 청구 찾기 | `agent/tools/damage.py` |
| 이상 징후 | 사고유형의 충돌 가능 부위 ↔ 사진 손상 부위 모순 → SIU 이관 | `agent/tools/anomaly.py` |
| 산출물 | 손해사정서, **상대 보험사용 협의 근거 문서**(분쟁심의 가능성 포함), 정비공장 조정 요청서, SIU 메모 | `agent/tools/report.py`, `agent/tools/negotiation.py` |

설계는 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), 업무별 범위와 남은 일은 [docs/SCOPE.md](docs/SCOPE.md).

## NVIDIA 스택

| 구성 | 쓰임 |
|---|---|
| **NemoClaw** (OpenClaw 하네스) | 에이전트 실행. 계획·도구 호출 모델은 Nemotron 3 Super |
| **OpenShell** | 샌드박스. 네트워크 기본 차단과 목적지별 허용, 자격증명은 샌드박스 밖 |
| **VSS Blueprint** | 사고 영상 저장(VST)과 영상 질의응답. 영상 모델 Cosmos3 Nano Reasoner(NIM)를 GPU에서 직접 서빙, VSS Agent는 NeMo Agent Toolkit 기반 |
| **모델 API** (OpenRouter · build.nvidia.com) | Nemotron 3 Super(에이전트), Nemotron 3.5 Lightning(VSS 에이전트), DeepSeek-V4.1-Flash(프레임 판정 비교). 무료 API 과부하로 OpenRouter 경유 |
| 실행 환경 | Brev RTX A6000 48GB 한 대에 VSS와 NemoClaw |

## 데이터와 검증

- AI Hub 교통사고 영상(597), 차량 파손 이미지·견적서(581), 교통사고 모사(71958). **원본은 저장소에 없습니다**(재배포 제한 가능성). 파일 키 목록과 다운로드·재생성 스크립트만 있습니다.
- 평가 영상 150건을 사람이 한 건씩 검수해, 라벨이 영상과 맞는 **92건**만 씁니다([docs/LABEL_REVIEW.md](docs/LABEL_REVIEW.md)).
- 손해보험협회 과실비율 인정기준(제10차 개정)의 차대차 도표 108개와 수정요소 829개를 추출했습니다. AI Hub 사고유형 84개를 도표 65개에 대응시켜 기본과실 79/84를 재현하고, 나머지는 개정 내용을 반영했습니다.
- 수리비 정답은 쏘카 견적서의 실제 손해사정 전·후 금액입니다.
- 합성 사고 건, 진술, 평가 표본은 모두 `SEED=42`로 재현됩니다.

## 재현

```bash
# 1. AI Hub 데이터 (AI Hub 승인과 API 키 필요)
python scripts/download_aihub.py --stage 1 meta 2 3
# 2. 파싱과 평가 세트
python scripts/build_interim.py
python scripts/build_eval_fault.py
python scripts/build_eval_reviewed.py
# 3. 과실비율 인정기준 원문과 도표 매핑
python scripts/download_knia.py
python scripts/build_chart_map.py
# 4. 합성 사고 건과 진술, 미디어
python scripts/build_synth_cases.py
python scripts/build_statements.py
python scripts/extract_media.py
# 5. 감사와 오프라인 평가 (정답 주입 상한)
python scripts/audit_eval_sets.py
python eval/run_eval.py --backend oracle
```

실제 모델 실행은 `python eval/run_eval.py --backend nim --limit N`(호출 전 예상 호출 수와 토큰을 출력하고 `--yes`가 있어야 호출). API 키는 `.env.example`을 참고해 환경변수로 넣습니다.

## 현재 상태

- 완료: 검수된 평가 세트와 합성 사고 건, 인정기준 도표 매핑, 진술 대조, 협의 근거 문서, 손해액 검증과 SIU 라우팅, Brev에 VSS와 NemoClaw 배포, VSS로 사고 영상 질의응답 확인.
- 진행 중: NemoClaw 에이전트가 스킬로 전체 흐름을 계획·실행하도록 전환(지금은 고정 순서 파이프라인), 수정요소별 영상 재조사 루프, 영상 모델의 사고유형 판정 정확도 측정(지금은 소표본 시험만).
- 정답 주입(oracle) 평가 수치는 인식이 완벽할 때의 상한이며 실제 모델 성능이 아닙니다.

## 문서

| 문서 | 내용 |
|---|---|
| [docs/HANDOFF.md](docs/HANDOFF.md) | 배경, 데이터 확인 결과, 결정 이력 전체 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 파이프라인과 도구 |
| [docs/DIRECTION.md](docs/DIRECTION.md) · [docs/SCOPE.md](docs/SCOPE.md) | 문제 정의, 범위, 남은 일 |
| [docs/LABEL_REVIEW.md](docs/LABEL_REVIEW.md) | 평가 영상 150건 검수 |
| [docs/ROI_EVIDENCE.md](docs/ROI_EVIDENCE.md) | 현업 조사와 통계 |
| [docs/submission/](docs/submission/) | 제출용 한 페이지 소개서 |

과실 판정은 "초안 + 근거 + 사람 승인"을 원칙으로 합니다. 이 에이전트는 과실을 결정하지 않습니다.
