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
        # leads table + trigger
        """
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
        """,
        # Ensure new columns exist on already-created tables
        """
        alter table if exists leads
        add column if not exists raw jsonb;
        """,
        """
        drop trigger if exists trg_leads_updated_at on leads;
        """,
        """
        create trigger trg_leads_updated_at
        before update on leads
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
    ]

    with get_connection() as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        conn.commit()


