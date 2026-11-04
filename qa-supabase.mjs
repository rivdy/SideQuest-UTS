
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';
const root=process.cwd(),out=path.join(root,'qa');
fs.mkdirSync(out,{recursive:true});
const child=spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+path.join(out,'chrome-supabase-profile'),'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
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

try {
 await call('Page.navigate',{url:'http://127.0.0.1:3000/baylab-figma.html#login'});
 await until("!!document.querySelector('#org-login') && document.body.innerText.includes('Gunakan akun Supabase')");
 await check('Supabase login instructions visible',"document.body.innerText.includes('Akun lokal tidak otomatis berlaku')");
 await check('No initial false connection error',"!document.body.innerText.includes('Backend belum tersedia') && !document.body.innerText.includes('Sesi berakhir')");
 await check('Actual cloud provider active',"fetch('/api/auth/config').then(r=>r.json()).then(x=>x.provider==='supabase')");
 await check('Anonymous workspace denied',"fetch('/api/workspace/overview').then(r=>r.status===401)");
 await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
 await check('Mobile login fits',"document.documentElement.scrollWidth<=390");
 await shot('supabase-login');
 fs.writeFileSync(path.join(out,'supabase-browser-report.json'),JSON.stringify({report,failures},null,2));
 console.log(JSON.stringify({passed:report.length-failures.length,failures}));
 if(failures.length)process.exitCode=1;
}finally{try{await call('Browser.close',{},null)}catch{}ws.close();child.kill();}
