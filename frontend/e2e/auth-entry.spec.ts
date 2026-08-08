import { expect, test } from "./fixtures";
import { readE2EManifest, readE2EPassword, type E2EManifest } from "./manifest";

let manifest: E2EManifest;
let password: string;

test.beforeAll(() => {
  manifest = readE2EManifest();
  password = readE2EPassword();
});

test("first-half journey signs up, restores the session, and creates an entry", async ({
  page,
}) => {
  await test.step("create the reserved signup account through the real form", async () => {
    await page.goto("/signup");
    await expect(
      page.getByRole("heading", { name: "Create your account" }),
    ).toBeVisible();
    await page.getByLabel("Email").fill(manifest.signup_user.email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Create account" }).click();

    await expect(page).toHaveURL(/\/dashboard$/u);
    await expect(
      page.getByRole("heading", { name: "Dashboard" }),
    ).toBeVisible();
    await expect(page.getByText(manifest.signup_user.email)).toBeVisible();
  });

  await test.step("reload and prove the HttpOnly-cookie session restores", async () => {
    await page.reload();
    await expect(page).toHaveURL(/\/dashboard$/u);
    await expect(
      page.getByRole("heading", { name: "Dashboard" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
    await assertSecretIsNotBrowserVisible(page);
  });

  await test.step("create one uniquely run-owned waiting entry", async () => {
    await page.getByRole("link", { name: "Add new impulse purchase" }).click();
    await expect(
      page.getByRole("heading", { name: "Add a new entry" }),
    ).toBeVisible();
    await page.getByLabel("Item name").fill(manifest.signup_entry_item_name);
    await page
      .getByLabel("Price")
      .fill((manifest.signup_entry_price_cents / 100).toFixed(2));
    await page.getByLabel("Reason wanted").fill(manifest.signup_entry_reason);
    await page.getByRole("button", { name: "Add entry" }).click();

    await expect(page).toHaveURL(/\/dashboard$/u);
    await expect(page.getByText("Entry added to Waiting.")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: manifest.signup_entry_item_name }),
    ).toBeVisible();

    await page.reload();
    await expect(
      page.getByRole("heading", { name: manifest.signup_entry_item_name }),
    ).toHaveCount(1);
  });

  await test.step("log out and prove protected navigation returns to login", async () => {
    await page.getByRole("button", { name: "Log out" }).click();
    await expect(page).toHaveURL(/\/login$/u);
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login$/u);
    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
  });
});

test("seeded journey account logs in and sees its eligible entry", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(manifest.journey_user.email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();

  await expect(page).toHaveURL(/\/dashboard$/u);
  await expect(
    page.getByRole("heading", { name: "Needs check-in" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: manifest.eligible_item_name }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Check in" })).toBeVisible();
});

async function assertSecretIsNotBrowserVisible(
  page: import("@playwright/test").Page,
): Promise<void> {
  expect(page.url()).not.toContain(password);
  const browserStorage = await page.evaluate(() => ({
    local: { ...localStorage },
    session: { ...sessionStorage },
  }));
  expect(JSON.stringify(browserStorage)).not.toContain(password);
  expect(JSON.stringify(browserStorage)).not.toContain("penny_saved_session");
}
