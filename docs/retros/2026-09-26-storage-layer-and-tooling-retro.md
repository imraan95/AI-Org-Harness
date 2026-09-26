# Retro — storage layer simplification, deployment prep, and the error loops along the way

**Date:** 2026-09-26
**Scope:** Everything from "let's deploy this first" through killing OpenViking as the default storage layer, the Postgres migration, and the test/tooling issues hit while doing it. Written as a synthesis, not a duplicate of `build-plan.md`'s task-by-task log — read that for exact status/test counts.

## What we set out to do vs. what actually happened

The original ask was "let's deploy this." That surfaced a real question before any VPS was provisioned: OpenViking (kept warm, needs downloading, drives Ollama contention) makes the deployment bigger and more expensive than it needs to be. Pulling that thread led to `docs/decisions/0009` (Postgres replaces OpenViking as the default storage layer) and a same-session discovery that ingestion-service's chunk-embedding step was dead weight too. Deployment itself hasn't resumed yet — this whole detour was scoping work that had to happen first, not a distraction from it.

## Error loops and tooling gotchas (not architecture — just friction)

- **`uv sync` at the workspace root doesn't sync every member.** It only syncs the root project's own dependencies. After any `pyproject.toml` edit anywhere in the workspace, `uv sync --all-packages` is the command that actually installs everything — plain `uv sync` will silently under-install and even report "Checked N packages, no changes" against a broken environment. Compounded by a corrupted `.venv` in this same session that made the problem hard to diagnose (only 19 site-packages entries, imports failing, but `uv sync` claiming nothing needed to change). `rm -rf .venv && uv sync --all-packages` is the reliable recovery.
- **Terminal got stuck in a `dquote>` prompt** pasting a multi-line `git commit -m "..."` message — most likely the terminal's smart-quote substitution turning a straight `"` into a curly one mid-paste, which breaks the shell's quote matching. Fix that actually worked: write the commit message to a file and use `git commit -F <path>` instead of a multi-line `-m` string. Worth adopting as the default for any commit message longer than one line, rather than re-hitting this.
- **Bracketed-paste artifacts** (`^[[200~` literal characters, `zsh: bad pattern`) showed up once when a long command was pasted — a terminal/paste-mode quirk, not a real error; re-running the same command cleanly fixed it.
- **`git: 'credential-manager' is not a git command`** appeared on push — a misconfigured git alias or credential helper somewhere in global git config. Didn't block the push (it completed via the normal path right after), but worth tracking down before it does block something.
- **`supabase db reset` failed once with a generic Docker "exit 1"** and succeeded cleanly on an immediate retry — treated as a one-off Docker hiccup since the retry's full output was clean, not chased further.

None of these are architecture problems. They're the kind of thing that eats a session if not named — worth remembering the fixes rather than rediscovering them next time.

## Real bugs found (not friction — actual defects caught before shipping)

- **pgvector rejects a zero-dimension vector.** Removing the dead embedding step meant `TranscriptChunk.embedding` became `[]` instead of a real vector, and Postgres's `vector` column type raises `DataError: vector must have at least 1 dimension` on an empty list. Fix was one line — store `None` instead of `[]` — because the column was already nullable and the read path already treated `NULL` as `[]`. Caught immediately by running the real test suite, not assumed to be fine.
- **Test fixtures disconnected from the app's own default.** ~13 test files across `harness-api`/`mcp-server`/the smoke test were seeding data by constructing `RealOpenVikingClient()` directly, instead of through whatever `get_knowledge_store()` actually resolves to. The moment harness-api's default flipped to Postgres, those tests would have silently validated against a backend the app no longer reads from — masked in dev only because `OPENVIKING_API_KEY` isn't set in this shell, so the tests still "passed" without actually proving anything. Caught by running the real suite and reporting the honest scope before declaring the config switch done, not by assuming green tests meant correctly wired.
- **A real hang traced to a real cause.** `scripts/test_e2e_smoke.py` got stuck mid-run. Working theory (not exhaustively proven, but consistent with the fix): the real Ollama embedding call inside ingestion-service's webhook handler, contended by OpenViking's container per the already-known T078 issue. Removing the dead embedding step resolved the hang in the same run that confirmed the fix — good but not airtight evidence, since no isolated repro was done first.
- **Older bugs from the same pattern, worth remembering as a class**: a stale event-loop-bound singleton (`OllamaLLM`/DB session factory) breaking under pytest's per-test loops (T047); OpenViking's `search/glob`/`search/grep` returning `404` for a not-yet-existing directory, which every earlier test avoided by coincidence until a genuinely brand-new topic hit it for real (T048); `source_ids` silently never being populated because `llm.extract()` only ever returned `topic`/`statement`, making a whole provenance feature a no-op against real data until wiring it up surfaced it (T058); OpenViking's `glob` capping at 256 matches with no pagination, invisible until real accumulated test data actually crossed that line (T061). Common thread: **fixture/test conditions accidentally avoided the exact case that broke in the real world**, every time. Not a criticism of any one task — a pattern worth watching for going forward: when a test passes, ask what specific case it didn't exercise, not just whether it's green.

