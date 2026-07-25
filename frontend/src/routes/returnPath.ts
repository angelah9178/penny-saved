const DEFAULT_RETURN_PATH = "/dashboard";
const AUTH_PATHS = new Set(["/login", "/signup"]);

export function safeReturnPath(value: unknown): string {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.length > 2_048 ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    value.includes("\\") ||
    hasControlCharacter(value)
  ) {
    return DEFAULT_RETURN_PATH;
  }

  let url: URL;

  try {
    url = new URL(value, "https://penny-saved.local");
  } catch {
    return DEFAULT_RETURN_PATH;
  }

  if (url.origin !== "https://penny-saved.local") {
    return DEFAULT_RETURN_PATH;
  }

  const decodedPath = decodePath(url.pathname);
  if (
    decodedPath === null ||
    decodedPath.startsWith("//") ||
    decodedPath.includes("\\") ||
    AUTH_PATHS.has(normalizePath(decodedPath))
  ) {
    return DEFAULT_RETURN_PATH;
  }

  return `${url.pathname}${url.search}${url.hash}`;
}

function decodePath(path: string): string | null {
  let decoded = path;

  try {
    for (let index = 0; index < 3; index += 1) {
      const next = decodeURIComponent(decoded);
      if (next === decoded) {
        return decoded;
      }
      decoded = next;
    }
  } catch {
    return null;
  }

  return decoded.includes("%") ? null : decoded;
}

function normalizePath(path: string): string {
  return path.length > 1 ? path.replace(/\/+$/u, "") : path;
}

function hasControlCharacter(value: string): boolean {
  return Array.from(value).some((character) => {
    const codePoint = character.codePointAt(0);
    return codePoint !== undefined && (codePoint <= 31 || codePoint === 127);
  });
}
