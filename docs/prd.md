# AI Organisational Harness

## MVP Product Requirements Document

## 1. Product summary

Build an AI employee that continuously observes company conversations and automatically builds and maintains a structured organisational "harness".

The harness captures:

- What the company knows
- What the company believes
- What has been decided
- What has changed
- What customers are saying
- Who owns what
- What processes and rules exist
- Where organisational knowledge conflicts

The harness can then be consumed by other AI tools through MCP/API so that AI employees have access to relevant company context without employees manually creating prompts, uploading documents or maintaining knowledge bases.

## 2. Core hypothesis

Companies are increasingly using AI tools, but those tools lack organisational context.

Important context currently exists across:

- Meeting conversations
- Slack
- CRM
- Support tickets
- Documents
- Sales calls
- Product tools
- Individual employees' institutional knowledge

Most AI products treat this as a search problem.

This product treats it as a continuous organisational memory problem.

The hypothesis: an AI that continuously converts company activity into structured, current and permission-aware organisational context will make downstream AI substantially more useful.

## 3. MVP scope

The MVP should deliberately focus on meetings as the first source of organisational knowledge.

**Input**

Meeting transcripts captured by Anarlog.

**Processing**

AI analyses each transcript and identifies:

1. Decisions
2. Facts / organisational knowledge
3. Customer insights
4. Actions
5. People and ownership
6. Changes to existing knowledge
7. Potential contradictions
8. Emerging themes

**Output**

A continuously updated organisational memory.

**Consumption**

Expose the memory through MCP so Claude, Cursor or another AI agent can query it.

## 4. MVP user

**Primary user**

A founder, product leader or knowledge-intensive team using multiple AI tools.

The user should be able to connect the system once and then largely leave it alone. The AI employee does the ongoing knowledge maintenance.

## 5. Core user experience

The user connects Anarlog. The system periodically discovers new meetings.

For every new meeting:

```
Meeting
   ↓
Transcript
   ↓
AI analysis
   ↓
Existing organisational knowledge retrieved
   ↓
New information compared against existing knowledge
   ↓
Knowledge updated
   ↓
Harness updated
```

The user should not need to manually summarise meetings.

## 6. Example

A meeting transcript contains: "Three enterprise customers have asked for SSO and Sales says it's becoming a blocker."

The system searches existing knowledge.

Existing memory:

```
Enterprise SSO

Status:
Occasional customer request

Evidence:
2 customer conversations

Last updated:
July 2026
```

The new meeting produces:

```
Potential knowledge update

Topic:
Enterprise SSO

New evidence:
3 enterprise customers reportedly requesting SSO.

New signal:
Sales considers SSO a potential deal blocker.

Existing belief:
SSO is an occasional request.

Proposed update:
SSO may represent a recurring enterprise requirement.

Confidence:
Medium

Source:
September 2026 product meeting
```

The system does not blindly overwrite the old knowledge. It records the evolution of the belief.

## 7. Knowledge model

Every organisational memory should have structured metadata.

```json
{
  "id": "K-00142",
  "type": "customer_insight",
  "topic": "enterprise_sso",
  "statement": "SSO is becoming a recurring enterprise requirement",
  "status": "active",
  "confidence": 0.82,
  "source_ids": [
    "meeting_123",
    "meeting_127"
  ],
  "people": [
    "person_12",
    "person_31"
  ],
  "created_at": "...",
  "observed_at": "...",
  "last_updated_at": "...",
  "supersedes": "K-00087"
}
```

Initial knowledge types:

- `decision`
- `fact`
- `customer_insight`
- `strategy`
- `product_requirement`
- `process`
- `policy`
- `person`
- `ownership`
- `action`
- `hypothesis`
- `conflict`

## 8. Temporal memory

The system must distinguish between "the company has discussed X" and "X is currently true." Organisational knowledge changes over time.

For important memories, maintain:

- First observed
- Last observed
- Effective date
- Superseded date
- Current status
- Confidence
- Supporting evidence

Example:

```
Product strategy

Jan 2026:
SMB acquisition

Jun 2026:
Enterprise expansion

Sep 2026:
Enterprise retention

Current:
Enterprise retention
```

The system should preserve historical knowledge rather than deleting it.

## 9. Contradiction detection

This is a core MVP capability.

