# 파이프라인 구조

차대차 대물 사고 1건(사고 접수 묶음)을 받아 **과실비율 초안, 인정 수리비, 이상 징후, 라우팅, 손해사정서 초안**을 만들고 담당자 승인을 기다리는 에이전트. 배경과 데이터는 `docs/HANDOFF.md`.

## 1. 흐름

```
ClaimBundle (영상, 사진, 견적서, [진술])
 │
 ├─ 0. intake        입력 검증, 개인정보 가드(번호판·얼굴·연락처 마스킹 대상 표시)
 │
 ├─ A. fault         analyze_video ─► search_fault_table ─► base fault + 근거
 │                   (영상 → 장면 JSON → 사고유형 top-3 → 코드표 기본과실)
 │
 ├─ B. damage        assess_damage(사진) ─► parse_estimate ─► check_estimate
 │                   (사진 부위·방향 ↔ 견적 항목 대조 → 조정 대상 항목, 인정액)
 │
 ├─ C. anomaly       check_consistency(사고유형 충돌부위 ↔ 사진 방향)
 │                   [+ detect_synthetic_video, claim_history, collision_prior]
 │
 ├─ route            approve | adjust | siu  (+ 사유)
 │
 └─ draft            손해사정서 초안(한국어) / 조정 요청서 / SIU 이관 메모
                     status = pending_approval  ← 담당자 승인(HITL)
```

각 단계는 **도구(tool) 함수**이고, 파이프라인은 단계별 입력·출력·소요시간·토큰을 `trace`로 남긴다(GPU 수요 근거, 디버깅).

## 2. 모델 백엔드 (교체 가능)

모델이 필요한 곳은 인터페이스 3개로 모았다. 나머지는 결정적 규칙이다.

| 인터페이스 | 하는 일 | `oracle` (오프라인) | `nim` (결제 후) |
|---|---|---|---|
| `VideoAnalyzer` | 영상 → 장면 설명 + 사고유형 top-3 | 데이터셋 라벨의 사고유형을 그대로 반환 | Omni, 프레임 8장 + 영어 후보표, 추론 off (5.3절 3차 설정) |
| `DamageAnalyzer` | 사진 → 손상 부위 목록 | 파손 라벨의 수리 부위 | Omni 이미지 입력 |
| `Writer` | 사정서 문장 작성 | 템플릿 | Nemotron 3 Ultra(한국어) |

- `oracle`은 **정답을 주입하는 테스트용**이다. 이 백엔드의 점수는 "인식이 완벽할 때 규칙·라우팅이 얼마나 맞는가"의 **상한**이며 실제 성능이 아니다. 보고서와 평가 결과에 `backend=oracle`을 항상 표시한다.
- `nim`은 `agent/nim_client.py`(호출 상한·캐시·사용량 로그)를 쓴다. DGX Spark 자체 서빙은 같은 OpenAI 호환 API라 `base_url`만 바꾼다.
- 백엔드 선택: `--backend oracle|nim`.

## 3. 결정적 도구 (모델 불필요)

| 도구 | 입력 → 출력 | 근거 자료 |
|---|---|---|
| `search_fault_table` | 사고유형 코드 → 장소·상황·진행방향·기본과실 | `data/interim/accident_codes.csv`, 영어판 `data/reference/accident_codes_en.csv` |
| `impact_directions` | 사고유형 → A·B 충돌 가능 방향, 신뢰도 | `data/reference/collision_areas.csv` |
| `parse_estimate` | 견적서 → 항목(이름·작업·금액·방향) | `aihub/estimates.py`, `aihub/parts.py` |
| `check_estimate` | 사진 방향 ↔ 견적 항목 → 사진에 없는 방향의 교환·판금·수리 항목 | `aihub/parts.py` |
| `check_consistency` | 청구 차량 충돌 방향 ↔ 사진 방향 → consistent / partial / contradiction | 위 두 표 |
| `route` | 이상징후·조정 항목 → approve / adjust / siu | 4절 규칙 |
| `draft_report` | 전체 결과 → 한국어 사정서 초안 | 템플릿(오프라인) |

## 4. 라우팅 규칙 (초안)

1. 사진 방향이 청구 차량 충돌 방향과 **전혀 겹치지 않고**(contradiction) 사고유형 신뢰도가 high/medium → **siu**
2. 그 외 contradiction(신뢰도 low) → **adjust**(현장 확인 요청) + 사유
3. 사진에 없는 방향의 수리 항목이 있으면 → **adjust**(해당 항목 불인정 제안)
4. 그 외 → **approve**

