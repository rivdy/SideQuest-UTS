-- First create your own account in Supabase Authentication > Users > Add user.
-- Replace the UUID below with its User UID, then run this in SQL Editor.
-- Never run this file with the placeholder unchanged. No password belongs here.
begin;
insert into public.baylab_memberships(organization_slug, user_id, display_name, role)
values ('lkpi', 'b31c40b7-4edc-4905-a161-5d51187006f1'::uuid, 'Administrator BAYLab', 'admin');
commit;
