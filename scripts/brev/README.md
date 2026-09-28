# Brev 인스턴스 구성 (VSS + NemoClaw)

GPU 인스턴스 한 대에 VSS Blueprint와 NemoClaw를 함께 올리는 절차입니다. 본선 DGX Spark에서도 같은 순서를 씁니다.
2026-09-28 Brev MassedCompute RTX A6000 48GB(CPU 6, RAM 48GB, SSD 256GB, 시간당 $0.68, **정지 불가 → 쓰고 나면 삭제**)에서 확인했습니다.
아래 "막힌 점"은 그날 실제로 실패한 것들이고, 스크립트가 모두 미리 처리합니다. 이 순서로 샌드박스를 새로 만들어 **연결 가이드 전 셀 통과(대시보드 포함)**를 확인했습니다.

## 순서

| 단계 | 어디서 | 명령 |
|---|---|---|
| 0 | 이 PC(WSL) | `brev login` → `bash scripts/brev_sync.sh claim-agent-a6000` (코드 + 실행 데이터 약 780MB) |
| 1 | 인스턴스, **사람이 직접** | API 키 파일 만들기 (아래) |
| 2 | 인스턴스 | `bash scripts/brev/00_prereqs.sh` |
| 3 | 인스턴스 | `bash scripts/brev/01_deploy_vss.sh` (모의 실행은 `-d`. 컨테이너 약 38GB, 20분 남짓) |
| 4 | 인스턴스 | `bash scripts/brev/02_connect_nemoclaw_vss.sh` (NemoClaw 설치 + VSS 연결 + 복구, 20~30분) |
| 5 | 인스턴스 | `bash scripts/brev/03_install_claim_skill.sh demo` (우리 `claim-evidence` 스킬과 도구 코드 설치) |
| 6 | 인스턴스 | (권장) OpenRouter 키를 키 파일에 추가한 뒤 `bash scripts/brev/04_use_openrouter.sh demo` (에이전트·VSS LLM을 유료 엔드포인트로, P10 대응) |
| 7 | 인스턴스 | `bash scripts/brev/vss_ask_clip.sh F016` (VSS 동작 확인) |

접속은 `brev shell claim-agent-a6000`. 스크립트는 저장소 루트(`~/car-accident-model`)에서 실행합니다.

### API 키 파일 (1단계)

키는 채팅이나 스크립트에 넣지 않고 권한 제한 파일에 둡니다.

```bash
read -rsp "NVIDIA API key: " K && printf 'export NVIDIA_API_KEY=%s\n' "$K" > ~/.nvidia_keys && chmod 600 ~/.nvidia_keys && unset K
```

build.nvidia.com 키(`nvapi-`)가 NGC 레지스트리(`nvcr.io`) 로그인에도 그대로 통합니다(별도 NGC 키 불필요).

## 구성

- VSS base 프로필: 영상 모델 Cosmos3 Nano Reasoner(BF16)를 GPU에서 직접 서빙(메모리 70%), VSS 에이전트의 LLM은 Nemotron 3.5 Lightning(build.nvidia.com), `-H OTHER`(A6000은 VSS 하드웨어 목록에 없음).
- NemoClaw: VSS 저장소의 공식 가이드 `deploy/docker/scripts/deploy_nemoclaw.ipynb`를 `run_nemoclaw_notebook.py`가 셀 순서대로 실행합니다. 모델 제공자는 (c) build.nvidia.com만 쓰고 (a)(b) 셀은 건너뜁니다. 샌드박스 이름 `demo`, NemoClaw v0.0.127(가이드 고정), 에이전트 OpenClaw, 모델 Nemotron 3 Super.
- 결과(2026-09-28): 샌드박스 안의 `vss` 명령이 agent·vst·rt_vlm에 연결되고, 스킬 vss-ask-video, vss-generate-video-report, vss-manage-alerts, vss-manage-video-io-storage가 활성화됩니다. 에이전트에게 목표만 주면 `vss vios list`, `vss vlm run --sensor …` 같은 명령을 스스로 골라 실행합니다.

## 막힌 점과 대응 (스크립트에 반영됨)

