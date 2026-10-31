
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
await evaluate('localStorage.removeItem("baylab-state");location.reload()');await new Promise(r=>setTimeout(r,500));
for(const page of ['login','dashboard','formulasi','screening','literatur','rekomendasi','aroma','evaluasi','input','model','chat','library','pengaturan','dataset','pitch']){
await navigate(page);
await check(page+' renders',page==='login'?'!!document.querySelector(".login-box")':'!!document.querySelector("main h1") && document.querySelector("main").innerText.length>200');
await check(page+' desktop no overflow','document.documentElement.scrollWidth<=1440');
}
await check('Unknown chemical is not classified safe','evaluateChemical("unmapped mystery").risk==="Belum diketahui"');
await check('Dihydromyrcenol still triggers R-01','evaluateChemical("Dihydromyrcenol").rules.some(r=>r.id==="R-01")');
await check('Tetrahydrolinalool does not trigger alkene rule','!evaluateChemical("Tetrahydrolinalool").rules.some(r=>r.id==="R-01")');
await check('Citral triggers alkene and aldehyde','["R-01","R-02"].every(id=>evaluateChemical("Citral").rules.some(r=>r.id===id))');
await check('CAS and alias normalization','findChemical("93-92-5").name===findChemical("methylbenzyl acetate").name');
await navigate('screening');
await evaluate('document.querySelector("#screen-compound").value="Tetrahydrolinalool";addScreeningCompound()');
await check('Screening add renders actual chosen chemical','document.querySelector("main").innerText.includes("Tetrahydrolinalool") && state.knowledge.names.length===2');
await evaluate('document.querySelector("#screen-ph").value="4";runKnowledge()');
await check('Screening context persists','JSON.parse(localStorage.getItem("baylab-state")).knowledge.ph===4');
await navigate('literatur');await evaluate('document.querySelector("#source-search").value="US5180514A";filterSources()');
await check('Evidence search returns actual patent','document.querySelectorAll("#source-list article").length===1 && document.querySelector("#source-list a").href.includes("US5180514A")');
await navigate('aroma');await evaluate('subOriginal="Decanal";subChoice="saturated";useSubstitution()');await new Promise(r=>setTimeout(r,100));
await check('Substitution updates F01 composition','location.hash==="#rekomendasi" && comp("F-01")[2][0].includes("Tetrahydrolinalool") && JSON.parse(localStorage.getItem("baylab-state")).substitution.original==="Decanal"');
await navigate('dataset');
await check('Dataset has 10 synthetic rows','computedSynthetic().length===10 && computedSynthetic().every(r=>r.Data_Origin==="synthetic" && r.Eligible_For_Training===false)');
await check('Synthetic initial range 15 to 25','computedSynthetic().every(r=>r.H2O2_Concentration_Pct>=15 && r.H2O2_Concentration_Pct<=25)');
await check('Synthetic pH range 3 to 4.5','computedSynthetic().every(r=>r.Initial_pH>=3 && r.Initial_pH<=4.5 && r.Final_pH>=3 && r.Final_pH<=4.5)');
await check('Retention is reproducible','computedSynthetic().every(r=>Math.abs(r.H2O2_Retention_Pct-r.Final_H2O2_Concentration_Pct/r.H2O2_Concentration_Pct*100)<0.0001)');
await check('79.99 fails','labelExperiment(79.99,"Jernih")==="Gagal"');
await check('80 requires review','labelExperiment(80,"Jernih")==="Perlu tinjauan"');
await check('89.99 requires review','labelExperiment(89.99,"Jernih")==="Perlu tinjauan"');
await check('90 clear passes','labelExperiment(90,"Jernih")==="Lolos"');
await check('Cloudy overrides high retention','labelExperiment(99,"Keruh")==="Gagal"');
await check('Phase separation overrides high retention','labelExperiment(99,"Pemisahan Fase")==="Gagal"');
await evaluate('editSynthetic(0,"Final_H2O2_Concentration_Pct","12")');
await check('Editable data recomputes 80 review','computedSynthetic()[0].H2O2_Retention_Pct===80 && computedSynthetic()[0].Status_Label==="Perlu tinjauan"');
await evaluate('editSynthetic(0,"Final_H2O2_Concentration_Pct","100")');
await check('Invalid data rejected','computedSynthetic()[0].Final_H2O2_Concentration_Pct===12');
await check('CSV has header plus 10 rows and origin flags','syntheticCSV().split("\\r\\n").length===11 && syntheticCSV().includes("Data_Origin") && syntheticCSV().includes("false")');
await check('Markdown has 10 data rows','datasetMarkdown().split("\\n").length===12');
await check('Synthetic data does not become real experiment','state.results.length===0');
await evaluate('showDatasetMarkdown()');await check('Markdown preview opens','document.querySelector("#modal").open && document.querySelector("#dataset-markdown").value.includes("SIM-010")');await evaluate('document.querySelector("#modal").close()');
await shot('modules-dataset-desktop');
await navigate('chat');await evaluate('askChat("Apa risiko dihydromyrcenol?")');
await check('Chat grounded source S5','document.querySelector("#messages").lastElementChild.textContent.includes("C=C") && document.querySelector("#messages").lastElementChild.querySelector("a").href.includes("18479-58-8")');
await evaluate('askChat("<img src=x onerror=alert(1)>")');
await check('Chat escapes user input','document.querySelectorAll("#messages img").length===0');
await check('Chat does not invent citations for unknown query','document.querySelector("#messages").lastElementChild.querySelectorAll("a").length===0');
await navigate('pitch');await shot('modules-pitch-desktop');
await evaluate('togglePitchTimer()');await new Promise(r=>setTimeout(r,1100));await evaluate('togglePitchTimer()');
await check('Pitch timer starts and pauses','pitchRemaining<180 && pitchInterval===null');
await evaluate('resetPitchTimer()');await check('Pitch timer resets','pitchRemaining===180 && document.querySelector("#pitch-timer").textContent==="3:00"');
await check('Pitch states metrics as targets','pitchPlain().includes("target") && pitchPlain().includes("bukan hasil yang sudah kami capai")');
report.push({name:'Pitch word count',result:await evaluate('pitchSections.map(x=>x.text).join(" ").split(/\\s+/).length')});
await navigate('screening');await shot('modules-screening-desktop');
await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
for(const page of ['dashboard','formulasi','screening','literatur','rekomendasi','aroma','evaluasi','input','model','chat','library','pengaturan','dataset','pitch']){
await navigate(page);await check(page+' mobile no overflow','document.documentElement.scrollWidth<=390');
if(page==='screening'||page==='dataset')await shot('modules-'+page+'-mobile');
}
const exceptions=events.filter(x=>x.method==='Runtime.exceptionThrown').map(x=>x.params.exceptionDetails);report.push({name:'Runtime exceptions',result:exceptions});if(exceptions.length)failures.push('Runtime exceptions');
await evaluate('localStorage.removeItem("baylab-state")');
fs.writeFileSync(path.join(out,'modules-report.json'),JSON.stringify({report,failures},null,2));console.log(JSON.stringify({checks:report.length,failures},null,2));
}finally{await call('Browser.close',{},null).catch(()=>{});ws.close();child.kill()}
if(failures.length)process.exitCode=1;
