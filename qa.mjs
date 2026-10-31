
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
const url=pathToFileURL(path.join(root,'index.html')).href;
await call('Page.navigate',{url});
await new Promise(r=>setTimeout(r,1500));
await evaluate('document.fonts.ready.then(()=>true)');
const report=[],failures=[];
async function check(name,expression){const result=await evaluate(expression);report.push({name,result});if(!result){failures.push(name);if(name.includes('overflow')){report.push({name:name+' details',result:await evaluate('[...document.querySelectorAll("main *")].filter(x=>x.getBoundingClientRect().right>innerWidth).slice(0,8).map(x=>({tag:x.tagName,cls:x.className,width:x.getBoundingClientRect().width,right:x.getBoundingClientRect().right,text:x.textContent.slice(0,90)}))')})}}}
async function navigate(page){await evaluate('location.hash='+JSON.stringify(page));await new Promise(r=>setTimeout(r,100))}
async function shot(name){const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.data,'base64'))}
try{
await check('Login rendered','document.querySelector(".login-box h2").textContent==="Masuk"');await shot('login-desktop');
await evaluate('[...document.querySelectorAll("button")].find(b=>b.textContent==="Masuk dengan akun demo").click()');await new Promise(r=>setTimeout(r,100));
await check('Demo login routes to dashboard','location.hash==="#dashboard" && document.querySelector("h1").textContent.includes("Dewi")');await shot('dashboard-desktop');
for(const page of ['formulasi','screening','literatur','rekomendasi','aroma','evaluasi','input','model','chat','library','pengaturan']){
await navigate(page);
await check(page+' renders','!!document.querySelector("main h1") && document.querySelector("main").innerText.length>200');
await check(page+' desktop no document overflow','document.documentElement.scrollWidth<=1440');
}
await navigate('library');await evaluate('document.querySelector("#library-search").value="HEDP";filterLibrary()');
await check('Library search filters to HEDP','document.querySelectorAll("#library-table tbody tr").length===1 && document.querySelector("#library-table").textContent.includes("HEDP")');
await evaluate('document.querySelector("#library-search").value="zzzz";filterLibrary()');
await check('Library empty state','document.querySelector("#library-table").textContent.includes("Tidak ada bahan")');
await navigate('rekomendasi');await evaluate('toggleCandidate("F-03")');await check('Candidate selection persists','JSON.parse(localStorage.getItem("baylab-state")).selected.includes("F-03")');await evaluate('toggleCandidate("F-03")');
await navigate('formulasi');await evaluate('addIngredient("ingredients")');await check('Add ingredient creates editable input','document.querySelectorAll("#ingredients .ingredient").length===4');
await evaluate('document.querySelector("#target").value="4";storeDraft()');await navigate('dashboard');await navigate('formulasi');await check('Form restores saved input','document.querySelector("#target").value==="4"');
await navigate('input');await evaluate('document.querySelector("#initial").value="3";document.querySelector("#final").value="2.7";calcRetention()');
await check('Retention calculation 90 percent','document.querySelector("#retention-result").textContent.includes("90.0%")');
await evaluate('saveExperiment(false)');await new Promise(r=>setTimeout(r,100));await check('Experiment saves and updates evaluation','location.hash==="#evaluasi" && document.querySelector("#trial-table").textContent.includes("Retensi 90.0%")');
await navigate('chat');await evaluate('askChat("Bandingkan F-01 dan F-02")');await check('Chat appends demo reply','document.querySelectorAll(".message").length===3 && document.querySelectorAll(".message")[2].textContent.includes("0,84")');
await evaluate('askChat("<img src=x onerror=alert(1)>")');await check('Chat escapes HTML','document.querySelectorAll(".message img").length===0');
await navigate('pengaturan');await evaluate('document.querySelector("[data-setting=param0]").value="≥ 95 %";saveSettings()');await navigate('dashboard');await navigate('pengaturan');await check('Settings persist','document.querySelector("[data-setting=param0]").value==="≥ 95 %"');
await navigate('formulasi');await shot('formulasi-desktop');
await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
for(const page of ['login','dashboard','formulasi','screening','literatur','rekomendasi','aroma','evaluasi','input','model','chat','library','pengaturan']){
await navigate(page);await check(page+' mobile no document overflow','document.documentElement.scrollWidth<=390');
if(page==='dashboard'||page==='input')await shot(page+'-mobile');
}
const exceptions=events.filter(x=>x.method==='Runtime.exceptionThrown').map(x=>x.params.exceptionDetails);
report.push({name:'Runtime exceptions',result:exceptions});if(exceptions.length)failures.push('runtime exceptions');
await evaluate('localStorage.removeItem("baylab-state")');
fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({report,failures},null,2));
console.log(JSON.stringify({checks:report.length,failures},null,2));
} finally {await call('Browser.close',{},null).catch(()=>{});ws.close();child.kill();}
if(failures.length)process.exitCode=1;

