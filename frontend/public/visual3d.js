/* 3D molecule viewer (RDKit coordinates from the local backend) and sample-vial visualization.
   The vial is drawn only from organoleptic observations people recorded; it is never a prediction. */
(() => {
  const safe = value => esc(String(value ?? ''));
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------- 3D molecule ----------
  const CPK = {H:'#e9e9ee',C:'#4b4b55',N:'#3b6cf6',O:'#e5413a',S:'#e2bb2a',P:'#f08a24',Cl:'#38b44a',F:'#7fd45a',Br:'#a5422a',I:'#7a3fa0',Na:'#a26ff0',K:'#8f40d4'};
  const cache = new Map();
  async function conformer(smiles){
    if(!cache.has(smiles))cache.set(smiles,(async()=>{
      const response=await (window.baylabFetch||fetch)('/api/chemistry/conformer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({smiles}),signal:AbortSignal.timeout(25000)});
      let value;try{value=await response.json();}catch{throw new Error('Backend lokal belum tersedia.');}
      if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:'Struktur 3D tidak dapat dibuat.');
      return value;
    })().catch(e=>{cache.delete(smiles);throw e;}));
    return cache.get(smiles);
  }
  function viewer(canvas,data){
    const st={rx:-0.35,ry:0.6,auto:!reduced,showH:true,drag:null};
    const maxR=Math.max(1,...data.atoms.map(a=>Math.hypot(a.x,a.y,a.z)));
    const ctx=canvas.getContext('2d');
    canvas.addEventListener('pointerdown',e=>{st.drag={x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId);});
    canvas.addEventListener('pointermove',e=>{if(!st.drag)return;st.ry+=(e.clientX-st.drag.x)*0.01;st.rx+=(e.clientY-st.drag.y)*0.01;st.drag={x:e.clientX,y:e.clientY};if(!st.auto)draw();});
    canvas.addEventListener('pointerup',()=>{st.drag=null;});
    function draw(){
      const dpr=window.devicePixelRatio||1,w=canvas.clientWidth,h=canvas.clientHeight;
      if(canvas.width!==Math.round(w*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);}
      ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
      const scale=Math.min(w,h)/(2*maxR+2.4),cy=Math.cos(st.ry),sy=Math.sin(st.ry),cx=Math.cos(st.rx),sx=Math.sin(st.rx);
      const pts=data.atoms.map(a=>{const x1=a.x*cy+a.z*sy,z1=-a.x*sy+a.z*cy,y2=a.y*cx-z1*sx,z2=a.y*sx+z1*cx,p=1/(1-z2/(maxR*5));return {x:w/2+x1*scale*p,y:h/2-y2*scale*p,z:z2,p,el:a.element};});
      const visible=i=>st.showH||pts[i].el!=='H';
      const items=[];
      for(const b of data.bonds)if(visible(b.a)&&visible(b.b))items.push({z:(pts[b.a].z+pts[b.b].z)/2-0.01,bond:b});
      pts.forEach((p,i)=>{if(visible(i))items.push({z:p.z,atom:i});});
      items.sort((a,b)=>a.z-b.z);
      for(const it of items){
        if(it.bond){const A=pts[it.bond.a],B=pts[it.bond.b],dx=B.x-A.x,dy=B.y-A.y,len=Math.hypot(dx,dy)||1,nx=-dy/len,ny=dx/len,lines=it.bond.order>=2?(it.bond.order>=3?[-1,0,1]:[-0.5,0.5]):[0],gap=scale*0.11;
          ctx.strokeStyle='#8d8aa0';ctx.lineWidth=Math.max(1.2,scale*(lines.length>1?0.07:0.11));ctx.lineCap='round';
          for(const k of lines){ctx.beginPath();ctx.moveTo(A.x+nx*gap*k,A.y+ny*gap*k);ctx.lineTo(B.x+nx*gap*k,B.y+ny*gap*k);ctx.stroke();}
        } else {const p=pts[it.atom],r=scale*(p.el==='H'?0.22:0.36)*p.p,col=CPK[p.el]||'#b46cf0',g=ctx.createRadialGradient(p.x-r*0.35,p.y-r*0.35,r*0.1,p.x,p.y,r);
          g.addColorStop(0,'#ffffff');g.addColorStop(0.25,col);g.addColorStop(1,shade(col,-0.45));
          ctx.fillStyle=g;ctx.beginPath();ctx.arc(p.x,p.y,r,0,Math.PI*2);ctx.fill();}
      }
    }
    function loop(){if(!canvas.isConnected)return;if(st.auto&&!st.drag)st.ry+=0.008;draw();requestAnimationFrame(loop);}
    draw();if(st.auto)requestAnimationFrame(loop);
    return {toggleH(){st.showH=!st.showH;draw();return st.showH;},toggleSpin(){st.auto=!st.auto;if(st.auto)requestAnimationFrame(loop);return st.auto;}};
  }
  function shade(hex,amt){const n=parseInt(hex.slice(1),16),f=c=>Math.max(0,Math.min(255,Math.round(c+(amt<0?c:255-c)*amt)));return 'rgb('+f(n>>16)+','+f((n>>8)&255)+','+f(n&255)+')';}
  // Markup only; the observer below mounts the canvas once it is in the page.
  window.mol3dHTML=(smiles,label,{height=280}={})=>'<figure class="mol3d"><div class="mol3d-stage" style="height:'+height+'px"><canvas data-mol3d="'+safe(smiles)+'" aria-label="Struktur 3D '+safe(label)+'"></canvas><span class="mol3d-status">Menyiapkan 3D…</span></div><figcaption><strong>'+safe(label)+'</strong> <span class="mol3d-ctl"><button type="button" data-mol3d-h>Sembunyikan H</button> <button type="button" data-mol3d-spin>'+(reduced?'Putar':'Jeda putar')+'</button></span><br><span class="tiny muted mol3d-meta">Geser untuk memutar. Bentuk ilustratif dari satu konformer; bukan prediksi warna atau stabilitas.</span></figcaption></figure>';
  async function mount(canvas){
    canvas.dataset.ready='1';
    const fig=canvas.closest('.mol3d'),status=fig.querySelector('.mol3d-status');
    try{
      const data=await conformer(canvas.dataset.mol3d);if(!canvas.isConnected)return;
      status.remove();const v=viewer(canvas,data);
      fig.querySelector('[data-mol3d-h]').onclick=e=>{e.target.textContent=v.toggleH()?'Sembunyikan H':'Tampilkan H';};
      fig.querySelector('[data-mol3d-spin]').onclick=e=>{e.target.textContent=v.toggleSpin()?'Jeda putar':'Putar';};
      const els={};for(const a of data.atoms)els[a.element]=(els[a.element]||0)+1;
      fig.querySelector('.mol3d-meta').textContent=Object.entries(els).map(([k,n])=>k+n).join(' ')+' · '+data.method+'. '+data.note+' Geser untuk memutar.';
    }catch(e){status.textContent=e.message;status.classList.add('err');}
  }
  new MutationObserver(()=>document.querySelectorAll('canvas[data-mol3d]:not([data-ready])').forEach(mount)).observe(document.body,{childList:true,subtree:true});
  window.mol3dOpen=(label,smiles)=>{modal('Struktur 3D',mol3dHTML(smiles,label,{height:340}));};
  document.addEventListener('click',e=>{const b=e.target.closest('[data-open3d]');if(b){e.preventDefault();mol3dOpen(b.dataset.label,b.dataset.open3d);}});
  window.mol3dButton=(label,smiles,text)=>'<button type="button" class="mol3d-link" data-open3d="'+safe(smiles)+'" data-label="'+safe(label)+'">'+safe(text||label)+' <span aria-hidden="true">⟳ 3D</span></button>';

  // ---------- Sample vial from recorded organoleptic observations ----------
  const COLORS=[[/tidak berwarna|bening|transparan/,'#dbe9f5'],[/kuning pucat|kuning muda/,'#f4ecb0'],[/kuning/,'#f0d54e'],[/jingga|oranye|orange/,'#f3a65a'],[/merah muda|pink/,'#f4b4c8'],[/merah/,'#e0605a'],[/hijau/,'#96d49a'],[/biru muda/,'#a9cdf7'],[/biru/,'#6e9ff0'],[/ungu|violet/,'#b9a2f0'],[/coklat|cokelat/,'#b98a55'],[/putih|susu/,'#f3f1ec']];
  const colorFor=text=>{const t=String(text||'').toLowerCase();for(const [re,c] of COLORS)if(re.test(t))return c;return null;};
  let vialId=0;
  function vialSVG(o,uid){
    const base=colorFor(o.color)||'#d9d9e3',haze={jernih:0,opalesen:0.32,keruh:0.62}[o.clarity]??0,sed={sedikit:8,banyak:20}[o.sediment]||0,top=74,bottom=206;
    return '<svg viewBox="0 0 120 220" role="img" aria-label="Visualisasi sampel: '+safe(o.color||'warna belum dicatat')+', '+safe(o.clarity||'kejernihan belum dicatat')+', endapan '+safe(o.sediment||'belum dicatat')+'"><defs>'
      +'<clipPath id="vb'+uid+'"><rect x="20" y="34" width="80" height="176" rx="16"/></clipPath>'
      +'<linearGradient id="lq'+uid+'" x1="0" x2="1"><stop offset="0" stop-color="'+shade(base,-0.28)+'"/><stop offset=".42" stop-color="'+base+'"/><stop offset=".72" stop-color="'+shade(base,0.35)+'"/><stop offset="1" stop-color="'+shade(base,-0.22)+'"/></linearGradient>'
      +'<linearGradient id="gl'+uid+'" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity=".05"/><stop offset=".18" stop-color="#fff" stop-opacity=".7"/><stop offset=".3" stop-color="#fff" stop-opacity=".08"/><stop offset=".85" stop-color="#fff" stop-opacity=".05"/><stop offset="1" stop-color="#fff" stop-opacity=".35"/></linearGradient></defs>'
      +'<rect x="38" y="4" width="44" height="22" rx="5" fill="#3d3a4f"/><rect x="42" y="24" width="36" height="12" fill="#cfd3de"/>'
      +'<g clip-path="url(#vb'+uid+')"><rect x="20" y="34" width="80" height="176" fill="#f6f8fb"/>'
      +'<g class="vial-liquid"><rect x="14" y="'+top+'" width="92" height="'+(bottom-top+6)+'" fill="url(#lq'+uid+')"/>'
      +(o.phase_separation?'<rect x="14" y="'+top+'" width="92" height="26" fill="'+shade(base,0.55)+'" opacity=".85"/><line x1="20" x2="100" y1="'+(top+26)+'" y2="'+(top+26)+'" stroke="'+shade(base,-0.4)+'" stroke-dasharray="4 3"/>':'')
      +'<ellipse class="vial-wave" cx="60" cy="'+top+'" rx="44" ry="5" fill="'+shade(base,0.5)+'"/>'
      +(haze?'<rect class="'+(o.clarity==='opalesen'?'vial-shimmer':'')+'" x="14" y="'+top+'" width="92" height="'+(bottom-top+6)+'" fill="#ffffff" opacity="'+haze+'"/>':'')
      +(sed?'<path d="M20 '+(210-sed)+' Q40 '+(206-sed)+' 60 '+(210-sed)+' T100 '+(209-sed)+' V212 H20Z" fill="#8a7a62" opacity=".9"/>'+Array.from({length:sed>10?14:6},(_,i)=>'<circle cx="'+(26+(i*37)%70)+'" cy="'+(210-sed*0.4-(i%3)*2)+'" r="1.4" fill="#5d5141"/>').join(''):'')
      +'</g></g><rect x="20" y="34" width="80" height="176" rx="16" fill="url(#gl'+uid+')" stroke="#9aa3b5" stroke-width="2"/></svg>';
  }
  window.organoVialHTML=(trial,{small=false}={})=>{
    const o=trial?.organoleptic,uid=++vialId,cls='vial'+(small?' vial-sm':'');
    if(!o||!(o.color||o.clarity||o.sediment||o.phase_separation!=null))return '<figure class="'+cls+' vial-empty"><svg viewBox="0 0 120 220" aria-hidden="true"><rect x="38" y="4" width="44" height="22" rx="5" fill="#d9d6e6"/><rect x="20" y="34" width="80" height="176" rx="16" fill="none" stroke="#c9c5da" stroke-width="2" stroke-dasharray="6 5"/></svg><figcaption>'+(trial?'Batch '+safe(trial.batch_id)+': ':'')+'belum ada catatan organoleptik</figcaption></figure>';
    const facts=[o.color?'Warna: '+safe(o.color)+(colorFor(o.color)?'':' (warna tidak dikenali, ditampilkan abu-abu)'):'',o.clarity?'Kejernihan: '+safe(o.clarity):'',o.sediment?'Endapan: '+safe(o.sediment):'',o.phase_separation!=null?'Pemisahan fase: '+(o.phase_separation?'ya':'tidak'):'',o.odor_note?'Bau: '+safe(o.odor_note):'',trial.aroma_intensity!=null?'Intensitas aroma: '+safe(trial.aroma_intensity)+'/5'+(o.panelists?' ('+o.panelists+' panelis)':''):''].filter(Boolean);
    if(small)return '<figure class="'+cls+'" title="'+safe('Batch '+trial.batch_id+(trial.data_origin==='synthetic'?' (data contoh ilustratif)':'')+'. '+facts.join('; ').replace(/<[^>]+>/g,'')+'. Digambar dari catatan organoleptik, bukan foto atau prediksi.')+'"><div class="vial-3d">'+vialSVG(o,uid)+'</div><figcaption>'+safe(trial.batch_id)+(trial.data_origin==='synthetic'?'<br><span class="vial-tag">contoh</span>':'')+'</figcaption></figure>';
    return '<figure class="'+cls+'"><div class="vial-3d">'+vialSVG(o,uid)+'</div><figcaption><strong>Batch '+safe(trial.batch_id)+'</strong>'+(trial.data_origin==='synthetic'?' <span class="vial-tag">Data contoh ilustratif</span>':'')+'<br>'+facts.join('<br>')+'<br><span class="tiny muted">Digambar dari catatan organoleptik, bukan foto atau prediksi.</span></figcaption></figure>';
  };
  window.organoLatest=formId=>{const t=(window.labSnapshot?.().trials||[]).filter(x=>x.formulation_id===formId);t.sort((a,b)=>String(b.measured_on).localeCompare(String(a.measured_on))||(b.created||0)-(a.created||0));return t.find(x=>x.organoleptic)||t[0]||null;};

  // ---------- Screening page section: organoleptic record + 3D of each ingredient ----------
  const organo={formId:'',mol:''};
  window.organoPick=id=>{organo.formId=id;organo.mol='';render();};
  window.organoMol=smiles=>{organo.mol=smiles;render();};
  window.organoSectionHTML=()=>{
    const snap=window.labSnapshot?.();if(!snap||!snap.forms.length)return '';
    const withObs=snap.forms.find(f=>snap.trials.some(t=>t.formulation_id===f.id&&t.organoleptic));
    const form=snap.forms.find(f=>f.id===organo.formId)||withObs||snap.forms[0];organo.formId=form.id;
    const trials=snap.trials.filter(t=>t.formulation_id===form.id).sort((a,b)=>String(a.measured_on).localeCompare(String(b.measured_on)));
    const mols=form.ingredients.filter(i=>i.smiles),current=mols.find(i=>i.smiles===organo.mol)||mols.find(i=>i.role==='fragrance')||mols[0];
    return '<section class="card mt organo"><div class="row between"><h2>4. Uji organoleptik dan visual 3D</h2><button onclick="go(\'input\')">Catat uji organoleptik</button></div>'
      +'<p class="tiny muted">Organoleptik (warna, kejernihan, endapan, pemisahan fase, bau) diamati orang saat uji lab, dengan latar hitam dan putih sesuai rencana eksperimen. Software tidak menebaknya; vial di bawah digambar dari catatan tersebut.</p>'
      +'<label class="field">Formulasi<select onchange="organoPick(this.value)">'+snap.forms.map(f=>'<option value="'+f.id+'" '+(f.id===form.id?'selected':'')+'>'+safe(f.name)+'</option>').join('')+'</select></label>'
      +'<div class="organo-grid"><div><h3>Sampel per batch</h3><div class="vial-row">'+(trials.length?trials.map(t=>organoVialHTML(t)).join(''):organoVialHTML(null))+'</div></div>'
      +'<div><h3>Struktur 3D bahan</h3>'+(mols.length?'<div class="organo-chips">'+mols.map(i=>'<button type="button" class="'+(i===current?'active':'')+'" onclick="organoMol(this.dataset.s)" data-s="'+safe(i.smiles)+'">'+safe(i.name)+'</button>').join('')+'</div>'+mol3dHTML(current.smiles,current.name):'<p class="muted">Formulasi ini belum menyimpan struktur (SMILES) bahannya.</p>')+'</div></div></section>';
  };

  const style=document.createElement('style');
  style.textContent='.mol3d{margin:8px 0}.mol3d-stage{position:relative;border-radius:14px;background:radial-gradient(circle at 40% 35%,#ffffff,#eeecf7);border:1px solid var(--line);overflow:hidden}.mol3d canvas{width:100%;height:100%;display:block;cursor:grab;touch-action:none}.mol3d canvas:active{cursor:grabbing}.mol3d-status{position:absolute;inset:0;display:grid;place-items:center;color:var(--muted);font-size:13px}.mol3d-status.err{color:#b3261e;padding:16px;text-align:center}.mol3d figcaption{margin-top:6px;font-size:13px}.mol3d-ctl button{padding:3px 10px;font-size:12px}.mol3d-link{border:0;background:none;padding:0;color:var(--link,#5026ff);font:inherit;text-decoration:underline dotted;cursor:pointer}.mol3d-link span{font-size:11px;text-decoration:none}'
    +'.vial{margin:0;display:grid;justify-items:center;gap:6px;width:150px;text-align:center;font-size:12px}.vial svg{width:96px;height:176px;display:block;overflow:visible}.vial-sm{width:72px;font-size:11px;line-height:1.3}.vial-sm svg{width:40px;height:74px}.vial-3d{perspective:500px}.vial-3d svg{transform-style:preserve-3d;animation:vial-sway 7s ease-in-out infinite;filter:drop-shadow(0 8px 10px #2a204a22)}.vial-wave{animation:vial-wave 3.2s ease-in-out infinite;transform-origin:center}.vial-shimmer{animation:vial-shimmer 4s ease-in-out infinite}.vial-empty figcaption{color:var(--muted)}.vial-tag{display:inline-block;background:#fff3dc;color:#8a4b00;border-radius:6px;padding:0 5px;font-size:11px}'
    +'@keyframes vial-sway{0%,100%{transform:rotateY(-14deg) rotateZ(-1deg)}50%{transform:rotateY(14deg) rotateZ(1deg)}}@keyframes vial-wave{0%,100%{transform:scaleY(1) translateY(0)}50%{transform:scaleY(1.6) translateY(1px)}}@keyframes vial-shimmer{0%,100%{opacity:.25}50%{opacity:.42}}@media(prefers-reduced-motion:reduce){.vial-3d svg,.vial-wave,.vial-shimmer{animation:none}}'
    +'.organo-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:24px;margin-top:8px}.vial-row{display:flex;flex-wrap:wrap;gap:18px}.organo-chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px}.organo-chips button{padding:4px 10px;font-size:12px}.organo-chips button.active{background:#ede7ff;border-color:#5026ff;color:#5026ff}@media(max-width:900px){.organo-grid{grid-template-columns:1fr}}'
    +'.rank-visual{display:flex;align-items:center}';
  document.head.append(style);
})();
