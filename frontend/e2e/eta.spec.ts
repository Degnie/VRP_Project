import { test, expect } from "@playwright/test";
import { loginFreshAccount } from "./helpers";

test.beforeEach(async ({ page }) => {
  await loginFreshAccount(page);
});

test("resuelve una instancia chica y muestra horarios estimados HH:MM crecientes", async ({ page }) => {
  await page.locator("#depot-x").fill("-77.035");
  await page.locator("#depot-y").fill("-12.0464");

  const cards = page.locator(".client-card");
  const coords: [string, string][] = [
    ["-77.06", "-11.98"],
    ["-77.03", "-12.12"],
    ["-77.10", "-12.05"],
  ];
  for (let i = 0; i < coords.length; i++) {
    const card = cards.nth(i);
    await card.locator(".client-card-summary").click();
    await card.locator(".field-row input").nth(0).fill(coords[i][0]);
    await card.locator(".field-row input").nth(1).fill(coords[i][1]);
    await card.locator('input[placeholder="kg"]').fill("5");
  }

  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15_000 });

  const stopEta = page.locator(".route-stop-eta").first();
  await expect(stopEta).toBeVisible({ timeout: 15_000 });
  await expect(stopEta).toHaveText(/\d{2}:\d{2}–\d{2}:\d{2}/);
});
