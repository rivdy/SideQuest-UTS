"use client";

import { useState, useEffect, type CSSProperties, type PointerEvent } from "react";

export default function Home() {
  const [visible, setVisible] = useState(false);
  const [paused, setPaused] = useState(false);
  const [theme, setTheme] = useState("violet");
  const [message, setMessage] = useState("");
  useEffect(() => { const root = document.querySelector<HTMLElement>(".bl-login"); if (root) return mountKimiMotion(root); }, []);
  function move(event: PointerEvent<HTMLElement>) {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches || paused) return;
    const rect = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty("--mx", `${(event.clientX - rect.left - rect.width / 2) / 65}px`);
    event.currentTarget.style.setProperty("--my", `${(event.clientY - rect.top - rect.height / 2) / 65}px`);
  }
  return (
    <main className="bl-login bl-kimi" data-theme={theme} data-paused={paused} onPointerMove={move} onPointerLeave={event => { event.currentTarget.style.setProperty("--mx", "0px"); event.currentTarget.style.setProperty("--my", "0px"); }}>
      <div className="bl-kimi-hero"><canvas className="bl-contours" aria-hidden="true"/><div className="bl-scan" aria-hidden="true"/><div className="bl-atmosphere" aria-hidden="true">{Array.from({length: 16}, (_, i) => <i key={i} style={{"--i": i, "--left": `${(i * 37 + 9) % 100}%`, "--size": `${5 + i % 4 * 8}px`} as CSSProperties} />)}</div>
      <header className="bl-header">
        <a href="#login" className="bl-brand" aria-label="BAYLab AI, halaman masuk"><svg viewBox="0 0 40 40" aria-hidden="true"><path d="M10 12 29 8 31 29 13 32 10 12 31 29M29 8 13 32"/><circle cx="10" cy="12" r="5"/><circle cx="29" cy="8" r="4"/><circle cx="31" cy="29" r="6"/><circle cx="13" cy="32" r="4"/></svg><span>BAYLab<span className="bl-ai">AI</span></span></a>
        <span className="bl-nav-note">BAYLAB / FORMULATION RESEARCH SYSTEMS</span>
        <span className="bl-preview"><i /> Pratinjau interaktif</span>
      </header>
      <div className="bl-stage">
        <section className="bl-story">
          <p className="bl-eyebrow"><span /> RESEARCH_001 / SCENT EXPLORATION</p>
          <h1>Racik.<br/><em>Temukan.</em><br/><span>Beri dampak.</span></h1>
          <p className="bl-description">Ruang untuk ide besar dan detail kecil.<br/>Eksplorasi formulasi H₂O₂ beraroma,<br className="bl-desktop-break"/> bersama sains yang bisa ditelusuri.</p>
          <a className="bl-explore" href="./demo.html#dashboard">Jelajahi ruang lab <span aria-hidden="true">↗</span></a>
          <div className="bl-story-foot"><span className="bl-mini-orbit" aria-hidden="true">✳</span><p>Dirancang untuk rasa ingin tahu.<br/><strong>Dikembangkan untuk tim R&D.</strong></p></div>
        </section>
        <div className="bl-scene bl-perfume-scene" role="img" aria-label="Tiga botol parfum BAYLab: Citrus Lemon, Bergamot, dan Lavender, dikelilingi buah citrus dan bunga lavender.">
          <div className="bl-halo"/><div className="bl-orbit bl-orbit-one"/><div className="bl-orbit bl-orbit-two"/>
          <span className="bl-collection">BOTANICAL SERIES / 001—003 <small>03 NOTES. ENDLESS POSSIBILITIES.</small></span>
          {[
            {id:"lemon", number:"01", name:"Citrus", sub:"Lemon", note:"BRIGHT · ZESTY"},
            {id:"bergamot", number:"02", name:"Green", sub:"Bergamot", note:"FRESH · CITRUS"},
            {id:"lavender", number:"03", name:"Soft", sub:"Lavender", note:"FLORAL · AROMATIC"}
          ].map(scent => <div className={`bl-bottle-position bl-perfume-position bl-perfume-${scent.id}`} key={scent.id}>
            <div className="bl-perfume-bottle">
              <div className="bl-perfume-cap"/><div className="bl-perfume-collar"/>
              <div className="bl-perfume-glass"><div className="bl-perfume-juice"/><div className="bl-perfume-tube"/>
                <div className="bl-perfume-label"><span>BAYLab AI</span><i>NO. {scent.number}</i><strong>{scent.name}<em>{scent.sub}</em></strong><small>{scent.note}</small><b>SCENT EXPLORATION</b></div>
              </div>
            </div>
          </div>)}
          <div className="bl-ingredient bl-lemon-slice"><Citrus kind="lemon"/></div>
          <div className="bl-ingredient bl-bergamot-slice"><Citrus kind="bergamot"/></div>
          <div className="bl-ingredient bl-whole-lemon"><span/><i/></div>
          <div className="bl-ingredient bl-leaf bl-leaf-one"/><div className="bl-ingredient bl-leaf bl-leaf-two"/>
          <svg className="bl-ingredient bl-lavender-sprig" viewBox="0 0 90 180" aria-hidden="true">
            <path d="M45 176Q37 100 48 17M42 138Q14 114 18 70M43 114Q75 86 71 48" fill="none" stroke="#9ab37d" strokeWidth="3"/>
            {[0,1,2,3,4,5].map(i => <g key={i}><ellipse cx={43-i%2*5} cy={26+i*14} rx="7" ry="11" fill={i%2 ? "#bfa2e9":"#e1c8fa"} transform={`rotate(-22 43 ${26+i*14})`}/><ellipse cx="55" cy={30+i*14} rx="6" ry="10" fill="#9a74c7" transform={`rotate(27 55 ${30+i*14})`}/></g>)}
            {[0,1,2].map(i => <g key={i}><ellipse cx="18" cy={70+i*12} rx="6" ry="9" fill="#baa0df"/><ellipse cx="71" cy={48+i*13} rx="6" ry="9" fill="#d3b8ec"/></g>)}
          </svg>
          <span className="bl-perfume-caption">Citrus lemon · Bergamot · Lavender<small>Inspirasi aroma untuk eksplorasi formulasi</small></span>
          <div className="bl-bottle-shadow"/>
        </div>
        <section className="bl-access" aria-labelledby="bl-login-title">
          <form className="bl-form login-box" id="bl-login-form" onSubmit={event => { event.preventDefault(); setMessage("Login organisasi belum aktif. Pilih Jelajahi demo untuk mencoba BAYLab tanpa akun asli."); }}>
            <div className="bl-form-top"><span className="bl-form-icon" aria-hidden="true">↗</span><span>RUANG KERJA BAYLAB</span></div>
            <h2 id="bl-login-title">Ide hebat dimulai<br/>dari sini.</h2><p className="bl-form-intro">Selamat datang kembali di ruang riset Anda.</p>
            <label className="bl-field" htmlFor="bl-email">Email<input id="bl-email" type="email" placeholder="nama@lkpi.co.id" autoComplete="off" maxLength={254} required /></label>
            <label className="bl-field" htmlFor="password">Kata sandi</label><div className="bl-password"><input id="password" type={visible ? "text" : "password"} placeholder="Masukkan kata sandi" autoComplete="off" minLength={6} maxLength={128} required/><button id="bl-reveal" type="button" aria-pressed={visible} aria-label={visible ? "Sembunyikan kata sandi" : "Tampilkan kata sandi"} onClick={() => setVisible(!visible)}>{visible ? "Sembunyikan" : "Lihat"}</button></div>
            <div className="bl-options"><span>Akses khusus tim R&D</span><button id="bl-forgot" type="button" onClick={() => setMessage("Hubungi admin LKPI untuk akses organisasi. Pada pratinjau ini, Anda bisa masuk melalui Jelajahi demo.")}>Lupa kata sandi?</button></div>
            <button className="bl-submit" type="submit">Masuk ke ruang lab <span aria-hidden="true">↗</span></button>
            <div className="bl-divider"><span/> atau mulai eksplorasi <span/></div>
            <a className="bl-demo" href="./demo.html#dashboard">Jelajahi demo <span aria-hidden="true">→</span></a>
            <p id="bl-status" className="bl-status" role="status" aria-live="polite">{message}</p>
            <p className="bl-demo-note"><span aria-hidden="true">◇</span> Mode pratinjau. Gunakan data contoh, bukan akun atau data rahasia.</p>
          </form>
        </section>
      </div>
      </div>
      <section className="bl-research" aria-labelledby="bl-research-title">
        <div className="bl-checker" aria-hidden="true"/>
        <div className="bl-section-meta"><span>[ 01 / THE RESEARCH LOOP ]</span><span>BAYLAB AI — HUMAN + SCIENCE</span></div>
        <div className="bl-research-grid">
          <div><p className="bl-kicker">DARI AROMA KE HIPOTESIS</p><h2 id="bl-research-title">RASA INGIN TAHU.<br/><em>ALUR YANG TERUKUR.</em></h2><p className="bl-research-copy">Kenali bahan, telusuri bukti, lalu rancang pengujian. Setiap ide formulasi memerlukan penilaian ahli dan verifikasi laboratorium.</p><a href="./demo.html#screening" className="bl-research-cta">JELAJAHI SCREENING <span>↗</span></a></div>
          <div className="bl-research-map" role="img" aria-label="Alur riset: bahan, screening, literatur, dan eksperimen.">
            <svg viewBox="0 0 600 400"><defs><pattern id="research-dots" width="16" height="16" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#776b8e" opacity=".35"/></pattern></defs><rect width="600" height="400" fill="url(#research-dots)"/><path className="bl-map-base" d="M100 270L160 100 390 65 505 190 390 325 100 270Z"/><path className="bl-map-trace" d="M100 270L160 100 390 65 505 190 390 325 100 270Z" pathLength="100"/>{[[100,270],[160,100],[390,65],[505,190],[390,325]].map(([x,y],i)=><g key={i}><circle cx={x} cy={y} r="9" fill="#15121c" stroke="#b99aff" strokeWidth="2"/><circle cx={x} cy={y} r="3" fill="#d3bfff"/></g>)}<text x="46" y="310">01 / BAHAN</text><text x="130" y="74">02 / SCREENING</text><text x="368" y="39">03 / LITERATUR</text><text x="400" y="222">04 / KANDIDAT</text><text x="340" y="363">05 / EKSPERIMEN</text><circle className="bl-map-ping" cx="290" cy="201" r="47"/><circle cx="290" cy="201" r="32" fill="none" stroke="#695780"/><text className="bl-map-center" x="290" y="205" textAnchor="middle">BAYLAB</text></svg>
            <span className="bl-map-caption">VISUALISASI ALUR / BUKAN HASIL ANALISIS</span>
          </div>
        </div>
      </section>
      <section className="bl-notes" aria-labelledby="bl-notes-title">
        <div className="bl-section-meta"><span>[ 02 / BOTANICAL LIBRARY ]</span><span>03 KARAKTER / SATU RUANG EKSPLORASI</span></div>
        <h2 id="bl-notes-title">KENALI <em>KARAKTERNYA.</em></h2>
        <div className="bl-note-grid">
          {[{n:"01",title:"CITRUS LEMON",type:"BRIGHT / ZESTY",text:"Inspirasi citrus yang cerah. Mulai eksplorasi dari identitas bahan dan komposisinya."},{n:"02",title:"GREEN BERGAMOT",type:"FRESH / CITRUS",text:"Nuansa hijau dalam koleksi aroma. Telusuri sumber sebelum memilih kandidat formulasi."},{n:"03",title:"SOFT LAVENDER",type:"FLORAL / AROMATIC",text:"Karakter floral sebagai arah eksplorasi. Profil aroma tetap memerlukan evaluasi organoleptik."}].map(note=><article className="bl-note-card" key={note.n}><span className="bl-note-number">{note.n}</span><span className="bl-note-type">{note.type}</span><h3>{note.title}</h3><p>{note.text}</p><a href="./demo.html#library">BUKA LIBRARY BAHAN ↗</a></article>)}
        </div>
        <p className="bl-notes-disclaimer">Koleksi visual merupakan konsep aroma, bukan rekomendasi kompatibilitas H₂O₂ atau klaim efikasi produk.</p>
      </section>
      <footer className="bl-footer"><span>BAYLab AI <span className="bl-footer-separator">/</span> Riset dengan rasa ingin tahu.</span><div className="bl-controls"><span>SUASANA</span><button className="bl-theme bl-violet" type="button" data-color="violet" aria-label="Suasana violet" aria-pressed={theme === "violet"} onClick={() => setTheme("violet")}/><button className="bl-theme bl-teal" type="button" data-color="teal" aria-label="Suasana teal" aria-pressed={theme === "teal"} onClick={() => setTheme("teal")}/><span className="bl-control-line"/><button id="bl-pause" className="bl-pause" type="button" aria-pressed={paused} onClick={() => setPaused(!paused)}>{paused ? "▷ Putar animasi" : "Ⅱ Jeda animasi"}</button></div><span className="bl-footer-right">HUMAN CURIOSITY. SCIENTIFIC CLARITY.</span></footer>
    </main>
  );
}