지급 예상액 = 인정 수리비(부가세 별도) × 상대 과실(A)%. 우리 쪽은 A의 보험사, 청구인은 1인칭 영상의 촬영 차량 B.

## 5. 평가 (`eval/run_eval.py`)

합성 사고 92건(`data/interim/synth_cases.jsonl`)에 파이프라인을 돌려 HANDOFF 8절 지표를 계산한다. 2026-09-28부터 **라벨 검수를 통과한 영상만** 쓴다(`docs/LABEL_REVIEW.md`, `scripts/build_eval_reviewed.py`). 청구 차량은 도표의 B가 기본이지만, 검수에서 역할이 뒤바뀐 19건은 A다(`claimant`). 과실 지표는 청구 차량의 과실로 계산하고, 청구 차량 역할(A/B) 정확도를 따로 잰다.

| 지표 | 계산 |
|---|---|
| 사고유형 top-1 / top-3 | 예측 코드 vs 라벨 코드 |
| 과실비율 완전 일치 / ±10%p | 기본과실 A |
| 라우팅 정확도, SIU 재현율·정밀도 | expected_route vs 예측 |
| 과잉 항목 탐지 정밀도·재현율 | 주입 항목 vs 불인정 제안 항목 |
| 인정액 오차 | 예측 인정액 vs `approved_total`(실제 손해사정 후 금액) |
| 비용·지연 | trace의 호출 수·토큰·초 |

**oracle 결과 (2026-09-28, 검수 통과 92건)**: 사고유형·청구 차량 역할·과실·SIU·과잉 항목 모두 1.000, **라우팅 0.924**, 인정액 MAPE 0.005. 라우팅 오답은 모두 정상 건의 실제 조정(아래와 같은 한계).

이전 **oracle 결과 (2026-09-27, 검수 전 150건, 0.3초)**: 사고유형·과실·SIU·과잉 항목 모두 1.000, **라우팅 0.940**, 인정액 MAPE 0.006. 라우팅 오답 9건은 전부 "정상 건인데 실제 손해사정사가 금액을 조정한 건"(expected adjust → 예측 approve)이다. 단가 수준 감액 같은 조정은 사진·견적 대조 규칙으로 잡을 수 없으므로 **인식이 완벽해도 남는 한계**다. 보완 후보: 공임 단가(M/H) 기준표 대조, 같은 차종 견적 분포 대비 이상치.

`nim` 예상 비용: 사고 1건 = 호출 3회(영상·사진·사정서), 약 1.05만 토큰(`eval/run_eval.py`의 `EST_TOKENS`). `--yes` 없이는 추정만 출력하고 호출하지 않는다.

주의: 과잉 견적 주입과 `check_estimate`가 같은 방향 규칙을 쓰므로, oracle 백엔드에서 과잉 항목 탐지는 구조상 거의 100%가 된다(순환). 실제 성능은 `nim` 백엔드의 사진 인식으로만 측정된다.

## 6. 디렉터리

```
agent/
  schemas.py        입력·중간 결과·결정 데이터 구조
  backends/         base.py(인터페이스), oracle.py, nim.py
  tools/            fault.py, damage.py, anomaly.py, routing.py, report.py
  pipeline.py       단계 실행 + trace
  cases.py          합성 사고 건 → ClaimBundle (정답은 분리)
  nim_client.py     호스팅 NIM 클라이언트
eval/run_eval.py    지표 계산, 결과 저장
scripts/run_case.py 사고 1건 실행 → 사정서 초안 출력
```

## 7. 이후 확장 (구현 순서)

1. `nim` 백엔드 실제 호출 검증(결제 후): 평가 영상 소표본 → 검수 통과 92건
2. 인정기준 RAG: 손해보험협회 과실비율 인정기준 확보 → `nemotron-3-embed-1b` 색인 → 사고유형별 도표·수정요소·판례 인용
3. 수정요소 추론 루프(정성): 영상에서 가감 요소 후보를 찾고 근거 프레임 제시
4. 이상 징후 확장: AI 생성 영상 탐지(`ai-synthetic-video-detector`), 합성 사고 이력 DB, 모사 데이터 충돌부위 분포
5. 가드레일(`nemotron-3.5-content-safety` + `nemotron-policy-generator`), NemoClaw/OpenShell 샌드박스
6. 도구를 NVIDIA 스킬 규격(SKILL.md)으로 포장, NeMo Relay로 호출 추적
7. 데모 UI(담당자 승인 화면)
