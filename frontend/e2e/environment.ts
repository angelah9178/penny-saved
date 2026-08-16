const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);
const PRODUCTION_ORIGIN = "https://stopimpulsebuying.online";

export const E2E_ENVIRONMENT_NAMES = [
  "E2E_FRONTEND_URL",
  "E2E_BACKEND_URL",
  "E2E_DATABASE_URL",
  "E2E_RUN_ID",
  "E2E_EMAIL_DOMAIN",
  "E2E_PASSWORD",
  "E2E_SETUP_AT",
  "E2E_MANIFEST_PATH",
] as const;

function readLoopbackUrl(name: string, fallback: string): string {
  const rawValue = process.env[name] ?? fallback;
  let parsed: URL;

  try {
    parsed = new URL(rawValue);
  } catch {
    throw new Error(`${name} must be a valid absolute URL`);
  }

  if (parsed.origin === PRODUCTION_ORIGIN) {
    throw new Error(`${name} must never target the production origin`);
  }
  if (!LOOPBACK_HOSTS.has(parsed.hostname)) {
    throw new Error(`${name} must use localhost or another loopback address`);
  }
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error(`${name} must use HTTP or HTTPS`);
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error(
      `${name} must not contain credentials, a query, or a fragment`,
    );
  }

  return parsed.origin;
}

export const browserEnvironment = Object.freeze({
  frontendUrl: readLoopbackUrl("E2E_FRONTEND_URL", "http://127.0.0.1:4173"),
  backendUrl: readLoopbackUrl("E2E_BACKEND_URL", "http://127.0.0.1:8000"),
});
