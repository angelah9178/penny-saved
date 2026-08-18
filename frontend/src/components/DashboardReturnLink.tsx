import { Link } from "react-router-dom";

export function DashboardReturnLink() {
  return (
    <Link className="dashboard-return-link" to="/dashboard">
      Return to dashboard
    </Link>
  );
}
