import { expect, test } from "./fixtures";

test("pinned Chromium opens an isolated accessible fixture", async ({
  browserName,
  page,
}) => {
  expect(browserName).toBe("chromium");

  await page.setContent(`
    <main>
      <h1>Browser smoke runner ready</h1>
      <label for="contract-status">Contract status</label>
      <input id="contract-status" value="isolated" readonly>
    </main>
  `);

  await expect(
    page.getByRole("heading", { name: "Browser smoke runner ready" }),
  ).toBeVisible();
  await expect(page.getByLabel("Contract status")).toHaveValue("isolated");
  await expect(page).toHaveURL("about:blank");
});
