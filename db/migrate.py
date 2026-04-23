import re
from pathlib import Path

from db.connection import get_connection


def ensure_schema() -> None:
    statements = [
        # job_runs
        """
        create table if not exists job_runs (
            id bigserial primary key,
            job_name text not null,
            status text not null,
            started_at timestamptz not null,
            finished_at timestamptz,
            row_count integer,
            error text
        );
        """,
        """
        create index if not exists idx_job_runs_job_name_started_at
        on job_runs (job_name, started_at desc);
        """,
        # updated_at trigger function
        """
        create or replace function set_updated_at()
        returns trigger as $$
        begin
          new.updated_at = now();
          return new;
        end;
        $$ language plpgsql;
        """,
        # Informacion Reservas table + trigger
        """
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
        """,
        # Ensure new columns exist on already-created tables
        """
        alter table if exists "Informacion Reservas"
        add column if not exists raw jsonb;
        """,
        """
        drop trigger if exists trg_informacion_reservas_updated_at on "Informacion Reservas";
        """,
        """
        create trigger trg_informacion_reservas_updated_at
        before update on "Informacion Reservas"
        for each row execute procedure set_updated_at();
        """,
        # booknetic_appointments + trigger
        """
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
        """,
        """
        drop trigger if exists trg_booknetic_updated_at on booknetic_appointments;
        """,
        """
        create trigger trg_booknetic_updated_at
        before update on booknetic_appointments
        for each row execute procedure set_updated_at();
        """,
        # booknetic_customers + trigger
        """
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
        """,
        """
        drop trigger if exists trg_booknetic_cust_updated_at on booknetic_customers;
        """,
        """
        create trigger trg_booknetic_cust_updated_at
        before update on booknetic_customers
        for each row execute procedure set_updated_at();
        """,
        # payments
        """
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
        """,
        """
        drop trigger if exists trg_booknetic_pay_updated_at on booknetic_payments;
        """,
        """
        create trigger trg_booknetic_pay_updated_at
        before update on booknetic_payments
        for each row execute procedure set_updated_at();
        """,
        # Stock table + trigger
        """
        create table if not exists "Stock" (
            id text primary key,
            raw jsonb,
            source text,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        );
        """,
        """
        drop trigger if exists trg_stock_updated_at on "Stock";
        """,
        """
        create trigger trg_stock_updated_at
        before update on "Stock"
        for each row execute procedure set_updated_at();
        """,
        # Precios Extras table + trigger
        """
        create table if not exists "Precios Extras" (
            id text primary key,
            raw jsonb,
            source text,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        );
        """,
        """
        drop trigger if exists trg_precios_extras_updated_at on "Precios Extras";
        """,
        """
        create trigger trg_precios_extras_updated_at
        before update on "Precios Extras"
        for each row execute procedure set_updated_at();
        """,
        # Meta Ads (Marketing API sync for DBeaver / analytics)
        """
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
        """,
        """
        drop trigger if exists trg_meta_campaigns_updated_at on meta_campaigns;
        """,
        """
        create trigger trg_meta_campaigns_updated_at
        before update on meta_campaigns
        for each row execute procedure set_updated_at();
        """,
        """
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
        """,
        """
        drop trigger if exists trg_meta_adsets_updated_at on meta_adsets;
        """,
        """
        create trigger trg_meta_adsets_updated_at
        before update on meta_adsets
        for each row execute procedure set_updated_at();
        """,
        """
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
        """,
        """
        drop trigger if exists trg_meta_ads_updated_at on meta_ads;
        """,
        """
        create trigger trg_meta_ads_updated_at
        before update on meta_ads
        for each row execute procedure set_updated_at();
        """,
        """
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
        """,
        """
        create index if not exists idx_meta_ads_insights_campaign_date
        on meta_ads_insights (campaign_id, date_start desc);
        """,
        """
        create index if not exists idx_meta_ads_insights_date
        on meta_ads_insights (date_start desc);
        """,
        # flujo_caja (importado desde Google Sheets "Looker HotBoat")
        """
        create table if not exists flujo_caja (
            id text primary key,
            fila integer,
            raw jsonb,
            synced_at timestamptz not null default now(),
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        );
        """,
        """
        drop trigger if exists trg_flujo_caja_updated_at on flujo_caja;
        """,
        """
        create trigger trg_flujo_caja_updated_at
        before update on flujo_caja
        for each row execute procedure set_updated_at();
        """,
    ]

    with get_connection() as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        conn.commit()

    _ensure_meta_analytics_view()
    _ensure_marketing_costs_daily_view()


def _ensure_marketing_costs_daily_view() -> None:
    """Redefine marketing_costs_daily desde meta_ads_insights (sql/marketing_costs_daily_view.sql)."""
    path = Path(__file__).resolve().parent.parent / "sql" / "marketing_costs_daily_view.sql"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    text = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("--")
    ).strip()
    if not text:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP VIEW IF EXISTS marketing_costs_daily CASCADE")
            cur.execute(text)
        conn.commit()


def _ensure_meta_analytics_view() -> None:
    """Crea funciones helper + vista v_meta_ads_analytics (sql/v_meta_ads_analytics.sql)."""
    path = Path(__file__).resolve().parent.parent / "sql" / "v_meta_ads_analytics.sql"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    text = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("--")
    )
    # Partir en CREATE/COMMENT sin romper $$ ... $$
    parts = re.split(r"(?=\n(?:CREATE OR REPLACE|COMMENT ON))", "\n" + text.strip())
    stmts = [p.strip() for p in parts if p.strip()]
    if not stmts:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP VIEW IF EXISTS v_meta_ads_analytics CASCADE")
            for stmt in stmts:
                cur.execute(stmt)
        conn.commit()


