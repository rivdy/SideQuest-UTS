-- BAYLab cloud workspace v2. Run AFTER 202611040001_organization_auth.sql.
-- Preserves imported records. No service-role key, public writes, or new accounts.
begin;

create table if not exists public.baylab_audit_events (
  id uuid primary key default gen_random_uuid(),
  organization_slug text not null references public.baylab_organizations(slug),
  actor uuid not null references auth.users(id),
  action text not null,
  record_id uuid not null references public.baylab_records(id),
  created_at timestamptz not null default now()
);
alter table public.baylab_audit_events enable row level security;
revoke all on public.baylab_audit_events from public, anon, authenticated;
grant select on public.baylab_audit_events to authenticated;
drop policy if exists baylab_audit_read on public.baylab_audit_events;
create policy baylab_audit_read on public.baylab_audit_events for select to authenticated
  using (baylab_private.has_membership(organization_slug, 'admin'));
-- Keep raw table writes closed, including changes to org, creator, archived or model runs.
revoke insert, update, delete, truncate, references, trigger
  on public.baylab_records from public, anon, authenticated;

create or replace function baylab_private.check_object(v jsonb, allowed text[], required text[])
returns void language plpgsql immutable set search_path = '' as $$
begin
  if v is null or jsonb_typeof(v) <> 'object' then
    raise exception using errcode='22023', message='Payload harus berupa objek.';
  end if;
  if exists(select 1 from jsonb_object_keys(v) k where not(k=any(allowed)))
     or not(v ?& required) then
    raise exception using errcode='22023', message='Field payload tidak sesuai atau belum lengkap.';
  end if;
end;
$$;
create or replace function baylab_private.text_field(v jsonb, k text, lo int, hi int, fallback text default null)
returns text language plpgsql immutable set search_path = '' as $$
declare result text;
begin
  if not(v ? k) and fallback is not null then return fallback; end if;
  if jsonb_typeof(v->k) is distinct from 'string' then
    raise exception using errcode='22023', message='Isian '||k||' harus berupa teks.';
  end if;
  result := btrim(v->>k);
  if length(result)<lo or length(result)>hi then
    raise exception using errcode='22023', message='Panjang isian '||k||' tidak sesuai.';
  end if;
  return result;
end;
$$;
create or replace function baylab_private.number_field(v jsonb, k text, lo numeric, hi numeric)
returns numeric language plpgsql immutable set search_path = '' as $$
declare result numeric;
begin
  if jsonb_typeof(v->k) is distinct from 'number' then
    raise exception using errcode='22023', message='Isian '||k||' harus berupa angka.';
  end if;
  result := (v->>k)::numeric;
  if result < lo or result > hi then
    raise exception using errcode='22023', message='Nilai '||k||' di luar rentang.';
  end if;
  return result;
end;
$$;
create or replace function baylab_private.assessment(v jsonb)
returns jsonb language plpgsql immutable set search_path = '' as $$
declare result jsonb; k text; criterion jsonb;
begin
  perform baylab_private.check_object(v,
    array['comparison_protocol','oxidation','solubility','compatibility','temperature','aroma'],
    array['comparison_protocol']);
  result := jsonb_build_object('comparison_protocol',baylab_private.text_field(v,'comparison_protocol',3,120));
  foreach k in array array['oxidation','solubility','compatibility','temperature','aroma'] loop
    criterion := v->k;
    if criterion is null or criterion='null'::jsonb then
      result := result || jsonb_build_object(k,null);
    else
      perform baylab_private.check_object(criterion,array['score','source_ref','rationale'],array['score','source_ref','rationale']);
      result := result || jsonb_build_object(k,jsonb_build_object(
        'score',baylab_private.number_field(criterion,'score',0,100),
        'source_ref',baylab_private.text_field(criterion,'source_ref',3,240),
        'rationale',baylab_private.text_field(criterion,'rationale',3,800)));
    end if;
  end loop;
  return result;
end;
$$;

