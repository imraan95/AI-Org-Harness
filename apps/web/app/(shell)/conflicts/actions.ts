"use server";

// T071: Approve/Reject/Edit, wired to harness-api's existing routes
// (T055/T056/T057). Each action revalidates the pane afterward so the
// record's new status/content shows up without a manual refresh.
import { revalidatePath } from "next/cache";

import { getHarnessApiClient } from "@/lib/harness-api/client";
import { createClient as createSupabaseServerClient } from "@/lib/supabase/server";

export async function approveRecord(knowledgeId: string): Promise<void> {
  const harnessApi = await getHarnessApiClient();
  await harnessApi.POST("/knowledge/{knowledge_id}/approve", {
    params: { path: { knowledge_id: knowledgeId } },
  });
  revalidatePath("/conflicts");
}

export async function rejectRecord(knowledgeId: string): Promise<void> {
  const harnessApi = await getHarnessApiClient();
  await harnessApi.POST("/knowledge/{knowledge_id}/reject", {
    params: { path: { knowledge_id: knowledgeId } },
  });
  revalidatePath("/conflicts");
}

export async function editRecord(knowledgeId: string, formData: FormData): Promise<void> {
  const supabase = await createSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const statement = formData.get("statement");
  const topic = formData.get("topic");
  const confidenceRaw = formData.get("confidence");

  const harnessApi = await getHarnessApiClient();
  await harnessApi.POST("/knowledge/{knowledge_id}/edit", {
    params: { path: { knowledge_id: knowledgeId } },
    body: {
      // Server-supplied from the logged-in session, not a client-editable
      // field - a human reviewer can't attribute an edit to someone else.
      edited_by: user?.email ?? "unknown",
      statement: typeof statement === "string" && statement.length > 0 ? statement : null,
      topic: typeof topic === "string" && topic.length > 0 ? topic : null,
      confidence:
        typeof confidenceRaw === "string" && confidenceRaw.length > 0
          ? Number(confidenceRaw)
          : null,
    },
  });
  revalidatePath("/conflicts");
}
