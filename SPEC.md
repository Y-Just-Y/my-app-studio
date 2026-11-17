# App Studio decisions

The durable agreement between learner and AI. Update only agreed decisions and
actual evidence; pending is a valid state. Keep explanations/help in
[LEARNING.md](LEARNING.md), not a second copy here.

## Current stage

- **Current feature:** Reviewed Newark budget data and nightly selected-source ETL.
- **Status:** APP-003 is present in merged PR #6. The authorized extension has real Newark ETL, SQLite/FTS5, sqlite-vec embeddings, hybrid retrieval and an OpenAI chatbot. Local full checks passed November 10, 2026. Hosted verification and publication are recorded separately below.
- **Next step:** Keep source failures and embedding coverage visible, and collect Juan's actual feedback, detailed task agreement and own group submission. Both Plan entries were verified submitted November 16; the budget/refresh extension is deployed and checked below.
- **Implementation marker:** 3 after explicit cumulative APP-003 checks passed; normal full check also passed.

This repository owns application code. The original three lessons did not include
deployment; the later explicit request authorizes a separate Civic host and
subdomain. Existing Asteri deployment and root-domain records are outside that
extension. Prepared helpers are not evidence that a feature works.

## Professional portfolio · Local draft, November 10, 2026

**Scope:** prioritize the individual deliverables by adding a professional
portfolio at `/portfolio` in the existing FastAPI app. Reuse the combined Plan's
cloud/platform direction and Layout A, with projects and evidence first.
The learner explicitly requested LWDGY ASTERI as another featured project,
covering experience with RAG, CI/CD, Docker and server configuration.

**Draft content:** introduction, Newark Civic Pulse and LWDGY ASTERI featured
cards, Docker/server and account-permission coursework, skill-to-evidence links,
about/profile links, and a clearly planned group-case-study placeholder. RAG/ETL
evidence belongs to Newark. ASTERI supports Docker/server and signed release
workflow evidence. Its private source repository is not offered as public proof.
The current ASTERI gate documentation supersedes older Actions deployment prose.

**Files:** `app/features/portfolio.py`, `app/templates/portfolio.html` and
`app/static/portfolio.css`; router registration in `app/main.py`.

**Review:** The learner confirmed that the proposed introduction accurately
describes them and asked to keep it. That wording is approved. The learner subsequently identified design, server setup, Docker, testing and
release decisions as their work, then clarified ownership of all project work.
The ASTERI page records end-to-end ownership with AI assistance explicit.
Preferred profile/contact links and resume/LinkedIn still need review.
No graduation date, work history or unaided authorship is inferred. AI drafted
the page and the summaries. The learner's November 11 browser observation and
keep decision are recorded below; their November 16 RAG check reason is recorded
in [LEARNING.md](LEARNING.md). Human peer feedback and independent claim
verification remain pending.

