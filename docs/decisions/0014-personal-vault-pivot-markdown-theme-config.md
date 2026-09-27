# 0014 — Personal-vault architecture pivot: themes move to markdown, shared/org vault deferred

**Status:** Accepted (partial - only the theme-config piece is built; see "What's still open" below)
**Date:** 2026-09-27
**Context:** A stress-test of the whole knowledge-harness idea ("what's the benefit of a structured store if we still lean on an LLM for everything downstream?"), prompted by researching an open-source project, `memoryvault-kit` (github.com/ayushmall/memoryvault-kit), which stores personal AI memory as plain markdown files with no database and no LLM in its retrieval path.

## Decision

Two things changed, and one thing was explicitly deferred:

1. **Vaults are personal, not a company requirement (for now).** Multi-tenant/shared-org semantics are TBD and out of scope until revisited - nothing in this decision assumes one shared org-wide vault.
2. **A workspace's custom themes (T077's `custom_knowledge_types`) now live in a markdown file, not a Postgres table.** `libs/vault_config` reads/writes `<VAULTS_ROOT>/<workspace_id>/themes.md` - a plain `- key: Label` bullet list, hand-editable, one file per workspace. `context-agent`'s `_tag_themes()` step and `harness-api`'s `/taxonomy/types` routes read/write this file instead of the old table.
3. **Everything else stays as it is, deliberately:** the `knowledge_records` table (with its `supersedes` chain and full schema) is unchanged; ingestion stays automatic/server-side (the Anarlog webhook still triggers `context-agent` unattended - a markdown vault the user edits by hand, per memoryvault-kit's model, doesn't fit an unattended pipeline the way it fits a human-present Claude Code session); `custom_knowledge_types`'s Postgres table and migration are left in place, unused, not dropped.

## Why

Researching `memoryvault-kit` surfaced a real, working precedent for markdown-backed AI memory with no LLM in the retrieval path (plain BM25 + graph walk, sub-ms latency) - useful evidence that not every layer needs a database or an LLM call to be effective. But its architecture assumes a human-present session doing the ingesting (auth for Slack/Notion/etc. needs a human, so it explicitly removed background cron), which is the opposite of how this project's ingestion pipeline works (an unattended webhook). That ruled out moving the actual knowledge-extraction pipeline to a user-triggered, agent-driven model - too large a rewrite for what the evidence actually supports.

What markdown-as-substrate does fit today: the theme/taxonomy layer. It's low-volume, workspace-scoped config, not the record store itself, and a person directly editing a themes.md file is a genuine UX improvement over a database row reachable only through a form - the exact thing memoryvault-kit's "plain files, hand-editable" philosophy is good evidence for.

## What changed, concretely

- New library `libs/vault_config` (`themes.py`): `read_themes`, `add_theme`, `remove_theme`, keyed by `workspace_id`, backed by `<VAULTS_ROOT>/<workspace_id>/themes.md` (`VAULTS_ROOT` env var, defaults to `./vaults`).
- `apps/context-agent/src/context_agent/pipeline.py`: `process_transcript()` no longer takes a Postgres `session` - takes `workspace_id: str = "default"` instead, and reads themes via `vault_config.read_themes()`.
- `apps/context-agent/src/context_agent/worker.py`: `run_worker_once()`'s call to `process_transcript()` no longer passes a session for theming (the session it does still hold is unrelated - the job queue).
- `apps/harness-api/src/harness_api/main.py`: `/taxonomy/types` GET/POST and `DELETE /taxonomy/types/{key}` now read/write the markdown file via `vault_config`, not the DB. Built-in-type validation logic unchanged.
- `vaults/default/themes.md` - checked in as the markdown equivalent of the old seed migration (`20260927100000_seed_default_custom_knowledge_types.sql`), holding the same 3 preselected themes (Customer Problems, Org Decisions, Strategic).
- `custom_knowledge_types` table, its migration, and `libs/db`'s `list_custom_knowledge_types`/`create_custom_knowledge_type`/`delete_custom_knowledge_type` are untouched but no longer called from any app - left dormant rather than dropped, same reasoning 0009 originally used for OpenViking (cheap to keep, no destructive migration needed until this direction is confirmed to stick).
- Web app's `/taxonomy` page needed no changes - it only talks to harness-api's HTTP routes, which kept the same request/response shapes.

## What's still open

- **Deployment path for `VAULTS_ROOT`.** Local dev defaults to `./vaults` relative to the working directory - fine for now, but a real deployment needs this pointed at a persistent volume outside the git checkout, not decided yet.
- **Conflict/supersession review workflow** (build-plan, separate task): now that a vault is personal, the multi-person sign-off model doesn't apply the same way - being handled as its own follow-up, not part of this decision.
- **Whether/how a shared, company-wide vault ever gets built.** Explicitly deferred, not ruled out.

## Alternatives considered

- **Move the actual `knowledge_records` content to markdown too** (the more literal reading of "switch to markdown"). Rejected for now - the records table's `supersedes` chain and status gating are doing real work this session's own stress-test didn't find a good markdown-native replacement for, and moving it wasn't actually what was needed to get the onboarding/theme-editing benefit.
- **Move ingestion to a user-triggered, agent-driven model** (matching memoryvault-kit's own architecture more fully). Rejected - would require rebuilding how `ingestion-service`/`context-agent` are triggered entirely, a much larger rewrite than the evidence (one project's README) justifies right now.

## Revisit when

If a real multi-person/shared-org vault becomes a requirement, this decision's "personal, not company" framing needs revisiting - probably alongside whether markdown remains the right substrate at that scale (memoryvault-kit's own numbers are for one person's vault, not a shared one with concurrent writers).
