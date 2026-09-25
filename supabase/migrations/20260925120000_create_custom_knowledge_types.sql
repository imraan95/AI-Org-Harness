-- T077: lets a workspace define its own KnowledgeType values on top of the
-- fixed built-in set (decision, fact, customer_insight, ...) - the built-ins
-- stay hardcoded (every MCP tool and the pipeline's classifier depend on
-- their exact values); this table only ever adds to that set.
create table if not exists custom_knowledge_types (
  id uuid primary key default gen_random_uuid(),
  workspace_id text not null default 'default',
  key text not null,
  label text not null,
  created_at timestamptz not null default now(),
  unique (workspace_id, key)
);
