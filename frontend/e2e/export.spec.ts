import { test, expect } from "@playwright/test";
import { loginFreshAccount } from "./helpers";
import fs from "node:fs/promises";

test.beforeEach(async ({ page }) => {
  await loginFreshAccount(page);
});

async function solveSmallInstance(page: import("@playwright/test").Page) {
  await page.locator("#depot-x").fill("-77.035");
  await page.locator("#depot-y").fill("-12.0464");

  const cards = page.locator(".client-card");
  const coords: [string, string][] = [
    ["-77.06", "-11.98"],
    ["-77.03", "-12.12"],
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
}

test("exporta CSV con la hoja de ruta resuelta", async ({ page }) => {
  await solveSmallInstance(page);

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar CSV" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^ruta_.*\.csv$/);
});

test("exportar CSV tras editar un cliente incluye el dato nuevo, no el original", async ({ page }) => {
  // Bug real (Ronda 41, operario): el botón "Exportar CSV" armaba el archivo
  // con la prop `contacts` (snapshot original de App.tsx), no con
  // `localContacts` (el estado que SÍ se actualiza al editar un cliente con
  // ClientEditControl) — la lista en pantalla mostraba el dato editado
  // correctamente, pero el CSV descargado traía el nombre/teléfono/dirección
  // VIEJOS, justo el caso de uso para el que existe el botón "Editar".
  await solveSmallInstance(page);

  await page.locator(".btn-tertiary", { hasText: "Editar" }).first().click();
  await page.getByLabel("Nombre", { exact: true }).fill("Nombre Corregido");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByRole("button", { name: "Guardar", exact: true })).not.toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar CSV" }).click();
  const download = await downloadPromise;
  const csvPath = await download.path();
  const csvContent = await fs.readFile(csvPath!, "utf-8");
  expect(csvContent).toContain("Nombre Corregido");
});

test("el número de vehículo en el CSV coincide con el mostrado en pantalla y en el PDF", async ({ page }) => {
  // Bug real (Ronda 1, ciclo nuevo, dueño): la UI y el PDF muestran
  // "Vehículo N" con route.vehicle_id + 1 (1-indexado), pero el CSV exportaba
  // la columna "vehiculo" con route.vehicle_id crudo (0-indexado) — un dueño
  // que compara ambos documentos para la misma instancia ve los números
  // desalineados (el vehículo 2 en pantalla/PDF aparece como "1" en el CSV).
  await page.locator("#depot-x").fill("-77.035");
  await page.locator("#depot-y").fill("-12.0464");
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();
  await page.getByLabel("Nombre del vehículo").fill("Camioneta");
  await page.getByLabel("Capacidad de peso en kg").fill("45");
  await page.waitForTimeout(500);
  await page.getByLabel(/Cantidad disponible de Camioneta/).fill("2");

  // Pesos que superan la capacidad EFECTIVA de UN vehículo (45kg * 90% margen
  // = 40.5kg) para forzar al solver a usar los 2 vehículos seleccionados, en
  // vez de optimizar a 1.
  const cards = page.locator(".client-card");
  const coords: [string, string][] = [
    ["-77.06", "-11.98"],
    ["-77.03", "-12.12"],
  ];
  for (let i = 0; i < coords.length; i++) {
    const card = cards.nth(i);
    await card.locator(".client-card-summary").click();
    await card.locator(".field-row input").nth(0).fill(coords[i][0]);
    await card.locator(".field-row input").nth(1).fill(coords[i][1]);
    await card.locator('input[placeholder="kg"]').fill("22");
  }

  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  await expect(page.locator(".error-message")).toHaveCount(0);
  await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Vehículo 2")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar CSV" }).click();
  const download = await downloadPromise;
  const csvPath = await download.path();
  const csvContent = await fs.readFile(csvPath!, "utf-8");
  expect(csvContent).toMatch(/^2,/m);
});

test("exporta PDF con la hoja de ruta resuelta", async ({ page }) => {
  await solveSmallInstance(page);

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar PDF" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^ruta_.*\.pdf$/);
});