| # | 증상 | 원인 | 대응 |
|---|---|---|---|
| P1 | NemoClaw 대시보드 포워딩 실패("launch-readiness epoch could not be safely revalidated … secure OS runtime authority"), 에이전트가 게이트웨이 대신 내장 방식으로 우회("pairing required: … more scopes") | SSH 비로그인 세션에 systemd 사용자 버스와 `/run/user/<uid>`가 없는 상태에서 NemoClaw를 설치 → 실행 준비 기록을 신뢰할 수 없어 격리(문서상 최대 24시간) | `00_prereqs.sh`가 **NemoClaw 설치 전에** `loginctl enable-linger`와 `XDG_RUNTIME_DIR`를 설정 |
| P2 | 샌드박스 온보딩 실패: 샌드박스 컨테이너가 게이트웨이(172.18.0.1:8080)에 닿지 못함 | ufw가 Docker 브리지 트래픽을 막음 | Docker 브리지 대역 → 8080만 허용하는 ufw 규칙. 외부에서 열린 포트는 SSH(22)뿐 |
| P3 | 가이드 보조 스크립트 `ImportError: StrEnum` | Ubuntu 22.04의 Python 3.10 | `uv`로 Python 3.12 + IPython 가상환경(`~/nbenv`) |
| P4 | VSS 에이전트의 LLM 호출이 404 "page not found" | 에이전트 설정이 주소 끝에 `/v1`을 붙이는데 `LLM_ENDPOINT_URL`에도 `/v1`이 있었음 | `LLM_ENDPOINT_URL=https://integrate.api.nvidia.com` |
| P5 | 가이드 실행 중 "pre-upgrade backup failed" | 가이드 전에 NemoClaw를 따로 설치해 둔 샌드박스가 있었음(버전도 달랐음) | NemoClaw를 따로 설치하지 않고 가이드가 설치하게 함 |
| P6 | 온보딩 마지막 점검 "bounded CLI scope warm-up could not run" | P1과 같은 원인으로 추정 | P1 선처리. 그래도 실패하면 `--after-onboard`로 남은 단계(정책, `vss configure`, 웹훅)만 실행 |
| P7 | 샌드박스에서 `/vst` 503, 에이전트가 "vst service absent" | 가이드의 Docker 고정 단계에서 Docker 데몬이 재시작되며 VSS의 VST 서비스가 멈춤 | `02_connect…`가 끝에 `docker compose up -d`로 VSS 복구 후 `vss configure` 재실행 |
| P8 | 스크립트 뒷부분이 실행되지 않음 | `ssh … bash -s <<EOF` 안에서 `ffmpeg`·`openshell sandbox exec`가 표준입력(스크립트)을 읽어 버림 | `ffmpeg -nostdin`, `openshell sandbox exec … </dev/null` |
| P9 | VST 업로드 거부 "Video encode format not supported: mpeg4" | 데이터셋 영상 코덱 | H.264로 변환 후 업로드(`vss_ask_clip.sh`) |
| P10 | 에이전트가 "The AI service is temporarily overloaded" | build.nvidia.com 무료 엔드포인트 과부하. 에이전트는 목표 하나에 모델을 10번 넘게 부름 | 유료 엔드포인트(OpenRouter 등)나 자체 서빙으로 전환 검토 |
| P11 | 설정을 고친 뒤에도 에이전트가 예전 실패를 답함 | 같은 대화 세션의 기억 | 시험할 때 `openclaw agent --session-id <새 id>` |
| P12 | 완료를 기다리는 감시 작업이 끝나지 않음 | `pgrep -f 이름`이 검사 명령 자신과 일치 | 프로세스 대신 로그의 완료 표식으로 판단 |
| P13 | `nemoclaw inference set --provider openrouter` → "provider 'openrouter-api' not found" | OpenRouter 제공자는 온보딩 마법사에서만 등록됨 | `openshell provider create --type openai …`로 직접 등록 후 `inference set`(`04_use_openrouter.sh`) |
| P14 | OpenRouter에서도 "API rate limit reached" | 유료 모델도 업스트림 한도에 걸림(원인 미확인) | 같은 세션 id로 이어서 실행하면 앞 단계 결과를 다시 쓴다 |

## 비용

- 인스턴스 시간당 $0.68. 크레딧이 다 떨어지면 Brev가 인스턴스와 데이터를 자동 삭제합니다.
- 다시 만들 때 드는 시간: 0~5단계 합쳐 약 1시간(대부분 VSS 컨테이너 다운로드와 NemoClaw 샌드박스 이미지 빌드).
