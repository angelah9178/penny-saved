# DEV-004 — Establish Frontend Application Foundation

## Commit Tracker

Change `[ ]` to `[x]` only after the commit's implementation and commit gate are complete.

|  | Commit | Title | Depends on |
|---|---|---|---|
| &#91;&#160;&#93; | [1](#commit-1--define-api-contract-types-and-query-keys) | Add frontend API contracts and query keys | — |
| &#91;&#160;&#93; | [2](#commit-2--add-the-credentialed-api-client) | Add the credentialed API client | Commit 1 |
| &#91;&#160;&#93; | [3](#commit-3--configure-tanstack-query-behavior) | Configure frontend query behavior | Commit 1 |
| &#91;&#160;&#93; | [4](#commit-4--add-common-request-state-components) | Add accessible request-state components | — |
| &#91;&#160;&#93; | [5](#commit-5--build-the-router-provider-tree-and-application-shell) | Add the router, providers, and application shell | Commits 3, 4 |
| &#91;&#160;&#93; | [6](#commit-6--add-msw-api-testing-and-the-development-proxy) | Add MSW API testing and the Vite proxy | Commits 2, 5 |
| &#91;&#160;&#93; | [7](#commit-7--document-and-verify-the-completed-foundation) | Document DEV-004 frontend foundation | Commits 1–6 |

## Objective

Build the frontend foundation in small, independently testable commits. DEV-004 provides
shared API contracts, stable query keys, a credentialed API client, predictable TanStack
Query behavior, reusable request states, a React Router application shell, an application
provider tree, MSW-backed testing utilities, and the Vite development proxy.

Complete and commit each section in order. Every commit must leave the frontend checks
green before work begins on the next commit. Run frontend commands from `frontend/`.

## Commit 1 — Define API Contract Types and Query Keys

The API is the connection between the React frontend and the FastAPI backend. The
frontend sends HTTP requests to API endpoints, the backend performs the required work
and communicates with PostgreSQL when necessary, and the backend returns JSON responses
that the frontend can display.

An API contract is the agreed shape of those requests and responses. It defines details
such as endpoint payload fields, response fields, allowed status values, nullable values,
timestamp formats, and how money is represented. For example, the contract says that an
entry uses `item_name`, sends its price as integer `price_cents`, and has a status such as
`waiting`, `saved`, or `purchased`.

Commit 1 records those approved API contracts as TypeScript types. In other words, it
defines what data the frontend is allowed to send to the backend and what data the
frontend should expect to receive. TypeScript can then detect incorrect field names,
missing required values, or unsupported values while the frontend is being developed.
The actual network connection and HTTP request behavior are added by the API client in
Commit 2.

The frontend and backend communicate through JSON contracts. TypeScript types describe
those contracts so components, query hooks, and API calls agree on field names and
allowed values. These types preserve the backend's `snake_case` names and represent money
as integer cents. They do not translate API fields into a second frontend-only model.

DEV-004 defines the shared contract vocabulary needed by later features:

- Users and authentication payloads.
- Entries, dashboard buckets, and entry mutation payloads.
- Statistics ranges and summaries.
- Opportunity-cost examples and their mutation payloads.
- The standard success wrappers and error envelope.

The types describe data; they do not validate untrusted responses at runtime or implement
product behavior. The backend remains responsible for authorization, entry eligibility,
dashboard grouping, statistics, and lifecycle transitions.

TanStack Query identifies cached server data with query keys. Central factories prevent
different features from accidentally using different keys for the same resource. They
also make invalidation precise after later mutations.

The stable key families are:

```text
['auth', 'me']
['entries', 'dashboard']
['entries', 'detail', entryId]
['stats', 'summary', range]
['opportunity-costs', 'list']
```

Key factories return readonly tuples so TypeScript preserves their exact shape. Tests
assert the public shapes because changing a key silently would split or strand cached
data.

Suggested commit message:

```text
Add frontend API contracts and query keys
```

Implement:

