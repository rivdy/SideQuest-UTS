
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

const url='http://127.0.0.1:3000/baylab-figma.html#screening';
const report=[],failures=[];
async function check(name, expression){const ok=!!await evaluate(expression);report.push({name,ok});if(!ok)failures.push(name);}
async function shot(name){const result=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(result.data,'base64'));}
try{
await call('Page.navigate',{url});
await new Promise(r=>setTimeout(r,1600));
await check('real screening replaces fixed results','!!document.querySelector("#chem-smiles") && !document.querySelector(".screen-steps")');
await evaluate('chemistryInput("CCO"); chemistryScreen()');
await check('ethanol calculated','document.querySelector(".chem-layout").innerText.includes("C2H6O") && document.querySelector(".chem-layout").innerText.includes("DRAFT-ALCOHOL")');
await check('molecule rendered','document.querySelector(".chem-molecule").complete && document.querySelector(".chem-molecule").naturalWidth > 0');
await evaluate('chemistryInput("CC=O"); chemistryScreen()');
await check('input changes detected features','document.querySelector(".chem-layout").innerText.includes("DRAFT-ALDEHYDE") && !document.querySelector(".chem-layout").innerText.includes("DRAFT-ALCOHOL")');
await check('no validated safety claim','document.querySelector(".chem-layout").innerText.includes("Semua aturan masih draft")');
await shot('chemistry-desktop');
await evaluate('chemistryInput("bad<smiles>"); chemistryScreen()');
await check('invalid input clears stale results','!!document.querySelector("[role=alert]") && !document.querySelector(".chem-molecule")');
await evaluate('chemistryInput("c1ccccc1"); chemistryScreen()');
await check('no match abstains','document.querySelector(".chem-layout").innerText.includes("bukan kesimpulan keamanan")');
await check('desktop fits','document.documentElement.scrollWidth <= innerWidth');
await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
await check('mobile fits','document.documentElement.scrollWidth <= innerWidth');
await shot('chemistry-mobile');
await evaluate('go("chat")');await new Promise(r=>setTimeout(r,700));
await check('RAG preserved','!!document.querySelector("#rag-upload")');
fs.writeFileSync(path.join(out,'chemistry-report.json'),JSON.stringify({report,failures},null,2));
console.log(JSON.stringify({checks:report.length,failures}));if(failures.length)process.exitCode=1;
}finally{await call('Browser.close',{},null).catch(()=>{});ws.close();child.kill();}
