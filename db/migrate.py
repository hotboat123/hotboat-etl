import re
import time
from pathlib import Path

from db.connection import get_connection

# Advisory lock ID único para serializar migraciones entre instancias concurrentes
_SCHEMA_LOCK_ID = 7_272_727_272


def ensure_schema() -> None:
    """
    Crea/actualiza el schema.
    Usa pg_advisory_lock para que solo una instancia corra DDL a la vez
    (necesario en rolling deploys de Railway donde dos contenedores se solapan).
    """
    with get_connection() as lock_conn:
        with lock_conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (_SCHEMA_LOCK_ID,))
        try:
            _ensure_schema_once()
        finally:
            with lock_conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_SCHEMA_LOCK_ID,))


def _ensure_schema_once() -> None:
    statements = [
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
        # flujo_caja_actual: mismas filas que flujo_caja pero con columnas tipadas
        """
        create table if not exists flujo_caja_actual (
            id            text primary key,
            fila          integer not null,
            synced_at     timestamptz not null default now(),
            fecha         date,
            descripci_n   text,
            cargos        numeric,
            abonos        numeric,
            saldo         numeric,
            categor_a_1   text,
            categor_a_2   text,
            observaciones text,
            origen        text
        );
        """,
        # Migrar columnas si ya existían como text (deploy anterior)
        """
        DO $$
        BEGIN
            IF (SELECT data_type FROM information_schema.columns
                WHERE table_name = 'flujo_caja_actual' AND column_name = 'fecha') = 'text' THEN
                ALTER TABLE flujo_caja_actual
                    ALTER COLUMN fecha  TYPE date
                        USING NULLIF(trim(fecha), '')::date,
                    ALTER COLUMN cargos TYPE numeric
                        USING NULLIF(replace(replace(trim(replace(cargos, '$', '')), ',', ''), '.', ''), '')::numeric,
                    ALTER COLUMN abonos TYPE numeric
                        USING NULLIF(replace(replace(trim(replace(abonos, '$', '')), ',', ''), '.', ''), '')::numeric,
                    ALTER COLUMN saldo  TYPE numeric
                        USING NULLIF(replace(replace(trim(replace(saldo,  '$', '')), ',', ''), '.', ''), '')::numeric;
            END IF;
        END $$;
        """,
    ]

    with get_connection() as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        conn.commit()

    _ensure_meta_analytics_view()
    _ensure_marketing_costs_daily_view()
    _ensure_google_ads_schema()


def _ensure_google_ads_schema() -> None:
    """Crea las tablas de Google Ads."""
    statements = [
        """
        create table if not exists google_ads_campaigns (
            id            text primary key,
            customer_id   text not null,
            name          text,
            status        text,
            channel_type  text,
            budget_micros bigint,
            raw           jsonb,
            created_at    timestamptz not null default now(),
            updated_at    timestamptz not null default now()
        );
        """,
        """
        drop trigger if exists trg_gads_campaigns_updated_at on google_ads_campaigns;
        """,
        """
        create trigger trg_gads_campaigns_updated_at
        before update on google_ads_campaigns
        for each row execute procedure set_updated_at();
        """,
        """
        create table if not exists google_ads_adgroups (
            id           text primary key,
            customer_id  text not null,
            campaign_id  text,
            name         text,
            status       text,
            raw          jsonb,
            created_at   timestamptz not null default now(),
            updated_at   timestamptz not null default now()
        );
        """,
        """
        drop trigger if exists trg_gads_adgroups_updated_at on google_ads_adgroups;
        """,
        """
        create trigger trg_gads_adgroups_updated_at
        before update on google_ads_adgroups
        for each row execute procedure set_updated_at();
        """,
        """
        create table if not exists google_ads_performance (
            customer_id                    text        not null,
            report_level                   text        not null,
            resource_id                    text        not null,
            date_start                     date        not null,
            resource_name                  text,
            campaign_id                    text,
            adgroup_id                     text,
            impressions                    bigint,
            clicks                         bigint,
            cost_micros                    bigint,
            average_cpc_micros             bigint,
            average_cpm_micros             bigint,
            conversions                    numeric,
            conversions_value              numeric,
            all_conversions                numeric,
            all_conversions_value          numeric,
            view_through_conversions       bigint,
            ctr                            numeric,
            search_impression_share        numeric,
            search_top_impression_share    numeric,
            search_abs_top_impression_share numeric,
            raw                            jsonb,
            fetched_at                     timestamptz not null default now(),
            primary key (customer_id, report_level, resource_id, date_start)
        );
        """,
        """
        create index if not exists idx_gads_perf_date
            on google_ads_performance (date_start desc, report_level);
        """,
        """
        create index if not exists idx_gads_perf_campaign
            on google_ads_performance (campaign_id, date_start desc);
        """,
    ]
    with get_connection() as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        conn.commit()


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


