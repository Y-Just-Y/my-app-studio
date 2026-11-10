# Newark Civic Pulse: RAG research and decisions

Reviewed November 10, 2026. This AI-authored supporting research page belongs
under **2. Individual RAG app + technical research** in the existing
[combined individual record](https://y-just-y.github.io/is373_ci_cd/#heading-11).
It records sources, interpretations and open checks; it is not learner testimony
or a second submission.

## Revised question and boundaries

Can a Newark resident ask a small question about imported council records,
inspect the evidence and receive an answer that stays within that evidence?
The user replaced the earlier Docker-document corpus with Newark Civic Pulse
and requested official data, ETL and a testable chatbot.

The initial source family is public Newark Legistar meeting and selected agenda
metadata. The [City Clerk](https://www.newarknj.gov/166/Office-of-the-City-Clerk)
links to that system. An anonymous API request succeeded during this session.
[Legistar documentation](https://webapi.legistar.com/Home/Examples) explains
bounded queries and notes that token requirements vary by client. This observed
read does not promise permanent availability, a complete calendar or permission
to redistribute unrelated documents and assets. Keep attribution and acquisition
dates; inspect additional source rights before expanding the corpus.

## What the professor's repository actually provides

Reviewed [kaw393939/is373-rag](https://github.com/kaw393939/is373-rag), revision
`242fd57ecde387c98ff904cbe3dd2911aa46e2b0`. Its
[README](https://github.com/kaw393939/is373-rag/blob/242fd57ecde387c98ff904cbe3dd2911aa46e2b0/README.md)
and [status](https://github.com/kaw393939/is373-rag/blob/242fd57ecde387c98ff904cbe3dd2911aa46e2b0/docs/status.md)
identify documentation, synthetic labs and a static welcome scaffold; the
research backend remains planned. It supplies design ideas rather than a working
RAG application to copy. Its test receipts are not evidence for this project.

| Reference idea | Use here | Remaining boundary |
| --- | --- | --- |
| [Ingestion contracts](https://github.com/kaw393939/is373-rag/blob/242fd57ecde387c98ff904cbe3dd2911aa46e2b0/docs/architecture/ingestion.md): source revisions, dependent artifacts and separate readiness | Preserve source IDs/hashes; replace changed chunks; report lexical and vector readiness separately | No workflow engine or durable broker is running |
| [Retrieval contracts](https://github.com/kaw393939/is373-rag/blob/242fd57ecde387c98ff904cbe3dd2911aa46e2b0/docs/architecture/retrieval.md): distinct lexical/semantic evidence and bounded composition | FTS5 baseline plus an optional sqlite-vec index; prevent stale vectors entering current answers | Compare relevance before claiming a hybrid advantage |
| [Knowledge invariants](https://github.com/kaw393939/is373-rag/blob/242fd57ecde387c98ff904cbe3dd2911aa46e2b0/docs/project/knowledge.md): evidence identity differs from names and generated interpretations | Retain official IDs, dates and original links; an agenda listing does not establish final passage | No automatic entity resolution, graph publication or truth scoring |
| [Publication example source](https://github.com/kaw393939/is373-rag/blob/242fd57ecde387c98ff904cbe3dd2911aa46e2b0/docs/examples/publication.py): digest-bound requests, idempotency and transaction rollback | Independently test repeat imports, failed updates and stale-vector exclusion | Inspected the example's synthetic in-memory code; did not execute or adopt it as a production backend |

The reference status supersedes its older architecture ordering and defers a
broker. A direct Python importer is our first bounded step. Rust/NATS remain a
later experiment, rather than an unimplemented dependency disguised as complete.

## Primary research to project choices

| Source and passages read | What it supports | Decision and check here |
| --- | --- | --- |
| [Lewis et al., 2020, sections 2–2.2](https://arxiv.org/html/2005.11401v4) | Retrieval supplies external passages to generation; the original paper combines a trained retriever and generator | Retrieve current civic chunks before generation. Our API-based design is not a reproduction of its end-to-end training. Record actual retrieved IDs and answer support. |
| [Karpukhin et al., 2020, sections 3 and 5](https://arxiv.org/html/2004.04906v3) | Dense passage/query representations support retrieval; retrieval can be evaluated separately from answer generation | Compare required-source coverage at a fixed top-five budget against lexical search. Its benchmark gains do not establish gains for Newark records or OpenAI embeddings. |
| [Wang et al., 2024, sections 3.2, 3.4 and 5.1](https://arxiv.org/html/2407.01219v1) | Chunk boundaries, metadata and retrieval combinations involve quality/efficiency tradeoffs; more elaborate pipelines can cost more | Keep short civic records intact; split long paragraphs at bounded word boundaries. Compare against fixed windows. Retain headings and dates. Do not adopt the paper's models, sizes or preferred stack without local evidence. |
| [Es et al., 2023, section 3](https://arxiv.org/html/2309.15217v1) | Faithfulness, answer relevance and context relevance describe different evaluation dimensions | Judge retrieved evidence separately from whether answer claims follow from it. Human inspection is the initial rubric; no RAGAS score or automatic judge has been executed. |
| [Liu et al., 2023, section 2.3](https://arxiv.org/html/2307.03172v3) | In the evaluated models/tasks, useful evidence placement and long distracting context affected results | Supply a small ranked context rather than the whole website. This is a design precaution, not a measured position effect for our current model. |

## Database and chunking comparison

The small first corpus favors SQLite plus
[FTS5](https://sqlite.org/fts5.html) for exact names/IDs and
[sqlite-vec](https://alexgarcia.xyz/sqlite-vec/python.html) for optional semantic
search. The stable extension is pinned to `0.1.9`. A separate civic database
keeps public source material out of account/session storage.

[Graph databases](https://neo4j.com/docs/getting-started/graph-database/) represent
entities and typed relationships. A plausible civic model is
`AgendaItem → LISTED_AT → Meeting`, with the official item/meeting IDs and source
as evidence. Names alone do not establish entity identity, and listed items do
not imply approval. Native graph storage/extraction is deferred until a
relationship question demonstrates a useful missing capability.

ETL is the engineering sequence **extract → transform → load**: request bounded
official records, validate/normalize their fields into versioned text and
metadata, then commit sources/chunks/indexes. It is not a claim that the RAG papers
invented this data-engineering pattern. Current paragraph splitting is measured
in Unicode characters, not model tokens. Compare boundary methods on the same
records; preserve a complete date/time/location statement when possible.

## Evidence snapshot and next experiment

The actual sqlite-vec extension passed **21 local fixture tests**, including
ranking mechanics, repeat-import reuse, stale-version exclusion and atomic model
replacement. Fixture vectors prove these contracts; they do not establish real
embedding quality. Subsequent integration produced eight real compatible
1,536-dimensional embeddings and five saved model-answer trials. The
[results](newark-results.md) separate actual model outputs and AI evidence review
from human peer verification, which remains pending.

The evaluated demo fixed five questions: one exact-term lookup, one
paraphrase, one agenda-to-meeting relationship, one comparison across imported
records and one unsupported budget question. Expected source IDs were frozen
before calls; actual ranks/context/answers/model configuration and citation
support reviews are retained. Keyword and hybrid covered all required sources
on four supported questions; vector alone missed one required source on the
relationship question. No general hybrid improvement is inferred. The unsupported
budget question was actually declined. Missing-evidence and future-calendar
questions must remain honest:
a recent-record snapshot cannot establish Newark's next meeting.
