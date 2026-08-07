import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";

const root = new URL("../", import.meta.url);
const frontend = new URL("frontend/", root);
const triage = JSON.parse(
  readFileSync(
    new URL("development/security-advisory-triage.json", root),
    "utf8",
  ),
);
const audit = spawnSync("npm", ["audit", "--json"], {
  cwd: frontend,
  encoding: "utf8",
});

if (audit.error) throw audit.error;

let report;
try {
  report = JSON.parse(audit.stdout);
} catch {
  process.stderr.write(audit.stderr || audit.stdout);
  process.exit(2);
}

const approvals = new Map(
  triage.advisories.map((item) => {
    if (!/^GHSA-[a-z0-9-]+$/.test(item.id))
      throw new Error(`Invalid triage ID: ${item.id}`);
    if (Date.parse(`${item.review_date}T23:59:59Z`) < Date.now()) {
      throw new Error(`Advisory triage expired: ${item.id}`);
    }
    for (const field of ["impact", "rationale", "owner", "follow_up"]) {
      if (!item[field])
        throw new Error(`Advisory triage ${item.id} is missing ${field}`);
    }
    return [item.id.toUpperCase(), item];
  }),
);
const vulnerabilities = report.vulnerabilities ?? {};

function advisoryIds(packageName, visited = new Set()) {
  if (visited.has(packageName)) return new Set();
  visited.add(packageName);
  const vulnerability = vulnerabilities[packageName];
  if (!vulnerability) return new Set();
  const ids = new Set();
  for (const cause of vulnerability.via ?? []) {
    if (typeof cause === "string") {
      for (const id of advisoryIds(cause, visited)) ids.add(id);
    } else {
      const match = String(cause.url ?? "").match(/GHSA-[a-z0-9-]+/i);
      if (match) ids.add(match[0].toUpperCase());
    }
  }
  return ids;
}

const blocking = [];
const accepted = [];
for (const [packageName, vulnerability] of Object.entries(vulnerabilities)) {
  if (!["high", "critical"].includes(vulnerability.severity)) continue;
  const ids = [...advisoryIds(packageName)];
  const fullyTriaged =
    ids.length > 0 &&
    ids.every((id) => approvals.get(id)?.packages.includes(packageName));
  if (fullyTriaged) accepted.push(`${packageName}: ${ids.join(", ")}`);
  else
    blocking.push(
      `${packageName}: ${ids.join(", ") || "unidentified advisory"}`,
    );
}

if (accepted.length) {
  process.stdout.write(
    `Reviewed advisory triage:\n${accepted.map((item) => `- ${item}`).join("\n")}\n`,
  );
}
if (blocking.length) {
  process.stderr.write(
    `Untriaged high/critical frontend advisories:\n${blocking.map((item) => `- ${item}`).join("\n")}\n`,
  );
  process.exit(1);
}
process.stdout.write(
  "No untriaged high/critical frontend dependency advisories.\n",
);
