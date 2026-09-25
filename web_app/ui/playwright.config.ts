import { defineConfig, devices } from "@playwright/test";

// End-to-end tests against a running stack. Start both parts first:
//   bridge (mock):  python -m web_app.bridge   (with HUENIT_MOCK_FACE=1)
//   ui:             npm run dev
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    ...devices["Desktop Chrome"],
  },
});
