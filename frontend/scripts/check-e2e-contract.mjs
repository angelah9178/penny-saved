import { readFileSync } from "node:fs";
import { readdir } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const frontendRoot = process.cwd();
const e2eRoot = path.join(frontendRoot, "e2e");
const failures = [];
const forbiddenInSpecs = [
  [/\.only\s*\(/u, "focused tests"],
  [/waitForTimeout\s*\(/u, "waitForTimeout"],
  [/\b(?:sleep|setTimeout)\s*\(/u, "fixed sleeps"],
  [/stopimpulsebuying\.us/iu, "the production hostname"],
];

for (const entry of await readdir(e2eRoot, { withFileTypes: true })) {
  if (!entry.isFile() || !entry.name.endsWith(".spec.ts")) continue;
  const source = readFileSync(path.join(e2eRoot, entry.name), "utf8");
  for (const [pattern, description] of forbiddenInSpecs) {
    if (pattern.test(source))
      failures.push(`${entry.name} contains ${description}`);
  }
}

const packageJson = JSON.parse(
  readFileSync(path.join(frontendRoot, "package.json"), "utf8"),
);
const playwrightVersion = packageJson.devDependencies?.["@playwright/test"];
if (!/^\d+\.\d+\.\d+$/u.test(playwrightVersion ?? "")) {
  failures.push("@playwright/test must be pinned to an exact version");
}

const gitignore = readFileSync(
  path.join(frontendRoot, "..", ".gitignore"),
  "utf8",
);
for (const artifactDirectory of [
  "test-results",
  "playwright-report",
  "blob-report",
  "e2e-artifacts",
]) {
  if (!gitignore.includes(`frontend/${artifactDirectory}/`)) {
    failures.push(`${artifactDirectory} browser artifacts must be ignored`);
  }
}

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log("Browser smoke contract checks passed.");
}
