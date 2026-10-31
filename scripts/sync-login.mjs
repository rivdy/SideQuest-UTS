// Keep the buildless prototype login synchronized with the Next.js design.
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const source = fs.readFileSync('frontend/src/app/page.tsx', 'utf8');
const output = ts.transpileModule(source, {compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
const mod = {exports:{}};
new Function('require','module','exports',output)(require,mod,mod.exports);
const markup = renderToStaticMarkup(React.createElement(mod.exports.default)).replaceAll('./demo.html#dashboard','#dashboard');
let html = fs.readFileSync('index.html','utf8');
html = html.replace(/^function login\(\).*$/m, () => 'function login(){return '+JSON.stringify(markup)+'}');
const css = fs.readFileSync('frontend/src/app/login.css','utf8');
html = html.replace(/<style id="baylab-soda-login">[\s\S]*?<\/style>/g,'');
html = html.replace('</head>','<style id="baylab-soda-login">'+css+'</style></head>');
html = html.replace(/<script id="baylab-login-events">[\s\S]*?<\/script>/g,'');
const events = `
document.addEventListener('submit',function(event){if(event.target.id!=='bl-login-form')return;event.preventDefault();document.getElementById('bl-status').textContent='Login organisasi belum aktif. Pilih Jelajahi demo untuk mencoba BAYLab tanpa akun asli.';});
document.addEventListener('click',function(event){
 const root=event.target.closest('.bl-login');if(!root)return;
 const button=event.target.closest('button');if(!button)return;
 if(button.id==='bl-reveal'){const input=root.querySelector('#password');const visible=input.type==='password';input.type=visible?'text':'password';button.textContent=visible?'Sembunyikan':'Lihat';button.setAttribute('aria-pressed',String(visible));button.setAttribute('aria-label',visible?'Sembunyikan kata sandi':'Tampilkan kata sandi');}
 if(button.id==='bl-forgot')root.querySelector('#bl-status').textContent='Hubungi admin LKPI untuk akses organisasi. Pada pratinjau ini, Anda bisa masuk melalui Jelajahi demo.';
 if(button.id==='bl-pause'){const paused=root.dataset.paused!=='true';root.dataset.paused=String(paused);button.setAttribute('aria-pressed',String(paused));button.textContent=paused?'▷ Putar animasi':'Ⅱ Jeda animasi';}
 if(button.dataset.color){root.dataset.theme=button.dataset.color;root.querySelectorAll('[data-color]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));}
});
document.addEventListener('pointermove',function(event){const root=event.target.closest('.bl-login');if(!root||root.dataset.paused==='true'||matchMedia('(prefers-reduced-motion: reduce)').matches)return;const rect=root.getBoundingClientRect();root.style.setProperty('--mx',(event.clientX-rect.left-rect.width/2)/65+'px');root.style.setProperty('--my',(event.clientY-rect.top-rect.height/2)/65+'px');});
`;
html = html.replace('</body>','<script id="baylab-login-events">'+events+'</script></body>');
fs.writeFileSync('index.html',html);
fs.mkdirSync('frontend/public',{recursive:true});
fs.writeFileSync('frontend/public/demo.html',html);
console.log('Synchronized animated login in index.html and demo.html');