function Citrus({kind}: {kind: "lemon" | "bergamot"}) {
  const green = kind === "bergamot";
  return <svg viewBox="0 0 120 120" aria-hidden="true">
    <defs><radialGradient id={`citrus-${kind}`}><stop stopColor={green ? "#edf3b1" : "#fff6bd"}/><stop offset="1" stopColor={green ? "#a9c548" : "#f6bf35"}/></radialGradient></defs>
    <circle cx="60" cy="60" r="57" fill={green ? "#6e9135" : "#e9b527"}/><circle cx="60" cy="60" r="51" fill="#faf0c6"/>
    {Array.from({length:9},(_,i)=>{const a=i*Math.PI*2/9+.025,b=(i+1)*Math.PI*2/9-.025;return <path key={i} d={`M${60+8*Math.cos(a)} ${60+8*Math.sin(a)} L${60+46*Math.cos(a)} ${60+46*Math.sin(a)} A46 46 0 0 1 ${60+46*Math.cos(b)} ${60+46*Math.sin(b)} L${60+8*Math.cos(b)} ${60+8*Math.sin(b)}Z`} fill={`url(#citrus-${kind})`} stroke="#fff5d9" strokeWidth="1.2"/>;})}
    <circle cx="60" cy="60" r="7" fill="#fff4d3"/>
    {Array.from({length:27},(_,i)=><ellipse key={i} cx={60+ (22+i%3*8)*Math.cos(i*2.4)} cy={60+(22+i%3*8)*Math.sin(i*2.4)} rx="1.2" ry="3" fill="#fffbe2" opacity=".48" transform={`rotate(${i*32} ${60+(22+i%3*8)*Math.cos(i*2.4)} ${60+(22+i%3*8)*Math.sin(i*2.4)})`}/>)}
  </svg>;
}

