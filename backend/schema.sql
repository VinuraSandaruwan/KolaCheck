create table if not exists scans (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  label text not null,
  confidence real not null,
  society_id text not null default 'demo',
  device_id text not null default 'anon',
  lat double precision,
  lon double precision,
  is_demo boolean not null default false
);
alter table scans enable row level security;  -- backend uses the service key
