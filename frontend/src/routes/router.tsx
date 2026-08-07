import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { App } from "../app/App";
import { NotFoundPage } from "../pages/NotFoundPage";
import { GuestRoute } from "./GuestRoute";
import { IndexRoute } from "./IndexRoute";
import { ProtectedRoute } from "./ProtectedRoute";
import { RouteErrorPage } from "./RouteErrorPage";
import { RouteLoading } from "./RouteLoading";

export const appRoutes = [
  {
    path: "/",
    element: <App />,
    errorElement: <RouteErrorPage />,
    HydrateFallback: RouteLoading,
    children: [
      {
        index: true,
        element: <IndexRoute />,
      },
      {
        element: <GuestRoute />,
        children: [
          {
            path: "login",
            lazy: async () => {
              const { LoginPage } = await import("../pages/LoginPage");
              return { Component: LoginPage };
            },
          },
          {
            path: "signup",
            lazy: async () => {
              const { SignupPage } = await import("../pages/SignupPage");
              return { Component: SignupPage };
            },
          },
        ],
      },
      {
        element: <ProtectedRoute />,
        children: [
          {
            path: "dashboard",
            lazy: async () => {
              const { DashboardPage } = await import("../pages/DashboardPage");
              return { Component: DashboardPage };
            },
          },
          {
            path: "entries/new",
            lazy: async () => {
              const { NewEntryPage } = await import("../pages/NewEntryPage");
              return { Component: NewEntryPage };
            },
          },
          {
            path: "settings/opportunity-costs",
            lazy: async () => {
              const { OpportunityCostSettingsPage } =
                await import("../pages/OpportunityCostSettingsPage");
              return { Component: OpportunityCostSettingsPage };
            },
          },
          {
            path: "entries/:entryId",
            lazy: async () => {
              const { EntryDetailPage } =
                await import("../pages/EntryDetailPage");
              return { Component: EntryDetailPage };
            },
          },
          {
            path: "entries/:entryId/edit",
            lazy: async () => {
              const { EditEntryPage } = await import("../pages/EditEntryPage");
              return { Component: EditEntryPage };
            },
          },
          {
            path: "entries/:entryId/check-in",
            lazy: async () => {
              const { CheckInEntryPage } =
                await import("../pages/CheckInEntryPage");
              return { Component: CheckInEntryPage };
            },
          },
        ],
      },
      {
        path: "*",
        element: <NotFoundPage />,
      },
    ],
  },
] satisfies RouteObject[];

export function createAppRouter() {
  return createBrowserRouter(appRoutes);
}
