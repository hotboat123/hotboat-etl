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

-- Meta Ads (Marketing API; synced by jobs/job_meta_ads.py)
create table if not exists meta_campaigns (
    id text primary key,
    ad_account_id text not null,
    name text,
    status text,
    objective text,
    raw jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_meta_campaigns_updated_at on meta_campaigns;
create trigger trg_meta_campaigns_updated_at
before update on meta_campaigns
for each row execute procedure set_updated_at();

create table if not exists meta_adsets (
    id text primary key,
    ad_account_id text not null,
    campaign_id text,
    name text,
    status text,
    raw jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_meta_adsets_updated_at on meta_adsets;
create trigger trg_meta_adsets_updated_at
before update on meta_adsets
for each row execute procedure set_updated_at();

create table if not exists meta_ads (
    id text primary key,
    ad_account_id text not null,
    campaign_id text,
    adset_id text,
    name text,
    status text,
    raw jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

drop trigger if exists trg_meta_ads_updated_at on meta_ads;
create trigger trg_meta_ads_updated_at
before update on meta_ads
for each row execute procedure set_updated_at();

create table if not exists meta_ads_insights (
    ad_id text not null,
    date_start date not null,
    date_stop date,
    ad_account_id text,
    campaign_id text,
    adset_id text,
    impressions bigint,
    clicks bigint,
    reach bigint,
    spend numeric,
    frequency numeric,
    cpm numeric,
    cpc numeric,
    ctr numeric,
    cpp numeric,
    actions jsonb,
    cost_per_action_type jsonb,
    raw jsonb,
    fetched_at timestamptz not null default now(),
    primary key (ad_id, date_start)
);

create index if not exists idx_meta_ads_insights_campaign_date
on meta_ads_insights (campaign_id, date_start desc);

create index if not exists idx_meta_ads_insights_date
on meta_ads_insights (date_start desc);

-- Mismas métricas que meta_ads_insights pero pedidas con breakdowns=region
-- a la API — tabla separada (no una columna region en meta_ads_insights)
-- para no tocar la llave primaria (ad_id, date_start) de la que dependen
-- marketing_costs / v_meta_ads_analytics. Una fila por anuncio × día × región.
create table if not exists meta_ads_insights_region (
    ad_id text not null,
    date_start date not null,
    region text not null,
    date_stop date,
    ad_account_id text,
    campaign_id text,
    adset_id text,
    impressions bigint,
    clicks bigint,
    reach bigint,
    spend numeric,
    frequency numeric,
    cpm numeric,
    cpc numeric,
    ctr numeric,
    cpp numeric,
    actions jsonb,
    cost_per_action_type jsonb,
    raw jsonb,
    fetched_at timestamptz not null default now(),
    primary key (ad_id, date_start, region)
);

create index if not exists idx_meta_ads_insights_region_date
on meta_ads_insights_region (date_start desc);

create index if not exists idx_meta_ads_insights_region_campaign_date
on meta_ads_insights_region (campaign_id, date_start desc);

create index if not exists idx_meta_ads_insights_region_region
on meta_ads_insights_region (region, date_start desc);


