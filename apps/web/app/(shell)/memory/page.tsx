// T070: Company Memory pane (PRD §16.A's 4 categories: what we know,
// what we decided, what changed, what customers are saying).
//
// harness-api's /context/* endpoints don't map 1:1 onto those 4 labels,
// so this is a judgment call, not a strict correspondence:
//   - "What customers are saying" -> GET /context/customer directly.
//   - "What we decided"           -> GET /decisions directly.
//   - "What we know"              -> GET /context/product + /context/strategy.
//   - "What changed"              -> GET /context, filtered client-side
//     for records whose `supersedes` is set (i.e. they replaced an
//     earlier belief) - there's no dedicated "changed" endpoint yet.
import { getHarnessApiClient } from "@/lib/harness-api/client";
import type { components } from "@/lib/harness-api/schema";

type KnowledgeRecord = components["schemas"]["KnowledgeRecord"];

function RecordList({ records }: { records: KnowledgeRecord[] }) {
  if (records.length === 0) {
    return <p style={{ opacity: 0.6 }}>Nothing recorded here yet.</p>;
  }
  return (
    <ul>
      {records.map((record) => (
        <li key={record.id}>{record.statement}</li>
      ))}
    </ul>
  );
}

export default async function MemoryPage() {
  const harnessApi = await getHarnessApiClient();

  const [product, strategy, customer, decisions, context] = await Promise.all([
    harnessApi.GET("/context/product"),
    harnessApi.GET("/context/strategy"),
    harnessApi.GET("/context/customer"),
    harnessApi.GET("/decisions"),
    harnessApi.GET("/context"),
  ]);

  const whatWeKnow = [...(product.data ?? []), ...(strategy.data ?? [])];
  const whatWeDecided = decisions.data ?? [];
  const whatCustomersAreSaying = customer.data ?? [];
  const whatChanged = (context.data ?? []).filter((record) => record.supersedes);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      <h1>Company Memory</h1>

      <section>
        <h2>What we know</h2>
        <RecordList records={whatWeKnow} />
      </section>

      <section>
        <h2>What we decided</h2>
        <RecordList records={whatWeDecided} />
      </section>

      <section>
        <h2>What changed</h2>
        <RecordList records={whatChanged} />
      </section>

      <section>
        <h2>What customers are saying</h2>
        <RecordList records={whatCustomersAreSaying} />
      </section>
    </div>
  );
}