-- This is the sole write entrypoint. Auth UID and active membership are checked
-- inside PostgreSQL even when the RPC is called directly, bypassing Next.js.
create or replace function public.baylab_workspace_action(
  p_organization text, p_action text, p_payload jsonb default '{}'::jsonb,
  p_record_id uuid default null
) returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  actor uuid := auth.uid(); member_role text; row_data public.baylab_records;
  result jsonb; normalized jsonb; item jsonb; ingredients jsonb := '[]'::jsonb;
  criterion jsonb; weights jsonb; contributions jsonb; missing jsonb;
  ranked jsonb := '[]'::jsonb; incomplete jsonb := '[]'::jsonb;
  k text; ingredient_role text; origin text; first_origin text; protocol text;
  batch text; measured text; formula_id uuid; candidate_id uuid; new_id uuid;
  quantity numeric; total numeric := 0; initial_value numeric; final_value numeric;
  duration numeric; weight numeric; score numeric; canonical jsonb;
  selected_ids uuid[] := '{}'::uuid[]; required_keys text[];
begin
  if actor is null then
    raise exception using errcode='42501', message='Silakan masuk dengan akun organisasi.';
  end if;
  select m.role into member_role from public.baylab_memberships m
    where m.organization_slug=p_organization and m.user_id=actor and m.active for share;
  if member_role is null then
    raise exception using errcode='42501', message='Keanggotaan organisasi tidak aktif.';
  end if;
  if p_action is null or p_action not in ('create_formulation','assess_formulation','create_experiment','archive_experiment','rank') then
    raise exception using errcode='22023', message='Operasi workspace tidak dikenal.';
  end if;
  if p_action <> 'rank' and member_role not in ('admin','formulator') then
    raise exception using errcode='42501', message='Akun pembaca tidak dapat mengubah data.';
  end if;
  if p_payload is null or octet_length(p_payload::text)>32768 then
    raise exception using errcode='22023', message='Payload kosong atau terlalu besar.';
  end if;

  if p_action='create_formulation' then
    perform baylab_private.check_object(p_payload,array['name','aroma_profile','ingredients','notes','data_origin'],array['name','ingredients']);
    origin := baylab_private.text_field(p_payload,'data_origin',4,9,'real');
    if origin not in ('real','synthetic') then
      raise exception using errcode='22023', message='Asal data tidak valid.';
    end if;
    if jsonb_typeof(p_payload->'ingredients') is distinct from 'array' then
      raise exception using errcode='22023', message='Komposisi harus berupa daftar bahan.';
    end if;
    if jsonb_array_length(p_payload->'ingredients') not between 1 and 30 then
      raise exception using errcode='22023', message='Komposisi memerlukan 1 sampai 30 bahan.';
    end if;
    for item in select value from jsonb_array_elements(p_payload->'ingredients') loop
      perform baylab_private.check_object(item,array['name','role','percent','smiles'],array['name','role','percent']);
      ingredient_role := baylab_private.text_field(item,'role',1,20);
      if ingredient_role not in ('active','fragrance','solubilizer','stabilizer','solvent','water','other') then
        raise exception using errcode='22023', message='Peran bahan tidak dikenal.';
      end if;
      quantity := baylab_private.number_field(item,'percent',0,100);
      if quantity <= 0 then raise exception using errcode='22023', message='Persentase bahan harus lebih dari nol.'; end if;
      total := total+quantity;
      ingredients := ingredients || jsonb_build_array(jsonb_build_object(
        'name',baylab_private.text_field(item,'name',1,120),'role',ingredient_role,'percent',quantity,
        'smiles',baylab_private.text_field(item,'smiles',0,2000,'')));
    end loop;
    if abs(total-100)>0.01 then raise exception using errcode='22023', message='Total komposisi wajib 100% massa.'; end if;
    select jsonb_agg(entry order by entry::text) into canonical from (
      select jsonb_build_array(lower(value->>'name'),value->>'role',round((value->>'percent')::numeric,6),value->>'smiles') entry
      from jsonb_array_elements(ingredients)
    ) sorted_ingredients;
    normalized := jsonb_build_object('name',baylab_private.text_field(p_payload,'name',2,120),
      'aroma_profile',baylab_private.text_field(p_payload,'aroma_profile',0,240,''),
      'notes',baylab_private.text_field(p_payload,'notes',0,1500,''),'ingredients',ingredients,
      'data_origin',origin,'assessment',null,
      'composition_hash',encode(sha256(convert_to(canonical::text,'UTF8')),'hex'));
    insert into public.baylab_records(organization_slug,kind,data,created_by)
      values(p_organization,'formulation',normalized,actor) returning * into row_data;

  elsif p_action='assess_formulation' then
    normalized := baylab_private.assessment(p_payload);
    select * into row_data from public.baylab_records r where r.id=p_record_id
      and r.organization_slug=p_organization and r.kind='formulation' and not r.archived for update;
    if not found then raise exception using errcode='P0002', message='Formulasi tidak ditemukan dalam organisasi ini.'; end if;
    update public.baylab_records set data=data || jsonb_build_object('assessment',normalized,'assessed_at',extract(epoch from now()))
      where id=row_data.id returning * into row_data;

  elsif p_action='create_experiment' then
    required_keys := array['formulation_id','batch_id','protocol','source_ref','measured_on','initial_h2o2','final_h2o2','ph','temperature_c','duration_days','homogeneous','data_origin'];
    perform baylab_private.check_object(p_payload,required_keys || array['aroma_intensity','notes','confirmed_actual'],required_keys);
    formula_id := baylab_private.text_field(p_payload,'formulation_id',36,36)::uuid;
    -- Serializes duplicate checks for the same formulation without a global lock.
    select * into row_data from public.baylab_records r where r.id=formula_id
      and r.organization_slug=p_organization and r.kind='formulation' and not r.archived for update;
    if not found then raise exception using errcode='P0002', message='Formulasi tidak ditemukan dalam organisasi ini.'; end if;
    origin := baylab_private.text_field(p_payload,'data_origin',4,9);
    if origin not in ('real','synthetic') then raise exception using errcode='22023', message='Asal data tidak valid.'; end if;
    if p_payload ? 'confirmed_actual' and jsonb_typeof(p_payload->'confirmed_actual') <> 'boolean' then
      raise exception using errcode='22023', message='Konfirmasi data harus berupa boolean.';
    end if;
    if origin='real' and coalesce(p_payload->'confirmed_actual','false'::jsonb)<>'true'::jsonb then
      raise exception using errcode='22023', message='Konfirmasikan bahwa nilai berasal dari pengukuran lab nyata.';
    end if;
    if origin='real' and row_data.data->>'data_origin'='synthetic' then
      raise exception using errcode='22023', message='Formulasi ilustrasi tidak dapat menghasilkan catatan lab nyata.';
    end if;
    if jsonb_typeof(p_payload->'homogeneous') is distinct from 'boolean' then
      raise exception using errcode='22023', message='Homogenitas harus berupa boolean.';
    end if;
    initial_value := baylab_private.number_field(p_payload,'initial_h2o2',0,100);
    if initial_value<=0 then raise exception using errcode='22023', message='Kadar awal harus lebih dari nol.'; end if;
    final_value := baylab_private.number_field(p_payload,'final_h2o2',0,100);
    duration := baylab_private.number_field(p_payload,'duration_days',0,3650);
    if duration<=0 then raise exception using errcode='22023', message='Durasi harus lebih dari nol.'; end if;
    measured := baylab_private.text_field(p_payload,'measured_on',10,10);
    if measured !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' or to_char(measured::date,'YYYY-MM-DD')<>measured then
      raise exception using errcode='22023', message='Tanggal pengukuran tidak valid.';
    end if;
    batch := baylab_private.text_field(p_payload,'batch_id',2,100);
    protocol := baylab_private.text_field(p_payload,'protocol',3,120);
    if exists(select 1 from public.baylab_records r where r.organization_slug=p_organization
      and r.kind='experiment' and not r.archived and r.data->>'formulation_id'=formula_id::text
      and r.data->>'batch_id'=batch and r.data->>'protocol'=protocol
      and (r.data->>'duration_days')::numeric=duration) then
      raise exception using errcode='23505', message='Pengukuran batch/protokol/hari ini sudah tercatat.';
    end if;
    select jsonb_build_object(
      'fragrance',coalesce(sum((value->>'percent')::numeric) filter(where value->>'role'='fragrance'),0),
      'solubilizer',coalesce(sum((value->>'percent')::numeric) filter(where value->>'role'='solubilizer'),0),
      'stabilizer',coalesce(sum((value->>'percent')::numeric) filter(where value->>'role'='stabilizer'),0)
    ) into canonical from jsonb_array_elements(row_data.data->'ingredients');
    quantity := null;
    if p_payload ? 'aroma_intensity' and p_payload->'aroma_intensity'<>'null'::jsonb then
      quantity := baylab_private.number_field(p_payload,'aroma_intensity',0,5);
    end if;
    normalized := jsonb_build_object('formulation_id',formula_id,'batch_id',batch,'protocol',protocol,
      'source_ref',baylab_private.text_field(p_payload,'source_ref',3,240),'measured_on',measured,
      'initial_h2o2',initial_value,'final_h2o2',final_value,
      'ph',baylab_private.number_field(p_payload,'ph',0,14),
      'temperature_c',baylab_private.number_field(p_payload,'temperature_c',-20,100),
      'duration_days',duration,'homogeneous',p_payload->'homogeneous','aroma_intensity',quantity,
      'notes',baylab_private.text_field(p_payload,'notes',0,1500,''),'data_origin',origin,
      'confirmed_actual',coalesce(p_payload->'confirmed_actual','false'::jsonb),
      'formulation_name',row_data.data->>'name','composition_hash',row_data.data->>'composition_hash',
      'composition_features',canonical,'retention_pct',round(final_value/initial_value*100,6));
    insert into public.baylab_records(organization_slug,kind,data,created_by)
      values(p_organization,'experiment',normalized,actor) returning * into row_data;

  elsif p_action='archive_experiment' then
    perform baylab_private.check_object(p_payload,'{}'::text[],'{}'::text[]);
    update public.baylab_records set archived=true where id=p_record_id
      and organization_slug=p_organization and kind='experiment' and not archived returning * into row_data;
    if not found then raise exception using errcode='P0002', message='Eksperimen tidak ditemukan dalam organisasi ini.'; end if;

  elsif p_action='rank' then
    perform baylab_private.check_object(p_payload,array['formulation_ids','weights','comparison_protocol'],array['formulation_ids','comparison_protocol']);
    protocol := baylab_private.text_field(p_payload,'comparison_protocol',3,120);
    weights := coalesce(p_payload->'weights','{"oxidation":25,"solubility":25,"compatibility":20,"temperature":20,"aroma":10}'::jsonb);
    required_keys := array['oxidation','solubility','compatibility','temperature','aroma'];
    perform baylab_private.check_object(weights,required_keys,required_keys);
    foreach k in array required_keys loop total := total+baylab_private.number_field(weights,k,0,100); end loop;
    if abs(total-100)>0.001 then raise exception using errcode='22023', message='Total bobot wajib 100%.'; end if;
    if jsonb_typeof(p_payload->'formulation_ids') is distinct from 'array' then
      raise exception using errcode='22023', message='Kandidat harus berupa daftar ID.';
    end if;
    if jsonb_array_length(p_payload->'formulation_ids') not between 2 and 50 then
      raise exception using errcode='22023', message='Pilih 2 sampai 50 kandidat.';
    end if;
    for item in select value from jsonb_array_elements(p_payload->'formulation_ids') loop
      if jsonb_typeof(item)<>'string' then raise exception using errcode='22023', message='ID kandidat tidak valid.'; end if;
      candidate_id := (item #>> '{}')::uuid;
      if candidate_id=any(selected_ids) then raise exception using errcode='22023', message='Kandidat tidak boleh duplikat.'; end if;
      selected_ids := array_append(selected_ids,candidate_id);
      select * into row_data from public.baylab_records r where r.id=candidate_id
        and r.organization_slug=p_organization and r.kind='formulation' and not r.archived for share;
      if not found then raise exception using errcode='P0002', message='Kandidat tidak ditemukan dalam organisasi ini.'; end if;
      origin := row_data.data->>'data_origin';
      if first_origin is not null and origin is distinct from first_origin then
        raise exception using errcode='22023', message='Bandingkan kandidat nyata dan kandidat ilustrasi secara terpisah.';
      end if;
      first_origin := origin;
      normalized := row_data.data->'assessment';
      if normalized is not null and normalized<>'null'::jsonb then normalized := baylab_private.assessment(normalized); end if;
      missing := '[]'::jsonb; contributions := '{}'::jsonb; score := 0;
      foreach k in array required_keys loop
        weight := (weights->>k)::numeric; criterion := normalized->k;
        if weight>0 and (criterion is null or criterion='null'::jsonb) then
          missing := missing || jsonb_build_array(k);
        elsif weight>0 then
          quantity := (criterion->>'score')::numeric*weight/100;
          contributions := contributions || jsonb_build_object(k,quantity); score := score+quantity;
        end if;
      end loop;
      if normalized->>'comparison_protocol' is distinct from protocol then missing := missing || '["comparison_protocol"]'::jsonb; end if;
      result := jsonb_build_object('id',row_data.id,'name',row_data.data->>'name','data_origin',origin);
      if jsonb_array_length(missing)>0 then
        incomplete := incomplete || jsonb_build_array(result || jsonb_build_object('missing',missing));
      else
        ranked := ranked || jsonb_build_array(result || jsonb_build_object('score',round(score,6),'contributions',contributions,'evidence',normalized));
      end if;
    end loop;
    select coalesce(jsonb_agg(value || jsonb_build_object('rank',position) order by (value->>'score')::numeric desc,value->>'id'),'[]'::jsonb)
      into ranked from (select value,rank() over(order by (value->>'score')::numeric desc) position from jsonb_array_elements(ranked)) ranked_rows;
    return jsonb_build_object('ranked',ranked,'incomplete',incomplete,'weights',weights,'protocol',protocol,
      'method','Weighted sum v1: sum(score_0_100 * weight_percent / 100)',
      'scope','Prioritas dari bukti tim; bukan sertifikasi keamanan atau efikasi.');
  end if;

  insert into public.baylab_audit_events(organization_slug,actor,action,record_id)
    values(p_organization,actor,p_action,row_data.id);
  if p_action in ('assess_formulation','archive_experiment') then return jsonb_build_object('ok',true); end if;
  return row_data.data || jsonb_build_object('id',row_data.id,'created',extract(epoch from row_data.created_at));
end;
$$;

create or replace function public.baylab_workspace_capabilities(p_organization text)
returns jsonb language plpgsql security invoker set search_path = '' as $$
begin
  if not baylab_private.has_membership(p_organization) then
    raise exception using errcode='42501', message='Keanggotaan organisasi tidak aktif.';
  end if;
  return jsonb_build_object('schema_version',2,'workspace_ready',true,'formulations',true,
    'experiments',true,'ranking',true,'rag',false,'chemistry',false,'training',false);
end;
$$;
revoke all on function baylab_private.check_object(jsonb,text[],text[]) from public,anon,authenticated;
revoke all on function baylab_private.text_field(jsonb,text,int,int,text) from public,anon,authenticated;
revoke all on function baylab_private.number_field(jsonb,text,numeric,numeric) from public,anon,authenticated;
revoke all on function baylab_private.assessment(jsonb) from public,anon,authenticated;
revoke all on function public.baylab_workspace_action(text,text,jsonb,uuid) from public,anon,authenticated;
revoke all on function public.baylab_workspace_capabilities(text) from public,anon,authenticated;
grant execute on function public.baylab_workspace_action(text,text,jsonb,uuid) to authenticated;
grant execute on function public.baylab_workspace_capabilities(text) to authenticated;
notify pgrst, 'reload schema';
commit;
