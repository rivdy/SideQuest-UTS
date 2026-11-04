/* Local document-grounded chat. All untrusted text is escaped before rendering. */
(() => {
  const api = '/api/rag';
  const rag = {documents:[], selected:new Set(), messages:[], status:null, error:'', busy:false, uploading:false, loaded:false, refreshing:false};
  const safe = value => esc(String(value ?? ''));
  const modes = {generated:'Jawaban Ollama lokal',retrieval_only:'Sumber ditemukan · model belum siap',no_evidence:'Belum ada sumber',no_supported_answer:'Belum ada jawaban terdukung'};
  function redraw(){if(route()==='chat')render();}
  async function request(path, options={}){
    const response=await (window.baylabFetch || fetch)(api+path,{...options,signal:AbortSignal.timeout(path==='/ask'?195000:30000)});
    let body;try{body=await response.json();}catch{throw new Error('Backend RAG belum aktif. Jalankan FastAPI di port 8000.');}
    if(!response.ok)throw new Error(typeof body.detail==='string'?body.detail:'Permintaan tidak valid. Periksa isian dan ukuran dokumen.');
    return body;
  }
  async function refresh(){
    if(rag.refreshing)return;rag.refreshing=true;
    try{[rag.documents,rag.status]=await Promise.all([request('/documents'),request('/status')]);rag.error='';const valid=new Set(rag.documents.map(d=>d.id));rag.selected=new Set([...rag.selected].filter(id=>valid.has(id)));}
    catch(error){rag.error=error.message;}finally{rag.loaded=true;rag.refreshing=false;redraw();}
  }
  function sourcesHTML(sources){return sources.map((s,i)=>'<details class="rag-source"><summary>['+(i+1)+'] '+safe(s.title)+' · hlm. '+safe(s.page)+'</summary><p class="tiny muted">Identitas sumber: '+safe(s.source_ref)+'</p><blockquote>'+safe(s.text)+'</blockquote></details>').join('');}
  function messagesHTML(){
    if(!rag.messages.length)return '<div class="rag-empty"><span class="stat-icon">'+icon('chat')+'</span><h2>Tanya dokumen Anda.</h2><p>Unggah proposal, abstrak, atau SDS yang boleh Anda gunakan. Jawaban dirangkai dari potongan dokumen terpilih, dengan kutipan yang dapat diperiksa.</p><p class="tiny muted">Belum ada dokumen? Tambahkan PDF, TXT, atau Markdown melalui panel Dokumen.</p></div>';
    return rag.messages.map(message=>{
      if(message.role==='user')return '<div class="message user">'+safe(message.text)+'</div>';
      if(message.error)return '<div class="message ai note amber">'+safe(message.error)+'</div>';
      const result=message.result;
      return '<div class="message ai"><div class="row tiny"><span class="avatar">AI</span><strong>'+safe(modes[result.mode]||result.mode)+'</strong></div><p class="tiny muted">'+safe(result.message)+'</p>'+result.claims.map(claim=>'<p>'+safe(claim.text)+'</p>'+claim.citations.map(c=>{const i=result.sources.findIndex(s=>s.id===c.source_id);return '<blockquote class="rag-quote">'+safe(c.quote)+' <strong>['+(i+1)+']</strong></blockquote>';}).join('')).join('')+sourcesHTML(result.sources)+'</div>';
    }).join('');
  }
  const ragHead=(...args)=>head(...args).replace(badge('Data contoh ilustratif','amber'),badge('Dokumen lokal','purple'));
  function chatView(){
    if(!rag.loaded&&!rag.refreshing)queueMicrotask(refresh);
    const ready=rag.status?.generation?.ready;
    return ragHead('Chat with AI','RAG lokal · jawaban dari dokumen, disertai kutipan sumber.','<button type="button" onclick="ragRefresh()">Muat ulang status</button><button class="primary" type="button" onclick="ragNew()" '+(rag.busy?'disabled':'')+'>+ Percakapan baru</button>')+
    '<div class="note mb">'+(ready?'Ollama siap · '+safe(rag.status.generation.model):'Model lokal belum siap. Pencarian sumber tetap tersedia setelah backend aktif.')+'<br><span class="tiny">Dokumen tetap diproses di komputer ini. Penelusuran menggunakan indeks kata BM25; keputusan risiko kimia tetap memerlukan rule engine tervalidasi.</span></div>'+
    (rag.error?'<p role="alert" class="note amber mb">'+safe(rag.error)+'</p>':'')+
    '<div class="rag-layout"><aside class="card"><h2>Dokumen</h2><p class="tiny muted">Centang untuk membatasi sumber. Tanpa pilihan: seluruh dokumen.</p><div class="rag-docs">'+(rag.documents.length?rag.documents.map(d=>'<div class="rag-document"><label class="check"><input type="checkbox" '+(rag.selected.has(d.id)?'checked':'')+' onchange="ragSelect(\''+d.id+'\',this.checked)"><strong>'+safe(d.title)+'</strong></label><p class="tiny muted">'+safe(d.source_ref)+' · '+d.chunks+' potongan</p><button type="button" class="link tiny" onclick="ragDelete(\''+d.id+'\')">Hapus dari indeks</button></div>').join(''):'<p class="tiny muted">Belum ada dokumen terindeks.</p>')+'</div><hr class="rag-rule"><h3>Tambah dokumen</h3><form id="rag-upload" onsubmit="event.preventDefault();ragUpload(this)"><label class="field">Judul<input name="title" maxlength="180" required placeholder="Proposal BAYLab AI"></label><label class="field">Identitas sumber<input name="source_ref" maxlength="240" required placeholder="DOI, nomor SDS, atau nama dokumen internal"></label><label class="field">Berkas (maks. 16 MB)<input name="file" type="file" accept=".pdf,.txt,.md" required></label><label class="check"><input type="checkbox" name="authorized" value="true" required> Saya berhak mengindeks isi dokumen ini secara lokal.</label><p class="tiny muted">PDF maksimal 80 halaman. PDF pindai perlu OCR; file asli tidak disimpan.</p><button class="primary wide" '+(rag.uploading?'disabled':'')+'>'+(rag.uploading?'Mengindeks...':'Unggah & indeks')+'</button></form></aside>'+
    '<section class="card rag-conversation"><div id="rag-messages" class="rag-messages" aria-live="polite">'+messagesHTML()+(rag.busy?'<p class="note" role="status">Mencari sumber dan menyusun jawaban di Ollama lokal...</p>':'')+'</div><form class="row mt" onsubmit="event.preventDefault();ragAsk(this.elements.question.value)"><input id="rag-question" name="question" placeholder="Apa yang dijelaskan dokumen tentang retensi H₂O₂?" aria-label="Pertanyaan tentang dokumen" minlength="3" maxlength="1600" required '+(rag.busy?'disabled':'')+'><button class="primary" '+(rag.busy?'disabled':'')+'>Kirim</button></form><p class="tiny muted">Sitasi diperiksa terhadap teks sumber. Itu tidak menjamin kesimpulan model benar; buka kutipan untuk meninjaunya. Chat tidak membaca data eksperimen di browser secara otomatis.</p></section></div>';
  }
  window.ragRefresh=refresh;
  window.ragSelect=(id,checked)=>{if(checked)rag.selected.add(id);else rag.selected.delete(id);};
  window.ragNew=()=>{if(!rag.busy){rag.messages=[];redraw();}};
  window.ragDelete=async id=>{
    if(!confirm('Hapus dokumen ini beserta seluruh potongannya dari indeks lokal?'))return;
    try{await request('/documents/'+encodeURIComponent(id),{method:'DELETE'});await refresh();}catch(error){rag.error=error.message;redraw();}
  };
  window.ragUpload=async form=>{
    if(rag.uploading)return;
    const data=new FormData(form);const file=data.get('file');
    if(file.size>16*1024*1024){rag.error='Ukuran maksimum berkas adalah 16 MB.';redraw();return;}
    rag.uploading=true;rag.error='';redraw();
    try{const result=await request('/documents',{method:'POST',body:data});await refresh();toast(result.duplicate?'Dokumen sudah ada di indeks.':'Dokumen berhasil diindeks.');}
    catch(error){rag.error=error.message;}finally{rag.uploading=false;redraw();}
  };
  window.ragAsk=async question=>{
    question=question.trim();if(question.length<3||rag.busy)return;
    rag.messages.push({role:'user',text:question});rag.busy=true;redraw();
    try{const result=await request('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,document_ids:[...rag.selected]})});rag.messages.push({role:'ai',result});}
    catch(error){rag.messages.push({role:'ai',error:error.message});}
    finally{rag.busy=false;redraw();document.querySelector('#rag-messages')?.lastElementChild?.scrollIntoView({block:'nearest',behavior:'smooth'});}
  };
  views.chat=chatView;
  askChat=question=>{go('chat');window.ragAsk(question);};
  const style=document.createElement('style');style.textContent='.rag-layout{display:grid;grid-template-columns:310px minmax(0,1fr);gap:18px}.rag-document{padding:12px 0;border-bottom:1px solid var(--line)}.rag-document p{overflow-wrap:anywhere;margin:4px 0 8px}.rag-document .check{align-items:flex-start}.rag-document input{flex-shrink:0}.rag-rule{border:0;border-top:1px solid var(--line);margin:22px 0}.rag-conversation{min-height:650px;display:flex;flex-direction:column}.rag-messages{flex:1;max-height:70vh;overflow:auto;padding:4px}.rag-empty{padding:40px 20px;color:var(--muted);max-width:600px}.rag-empty h2{margin-top:20px;color:var(--ink)}.rag-source{padding:12px;border:1px solid var(--line);border-radius:10px;margin:10px 0;font-size:12px;white-space:normal}.rag-source summary{cursor:pointer;font-weight:600}.rag-source blockquote,.rag-quote{white-space:pre-wrap;overflow-wrap:anywhere;border-left:3px solid #baa7ef;margin:12px 0;padding-left:12px;color:#645571;font-size:12px}.rag-layout .message{white-space:normal}.rag-layout .message p{white-space:pre-wrap}.rag-layout .message.user{white-space:pre-wrap}.rag-layout button:disabled{opacity:.5;cursor:wait}@media(max-width:900px){.rag-layout{grid-template-columns:1fr}.rag-conversation{min-height:500px}.rag-docs{max-height:250px;overflow:auto}}';document.head.append(style);
  if(route()==='chat')render();
})();
