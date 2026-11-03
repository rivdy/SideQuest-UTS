
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
const url='http://127.0.0.1:3000/baylab-figma.html#chat';
await call('Page.navigate',{url});
await new Promise(r=>setTimeout(r,1500));
await evaluate('document.fonts.ready.then(()=>true)');
const report=[],failures=[];
async function check(name,expression){const result=await evaluate(expression);report.push({name,result});if(!result){failures.push(name);if(name.includes('overflow')){report.push({name:name+' details',result:await evaluate('[...document.querySelectorAll("main *")].filter(x=>x.getBoundingClientRect().right>innerWidth).slice(0,8).map(x=>({tag:x.tagName,cls:x.className,width:x.getBoundingClientRect().width,right:x.getBoundingClientRect().right,text:x.textContent.slice(0,90)}))')})}}}
async function navigate(page){await evaluate('location.hash='+JSON.stringify(page));await new Promise(r=>setTimeout(r,100))}
async function shot(name){const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.data,'base64'))}
let testDocument;
try {
await new Promise(r=>setTimeout(r,1200));
await check('RAG replaces simulated chat','!!document.querySelector("#rag-upload") && !!document.querySelector("#rag-question")');
await check('proposal indexed','document.querySelector(".rag-docs").innerText.includes("Proposal BAYLab")');
await check('desktop no overflow','document.documentElement.scrollWidth<=innerWidth');
const upload = await evaluate(`(async()=>{const f=new FormData();f.append('title','QA <img src=x onerror=alert(1)>');f.append('source_ref','QA-RAG-TEST');f.append('authorized','true');f.append('file',new File(['Dokumen uji integrasi. Kode unik nebulaqa menunjukkan catatan pengujian aplikasi, bukan temuan ilmiah.'],'qa.txt',{type:'text/plain'}));return (await fetch('/api/rag/documents',{method:'POST',body:f})).json()})()`);
testDocument=upload.id;
await evaluate('ragRefresh()');await new Promise(r=>setTimeout(r,500));
await check('escaped document titles','document.querySelector(".rag-docs").innerText.includes("<img") && !document.querySelector(".rag-docs img")');
await evaluate('ragAsk("quasarxyz astronomiunknown")');await new Promise(r=>setTimeout(r,1500));
await check('unknown question abstains','document.querySelector("#rag-messages").innerText.includes("Belum ada sumber")');
await shot('rag-chat-desktop');
await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
await check('mobile no overflow','document.documentElement.scrollWidth<=innerWidth');
await shot('rag-chat-mobile');
await evaluate('go("dashboard")');await new Promise(r=>setTimeout(r,150));
await check('dashboard preserved','!!document.querySelector(".dashboard")');
fs.writeFileSync(path.join(out,'rag-report.json'),JSON.stringify({report,failures},null,2));
console.log(JSON.stringify({checks:report.length,failures}));if(failures.length)process.exitCode=1;
} finally {
if(testDocument)await evaluate('fetch("/api/rag/documents/'+testDocument+'",{method:"DELETE"})').catch(()=>{});
await call('Browser.close',{},null).catch(()=>{});ws.close();child.kill();
}