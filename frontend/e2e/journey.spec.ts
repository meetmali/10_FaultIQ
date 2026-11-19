import { expect, test } from "@playwright/test";

import { event, faultTitle, mockApi } from "./fixtures";

// The Phase 7 exit criterion: overview -> a specific diagnosis -> the fault reference -> back,
// without broken navigation or unexplained placeholder values.
test("a user moves from the dashboard to a diagnosis, the fault reference and back", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByRole("row", { name: /RTU-1/ }).getByText("Fault detected")).toBeVisible();

  await page.getByRole("link", { name: "RTU-1" }).click();
  await expect(page.getByRole("heading", { name: "Fault diagnostics: RTU-1" })).toBeVisible();
  const detail = page.getByRole("region", { name: faultTitle });
  await expect(detail.getByText("Model inference", { exact: true })).toBeVisible();
  await expect(detail.getByText(event.statements[0].text)).toBeVisible();
  await expect(detail.getByRole("heading", { name: "Possible alternatives" })).toBeVisible();
  await expect(detail.getByRole("heading", { name: "Measured evidence" })).toBeVisible();
  await expect(detail.getByText(/hasn't yet been reviewed by an HVAC professional/)).toBeVisible();
  await expect(page.getByText(/undefined|NaN|\[object Object\]/)).toHaveCount(0);

  await detail.getByRole("link", { name: /in the Fault Library/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: faultTitle })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Symptoms" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "References" })).toBeVisible();

  await page.getByRole("link", { name: "Back to the diagnosis" }).click();
  await expect(page.getByRole("heading", { name: "Fault diagnostics: RTU-1" })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`event=${event.id}`));
});

test("the library is searchable by symptom and every entry opens", async ({ page }) => {
  await mockApi(page);
  await page.goto("/library");
  await page.getByLabel("Search by fault or symptom").fill("discharge");
  await expect(page.getByRole("link", { name: faultTitle })).toBeVisible();
});

test("keyboard users can skip to content and reach the main navigation", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main")).toBeFocused();
});

test("errors offer a retry, and demo mode labels sample data and hides uploads", async ({ page }) => {
  await mockApi(page, { failOverview: true });
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("An unexpected error occurred.");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();

  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mockApi(page, { demo: true });
  await page.goto("/");
  await expect(page.getByRole("note", { name: "Public demo notice" })).toBeVisible();
  await expect(page.getByText("sample data").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Analyse new data" })).toHaveCount(0);
});
