// T068: browser-side Supabase client, for use in Client Components.
// Reads the two public env vars every @supabase/ssr app needs - see
// .env.example. NEXT_PUBLIC_* vars are safe to expose to the browser by
// Next.js convention (the anon key is meant to be public; real access
// control happens via Postgres RLS / harness-api's own auth, not by
// keeping this key secret).
import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
