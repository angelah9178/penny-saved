# DEV-020 Manual UX and Accessibility Audit

## Purpose

This document is the human-review checklist and issue log for DEV-020. Automated
`jest-axe` tests can detect some markup problems, but they cannot prove that keyboard
order, focus placement, screen-reader wording, contrast, zoom, or responsive layouts
are usable. Complete those checks here.

Commit 1 establishes this baseline. Commits 2–5 resolve confirmed findings. Commit 6
reruns and completes every applicable check. Do not mark an item as passing without
performing the described check.

## Result Key

| Result    | Meaning                                                      |
| --------- | ------------------------------------------------------------ |
| Pass      | Checked with the recorded environment and no issue found     |
| Issue     | Checked and recorded in the issue log                        |
| Pending   | Required but not manually checked yet                        |
| Automated | Baseline automated scan passes; manual checks remain         |
| N/A       | The state cannot occur; the reason must be recorded in Notes |

## Test Environment

Complete these fields for every manual audit session.

| Field                         | Value |
| ----------------------------- | ----- |
| Reviewer                      | —     |
| Date                          | —     |
| Commit                        | —     |
| Operating system              | —     |
| Browser and version           | —     |
| Screen reader and version     | —     |
| Input methods                 | —     |
| Reduced-motion setting        | —     |
| Contrast-checking method/tool | —     |

## Route and State Checklist

For every route, inspect each applicable state. “Automated” means only that Commit
1's representative markup scan passes; it does not replace the pending manual work.

| Route or experience                   | Loaded    | Loading / refresh | Empty   | Validation / pending | Error / retry | Auth / unavailable | Success | Notes                                          |
| ------------------------------------- | --------- | ----------------- | ------- | -------------------- | ------------- | ------------------ | ------- | ---------------------------------------------- |
| `/` home                              | Automated | N/A               | N/A     | N/A                  | Pending       | N/A                | N/A     | Static route; verify route fallback separately |
| `/signup`                             | Automated | Pending           | N/A     | Pending              | Pending       | Pending            | Pending | Baseline scan represented by `AuthForm`        |
| `/login`                              | Automated | Pending           | N/A     | Pending              | Pending       | Pending            | Pending | Baseline scan represented by `AuthForm`        |
| Session restoration and guest guard   | Pending   | Pending           | N/A     | N/A                  | Pending       | Pending            | Pending | Includes safe return path                      |
| `/dashboard` entries                  | Automated | Pending           | Pending | N/A                  | Pending       | Pending            | Pending | Baseline scan covers loaded empty response     |
| `/dashboard` statistics               | Automated | Pending           | Pending | N/A                  | Pending       | Pending            | Pending | Check all five range selections                |
| `/entries/new`                        | Automated | N/A               | N/A     | Pending              | Pending       | Pending            | Pending | Baseline scan represented by `EntryForm`       |
| `/entries/:id`                        | Pending   | Pending           | N/A     | N/A                  | Pending       | Pending            | N/A     | Include waiting and resolved entries           |
| `/entries/:id/edit`                   | Pending   | Pending           | N/A     | Pending              | Pending       | Pending            | Pending | Include unsaved-changes prompt                 |
| Entry deletion                        | Pending   | N/A               | N/A     | Pending              | Pending       | Pending            | Pending | Check trigger removal and focus destination    |
| `/entries/:id/check-in`               | Pending   | Pending           | N/A     | Pending              | Pending       | Pending            | Pending | Include stale `409` conflict                   |
| Resolved-comment editing              | Pending   | Pending           | N/A     | Pending              | Pending       | Pending            | Pending | Include blank and 4,000-character comments     |
| `/settings/opportunity-costs`         | Pending   | Pending           | Pending | Pending              | Pending       | Pending            | Pending | Include duplicate and long labels              |
| Opportunity-cost deletion dialog      | Automated | N/A               | N/A     | Pending              | Pending       | Pending            | Pending | Baseline scan covers open dialog markup        |
| Unknown route                         | Pending   | N/A               | N/A     | N/A                  | Pending       | N/A                | N/A     | Must not produce a blank screen                |
| Lazy-route or unexpected render error | Pending   | Pending           | N/A     | N/A                  | Pending       | N/A                | Pending | Verify safe recovery and no stack details      |

## Interaction Checklist

Run the primary V1 journey using only the keyboard. Record each issue below rather
than relying on a general impression that the page works.

| Check                                                          | Result    | Notes                                                      |
| -------------------------------------------------------------- | --------- | ---------------------------------------------------------- |
| Skip repeated navigation and reach main content                | Automated | Manual journey remains                                     |
| Traverse controls in a logical visible-focus order             | Automated | Representative routes; complete manual journey in Commit 6 |
| Activate links and buttons with their native keyboard inputs   | Automated | Direct component and route tests                           |
| Operate purchased disclosure and statistics range selector     | Automated | Enter, Space, Tab, and native select tests                 |
| Submit and correct every form                                  | Automated | Direct keyboard, focus, and correction tests               |
| Open, cycle through, cancel, and confirm each dialog           | Automated | Shared confirmation-dialog tests                           |
| Escape closes dialogs only when safe                           | Automated | Escape is blocked while pending                            |
| Focus returns or moves meaningfully after dismissal/deletion   | Automated | Trigger restoration and surviving notice focus tested      |
| Pending mutations reject repeated keyboard/click activation    | Automated | Keyboard, click, and repeated-activation tests             |
| Unsaved-changes prompt preserves or deliberately discards work | Automated | Focus trap, Escape, stay, and leave paths tested           |

