
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';
const root=process.cwd(),out=path.join(root,'qa');
fs.mkdirSync(out,{recursive:true});
const child=spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+path.join(out,'chrome-cloud-workspace-profile'),'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
let stderr='';
const endpoint=await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(new Error('Chrome startup timeout '+stderr.slice(-1000))),20000);child.stderr.on('data',d=>{stderr+=d;const m=stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);if(m){clearTimeout(timeout);resolve(m[1])}});child.on('error',reject)});
const ws=new WebSocket(endpoint);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
let seq=0,session,events=[],pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result)}}else events.push(m)};
function call(method,params={},sid=session){const id=++seq;return new Promise((resolve,reject)=>{pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params,...sid?{sessionId:sid}:{}}))})}
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.text+': '+JSON.stringify(r.exceptionDetails.exception));return r.result.value}
const target=await call('Target.createTarget',{url:'about:blank'},null);session=(await call('Target.attachToTarget',{targetId:target.targetId,flatten:true},null)).sessionId;
await call('Page.enable');await call('Runtime.enable');await call('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});

const report=[],failures=[];
async function check(name,expression){const ok=!!await evaluate(expression);report.push({name,ok});if(!ok)failures.push(name);}
async function until(expression){for(let i=0;i<100;i++){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,150));}throw new Error('Condition timeout: '+expression);}

