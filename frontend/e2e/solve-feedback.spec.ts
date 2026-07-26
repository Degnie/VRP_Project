import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loginFreshAccount } from "./helpers";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test.beforeEach(async ({ page }) => {
  await loginFreshAccount(page);
});

test("resolver sin flota seleccionada muestra un mensaje, no falla en silencio", async ({ page }) => {
  await page.locator("#depot-x").fill("-77.035");
  await page.locator("#depot-y").fill("-12.0464");
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();
  await page.getByLabel("Nombre del vehículo").fill("Moto");
  await page.getByLabel("Capacidad de peso en kg").fill("30");
  await page.waitForTimeout(500); // deja que el diff-sync guarde el catálogo

  const firstCard = page.locator(".client-card").first();
  await firstCard.locator(".client-card-summary").click();
  await firstCard.locator(".field-row input").nth(0).fill("-77.03");
  await firstCard.locator(".field-row input").nth(1).fill("-12.05");
  await firstCard.locator('input[placeholder="kg"]').fill("5");

  // Sin cantidad de flota seleccionada (todas en 0) — buildInstanceRequest devuelve null.
  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  await expect(page.locator(".error-message")).toContainText("Seleccioná al menos un vehículo");
});

test("resolver con todos los clientes fuera de cobertura muestra un mensaje", async ({ page }) => {
  // Importar primero: el recálculo de "inCoverage" por cliente ocurre al
  // importar CSV y cuando cambia el polígono (useEffect sobre coveragePoints)
  // — no al editar X/Y a mano — así que dibujar la zona después del import
  // garantiza que el useEffect recalcule "fuera de cobertura" para todos.
  const filePath = path.resolve(__dirname, "../examples/clientes_lima_50.csv");
  await page.locator("#clients-file").setInputFiles(filePath);
  await expect(page.locator(".import-status")).toContainText("Se importaron 50 clientes");

  await page.getByRole("button", { name: "Dibujar zona de cobertura" }).click();
  const map = page.locator(".route-map");
  const box = await map.boundingBox();
  if (box) {
    // Triángulo minúsculo en la esquina superior izquierda — con 50 clientes
    // dispersos por Lima, ninguno cae en un área tan chica.
    await page.mouse.click(box.x + 5, box.y + 5);
    await page.mouse.click(box.x + 25, box.y + 5);
    await page.mouse.click(box.x + 5, box.y + 25);
  }
  await page.getByRole("button", { name: "Cerrar polígono" }).click();
  await expect(page.getByRole("button", { name: "Redibujar zona de cobertura" })).toBeVisible();

  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  await expect(page.locator(".error-message")).toContainText("No hay clientes válidos");
});

test("pedido cuyo peso supera la capacidad de cualquier vehículo muestra un mensaje (modo simple)", async ({ page }) => {
  // Bug real: un pedido de 500kg con N vehiculos de 100kg (total 300kg o
  // 1000kg, da igual) nunca podia asignarse a UN vehiculo — el solver lo
  // ignoraba en silencio (Python) o colgaba (NearestNeighbor C++, while(true)
  // sin salida). Ahora se corta antes de POST /solve.
  await page.locator("#depot-x").fill("-77.035");
  await page.locator("#depot-y").fill("-12.0464");
  await page.locator("#capacity").fill("100");

  const firstCard = page.locator(".client-card").first();
  await firstCard.locator(".client-card-summary").click();
  await firstCard.locator(".field-row input").nth(0).fill("-77.03");
  await firstCard.locator(".field-row input").nth(1).fill("-12.05");
  await firstCard.locator('input[placeholder="kg"]').fill("500");

  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  await expect(page.locator(".error-message")).toContainText("supera la capacidad");
});

test("resolver con datos válidos no muestra ningún mensaje de error", async ({ page }) => {
  await page.locator("#depot-x").fill("-77.035");
  await page.locator("#depot-y").fill("-12.0464");

  const cards = page.locator(".client-card");
  const coords: [string, string][] = [["-77.06", "-11.98"], ["-77.03", "-12.12"]];
  for (let i = 0; i < coords.length; i++) {
    const card = cards.nth(i);
    await card.locator(".client-card-summary").click();
    await card.locator(".field-row input").nth(0).fill(coords[i][0]);
    await card.locator(".field-row input").nth(1).fill(coords[i][1]);
    await card.locator('input[placeholder="kg"]').fill("5");
  }

  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".error-message")).toHaveCount(0);
});
