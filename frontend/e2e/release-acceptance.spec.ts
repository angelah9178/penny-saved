import { expect, test } from "./fixtures";
import { readE2EManifest, readE2EPassword, type E2EManifest } from "./manifest";

let manifest: E2EManifest;
let password: string;

test.beforeAll(() => {
  manifest = readE2EManifest();
  password = readE2EPassword();
});

test("rendered accessibility safeguards hold in Chromium", async ({ page }) => {
  await test.step("skip navigation exposes and focuses main content", async () => {
    await page.goto("/login");
    const skipLink = page.getByRole("link", { name: "Skip to main content" });
    await skipLink.focus();
    await expect(skipLink).toBeFocused();
    await expect(skipLink).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(page.locator("#main-content")).toBeFocused();
  });

  await test.step("reduced motion reaches rendered controls", async () => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect(page.getByRole("button", { name: "Log in" })).toHaveCSS(
      "transition-duration",
      /^(?:0\.00001|1e-05)s$/u,
    );
  });

  await test.step("the account dashboard reflows at 320 CSS pixels", async () => {
    await page.setViewportSize({ width: 320, height: 720 });
    await page.getByLabel("Email").fill(manifest.journey_user.email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/dashboard$/u);

    const layout = await page.evaluate<{
      clientWidth: number;
      scrollWidth: number;
    }>(
      "({ clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth })",
    );
    expect(layout.scrollWidth).toBeLessThanOrEqual(layout.clientWidth);

    for (const control of await page
      .locator("button, select, .entry-card__actions a")
      .all()) {
      if (!(await control.isVisible())) continue;
      const box = await control.boundingBox();
      expect(box, "visible control must have rendered geometry").not.toBeNull();
      expect(box?.height).toBeGreaterThanOrEqual(44);
      expect(box?.width).toBeGreaterThanOrEqual(44);
    }

    await page.getByRole("button", { name: "Log out" }).click();
    await expect(page).toHaveURL(/\/login$/u);
  });
});
