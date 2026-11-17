# Newark 2026 introduced budget review

November 16, 2026, Eastern. Deployment, timer activation, full local checks and
bounded hosted checks are recorded in the [result receipt](newark-budget-check.json).
The new private backup and separate temporary restore also passed.

## Source and selected coverage

The user supplied the official [City of Newark introduced legal-line budget](https://www.newarknj.gov/DocumentCenter/View/3062/2026-City-of-Newark-Introduced--Legal-Line-Budget-).
It is a 105-page image-only scan: ordinary PDF text extraction returned no
selectable text. AI used local Apple Vision OCR and visually inspected
Poppler-rendered pages **1, 3, 4 and 6**, including the year columns and row labels.
The [reviewed public extract](../../app/data/newark_2026_introduced_budget.json)
retains selected OCR bounding boxes/confidence, raw amount strings and review
provenance. Confidence is extraction metadata; it does not establish correctness
or human peer approval. The other pages are not indexed.

Reviewed PDF SHA-256:
`dd9387451debf0b36c79d84e8d37fcc85466e823d4627bd5f0b04e82ab304474`

## Repeat the bounded local extraction

The optional [macOS Vision helper](review_budget_ocr.swift) reproduces OCR candidates
with page numbers, bounding boxes and confidence. It uses local system frameworks;
it is not installed in the server image or run by the nightly job. The reviewed
PDF is retained privately under ignored `runtime/source-documents/` on the Mac.

```sh
swift docs/research/review_budget_ocr.swift runtime/source-documents/newark-2026-introduced-budget.pdf /tmp/newark-budget-ocr 1 6
```

Compare the OCR candidates with the rendered table columns and row labels before
changing the reviewed extract. OCR alone cannot establish adoption or final approval.

## Figures and status

These are **2026 introduced-budget figures in USD**, from
[PDF page 1](https://www.newarknj.gov/DocumentCenter/View/3062/2026-City-of-Newark-Introduced--Legal-Line-Budget-#page=1),
an unnumbered computation sheet:

| Label | USD |
| --- | ---: |
| Total General Appropriations excluding Reserve for Uncollected Taxes | 880,149,264.94 |
| Reserve for Uncollected Taxes | 20,351,000.00 |
| Total General Appropriations including that reserve | 900,500,264.94 |
| Amount to Be Raised by Taxation in Municipal Budget | 288,267,071.55 |

[PDF page 6, printed Sheet 3](https://www.newarknj.gov/DocumentCenter/View/3062/2026-City-of-Newark-Introduced--Legal-Line-Budget-#page=6),
corroborates the total and reserve under **YEAR 2026**. Page 1 also lists Total
Anticipated Revenues of $612,233,193.39. Its separate $516,705,236.55 taxation
total includes other taxes; it is not the municipal-budget taxation amount above.

**Introduction date is unknown; adoption is not verified.** PDF page 3, printed
Sheet 1, has an unfilled Certification of Adopted Budget. Page 4, Sheet 2, has
blank resolution/approval/hearing dates and recorded-vote fields. The preprinted
approved-budget heading on Sheet 3 is not adoption evidence. The official source
filename identifies this as an introduced budget; this review does not establish
a later adopted total or an exhaustive search for adoption records.

## Import and observed checks

[The adapter](../../app/civic_documents.py) emits two single-chunk documents:
`newark-budget-2026-introduced-summary` and
`newark-budget-2026-introduced-status`. Each carries the introduced status, fiscal
year, relevant labels/units, page references and reviewed PDF hash. Table rows
retain their column context rather than splitting amounts away from labels.

[The explicit CLI](../../civic_budget_import.py) accepts a local PDF or fetches
only the fixed official URL. It bounds response type, bytes and time, disables
redirects, and verifies the full PDF hash. Unknown bytes require review; they do
not trigger automatic OCR or replace reviewed facts. The budget CLI shares the
nonblocking import lock used by nightly and admin imports.

Twenty-one isolated adapter/CLI tests passed with Black/Pylint. Importing the
actual reviewed PDF into a temporary database inserted two sources/two chunks;
reimport reported unchanged two with stable IDs/versions. The initial production
import added those two documents incrementally, preserving the original sources,
eight chunks and accounts, and reached nine sources/ten chunks. Source search
exposed the budget passage, and the 390px local layout had no page overflow.

On November 16, direct automatic PDF requests from both the Mac and server
returned **HTTP 403 with normal TLS verification**. Safari supplied the reviewed
copy for explicit local import. A 403 is a failed refresh: it neither advances
that source's successful verification date nor proves the automatic path works.

## Enabled nightly refresh and actual first result

The [job](../../deploy/civic/refresh/README.md) checks the fixed council
feed with limit five and this fixed PDF URL at **03:15 America/New_York**, with
up to five minutes of jitter and one active job. The timer was installed,
enabled and active; its next observed time was **November 17, 08:19:13 UTC**.
It makes no model or embedding calls. A changed PDF hash requires review; a failed
source retains its last verified records while a successful council fetch can load.

The first service attempt was manually started to verify the configured nightly
job; no calendar-triggered execution has yet been observed. It completed at **November 16, 22:13:53 Eastern**
with status **partial**, not an all-source success. Council returned five
documents: one inserted and four unchanged. Budget fetching failed; the separate
normal-TLS diagnostic returned HTTP 403. The job preserved the budget facts and
ended with ten sources/eleven chunks. Its nonzero service exit exposes the partial
result instead of hiding it as a successful refresh.

At job completion, eight of eleven chunks had compatible vectors and the job had
made zero provider requests. A later **explicit embedding step indexed three
chunks and reused eight**, producing eleven compatible 1,536-dimensional
`text-embedding-3-small` vectors. The job receipt's earlier 8/11 count and the
later current 11/11 count describe different moments. Future changed chunks still
need the explicit manual embedding command.

## Deployed checks and limits

The full local check passed Black/Pylint, **268 unit/integration tests, 18 lesson
contracts and three actual Chromium journeys**. Thirty-three isolated status
policy cases and four HTTP/UI cases cover introduced/adopted fiscal years,
negations, cited-source status, an unsupported approved-total request and a
deliberately false mocked answer carrying a valid citation. An independent AI
review found a resolution-wording bypass; the cited-budget guard and its
regression were fixed before this full run. These are bounded checks, not proof
that every generated claim is correct.

Application revision `69b721007e0b6276a8f80f5fc8a81e7084ac9dbc` was deployed;
its [Linux/Windows CI](https://github.com/Y-Just-Y/my-app-studio/actions/runs/44008090006)
passed. The [hosted receipt](newark-budget-check.json) records seven public HTTPS
routes returning 200 with certificate/hostname verification, anonymous import
denied with 401 and chat without CSRF denied with 403. Existing accounts, original
chunks and proxy configuration were preserved; no new cloud resources were created.

One real public `gpt-5-mini` answer returned the introduced total of
**$900,500,264.94 USD**, citing `newark-budget-2026-introduced-summary-v1-001`.
The separate approved-total request was refused by the deterministic adoption
guard with `model: null`. Hybrid retrieval still embedded that question; its
generation request was skipped. These are **one generated answer and one guard refusal**,
not two generated answers or a general accuracy measurement. Actual human peer
review remains separate.

The new private backup and separate temporary restore passed database integrity
checks. Source/chunk/version fingerprints and vector bytes matched, including
eleven indexed 1,536-dimensional vectors. The live database was not replaced;
the temporary restore was removed and the backup remains private.

The November 10 `newark-results.md` and `newark-results.json` remain immutable:
this new corpus is not a rerun of their five-question experiment.