- Add `frontend/src/types/api.ts`.
- Define API enums, entities, request payloads, response wrappers, and the standard error
  envelope.
- Preserve API `snake_case`, UTC timestamp strings, nullable comments, and integer-cent
  money fields.
- Add `frontend/src/lib/queryKeys.ts`.
- Define readonly factories for auth, dashboard, entry detail, statistics range, and
  opportunity-cost list keys.
- Add focused compile-time coverage where useful and runtime tests for exact query-key
  shapes.
- Create the feature-oriented directories for `auth`, `entries`, `stats`, and
  `opportunity-costs` without adding feature UI.

Commit gate:

```text
npm run format:check
npm run lint
npm run typecheck
npm test -- src/lib/queryKeys.test.ts
```

## Commit 2 — Add the Credentialed API Client

The API client gives all frontend features one consistent way to call the backend.
Without it, each feature would have to repeat URL construction, cookie behavior, headers,
empty-response handling, and error parsing.

Add a generic `apiFetch<T>()` wrapper. Its base URL comes from
`VITE_API_BASE_URL` and defaults to `/api`. The default keeps production requests
same-origin and works with the development proxy added in Commit 6. The client joins the
base URL and endpoint path safely so callers do not need to know whether the configured
base ends with a slash.

Every request sends:

```text
credentials: include
Accept: application/json
```

`credentials: "include"` allows the browser to send the backend's `HttpOnly` session
cookie. The JavaScript application never reads, stores, or logs that cookie. A JSON
`Content-Type` header is added only when a request has a JSON body, allowing bodyless
requests to remain bodyless.

Successful JSON responses are parsed into the requested TypeScript type. A `204 No
Content` response returns without attempting JSON parsing.

Backend failures use the standard envelope:

```json
{
  "error": {
    "code": "machine_readable_code",
    "message": "Safe user-facing summary.",
    "fields": {
      "optional_field": "Optional field-specific error."
    }
  }
}
```

The client converts a valid envelope into an `ApiError` containing the HTTP `status`,
stable `code`, safe `message`, and optional `fields`. Invalid JSON, a malformed error
body, and a network failure receive predictable safe fallbacks rather than leaking raw
browser or server details into UI components. The client also passes an `AbortSignal`
through to `fetch`, allowing TanStack Query to cancel work that is no longer needed.

DEV-004 does not implement the global `401` session-expiry redirect. Authentication
bootstrap, safe return paths, auth-cache clearing, and route guards belong together in
DEV-009. The client must still preserve the `401` status and error code so that work can
be added without replacing the request layer.

Suggested commit message:

```text
Add credentialed frontend API client
```

Implement:

- Add `frontend/src/api/errors.ts` with `ApiError` and safe fallback behavior.
- Add `frontend/src/api/client.ts` with the generic `apiFetch<T>()` wrapper.
- Read `VITE_API_BASE_URL`, falling back to `/api`.
- Always send credentials and an `Accept` header.
- Add JSON `Content-Type` only for JSON request bodies.
- Handle successful JSON and `204` responses.
- Parse the standard backend error envelope without trusting malformed response data.
- Forward caller headers, HTTP methods, and `AbortSignal` without weakening required
  defaults.
- Add focused tests for URL construction, headers, credentials, JSON, `204`, abort
  signals, network failures, and valid or malformed error responses.

Commit gate:

```text
npm run format:check
npm run lint
npm run typecheck
npm test -- src/api
```

## Commit 3 — Configure TanStack Query Behavior

TanStack Query owns remote server state. A shared `QueryClient` gives the application one
place to define when requests are considered stale and which failures may be retried.
Components and feature hooks can then focus on their data rather than recreating global
network policy.

Queries may retry temporary network failures and `5xx` responses at most twice with a
short backoff. Retrying a `4xx` response is normally wasteful because the same request
will continue to be unauthorized, invalid, missing, or in conflict. Mutations are not
retried automatically because repeating a write could create duplicate or confusing
effects.

The query client should also:

