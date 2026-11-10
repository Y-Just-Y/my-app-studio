# Newark civic RAG: executed local evaluation

Machine-readable evidence: [newark-results.json](newark-results.json).
Frozen question expectations precede model calls. This is AI-reviewed local
evidence, not human peer feedback, instructor grading or hosted availability.

Run phase: **completed**. Models: `gpt-5-mini`
and `text-embedding-3-small` (1536 dimensions).
Actual attempted calls: 5 query embedding,
5 generation. No automatic retries.

| Question | Keyword required-source coverage@5 | Vector coverage@5 | Hybrid coverage@5 | Evidence-review status |
| --- | --- | --- | --- | --- |
| Q1 | 100% | 100% | 100% | supported_with_wording_note |
| Q2 | 100% | 100% | 100% | supported_with_wording_note |
| Q3 | 100% | 50% | 100% | supported |
| Q4 | 100% | 100% | 100% | supported |
| Q5 | Not applicable | Not applicable | Not applicable | adequate_insufficient_evidence |

Five questions over seven sources/eight chunks. Hybrid restored Q3 coverage missed by vector-only search, but did not outperform keyword source coverage in this set.

## Q1: exact-term

What scheduled time and location are listed for the Newark Municipal Council meeting on November 5, 2026?

The meeting is scheduled for 12:30 PM (America/New_York) at the Council Chamber.

