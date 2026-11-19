import { defineConfig, devices } from "@playwright/test";

// CI: the built app served by `vite preview`, with every API call answered from e2e/fixtures.ts.
// Locally against the real stack: E2E_REAL=1 E2E_BASE_URL=http://localhost:5173 npm run test:e2e
const real = Boolean(process.env.E2E_REAL);

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:4173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: real
    ? undefined
    : { command: "npm run build && npm run preview -- --port 4173 --strictPort", url: "http://localhost:4173", reuseExistingServer: !process.env.CI, timeout: 120_000 },
});
