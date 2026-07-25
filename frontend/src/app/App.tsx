import { Outlet } from "react-router-dom";

import { PageShell } from "../components/PageShell";
import { AuthBootstrap } from "../features/auth/AuthBootstrap";

export function App() {
  return (
    <PageShell>
      <AuthBootstrap>
        <Outlet />
      </AuthBootstrap>
    </PageShell>
  );
}
