// T068: server-side Supabase client, for use in Server Components,
// Server Actions, and Route Handlers. Bridges Supabase's session cookies
// through Next.js's own cookie store - the standard @supabase/ssr
// pattern for the App Router.
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            for (const { name, value, options } of cookiesToSet) {
              cookieStore.set(name, value, options);
            }
          } catch {
            // Called from a Server Component, which can't set cookies -
            // safe to ignore as long as middleware.ts is also refreshing
            // the session (it is - see middleware.ts).
          }
        },
      },
    },
  );
}
