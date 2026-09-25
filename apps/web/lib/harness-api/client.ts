// T060: typed access to harness-api's REST surface, generated from its
// live OpenAPI schema (see scripts/generate-frontend-types.sh and
// schema.d.ts, which that script regenerates - never hand-edit it).
// openapi-fetch reads those `paths` types, so every call here is typed
// end to end with no hand-written request/response types.
import createClient from "openapi-fetch";

import { createClient as createSupabaseServerClient } from "@/lib/supabase/server";

import type { paths } from "./schema";

const BASE_URL = process.env.NEXT_PUBLIC_HARNESS_API_BASE_URL ?? "http://127.0.0.1:8001";

// `accessToken` is the logged-in user's own Supabase session token - see
// apps/harness-api/src/harness_api/auth.py's `get_current_user_or_service`,
// which verifies it via JWKS. Omit it only for routes that don't need
// auth (there currently are none besides /health).
export function createHarnessApiClient(accessToken?: string) {
  return createClient<paths>({
    baseUrl: BASE_URL,
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });
}

// T070: every Server Component pane needs the same two steps (get the
// logged-in user's session, then build a client with its token) - this
// collapses that into one call so panes don't repeat it.
export async function getHarnessApiClient() {
  const supabase = await createSupabaseServerClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return createHarnessApiClient(session?.access_token);
}
