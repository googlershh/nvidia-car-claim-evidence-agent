import { SuperDoc } from 'superdoc';
import { Document, Packer, Paragraph, TextRun, Header, Footer, PageNumber, AlignmentType, BorderStyle } from 'docx';
import 'superdoc/style.css';
import './style.css';

const $ = s => document.querySelector(s);
const origin = location.origin;
const mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
let editor, current, ready = false, revision = 0, cached, cachedRevision = -1, exporting;
const notify = (type, data = {}) => parent.postMessage({ channel: 'claim-docx', type, key: current?.key, ...data }, origin);
const status = text => { $('#status').textContent = text; };
const enable = value => document.querySelectorAll('.filebar button,.statusbar button').forEach(b => b.disabled = !value);
const safeName = name => name.replace(/[\\/:*?"<>|]/g, '-').slice(0, 140);

async function makeDocument({ artifact: a, caseTitle, caseId }) {
  const teal = '176B57', grey = '65746E';
  const body = a.body.split('\n').filter(line => line.trim()).map(line => {
    const heading = /^(\d+[.)]\s|조사 목적$|검토 내용$|미확정 사항$|다음 행동$|협의 요청 사항$|확인 요청$)/.test(line);
    const note = line.startsWith('※');
    return new Paragraph({
      spacing: { before: heading ? 210 : 50, after: heading ? 110 : 100, line: 330 },
      keepNext: heading,
      children: [new TextRun({ text: line, size: heading ? 26 : note ? 19 : 23, bold: heading, color: heading ? teal : note ? grey : '33463F', font: 'Arial' })],
    });
  });
  const doc = new Document({
    creator: '사건노트', title: a.title, description: '팀 리뷰용 예시 협의 문서',
    styles: { default: { document: { run: { font: 'Arial', size: 23 }, paragraph: { spacing: { line: 330 } } } } },
    sections: [{
      properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1000, right: 1000, bottom: 1000, left: 1000, header: 440, footer: 440 } } },
      headers: { default: new Header({ children: [new Paragraph({
        border: { bottom: { color: 'D8E3DD', style: BorderStyle.SINGLE, size: 4, space: 8 } },
        children: [new TextRun({ text: '사건노트   /   '+(a.kind === 'external' ? '협의 근거 문서' : '내부 검토 보고서'), size: 18, color: grey })],
      })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: caseId+'  ·  v'+a.version+'    |    ', size: 17, color: grey }), new TextRun({ children: [PageNumber.CURRENT], size: 17, color: grey })],
      })] }) },
      children: [
        new Paragraph({ spacing: { before: 120, after: 180 }, children: [new TextRun({ text: a.kind === 'external' ? 'NEGOTIATION BRIEF' : 'INTERNAL REPORT', size: 18, color: grey, characterSpacing: 30 })] }),
        new Paragraph({ spacing: { after: 240 }, children: [new TextRun({ text: a.title, bold: true, size: 38, color: teal })] }),
        new Paragraph({ spacing: { after: 220 }, border: { bottom: { color: teal, size: 10, style: BorderStyle.SINGLE, space: 12 } }, children: [new TextRun({ text: `${caseTitle}  /  ${caseId}  /  검토 전 초안 v${a.version}`, size: 19, color: grey })] }),
        ...body,
      ],
    }],
  });
  return Packer.toBlob(doc);
}