## Architectural trajectory: OpenViking's role, told straight

This is the more interesting thread, because it wasn't one decision — it was four, each responding to real evidence from the last:

1. **0002/0003**: OpenViking in from day one, as a forked service with its own semantic-searchable file store — the ambitious original design.
2. **0007**: exact-string topic matching shipped instead of semantic retrieval, with an explicit "revisit only if real data shows topic drift is a frequent problem" condition — deliberately not solving a theoretical problem early.
3. **0008**: real data *did* show topic drift. OpenViking's semantic search was tried for real (three variants, not guessed at) and rejected on measured evidence — it summarizes `.json` files as generic "code" structure, so every record scored similarly regardless of actual content. Replaced with a direct pairwise LLM call instead.
4. **0009 (this session)**: once 0008 removed the last real use of OpenViking's semantic layer, what was left was "a smart-ish filesystem" — plain storage plus glob/grep. That narrower job, plus the 256-match cap being hit for real, OpenViking's container being a contributor to Ollama contention (T078), and its AGPL licensing still lacking general Legal sign-off, added up to making Postgres the default and OpenViking a dormant opt-in.

The lesson isn't "we should have started with Postgres" — 0007/0008's own findings (real embedding search results, real drift patterns) are what made 0009's case solid rather than speculative. It's that **the abstract `OpenVikingClient` interface built at T023, before OpenViking even existed in the repo, is what made this whole four-step descoping cheap.** Every step swapped an implementation behind a fixed interface instead of rewriting callers. That interface-first choice — made for testability (`FakeOpenVikingClient`) long before storage-layer flexibility was ever a stated goal — is doing double duty now. Worth remembering as a reason to keep drawing that kind of boundary even when the immediate justification is "just for tests."

## Process notes worth keeping

- **Never accept "tests pass" as "correctly wired" without checking what the tests actually exercise.** The seeding-fixture disconnect above would have shipped silently if the real suite hadn't been run and its skip/pass counts inspected before declaring done.
- **Mechanical, same-shaped multi-file edits are lower-risk than they look, but still need per-file verification.** The ~13-file test rewiring used one consistent pattern, but each file's other imports (`httpx`, `pytest`, unrelated skip guards) were checked individually via grep before removing anything, so files with a second, unrelated reason to skip didn't lose that guard.
- **When a fix is small and independent of a paused decision, it's worth surfacing as its own option rather than bundling it into the paused work or silently skipping it.** The embedding removal was explicitly offered as "small, independent of the frontier-model decision you paused" rather than assumed in scope or dropped.
- **Commit messages longer than one line: use `-F <file>`, not `-m "..."`, by default from now on** — direct outcome of the `dquote>` friction above.

## Open items this retro doesn't resolve

- The `credential-manager` git alias issue — not yet root-caused, didn't block anything yet but should be checked before it does.
- The GitHub repository casing rename (`AI-org-harness` → `AI-Org-Harness`) — pushes still redirect correctly, but worth updating the remote URL at some point to avoid relying on the redirect indefinitely.
- The Ollama-embedding-contention theory for the smoke test hang is plausible and consistent with the fix, but wasn't isolated with a standalone repro — if a similar hang recurs elsewhere, don't assume this exact cause without checking.
- Deployment itself (VPS, Supabase Cloud, Vercel, Anarlog webhook registration) is still not started — this entire retro covers the detour that happened instead, not the original ask.
