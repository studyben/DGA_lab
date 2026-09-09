import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  use: {
    channel: process.env.BROWSER_CHANNEL,
    baseURL: process.env.BASE_URL ?? "http://127.0.0.1:8080",
    viewport: { width: 1920, height: 1080 },
    trace: "retain-on-failure",
  },
  workers: 1,
  reporter: "list",
});