- [newark-meeting-302232-v1-001](https://newark.legistar.com/MeetingDetail.aspx?LEGID=302232&GID=7&G=76B7E664-B393-4911-9914-3B4B31917701)

AI evidence judgment: The cited November 5 record lists 12:30 PM America/New_York and Council Chamber, matching the answer. Present-tense wording could sound upcoming; prefer “the record lists” because the question concerns a past dated record.

## Q2: paraphrase

For the council session dated November 5, 2026, where were residents told to go, and what local clock time was listed?

Residents were directed to the Council Chamber. The listed local time was 12:30 PM (America/New_York).

- [newark-meeting-302232-v1-001](https://newark.legistar.com/MeetingDetail.aspx?LEGID=302232&GID=7&G=76B7E664-B393-4911-9914-3B4B31917701)

AI evidence judgment: The location and clock time match the cited record. “Residents were directed” is stronger than the stored location field; prefer “the record lists Council Chamber.” No attendance or occurrence claim was verified.

## Q3: relationship

Which council meeting listed ordinance 26-0816, and what was that meeting's scheduled start time?

Ordinance 26-0816 was listed on the Newark Municipal Council meeting of 2026-11-05, which was scheduled to start at 12:30 PM (America/New_York).

- [newark-meeting-302232-v1-001](https://newark.legistar.com/MeetingDetail.aspx?LEGID=302232&GID=7&G=76B7E664-B393-4911-9914-3B4B31917701)
- [newark-agenda-517475-v1-001](https://newark.legistar.com/MeetingDetail.aspx?LEGID=302232&GID=7&G=76B7E664-B393-4911-9914-3B4B31917701)

AI evidence judgment: The item record links ordinance 26-0816 to November 5 and the meeting record lists 12:30 PM. Both required records are cited; the answer describes listing/scheduling without inferring a vote or passage.

## Q4: comparison

Were the November 5, 2026 and October 21, 2026 Newark council sessions scheduled at the same local time? State both listed times.

No. The November 5, 2026 session was scheduled for 12:30 PM America/New_York; the October 21, 2026 session was scheduled for 6:30 PM America/New_York.

- [newark-meeting-302232-v1-001](https://newark.legistar.com/MeetingDetail.aspx?LEGID=302232&GID=7&G=76B7E664-B393-4911-9914-3B4B31917701)
- [newark-meeting-302231-v1-001](https://newark.legistar.com/MeetingDetail.aspx?LEGID=302231&GID=7&G=76B7E664-B393-4911-9914-3B4B31917701)

AI evidence judgment: The cited November 5 and October 21 records list 12:30 PM and 6:30 PM respectively. The answer preserves the dates, identifies the difference and labels local scheduled times.

## Q5: unanswerable

What is the total approved City of Newark budget for 2026 in dollars?

I cannot find the City of Newark’s approved 2026 budget amount in the supplied records. The imported items are meeting agendas/dates and do not state a total budget figure.


AI evidence judgment: No total approved 2026 budget amount appears in the supplied context. The model returns insufficient_evidence=true, no invented dollar amount and no citation IDs; this establishes nothing about the actual city budget.

## Source-link checks

- HTTP 200: [newark-agenda-517475](https://newark.legistar.com/MeetingDetail.aspx?LEGID=302232&GID=7&G=76B7E664-B393-4911-9914-3B4B31917701)
- HTTP 200: [newark-meeting-302227](https://newark.legistar.com/MeetingDetail.aspx?LEGID=302227&GID=7&G=76B7E664-B393-4911-9914-3B4B31917701)
- HTTP 410: [newark-meeting-302228](https://newark.legistar.com/MeetingDetail.aspx?LEGID=302228&GID=7&G=76B7E664-B393-4911-9914-3B4B31917701)
- HTTP 410: [newark-meeting-302230](https://newark.legistar.com/MeetingDetail.aspx?LEGID=302230&GID=7&G=76B7E664-B393-4911-9914-3B4B31917701)
- HTTP 200: [newark-meeting-302231](https://newark.legistar.com/MeetingDetail.aspx?LEGID=302231&GID=7&G=76B7E664-B393-4911-9914-3B4B31917701)

## Executed chunk-boundary comparison

At equal 1600-character caps and zero overlap, the paragraph method produced 8 chunks and fixed windows produced 8. The complete date/time/location span stayed together in 5/5 meeting records with paragraph splitting and 5/5 with fixed windows.
These observations establish no retrieval/answer-quality advantage. The sources were short; tokenizer-aware and broader quality experiments remain open.

## Limits and next check

Seven public sources/eight chunks are a small recent-record snapshot.
Nearest neighbors may be irrelevant; missing budget data cannot establish
a budget amount. Source ID validity alone does not establish answer support.
This run uses hybrid context for generation; it does not compare generated
answer quality across all retrievers. Dollar spend and latency were not measured.
Required-source coverage@5 is not precision: irrelevant retrieved passages can remain even when every required source is present.
Chunk comparison uses equal 1600-character caps, not tokenizer tokens; inspect
the JSON boundary experiment before claiming a quality difference.
A human peer, an expanded question set and hosted end-to-end checks remain necessary.

## Post-evaluation source-link repair

On November 10, 2026, the importer verified the original meeting-page links
before loading. The two original 410 responses recorded above remain part of
the frozen evaluation evidence. After verifying HTTP 200 and matching record
identity/date in the official API, the current catalog now uses:

- [October 6 record / Event 302228](https://webapi.legistar.com/v1/newark/events/302228),
  current chunk `newark-meeting-302228-v2-001`.
- [October 13 record / Event 302230](https://webapi.legistar.com/v1/newark/events/302230),
  current chunk `newark-meeting-302230-v2-001`.

Original page URL, original HTTP status and link-check time are preserved in
source metadata. The last repair verification was
`2026-11-10T19:00:20.078116+00:00`. Other original links that returned 200 were
preserved. A redirect, access failure or transient outage does not authorize a
different citation target; a mismatched fallback record aborts the import.

The first repair import reported **2 updated / 5 unchanged**; the next reported
**7 unchanged**, retaining **7 sources / 8 chunks**. The two changed chunks were
re-embedded, leaving **8 current compatible embeddings at 1536 dimensions**.
Every URL actually cited by Q1–Q4 returned 200; those cited records did not need
replacement. This note preserves the original five-question receipt and does
not claim a newly executed answer-quality comparison after the repair.

## Public pilot and persistence check

The seven-source/eight-chunk/eight-vector app is now served over verified HTTPS
at [Ask Newark](https://civic.lwdgyasteri.com/ask), with methods at
[Research](https://civic.lwdgyasteri.com/research). One real public hybrid/model
question returned the November 5 record's scheduled 12:30 PM, Council Chamber
and expected citation. It is a separate hosted smoke check, not a rerun of this
five-question comparison. [Request evidence](newark-hosted-check.json) retains
the answer and boundary checks.

An ordinary restart/container recreation preserved the corpus and vector index.
A consistent SQLite backup, restored into a distinct temporary database,
matched integrity, source/version fingerprints, mapping hashes and vector bytes;
the live database was not replaced during the recovery test.
[Recovery evidence](newark-recovery-check.json) retains the result. Human peer
review and broader answer-quality testing remain pending. The chatbot's scope is
Newark data only; research explanations remain on the research page.
