# DEV-020 — Shared UX Hardening

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Audit Standard](#audit-standard)
- [Route and State Matrix](#route-and-state-matrix)
- [Commit 1 — Establish the Cross-Application Audit Baseline](#commit-1--establish-the-cross-application-audit-baseline)
- [Commit 2 — Harden the Application Shell and Route Experience](#commit-2--harden-the-application-shell-and-route-experience)
- [Commit 3 — Standardize Request, Form, and Mutation Feedback](#commit-3--standardize-request-form-and-mutation-feedback)
- [Commit 4 — Complete Keyboard and Focus Behavior](#commit-4--complete-keyboard-and-focus-behavior)
- [Commit 5 — Complete Responsive and Visual Accessibility](#commit-5--complete-responsive-and-visual-accessibility)
- [Commit 6 — Complete the Manual Audit and Verification](#commit-6--complete-the-manual-audit-and-verification)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after that commit is implemented, committed, and its gate
passes.

|                  | Commit                                                            | Title                                      | Depends on                 |
| ---------------- | ----------------------------------------------------------------- | ------------------------------------------ | -------------------------- |
| &#91;&#160;&#93; | [1](#commit-1--establish-the-cross-application-audit-baseline)    | Establish audit baseline                   | DEV-012, 015, 018, and 019 |
| &#91;&#160;&#93; | [2](#commit-2--harden-the-application-shell-and-route-experience) | Harden shell and routes                    | Commit 1                   |
| &#91;&#160;&#93; | [3](#commit-3--standardize-request-form-and-mutation-feedback)    | Standardize state feedback                 | Commit 2                   |
| &#91;&#160;&#93; | [4](#commit-4--complete-keyboard-and-focus-behavior)              | Complete keyboard and focus behavior       | Commit 3                   |
| &#91;&#160;&#93; | [5](#commit-5--complete-responsive-and-visual-accessibility)      | Complete responsive and visual behavior    | Commit 4                   |
| &#91;&#160;&#93; | [6](#commit-6--complete-the-manual-audit-and-verification)        | Complete audit and repository verification | Commits 1–5                |

## Objective

DEV-020 is the application-wide hardening pass for the V1 user experience. Earlier
feature PRs made their own screens usable. This task checks those screens together,
closes inconsistencies between them, and proves that the complete application works
with a keyboard and from a 320 CSS-pixel mobile viewport through desktop layouts.

The work covers the public home, signup, and login routes plus every protected V1
workflow: dashboard lists and statistics, entry creation and editing, entry details,
check-in, resolved-comment editing, and opportunity-cost settings. Each route must
explain what is happening during initial loading, empty results, validation failure,
session expiry, inaccessible or missing resources, server failure, retry, background
refresh, mutation progress, and confirmed success whenever that state applies.

This task does not redesign the product or move server-owned rules into React. It
reuses feature components when they already behave consistently and introduces a
shared primitive only when the audit proves that multiple features need the same
semantics or interaction.

## Audit Standard

The target is WCAG 2.2 AA for the V1 workflows, with particular attention to:

- one clear page-level heading and logical nested headings;
- `header`, `nav`, and `main` landmarks with a working skip link;
- native controls, programmatic names, descriptions, and error associations;
- visible focus, logical keyboard order, deliberate focus movement, and no keyboard
  trap except a correctly managed open modal;
- useful `status` and `alert` announcements without announcing the same event twice;
- information and actions that do not rely on color, position, hover, or motion alone;
- readable text and controls with AA contrast in normal, hover, focus, disabled,
  error, and success states;
- interactive targets at least 44 by 44 CSS pixels where the design requires a
  touch target;
- layouts that work at 320 CSS pixels, at 200% browser zoom, and at representative
  tablet and desktop widths without horizontal page scrolling;
- wrapping for long titles, comments, labels, units, email addresses, timestamps,
  validation messages, and maximum supported currency values; and
- behavior that respects `prefers-reduced-motion: reduce`.

Automated accessibility checks are regression protection, not proof of conformance.
Use `jest-axe` where it can detect structural violations, and retain direct Testing
Library assertions for names, descriptions, focus, keyboard interaction, live
regions, and state transitions. The manual matrix is required because layout,
contrast, zoom, screen-reader clarity, and usable focus order cannot be established
by jsdom alone.

## Route and State Matrix

The audit record created in Commit 1 and completed in Commit 6 must cover at least:

| Area                        | Required routes or experiences                                     |
| --------------------------- | ------------------------------------------------------------------ |
| Public and authentication   | Home, signup, login, guest redirects, session restoration          |
| Dashboard                   | Waiting, check-in, saved, purchased, statistics, range selection   |
| Entry management            | Create, detail, edit, delete confirmation                          |
| Check-in and comments       | Check-in choice, stale conflict, success, resolved-comment editing |
| Opportunity-cost management | List, create, edit, delete confirmation                            |
| Application-level fallbacks | Unknown route, lazy-route failure, unexpected render failure       |

For each applicable route, record initial loading, populated, empty, validation,
pending, success, retryable error, expired session, forbidden/not-found, long
content, and background-refresh behavior. Mark a cell `N/A` only with a short reason;
an absent state must not be mistaken for an untested state.

The manual pass uses representative widths of 320, 768, and 1280 CSS pixels and a
desktop pass at 200% zoom. It also includes keyboard-only use, reduced motion, and at
least one screen-reader pass through the primary journey. Record the browser,
assistive technology, operating system, date, result, and any approved deferral.

## Commit 1 — Establish the Cross-Application Audit Baseline

**Status:** Not started.

### In Plain English

Commit 1 creates the checklist and automated safety net for the hardening work. It
lists every route and meaningful state, records which behavior already works, and
turns each genuine gap into work owned by one of the following commits.

It also adds a small automated accessibility test helper and representative baseline
checks. In plain terms, the project gains a repeatable way to catch common problems
such as unnamed controls, invalid ARIA, or broken landmark structure. This first
commit does not claim that an automated scanner can certify accessibility, and it
does not make broad visual changes before the audit identifies what needs repair.

Suggested commit message:

```text
Commit 1: Establish the shared UX audit baseline
```

Implement:

- Add a DEV-020 manual audit document containing the route/state matrix, viewport
  matrix, keyboard checks, reduced-motion check, screen-reader check, and issue log.
- Inventory existing shared request states, form feedback, dialogs, landmarks, and
  responsive rules before creating new abstractions.
- Add and configure `jest-axe` for Vitest/Testing Library if it is not already
  available.
- Add a narrow render-and-scan helper that fails on accessibility violations without
  hiding ordinary test assertions.
- Add representative automated checks for the application shell, an authentication
  form, the dashboard, a feature form, and a confirmation dialog.
- Document scanner limitations and keep direct keyboard, focus, and semantic tests.
- Classify findings by critical, serious, moderate, or minor impact and assign each
  actionable finding to Commit 2, 3, 4, or 5.
- Do not suppress an accessibility rule without a documented reason and a focused
  regression test for the intended behavior.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 2 — Harden the Application Shell and Route Experience

**Status:** Not started.

### In Plain English

Commit 2 makes navigation and page structure predictable. No matter which screen a
person opens, they can understand where the page begins, skip repeated navigation,
identify the current page, and receive an explanation instead of a blank screen when
a route or lazy-loaded module fails.

This commit concentrates on the frame around features. It corrects landmarks,
heading structure, skip-link behavior, document titles, route-change focus, and
application-level fallbacks. Feature-specific forms and dialogs remain in the later
commits so this change stays easy to review.

Suggested commit message:

```text
Commit 2: Harden the application shell and route experience
```

Implement:

- Audit the shared page shell for one reachable skip link and correctly named
  `header`, `nav`, and `main` landmarks.
- Ensure every route has one descriptive page-level heading and a logical heading
  hierarchy below it.
- Set a useful document title for each route, including unknown and error routes.
- Move focus deliberately after client-side navigation without stealing focus during
  ordinary updates on the current route.
- Preserve safe return paths through authentication and announce session expiry once.
- Add a useful not-found page with a clear route back into the application.
- Add route error and unexpected-render fallbacks that explain the failure, offer a
  safe retry or navigation action, and avoid exposing stack traces or raw internals.
- Ensure lazy-route loading has an accessible name and cannot become an unexplained
  blank page.
- Add focused shell/router tests for landmarks, titles, skip navigation, route focus,
  unknown routes, import/render failures, recovery, and expired-session redirects.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
make frontend-build
```

## Commit 3 — Standardize Request, Form, and Mutation Feedback

**Status:** Not started.

### In Plain English

Commit 3 makes application feedback consistent. A loading screen says what is
loading, an empty screen is different from a failed request, and an error tells the
user what happened and what they can do next. Existing content stays visible during
a background refresh instead of disappearing.

Forms follow the same pattern as one another: the relevant field explains a local
problem, a summary receives focus after an invalid submission, a server failure is
announced, pending controls prevent duplicate work, and confirmed success is clear.
The commit shares only the small presentation or focus behavior that has genuinely
been repeated; API calls and feature rules stay with their owning features.

Suggested commit message:

```text
Commit 3: Standardize request and form feedback
```

Implement:

- Audit all query-backed routes for distinct initial loading, empty, populated,
  retryable error, and background-refresh behavior.
- Give loading and updating messages specific accessible names and avoid unnecessary
  live-region repetition.
- Make retry controls keyboard reachable, pending-safe, and specific about the
  operation being retried.
- Present forbidden/not-found results as deliberate inaccessible-resource states;
  do not mislabel them as empty lists or retryable server failures.
- Audit every form for labels, help text, required indicators, `aria-invalid`, error
  associations, a focused error summary, pending feedback, and duplicate-submit
  prevention.
- Preserve the exact server-confirmed success behavior for entry, check-in, comment,
  authentication, and opportunity-cost mutations while making announcements
  consistent.
- Treat backend messages as plain text and retain server ownership of authorization,
  money, lifecycle, statistics, and date rules.
- Extract shared status or error-summary behavior only where at least two existing
  features require the same contract.
- Add focused tests for all state distinctions, retry, background refresh, form
  correction, pending behavior, focus placement, and live announcements.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 4 — Complete Keyboard and Focus Behavior

**Status:** Not started.

### In Plain English

Commit 4 proves that every V1 task can be finished without a mouse. A user can move
through links and controls in a sensible order, open and close disclosures, submit
forms, correct errors, confirm or cancel deletion, complete check-in, and return to a
useful place after an action.

The most careful work is around dialogs. When one opens, focus moves inside it and
stays there. Escape and Cancel close it when safe, and focus returns to the control
that opened it. If the triggering item is deleted, focus moves to a sensible surviving
heading or action rather than a DOM node that no longer exists.

Suggested commit message:

```text
Commit 4: Complete keyboard and focus behavior
```

Implement:

- Test the primary journey with Tab, Shift+Tab, Enter, Space, arrow keys where native
  controls require them, and Escape where dismissal is safe.
- Remove clickable noninteractive elements and unnecessary positive `tabindex`
  values; prefer native buttons, links, inputs, radios, and `details`/`summary`.
- Verify the purchased disclosure, range selector, forms, comment editor, check-in
  choices, navigation, and all retry actions by keyboard.
- Make entry and opportunity-cost delete confirmations use the same proven dialog
  behavior where their requirements are identical.
- Move initial focus into each dialog, trap focus while it is open, support safe
  Escape and Cancel behavior, and restore or deliberately relocate focus on close.
- Prevent repeated keyboard, click, and touch activation while a mutation is pending.
- Verify that unsaved-changes prompts do not create a trap or discard work without
  the documented confirmation.
- Ensure success, conflict, removal, and route transitions leave focus at meaningful
  content.
- Add direct interaction tests; do not rely on an automated accessibility scan to
  prove keyboard or focus behavior.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 5 — Complete Responsive and Visual Accessibility

**Status:** Not started.

### In Plain English

Commit 5 makes the same workflows usable on a narrow phone, a zoomed desktop, and a
wide screen. Content wraps instead of forcing sideways scrolling, actions remain
reachable, and controls are large enough to use by touch. Wider screens use space
well without stretching text into unreadably long lines.

It also checks the visual parts of accessibility: readable color contrast, a focus
indicator that is never clipped or hidden, non-color cues for errors and status, and
reduced-motion behavior. This is refinement of the existing interface, not a new
brand or product redesign.

Suggested commit message:

```text
Commit 5: Complete responsive and visual accessibility
```

Implement:

- Audit every route at 320, 768, and 1280 CSS pixels and at 200% desktop zoom.
- Prevent page-level horizontal scrolling while allowing intentionally scrollable
  content to have an accessible name and keyboard access when applicable.
- Keep forms, cards, statistics, definition lists, dialogs, navigation, and action
  groups usable at narrow widths; use wider grids only when space supports them.
- Wrap long and unbroken user content and maximum currency values without hiding
  information or overlapping controls.
- Preserve a readable content width and logical source order at wider breakpoints.
- Verify 44-by-44 CSS-pixel touch targets and adequate spacing for adjacent actions.
- Check text, controls, borders, errors, successes, disabled states, and focus
  indicators for WCAG 2.2 AA contrast.
- Ensure errors, priorities, selection, and status are understandable without color
  alone.
- Ensure focus outlines remain visible and are not clipped by overflow or sticky
  regions.
- Disable nonessential animation and smooth scrolling under
  `prefers-reduced-motion: reduce` without hiding state changes.
- Add stable component assertions for responsive classes/structure where useful;
  record visual layout, zoom, contrast, and touch-target evidence in the manual audit
  rather than pretending jsdom measures rendered geometry.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
make frontend-build
```

## Commit 6 — Complete the Manual Audit and Verification

**Status:** Not started.

### In Plain English

Commit 6 checks the finished application as one product. It runs every automated
quality command, completes the manual route/state and viewport matrices, and records
the evidence. Any critical or serious accessibility problem found here is fixed and
covered before the commit is complete.

This commit is not a placeholder for undocumented cleanup. Its purpose is to prove
that Commits 1–5 work together: the user can move through the primary V1 journey by
keyboard, understand feedback with assistive technology, zoom or resize the layout,
and recover from expected failures without encountering a blank or misleading
screen.

Suggested commit message:

```text
Commit 6: Complete shared UX and accessibility verification
```

Implement:

- Complete every applicable cell in the route/state and viewport matrices.
- Run the primary journey by keyboard: authenticate, create an entry, inspect and
  edit it, complete an eligible check-in, edit a resolved comment, change statistics
  range, manage an opportunity-cost example, and log out.
- Complete the documented screen-reader, 200% zoom, 320-pixel viewport, desktop,
  contrast, touch-target, long-content, maximum-currency, and reduced-motion checks.
- Verify session expiry, forbidden/not-found resources, recoverable server failure,
  retry, and unexpected route/render failure without unexplained blank states.
- Fix and regression-test every unresolved critical or serious issue.
- Record moderate or minor deferrals only with impact, rationale, owner, and a linked
  follow-up task; do not silently mark them passed.
- Update this document's tracker, implementation record, and verification evidence.
- Update the master development tracker only after the DEV-020 PR is merged and its
  acceptance checks pass on the default branch.
- Run the complete repository quality gate.

Commit gate:

```bash
make check
git status --short
```

## Out of Scope

- Login/signup rate limiting, trusted-host and proxy policy, request-size limits,
  security headers, dependency scanning, and broader log redaction belong to DEV-021.
- Production structured logging, readiness behavior, deployment configuration,
  reverse proxy, TLS, backup, and restore guidance belong to DEV-022.
- A real-browser automated smoke suite, its environment lifecycle, and failure
  artifacts belong to DEV-023. DEV-020 may perform manual browser checks but does not
  introduce that suite.
- Final release validation and the operational release checklist belong to DEV-024.
- New product workflows, visual rebranding, native applications, pagination,
  password reset, account deletion, or multi-currency support are not part of this
  hardening pass.
- Backend business rules, API response shapes, authentication authorization, and
  database behavior do not change unless the audit reveals a separately documented
  defect that cannot be fixed safely within frontend semantics or presentation.

## Implementation Record

Complete this section as each commit lands. Record commit hashes, the concrete audit
findings resolved, focused test results, manual evidence, and any approved deferrals.

### Commit Evidence

| Commit | Hash | Result          | Verification |
| ------ | ---- | --------------- | ------------ |
| 1      | —    | Not implemented | —            |
| 2      | —    | Not implemented | —            |
| 3      | —    | Not implemented | —            |
| 4      | —    | Not implemented | —            |
| 5      | —    | Not implemented | —            |
| 6      | —    | Not implemented | —            |

### Manual Audit Evidence

Record the completed audit document path, browsers, operating systems, viewport and
zoom results, keyboard result, screen reader and version, reduced-motion result,
contrast method, date, reviewer, unresolved findings, and linked follow-up tasks.

### Final Verification

Record the final `make check` result, production frontend build result, automated
accessibility test result, and confirmation that the manual audit contains no
unresolved critical or serious issue.
