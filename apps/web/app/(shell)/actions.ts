"use server";

// T069: logout - deferred from T068 (nothing needed it yet), needed now
// that there's a real nav to put it in.
import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";

export async function logout(): Promise<never> {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/login");
}
