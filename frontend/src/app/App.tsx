import { Outlet } from "react-router-dom";

import { PageShell } from "../components/PageShell";
import { ThemeToggle } from "../components/ThemeToggle";
import { AccountControl } from "../features/auth/AccountControl";
import { AuthBootstrap } from "../features/auth/AuthBootstrap";
import { SessionExpiryCoordinator } from "../features/auth/SessionExpiryCoordinator";
import { RouteExperience } from "../routes/RouteExperience";

export function App() {
  return (
    <PageShell
      headerActions={
        <div className="header-actions">
          <ThemeToggle />
          <AccountControl />
        </div>
      }
    >
      <RouteExperience />
      <SessionExpiryCoordinator />
      <AuthBootstrap>
        <Outlet />
      </AuthBootstrap>
    </PageShell>
  );
}
