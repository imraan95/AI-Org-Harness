# infra

Local dev infrastructure that isn't Supabase (Supabase runs via its own CLI - `supabase start`/`supabase migration up`).

Currently empty. It held OpenViking's docker-compose entry from Phase 6 through `docs/decisions/0009` (made it opt-in only) until `docs/decisions/0011` (removed it entirely, along with the `vendor/openviking` submodule and `libs/openviking_client`'s `RealOpenVikingClient`). See those decisions for why - the short version: OpenViking's remaining role had shrunk to plain file storage, a plain Postgres table does that with less overhead, no AGPL question, and no Ollama-contention risk from a second service keeping its own models warm.

If this project ever needs local infra beyond Supabase again (a real Anarlog test double, a queue broker, etc.), this is where its docker-compose entry would go.