try {
 await call('Page.navigate',{url:'http://127.0.0.1:3012/baylab-figma.html#login'});
 await until("!!document.querySelector('#org-login')");
 await evaluate(`{const f=document.querySelector('#org-login');f.elements.organization.value='lkpi';f.elements.email.value='admin@example.test';f.elements.password.value='Valid-Test-Password-123';f.requestSubmit();}`);
 await until("!!document.querySelector('.main') && !document.querySelector('.main > [role=status]')");
 await check('cloud activation status reflects database capability',"document.body.innerText.includes('Formulasi, penilaian kandidat, dan eksperimen tersimpan di Supabase') && !document.body.innerText.includes('data lokal belum dipindahkan')");
 await call('Network.enable');
 await call('Network.setCookie',{name:'baylab_cloud_csrf',value:'a'.repeat(64),url:'http://127.0.0.1:3012/',httpOnly:true,sameSite:'Strict',path:'/'});
 for(const name of ['UI Candidate A','UI Candidate B']){
  await evaluate("go('formulasi')");
  await check('formulation form enabled '+name,"!!document.querySelector('#lab-formulation')");
  await evaluate(`{const f=document.querySelector('#lab-formulation');f.elements.name.value=${JSON.stringify(name)};f.elements.data_origin.value='synthetic';const rows=f.querySelectorAll('.lab-ingredient');rows[0].querySelector('[name=ingredient_name]').value='Water';rows[0].querySelector('[name=ingredient_role]').value='water';rows[0].querySelector('[name=ingredient_percent]').value='95';rows[1].querySelector('[name=ingredient_name]').value='Fragrance';rows[1].querySelector('[name=ingredient_role]').value='fragrance';rows[1].querySelector('[name=ingredient_percent]').value='5';f.requestSubmit();}`);
  await until(`document.body.innerText.includes(${JSON.stringify(name)}) && !!document.querySelector('#lab-rank') && !document.querySelector('.main > [role=status]')`);
  await check('saved formulation visible '+name,"!document.querySelector('.main > [role=alert]')");
 }
 await check('stale CSRF recovers without duplicating formulation',"baylabFetch('/api/workspace/formulations').then(r=>r.json()).then(x=>x.filter(f=>f.name==='UI Candidate A').length===1)");
 for(const [name,score] of [['UI Candidate A',90],['UI Candidate B',40]]){
  await evaluate(`{const row=[...document.querySelectorAll('.lab-candidate')].find(x=>x.innerText.includes(${JSON.stringify(name)}));row.querySelector('button').click();}`);
  await evaluate(`{const f=document.querySelector('.lab-criterion').closest('form');f.elements.comparison_protocol.value='QA-UI';for(const k of ['oxidation','solubility','compatibility','temperature','aroma']){f.elements[k].value=${JSON.stringify(String(score))};f.elements[k+'_source'].value='QA synthetic fixture';f.elements[k+'_rationale'].value='Synthetic UI test score';}f.requestSubmit();}`);
  await until("!document.querySelector('.main > [role=status]')");
  await check('assessment saved '+name,"!document.querySelector('.main > [role=alert]')");
 }
 await evaluate(`{for(const name of ['UI Candidate A','UI Candidate B']){const row=[...document.querySelectorAll('.lab-candidate')].find(x=>x.innerText.includes(name));row.querySelector('input[type=checkbox]').click();}const f=document.querySelector('#lab-rank');f.elements.comparison_protocol.value='QA-UI';f.requestSubmit();}`);
 await until("document.querySelectorAll('.lab-rank-row').length===2 && !document.querySelector('.main > [role=status]')");
 await check('rank renders actual weighted results',"document.querySelector('.lab-rank-row').innerText.includes('UI Candidate A') && document.querySelector('.lab-rank-row').innerText.includes('90')");
 const id=await evaluate("baylabFetch('/api/workspace/formulations').then(r=>r.json()).then(x=>x.find(f=>f.name==='UI Candidate A').id)");
 await evaluate("go('input')");
 await evaluate(`{const f=document.querySelector('#lab-experiment');const values={formulation_id:${JSON.stringify(id)},batch_id:'UI-B1',protocol:'UI-P1',source_ref:'QA synthetic fixture',measured_on:'2026-11-04',initial_h2o2:'3',final_h2o2:'2.7',ph:'4',temperature_c:'25',duration_days:'7',data_origin:'synthetic'};for(const [k,v] of Object.entries(values))f.elements[k].value=v;f.requestSubmit();}`);
 await until("location.hash.includes('evaluasi') && !document.querySelector('.main > [role=status]')");
 await check('experiment saved with real computed retention',"baylabFetch('/api/workspace/experiments').then(r=>r.json()).then(x=>x.some(e=>e.batch_id==='UI-B1'&&e.retention_pct===90&&e.data_origin==='synthetic'))");
 await call('Page.reload');
 await until("performance.getEntriesByType('navigation')[0]?.type==='reload' && document.body.innerText.includes('UI-B1') && document.body.innerText.includes('Formulasi, penilaian kandidat, dan eksperimen tersimpan di Supabase')");
 await check('session and saved experiment survive reload',"document.body.innerText.includes('UI-B1')");
 await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
 await evaluate("go('formulasi')");
 await check('mobile formulation page fits',"document.documentElement.scrollWidth<=390");
 await evaluate("go('input')");
 await check('mobile experiment page fits',"document.documentElement.scrollWidth<=390");

 await check('generic forbidden response is not retried',`(async()=>{const original=window.fetch;let calls=0;window.fetch=async()=>{calls++;return new Response(JSON.stringify({detail:'Role denied'}),{status:403,headers:{'Content-Type':'application/json'}})};try{const r=await baylabFetch('/api/workspace/formulations',{method:'POST',body:'{}'});return r.status===403&&calls===1;}finally{window.fetch=original;}})()`);
 await check('persistent CSRF mismatch retries at most once',`(async()=>{const original=window.fetch;let writes=0;window.fetch=async(url,options)=>{if(String(url)==='/api/auth/session')return original(url,options);writes++;return new Response(JSON.stringify({detail:'Token CSRF tidak valid. Muat ulang halaman.',code:'csrf_invalid'}),{status:403,headers:{'Content-Type':'application/json'}})};try{const r=await baylabFetch('/api/workspace/formulations',{method:'POST',body:'{}'});return r.status===403&&writes===2;}finally{window.fetch=original;}})()`);
 await call('Network.setCookie',{name:'baylab_cloud_csrf',value:'b'.repeat(64),url:'http://127.0.0.1:3012/',httpOnly:true,sameSite:'Strict',path:'/'});
 await check('changed organization blocks mutation replay',`(async()=>{const original=window.fetch;let writes=0;window.fetch=async(url,options)=>{const r=await original(url,options);if(String(url)==='/api/auth/session'){const data=await r.json();data.user.organization.slug='other';return new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}});}if(options?.method==='POST')writes++;return r;};try{const r=await baylabFetch('/api/workspace/formulations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'Must not save',ingredients:[{name:'Water',role:'water',percent:100}],data_origin:'synthetic'})});return r.status===401&&writes===1&&document.body.innerText.includes('Akun atau organisasi berubah');}finally{window.fetch=original;}})()`);
 await check('no browser runtime exceptions',"true");
 const errors=events.filter(x=>x.method==='Runtime.exceptionThrown');if(errors.length)failures.push('runtime exceptions: '+JSON.stringify(errors));
 fs.writeFileSync(path.join(out,'cloud-workspace-browser-report.json'),JSON.stringify({report,failures},null,2));
 console.log(JSON.stringify({browserPassed:report.length-failures.length,failures}));if(failures.length)process.exitCode=1;
}finally{try{await call('Browser.close',{},null)}catch{}ws.close();child.kill();}
