-- Run in Supabase SQL Editor as the project administrator.
-- Initial migration: accounts are created separately in Authentication > Users.
-- The browser may read authorized data; all membership/record writes remain closed.
begin;
create schema if not exists baylab_private;
revoke all on schema baylab_private from public;
grant usage on schema baylab_private to authenticated;

create table if not exists public.baylab_organizations (
  slug text primary key check (slug ~ '^[a-z0-9][a-z0-9-]{1,39}$'),
  name text not null check (length(name) between 2 and 160),
  created_at timestamptz not null default now()
);
create table if not exists public.baylab_memberships (
  organization_slug text not null references public.baylab_organizations(slug),
  user_id uuid not null references auth.users(id) on delete cascade,
  display_name text not null check (length(display_name) between 2 and 120),
  role text not null check (role in ('admin','formulator','viewer')),
  active boolean not null default true,
  primary key (organization_slug, user_id)
);
create index if not exists baylab_memberships_user on public.baylab_memberships(user_id);
create table if not exists public.baylab_records (
  id uuid primary key default gen_random_uuid(),
  organization_slug text not null references public.baylab_organizations(slug),
  kind text not null check (kind in ('formulation','experiment','model_run')),
  data jsonb not null check (jsonb_typeof(data) = 'object'),
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  archived boolean not null default false
);
create index if not exists baylab_records_org on public.baylab_records(organization_slug, kind);

-- Fixed search_path and no user-id parameter prevent spoofed membership checks.
-- SECURITY DEFINER avoids a recursive RLS lookup on memberships.
create or replace function baylab_private.has_membership(org text, required_role text default null)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists(select 1 from public.baylab_memberships m
    where m.organization_slug = org and m.user_id = (select auth.uid())
      and m.active and (required_role is null or m.role = required_role));
$$;
revoke all on function baylab_private.has_membership(text,text) from public;
grant execute on function baylab_private.has_membership(text,text) to authenticated;

alter table public.baylab_organizations enable row level security;
alter table public.baylab_memberships enable row level security;
alter table public.baylab_records enable row level security;
revoke all on public.baylab_organizations, public.baylab_memberships, public.baylab_records from anon, authenticated;
grant select on public.baylab_organizations, public.baylab_memberships, public.baylab_records to authenticated;

drop policy if exists baylab_org_read on public.baylab_organizations;
create policy baylab_org_read on public.baylab_organizations for select to authenticated
  using (baylab_private.has_membership(slug));
drop policy if exists baylab_members_read on public.baylab_memberships;
create policy baylab_members_read on public.baylab_memberships for select to authenticated
  using (user_id = (select auth.uid()) or baylab_private.has_membership(organization_slug, 'admin'));
drop policy if exists baylab_records_read on public.baylab_records;
create policy baylab_records_read on public.baylab_records for select to authenticated
  using (baylab_private.has_membership(organization_slug));

insert into public.baylab_organizations(slug, name)
values ('lkpi','PT Likuid Pharmalab Indonesia') on conflict (slug) do nothing;
commit;
