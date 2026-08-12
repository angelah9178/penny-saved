# DEV-024 Manual Acceptance Checklist

## Purpose

Automation has checked markup, keyboard event behavior, focus management, route titles,
live regions, production builds, the complete browser journey, rendered 320-pixel
overflow and touch targets, skip-link focus, and reduced-motion CSS. A human must
complete the checks below because they require perception, listening, or judgment.

Do not enter `Pass` unless you personally performed the step. Use `Issue` for a problem
and describe it in the findings table. Serious or critical issues block release.

## Test Record

| Field                     | Value                                            |
| ------------------------- | ------------------------------------------------ |
| Reviewer                  | User reviewer                                    |
| Date                      | 2026-08-12                                       |
| Commit                    | `cdf8d67` baseline plus Commit 4 working changes |
| Operating system          | Checked by reviewer; version not recorded        |
| Browser and version       | Checked by reviewer; version not recorded        |
| Screen reader and version | Checked by reviewer; version not recorded        |
| Input method              | Physical keyboard                                |

## 1. Keyboard and Visible Focus

1. Start the production preview through the documented local workflow and log in with
   the local demo account.
2. Put the mouse aside. Press `Tab` from the top of each route.
3. Confirm “Skip to main content” appears, pressing `Enter` moves focus to the main
   content, and every later focus indicator is easy to see and never clipped.
4. Complete entry creation, entry editing, check-in, statistics range selection,
   opportunity-cost editing/deletion, dialogs, and logout using only `Tab`,
   `Shift+Tab`, arrow keys, `Enter`, `Space`, and `Escape`.
5. Confirm the order follows the visual/logical reading order, dialogs keep focus
   inside, `Escape` behaves safely, and closing a dialog returns focus meaningfully.

| Check                                           | Result | Notes          |
| ----------------------------------------------- | ------ | -------------- |
| Full journey is practical without a mouse       | Pass   | User confirmed |
| Focus order is logical and indicators are clear | Pass   | User confirmed |
| Dialog focus trap/return feels correct          | Pass   | User confirmed |

## 2. Screen Reader

Use one real combination, such as NVDA with current Firefox/Chrome on Windows,
VoiceOver with Safari on macOS, or Orca with Firefox on Linux.

1. Turn on the screen reader before opening the application.
2. Navigate by landmarks and headings. Confirm page names, heading levels, and regions
   make the page understandable without looking at it.
3. Complete signup/login, create an entry, cause and correct validation errors, check
   in an eligible entry, change statistics range, edit an opportunity-cost example,
   open/cancel/confirm a dialog, and log out.
4. Listen for loading, errors, success, updating, session expiry, and empty-state
   messages. Confirm each useful message is announced once and does not expose a stack
   trace, token, database detail, or other secret.
5. Confirm controls have concise names and state, required/error relationships make
   sense, and empty content cannot be mistaken for a failed request.

| Check                                                | Result | Notes          |
| ---------------------------------------------------- | ------ | -------------- |
| Landmarks/headings provide an understandable outline | Pass   | User confirmed |
| Controls and validation are understandable           | Pass   | User confirmed |
| Status/error/success messages are announced clearly  | Pass   | User confirmed |
| Critical journey is practical with the screen reader | Pass   | User confirmed |

## 3. Zoom, Reflow, and Content

1. In the browser, set zoom to exactly 200% using its menu or `Ctrl/Cmd` and `+`.
2. At 200%, repeat the dashboard, longest entry/detail form, statistics, settings, and
   an open confirmation dialog. Do not substitute CSS zoom or browser automation.
3. Resize to approximately 320 CSS pixels wide (or use a real narrow mobile device).
4. Confirm no page-level horizontal scrolling, overlap, clipped content, unreachable
   action, or obscured focused control appears.
5. Inspect long email/item/reason/comment/label text and the maximum supported currency
   display. Confirm wrapping remains readable and source order still makes sense.

| Check                                             | Result | Notes          |
| ------------------------------------------------- | ------ | -------------- |
| 200% zoom remains usable without lost content     | Pass   | User confirmed |
| Narrow/mobile layout is understandable and usable | Pass   | User confirmed |
| Long content and maximum currency remain readable | Pass   | User confirmed |

## 4. Contrast, Color, and Motion

1. Use browser developer tools or a WCAG contrast checker on normal text, muted text,
   buttons, links, errors, success messages, borders, disabled controls, and focus
   indicators. Confirm normal text is at least 4.5:1, large text at least 3:1, and
   meaningful non-text UI/focus boundaries at least 3:1 against adjacent colors.
2. Confirm error, success, disabled, selected, and focus states are understandable
   without color, hover, position, or motion alone.
3. Enable the operating system's “reduce motion” preference, reload, navigate, open
   dialogs, and submit forms. Confirm nonessential animation and smooth scrolling are
   absent while state changes remain understandable.

| Check                                        | Result | Notes          |
| -------------------------------------------- | ------ | -------------- |
| Text and meaningful UI contrast meet WCAG AA | Pass   | User confirmed |
| Meaning does not depend on color alone       | Pass   | User confirmed |
| Reduced-motion experience feels appropriate  | Pass   | User confirmed |

## 5. Human Clarity and Error Recovery

Inspect validation, empty dashboard/settings, unknown route, expired session,
not-found/forbidden data, retryable server error, and database-unavailable experiences.
Judge whether a person can understand what happened and what to do next. Confirm USD-only
language and formatting are not misleading.

| Check                                           | Result | Notes          |
| ----------------------------------------------- | ------ | -------------- |
| Errors and empty states explain the next action | Pass   | User confirmed |
| No state is confusing, misleading, or blank     | Pass   | User confirmed |
| USD-only scope is clear to the reviewer         | Pass   | User confirmed |

## Findings

| ID  | Severity | Route/state | Finding                   | Reproduction         | Owner | Status |
| --- | -------- | ----------- | ------------------------- | -------------------- | ----- | ------ |
| —   | —        | —           | No human finding reported | All checks completed | —     | Closed |

## Sign-Off

| Decision                           | Value                      |
| ---------------------------------- | -------------------------- |
| Critical or serious issues remain? | No                         |
| Moderate/minor deferrals approved? | No                         |
| Human acceptance result            | Pass                       |
| Reviewer name and date             | User reviewer — 2026-08-12 |
