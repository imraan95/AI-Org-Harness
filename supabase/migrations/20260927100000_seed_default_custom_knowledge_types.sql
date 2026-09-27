-- By user decision (2026-09-27, revised same day - dropped a 4th
-- "Team Personas" type pending a separate design/policy decision, see
-- build-plan.md's "Open design questions"): preselect 3 custom knowledge
-- types "out of the box" for the default workspace, on top of T077's 12
-- fixed built-ins, so a new/existing workspace sees them in the taxonomy
-- immediately rather than starting empty and requiring manual setup.
--
-- `ON CONFLICT DO NOTHING` (keyed on T077's existing `unique (workspace_id,
-- key)` constraint) makes this safe to re-run - `supabase db reset` replays
-- every migration in order every time.
insert into custom_knowledge_types (workspace_id, key, label) values
  ('default', 'customer_problems', 'Customer Problems'),
  ('default', 'org_decisions', 'Org Decisions'),
  ('default', 'strategic', 'Strategic')
on conflict (workspace_id, key) do nothing;
