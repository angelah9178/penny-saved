import { matchPath } from "react-router-dom";

const APPLICATION_NAME = "A Penny Saved";

const ROUTE_TITLES = [
  { pattern: "/dashboard", title: "Dashboard" },
  { pattern: "/login", title: "Log in" },
  { pattern: "/signup", title: "Create your account" },
  { pattern: "/entries/new", title: "Add an entry" },
  {
    pattern: "/settings/opportunity-costs",
    title: "Opportunity-cost examples",
  },
  { pattern: "/entries/:entryId/edit", title: "Edit entry" },
  { pattern: "/entries/:entryId/check-in", title: "Check in" },
  { pattern: "/entries/:entryId", title: "Entry details" },
] as const;

export function titleForPath(pathname: string): string {
  const route = ROUTE_TITLES.find(({ pattern }) =>
    matchPath({ path: pattern, end: true }, pathname),
  );

  return route === undefined
    ? `Page not found | ${APPLICATION_NAME}`
    : `${route.title} | ${APPLICATION_NAME}`;
}
