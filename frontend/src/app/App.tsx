import { Outlet } from "react-router-dom";

import { PageShell } from "../components/PageShell";

export function App() {
  return (
    <PageShell>
      <Outlet />
    </PageShell>
  );
}
