import { expect, test } from "./fixtures";
import { readE2EManifest, readE2EPassword, type E2EManifest } from "./manifest";

let manifest: E2EManifest;
let password: string;

test.beforeAll(() => {
  manifest = readE2EManifest();
  password = readE2EPassword();
});

test("logged-in user completes check-in, statistics, and logout", async ({
  context,
  page,
}) => {
  await test.step("log in as the seeded user and open its eligible entry", async () => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(manifest.journey_user.email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/dashboard$/u);

    const eligibleCard = page.locator("article").filter({
      has: page.getByRole("heading", { name: manifest.eligible_item_name }),
    });
    await expect(eligibleCard).toContainText("Needs check-in");
    await eligibleCard.getByRole("link", { name: "Check in" }).click();
    await expect(
      page.getByRole("heading", {
        name: `Check in: ${manifest.eligible_item_name}`,
      }),
    ).toBeVisible();
  });

  await test.step("resolve the entry as saved through the visible form", async () => {
    await page.getByLabel("I did not buy it").check();
    await page
      .getByLabel("Reflection (optional)")
      .fill(manifest.check_in_comment);
    await page.getByRole("button", { name: "Submit check-in" }).click();

    await expect(
      page.getByRole("heading", { name: "Check-in complete" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Purchase avoided" }),
    ).toBeVisible();
    await expect(page.getByText(manifest.check_in_comment)).toBeVisible();
    await page.getByRole("link", { name: "Return to dashboard" }).click();

    const savedSection = page.locator("section.entry-section--saved");
    await expect(
      savedSection.getByRole("heading", { name: manifest.eligible_item_name }),
    ).toBeVisible();
    await expect(
      page
        .locator(
          "section.entry-section--needs_check_in, section.entry-section--waiting",
        )
        .getByRole("heading", { name: manifest.eligible_item_name }),
    ).toHaveCount(0);
  });

  await test.step("verify saved totals and manifest-defined equivalents", async () => {
    await page.getByLabel("Time range").selectOption("all_time");
    await expect(page).toHaveURL(/range=all_time/u);
    await assertStatistics(page);

    await page.reload();
    await expect(page.getByLabel("Time range")).toHaveValue("all_time");
    await assertStatistics(page);
  });

  await test.step("log out and prove account-specific access and state are gone", async () => {
    await page.getByRole("button", { name: "Log out" }).click();
    await expect(page).toHaveURL(/\/login$/u);
    const storedState = await page.evaluate(() =>
      JSON.stringify({
        local: { ...localStorage },
        session: { ...sessionStorage },
      }),
    );
    expect(storedState).not.toContain(manifest.journey_user.email);
    expect(storedState).not.toContain("penny_saved_session");
    expect(
      (await context.cookies()).map((cookie) => cookie.name),
    ).not.toContain("penny_saved_session");

    await page.goto("/dashboard?range=all_time");
    await expect(page).toHaveURL(/\/login$/u);
    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
  });
});

async function assertStatistics(
  page: import("@playwright/test").Page,
): Promise<void> {
  await expect(statistic(page, "Total saved")).toHaveText(
    formatUsd(manifest.expected_saved_total_cents),
  );
  await expect(statistic(page, "Purchases avoided")).toHaveText(
    String(manifest.expected_avoided_purchase_count),
  );
  await expect(statistic(page, "Items purchased")).toHaveText(
    String(manifest.expected_purchased_count),
  );

  const wholeEquivalent = page.locator("li").filter({
    hasText: manifest.whole_equivalent_label,
  });
  await expect(wholeEquivalent).toContainText(
    `${manifest.whole_equivalent_units} transit ride`,
  );
  const fractionalEquivalent = page.locator("li").filter({
    hasText: manifest.fractional_equivalent_label,
  });
  await expect(fractionalEquivalent).toContainText(
    `${manifest.fractional_equivalent_units} lunch`,
  );
}

function statistic(page: import("@playwright/test").Page, label: string) {
  return page
    .locator(".statistics__card")
    .filter({ hasText: label })
    .locator("dd");
}

function formatUsd(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}
