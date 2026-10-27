# App Studio decisions

The durable agreement between learner and AI. Update only agreed decisions and
actual evidence; pending is a valid state. Keep explanations/help in
[LEARNING.md](LEARNING.md), not a second copy here.

## Current stage

- **Current feature:** APP-003.
- **Status:** APP-002 merged in PR #4, issue #3 closed, final evidence status passed. APP-003 implemented locally; learner interpretation, browser observations and keep reason recorded. Accuracy review approved; GitHub completion pending.
- **Next step:** Commit/push approved APP-003 work, open its PR and verify CI before the learner merge decision.
- **Implementation marker:** 3 after explicit cumulative APP-003 checks passed; normal full check also passed.

This repository owns application code. Server/proxy changes and production
deployment are outside these three local-development lessons. Prepared helpers
are reusable foundations, not evidence that unfinished routes are implemented.

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
| Own issue / branch / PR | [Issue #5](https://github.com/Y-Just-Y/my-app-studio/issues/5), `codex/app-003-roles`; PR pending. |

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
| APP-003 | [Issue #5](https://github.com/Y-Just-Y/my-app-studio/issues/5); roles.py, admin.html, forbidden.html | Black/Pylint, 98 foundation tests, 18 cumulative contracts and 2 Chromium journeys passed. Isolated admin desktop/mobile and member forbidden page visually reviewed. | Learner chose keep and approved evidence; PR pending |

The instructor's reference branches show possible implementations. They do not
establish this repository's completion or the learner's own reasoning.
