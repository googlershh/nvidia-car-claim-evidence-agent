# Brev 인스턴스 구성 (VSS + NemoClaw)

개발용 GPU 인스턴스 한 대에 VSS Blueprint와 NemoClaw를 함께 올리는 절차입니다. 본선 DGX Spark에서도 같은 순서를 씁니다.
2026-09-28 Brev MassedCompute RTX A6000 48GB(CPU 6, RAM 48GB, SSD 256GB, 시간당 $0.68, 정지 불가 → 쓰고 나면 삭제)에서 확인했습니다.

## 0. 이 PC에서 (WSL)

```bash
# Brev CLI 설치(WSL, ~/.local/bin/brev) 후 로그인
brev login
# 코드와 실행 데이터(약 780MB) 동기화
bash scripts/brev_sync.sh claim-agent-a6000
```

## 1. 인스턴스에서: API 키 파일 (사람이 직접)

키는 채팅이나 스크립트에 넣지 않고 권한 제한 파일에 둡니다.

```bash
read -rsp "NVIDIA API key: " K && printf 'export NVIDIA_API_KEY=%s\n' "$K" > ~/.nvidia_keys && chmod 600 ~/.nvidia_keys && unset K
```

build.nvidia.com 키(`nvapi-`)가 NGC 레지스트리(`nvcr.io`) 로그인에도 그대로 통했습니다(별도 NGC 키 불필요).

## 2. NemoClaw

```bash
bash scripts/brev/01_install_nemoclaw.sh claim-agent
```

- 비대화식 설치, 제3자 소프트웨어 고지 동의, 모델 제공자 build.nvidia.com(기본 모델 Nemotron 3 Super).
- 겪은 문제
  - ufw가 켜진 호스트에서 샌드박스 컨테이너가 게이트웨이(172.18.0.1:8080)에 닿지 못함 → 스크립트가 Docker 브리지 대역만 허용하는 규칙을 추가.
  - SSH 비로그인 세션에는 systemd 사용자 버스가 없어 OpenShell 게이트웨이가 임시 방식으로 뜸 → `loginctl enable-linger`와 `XDG_RUNTIME_DIR` 설정.

## 3. VSS

```bash
bash scripts/brev/02_deploy_vss.sh -d   # 모의 실행
bash scripts/brev/02_deploy_vss.sh      # 배포 (컨테이너 약 38GB, 이 인스턴스에서 20분 남짓)
bash scripts/brev/vss_ask_clip.sh F016  # 평가 영상 한 건에 질문
```

- 구성: 영상 모델 Cosmos3 Nano Reasoner(BF16, GPU 메모리 70%)를 로컬 서빙, 언어 모델 Nemotron 3.5 Lightning은 build.nvidia.com. A6000은 VSS 하드웨어 목록에 없어 `-H OTHER`.
- 겪은 문제
  - `LLM_ENDPOINT_URL`에 `/v1`을 붙이면 에이전트 설정이 한 번 더 붙여 404 → `https://integrate.api.nvidia.com`로 지정.
  - VST가 데이터셋 영상 코덱(mpeg4)을 거부 → H.264로 변환해 업로드(`vss_ask_clip.sh`).
- 외부 노출: 컨테이너 포트는 0.0.0.0에 열리지만 제공사 방화벽으로 외부에서는 SSH(22)만 닿습니다(2026-09-28 확인). 화면은 SSH 터널로 봅니다(VSS UI 7777, NemoClaw 대시보드 18789).

## 4. NemoClaw ↔ VSS 연결

```bash
bash -c 'source ~/.nvidia_keys; export NVIDIA_API_KEY; ~/nbenv/bin/python scripts/brev/03_connect_nemoclaw_vss.py'
```

- VSS 저장소의 공식 가이드 `deploy/docker/scripts/deploy_nemoclaw.ipynb`를 셀 순서대로 실행합니다(모델 제공자 (a)(b) 셀은 건너뛰고 (c) build.nvidia.com만). VSS 스킬과 `vss` 명령이 들어 있는 이미지로 샌드박스(`demo`)를 새로 만들고 VSS 접근 정책을 적용합니다.
- 가이드 보조 스크립트가 Python 3.11 이상을 요구 → `uv venv --python 3.12 ~/nbenv` + IPython.
- 2026-09-28 결과: 온보딩 마지막 점검("bounded CLI scope warm-up")은 실패했지만 샌드박스는 Ready. `--after-onboard`로 이후 단계만 실행해 VSS 정책·`vss configure`·웹훅까지 성공, 스킬 vss-ask-video 등 4개 활성. 대시보드 포워딩(3.5)은 실패.
  ```bash
  bash -c 'source ~/.nvidia_keys; export NVIDIA_API_KEY; ~/nbenv/bin/python scripts/brev/03_connect_nemoclaw_vss.py --after-onboard'
  ```
- 자세한 기록은 [docs/HANDOFF.md](../../docs/HANDOFF.md) 7.3 "Brev 인스턴스 구성".
