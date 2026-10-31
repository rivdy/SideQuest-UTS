
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
try {
for (const target of [url, 'http://127.0.0.1:3318']) {
 await call('Page.navigate',{url:target}); await new Promise(r=>setTimeout(r,1300));
 await check(target+' login visible','!!document.querySelector("#bl-login-form") && document.querySelector("h1").textContent.includes("Racik")');
 await check('three perfume bottles','document.querySelectorAll(".bl-perfume-bottle").length===3');
 await check('botanical ingredients','document.querySelectorAll(".bl-ingredient").length===6');
 await check('desktop no overflow','document.documentElement.scrollWidth<=innerWidth');
 await shot(target.startsWith('file')?'login-soda-html-desktop':'login-soda-next-desktop');
 await evaluate('document.querySelector("[data-color=teal]").click()'); await new Promise(r=>setTimeout(r,100));
 await check('theme toggles','document.querySelector(".bl-login").dataset.theme==="teal"');
 await evaluate('document.querySelector("#bl-pause").click()'); await new Promise(r=>setTimeout(r,100));
 await check('pause stops animation','(async()=>{const el=document.querySelector(".bl-perfume-position");const before=el.style.transform;await new Promise(r=>setTimeout(r,160));return before===el.style.transform})()');
 await evaluate('document.querySelector("#bl-reveal").click()'); await new Promise(r=>setTimeout(r,100));
 await check('password reveal','document.querySelector("#password").type==="text"');
 await evaluate('document.querySelector("#bl-forgot").click()'); await new Promise(r=>setTimeout(r,100));
 await check('help visible','document.querySelector("#bl-status").innerText.includes("admin LKPI")');
 await evaluate('document.querySelector("#bl-email").value="demo@example.com"; document.querySelector("#password").value="example-only";document.querySelector("#bl-login-form").requestSubmit()'); await new Promise(r=>setTimeout(r,100));
 await check('no fake authentication','document.querySelector("#bl-status").innerText.includes("belum aktif")');
 await call('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
 await check('reduced motion honored','getComputedStyle(document.querySelector(".bl-bottle-position")).animationName==="none"');
 await call('Emulation.setEmulatedMedia',{features:[]});
 await evaluate('document.querySelector("[data-color=violet]").click();document.querySelector("#bl-pause").click();document.querySelector("#bl-email").value="";document.querySelector("#password").value="";');
 for(const width of [390, 768, 320]) {
  await call('Emulation.setDeviceMetricsOverride',{width,height:844,deviceScaleFactor:1,mobile:true});
  await check('responsive '+width,'document.documentElement.scrollWidth<=innerWidth');
  if(width===390){await new Promise(r=>setTimeout(r,1200));await evaluate('window.scrollTo(0,0)');await shot(target.startsWith('file')?'login-soda-html-mobile':'login-soda-next-mobile');}
 }
 await evaluate('document.querySelector(".bl-research").scrollIntoView()');
 await new Promise(r=>setTimeout(r,400));
 await check('research trace starts','Number(document.querySelector(".bl-map-trace").style.strokeDashoffset)<100');
 await check('three ingredient panels','document.querySelectorAll(".bl-note-card").length===3');
 await shot(target.startsWith('file')?'kimi-research-html':'kimi-research-next');
 await evaluate('document.querySelector(".bl-demo").click()'); await new Promise(r=>setTimeout(r,1400));
 await check('demo opens existing dashboard','location.hash==="#dashboard" && !!document.querySelector(".dashboard")');
 await call('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
}
fs.writeFileSync(path.join(out,'login-report.json'),JSON.stringify({report,failures},null,2));
console.log(JSON.stringify({checks:report.length,failures}));
if(failures.length)process.exitCode=1;
} finally { await call('Browser.close',{},null).catch(()=>{}); ws.close(); child.kill(); }