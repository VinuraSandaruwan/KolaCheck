-- KolaCheck scan storage schema. Apply in the Supabase SQL editor.
create table if not exists public.scans (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  label text not null,
  confidence real not null,
  society_id text not null default 'demo',
  device_id text not null default 'anon',
  model_version text,
  lat double precision,
  lon double precision,
  is_demo boolean not null default false
);

alter table public.scans add column if not exists model_version text;

do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'scans_label_allowed') then
    alter table public.scans add constraint scans_label_allowed
      check (label in ('algal_leaf_spot', 'black_blight', 'blister_blight', 'gray_blight', 'healthy', 'spider_mite'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'scans_confidence_range') then
    alter table public.scans add constraint scans_confidence_range
      check (confidence >= 0 and confidence <= 1);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'scans_coordinates_pair') then
    alter table public.scans add constraint scans_coordinates_pair
      check ((lat is null) = (lon is null));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'scans_latitude_range') then
    alter table public.scans add constraint scans_latitude_range
      check (lat is null or lat between -90 and 90);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'scans_longitude_range') then
    alter table public.scans add constraint scans_longitude_range
      check (lon is null or lon between -180 and 180);
  end if;
end $$;

create index if not exists scans_society_created_idx
  on public.scans (society_id, created_at desc, id);
create index if not exists scans_society_label_idx
  on public.scans (society_id, label);

alter table public.scans enable row level security;

-- The API uses a server-only Supabase service key, which bypasses RLS.
-- This project has no user authentication yet, so keep it local/demo only.
