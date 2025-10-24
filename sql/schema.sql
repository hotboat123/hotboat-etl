-- Base tables

create table if not exists leads (
    id text primary key,
    name text,
    email text,
    phone text,
    raw jsonb,
    source text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_leads_updated_at on leads;
create trigger trg_leads_updated_at
before update on leads
for each row execute procedure set_updated_at();


create table if not exists booknetic_appointments (
    id text primary key,
    customer_name text,
    customer_email text,
    service_name text,
    starts_at timestamptz,
    status text,
    raw jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_booknetic_updated_at on booknetic_appointments;
create trigger trg_booknetic_updated_at
before update on booknetic_appointments
for each row execute procedure set_updated_at();


