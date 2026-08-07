import { Outlet } from "react-router-dom";

import { PageShell } from "../components/PageShell";
import { AccountControl } from "../features/auth/AccountControl";
import { AuthBootstrap } from "../features/auth/AuthBootstrap";
import { SessionExpiryCoordinator } from "../features/auth/SessionExpiryCoordinator";
import { RouteExperience } from "../routes/RouteExperience";

export function App() {
  return (
    <PageShell headerActions={<AccountControl />}>
      <RouteExperience />
      <SessionExpiryCoordinator />
      <AuthBootstrap>
        <Outlet />
      </AuthBootstrap>
    </PageShell>
  );
}
