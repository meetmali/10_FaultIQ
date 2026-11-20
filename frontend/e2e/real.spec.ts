import { expect, test } from "@playwright/test";

// The same journey against a real running stack (API, worker, PostgreSQL, seeded with
// scripts/seed_demo.py). Skipped unless E2E_REAL=1, because CI has no LBNL data or models.
test.skip(!process.env.E2E_REAL, "set E2E_REAL=1 with the full stack running and seeded");

test("real stack: technician from units to the workbench, the library and back", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("faultiq.persona", "technician"));
  await page.goto("/units");
  await page.getByRole("link", { name: "RTU-1", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Diagnostic workbench: RTU-1" })).toBeVisible();
  await expect(page.getByRole("img", { name: /Rooftop unit schematic at/ })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Model inference", { exact: true }).first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "Measured evidence" })).toBeVisible();
  await page.getByRole("link", { name: /in the Fault Library/ }).click();
  await expect(page.getByRole("heading", { name: "Symptoms" })).toBeVisible();
  await page.getByRole("link", { name: "Back to the diagnosis" }).click();
  await expect(page.getByRole("heading", { name: "Diagnostic workbench: RTU-1" })).toBeVisible();
});