## Screen-Reader and Feedback Checklist

| Check                                                                                | Result  | Notes |
| ------------------------------------------------------------------------------------ | ------- | ----- |
| Page, heading, landmark, and navigation structure is understandable                  | Pending | —     |
| Controls have concise names, descriptions, and state                                 | Pending | —     |
| Required fields and validation relationships are announced                           | Pending | —     |
| Error summary and field errors are understandable without repetition                 | Pending | —     |
| Loading, updating, mutation, session-expiry, and success messages are announced once | Pending | —     |
| Empty content is distinguishable from a failed request                               | Pending | —     |
| Dialog name, description, modal state, and focus behavior are clear                  | Pending | —     |
| Forbidden/not-found and retryable failures suggest an action                         | Pending | —     |

## Viewport, Zoom, and Content Checklist

Repeat relevant routes with realistic and worst-case content.

| Check                                                              | 320 px  | 768 px  | 1280 px | 200% zoom | Notes                                       |
| ------------------------------------------------------------------ | ------- | ------- | ------- | --------- | ------------------------------------------- |
| No page-level horizontal scrolling                                 | Pending | Pending | Pending | Pending   | —                                           |
| Navigation and all actions remain reachable                        | Pending | Pending | Pending | Pending   | —                                           |
| Forms, cards, definition lists, and dialogs do not overlap         | Pending | Pending | Pending | Pending   | —                                           |
| Long and unbroken names, reasons, comments, labels, and email wrap | Pending | Pending | Pending | Pending   | —                                           |
| Maximum supported currency values remain readable                  | Pending | Pending | Pending | Pending   | —                                           |
| Content retains a readable width and logical source order          | Pending | Pending | Pending | Pending   | —                                           |
| Interactive touch targets are at least 44 by 44 CSS pixels         | Pending | Pending | N/A     | N/A       | Desktop pointer layouts recorded separately |

## Visual and Motion Checklist

| Check                                                                                  | Result  | Notes |
| -------------------------------------------------------------------------------------- | ------- | ----- |
| Text and informative graphics meet AA contrast                                         | Pending | —     |
| Controls, borders, focus, error, success, and disabled states meet applicable contrast | Pending | —     |
| Meaning does not depend on color, position, hover, or motion alone                     | Pending | —     |
| Focus indicators remain visible and unclipped                                          | Pending | —     |
| Reduced motion disables nonessential animation and smooth scrolling                    | Pending | —     |

## Automated Baseline

Commit 1 adds `frontend/src/test/accessibility.ts` and representative scans for the
application shell, authentication form, loaded dashboard, entry form, and open
opportunity-cost deletion dialog. Color contrast is intentionally disabled in the
jsdom scan because it has no real layout or computed browser rendering; it remains a
required manual check above.

Do not disable another rule globally. If a rule is genuinely inapplicable, document
the reason here and use the narrowest possible per-test configuration.

| Automated check                       | Baseline result | Manual work still required                         |
| ------------------------------------- | --------------- | -------------------------------------------------- |
| Application shell                     | Pass            | Skip-link operation, focus order, titles, contrast |
| Authentication form                   | Pass            | Validation focus, announcements, keyboard journey  |
| Loaded dashboard                      | Pass            | States, disclosure, refresh, responsive layout     |
| Entry feature form                    | Pass            | Error correction, pending state, zoom/layout       |
| Open opportunity-cost deletion dialog | Pass            | Focus trap/return, Escape, contrast, touch         |

## Baseline Issue Log

Severity meanings:

- **Critical:** prevents a V1 workflow for an affected user or exposes them to
  serious harm; fix immediately.
- **Serious:** creates a major barrier with no reasonable workaround; must be fixed
  before DEV-020 completes.
- **Moderate:** makes a workflow substantially harder but a workaround exists.
- **Minor:** limited inconvenience or clarity problem.

Commit 1's automated baseline found no automatically detectable violations in the
five representative scans. Manual findings are intentionally pending and must be
added to this log as they are discovered.

| ID  | Severity | Route/component | Finding                                  | Reproduction/evidence         | Owner       | Status        |
| --- | -------- | --------------- | ---------------------------------------- | ----------------------------- | ----------- | ------------- |
| —   | —        | —               | No confirmed manual finding recorded yet | Complete the checklists above | Commits 2–5 | Pending audit |

## Deferrals

Do not defer critical or serious findings. Any moderate or minor deferral must name
its impact, rationale, owner, and linked follow-up task.

| Finding ID | Impact | Rationale            | Owner/follow-up | Approval |
| ---------- | ------ | -------------------- | --------------- | -------- |
| —          | —      | No deferral recorded | —               | —        |
