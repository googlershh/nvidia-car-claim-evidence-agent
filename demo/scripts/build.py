"""Package only the static case demo, its editor, licenses, and integration source."""
from pathlib import Path
from shutil import copy2, copytree, rmtree
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json

DEMO = Path(__file__).resolve().parents[1]
OUT = DEMO / 'dist'
MEDIA = DEMO / 'media'
manifest = json.loads((DEMO / 'media-manifest.json').read_text())
for name, expected in manifest['files'].items():
    p = MEDIA / name
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
        raise SystemExit(f'Missing or mismatched demo media: {name}. Restore the authorized demo/media files from git.')
if not (OUT / 'docx-editor/index.html').is_file():
    raise SystemExit('Build the DOCX editor first: npm run build --prefix demo/editor')
for p in OUT.iterdir():
    if p.name != 'docx-editor':
        rmtree(p) if p.is_dir() else p.unlink()
for p in (DEMO / 'site').iterdir():
    if p.is_file(): copy2(p, OUT / p.name)
copytree(MEDIA, OUT / 'media')
editor = OUT / 'docx-editor'
notices = editor / 'licenses'
notices.mkdir(exist_ok=True)
for package, names in {
    'superdoc': ['LICENSE', 'NOTICE'],
    '@superdoc/docx-engine': ['DOCX-ENGINE-LICENSE.md', 'NOTICE.md', 'THIRD_PARTY_NOTICES'],
    'docx': ['LICENSE'],
}.items():
    for name in names:
        copy2(DEMO/'editor/node_modules'/package/name, notices/(package.replace('/', '-')+'-'+name))
(editor / 'NOTICE.txt').write_text('''사건노트 DOCX 편집기 — 패키지 고지
SuperDoc 2.18.0: AGPL-3.0, https://github.com/superdoc/docx-editor
DOCX Engine 0.17.0: 별도 독점 라이선스, https://docs.superdoc.dev/resources/docx-engine-license
DOCX 9.7.1: MIT, https://github.com/dolanmiu/docx
원문 라이선스·고지: ./licenses/
사건노트 통합 소스 및 빌드 잠금 파일: ../integration-source.zip
브라우저 편집 및 다운로드만 지원합니다. 서버 저장 및 외부 발송은 하지 않습니다.
''')
with ZipFile(OUT/'integration-source.zip', 'w', ZIP_DEFLATED) as z:
    paths = [* (DEMO/'site').rglob('*'), * (DEMO/'scripts').rglob('*'), * (DEMO/'editor').rglob('*'), *DEMO.glob('*')]
    excluded = {'node_modules', 'dist', 'media', '.wrangler', '__pycache__'}
    for p in sorted(set(paths)):
        relative = p.relative_to(DEMO)
        if p.is_file() and not excluded.intersection(relative.parts) and not p.name.startswith('.'):
            z.write(p, Path('demo')/relative)
print(f'Built {OUT} with {len(list(OUT.rglob("*")))} public files/directories')
