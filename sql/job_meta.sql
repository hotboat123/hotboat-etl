create table if not exists job_runs (
    id bigserial primary key,
    job_name text not null,
    status text not null,
    started_at timestamptz not null,
    finished_at timestamptz,
    row_count integer,
    error text
);

create index if not exists idx_job_runs_job_name_started_at
on job_runs (job_name, started_at desc);


