-- First create your own account in Supabase Authentication > Users > Add user.
-- Replace the UUID below with its User UID, then run this in SQL Editor.
-- Never run this file with the placeholder unchanged. No password belongs here.
begin;
insert into public.baylab_memberships(organization_slug, user_id, display_name, role)
values ('lkpi', '5de818a7-25c5-45fd-b8e7-f4b1b84c46f0'::uuid, 'Administrator BAYLab', 'admin');
commit;
