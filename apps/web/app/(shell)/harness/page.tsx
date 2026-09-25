// T073: Harness pane (PRD §16.D: "what an AI would retrieve" for a topic).
//
// The MCP tool this mirrors, `search_company_context()` (T062), takes no
// query itself - it just returns every active record via `GET /context`
// and lets the model read the whole thing. There's no dedicated
// server-side search endpoint, so - same pattern as T070/T071/T072 - this
// pane fetches that same `/context` list and filters it client-side by
// the typed topic (substring match against topic + statement), as a
// preview of what's actually in the pool `search_company_context()` would
// hand the model.
import { getHarnessApiClient } from "@/lib/harness-api/client";
import type { components } from "@/lib/harness-api/schema";

type KnowledgeRecord = components["schemas"]["KnowledgeRecord"];

export default async function HarnessPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  const query = q?.trim() ?? "";

  const harnessApi = await getHarnessApiClient();
  const { data: context } = await harnessApi.GET("/context");
  const records: KnowledgeRecord[] = context ?? [];

  const matches = query
    ? records.filter((record) => {
        const haystack = `${record.topic} ${record.statement}`.toLowerCase();
        return haystack.includes(query.toLowerCase());
      })
    : [];

  return (
    <div>
      <h1>Harness</h1>
      <p style={{ opacity: 0.6 }}>
        Preview what an AI asking about a topic would be able to see in the harness right now.
      </p>

      <form method="get" style={{ display: "flex", gap: 8, marginBottom: "1.5rem" }}>
        <input
          name="q"
          type="text"
          defaultValue={query}
          placeholder="Type a topic..."
          style={{ flex: 1, padding: "0.5rem" }}
        />
        <button type="submit">Search</button>
      </form>

      {!query ? (
        <p style={{ opacity: 0.6 }}>Type a topic above to see what's currently recorded about it.</p>
      ) : matches.length === 0 ? (
        <p style={{ opacity: 0.6 }}>Nothing in the harness matches "{query}" yet.</p>
      ) : (
        <ul>
          {matches.map((record) => (
            <li key={record.id} style={{ marginBottom: "0.75rem" }}>
              <strong>{record.topic}</strong>
              <br />
              {record.statement}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
