# 사건노트 — 공유용 사건 상세 데모

대시보드 없이 사건 상세만 공개하는 정적 사이트입니다. Workers에는 `demo/dist/`만 배포합니다. Python 업무 API, NemoClaw/VSS, 데이터베이스, 이메일 계정과 연결하지 않습니다.

## 화면과 데이터

- 왼쪽: 영상, 실제 영상 캡처 3장, 양측 가상 진술, 가상 견적·메일, 기준 적용 검토 메모.
- 중앙: 종합 조사, 근거별 원문, 진술 대조 3개 쟁점, 조사 일지, 준비된 시나리오 질의.
- 오른쪽: 실제 DOCX 편집기. 협의 요청서와 종합 보고서의 작업 사본을 각각 유지하고 다운로드합니다.
- 데스크톱에서는 자료 목록을 제외한 공간을 근거와 문서가 절반씩 사용합니다.
- `demo.mp4`는 제공 영상이며, 나머지 사건 내용은 장면에 맞춘 합성 사례입니다. 과실비율·인정액을 확정하거나 실제 AI 실행 결과로 표시하지 않습니다.
- 대화와 편집본은 현재 페이지 메모리에만 보관합니다. 새로고침 전 필요한 DOCX를 다운로드합니다.

## 로컬 실행

Node.js 22+, Python 3.10+가 필요합니다.

```bash
npm ci --prefix demo
npm ci --prefix demo/editor
npm run build --prefix demo
npm run preview --prefix demo
```

`http://127.0.0.1:8767/`에서 확인합니다. 공유용으로 제공된 영상과 캡처는 사용자의 명시적 요청에 따라 `demo/media/`에 포함했습니다. SHA-256을 빌드 시 검증합니다. 원본 데이터셋 폴더나 다른 사건 영상은 포함하지 않습니다.

## Workers 화면에서 GitHub를 연결한 경우

이 PR을 main에 병합한 후 Workers의 Build settings를 다음과 같이 지정합니다.

| 설정 | 값 |
|---|---|
| Worker 이름 | `case-note-demo` |
| Production branch | `main` |
| Root directory | `demo` |
| Build command | `npm ci && npm ci --prefix editor && npm run build` |
| Deploy command | `npx wrangler deploy` |
| Enable Preview builds | 초기 공유는 끄기 |
| Protect with Cloudflare Access | 로그인 없이 공유하려면 끄기 |

영상까지 저장소에 포함했으므로 GitHub 토큰이나 별도의 미디어 업로드 설정은 필요하지 않습니다.

Wrangler 설정에 `dist/`를 정적 자산 폴더로 지정해 두었습니다. 별도 Worker 코드·DB·AI API 키는 필요하지 않습니다. 이 방식을 사용하면 아래 GitHub Actions 배포용 Cloudflare 변수·토큰은 설정하지 않습니다. Actions는 검증만 수행하고 실제 배포는 Cloudflare Git 연결에서 실행합니다.

## GitHub Actions에서 Workers를 배포하는 대안

GitHub Actions에서 빌드·브라우저 검증을 통과한 정적 번들을 Workers에 배포합니다. SSH 서버와 터널은 필요하지 않습니다. Cloudflare의 별도 Git 저장소 연결도 필요하지 않습니다.

최초 설정:

1. Cloudflare 계정의 **Account ID**를 확인합니다.
2. 해당 계정으로 범위를 한정한 **Edit Cloudflare Workers** API 토큰을 만듭니다.
3. GitHub 저장소 → **Settings → Secrets and variables → Actions**에 등록합니다.
   - **Variables**: `CLOUDFLARE_ACCOUNT_ID`
   - **Secrets**: `CLOUDFLARE_API_TOKEN` (토큰을 코드나 대화에 붙여 넣지 않습니다.)
4. 데모 PR을 `main`에 병합합니다. `Case demo — build and deploy`가 `case-note-demo` Worker를 생성/갱신합니다.
5. 이미 병합한 뒤 계정을 설정했다면 **Actions → Case demo — build and deploy → Run workflow → main**으로 실행합니다.

계정 ID가 미설정이면 검증과 번들 생성까지 실행하고 배포 작업은 건너뜁니다. PR에서는 배포 토큰을 사용하지 않습니다. 성공한 배포 로그에 실제 `workers.dev` 주소가 표시됩니다.

정적 파일만 등록하므로 `/dashboard`, `/cases`, `/api/cases`에 해당하는 화면이나 API가 없습니다. 알려지지 않은 경로는 404이며, 이전 대시보드 해시 링크도 상세 화면을 벗어나지 않습니다.

수동 배포는 `demo/`에서 `npx wrangler login` 후 `npm run deploy`로 할 수 있습니다. 이 경우에도 먼저 로컬 빌드가 필요합니다.

현재 GitHub 비공개 저장소의 요금제는 GitHub Pages를 지원하지 않아 Workers 배포를 기본으로 구성했습니다. 저장소 공개 범위를 바꾸지 않습니다.

## 검증

```bash
cd demo/editor && npx playwright install chromium && cd ../..
DEMO_URL=http://127.0.0.1:8767/ npm test --prefix demo
cd demo && npx wrangler deploy --dry-run
```

실제 영상 재생·탐색, 자료 7종, 질의·조사 일지, DOCX 편집·버전 전환·다운로드, 화면 크기 1280/768/390, 대시보드/API 경로 차단을 브라우저에서 검증합니다.

## 편집기 고지

SuperDoc 2.18.0(AGPL-3.0), docx 9.7.1(MIT), DOCX Engine 0.17.0(별도 라이선스)을 사용합니다. 빌드에 원문 라이선스·고지 및 통합 소스 ZIP을 포함하고 화면 하단에서 제공합니다. DOCX Engine은 독립 배포하지 않으며 SuperDoc 기반 평가 데모의 의존성으로 사용합니다.

참고: [Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/get-started/), [Workers의 GitHub Actions 배포](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/).
