# car-accident-model

NVIDIA Agentic AI Hackathon(Creative Use-case 트랙) 출품작.
**손해보험사 대물보상팀의 차대차 사고 1차 손해사정 에이전트**를 만든다.
블랙박스 영상·파손 사진·정비공장 견적서를 받아 과실비율 초안, 인정 수리비, 이상 징후(SIU 이관)를 근거와 함께 산출하고 담당자가 승인한다.

전체 배경, 결정 이력, 데이터 구조, 설계는 아래 문서에 있다. 작업 전에 반드시 읽을 것.

@docs/HANDOFF.md

## 작업 규칙

- 언어: 사용자와의 대화와 문서는 한국어. 코드 식별자와 커밋 메시지는 영어.
- 환경: Windows, 프로젝트 루트는 `F:\car-accident-model`. 경로는 `pathlib`로 다루고 하드코딩하지 않는다.
- **AI Hub 원본 데이터는 절대 git에 올리지 않는다.** 재배포 제한 가능성 때문이다. `data/raw/`, `data/interim/`은 `.gitignore`에 넣는다. 저장소에는 파일 키 목록과 다운로드·재생성 스크립트만 둔다.
- 재현성: 합성 사고 건 생성, 평가 세트 샘플링은 모두 고정 시드(`SEED=42`)를 쓴다. 심사위원이 스크립트만으로 같은 결과를 재현할 수 있어야 한다(해커톤 전제 조건).
- 범위 밖 기능(대인·부상, 전손, 보행자·이륜차 사고, 영상→시뮬레이션 자동 생성, .pro 파일 해석)은 구현하지 않는다. 필요하면 먼저 사용자에게 묻는다.
- 데이터 필드 구조는 추측하지 말고 실제 파일을 열어 확인한 뒤 코드를 짠다. 확인한 내용은 `docs/HANDOFF.md`의 "확인 결과" 절에 기록한다.
- 파일 다운로드, 외부 전송, 패키지 설치처럼 되돌리기 어려운 작업은 실행 전에 사용자에게 확인한다.

## 지금 할 일 (우선순위 순)

1. ~~1차 확인 체크리스트~~ 완료 (HANDOFF 7.3).
2. ~~라벨 파서~~ 완료: `aihub/` 패키지, `python scripts/build_interim.py`.
3. ~~평가 세트, 합성 사고 건~~ 완료: `scripts/build_eval_fault.py`, `scripts/build_synth_cases.py` (HANDOFF 7.3).
4. 2차·3차 다운로드(평가 영상 8.5GB, 파손 사진 4GB) 후, 입력→사정서 초안까지 가장 단순한 end-to-end 파이프라인을 먼저 돌린다. 정확도는 그 다음.

재생성 순서: `download_aihub.py --stage 1` (+ `--stage meta`) → `build_interim.py` → `build_eval_fault.py` → `build_synth_cases.py`.
