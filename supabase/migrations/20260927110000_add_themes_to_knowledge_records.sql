-- User decision (2026-09-27): user-defined custom themes (customer_problems,
-- org_decisions, strategic, and whatever else a workspace adds via T077's
-- taxonomy) are multi-tag, not single-select like the existing `type`
-- column - a statement can genuinely belong to more than one theme at
-- once (e.g. a customer complaint that's also a strategic signal), and
-- forcing a single pick would throw one of those away. Kept as a
-- separate array column rather than folded into `type`, so nothing about
-- `type`'s existing single-value semantics (status logic, MCP tools,
-- every existing test) changes.
alter table knowledge_records
  add column if not exists themes text[] not null default '{}';
