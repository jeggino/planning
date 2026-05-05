drop table if exists rounds cascade;
drop table if exists assignments cascade;
drop table if exists areas cascade;

create table assignments (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  type text not null check (type in ('Deskwork', 'Fieldwork')),
  hours_per_round numeric, -- only for Fieldwork
  min_days_between_rounds int, -- only for Fieldwork
  hourly_rate numeric not null,
  created_at timestamp default now()
);

create table areas (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  description text,
  created_at timestamp default now()
);

create table rounds (
  id uuid primary key default gen_random_uuid(),
  assignment_id uuid references assignments(id) on delete cascade,
  area_id uuid references areas(id) on delete set null,
  work_date date not null,
  hours_worked numeric, -- used for Deskwork; null for Fieldwork
  created_at timestamp default now()
);




