// T072: Sources pane (PRD §16.C: "meetings supporting each memory").
//
// harness-api only attaches `sources` (meeting title/date) to the
// single-item route `GET /knowledge/{id}` (T058), not to list routes like
// `/context` - so this pane is select-then-view, not list-everything:
// a left-hand list of topics (from the cheap `/context` call) links to
// `?id=<record id>`, and only the selected record fetches its sources.
import Link from "next/link";

import { getHarnessApiClient } from "@/lib/harness-api/client";
import type { components } from "@/lib/harness-api/schema";

type KnowledgeRecord = components["schemas"]["KnowledgeRecord"];

function formatMeetingDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default async function SourcesPage({
  searchParams,
}: {
  searchParams: Promise<{ id?: string }>;
}) {
  const { id } = await searchParams;
  const harnessApi = await getHarnessApiClient();

  const { data: context } = await harnessApi.GET("/context");
  const records: KnowledgeRecord[] = context ?? [];

  const selected = id
    ? await harnessApi.GET("/knowledge/{knowledge_id}", { params: { path: { knowledge_id: id } } })
    : null;

  return (
    <div style={{ display: "flex", gap: "2rem" }}>
      <div style={{ minWidth: 260 }}>
        <h1>Sources</h1>
        {records.length === 0 ? (
          <p style={{ opacity: 0.6 }}>No knowledge recorded yet.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0 }}>
            {records.map((record) => (
              <li key={record.id} style={{ marginBottom: "0.5rem" }}>
                <Link
                  href={`/sources?id=${record.id}`}
                  style={{ fontWeight: record.id === id ? "bold" : "normal" }}
                >
                  {record.topic}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div style={{ flex: 1 }}>
        {!id ? (
          <p style={{ opacity: 0.6 }}>Select an item on the left to see what it's based on.</p>
        ) : !selected?.data ? (
          <p style={{ opacity: 0.6 }}>That record couldn't be found.</p>
        ) : (
          <div>
            <h2>{selected.data.topic}</h2>
            <p>{selected.data.statement}</p>
            <h3>Supporting meetings</h3>
            {selected.data.sources.length === 0 ? (
              <p style={{ opacity: 0.6 }}>No linked meetings found for this record.</p>
            ) : (
              <ul>
                {selected.data.sources.map((source, index) => (
                  <li key={index}>
                    {source.meeting_title} - {formatMeetingDate(source.meeting_date)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