When new information conflicts with existing knowledge, the system should flag it.

Example:

Existing: "SSO is not planned for Q4."

New meeting: "We're going to ship SSO in November."

The system produces:

```
Potential contradiction

Existing:
SSO not planned for Q4

New:
SSO planned for November

Sources:
Product roadmap meeting
Leadership meeting

Status:
Requires confirmation
```

The system should not automatically decide which statement is correct unless sufficient evidence exists.

## 10. Confidence

Every extracted item should have a confidence score.

Confidence should consider:

- Explicitness of statement
- Source reliability
- Number of supporting sources
- Recency
- Whether multiple people corroborated it
- Whether it conflicts with existing knowledge

Example:

```
CEO-approved decision        High
Formal roadmap decision      High
PM statement                 Medium
Customer statement           Medium
Speculation                  Low
Casual conversation          Low
```

These should initially be rules/prompts rather than a sophisticated ML model.

## 11. AI model strategy

The product should not depend on a proprietary frontier model.

Default model: an open-weight model that can be run locally or inexpensively, initially a Llama-family model or comparable model.

Architecture:

```
                MODEL ROUTER
                     │
       ┌─────────────┼─────────────┐
       ↓             ↓             ↓
     Llama        Other open      Optional
                  model           frontier API
```

The application should abstract the model behind a common interface.

Example:

```
LLM.generate()
LLM.extract()
LLM.classify()
LLM.compare()
LLM.summarise()
```

This allows the model to be swapped without rewriting the application.

**MVP principle**: use the cheapest capable model for each task.

For example:

```
Transcript classification → small model
Entity extraction → small model
Basic summarisation → small model
Contradiction detection → larger model
Complex synthesis → larger model
```

A future optimisation could route inference based on complexity.

## 12. Context/memory architecture

MVP architecture:

```
                  Context Agent
                       │
                       ▼
                  OpenViking
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
    Resources       Memories        Skills
```

OpenViking is the memory/context orchestration layer from day one — the Context Agent reads and writes through it rather than talking to storage directly. Postgres + pgvector sits underneath OpenViking as the concrete store for:

- Raw transcripts
- Chunks
- Entities
- Memories
- Decisions
- Evidence
- Relationships
- Metadata

OpenViking is infrastructure, not the product. The system should remain replaceable if required — Postgres + pgvector is the fallback of record if OpenViking ever needs to be swapped out or bypassed.

## 13. Meeting ingestion

**MVP source**: Anarlog.

Anarlog provides:

- Meeting recording
- On-device transcription
- Local storage
- API
- MCP
- CLI
- Webhooks

The MVP should consume the resulting transcript rather than build its own transcription system.

Initial flow:

```
Anarlog
   ↓
New transcript
   ↓
Webhook / API / MCP
   ↓
Ingestion service
```

## 14. Harness API

The organisational harness should be accessible programmatically.

Example:

```
GET /context
GET /context/product
GET /context/customer
GET /context/strategy
GET /decisions
GET /people
GET /conflicts
GET /knowledge/{id}
```

But the primary AI interface should be MCP.

Example tools:

```
search_company_context()
get_current_strategy()
get_recent_decisions()
get_customer_insights()
get_product_context()
get_person_context()
get_conflicting_information()
get_evidence()
```

This allows other AI applications to consume the harness.

## 15. MCP experience

A user connects the company harness to Claude. They ask: "Why aren't we building SSO?"

The harness should return:

```
Current understanding:

SSO has been identified as a recurring enterprise
customer requirement.

However, the current product roadmap does not include
SSO this quarter.

Evidence:
- 3 customer conversations
- 2 sales discussions
- Product planning meeting
- Leadership meeting

The latest product decision prioritised onboarding
improvements over SSO.

There is currently a tension between customer demand
and product prioritisation.
```

Every answer should provide provenance.

## 16. Simple web interface

The MVP UI only needs four areas.

**A. Company Memory**

```
What we know
What we decided
What changed
What customers are saying
```

**B. Conflicts**

```
Potential contradictions
Pending confirmation
```

**C. Sources**

Show the meetings supporting each memory.

**D. Harness**

Show what an AI would retrieve when asking about a topic.

Do not build a sophisticated enterprise dashboard initially.

## 17. Human-in-the-loop

Initially, humans should be able to approve important changes.