- Avoid surprising refetches while tests and initial feature work are being established.
- Keep defaults small and explicit.
- Allow feature hooks to override stale times such as the five-minute auth bootstrap and
  roughly thirty-second dashboard data.
- Be created once for the browser application, but freshly for each test.

Expose a factory rather than only a module-level instance. Production can use one shared
client while tests receive isolated caches that cannot leak data or errors between test
cases.

Suggested commit message:

```text
Configure frontend query behavior
```

Implement:

- Add `frontend/src/app/queryClient.ts`.
- Export a `createQueryClient()` factory with explicit query and mutation defaults.
- Retry only eligible query failures, at most twice.
- Do not retry `ApiError` instances representing `4xx` responses.
- Disable automatic mutation retries.
- Add deterministic tests for query retry decisions, retry limits, and isolated client
  creation.

Commit gate:

```text
npm run format:check
npm run lint
npm run typecheck
npm test -- src/app/queryClient.test.ts
```

## Commit 4 — Add Common Request-State Components

Every server-backed page needs to distinguish loading, failure, and genuinely empty data.
Shared components make those states consistent and prevent a network failure from being
presented as an empty list.

Add small reusable primitives:

- `Loading` communicates that work is in progress with an accessible status.
- `ErrorAlert` presents a safe message and an optional retry action.
- `EmptyState` explains that a successful request returned no relevant data.
- `PageShell` supplies the initial landmark and readable content structure.

These are presentation components. They do not import the API client, inspect query
caches, or decide which business state applies. Feature pages choose the correct state
from their query result and pass narrow typed props.

The initial shell needs meaningful landmarks, ordered headings, visible keyboard focus,
and a layout that works at 320px without horizontal page scrolling. It should respect
reduced-motion preferences and leave space for later navigation and feature content
without pretending those features already exist.

Suggested commit message:

```text
Add accessible frontend request states
```

Implement:

- Add reusable `Loading`, `ErrorAlert`, `EmptyState`, and `PageShell` components under
  `frontend/src/components/`.
- Use native semantic elements and appropriate live-region roles.
- Support an optional retry callback with a real `<button>`.
- Keep component props narrow and independent of TanStack Query.
- Add behavior-focused Testing Library tests using accessible roles and names.
- Establish responsive base styles, visible focus treatment, readable content width, and
  reduced-motion handling.

Commit gate:

```text
npm run format:check
npm run lint
npm run typecheck
npm test -- src/components
```

## Commit 5 — Build the Router, Provider Tree, and Application Shell

The provider tree assembles application-wide infrastructure around the routed UI. It
keeps startup wiring in one place and prevents pages from creating their own router or
query cache.

The initial tree is:

```text
StrictMode
└── AppProviders
    ├── QueryClientProvider
    └── RouterProvider
        └── PageShell
            └── Route content
```

React Router owns location and route rendering. TanStack Query owns server state. The
application entry point creates the browser router and one browser query client, then
passes them into the provider tree. Tests can instead provide a memory router and a fresh
query client.

DEV-004 adds only foundation routes:

- `/` renders the minimal accessible home placeholder inside the application shell.
- `*` renders a not-found page with a link back home.

The product routes, lazy feature pages, auth bootstrap, protected routes, and guest-only
routes are deliberately deferred until their owning DEV tasks. Adding fake
authentication behavior here would be thrown away or could briefly render the wrong
screen during session restoration.

Suggested commit message:

```text
Add frontend router and provider shell
```

Implement:

- Add `frontend/src/app/providers.tsx`.
- Add `frontend/src/routes/router.tsx`.
- Refactor `frontend/src/app/App.tsx` into the routed application layout.
- Update `frontend/src/main.tsx` to create and render the browser router and query client.
- Add the minimal home and not-found route content.
- Allow tests to use a memory router and isolated query client without browser-global
  coupling.
- Add router-level tests for the provider tree, home route, unknown routes, navigation,
  and semantic landmarks.

Commit gate:

```text
npm run format:check
npm run lint
npm run typecheck
npm test -- src/app src/routes
npm run build
```

