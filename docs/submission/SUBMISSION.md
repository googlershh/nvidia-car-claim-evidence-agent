# 제출 양식 답변

## 1. 서비스 명

협의 근거 에이전트 (Claim Evidence Agent) — 자동차보험 대물 과실·수리비 협의 지원 에이전트

## 2. 서비스 파일 (또는 배포 URL)

- GitHub 저장소: https://github.com/googlershh/nvidia-car-claim-evidence-agent (현재 비공개, 제출 전 공개 전환 필요)
- 제출 파일: `docs/submission/NVIDIA 해커톤_종지_협의 근거 에이전트.pdf` (한 페이지 소개서 + 스택 다이어그램 + 저장소 링크)

## 3. 해결하고자 했던 문제 (Problem Definition)

**한 줄 정의: 대물보상 담당자가 상대가 받아들일 협의 근거를 만들기 어려워, 인정기준으로 결론이 예측되는 사고도 분쟁심의까지 가서 두 달 가까이 늦어진다.**

손해보험사 대물보상 담당자는 사고 한 건을 끝내려면 상대 보험사와 과실비율을, 정비공장과 수리비를 모두 합의해야 합니다. 합의가 안 되면 보험사가 분쟁심의를 청구하는데, 2024년 약 15.7만 건에 소심의만 평균 61일이 걸립니다. 그런데 심의 결정의 95%가 그대로 받아들여집니다. 결론은 과실비율 인정기준으로 예측되는데도, 상대가 받아들일 근거(적용 도표, 영상 속 시각, 진술과의 차이)를 담당자가 일일이 만들기 어려워 협의가 길어집니다. 이 근거 작성 부담을 덜기 위해 시작했습니다.

## 4. 서비스 소개 및 주요 기능 (Solution)

담당자가 "이 건 상대사와 공장에 보낼 근거를 만들어줘"라고 목표를 주면, NemoClaw 샌드박스 안의 에이전트가 사고 자료를 조사해 협의 근거 묶음을 만듭니다.
① 블랙박스 영상을 VSS(Cosmos3)로 분석해 두 차의 진행과 충돌 시각을 파악하고 사고유형을 판정합니다.
② 손해보험협회 과실비율 인정기준(제10차)의 도표와 현행 기본과실을 인용합니다. 도표 108개와 수정요소 829개를 추출해 두었습니다.
③ 피보험자 진술과 상대 보험사 주장을 영상 판단과 대조해 다른 점과 영상으로 확인할 수정요소를 표시합니다.
④ 파손 사진과 견적서를 대조해 사진에 없는 부위의 청구를 찾고, 충돌 부위가 사고 형태와 모순되면 SIU로 넘깁니다.
⑤ 상대 보험사용 협의 근거 문서(분쟁심의 가능성 포함), 정비공장 조정 요청서, SIU 메모 초안을 만들고, 담당자가 승인한 뒤에만 발송합니다. 사고 영상과 개인정보는 OpenShell 정책으로 외부 전송을 막습니다.

## 5. 활용한 핵심 기술 및 AI 모델 (Tech Stack)

**NVIDIA**
- NemoClaw (OpenClaw 에이전트 하네스) — 에이전트 실행, 샌드박스 관리
- OpenShell — 샌드박스 런타임, 네트워크 정책(기본 차단, 목적지별 허용), 자격증명 분리
- Video Search and Summarization(VSS) Blueprint — 영상 저장(VST), VSS Agent(NeMo Agent Toolkit 기반), VSS 스킬(vss-ask-video 등)
- NIM — Cosmos3 Nano Reasoner(영상 이해, GPU 자체 서빙)
- build.nvidia.com NIM API — Nemotron 3 Super(에이전트 계획·도구 호출), Nemotron 3.5 Lightning(VSS 에이전트), Nemotron 3 Ultra(한국어 문서 작성), Nemotron 3 Nano Omni(영상·사진), DeepSeek-V4.1-Flash(프레임 기반 판정 비교)
- Brev (RTX A6000 48GB) 개발 환경, 본선 DGX Spark

**그 밖의 스택**
- Python 3 (표준 라이브러리 중심), ffmpeg, Docker / Docker Compose
- 데이터: AI Hub 교통사고 영상·차량 파손 이미지·견적서·교통사고 모사 데이터, 손해보험협회 과실비율 인정기준(제10차 개정)
- 재현성: 고정 시드(SEED=42) 데이터 생성, 원본 대조 감사 스크립트, 원본 데이터 미포함 + 다운로드·재생성 스크립트

## 6. [선택] 추가 URL

- GitHub 저장소 README(스택 다이어그램 포함): https://github.com/googlershh/nvidia-car-claim-evidence-agent#readme
