create table if not exists ingestion_events (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  payload jsonb not null default '{}'::jsonb,
  received_at timestamptz not null default now(),
  transcript_id text references transcripts(id)
);