## Commit 6 — Add MSW API Testing and the Development Proxy

Mock Service Worker intercepts requests at the network boundary. Components and
integration tests call the real `apiFetch()` client while MSW supplies controlled API
responses. This exercises URLs, headers, credentials, parsing, query behavior, and UI
states without asserting internal function calls.

Create one test server with strict unhandled-request behavior. Each test may add only the
handlers it needs; handlers are reset after the test so state cannot leak. A shared
`renderWithApp()` helper supplies a fresh memory router and query client while preserving
Testing Library's normal user-facing queries.

The test lifecycle is:

```text
beforeAll  → start the MSW server
afterEach  → reset handlers and clear isolated state
afterAll   → stop the MSW server
```

Commit 6 also configures Vite to proxy development requests beginning with `/api` to the
local FastAPI server. The browser still calls `/api`, which matches production's
same-origin shape and avoids hard-coding a development server URL in application code.
The proxy is development tooling only; it does not weaken the backend CORS or cookie
configuration.

Suggested commit message:

```text
Add MSW frontend test foundation and API proxy
```

Implement:

- Add `frontend/src/test/server.ts` with the MSW Node server.
- Add `frontend/src/test/handlers.ts` for shared baseline handlers or handler factories.
- Add `frontend/src/test/render.tsx` with a fresh query client and memory router per
  render.
- Extend `frontend/src/test/setup.ts` to start, reset, and stop MSW with unhandled
  requests treated as test failures.
- Move API client coverage to MSW where it improves request-boundary confidence.
- Prove credentials are included and the standard backend error envelope becomes
  `ApiError`.
- Prove routed UI can render loading, success, retryable error, and empty states from
  mocked API behavior without implementation-detail assertions.
- Add the Vite `/api` development proxy targeting the local backend at
  `http://127.0.0.1:8000`.
- Keep the target configurable only if the committed environment design requires it; do
  not expose secrets through `VITE_` variables.

Commit gate:

```text
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
```

## Commit 7 — Document and Verify the Completed Foundation

Suggested commit message:

```text
Document DEV-004 frontend foundation
```

Complete:

- Document frontend startup, the local backend proxy, tests, and troubleshooting.
- Record what DEV-004 achieved, how it was verified, and what remains out of scope.
- Mark DEV-004 complete in `development/0-development-plan.md` only after every check
  passes.
- Update this commit tracker only as each commit and gate is completed.
- Confirm local environment files, coverage, build output, caches, and other generated
  artifacts are not tracked.

Final gate:

```text
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
git diff --check
git status --short
```

## Out of Scope

- Signup, login, logout, session bootstrap, and route guards (DEV-009).
- Dashboard entry lists and feature-specific query hooks (DEV-011).
- Entry create, edit, and delete flows (DEV-012).
- Check-in and comment-editing experiences (DEV-014/DEV-015).
- Statistics and opportunity-cost feature UI (DEV-018/DEV-019).
- Complete shared component library, responsive polish, and accessibility audit
  (DEV-020).
- Continuous integration and combined root quality commands (DEV-006).
- Runtime validation of every successful backend response unless a later feature
  explicitly requires it.

## Planned Implementation Record

Complete this section during Commit 7 with the actual result rather than anticipated
claims.

### Overview

Record the provider tree, router shell, query client, API client, shared request states,
test utilities, and development proxy delivered by DEV-004.

### What It Achieved

Record the observable application and contributor outcomes, including strict builds,
credentialed requests, standard error handling, isolated query caches, accessible route
rendering, and MSW-backed request tests.

### Usage and Safety

Document the exact frontend development command, expected local backend address, use of
`VITE_API_BASE_URL`, cookie handling, and the rule that secrets must never use `VITE_`
variables.

### Verification

Record the exact commands, test count, production-build result, manual smoke checks, and
generated-artifact review performed after implementation.

### Limitations and Follow-up

Replace the out-of-scope list with the remaining concrete follow-up work and any
environment limitations discovered during implementation.
