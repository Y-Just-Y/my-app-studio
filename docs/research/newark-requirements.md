# Individual review: requirement and evidence map

Snapshot: November 10, 2026. AI-authored checklist linked from the existing
combined record, not a duplicate report or a grade. Code presence, a planned
check, a passed fixture test and an observed hosted journey are different claims.

Authoritative sources checked: [Canvas Plan assignment](https://njit.instructure.com/courses/70733/assignments/769188),
[portfolio brief](https://github.com/kaw393939/is373-studio/blob/8f6acc238b7c6b2dc1b7c4dab5710e8e54892bab/docs/projects/portfolio.md),
[RAG brief](https://github.com/kaw393939/is373-studio/blob/8f6acc238b7c6b2dc1b7c4dab5710e8e54892bab/docs/projects/individual.md),
[milestones](https://github.com/kaw393939/is373-studio/blob/8f6acc238b7c6b2dc1b7c4dab5710e8e54892bab/docs/course/milestones.md)
and [record/workshop instructions](https://github.com/kaw393939/is373-studio/blob/8f6acc238b7c6b2dc1b7c4dab5710e8e54892bab/docs/templates/project-record.md).

## 1. Individual portfolio + career research

| Requirement | Evidence location and current limit |
| --- | --- |
| Three original employer records across at least two role families; FDE reference and verified junior/internship example when available | [Existing portfolio research](https://y-just-y.github.io/is373_ci_cd/#heading-2) records three postings. Their current availability, eligibility and accuracy were not rechecked in this Newark implementation pass. |
| Employer/title/link/access date; location/eligibility; required/preferred qualifications; three responsibilities; existing evidence/gap/dated next action | Existing employer entries contain these fields or explicit unknowns. Learner verification remains pending; no qualification is inferred from coursework. |
| Compare two career directions; choose target reader; map three responsibilities to evidence | Existing career comparison/evidence map. Confirm the revised Newark RAG case study still supports the chosen cloud/platform direction. |
| Outline portfolio pages; compare two lightweight layouts and explain selection | Existing Plan outlines both. Hosted portfolio implementation and the visitor's response remain unverified. |
| Accurate introduction, individual RAG and group case studies, own contribution, code/demo links, suitable resume/profiles/contact | Planned portfolio routes in the combined record. Civic Pulse is project evidence; its homepage alone is not a finished professional portfolio. Confirm contact assets and contributions before publication. |
| Public access, readability, keyboard/mobile behavior and working links | Prior application checks do not establish the later portfolio. Run and link route-specific checks when implemented. |
| Real peer finds role direction/evidence; meaningful improvement and retest | Pending. AI review is not human peer feedback. Keep private career reflection in Canvas. |

## 2. Individual RAG app + technical research

| Requirement | Implementation/evidence and remaining check |
| --- | --- |
| Research vector/graph databases, RAG, chunking, embeddings, entities/relationships and import; compare before choosing | [Research and decisions](newark-rag.md) includes primary papers and the professor reference. Native graph storage is deferred with a reason. |
| Bounded permitted corpus, source manifest, versions and repeat/update behavior | [Importer](../../civic_import.py), [ETL](../../app/civic_etl.py), [store](../../app/civic_store.py). Actual import: **7 public sources / 8 chunks**: five recent Municipal Council meeting records and two selected agenda items. Public metadata is read from the City Clerk-linked Newark Legistar API without a key; source IDs, URLs, hashes, source/fetch dates and local meeting timezone are retained. After two broken original-page links were repaired through verified matching official API records, repeat import reported **7 unchanged**, with stable counts/IDs. The collection is a bounded recent-record snapshot, not all Newark data or a complete current calendar. |
| Real representation and retrieval; chosen model/database configuration | [Vector adapter](../../app/civic_vectors.py), [embedding CLI](../../civic_embed.py) and [executed evidence](newark-results.md). SQLite FTS5 supplies the keyword baseline; sqlite-vec holds **8 current, compatible real embeddings**, generated with `text-embedding-3-small`, **1536 dimensions**. The two source chunks whose citation URLs changed were re-embedded after the link repair. Fixture vectors are used only in explicitly labeled isolated tests. |
| Source-supported generated answers, usable references and insufficient-evidence behavior | The [OpenAI gateway](../../app/civic_ai.py) was exercised with **five actual `gpt-5-mini` generation requests**, with frozen expectations and AI claim-level review in [results](newark-results.md) / [machine-readable receipt](newark-results.json). Q1–Q4 were supported within the stated wording limits; Q5 returned insufficient evidence without inventing a budget amount. Every URL actually cited in those answers returned **HTTP 200**. Two original, uncited catalog page URLs returned **410**; their failure is retained in provenance and their current citation targets are verified official per-record API URLs. A valid source ID alone does not prove claim support. |
| Compare keyword baseline and selected retrieval; compare two bounded design choices | The same five-question evaluation recorded keyword, vector and hybrid rankings. For the four answerable questions, keyword and hybrid each retrieved every required source set in **4/4** cases; vector did so in **3/4**, with partial Q3 coverage. This set shows no hybrid source-coverage improvement over keyword. At equal **1600-character caps and zero overlap**, paragraph and fixed-window splitting each produced **8 chunks**, retaining the complete date/time/location span in **5/5** meeting records. These are character-based boundary observations, not evidence of a tokenizer-aware or answer-quality advantage. |
| Small evaluation set including exact term, paraphrase, relationship and unanswerable case; three to five observable stories/checks | [Frozen evaluation receipt](newark-results.json) records expected source IDs, actual rankings, supplied context, generated answers, citations and review for Q1–Q5. Q5 appropriately refused the unsupported total-budget question. Import/reimport/update, denied admin access, request limits and browser source-search journeys have isolated checks. Keep scheduled dates distinct from occurrence, future dates or final passage; broader questions and human review remain open. |
| Private services/credentials, server-side import authorization, bounded public usage and cost/resource limits | [Civic routes](../../app/features/civic.py), [limits](../../app/civic_limits.py) and [HTTP/security tests](../../tests/test_civic_routes.py) verify anonymous import **401**, member import **403**, current-admin plus CSRF enforcement, strict import scope, question/body bounds, sanitized errors and key/account isolation. Durable ceilings are **5 requests per client per 5 minutes** and **30 application-wide per day**, with one active AI call. Changed source state returns **409** instead of using a stale answer snapshot. Public retrieval storage remains separate from accounts; API keys stay server-side. **Local full check passed:** Black, Pylint, **196 unit/integration + 18 cumulative contracts + 3 Chromium journeys = 217 tests**. This is scoped technical evidence, not a security certification or evidence of learner understanding. |
| Working hosted journey, persistent data, selected revision and repeatable setup/recovery | Deployed application revision `65c0e4914d18` on the separate **$6/month DigitalOcean host** serves [chat](https://civic.lwdgyasteri.com/ask) and [research](https://civic.lwdgyasteri.com/research). DNS, normal TLS chain/hostname verification, production health and one real public cited model answer passed. Seven sources/eight chunks/eight vectors survived restart and recreation; an isolated backup/restore matched integrity, source/version fingerprints and vector bytes. [Hosted receipt](newark-hosted-check.json), [recovery receipt](newark-recovery-check.json) and [setup](../../deploy/civic/README.md) retain the scope. This is no load or security certification. Rust/NATS are not running in this first direct-import implementation. |
| Real peer supported/missing-evidence tasks, useful change and retest | Pending human reviewer/date/task/issue/decision/change/retest. Do not fill from generated roleplay. |

## Reviews, record and submission

| Stage, 2026 Eastern | Required outcome and present boundary |
| --- | --- |
| Plan — November 17, 1 p.m. | Research, alternatives, architecture/sources/questions/hosting plan; hosted application optional. Current support pages help the plan but do not complete learner verification or submission. |
| Build — November 24, 1 p.m. | Hosted portfolio foundation and real small import → retrieval → chat journey. Real import, embeddings, retrieval and public cited generation are observed over HTTPS. The professional portfolio foundation remains pending. |
| Checked Release — December 3, 1 p.m. | Local import repeatability, references, five-query evaluation and full checks have evidence above. Hosted operation, restart persistence, isolated backup/restore and the deployed revision/setup now have evidence. Human claim review and any remaining portfolio requirements stay pending; this is not a declaration that the whole Release stage is complete. |
| Improve — December 10, 11:59 p.m. | Actual peer feedback, meaningful changes, retests and final case studies/evidence. Pending. |
| Demo Day — December 18, 8:30 a.m. | Explanation using current Improve links; required individual PowerPoint and separate team deck. Delivery specifics remain in Canvas. |

Keep the exact two individual headings and a source/comparison/decision/check
index in the [combined record](https://y-just-y.github.io/is373_ci_cd/). Under each,
include changed/checked/next, revision/date, local/CI/hosted labels, help received
and actual contribution. Show an original source → representation → retrieval →
answer trace; separate source facts, assumptions, plans and observed outputs.
Capture real workshop feedback and its decision in the existing workflow.

The group content system is Deliverable 3 in its own shared record/review; this
Newark import does not establish group contributions. Existing November 6 Studio
scope/rubrics are unchanged. Project reviews use Complete, Thoughtful, Checked
and Understood, 25 points each. This checklist awards no points and does not
submit anything to Canvas. Local technical results do not complete the remaining
portfolio, learner-verification, human-peer, private-reflection, Canvas
submission or individual-PowerPoint requirements.