Example:

```
NEW PROPOSED MEMORY

"Enterprise customers increasingly require SSO."

Evidence:
3 meetings

Confidence:
82%

[Approve]
[Edit]
[Reject]
```

Low-risk updates can eventually become automatic. High-impact updates should require approval. The system should learn from these approvals.

## 18. Permissions

MVP assumption: one trusted workspace.

Do not attempt sophisticated enterprise permissions initially.

However, the data model must support:

```
workspace_id
source_id
visibility
owner
access_level
```

This prevents a future architectural rewrite when Slack, HR, finance or confidential sales information is added.

## 19. Future data sources

After meetings work:

**Phase 2**

```
Slack
Notion
Google Drive
```

**Phase 3**

```
Gong
Zendesk
Intercom
Salesforce
HubSpot
Jira
Linear
GitHub
```

Each source becomes another organisational sensor.

```
                 COMPANY
                    │
       ┌────────────┼────────────┐
       ↓            ↓            ↓
    Meetings       Slack       CRM
       │            │            │
       └────────────┼────────────┘
                    ↓
              Context Agent
                    ↓
             Business Harness
```

## 20. What is explicitly NOT in MVP

Do not build:

- Custom foundation model
- Fine-tuning
- Autonomous email sending
- Autonomous decision making
- Enterprise SSO
- Complex RBAC
- Multi-agent architecture
- Custom transcription engine
- Mobile app
- Dozens of integrations
- Graph database
- Sophisticated analytics
- Fully autonomous knowledge deletion

The goal is to prove the core loop.

## 21. Success metrics

**Primary metric**

Harness usefulness: after processing a company's meetings, can another AI answer company-specific questions better using the harness than without it?

**Secondary metrics**

Knowledge extraction accuracy: percentage of extracted decisions/knowledge that humans consider correct.

Knowledge freshness: percentage of answers based on current rather than superseded organisational knowledge.

Conflict detection precision: percentage of flagged conflicts that humans consider genuine conflicts.

Coverage: percentage of important organisational decisions appearing in the harness.

Human intervention: number of manual edits/approvals required per 100 meetings.

The long-term goal is to reduce human maintenance toward zero.

## 22. Technical architecture

```
                  ANARLOG
                     │
                     ▼
              INGESTION SERVICE
                     │
                     ▼
              TRANSCRIPT STORE
                     │
                     ▼
               CONTEXT AGENT
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       Extract    Compare     Classify
          │          │          │
          └──────────┼──────────┘
                     ▼
                OPENVIKING
             (Resources / Memories / Skills)
                     │
             ┌───────┴────────┐
             ▼                ▼
          Postgres        pgvector
             │                │
             └───────┬────────┘
                     ▼
               HARNESS API
                     │
                     ▼
                    MCP
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       Claude      Cursor    Other AI
```

## 23. Recommended build sequence

**Milestone 1** — Transcript upload. Input a transcript manually. Output structured decisions, insights and actions.

**Milestone 2** — Persistent memory on OpenViking. Store extracted information in OpenViking (Resources/Memories/Skills, backed by Postgres + pgvector) and retrieve it later.

**Milestone 3** — Context comparison. Before creating a memory, search existing memories via OpenViking.

**Milestone 4** — Contradiction detection. Identify conflicting organisational knowledge.

**Milestone 5** — Anarlog integration. Automatically ingest new meeting transcripts.

**Milestone 6** — MCP. Allow Claude to query the organisational harness.

**Milestone 7** — Temporal knowledge. Track what changed and what is currently believed.

**Milestone 8** — First external source. Add Slack or another high-value source.

## 24. Product north star

The eventual product should feel less like "chat with your company documents" and more like "your company's institutional memory is continuously maintained by an AI employee."

The AI employee should eventually:

```
OBSERVE
Meetings, conversations, systems

UNDERSTAND
What happened and what matters

REMEMBER
Maintain organisational knowledge

RECONCILE
Detect conflicts and outdated beliefs

STRUCTURE
Maintain people, decisions, processes and relationships

SERVE
Give every AI agent the right context

LEARN
Adapt to how the organisation actually operates
```

The long-term moat is therefore not the underlying LLM. It is the organisation-specific context graph, temporal memory, source relationships, decision history, permissions and accumulated understanding of how that company operates.
