// Isolated HTTP contract tests. Mock Auth/PostgREST; never creates real cloud users.
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdirSync, writeFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import path from 'node:path';
const root=process.cwd(), report=[];
const uid='11111111-1111-4111-8111-111111111111';
let role='admin', missingSchema=false, revoked=false;
const token=()=>[Buffer.from(JSON.stringify({alg:'HS256',typ:'JWT'})).toString('base64url'),Buffer.from(JSON.stringify({sub:uid,exp:Math.floor(Date.now()/1000)+3600,iat:Math.floor(Date.now()/1000),aud:'authenticated',role:'authenticated'})).toString('base64url'),'mock-signature'].join('.');
const user={id:uid,aud:'authenticated',role:'authenticated',email:'admin@example.test',email_confirmed_at:new Date().toISOString(),app_metadata:{provider:'email'},user_metadata:{},created_at:new Date().toISOString()};
const mock=createServer(async(req,res)=>{
 const url=new URL(req.url,'http://mock'); let body='';for await(const chunk of req)body+=chunk;
 const json=(data,status=200)=>{res.writeHead(status,{'content-type':'application/json'});res.end(JSON.stringify(data));};
 if(url.pathname==='/auth/v1/token'){
  const input=JSON.parse(body||'{}');
  if(input.password==='rate-limited')return json({code:'over_request_rate_limit',msg:'Rate limited'},429);
  if(input.password!=='Valid-Test-Password-123')return json({code:'invalid_credentials',msg:'Invalid login'},400);
  return json({access_token:token(),token_type:'bearer',expires_in:3600,refresh_token:'mock-refresh',user});
 }
 if(url.pathname==='/auth/v1/user')return revoked?json({code:'bad_jwt',msg:'Revoked'},401):json(user);
 if(url.pathname==='/auth/v1/logout'){res.writeHead(204);return res.end();}
 if(url.pathname==='/rest/v1/baylab_memberships'){
  if(missingSchema)return json({code:'PGRST205',message:'Missing table'},404);
  if(url.searchParams.get('select').includes('user')||url.searchParams.has('user_id')){
   if(url.searchParams.get('organization_slug')!=='eq.lkpi')return json(null);
   return json({organization_slug:'lkpi',role,display_name:'QA Admin',active:true,baylab_organizations:{name:'QA LKPI'}});
  }
  return json([{display_name:'QA Admin',role,active:true}]);
 }
 if(url.pathname==='/rest/v1/baylab_records')return json([]);
 return json({message:'Unknown mock route'},404);
});
mock.listen(0,'127.0.0.1');await once(mock,'listening');
const mockUrl='http://127.0.0.1:'+mock.address().port;
const port=3012,base='http://127.0.0.1:'+port;
const child=spawn(process.execPath,[path.join(root,'frontend/node_modules/next/dist/bin/next'),'start','-H','127.0.0.1','-p',String(port)],{cwd:path.join(root,'frontend'),windowsHide:true,env:{...process.env,BAYLAB_AUTH_PROVIDER:'supabase',SUPABASE_URL:mockUrl,SUPABASE_PUBLISHABLE_KEY:'sb_publishable_mock',BAYLAB_SECURE_COOKIES:'false'},stdio:['ignore','pipe','pipe']});
let output='';child.stdout.on('data',d=>output+=d);child.stderr.on('data',d=>output+=d);
const jar=new Map();let csrf='';
async function request(route,body,extra={}){
 const response=await fetch(base+'/api/'+route,{method:body?'POST':'GET',headers:{...body?{'content-type':'application/json','origin':base}:{},cookie:[...jar].map(([k,v])=>k+'='+v).join('; '),...extra},...body?{body:JSON.stringify(body)}:{}});
 for(const cookie of response.headers.getSetCookie()) {const pair=cookie.split(';')[0]; const idx=pair.indexOf('=');if(pair.slice(idx+1))jar.set(pair.slice(0,idx),pair.slice(idx+1));else jar.delete(pair.slice(0,idx));}
 return response;
}
const login=(organization='lkpi',password='Valid-Test-Password-123')=>request('auth/login',{organization,email:user.email,password});
function check(name,fn){fn();report.push({name,ok:true});}
try{
 let ready=false;for(let i=0;i<80;i++){try{if((await fetch(base+'/api/auth/config')).ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,200));}
 assert.ok(ready,'Next startup failed: '+output.slice(-1500));
 let r=await request('auth/config');check('cloud mode selected',()=>assert.equal(r.status,200));
 r=await request('workspace/overview');check('anonymous workspace denied',()=>assert.equal(r.status,401));
 r=await request('auth/login',{organization:'lkpi',email:user.email,password:'Valid-Test-Password-123',role:'admin'});check('extra authorization field rejected',()=>assert.equal(r.status,422));
 r=await login('lkpi','incorrect');check('incorrect password denied',()=>assert.equal(r.status,401));
 r=await login('lkpi','rate-limited');check('Auth rate limit propagated',()=>assert.equal(r.status,429));
 r=await login('other-org');check('nonmember organization denied',()=>assert.equal(r.status,403));
 r=await request('auth/session');check('failed membership clears login',()=>assert.equal(r.status,401));
 missingSchema=true;r=await login();check('missing SQL setup explained',()=>assert.equal(r.status,503));missingSchema=false;
 r=await login();const result=await r.json();csrf=result.csrf_token;
 check('valid member signs in',()=>{assert.equal(r.status,200);assert.equal(result.user.organization.slug,'lkpi');assert.equal(result.user.role,'admin');assert.ok(csrf);assert.equal(result.access_token,undefined);});
 check('auth cookies HttpOnly SameSite Strict',()=>{const all=r.headers.getSetCookie();assert.ok(all.length>=3);assert.ok(all.every(x=>/httponly/i.test(x)&&/samesite=strict/i.test(x)));});
 r=await request('auth/session');check('authenticated response never cached',()=>{assert.equal(r.status,200);assert.match(r.headers.get('cache-control'),/no-store/);});
 r=await request('workspace/overview');check('cloud overview reads actual empty records',()=>{assert.equal(r.status,200);});
 r=await request('auth/logout',{});check('missing CSRF denied',()=>assert.equal(r.status,403));
 r=await request('auth/logout',{}, {'x-csrf-token':csrf,origin:'https://evil.example'});check('cross-origin mutation denied',()=>assert.equal(r.status,403));
 r=await request('workspace/formulations',{name:'fake'},{'x-csrf-token':csrf});check('unimplemented cloud writes explicitly blocked',()=>assert.equal(r.status,503));
 r=await request('rag/status');check('local-only AI explicitly unavailable',()=>assert.equal(r.status,503));
 role='viewer';r=await request('auth/users');check('current membership role rechecked',()=>assert.equal(r.status,403));role='admin';
 revoked=true;r=await request('workspace/overview');check('revoked identity denied',()=>assert.equal(r.status,401));revoked=false;
 r=await login();csrf=(await r.json()).csrf_token;
 r=await request('auth/logout',{}, {'x-csrf-token':csrf});check('valid logout',()=>assert.equal(r.status,200));
 r=await request('auth/session');check('logout removes session',()=>assert.equal(r.status,401));
 mkdirSync(path.join(root,'qa'),{recursive:true});writeFileSync(path.join(root,'qa/supabase-contract-report.json'),JSON.stringify({scope:'mock Supabase HTTP; not a live SQL/RLS verification',report},null,2));
 console.log(JSON.stringify({passed:report.length,scope:'isolated HTTP contracts'}));
}finally{child.kill();await once(child,'exit').catch(()=>{});mock.closeAllConnections();await new Promise(resolve=>mock.close(resolve));}
