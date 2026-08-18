import { useEffect, useState } from "react";

import { apiFetch } from "../api/client";

type ServiceStatus = "checking" | "ready" | "unavailable";

type ReadinessResponse = {
  status: string;
};

const CHECK_INTERVAL_MILLISECONDS = 60_000;

const STATUS_LABELS: Record<ServiceStatus, string> = {
  checking: "Checking app status",
  ready: "App is healthy",
  unavailable: "App is unavailable",
};

export function ServiceHealthIndicator() {
  const [status, setStatus] = useState<ServiceStatus>("checking");

  useEffect(() => {
    let isMounted = true;

    async function checkReadiness(): Promise<void> {
      try {
        const response = await apiFetch<ReadinessResponse>("/ready");
        if (isMounted) {
          setStatus(response.status === "ready" ? "ready" : "unavailable");
        }
      } catch {
        if (isMounted) {
          setStatus("unavailable");
        }
      }
    }

    void checkReadiness();
    const intervalId = window.setInterval(
      () => void checkReadiness(),
      CHECK_INTERVAL_MILLISECONDS,
    );

    return () => {
      isMounted = false;
      window.clearInterval(intervalId);
    };
  }, []);

  const label = STATUS_LABELS[status];

  return (
    <span
      aria-label={label}
      className={`service-health service-health--${status}`}
      role="img"
      title={label}
    />
  );
}
