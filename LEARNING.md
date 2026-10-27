# Conversation evidence

AI-drafted task summary, not a transcript or grade. It may be public. Use actual
short words or labeled paraphrases; disclose help and leave missing responses
pending. The learner reviews, corrects or removes new excerpts before commit/push.
Accuracy approval is not proof of understanding. Label simulated trials explicitly.

**Available conversation context:** October 27, 2026 local setup and APP-001 planning. APP-001 evidence was reviewed and approved by the learner for the public repository.

## APP-001

- Prediction: Learner: “I think it would help residents trust the information because they can see where it came from and how recent it is, and check the source themselves.” The question concerned source and last-updated labels beside statistics.
- Check interpretation: Learner: “It would catch a broken button or a link going to the wrong section. It wouldn’t prove the information is accurate, all the other links work, or the whole site is accessible.” This referred to the primary CTA browser check.
- Browser observation: On the first branded design, learner: “I notice the source and last updated labels, and that it clearly says no live data. That helps residents know what they can trust and what isn’t ready yet.” On the revised design, learner: “the logo and orange stand out first, and the local decisions are easier to find.”
- Keep decision: Keep the revised civic newsroom design. Previously, revise. Learner requested a more attractive logo, archetype/color combination and layout while showing important information. Learner then approved the civic newsroom direction, stronger logo and local information first. After viewing the revision, learner: “i like this version, lets keep it”; the stated reason was the stronger visual identity and easier-to-find local decisions.
- Review: Learner confirmed the summary is accurate and authorized public inclusion, commit and push on October 27, 2026. This confirms record accuracy, not proof of understanding.
- Help/gaps: Learner chose a new identity and a Newark-resident audience with city comparisons. AI proposed Newark Civic Pulse, the promise, Sage archetype, and navy/teal/light style; learner accepted these and the homepage-only plan. API integration, real figures and later account features were explicitly deferred. After the first design, the learner requested revision. AI proposed a civic newsroom layout using charcoal, ivory and orange, a stronger original N mark and local information first while retaining the factual Sage approach; learner approved this direction. AI implemented it and reran the full APP-001 checks (102 tests passed), then visually inspected desktop and mobile layouts. Learner supplied a revised-design observation and keep reason. Learner completed the accuracy review and authorized publication.
- Evidence links / next step: [Issue #1](https://github.com/Y-Just-Y/my-app-studio/issues/1); approved decisions in SPEC.md. PR #2 merged; issue closed; check/windows and final lesson evidence status passed.

## APP-002

- Prediction: Learner: “before logging in it should send them to the login page, after logging in they should be able to see their private dashboard”
- Check interpretation: Learner: “it would catch a bug where logging out only clears the browser cookie, but the old session still works if someone reuses it”. This referred to the passing copied-cookie replay test after logout.
- Browser observation: Learner: “after logging out and clicking member space again, it sends me back to the login page and i cant see the dashboard”.
- Keep decision: Learner: “lets keep it, signup and login worked and after logging out i couldnt get back to the dashboard without logging in again”.
- Review: Learner confirmed the APP-002 summary is accurate and authorized public inclusion, commit and push on October 27, 2026. Approval confirms record accuracy, not understanding.
- Help/gaps: Learner approved signup, login, private dashboard and logout, with new users as regular members. AI connected the prepared security helpers and built the forms/API. Full checks passed: 98 foundation tests, 14 cumulative contracts and 2 Chromium journeys. AI reviewed desktop login and mobile signup rendering. AI explained password hashing, signed expiring cookies and server-side logout revocation. Learner chose keep based on the successful signup/login and post-logout dashboard restriction. Accuracy review approved; public inclusion, commit and push authorized.
- Evidence links / next step: [Issue #3](https://github.com/Y-Just-Y/my-app-studio/issues/3); APP-002 evidence reviewed and published; PR #4 merged, issue #3 closed, final evidence status passed.

## APP-003

- Prediction: Learner: “it should deny access and return 403 forbidden, because being logged in as a regular member doesnt give them admin permission”.
- Check interpretation: Learner: “it would catch a bug where the app keeps using the old admin role from the session, so someone could still access the admin api after being changed back to a regular member”. This referred to the passing same-session member/admin/member API test.
- Browser observation: Learner as a regular member: “it says admin access required and that my account doesnt have permission to open the page, but i can still go back to my dashboard”. After local promotion, learner: “now it says administration and welcomes derrick, i can see the admin page without logging in again”. After downgrade, learner: “it says admin access required again, i cant see the admin page anymore even though im still logged in, but i can still use my dashboard”.
- Keep decision: Learner: “lets keep it, regular members can use the dashboard but cant access the admin page, and changing the role takes effect without having to log out and back in”.
- Review: Learner confirmed the APP-003 summary is accurate and authorized public inclusion, commit and push on October 27, 2026. This confirms record accuracy, not understanding.
- Help/gaps: Learner approved dashboard access for members and admin-only page/API access. AI implemented both routes with the prepared current-database-role guard. AI tests verify direct requests and promotion/downgrade on an existing session. All 118 cumulative tests passed. AI visually reviewed admin desktop/mobile and member denial pages with a disposable isolated database, leaving the learner account unchanged. Member browser observation recorded; promotion and downgrade observations recorded; learner chose keep based on the access restrictions and same-session role updates. Accuracy review approved; publication, commit and push authorized.
- Evidence links / next step: [Issue #5](https://github.com/Y-Just-Y/my-app-studio/issues/5); APP-003 evidence reviewed and approved for publication; PR and CI verification next.
