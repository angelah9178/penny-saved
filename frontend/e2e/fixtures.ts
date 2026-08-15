import { expect, test as base } from "@playwright/test";

export const test = base.extend({
  page: async ({ page }, use, testInfo) => {
    const consoleMessages: string[] = [];
    page.on("console", (message) => {
      consoleMessages.push(`[${message.type()}] ${message.text()}`);
    });

    await use(page);

    const ephemeralPassword = process.env.E2E_PASSWORD;
    if (
      ephemeralPassword &&
      consoleMessages.some((message) => message.includes(ephemeralPassword))
    ) {
      throw new Error("Browser console exposed the ephemeral E2E password");
    }

    if (
      testInfo.status !== testInfo.expectedStatus &&
      consoleMessages.length > 0
    ) {
      await testInfo.attach("browser-console", {
        body: Buffer.from(consoleMessages.slice(-100).join("\n")),
        contentType: "text/plain",
      });
    }
  },
});

export { expect };
