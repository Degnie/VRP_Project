import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loginFreshAccount } from "./helpers";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test.beforeEach(async ({ page }) => {
  await loginFreshAccount(page);
});

test("agregar cliente a mano genera un ID legible (row-N), no un timestamp", async ({ page }) => {
  // Bug real: el botón "+ Agregar cliente" generaba IDs tipo
  // "row-3-1721937482013" (timestamp epoch pegado al final) — se mostraban
  // crudos en la tarjeta cuando el cliente no tiene nombre todavía.
  await page.getByRole("button", { name: "+ Agregar cliente" }).click();
  const newCard = page.locator(".client-card").nth(3);
  await expect(newCard.locator(".client-summary-id")).toHaveText("row-3");
});

test("agregar cliente después de importar un CSV no repite un ID ya usado", async ({ page }) => {
  const filePath = path.resolve(__dirname, "../examples/clientes_lima_multipaquete.csv");
  await page.locator("#clients-file").setInputFiles(filePath);
  await expect(page.locator(".import-status")).toContainText("Se importaron 4 clientes");

  await page.getByRole("button", { name: "+ Agregar cliente" }).click();
  await expect(page.locator(".client-card")).toHaveCount(5);
  // Los 4 clientes importados tienen id propio del CSV (c1..c4) — el nuevo
  // arranca después del conteo importado, no colisiona con ninguno.
  const newCard = page.locator(".client-card").nth(4);
  await expect(newCard.locator(".client-summary-id")).toHaveText("row-4");
});
