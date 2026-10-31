"use client";

import { useState, type CSSProperties, type PointerEvent } from "react";

export default function Home() {
  const [visible, setVisible] = useState(false);
  const [paused, setPaused] = useState(false);
  const [theme, setTheme] = useState("violet");
  const [message, setMessage] = useState("");
  function move(event: PointerEvent<HTMLElement>) {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches || paused) return;
    const rect = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty("--mx", `${(event.clientX - rect.left - rect.width / 2) / 65}px`);
    event.currentTarget.style.setProperty("--my", `${(event.clientY - rect.top - rect.height / 2) / 65}px`);
  }
  return (
    <main className="bl-login" data-theme={theme} data-paused={paused} onPointerMove={move} onPointerLeave={event => { event.currentTarget.style.setProperty("--mx", "0px"); event.currentTarget.style.setProperty("--my", "0px"); }}>
      <div className="bl-atmosphere" aria-hidden="true">{Array.from({length: 16}, (_, i) => <i key={i} style={{"--i": i, "--left": `${(i * 37 + 9) % 100}%`, "--size": `${5 + i % 4 * 8}px`} as CSSProperties} />)}</div>
      <header className="bl-header">
        <a href="#login" className="bl-brand" aria-label="BAYLab AI, halaman masuk"><svg viewBox="0 0 40 40" aria-hidden="true"><path d="M10 12 29 8 31 29 13 32 10 12 31 29M29 8 13 32"/><circle cx="10" cy="12" r="5"/><circle cx="29" cy="8" r="4"/><circle cx="31" cy="29" r="6"/><circle cx="13" cy="32" r="4"/></svg><span>BAYLab<span className="bl-ai">AI</span></span></a>
        <span className="bl-nav-note">SCIENCE IN EVERY FORMULA.</span>
        <span className="bl-preview"><i /> Pratinjau interaktif</span>
      </header>
      <div className="bl-stage">
        <section className="bl-story">
          <p className="bl-eyebrow"><span /> DARI IDE, MENJADI INOVASI</p>
          <h1>Racik.<br/><em>Temukan.</em><br/><span>Beri dampak.</span></h1>
          <p className="bl-description">Ruang untuk ide besar dan detail kecil.<br/>Eksplorasi formulasi H₂O₂ beraroma,<br className="bl-desktop-break"/> bersama sains yang bisa ditelusuri.</p>
          <a className="bl-explore" href="./demo.html#dashboard">Jelajahi ruang lab <span aria-hidden="true">↗</span></a>
          <div className="bl-story-foot"><span className="bl-mini-orbit" aria-hidden="true">✳</span><p>Dirancang untuk rasa ingin tahu.<br/><strong>Dikembangkan untuk tim R&D.</strong></p></div>
        </section>
        <div className="bl-scene" aria-hidden="true">
          <div className="bl-halo"/><div className="bl-orbit bl-orbit-one"/><div className="bl-orbit bl-orbit-two"/>
          <span className="bl-float-label bl-label-top">H₂O₂ <small>THE SCIENCE OF POSSIBILITY</small></span>
          <div className="bl-molecule bl-molecule-one"><b/><i/><b/><i/><b/></div>
          <div className="bl-molecule bl-molecule-two"><b/><i/><b/></div>
          <div className="bl-bottle-position"><div className="bl-bottle">
            <div className="bl-cap"><i/></div><div className="bl-neck"/>
            <div className="bl-glass"><div className="bl-liquid"/><div className="bl-glint"/>
              <div className="bl-bottle-label"><span className="bl-label-brand">BAYLab AI</span><span className="bl-label-line"/><span className="bl-label-title">A little<br/><em>curiosity.</em><br/>A new<br/>possibility.</span><span className="bl-label-bottom">FORMULATION RESEARCH<br/>H₂O₂ + AROMA EXPLORATION</span></div>
              <div className="bl-volume">RESEARCH CONCEPT · 001</div>
            </div>
          </div></div>
          <span className="bl-float-label bl-label-bottom-scene"><span className="bl-spark">✦</span> Molekul kecil.<br/><strong>Kemungkinan besar.</strong></span>
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
      <footer className="bl-footer"><span>BAYLab AI <span className="bl-footer-separator">/</span> Riset dengan rasa ingin tahu.</span><div className="bl-controls"><span>SUASANA</span><button className="bl-theme bl-violet" type="button" data-color="violet" aria-label="Suasana violet" aria-pressed={theme === "violet"} onClick={() => setTheme("violet")}/><button className="bl-theme bl-teal" type="button" data-color="teal" aria-label="Suasana teal" aria-pressed={theme === "teal"} onClick={() => setTheme("teal")}/><span className="bl-control-line"/><button id="bl-pause" className="bl-pause" type="button" aria-pressed={paused} onClick={() => setPaused(!paused)}>{paused ? "▷ Putar animasi" : "Ⅱ Jeda animasi"}</button></div><span className="bl-footer-right">HUMAN CURIOSITY. SCIENTIFIC CLARITY.</span></footer>
    </main>
  );
}
