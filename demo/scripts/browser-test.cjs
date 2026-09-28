const path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {createRequire}=require('node:module');
const {chromium}=createRequire(path.resolve(__dirname,'../editor/package.json'))('playwright');
(async()=>{
 const base=process.env.DEMO_URL||'http://127.0.0.1:18967/';
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1020},acceptDownloads:true});
 const errors=[],external=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('404'))errors.push(m.text())});
 page.on('request',r=>{if(/^https?:/.test(r.url())&&new URL(r.url()).origin!==new URL(base).origin)external.push(r.url())});
 await page.goto(base);
 const f=page.frameLocator('#docx');
 await f.locator('#status').filter({hasText:'편집 가능'}).waitFor({timeout:90000});
 await page.locator('#clip').evaluate(v=>new Promise(resolve=>{if(v.readyState>=1)resolve();else v.addEventListener('loadedmetadata',resolve,{once:true})}));
 assert.equal(Math.round(await page.locator('#clip').evaluate(v=>v.duration)),10);
 const layout=await page.evaluate(()=>{const r=s=>document.querySelector(s).getBoundingClientRect();return {e:r('.evidence').width,d:r('.document').width,chatBottom:r('.chat').bottom,workBottom:r('.workspace').bottom}});
 assert(Math.abs(layout.e-layout.d)<2);assert(layout.chatBottom<=layout.workBottom+1,'chat must remain visible in desktop workspace');
 await page.locator('[data-seek="8.8"]').click();
 await page.waitForFunction(()=>document.querySelector('#clip').currentTime>=8.8);
 await page.locator('#clip').evaluate(v=>v.pause());
 for(const id of ['frames','a','b','estimate','mail','criteria','video']){
  await page.locator('.materials [data-source="'+id+'"]').click();
  if(id==='estimate')await page.getByText('957,000',{exact:false}).first().waitFor();
  if(id==='frames')assert.equal(await page.locator('.frame-card').count(),3);
 }
 await page.locator('.materials [data-source="estimate"]').click();
 await page.getByRole('button',{name:'250,000원을 감액하면 되나요?',exact:true}).click();
 await page.locator('.message.answer').filter({hasText:'바로 감액하는 결론은 아닙니다'}).waitFor();
 const payload='<img src=x onerror="window.xss=1">';
 await page.locator('#question').fill(payload);await page.getByRole('button',{name:'질문 보내기',exact:true}).click();
 assert.equal(await page.evaluate(()=>window.xss),undefined);assert(await page.locator('.message.user').last().innerText()===payload);
 await page.getByRole('tab',{name:'진술 대조 3',exact:true}).click();
 assert.equal(await page.locator('.compare-card').count(),3);
 await page.locator('#journal-button').click();
 assert.equal(await page.locator('.journal-entry').count(),7);
 await page.locator('.materials [data-source="overview"]').click();
 await f.locator('.superdoc-page').getByText('1. 협의 목적',{exact:true}).click();
 await page.keyboard.press('Control+End');await page.keyboard.press('Enter');
 const marker='공유 데모 검토: 추가 영상 회신 후 재검토합니다.';
 await page.keyboard.insertText(marker);
 await f.locator('.superdoc-page').getByText(marker,{exact:true}).waitFor();
 const child=page.frames().find(x=>x.url().includes('docx-editor/'));
 await child.evaluate(()=>window.keepEditor='yes');
 await page.locator('.materials [data-source="a"]').click();
 assert.equal(await child.evaluate(()=>window.keepEditor),'yes');
 await page.locator('#document-select').selectOption('internal');
 await f.locator('#status').filter({hasText:'편집 가능'}).waitFor();
 assert.equal(await f.locator('.superdoc-page').getByText(marker,{exact:true}).count(),0);
 await page.locator('#document-select').selectOption('external');
 await f.locator('#status').filter({hasText:'작업 사본 복원됨'}).waitFor();
 await f.locator('.superdoc-page').getByText(marker,{exact:true}).waitFor();
 const downloadEvent=page.waitForEvent('download');await f.locator('#download').click();
 const download=await downloadEvent;await download.saveAs(path.join(os.tmpdir(),'share-demo-edited.docx'));
 await page.locator('#expand-doc').click();await page.locator('.document.expanded').waitFor();
 await page.keyboard.press('Escape');await page.locator('.document.expanded').waitFor({state:'detached'});
 for(const hash of ['dashboard','cases','connections','case/DEMO-002']){
  await page.evaluate(h=>{location.hash=h},hash);
  await page.waitForFunction(()=>location.hash==='');
  assert.equal(await page.getByRole('heading',{name:'건물 진입로 차량 접촉 분쟁',exact:true}).count(),1);
  assert.equal(await page.getByRole('heading',{name:'오늘의 업무',exact:true}).count(),0);
 }
 for(const route of ['dashboard','cases','connections','api/cases','web/index.html','.env','manifest.json','media/','case-note-demo.html']){
  const response=await page.request.get(new URL(route,base).href);assert.equal(response.status(),404,route);
 }
 const post=await page.request.post(new URL('api/cases',base).href,{data:{title:'must not persist'}});assert(post.status()>=400);
 for(const width of [1280,768,390]){
  await page.setViewportSize({width,height:900});await page.waitForTimeout(500);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'page overflow '+width);
  const b=await child.evaluate(()=>{const r=document.querySelector('.superdoc-page').getBoundingClientRect();return {left:r.left,right:r.right,w:innerWidth}});
  assert(b.left>=-1&&b.right<=b.w+2,'document overflow '+width+JSON.stringify(b));
  if(width===390)await page.screenshot({path:path.join(os.tmpdir(),'share-mobile.png'),fullPage:true});
 }
 await page.setViewportSize({width:1440,height:1020});
 await page.locator('.materials [data-source="overview"]').click();
 await page.screenshot({path:path.join(os.tmpdir(),'share-final.png'),fullPage:true});
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 console.log(JSON.stringify({base,checks:['video playback and seeking','seven sources and actual frame previews','50/50 workspace and visible chat','script injection escaped','three comparisons and question journal','DOCX editing and working copies','DOCX download','expand and Escape','dashboard hashes neutralized','private/API/directory routes blocked','responsive 1280/768/390'],errors,external}));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
