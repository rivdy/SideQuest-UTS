
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';
const root=process.cwd(),out=path.join(root,'qa');
fs.mkdirSync(out,{recursive:true});
const child=spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+path.join(out,'chrome-profile'),'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
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
async function shot(name){const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.data,'base64'));}
const credentials=JSON.parse(fs.readFileSync(path.join(out,'browser-login.json'),'utf8'));
try{
await call('Page.navigate',{url:'http://127.0.0.1:8101/baylab-figma.html#model'});
await until('!!document.querySelector("#org-login")');
await check('protected route shows organization login','!document.querySelector(".sidebar") && !document.querySelector(".lab-scatter")');
await evaluate(`(()=>{const f=document.querySelector('#org-login');const d=${JSON.stringify(credentials)};for(const [k,v] of Object.entries(d))f.querySelector('[name='+k+']').value=v;return labLogin(f);})()`);
await until('!!document.querySelector(".sidebar")');
await check('authenticated profile replaces demo user','document.querySelector(".profile").innerText.includes("QA Administrator") && !document.querySelector(".profile").innerText.includes("Dewi")');
await check('no readable auth cookie','!document.cookie.includes("baylab_session")');
await check('no credential in browser storage','!Object.values(localStorage).some(x=>x.includes("qa@example.test"))');
for(let index=0;index<2;index++){
await evaluate('go("formulasi")');await until('!!document.querySelector("#lab-formulation")');
await evaluate(`(()=>{const f=document.querySelector('#lab-formulation');f.querySelector('[name=name]').value=${JSON.stringify(index?'QA Candidate B':'QA <img src=x onerror=alert(1)>')};f.querySelector('[name=data_origin]').value='synthetic';const rows=f.querySelectorAll('.lab-ingredient');rows[0].querySelector('[name=ingredient_name]').value='Test fragrance';rows[0].querySelector('[name=ingredient_role]').value='fragrance';rows[0].querySelector('[name=ingredient_percent]').value='${index+1}';rows[1].querySelector('[name=ingredient_name]').value='Water';rows[1].querySelector('[name=ingredient_role]').value='water';rows[1].querySelector('[name=ingredient_percent]').value='${99-index}';f.requestSubmit();})()`);
await until('!!document.querySelector("#lab-rank")');
const forms=await evaluate('(async()=>await (await baylabFetch("/api/workspace/formulations")).json())()');
const current=forms.find(f=>index?f.name==='QA Candidate B':f.name.startsWith('QA <img'));
await evaluate('labAssess('+JSON.stringify(current.id)+')');
await evaluate(`(()=>{const f=document.querySelector('.lab-criterion').closest('form');f.querySelector('[name=comparison_protocol]').value='QA-RUBRIC';for(const key of ['oxidation','solubility','compatibility','temperature','aroma']){f.querySelector('[name='+key+']').value='${index?80:40}';f.querySelector('[name='+key+'_source]').value='QA illustrative fixture';f.querySelector('[name='+key+'_rationale]').value='Software test only';}f.requestSubmit();})()`);
await until('!document.querySelector(".main > [role=status]")');
await evaluate('labSelectCandidate('+JSON.stringify(current.id)+',true)');
}
await check('stored candidate names escaped','!document.querySelector(".lab-candidate img") && document.querySelector(".lab-candidate").parentElement.innerText.includes("<img")');
await evaluate('(()=>{const f=document.querySelector("#lab-rank");f.querySelector("[name=comparison_protocol]").value="QA-RUBRIC";f.requestSubmit();})()');
await until('!!document.querySelector("#lab-ranking-result")');
await check('ranking calculated from submitted values','document.querySelector(".lab-rank-row").innerText.includes("QA Candidate B") && document.querySelector(".lab-rank-row").innerText.includes("80")');
await shot('workspace-ranking');
await evaluate('go("input")');await until('!!document.querySelector("#lab-experiment")');
await evaluate(`(()=>{const f=document.querySelector('#lab-experiment');const vals={formulation_id:f.querySelector('[name=formulation_id] option:nth-child(2)').value,batch_id:'QA-B01',protocol:'QA-PROTOCOL',source_ref:'QA test fixture only',measured_on:'2026-11-04',initial_h2o2:'3',final_h2o2:'2.7',ph:'4',temperature_c:'30',duration_days:'14',data_origin:'synthetic'};for(const [k,v] of Object.entries(vals))f.querySelector('[name='+k+']').value=v;f.requestSubmit();})()`);
await until('location.hash==="#evaluasi"');
await check('experiment retained with calculated retention','document.querySelector(".lab-scroll").innerText.includes("90%") && document.querySelector(".lab-scroll").innerText.includes("QA-B01")');
await evaluate('go("model")');await until('!!document.querySelector("#lab-model")');
await check('no placeholder model graph','!document.querySelector(".lab-scatter")');
await evaluate('document.querySelector("#lab-model").requestSubmit()');
await until('!!document.querySelector("#lab-model-result")');
await check('trained predictions displayed','document.querySelectorAll(".lab-scatter circle").length===200 && document.querySelector("#lab-model-result").innerText.includes("928")');
await shot('workspace-model');
await evaluate('labTarget("h2o2_retention")');await until('document.querySelector("#lab-model [name=target]").value==="h2o2_retention" && !document.querySelector(".main > [role=status]")');
await check('insufficient lab data blocks training','document.querySelector("#lab-model button").disabled && !document.querySelector(".lab-scatter")');
await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
await check('mobile model fits','document.documentElement.scrollWidth<=innerWidth');
await evaluate('go("formulasi")');await until('!!document.querySelector("#lab-formulation")');
await check('mobile formulation fits','document.documentElement.scrollWidth<=innerWidth');
await shot('workspace-mobile');
await evaluate('go("chat")');await until('!!document.querySelector("#rag-question")');
await check('RAG integrated with authenticated session','!!document.querySelector("#rag-upload")');
await evaluate('go("screening")');await until('!!document.querySelector("#chem-smiles")');
await evaluate('chemistryInput("CCO");chemistryScreen()');
await check('chemistry session and CSRF work','document.querySelector(".chem-layout").innerText.includes("C2H6O")');
await evaluate('labLogout()');await until('!!document.querySelector("#org-login")');
await check('logout invalidates API session','(async()=> (await fetch("/api/workspace/formulations")).status===401)()');
const errors=events.filter(e=>e.method==='Runtime.exceptionThrown');if(errors.length)failures.push('browser runtime exceptions: '+JSON.stringify(errors));
fs.writeFileSync(path.join(out,'workspace-browser-report.json'),JSON.stringify({report,failures},null,2));
console.log(JSON.stringify({checks:report.length,failures}));if(failures.length)process.exitCode=1;
}finally{await call('Browser.close',{},null).catch(()=>{});ws.close();child.kill();}