function mountKimiMotion(root: HTMLElement): () => void {
  const canvas=root.querySelector<HTMLCanvasElement>('.bl-contours');
  const hero=root.querySelector<HTMLElement>('.bl-kimi-hero');
  const ctx=canvas?.getContext('2d');
  if(!canvas || !hero || !ctx)return ()=>{};
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const bottles=Array.from(root.querySelectorAll<HTMLElement>('.bl-perfume-position'));
  const ingredients=Array.from(root.querySelectorAll<HTMLElement>('.bl-ingredient'));
  const reveal=Array.from(root.querySelectorAll<HTMLElement>('.bl-story h1,.bl-access,.bl-note-card'));
  const states=reveal.map(()=>({value:0,velocity:0}));
  const trace=root.querySelector<SVGPathElement>('.bl-map-trace');
  const section=root.querySelector<HTMLElement>('.bl-research');
  const scan=root.querySelector<HTMLElement>('.bl-scan');
  let width=0,height=0,frame=0,last=0,clock=0,progress=0;
  const resize=()=>{width=hero.clientWidth;height=hero.clientHeight;const dpr=Math.min(devicePixelRatio||1,1.5);canvas.width=width*dpr;canvas.height=height*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);};
  const draw=(time:number)=>{
    const dt=Math.min((time-(last||time))/1000,.032);last=time;
    if(root.dataset.paused!=='true' && !document.hidden){
      if(!reduced.matches)clock+=dt;
      const heroBox=hero.getBoundingClientRect();
      if(heroBox.bottom>0 && heroBox.top<innerHeight){
        ctx.clearRect(0,0,width,height);ctx.strokeStyle=root.dataset.theme==='teal'?'rgba(22,105,99,.13)':'rgba(85,56,138,.13)';ctx.lineWidth=.8;
        for(let n=0;n<22;n++){ctx.beginPath();for(let x=-20;x<width+20;x+=16){const y=height*.45+(n-11)*24+Math.sin(x/155+clock*.18+n*.18)*65+Math.cos(x/280-clock*.13)*55;if(x===-20)ctx.moveTo(x,y);else ctx.lineTo(x,y);}ctx.stroke();}
        bottles.forEach((el,i)=>{el.style.transform=`translateY(${Math.sin(clock*.8+i*1.8)*12}px) rotate(${[-17,4,17][i]+Math.sin(clock*.5+i)*3}deg)`;});
        ingredients.forEach((el,i)=>{el.style.translate=`${Math.sin(clock*.5+i)*4}px ${Math.sin(clock*.7+i)*10}px`;el.style.rotate=`${Math.sin(clock*.45+i)*7}deg`;});
        if(scan){scan.style.top=`${clock*.14%1*100}%`;scan.style.opacity=reduced.matches?'0':'.4';}
      }
      reveal.forEach((el,i)=>{const state=states[i];const target=el.getBoundingClientRect().top<innerHeight-20?1:state.value;if(reduced.matches)state.value=1;else for(let t=0;t<dt;t+=.001){state.velocity+=((target-state.value)*90-state.velocity*26)*.001;state.value+=state.velocity*.001;}el.style.opacity=String(state.value);el.style.translate=`0 ${(1-state.value)*25}px`;});
      if(section&&trace){const box=section.getBoundingClientRect();if(box.top<innerHeight*.8&&box.bottom>0)progress=Math.min(1,progress+(reduced.matches?1:dt/6));trace.style.strokeDashoffset=String(100-progress*100);const cover=innerWidth>820&&!reduced.matches?Math.max(0,Math.min(1,(innerHeight-box.top)/innerHeight)):0;hero.style.scale=String(1-cover*.05);hero.style.filter=`brightness(${1-cover*.2})`;}
    }
    frame=requestAnimationFrame(draw);
  };
  resize();const observer=new ResizeObserver(resize);observer.observe(hero);frame=requestAnimationFrame(draw);
  return ()=>{cancelAnimationFrame(frame);observer.disconnect();};
}
