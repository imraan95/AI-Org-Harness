"use server";

// T068: server action backing the login form - runs `signInWithPassword`
// server-side (so the Supabase session cookie is set via the server
// client, not exposed to hand-rolled client-side cookie logic) and
// redirects into the app on success.
import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";

export async function login(formData: FormData): Promise<{ error: string } | never> {
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  if (!email || !password) {
    return { error: "Email and password are required." };
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });

  if (error) {
    return { error: error.message };
  }

  redirect("/");
}