**Release record:** Review branch `codex/individual-portfolio` is based on the
checked RAG branch. [Draft PR #8](https://github.com/Y-Just-Y/my-app-studio/pull/8)
and the combined individual record track the current CI and hosted state.
Local previews, repository publication and verified deployment are separate
observations; a draft PR does not establish a merge or peer approval.

**AI checks:** Black/Pylint, 196 unit/integration tests, 18 lesson contracts and
three existing Chromium journeys passed. The new public page returned 200
without an account. Its internal anchors resolved; desktop and 390px mobile
layout were visually inspected with no horizontal overflow. Keyboard navigation
focused the skip link and activated the main content target. These are AI checks.

**Learner review, November 11, 2026 Eastern:** “I clicked the ASTERI case study
and it clearly shows the work I did”. The learner chose to keep it and requested
the Newark group Plan next. This records their own observation and decision.
The November 16 RAG check reason is recorded in [LEARNING.md](LEARNING.md);
Juan's actual feedback and independent claim verification remain pending.

### LWDGY ASTERI case-study draft

The approved introduction remains unchanged. A new local page at
`/portfolio/projects/asteri` covers the jewelry storefront and management
workspace, React/TypeScript/Express/Firebase boundaries, Docker and proxy setup,
and the signed build/test/release flow. The portfolio card links to this page.
Shared layout moved into `app/templates/portfolio_base.html`; case content is in
`app/templates/portfolio_asteri.html` and its page styles in `portfolio.css`.

The evidence brief used the private application's cached November 3 main
snapshot and the release gate's later documentation, rather than treating the
older dirty application checkout's README as current. The October 9 cutover
record documents unsigned-image rejection before state change and successful
signed-image acceptance with matching HTTPS revisions. Counts of 31 host gates,
13 application stages and 106 browser tests are explicitly dated historical
results. A separate October 1 sandbox retry/expiry result is labeled sandbox.
No ASTERI tests, releases or server operations were run to author the case study.

The public-facing summary excludes private repository links, credentials,
operational addresses, trust material and customer/test identifiers. It makes no
claim about present server uptime, measured sales impact, live-payment readiness
or unaided authorship. For the contribution statement, the learner reported handling design, server
setup, Docker, testing and release decisions, then clarified “I did everything.”
The page uses a concise paraphrase of that statement: end-to-end ownership,
including development, with AI assistance acknowledged. This is learner-reported
contribution, not an inference from commit authorship or a claim of unaided work.

**Case-page verification:** The normal full check passed with Black/Pylint,
196 unit/integration tests, 18 lesson contracts and three Chromium journeys.
An earlier existing login journey timed out waiting for navigation after the
server had returned its 303 and dashboard 200; the unchanged targeted journey
and the subsequent complete run both passed. No assertions or timeouts were
weakened. Anonymous portfolio/case requests returned 200 with the existing CSP;
the approved introduction remained exact, anchors resolved, and rendered links
contained no private source-repository URLs. Desktop and 390px mobile layouts
were checked with no horizontal overflow, and the keyboard skip link reached
main content. These are portfolio-page checks, not a rerun of ASTERI's historical
release or sandbox acceptance.

## Newark RAG extension · November 10, 2026

**Authorized scope:** replace the Docker-document corpus with public Newark
records, explain and implement ETL/chunking/retrieval, add a testable AI bot,
research primary arXiv papers and the professor's repository, and document actual
results against the existing combined assignment record. A separate DigitalOcean
host is authorized up to $6/month and initial OpenAI usage up to $5.

**Implementation:** `civic_import.py` and `app/civic_etl.py` extract bounded
Legistar JSON, normalize IDs/dates/URLs/metadata, preserve hashes and versions,
split paragraphs at a 1,600-character cap and load `app/civic_store.py`'s separate
SQLite/FTS5 store. `civic_embed.py` explicitly creates model/hash-bound embeddings
through `app/civic_vectors.py`. `app/features/civic.py` combines keyword and
vector rankings and exposes `/ask`, source search and protected ingestion.
`app/civic_ai.py` supplies bounded structured OpenAI answers and validates citation
IDs. Rust, NATS and native graph storage are deferred with reasons in the research.

**Observed data:** seven sources/eight chunks, five recent meetings and two
selected November 5 agenda items. Repeat import returned seven unchanged. Two
expired original meeting pages were replaced by verified same-ID official API
references, with original URL/status retained. All eight current chunks have real
`text-embedding-3-small` vectors at 1,536 dimensions. No account data is imported.

**Actual checks:** Black/Pylint and 196 unit/integration tests, 18 APP-003
contracts and three Chromium journeys passed. The frozen five-question run saved
actual retrieval ranks, context, model answers and citation support reviews.
Keyword and hybrid each covered all expected source sets for 4/4 supported
questions; vector alone did for 3/4. The budget question was refused. Paragraph
and fixed 1,600-character boundaries both yielded eight chunks and preserved five
schedule spans; no advantage was observed. See [results](docs/research/newark-results.md).

**Boundary:** this is an anonymous public-record snapshot, not a complete calendar
or proof of ordinance adoption. Fixture tests, AI inspection, real model results,
hosted operation and Derrick's own explanation are distinct evidence. The
[requirement map](docs/research/newark-requirements.md) keeps personal reflection,
human peer feedback, portfolio implementation and Canvas submission pending.

**Hosted result:** [chatbot](https://civic.lwdgyasteri.com/ask) and
[research](https://civic.lwdgyasteri.com/research) are public over verified HTTPS
on the separate $6/month host. Deployed application revision `65c0e4914d18`
preserves seven sources/eight chunks/eight vectors after restart. One actual
public AI question returned the correct listed time/location and source citation;
anonymous ingestion returned 401 and missing-CSRF chat returned 403. A private
SQLite backup and separate temporary restore matched integrity, source/version
fingerprints and vector bytes. See the
[public request receipt](docs/research/newark-hosted-check.json) and
[recovery receipt](docs/research/newark-recovery-check.json). The user's latest
scope keeps the chatbot focused on Newark data; research explanations remain on
the research page. Existing Asteri services and DNS records were left intact.

## Reviewed budget and automatic source checks · November 16, 2026

**Scope:** the learner supplied Newark's official 2026 introduced-budget PDF and
requested searchable budget data, populated website figures and automatic source
checks. This extension uses the existing separate Civic host and public sources;
it adds no paid infrastructure. AI assistance in extraction, code and checks is
explicit. These changes are individual prototype work, not completed group work.

**Representation:** the 105-page image scan has no selectable text. Local OCR and
visual inspection produced a reviewed, SHA-256-bound extract covering selected
facts on PDF pages 1, 3, 4 and 6. Two short passages keep year, introduced status,
USD, distinct monetary definitions and page references together. Introduction
date is unknown; blank certification templates do not establish adoption.
The four summary figures are $880,149,264.94 excluding reserve, $20,351,000.00
reserve, $900,500,264.94 including reserve and $288,267,071.55 municipal-budget
taxation. The remaining budget pages are not indexed.

**Refresh:** a separate server job checks at most five council records and the
fixed budget URL around 3:15 a.m. America/New_York. A shared OS writer lock prevents
overlap. Successful sources update versioned FTS5 passages; failed sources keep
their prior records and verification dates. A changed budget scan requires a
new reviewed extract. Nightly runs contain no API key and make no paid embedding
or generation calls. Semantic coverage is shown independently and refreshed only
by the explicit embedding command.

**Current source-access limit:** normal TLS-verified requests to the PDF returned
403 on both Mac and Civic host. The official PDF was saved through Safari and
verified locally. This permits the initial checked import, not a claim that
unattended PDF access works. The public refresh status must expose partial or
failed checks without making the saved budget look newly verified.

**Checks and release:** Black/Pylint, 268 unit/integration tests, 18 cumulative
APP-003 contracts and three actual Chromium journeys passed November 16. The
budget status checks include a false approved claim with a valid citation and
the resolution-wording bypass found during independent AI review. Desktop and
390px mobile review found no page overflow; source search returned the reviewed
table passage. Application revision `69b7210` is deployed with both Linux/Windows checks passed.
The initial two-source budget import preserved accounts and the original chunks.
The enabled nightly job added one council record and reported a partial result
for the blocked budget fetch. After one explicit embedding import, the live
corpus has ten sources, eleven chunks and eleven compatible vectors. One actual
introduced-total generation and one deterministic approved-total refusal passed;
a separate backup/restore matched the new source/chunk versions and vector bytes.
See [hosted extension receipt](docs/research/newark-budget-check.json).
The original November 10 evaluation remains unchanged. See
[budget methods and results](docs/research/newark-budget.md) for this separate
corpus extension and its actual validation boundary.

## APP-001 · Branded homepage

**Scope:** make the neutral FastAPI homepage express one chosen identity with
a simple original SVG mark, coherent copy, navigation and shared style tokens.
Keep account actions honest about their unfinished state. Approved previews cover local decisions, public funding/debt context, deadlines, symbolic conditions clock and city comparisons. No live APIs, verified events, risk method or numerical figures are supplied in APP-001. Leaders, official department links and news remain future scope.

| Decision | Agreement |
|---|---|
| Visitor and concrete use situation | Newark resident understanding local decisions, with city comparisons for context. |
| Reused IS117 brand, or name / promise / primary archetype | New identity: Newark Civic Pulse. “Understand your city. Compare the context. Know what’s next.” Sage archetype. |
| One visible choice and visitor benefit | Source/update labels support checking provenance and freshness. Approved civic newsroom direction: charcoal, warm ivory and orange; stronger architectural N mark; local decisions, deadlines and public money first, with a smaller conditions clock. Previews clearly disclose no live data. |
| Own issue / branch / PR | [Issue #1](https://github.com/Y-Just-Y/my-app-studio/issues/1), `codex/app-001-civic-pulse`; [merged PR #2](https://github.com/Y-Just-Y/my-app-studio/pull/2). |

**Keep when:** the agreed identity is visible and usable at desktop/narrow widths;
full foundation + APP-001 checks pass; AI review and the learner's actual check
interpretation/browser observation/keep reason are recorded; reviewed evidence
and verified GitHub state are linked below.

## APP-002 · Signup, login and logout

**Scope:** add browser forms and REST behavior for member signup, login, a private
dashboard and logout backed by SQLite. Reuse the prepared password/JWT/CSRF/session
helpers; keep data local. New accounts cannot choose their role.

| Decision | Agreement |
|---|---|
| Expected public/private behavior and account flow | Signup, login, private dashboard and logout. New accounts are regular members. Anonymous dashboard visits redirect to login; authenticated members see their dashboard. |
| Valid and rejected cases to demonstrate | Valid signup/login; reject duplicate/invalid signup, role input, wrong passwords, missing CSRF and revoked sessions. |
| Own issue / branch / PR | [Issue #3](https://github.com/Y-Just-Y/my-app-studio/issues/3), `codex/app-002-accounts`; [merged PR #4](https://github.com/Y-Just-Y/my-app-studio/pull/4). |

**Keep when:** the agreed forms/API work; duplicate/invalid signup and wrong
credentials are rejected; passwords are hashed; authentication uses validated,
expiring JWTs with protected cookies and CSRF; private requests require a live
session and logout revokes it. Full cumulative checks, AI review, actual learner
contributions and GitHub state are recorded. This is not a production-security certification.

## APP-003 · Server-enforced roles

**Scope:** enforce a small member/admin boundary in the API and browser. Assign
roles only through the trusted local terminal command; use current server-side
permissions, including for an existing session after a role change.

| Visitor | Homepage | Member area | Admin area/API |
|---|---|---|---|
| Anonymous | Allowed | Login required | Login required |
| Member | Allowed | Allowed | Forbidden |
| Admin | Allowed | Allowed | Allowed |

| Decision | Agreement |
|---|---|
| Intended admin-only result | Only current admins can open the protected overview at /admin and /api/admin. Anonymous HTML redirects to login, anonymous API returns 401, members receive 403. New signups remain members. |
| Actual allowed/denied request evidence | Cumulative contracts verify anonymous 401, member 403, admin 200 and immediate role downgrade enforcement on existing sessions. |
| Own issue / branch / PR | [Issue #5](https://github.com/Y-Just-Y/my-app-studio/issues/5), `codex/app-003-roles`; [merged PR #6](https://github.com/Y-Just-Y/my-app-studio/pull/6). |

**Keep when:** a direct request cannot bypass the role boundary, role changes
take effect as specified, new signup remains member-only, and full cumulative
checks plus AI review pass. Link the learner's actual interpretation/observation,
reviewed record and verified GitHub result. Hidden navigation alone is insufficient.

## Evidence

Link actual files/checks and the student's own issues/PRs. No fabricated URLs,
customer research or claims that a timestamp proves learning.

| Feature | Files / own issue / PR | Actual checks and learner observations | Kept / GitHub state |
|---|---|---|---|
| APP-001 | [Issue #1](https://github.com/Y-Just-Y/my-app-studio/issues/1); [brand](app/brand.json), [homepage](app/templates/home.html), [shared shell](app/templates/base.html), [styles](app/static/site.css), [logo](app/static/logo.svg) | Black/Pylint passed; 98 foundation/unit tests, 2 APP-001 contracts, 2 Chromium journeys passed. AI reviewed 1440px desktop and 390px mobile layouts; keyboard skip link and primary CTA passed. These checks passed again after the newsroom revision; desktop/mobile visual review also completed. Learner explained the CTA check limits and noticed source/date/no-live-data labels in the first design, then requested revision. Learner noticed the logo/orange first, found local decisions easier to find, and chose to keep the revision. | Kept; PR #2 merged, issue #1 closed, check/windows passed |
| APP-002 | [Issue #3](https://github.com/Y-Just-Y/my-app-studio/issues/3); account routes and templates | Black/Pylint; 98 foundation tests, 14 cumulative contracts and 2 Chromium journeys passed. Desktop login and narrow signup visually reviewed. | Kept; PR #4 merged, issue #3 closed, final evidence status passed |
| APP-003 | [Issue #5](https://github.com/Y-Just-Y/my-app-studio/issues/5); [PR #6](https://github.com/Y-Just-Y/my-app-studio/pull/6); roles.py, admin.html, forbidden.html | Black/Pylint, 98 foundation tests, 18 cumulative contracts and 2 Chromium journeys passed. Isolated admin desktop/mobile and member forbidden page visually reviewed. | Learner chose keep and approved evidence; merged PR #6 |

The instructor's reference branches show possible implementations. They do not
establish this repository's completion or the learner's own reasoning.