function reportError(error) {
  console.error('DOCX editor:', error);
  status('문서를 열지 못했습니다. 다시 열어 주세요.');
  notify('error', { message: 'DOCX 문서를 열지 못했습니다.' });
}
async function openDocument(data) {
  ready = false; enable(false); revision = 0; cachedRevision = -1; current = data;
  editor?.destroy(); $('#editor').replaceChildren(); $('#toolbar').replaceChildren();
  status('DOCX 문서를 여는 중…');
  $('#filename').textContent = data.name || `${data.artifact.title}.docx`;
  const blob = data.blob || await makeDocument(data);
  cached = blob; cachedRevision = 0;
  await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error('문서 열기 시간이 초과되었습니다.')),30000);
  const fail=error=>{clearTimeout(timer);reject(error instanceof Error?error:Error('DOCX 문서를 열 수 없습니다.'));};
  editor = new SuperDoc({
    selector: '#editor', document: blob, title: data.artifact.title,
    documentMode: 'editing', contained: true,
    user: { name: '보상 담당자', email: 'reviewer@example.invalid' },
    telemetry: { enabled: false },
    zoom: { mode: 'fit-width', fitWidth: { min: 25, max: 100, padding: 32 } },
    ui: { toolbar: { container: '#toolbar', responsiveTo: 'container', excludeItems: ['track-changes-accept-selection','track-changes-reject-selection','ruler'], strings: { bold:'굵게',italic:'기울임',underline:'밑줄',strikethrough:'취소선',undo:'실행 취소',redo:'다시 실행',search:'찾기',image:'그림',table:'표',link:'링크','font-family':'글꼴','font-size':'글자 크기','text-color':'글자 색','highlight-color':'강조 색','document-mode-editing':'편집','document-mode-viewing':'읽기','document-mode-suggesting':'변경 제안' } }, comments: false, ruler: false },
    onReady: () => { ready = true; enable(true); status(data.blob ? '작업 사본 복원됨' : '편집 가능 · A4'); notify('ready'); clearTimeout(timer);resolve(); },
    onEditorUpdate: () => { if (!ready) return; revision++; status('편집 중 · 다운로드로 보관'); notify('dirty'); },
    onContentError: ({ error }) => {reportError(error);fail(error);},
    onException: event => { if (!ready) {reportError(event.error || event);fail(event.error || event);} },
  });
  });
}
async function snapshot() {
  if (!ready) throw new Error('문서가 열릴 때까지 기다려 주세요.');
  if (cachedRevision === revision) return cached;
  if (exporting) { await exporting; return snapshot(); }
  const exportedRevision = revision;
  exporting = editor.export({ triggerDownload: false });
  try {
    const blob = await exporting;
    if (!(blob instanceof Blob)) throw new Error('DOCX 파일을 만들지 못했습니다.');
    cached = blob; cachedRevision = exportedRevision; return blob;
  } finally { exporting = null; }
}
window.addEventListener('message', async event => {
  if (event.origin !== origin || event.source !== parent || event.data?.channel !== 'claim-docx') return;
  const data = event.data;
  try {
    if (data.type === 'open') await openDocument(data);
    if (data.type === 'snapshot') notify('snapshot', { requestId: data.requestId, blob: await snapshot(), name: $('#filename').textContent });
  } catch (error) { notify('error', { requestId: data.requestId, message: error.message }); status(error.message); }
});
$('#download').addEventListener('click', async () => {
  enable(false);
  try {
    const blob = await snapshot();
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = safeName($('#filename').textContent.replace(/\.docx$/i, '')+'-편집본.docx'); link.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    status('DOCX 다운로드 완료'); notify('downloaded');
  } catch (error) { status('다운로드 실패 · '+error.message); }
  finally { enable(ready); }
});
$('#open-file').addEventListener('click', () => $('#file-input').click());
$('#file-input').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  if (!file.name.toLowerCase().endsWith('.docx') || file.size > 20 * 1024 * 1024) { status('20MB 이하 DOCX 파일을 선택해 주세요.'); return; }
  try {
    // Keep the previous working copy available if importing the new document fails.
    const previous = { ...current, blob: await snapshot(), name: $('#filename').textContent };
    try { await openDocument({ ...current, blob: file, name: file.name }); notify('dirty'); }
    catch (error) { await openDocument(previous); throw error; }
  } catch (error) { status('문서 열기 실패 · '+error.message); }
  event.target.value = '';
});
$('#fit').addEventListener('click', () => {document.body.classList.remove('manual-zoom');editor.setZoomMode('fit-width');});
$('#actual').addEventListener('click', () => {document.body.classList.add('manual-zoom');editor.setZoom(100);});
$('#expand').addEventListener('click', () => notify('expand'));
window.addEventListener('keydown', e=>{if(e.key==='Escape')notify('collapse');});
window.addEventListener('beforeunload', () => editor?.destroy());
notify('boot');
