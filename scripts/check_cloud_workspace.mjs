// Executes real PostgreSQL functions/RLS in an isolated PGlite database.
// Fixtures are synthetic; no cloud credentials or production requests are used.
import { PGlite } from '../frontend/node_modules/@electric-sql/pglite/dist/index.js';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import assert from 'node:assert/strict';
const db=new PGlite();
const uid={admin:'11111111-1111-4111-8111-111111111111',editor:'22222222-2222-4222-8222-222222222222',viewer:'33333333-3333-4333-8333-333333333333',other:'44444444-4444-4444-8444-444444444444'};
const migration=readFileSync('supabase/migrations/202611040002_cloud_workspace.sql','utf8');
const report=[];
async function check(name,fn){await fn();report.push({name,ok:true});}
async function session(user,fn,role='authenticated'){
 return db.transaction(async tx=>{await tx.exec('set local role '+role);await tx.query("select set_config('request.jwt.claim.sub',$1,true)",[user||'']);return fn(tx);});
}
async function rpc(user,action,payload={},id=null,org='lkpi'){
 return session(user,async tx=>(await tx.query('select public.baylab_workspace_action($1,$2,$3::jsonb,$4::uuid) as result',[org,action,JSON.stringify(payload),id])).rows[0].result);
}
async function reject(code,fn){await assert.rejects(fn,e=>e.code===code);}
const form=(name='Candidate',origin='synthetic')=>({name,data_origin:origin,ingredients:[{name:'Water',role:'water',percent:95},{name:'Fragrance',role:'fragrance',percent:5}]});
const criterion=score=>({score,source_ref:'QA synthetic reference',rationale:'Fixture score, not lab evidence'});
const assess=(oxidation,solubility=oxidation)=>({comparison_protocol:'QA-01',oxidation:criterion(oxidation),solubility:criterion(solubility),compatibility:criterion(50),temperature:criterion(50),aroma:criterion(50)});
const trial=id=>({formulation_id:id,batch_id:'QA-B1',protocol:'QA-P1',source_ref:'QA synthetic observation',measured_on:'2026-11-04',initial_h2o2:3,final_h2o2:2.7,ph:4,temperature_c:25,duration_days:7,homogeneous:true,data_origin:'synthetic',confirmed_actual:false});
try{
 await db.exec(`create role anon; create role authenticated; create schema auth;
 create table auth.users(id uuid primary key,email text,confirmed_at timestamptz);
 create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
 grant usage on schema auth to authenticated,anon;`);
 await db.exec(readFileSync('supabase/migrations/202611040001_organization_auth.sql','utf8'));
 for(const [key,id] of Object.entries(uid))await db.query('insert into auth.users values($1,$2,now())',[id,key+'@example.test']);
 await db.exec("insert into public.baylab_organizations values ('other','Other organization',now())");
 for(const [key,id] of Object.entries(uid))await db.query('insert into public.baylab_memberships values ($1,$2,$3,$4,true)',[key==='other'?'other':'lkpi',id,'QA '+key,key==='editor'?'formulator':key==='other'?'admin':key]);
 await db.query("insert into public.baylab_records(organization_slug,kind,data,created_by) values('lkpi','model_run',$1::jsonb,$2)",[JSON.stringify({algorithm:'catboost',scope:'Imported fixture'}),uid.admin]);
 await check('migration applies and can be repeated without erasing imports',async()=>{await db.exec(migration);await db.exec(migration);assert.equal((await db.query("select count(*)::int n from public.baylab_records where kind='model_run'")).rows[0].n,1);});
 await check('anonymous RPC denied',()=>reject('42501',()=>session(null,tx=>tx.query("select public.baylab_workspace_action('lkpi','create_formulation','{}')"),'anon')));
 await check('viewer writes denied even through direct RPC',()=>reject('42501',()=>rpc(uid.viewer,'create_formulation',form())));
 await check('foreign organization writes denied',()=>reject('42501',()=>rpc(uid.other,'create_formulation',form())));
 await check('raw table inserts denied',()=>reject('42501',()=>session(uid.admin,tx=>tx.query("insert into public.baylab_records(organization_slug,kind,data,created_by) values('lkpi','formulation','{}',$1)",[uid.admin]))));
 await check('private validation helper cannot be invoked directly',()=>reject('42501',()=>session(uid.admin,tx=>tx.query("select baylab_private.assessment('{}')"))));
 await check('capabilities reflect installed schema',async()=>{const r=await session(uid.viewer,tx=>tx.query("select public.baylab_workspace_capabilities('lkpi') c"));assert.equal(r.rows[0].c.workspace_ready,true);});
 await check('bad composition rejected',()=>reject('22023',()=>rpc(uid.editor,'create_formulation',{...form(),ingredients:[{name:'Water',role:'water',percent:99}]})));
 await check('unauthorized columns rejected',()=>reject('22023',()=>rpc(uid.admin,'create_formulation',{...form(),created_by:uid.other})));
 await check('nested ingredient tampering rejected',()=>reject('22023',()=>rpc(uid.admin,'create_formulation',{...form(),ingredients:[{name:'Water',role:'water',percent:100,secret_key:'tamper'}]})));
 let a,b,missing,real,other;
 await check('formulator creates normalized composition and server owner',async()=>{a=await rpc(uid.editor,'create_formulation',form("O'Brien <img src=x onerror=alert(1)>"));assert.equal(a.ingredients[0].smiles,'');assert.equal(a.composition_hash.length,64);const owner=await db.query('select created_by from public.baylab_records where id=$1',[a.id]);assert.equal(owner.rows[0].created_by,uid.editor);});
 b=await rpc(uid.admin,'create_formulation',form('Candidate B'));missing=await rpc(uid.admin,'create_formulation',form('No assessment'));real=await rpc(uid.admin,'create_formulation',form('Team candidate','real'));other=await rpc(uid.other,'create_formulation',form('Other candidate'),null,'other');
 await check('cross-organization RLS hides records',async()=>{const r=await session(uid.other,tx=>tx.query('select id from public.baylab_records'));assert.deepEqual(r.rows.map(x=>x.id),[other.id]);});
 await check('assessment requires references',()=>reject('22023',()=>rpc(uid.admin,'assess_formulation',{comparison_protocol:'QA-01',oxidation:{score:90}},a.id)));
 await check('assessment cannot target another organization',()=>reject('P0002',()=>rpc(uid.admin,'assess_formulation',assess(50),other.id)));
 await rpc(uid.editor,'assess_formulation',assess(90,10),a.id);await rpc(uid.admin,'assess_formulation',assess(10,90),b.id);
 const rankPayload={formulation_ids:[a.id,b.id],comparison_protocol:'QA-01',weights:{oxidation:100,solubility:0,compatibility:0,temperature:0,aroma:0}};
 await check('viewer can rank with traceable weighted contributions',async()=>{const r=await rpc(uid.viewer,'rank',rankPayload);assert.equal(r.ranked[0].id,a.id);assert.equal(r.ranked[0].score,90);assert.equal(r.ranked[0].contributions.oxidation,90);});
 await check('changing weights changes ranking',async()=>{const r=await rpc(uid.admin,'rank',{...rankPayload,weights:{...rankPayload.weights,oxidation:0,solubility:100}});assert.equal(r.ranked[0].id,b.id);});
 await check('missing assessment produces incomplete instead of zero',async()=>{const r=await rpc(uid.admin,'rank',{...rankPayload,formulation_ids:[a.id,missing.id]});assert.equal(r.ranked.length,1);assert.equal(r.incomplete[0].id,missing.id);});
 await check('mismatched protocol produces no ranks',async()=>{const r=await rpc(uid.admin,'rank',{...rankPayload,comparison_protocol:'OTHER'});assert.equal(r.ranked.length,0);assert.equal(r.incomplete.length,2);});
 await check('mixed real and synthetic ranking denied',()=>reject('22023',()=>rpc(uid.admin,'rank',{...rankPayload,formulation_ids:[a.id,real.id]})));
 await check('invalid weights rejected',()=>reject('22023',()=>rpc(uid.admin,'rank',{...rankPayload,weights:{...rankPayload.weights,oxidation:99}})));
 await check('duplicate candidates rejected',()=>reject('22023',()=>rpc(uid.admin,'rank',{...rankPayload,formulation_ids:[a.id,a.id]})));
 await check('foreign candidate cannot be ranked',()=>reject('P0002',()=>rpc(uid.admin,'rank',{...rankPayload,formulation_ids:[a.id,other.id]})));
 await check('ties use competition ranking',async()=>{await rpc(uid.admin,'assess_formulation',assess(90),b.id);const r=await rpc(uid.admin,'rank',rankPayload);assert.deepEqual(r.ranked.map(x=>x.rank),[1,1]);});
 await check('real trial requires explicit attestation',()=>reject('22023',()=>rpc(uid.editor,'create_experiment',{...trial(real.id),data_origin:'real'})));
 await check('synthetic formulation cannot produce real lab data',()=>reject('22023',()=>rpc(uid.editor,'create_experiment',{...trial(a.id),data_origin:'real',confirmed_actual:true})));
 await check('invalid date rejected',()=>reject('22008',()=>rpc(uid.editor,'create_experiment',{...trial(a.id),measured_on:'2026-02-30'})));
 await check('NaN/string inputs rejected',()=>reject('22023',()=>rpc(uid.editor,'create_experiment',{...trial(a.id),initial_h2o2:'NaN'})));
 await check('foreign experiment reference denied',()=>reject('P0002',()=>rpc(uid.admin,'create_experiment',trial(other.id))));
 let experiment;
 await check('retention and composition snapshot computed in database',async()=>{experiment=await rpc(uid.editor,'create_experiment',trial(a.id));assert.equal(experiment.retention_pct,90);assert.equal(experiment.composition_features.fragrance,5);assert.equal(experiment.composition_hash,a.composition_hash);});
 await check('duplicate batch/protocol/day rejected',()=>reject('23505',()=>rpc(uid.admin,'create_experiment',trial(a.id))));
 await check('client cannot override computed retention',()=>reject('22023',()=>rpc(uid.admin,'create_experiment',{...trial(a.id),batch_id:'OTHER',retention_pct:100})));
 await check('foreign archive denied',()=>reject('P0002',()=>rpc(uid.other,'archive_experiment',{},experiment.id,'other')));
 await check('archiving retains record and audit',async()=>{await rpc(uid.editor,'archive_experiment',{},experiment.id);const r=await db.query('select archived from public.baylab_records where id=$1',[experiment.id]);assert.equal(r.rows[0].archived,true);const audit=await db.query('select action from public.baylab_audit_events where record_id=$1 order by created_at',[experiment.id]);assert.deepEqual(audit.rows.map(x=>x.action),['create_experiment','archive_experiment']);});
 await check('viewer cannot read admin audit',async()=>{assert.equal((await session(uid.viewer,tx=>tx.query('select * from public.baylab_audit_events'))).rows.length,0);});
 await check('inactive membership immediately loses write access',async()=>{await db.query('update public.baylab_memberships set active=false where user_id=$1',[uid.editor]);await reject('42501',()=>rpc(uid.editor,'create_formulation',form()));});
 mkdirSync('qa',{recursive:true});writeFileSync('qa/cloud-workspace-sql-report.json',JSON.stringify({engine:'PGlite PostgreSQL; synthetic fixtures',report},null,2));
 console.log(JSON.stringify({passed:report.length,engine:'real PostgreSQL functions and RLS via PGlite'}));
}catch(error){console.error(JSON.stringify({failedAfter:report.length,message:error.message,code:error.code,where:error.where,stack:error.stack?.split('\n').slice(0,4)}));process.exitCode=1;}
finally{await db.close();}
