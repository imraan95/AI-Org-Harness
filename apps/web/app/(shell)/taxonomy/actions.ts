"use server";

// T077: add/delete custom knowledge types, wired to harness-api's
// /taxonomy/types routes. Same "server action + revalidatePath" shape as
// conflicts/actions.ts.
import { revalidatePath } from "next/cache";

import { getHarnessApiClient } from "@/lib/harness-api/client";

export async function createType(formData: FormData): Promise<void> {
  const key = formData.get("key");
  const label = formData.get("label");
  if (typeof key !== "string" || key.length === 0) return;
  if (typeof label !== "string" || label.length === 0) return;

  const harnessApi = await getHarnessApiClient();
  await harnessApi.POST("/taxonomy/types", { body: { key, label } });
  revalidatePath("/taxonomy");
}

export async function deleteType(key: string): Promise<void> {
  const harnessApi = await getHarnessApiClient();
  await harnessApi.DELETE("/taxonomy/types/{key}", {
    params: { path: { key } },
  });
  revalidatePath("/taxonomy");
}
