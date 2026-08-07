import { axe } from "jest-axe";
import { expect } from "vitest";

type AxeOptions = NonNullable<Parameters<typeof axe>[1]>;
type AxeResults = Awaited<ReturnType<typeof axe>>;

const DEFAULT_OPTIONS: AxeOptions = {
  rules: {
    // Color and layout require a real browser. They remain in the manual audit.
    "color-contrast": { enabled: false },
  },
};

/**
 * Scans rendered markup for automatically detectable accessibility violations.
 *
 * This helper is a regression alarm, not an accessibility certification. Keyboard
 * behavior, focus quality, screen-reader clarity, layout, zoom, and contrast still
 * require direct tests or the DEV-020 manual audit.
 */
export async function expectNoAccessibilityViolations(
  container: Element,
  options: AxeOptions = DEFAULT_OPTIONS,
): Promise<AxeResults> {
  const results = await axe(container, options);

  expect(results.violations, formatViolations(results)).toEqual([]);

  return results;
}

function formatViolations(results: AxeResults): string {
  if (results.violations.length === 0) {
    return "Expected the accessibility scan to pass.";
  }

  const details = results.violations.flatMap((violation) => [
    `${violation.id}: ${violation.help}`,
    ...violation.nodes.map(
      (node) => `  ${node.target.join(" ")} — ${node.failureSummary ?? ""}`,
    ),
  ]);

  return `Accessibility violations:\n${details.join("\n")}`;
}
