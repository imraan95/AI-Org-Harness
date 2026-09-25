// T071: Conflicts pane (PRD §16.B: "potential contradictions" and
// "pending confirmation"). harness-api's own /conflicts endpoint only
// covers status=conflicting (T053's own comment on that route); there's
// no dedicated "pending" endpoint, so this fetches /context (everything)
// and filters client-side for both statuses that need human review.
import { getHarnessApiClient } from "@/lib/harness-api/client";
import type { components } from "@/lib/harness-api/schema";

import { approveRecord, editRecord, rejectRecord } from "./actions";

type KnowledgeRecord = components["schemas"]["KnowledgeRecord"];
type TaxonomyType = components["schemas"]["TaxonomyType"];

const REVIEWABLE_STATUSES = new Set(["conflicting", "pending_review"]);

function ConflictCard({
  record,
  taxonomyTypes,
}: {
  record: KnowledgeRecord;
  taxonomyTypes: TaxonomyType[];
}) {
  const approve = approveRecord.bind(null, record.id);
  const reject = rejectRecord.bind(null, record.id);
  const edit = editRecord.bind(null, record.id);

  return (
    <li style={{ border: "1px solid #333", borderRadius: 8, padding: "1rem", marginBottom: "1rem" }}>
      <p>
        <strong>{record.status === "conflicting" ? "Contradiction" : "Pending confirmation"}</strong>
        {" - "}
        {record.topic}
      </p>
      <p>{record.statement}</p>

      <div style={{ display: "flex", gap: 8, marginBottom: "0.75rem" }}>
        <form action={approve}>
          <button type="submit">Approve</button>
        </form>
        <form action={reject}>
          <button type="submit">Reject</button>
        </form>
      </div>

      <details>
        <summary>Edit</summary>
        <form action={edit} style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
          <label>
            Statement
            <textarea name="statement" defaultValue={record.statement} style={{ width: "100%" }} />
          </label>
          <label>
            Topic
            <input name="topic" defaultValue={record.topic} style={{ width: "100%" }} />
          </label>
          <label>
            Confidence
            <input
              name="confidence"
              type="number"
              step="0.01"
              min="0"
              max="1"
              defaultValue={record.confidence}
            />
          </label>
          <label>
            Type
            <select name="type" defaultValue={record.type}>
              {taxonomyTypes.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <button type="submit">Save edit</button>
        </form>
      </details>
    </li>
  );
}

export default async function ConflictsPage() {
  const harnessApi = await getHarnessApiClient();
  const [{ data: context }, { data: taxonomyTypes }] = await Promise.all([
    harnessApi.GET("/context"),
    harnessApi.GET("/taxonomy/types"),
  ]);

  const reviewable = (context ?? []).filter((record) => REVIEWABLE_STATUSES.has(record.status));

  return (
    <div>
      <h1>Conflicts</h1>
      {reviewable.length === 0 ? (
        <p style={{ opacity: 0.6 }}>Nothing needs review right now.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {reviewable.map((record) => (
            <ConflictCard key={record.id} record={record} taxonomyTypes={taxonomyTypes ?? []} />
          ))}
        </ul>
      )}
    </div>
  );
}
