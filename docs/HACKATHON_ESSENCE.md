# NVIDIA Agentic AI Hackathon — 액기스 (주제 무관 가이드)

> 목적: 어떤 주제를 고르든 이 문서 하나로 "주최측이 원하는 것, 쓸 수 있는 재료, 이기는 방법"을 파악한다.
> 작성 2026-09-27. 확인 방법을 각 항목에 표시했다: **[확인]** 직접 확인, **[공식]** NVIDIA 공식 문서, **[제3자]** 외부 글(재확인 필요), **[추정]** 해석.

---

## 0. 한 줄 요약

**"build.nvidia.com의 모델 API와 에이전트 SKILL을 조합해, 스스로 계획·도구호출·위임하는 에이전트를 만들고, NemoClaw/OpenShell 위에서 안전하게 돌리는 작동 데모"**를 제출한다. 실제 산업 문제를 숫자로 증명하고, 보안이 억지가 아니라 필수인 주제일수록 유리하다.

---

## 1. 대회가 요구하는 것 [확인: 사용자 제공 공지]

- 규모: 지원 1,300팀 이상 예상, **본선 10팀 선발** → 상위 1% 싸움.
- 행사 정의: "질문에 답하는 챗봇이 아니라, **목표를 받으면 스스로 계획하고 도구를 호출해 문제를 해결하는 에이전트**".
- 트랙(Creative Use-case): 스스로 판단·실행하는 에이전트로 **진짜 문제**를 푼다. 데모가 아닌 **재현 가능한 코드와 작동하는 서비스**. GPU 활용보다 **다양한 모델 서빙 기반 에이전트 구현**이 주안점.
- 전제 조건: NeMo Framework 또는 NeMo Microservices 활용, 재현 가능한 코드, 작동하는 데모.
- 활용 도구로 명시된 것: Nemotron, NIM, NVIDIA Agent Toolkit, NeMo Agent Skills, Skill Spector, OpenShell(NemoClaw).
- 제공 인프라(본선): DGX Spark, L40S 등.

