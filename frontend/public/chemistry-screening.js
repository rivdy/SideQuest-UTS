/* Real local structure screening. Inputs and results live in memory, never localStorage. */
(() => {
  const chemistry = {smiles:'', query:'', namespace:'name', result:null, source:null, rules:null, evidence:null, busy:false, error:''};
  const safe = value => esc(String(value ?? ''));
  const redraw = () => { if(route()==='screening')render(); };
  async function request(path, body){
    const response=await fetch('/api/chemistry'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(25000)});
    let value;
    try { value=await response.json(); }
    catch { throw new Error('Backend belum tersedia. Jalankan FastAPI di port 8000.'); }
    if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:'Input tidak valid. Periksa SMILES atau identitas senyawa.');
    return value;
  }
  function evidenceHTML(items){
    return (items||[]).map(e=>'<details class="chem-evidence"><summary>'+safe(e.title)+'</summary><p class="tiny"><a href="'+safe(e.url)+'" target="_blank" rel="noopener noreferrer">'+safe(e.id)+' ↗</a></p><p class="tiny"><strong>Temuan:</strong> '+safe(e.finding)+'</p><p class="tiny"><strong>Kondisi studi:</strong> '+safe(e.conditions)+'</p><p class="note amber tiny"><strong>Batas penerapan:</strong> '+safe(e.limitation)+'</p><p class="tiny muted">Cakupan akses: '+safe(e.access_level)+'<br>Diperiksa '+safe(e.checked_on)+' · Draft berbasis literatur, belum validasi ahli.</p></details>').join('');
  }
  function resultHTML(){
    const r=chemistry.result;
    if(!r)return '<div class="card chem-empty"><h2>Mulai dari struktur molekul</h2><p>Masukkan SMILES atau cari identitas senyawa di PubChem. Hasil dihitung setelah Anda menekan Analisis struktur.</p><p class="tiny muted">Parfum dengan komposisi rahasia atau campuran homolog tidak dapat diwakili oleh satu struktur. Minta data komponen dari pemasok.</p></div>';
    return '<section class="card"><div class="row between"><h2>Hasil komputasi struktur</h2>'+badge('Aturan draft','amber')+'</div><img class="chem-molecule" src="'+safe(r.depiction)+'" alt="Struktur molekul; atom yang cocok dengan pola draft disorot"><div class="meta"><span>Rumus molekul</span><strong>'+safe(r.molecular_formula)+'</strong><span>Massa molekul</span><span>'+safe(r.molecular_weight)+' g/mol</span><span>Jumlah atom</span><span>'+r.atom_count+'</span><span>Muatan formal</span><span>'+r.formal_charge+'</span></div><p class="tiny">SMILES kanonik</p><code class="chem-code">'+safe(r.canonical_smiles)+'</code><p class="tiny muted">'+safe(r.engine)+' · '+safe(r.ruleset_version)+'<br>Dihitung: '+safe(new Date(r.analyzed_at).toLocaleString('id-ID'))+'</p></section>'+
    '<section class="card"><h2>Gugus yang terdeteksi</h2>'+(r.matches.length?r.matches.map(m=>'<article class="chem-rule"><div class="row between"><strong>'+safe(m.rule.name)+'</strong>'+badge(m.count+' kecocokan','purple')+'</div><code class="chem-code">'+safe(m.rule.smarts)+'</code><p class="tiny">'+safe(m.rule.id)+' · '+safe(m.rule.status)+' · versi '+safe(m.rule.version)+'</p><p class="tiny muted">Indeks atom (mulai 0): '+m.atom_matches.map(a=>a.join(', ')).join(' / ')+'<br>Catatan literatur: '+safe(m.rule.chemical_evidence)+'</p>'+evidenceHTML(m.rule.evidence)+'</article>').join(''):'<p>Tidak ada kecocokan dalam enam pola draft ini. Ini bukan kesimpulan keamanan.</p>')+'</section><section class="card"><h2>Konteks formulasi H₂O₂</h2><p class="tiny muted">Panduan umum; tidak dihitung sebagai hasil analisis molekul atau ambang formula.</p>'+evidenceHTML(r.formulation_context)+'</section><p class="note amber" role="status">'+safe(r.message)+'</p><button onclick="chemistryExport()">Unduh laporan JSON</button>';
  }
  function view(){
    const header=head('Knowledge Screening','Analisis struktur nyata dengan RDKit · pencarian identitas PubChem.','<button onclick="go(\'chat\')">Telusuri dokumen RAG →</button>','formulasi').replace(badge('Data contoh ilustratif','amber'),badge('Komputasi lokal · draft','purple'));
    return header+'<div class="note amber mb"><strong>Draft berbasis literatur.</strong> Sumber publik dan batas penerapannya tersedia. Enam pola ini bukan aturan LKPI R-01–R-12 yang disahkan ahli. Risiko oksidasi, kompatibilitas formula, dan efikasi belum dinilai.</div>'+
    '<div class="chem-layout"><aside class="stack"><section class="card"><h2>1. Identitas senyawa</h2><p class="tiny muted">Pencarian opsional. Nama/CAS atau CID dikirim ke PubChem NIH hanya ketika Anda menekan Cari. Jangan masukkan nama formula rahasia.</p><form onsubmit="event.preventDefault();chemistryLookup(this)"><label class="field">Jenis pencarian<select '+(chemistry.busy?'disabled':'')+' name="namespace" onchange="chemistryNamespace(this.value)"><option value="name" '+(chemistry.namespace==='name'?'selected':'')+'>Nama / CAS</option><option value="cid" '+(chemistry.namespace==='cid'?'selected':'')+'>PubChem CID</option></select></label><label class="field">Identitas<input '+(chemistry.busy?'disabled':'')+' name="query" maxlength="160" required value="'+safe(chemistry.query)+'" placeholder="Mis. limonene atau 440917" oninput="chemistryQuery(this.value)"></label><button class="wide" '+(chemistry.busy?'disabled':'')+'>Cari di PubChem</button></form>'+(chemistry.source?'<p class="tiny"><a href="'+safe(chemistry.source.source_url)+'" target="_blank" rel="noopener noreferrer">'+safe(chemistry.source.title)+' · CID '+chemistry.source.cid+'</a><br>Diambil: '+safe(new Date(chemistry.source.retrieved_at).toLocaleString('id-ID'))+'<br>'+safe(chemistry.source.identity_note)+'</p>':'')+'</section>'+
    '<section class="card"><h2>2. Struktur untuk dianalisis</h2><form onsubmit="event.preventDefault();chemistryScreen()"><label class="field">SMILES<textarea '+(chemistry.busy?'disabled':'')+' id="chem-smiles" name="smiles" required maxlength="2000" rows="4" placeholder="Masukkan struktur SMILES" oninput="chemistryInput(this.value)">'+safe(chemistry.smiles)+'</textarea></label><p class="tiny muted">Satu molekul, maksimum 200 atom. SMILES diproses di backend lokal; tidak dikirim ke PubChem atau LLM.</p><button class="primary wide" '+(chemistry.busy?'disabled':'')+'>'+(chemistry.busy?'Memproses…':'Analisis struktur')+'</button></form></section><section class="card"><h3>Bagaimana hasil dibaca?</h3><p class="tiny">Sorotan atom menunjukkan kecocokan SMARTS. Jumlah kecocokan bukan skor risiko. Sumber identitas PubChem tidak otomatis menjadi bukti kompatibilitas dengan H₂O₂.</p><button onclick="chemistryRules()" '+(chemistry.busy?'disabled':'')+'>Lihat semua pola draft</button>'+(chemistry.rules?chemistry.rules.rules.map(r=>'<p class="tiny"><strong>'+safe(r.name)+'</strong><br><code>'+safe(r.smarts)+'</code><br>'+safe(r.id)+' · draft</p>').join(''):'')+'</section><section class="card"><h3>Pustaka bukti</h3><p class="tiny muted">Enam sumber awal. Catatan hasil pencarian dipisahkan dari sumber yang dapat dibaca langsung. Pembaruan belum otomatis.</p><button onclick="chemistryEvidence()">Lihat sumber literatur</button>'+evidenceHTML(chemistry.evidence?.sources)+'</section></aside><div class="stack">'+(chemistry.error?'<p class="note amber" role="alert">'+safe(chemistry.error)+'</p>':'')+resultHTML()+'</div></div>';
  }
  window.chemistryNamespace=v=>{chemistry.namespace=v;};
  window.chemistryQuery=v=>{chemistry.query=v;};
  window.chemistryInput=v=>{chemistry.smiles=v;chemistry.source=null;chemistry.result=null;const stack=document.querySelector('.chem-layout > div.stack');if(stack)stack.innerHTML=resultHTML();};
  window.chemistryLookup=async form=>{
    if(chemistry.busy)return;
    chemistry.query=form.query.value.trim();chemistry.namespace=form.namespace.value;chemistry.busy=true;chemistry.error='';chemistry.result=null;chemistry.source=null;redraw();
    try{const source=await request('/pubchem',{query:chemistry.query,namespace:chemistry.namespace,consent_external_lookup:true});chemistry.source=source;chemistry.smiles=source.smiles;}
    catch(error){chemistry.error=error.message;}
    finally{chemistry.busy=false;redraw();}
  };
  window.chemistryScreen=async()=>{
    if(chemistry.busy)return;
    chemistry.smiles=chemistry.smiles.trim();chemistry.busy=true;chemistry.error='';chemistry.result=null;redraw();
    try{chemistry.result=await request('/screen',{smiles:chemistry.smiles});}
    catch(error){chemistry.error=error.message;}
    finally{chemistry.busy=false;redraw();}
  };
  window.chemistryRules=async()=>{try{chemistry.rules=await request('/rules');chemistry.error='';}catch(error){chemistry.error=error.message;}redraw();};
  window.chemistryEvidence=async()=>{try{chemistry.evidence=await request('/evidence');chemistry.error='';}catch(error){chemistry.error=error.message;}redraw();};
  window.chemistryExport=()=>{if(!chemistry.result)return;const report={...chemistry.result,source:chemistry.source};delete report.depiction;const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='baylab-screening-draft.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  const style=document.createElement('style');style.textContent='.chem-layout{display:grid;grid-template-columns:minmax(270px,340px) minmax(0,1fr);gap:24px}.chem-layout>*{min-width:0}.chem-molecule{display:block;width:100%;max-width:520px;height:auto;margin:12px auto}.chem-code{display:block;white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f3ff;padding:10px;border-radius:8px}.chem-evidence{margin:12px 0;overflow-wrap:anywhere}.chem-evidence summary{cursor:pointer;font-weight:600;line-height:1.5}.chem-rule{border-top:1px solid #eceaf3;padding:16px 0}.chem-empty{min-height:250px;display:flex;flex-direction:column;justify-content:center}.chem-layout textarea{width:100%;box-sizing:border-box;font-family:monospace}.chem-layout .meta{grid-template-columns:1fr 1fr}@media(max-width:900px){.chem-layout{grid-template-columns:1fr}}';document.head.append(style);
  views.screening=view;
  if(route()==='screening')render();
})();
