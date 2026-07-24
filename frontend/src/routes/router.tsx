import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { App } from "../app/App";
import { HomePage } from "../pages/HomePage";
import { NotFoundPage } from "../pages/NotFoundPage";

export const appRoutes = [
  {
    path: "/",
    element: <App />,
    children: [
      {
        index: true,
        element: <HomePage />,
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