### 온라인 사전 챌린지 3단계
1. **교육 미션**: DLI 코스 [Securing Agents with NemoClaw and OpenShell](https://learn.nvidia.com/courses/course-detail?course_id=course-v1:DLI+S-FX-43+V1) 수강.
2. **build.nvidia.com의 SKILL과 API를 활용해** 데모 프로젝트를 직접 개발(자유 주제).
3. 온라인 신청서로 제출.

### 채점 항목
| # | 항목 | 이 항목에서 점수를 받는 모습 [추정] |
|---|---|---|
| 1 | **NVIDIA Agent 기술 활용 심도** | NIM API 여러 종을 역할별로 쓰고, SKILL을 설치·작성해 호출하고, NemoClaw 하네스 + OpenShell 정책으로 실행. "API 한 번 부르기"는 얕다 |
| 2 | 실용성, 산업가치, 혁신성 | 실제 업무 페인포인트, 돈·시간으로 환산된 효과, 기존 방식과 다른 점 |
| 3 | 완성도 | 끝까지 돌아가는 데모, 재현 스크립트, 정량 평가 결과, 실패 처리 |
| 4 | 기타(커스터마이징, 독창성) | 도메인 전용 스킬·정책·데이터를 직접 만든 흔적, 남들이 안 한 조합 |

---

## 2. 주최측이 지향하는 것 (핵심 해석) [추정, 근거는 1·3절]

1. **에이전트다움**: 고정 파이프라인이 아니라 계획 → 도구 호출 → 결과 확인 → 재계획 루프. 여러 역할 에이전트 간 위임·라우팅.
2. **SKILL + API의 결합**: 모델은 build.nvidia.com API(NIM)로, 절차·도메인 지식은 SKILL.md 스킬로. NVIDIA 공식 스킬을 설치해 쓰고, **자기 도메인 스킬을 직접 작성**한다.
3. **안전한 실행이 기본값**: NemoClaw(참조 스택) + OpenShell(샌드박스). 네트워크 기본 차단, 필요한 목적지만 허용, 자격증명은 샌드박스 밖, 에이전트별 신원·권한 분리.
4. **지속·성장하는 에이전트**: 스킬 라이브러리를 쌓아 다음 작업에 재사용(코스 학습목표 5).
5. **근거 있는 답**: 검색(RAG)으로 근거를 붙이고, 사람이 승인(HITL)하는 구조.
6. **재현성과 실측**: 누구나 다시 돌릴 수 있는 코드, 숫자로 된 평가.

**한 문장 기준**: "이 데모에서 NemoClaw/OpenShell과 SKILL을 빼면 성립하지 않는가?" → 그렇다면 좋은 주제다.

---

## 3. 교육 미션 요약 (DLI S-FX-43) [확인: 코스 페이지]

- 무료, 4시간, 중급, 영어.
- 흐름: 단일 API 호출 → 에이전트 조율 → 근거 검색(grounded retrieval) → 심층 계획(deep planning) → 안전한 실행.
- 기준 스택: **NemoClaw**로 시스템을 부트스트랩하고, **OpenShell**을 에이전트가 안전하게 도는 샌드박스로 사용. 실제 배포 하네스로 **OpenClaw, Hermes**를 다룬다.
- 학습 목표 5개 → **데모에 하나씩 대응시키면 채점 1번이 채워진다.**

| 코스 학습 목표 | 데모에서 보여줄 것 |
|---|---|
| 1. 기본 에이전트 루프와 구성요소 | 계획·도구·메모리·라우팅이 보이는 루프, 트레이스 로그 |
| 2. 안정적인 도구 호출(function calling) | 도메인 도구를 스킬/함수로 정의, 스키마 검증·재시도 |
| 3. 멀티 에이전트 라우팅 | 역할 에이전트 분리(예: 조사·검증·보고), 라우터/플래너 |
| 4. OpenShell로 신원 설정·샌드박스 | 에이전트별 정책, 네트워크 차단 장면, 자격증명 분리 |
| 5. 자율 배포 + 지속 스킬 라이브러리 | 사람 피드백·반복 작업에서 새 스킬 생성·재사용 |

---

## 4. 표준 참조 구조 (주제 무관)

```
[사용자/업무 입력]
   │
 NemoClaw 하네스 (OpenClaw | Hermes | LangChain Deep Agents)
   ├─ 플래너/라우터 에이전트 ── 역할 에이전트 A, B, C (위임)
   ├─ SKILL 라이브러리: NVIDIA 공식 스킬 + 도메인 스킬(SKILL.md) + 학습된 스킬
   ├─ 모델: build.nvidia.com NIM API (역할별로 다른 모델) ─ 로컬 NIM(DGX Spark)로 교체 가능
   ├─ 근거 검색: 임베딩 NIM + 벡터DB(NeMo Retriever)
   └─ 사람 승인(HITL): 외부로 나가는 행동은 승인 후
   │
 OpenShell 샌드박스
   ├─ filesystem_policy: 작업 폴더만 읽기/쓰기
   ├─ network_policies: 모델 API 등 허용 목적지만 (기본 전부 차단)
   ├─ providers: 자격증명은 샌드박스 밖, 승인된 엔드포인트에서만 주입
   └─ logs: 차단·허용 기록 → 데모의 "보안 장면"
```

### NemoClaw [공식]
- 자율 에이전트용 오픈 블루프린트 모음. 구성: 런타임 OpenShell + 하네스(OpenClaw, Hermes Agents, LangChain Deep Agents) + 모델(Nemotron 3 Ultra 등, 로컬·클라우드 라우팅).
- 설치: `curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash` (OpenClaw 기본). Hermes: `NEMOCLAW_AGENT=hermes`, Deep Agents: `NEMOCLAW_AGENT=langchain-deepagents-code`.
- 하드웨어: RTX PC/노트북, RTX PRO, DGX Spark/Station, 또는 **Brev 클라우드**. Brev 콘솔 문구: "저가 머신에서 돌고 호스팅 모델에 연결 — 비싼 하드웨어 불필요" [확인].
- 스킬: `nemoclaw-user-guide`(NemoClaw 문서 MCP 안내).

### OpenShell [공식: docs.nvidia.com/openshell, github.com/NVIDIA/openshell]
- "자율 에이전트를 위한 안전하고 사적인 런타임". 커널 수준 격리(Landlock LSM 파일, seccomp 시스템콜).
- 플랫폼: Linux, macOS(Apple Silicon), **Windows는 WSL2(실험적)**. Docker/Podman 필요.
- 설치: `curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh`
- CLI: `openshell sandbox create`, `openshell policy update`, `openshell logs`, `openshell sandbox delete`.
- 정책 YAML(`version: 1`): `filesystem_policy`, `landlock`, `process`, `network_policies`, `network_middlewares`. **네트워크 규칙·미들웨어는 실행 중 변경 가능**, 파일·프로세스는 시작 시 고정.
- 네트워크 기본 거부. 예:
  ```yaml
  network_policies:
    nvidia_api:
      endpoints:
        - host: integrate.api.nvidia.com
          port: 443
          protocol: rest
          enforcement: enforce
          access: read-only        # 메서드 제한 가능
      binaries:
        - path: /usr/bin/python3
  ```
  차단 시 `403 ... policy_denied` → 데모에서 "외부 유출 차단" 장면으로 쓴다.
- providers: 자격증명은 승인된 호스트·포트·경로에서만 주입된다.
- Policy Advisor: 에이전트가 좁은 네트워크 규칙을 **제안**하고 사람이 검토하는 기능이 문서에 언급됨(세부 미확인) → HITL 장면 후보.
- SDK: Python/TypeScript/Go/Rust. 텔레메트리 끄기 `OPENSHELL_TELEMETRY_ENABLED=false`.

---

## 5. build.nvidia.com 재료 [확인: 2026-09-27, 카탈로그 `docs/reference/build_nvidia_catalog.xlsx`]

사이트 정체: NVIDIA의 **모델·스킬·블루프린트 진열대 + 무료 시험장**. 모델 97, 스킬 382, 블루프린트 33.

### 5.1 API (NIM, OpenAI 호환)
- 엔드포인트 `https://integrate.api.nvidia.com/v1/chat/completions`, 키 `nvapi-...`(계정 → API Keys). `GET /v1/models`로 호출 가능 목록 조회(토큰 소모 없음).
- **무료**, 계정당 **최대 40 RPM** [확인: 계정 메뉴]. 결제 화면 없음.
- **목록에 있어도 호출 불가일 수 있다**: `cosmos-reason2-8b`는 목록엔 있으나 404 "Function not found for account" [확인].
- 공용 워커가 붐비면 **503 "Worker local total request limit reached (16/16)"** → 재시도·백오프 필수, 데모는 로컬 서빙이나 여유 있는 엔드포인트로 [확인].

역할별 호출 가능 모델(API ID, 82개 중 발췌):

| 역할 | 모델 | 메모 |
|---|---|---|
| 기획·추론·에이전트 | `nvidia/nemotron-3-ultra-550b-a55b` | 1M 컨텍스트, 도구호출. **Nemotron 3 중 한국어 공식 지원 유일** |
| 경량 서브에이전트 | `nvidia/nemotron-3-super-120b-a12b`, `nvidia/nemotron-3.5-lightning-30b-a3b`, `nvidia/nemotron-nano-3-30b-a3b` | 한국어 공식 목록에 없음 |
| 멀티모달(영상·이미지·음성) | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | mp4 2분, 이미지 여러 장, JSON 출력. **영어 전용**. 분류 작업은 추론 off가 빠르고 정확했음 [확인] |
| 이미지 이해(대안) | `meta/llama-3.2-90b-vision-instruct`, `nvidia/vila`, `microsoft/phi-3-vision-128k-instruct`, `moonshotai/kimi-k3`, `z-ai/glm-5.3-flash`, `deepseek-ai/deepseek-v4.1-flash` | |
| 물리·영상 추론 | `nvidia/cosmos-reason2-8b` | 계정별 접근 확인 필요 |
| 임베딩 | `nvidia/nemotron-3-embed-1b`(다국어·한국어), `nvidia/llama-nemotron-embed-vl-1b-v2`(멀티모달), `nvidia/nv-embedqa-mistral-7b-v2` | 리랭커 API는 없음 |
| 문서 파싱 | `nvidia/nemotron-parse-2.0` | 웹은 다운로드 표시지만 API 호출 가능 |
| 안전·가드레일 | `nvidia/nemotron-3.5-content-safety`, `nvidia/llama-3.1-nemoguard-8b-content-safety`, `nvidia/llama-3.1-nemoguard-8b-topic-control`, `nvidia/llama-3.1-nemotron-safety-guard-8b-v3`, `meta/llama-guard-4-12b` | |
| 번역 | `nvidia/riva-translate-4b-instruct-v2` | 한국어 지원 |
| 기타 | `nvidia/ai-synthetic-video-detector`(AI 생성 영상 탐지), `nvidia/nvclip` | |

웹 배지와 실제가 다르다: 웹 "Free Endpoint"여도 API 목록에 없는 모델(cosmos3 계열)이 있고, "Downloadable"만 표시돼도 API로 되는 모델(nemotron-parse 등)이 있다. **항상 `/v1/models`와 실제 호출로 확인.**

### 5.2 SKILL (에이전트 스킬, SKILL.md 규격)
- 설치: `npx skills add NVIDIA/skills --skill <이름> --agent claude-code|codex|cursor` (패키지 설치이므로 사전 확인). 저장소 github.com/NVIDIA/skills.
- 주제 무관하게 쓸 만한 것:

| 범주 | 스킬 |
|---|---|
| 스킬 찾기·거버넌스 | `nvidia-skill-finder`, **`skill-card-generator`**(우리 스킬의 거버넌스 카드 → Skill Spector 스토리) |
| 근거 검색(RAG) | `nemo-retriever`(로컬 LanceDB), `nemo-retriever-mcp`, `rag-blueprint`, `rag-eval`(RAGAS), `rag-perf`, `nemotron-retrieval-recipes` |
| 안전 | **`nemotron-policy-generator`**(content-safety 가드레일용 맞춤 정책 생성), `nemoclaw-user-guide` |
| 관측·미들웨어 | **NeMo Relay** 10종(`nemo-relay-install`, `-instrument-calls`, `-plugin-observability`, …: 도구·LLM 호출 감싸기, 이벤트, 가드레일 미들웨어) |
| 데이터 | **`data-designer`**(합성 데이터 생성) |
| 심층 조사 | `aiq-research`, `aiq-deploy`(AI-Q Blueprint) |
| 영상 | VSS 18종(`vss-ask-video`, `vss-summarize-video`, `vss-generate-video-report`, …), DeepStream |
| 음성 | `nemotron-speech`, `nemotron-voice-agent-builder` |
| 최적화·데이터 | `cuopt-*`(경로·스케줄 최적화), `accelerated-computing-cudf` |
| 모델 맞춤 | `nemotron-customize`, `nemo-automodel-*` |

- 카탈로그에 **NeMo Agent Toolkit·Evaluator·Guardrails 이름의 스킬은 없다** → 해당 기능이 필요하면 각 제품을 직접 쓰거나 NeMo Relay로 대체, 본선 가용성 확인.

### 5.3 블루프린트(참조 구현) 33개 중 에이전트형
RAG Blueprint, NVIDIA Deep Researcher(AI-Q), Video Search and Summarization(VSS) Agent, **NemoClaw for OpenClaw / Hermes / LangChain Deep Agents**, Nemotron Voice Agent, Multi-Agent Intelligent Warehouse, Ambient Healthcare Agents, AI Factory Operations Agent, Financial Fraud Detection, Quantitative Signal Discovery Agent, Telecom Network Configuration Planning Agent, Vulnerability Analysis for Container Security, Retail Shopping Assistant / Agentic Commerce, Content Localization. → **이미 있는 블루프린트를 그대로 내면 독창성 점수가 없다.** 부품으로 가져와 도메인에 맞게 조합한다.

### 5.4 실행 환경·비용
| 경로 | 비용 | 용도 |
|---|---|---|
| build.nvidia.com API | 무료(40 RPM, 혼잡 시 503) | 개발·시험 [확인] |
| Brev(brev.nvidia.com) | 선불 크레딧. L40S 48GB 시간당 $1.06~9.09(보통 $1.7~2.2), CPU 인스턴스 다수 [확인] | NemoClaw 실행용 저가 머신, 자체 NIM 서빙. "정지 불가" 인스턴스는 삭제할 때까지 과금 |
| 통합(Integrations) 12곳: Baseten, Deep Infra, Fireworks, OpenRouter, Together 등 | 각 판매처 요금 | 안정적인 유료 엔드포인트가 필요할 때 [확인: 계정 화면] |
| NIM 내려받아 자체 실행 | **Developer Program 회원은 연구·개발·시험용으로 GPU 16개까지 무료 라이선스** [공식] | 본선 DGX Spark·L40S |
| NVIDIA AI Enterprise | 운영(실서비스)용 유료 라이선스. 90일 평가판은 **회사 메일 필요** [공식/제3자] | 발표의 "확장·사업화" 슬라이드용 |

---

## 6. 주제 선정 기준 (다른 주제에도 적용)

점수 = 채점 항목 × 가중치 [추정]. 아래 질문에 "예"가 많을수록 좋다.

| 채점 연결 | 질문 |
|---|---|
| 1 기술 심도 | 모델이 **2종 이상 역할별로** 필요한가(예: 멀티모달 인식 + 추론 + 임베딩 + 안전)? |
| 1 기술 심도 | 여러 단계를 **계획·재조사**해야 풀리는가(한 번 질문으로 안 끝나는가)? |
| 1 기술 심도 | **보안·개인정보가 필수**라 OpenShell 정책이 자연스러운가(의료·금융·보험·공공·법률·보안운영)? |
| 1 기술 심도 | 반복 업무에서 **스킬이 쌓일** 여지가 있는가? |
| 2 산업가치 | 페인포인트를 **돈·시간 숫자**로 말할 수 있는가(공식 통계 인용)? |
| 2 산업가치 | 실제 현업자가 매일 하는 일인가, 결제자가 분명한가? |
| 3 완성도 | **공개 데이터나 합성 데이터로 재현**할 수 있는가? 정답 라벨이 있는가? |
| 3 완성도 | 범위가 좁아서 마감 안에 **끝까지 돌아가는 데모**가 되는가? |
| 4 독창성 | build.nvidia.com 블루프린트를 그대로 복제한 것이 아닌가? 한국 특화 요소(제도·데이터·언어)가 있는가? |

피할 주제: 범용 챗봇·RAG Q&A, 블루프린트 복붙, 데이터가 없어 시연이 가짜인 주제, 보안이 끼워 넣기로 보이는 주제, 모델 1개 호출로 끝나는 주제.

---

## 7. 채점 항목별 체크리스트 (제출 전 점검)

**1. NVIDIA Agent 기술 활용 심도**
- [ ] DLI 코스 수료, 코스 학습목표 5개 각각이 데모의 어디에 있는지 표로 설명
- [ ] NemoClaw 하네스(OpenClaw/Hermes/Deep Agents) 위에서 실행
- [ ] OpenShell 정책 파일 공개(파일·네트워크·자격증명), 차단 로그를 데모에 표시
- [ ] 에이전트별 신원·권한 분리(최소 권한)
- [ ] NVIDIA 공식 스킬 2개 이상 실제 사용 + 도메인 스킬 직접 작성(SKILL.md) + 스킬 카드
- [ ] build.nvidia.com 모델 3종 이상을 역할별로 사용(추론·멀티모달·임베딩·안전), 호출 트레이스
- [ ] 스킬 라이브러리가 쌓이는 장면(피드백 → 새 스킬 → 다음 건 재사용)

**2. 실용성·산업가치·혁신성**
- [ ] 공식 통계로 문제 규모 제시, 효과를 원·시간으로 환산(가정 명시)
- [ ] "AI가 결정"이 아니라 "근거와 초안 → 사람 승인" 포지셔닝(규제 산업일수록)

**3. 완성도**
- [ ] `git clone` 후 문서대로 재현(고정 시드, 데이터 다운로드 스크립트, 원본 재배포 금지 준수)
- [ ] 정량 평가(정답 대비 지표, 건당 토큰·지연·비용)
- [ ] 실패 처리: 모델 오류·503·타임아웃 재시도, 비용 상한
- [ ] 3분 데모 영상 + 실행 가능한 데모 화면

**4. 커스터마이징·독창성**
- [ ] 도메인 데이터·매핑표·정책·스킬을 직접 만든 흔적
- [ ] 한국 제도·데이터·언어 특화

---

## 8. 3분 데모 구성 템플릿

1. (20초) 문제와 숫자: 누가, 얼마나 손해 보는가.
2. (60초) 정상 케이스: 입력 → 에이전트 계획 → 스킬·모델 호출 트레이스 → 근거 달린 결과 → 사람 승인.
3. (40초) 이상·예외 케이스: 에이전트가 재조사하거나 다른 에이전트에 위임하는 장면.
4. (30초) **보안 장면**: OpenShell이 외부 전송을 차단한 로그, 승인 후에만 나가는 행동.
5. (30초) 성장 장면: 사람 피드백이 새 스킬이 되어 다음 건에 적용.
6. (20초) 평가 대시보드: 정확도, 처리 시간, 건당 비용, 확장 계획(로컬 NIM, AI Enterprise).

---

## 9. 흔한 함정 (실제로 겪은 것 포함)

- 웹 배지만 믿고 모델을 고름 → 호출해 보니 404. **`/v1/models` + 실제 1회 호출로 확인** [확인].
- 무료 API 혼잡(503)으로 평가가 멈춤 → 재시도·캐시·호출 상한을 처음부터 코드에 [확인].
- 멀티모달 모델이 **영어 전용** → 한국어 후보표를 줬더니 오답, 영어로 바꾸자 정답(표본 1건) [확인]. 언어 지원을 모델 카드에서 먼저 확인.
- 추론(thinking) 모드는 출력 토큰을 다 써서 답을 못 냄 → 분류·추출은 추론 off부터 [확인].
- 공개 데이터 라벨의 채움률·스키마가 문서와 다름 → **파일을 직접 열어 확인** 후 코드 작성 [확인].
- 비용: 유료 경로(Brev·판매처)는 실행 전 금액을 추정해 승인받는다. 정지 불가 인스턴스 삭제 잊지 말 것.
- 범위 폭주: 채점과 무관한 정밀도 향상(판례 RAG, 자체 GPU 서빙 등)은 뒤로.

---

## 10. 아직 확인하지 못한 것 (새 세션에서 먼저 확인)

- 제출 마감, 팀 인원, **제출물 형식**(저장소·영상·URL), 심사위원이 직접 실행하는지.
- DLI 코스 수료 증빙 방식, 코스 안의 실제 실습 내용(하네스 선택, 스킬 라이브러리 구현 방식).
- NemoClaw/OpenShell의 Windows 지원(WSL2 실험적) → 로컬 WSL2 vs Brev CPU 인스턴스 선택.
- OpenShell Policy Advisor·승인 흐름의 세부, 에이전트 신원(identity) 설정 방법.
- NeMo Agent Toolkit·NeMo Evaluator·NeMo Guardrails를 "전제 조건(NeMo 활용)" 충족용으로 어떻게 넣을지, 본선 가용성.
- 무료 API 약관(NVIDIA API Trial Terms)의 대회 사용 제한 여부.

---

## 11. 부록: 현재 프로젝트(자동차보험 대물 손해사정)를 이 틀에 대입

| 틀 | 적용 |
|---|---|
| 보안 필수성 | 번호판·얼굴·연락처(개인정보), 보험사기 조사 → OpenShell 필수 |
| 역할 에이전트 | 과실 / 손해액 / SIU / 보고서 |
| 모델 | Omni(영상·사진, 영어), Ultra(한국어 사정서), embed(인정기준 검색), content-safety |
| 도메인 스킬 | 과실표 조회, 충돌부위 대조, 견적 대조, 라우팅, 사정서 작성 (`agent/tools/`를 SKILL.md로) |
| 정책 | 네트워크: NVIDIA API만. 파일: 사건 폴더만. 외부 발송(정비공장 조정 요청)은 승인 후 |
| 지속 스킬 | 담당자 수정 → "정비공장별 과다 청구 패턴" 스킬 생성 |
| 강점 | 실제 공공 데이터 + 실제 손해사정 결과를 정답으로 한 정량 평가, 재현 스크립트·감사 |
| 약점 | 에이전트 층(NemoClaw·스킬·OpenShell) 미구현, 영상 인식 정확도 미검증 |

상세: `docs/HANDOFF.md`(배경·데이터), `docs/ARCHITECTURE.md`(파이프라인).

---

## 출처
- DLI 코스: https://learn.nvidia.com/courses/course-detail?course_id=course-v1:DLI+S-FX-43+V1
- NemoClaw: https://www.nvidia.com/en-us/ai/nemoclaw/
- OpenShell: https://github.com/NVIDIA/openshell , https://docs.nvidia.com/openshell/how-it-works/policies/overview , https://docs.nvidia.com/openshell/tutorials/first-network-policy
- NIM 개발자 무료 접근: https://developer.nvidia.com/blog/access-to-nvidia-nim-now-available-free-to-developer-program-members
- AI Enterprise 평가판: https://enterpriseproductregistration.nvidia.com/?LicType=EVAL&ProductFamily=NVAIEnterprise
- build.nvidia.com 카탈로그(사용자 수집): `docs/reference/build_nvidia_catalog.xlsx`
