-- Postgres-backed replacement for OpenViking as the knowledge storage
-- layer (see docs/decisions/0008 and build-plan.md's "Is OpenViking still
-- the right storage layer?" open question). OpenViking's own client/tests
-- stay in the codebase, dormant - this table backs a second
-- OpenVikingClient implementation (PostgresOpenVikingClient) that becomes
-- the default at runtime.
create table if not exists knowledge_records (
  id text primary key,
  type text not null,
  topic text not null,
  statement text not null,
  status text not null,
  confidence double precision not null,
  source_ids text[] not null default '{}',
  people text[] not null default '{}',
  created_at timestamptz not null,
  observed_at timestamptz not null,
  last_updated_at timestamptz not null,
  supersedes text,
  superseded_at timestamptz,
  conflicts_with text[] not null default '{}',
  workspace_id text not null default 'default',
  source_id text not null default 'unspecified',
  visibility text not null default 'internal',
  owner text,
  access_level text not null default 'standard',
  edited_by text
);

create index if not exists knowledge_records_topic_idx on knowledge_records (topic);
create index if not exists knowledge_records_status_idx on knowledge_records (status);
create index if not exists knowledge_records_type_idx on knowledge_records (type);
