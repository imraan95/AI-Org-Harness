// T077: taxonomy management pane - lists the fixed built-in KnowledgeType
// values (read-only) alongside this workspace's own custom types, with a
// form to add a new one and a delete button on each custom type. Built-ins
// can't be deleted (harness-api rejects it - T077's own comment on
// delete_taxonomy_type), so no delete control is rendered for them.
import { getHarnessApiClient } from "@/lib/harness-api/client";

import { createType, deleteType } from "./actions";

export default async function TaxonomyPage() {
  const harnessApi = await getHarnessApiClient();
  const { data: types } = await harnessApi.GET("/taxonomy/types");

  const builtins = (types ?? []).filter((t) => t.builtin);
  const custom = (types ?? []).filter((t) => !t.builtin);

  return (
    <div>
      <h1>Taxonomy</h1>

      <h2>Built-in types</h2>
      <ul>
        {builtins.map((t) => (
          <li key={t.key}>
            {t.label} <code>({t.key})</code>
          </li>
        ))}
      </ul>

      <h2>Custom types</h2>
      {custom.length === 0 ? (
        <p style={{ opacity: 0.6 }}>No custom types yet.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {custom.map((t) => {
            const remove = deleteType.bind(null, t.key);
            return (
              <li key={t.key} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span>
                  {t.label} <code>({t.key})</code>
                </span>
                <form action={remove}>
                  <button type="submit">Delete</button>
                </form>
              </li>
            );
          })}
        </ul>
      )}

      <h2>Add a custom type</h2>
      <form action={createType} style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 320 }}>
        <label>
          Key
          <input name="key" placeholder="meeting_notes" required />
        </label>
        <label>
          Label
          <input name="label" placeholder="Meeting Notes" required />
        </label>
        <button type="submit">Add type</button>
      </form>
    </div>
  );
}
