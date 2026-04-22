-- Base tables

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- Informacion Reservas table
create table if not exists "Informacion Reservas" (
    id text primary key,
    name text,
    email text,
    phone text,
    raw jsonb,
    source text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_informacion_reservas_updated_at on "Informacion Reservas";
create trigger trg_informacion_reservas_updated_at
before update on "Informacion Reservas"
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

-- Customers table
create table if not exists booknetic_customers (
    id text primary key,
    name text,
    email text,
    phone text,
    status text,
    raw jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_booknetic_cust_updated_at on booknetic_customers;
create trigger trg_booknetic_cust_updated_at
before update on booknetic_customers
for each row execute procedure set_updated_at();

-- Payments table
create table if not exists booknetic_payments (
    id text primary key,
    appointment_id text,
    amount numeric,
    currency text,
    status text,
    method text,
    paid_at timestamptz,
    raw jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_booknetic_pay_updated_at on booknetic_payments;
create trigger trg_booknetic_pay_updated_at
before update on booknetic_payments
for each row execute procedure set_updated_at();

-- Stock table
create table if not exists "Stock" (
    id text primary key,
    raw jsonb,
    source text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_stock_updated_at on "Stock";
create trigger trg_stock_updated_at
before update on "Stock"
for each row execute procedure set_updated_at();

-- Precios Extras table
create table if not exists "Precios Extras" (
    id text primary key,
    raw jsonb,
    source text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_precios_extras_updated_at on "Precios Extras";
create trigger trg_precios_extras_updated_at
before update on "Precios Extras"
for each row execute procedure set_updated_at();


