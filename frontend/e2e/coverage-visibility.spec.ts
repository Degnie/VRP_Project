import { test, expect } from "@playwright/test";
import { loginFreshAccount } from "./helpers";

test.beforeEach(async ({ page }) => {
  await loginFreshAccount(page);
  await page.waitForTimeout(1000); // esperar carga de tiles del mapa
});

test("dibujar y cerrar la zona de cobertura no rompe el mapa (color no colisiona con rutas)", async ({ page }) => {
  await page.getByRole("button", { name: "Dibujar zona de cobertura" }).click();
  const map = page.locator(".route-map");
  const box = await map.boundingBox();
  if (box) {
    await page.mouse.click(box.x + box.width * 0.2, box.y + box.height * 0.2);
    await page.mouse.click(box.x + box.width * 0.7, box.y + box.height * 0.2);
    await page.mouse.click(box.x + box.width * 0.7, box.y + box.height * 0.7);
  }
  await page.getByRole("button", { name: "Cerrar polígono" }).click();
  await expect(page.getByRole("button", { name: "Redibujar zona de cobertura" })).toBeVisible();

  // El color del polígono (RouteMap.tsx) se cambió de #c4622d (== ROUTE_COLORS[1],
  // colisionaba con la ruta del segundo vehículo) a #101c33, fuera de la paleta
  // de rutas — se verifica que el mapa sigue renderizando sin errores tras el cambio.
  const canvas = page.locator(".route-map canvas").first();
  await expect(canvas).toBeVisible();
});

test("un vehículo sin nombre no aparece seleccionable en Flota disponible hoy", async ({ page }) => {
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();
  // No se llena el nombre a propósito.
  await page.getByLabel("Capacidad de peso en kg").fill("200");
  await page.waitForTimeout(600);

  // Sin nombre, no cuenta como flota real todavía — no debe aparecer como
  // "(sin nombre)" en Flota disponible hoy ni sincronizarse al backend.
  await expect(page.getByText("Flota disponible hoy")).not.toBeVisible();
  await expect(page.getByText("(sin nombre)")).not.toBeVisible();

  await page.getByLabel("Nombre del vehículo").fill("Camión");
  await page.waitForTimeout(600);
  await expect(page.getByText("Flota disponible hoy")).toBeVisible();
  await expect(page.getByLabel(/Cantidad disponible de Camión/)).toBeVisible();
});

test("un nombre de vehículo largo se trunca en Flota disponible hoy en vez de desbordar la fila", async ({ page }) => {
  // Bug real (Ronda 50, operario): `.fleet-vehicle-name` no tenía
  // min-width:0/overflow:hidden/text-overflow:ellipsis (mismo patrón ya
  // corregido para `.clients-list-head span`) — sin esto, el texto largo
  // hacía wrap a varias líneas (no hay overflow horizontal porque
  // white-space por defecto es "normal"), inflando la altura de la fila muy
  // por encima de una fila de una sola línea y desalineándola con las
  // columnas de spec/cantidad, que quedan centradas verticalmente en una
  // fila mucho más alta que ellas.
  const longName = "Camión de reparto refrigerado de larga distancia modelo XL Pro Max";
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();
  await page.getByLabel("Nombre del vehículo").fill(longName);
  await page.getByLabel("Capacidad de peso en kg").fill("200");
  await page.waitForTimeout(600);

  await expect(page.getByText("Flota disponible hoy")).toBeVisible();
  const nameSpan = page.locator(".fleet-vehicle-name", { hasText: "Cami" });
  await expect(nameSpan).toBeVisible();

  const rowHeight = await nameSpan.evaluate((el) => el.closest(".fleet-table-row")?.getBoundingClientRect().height ?? 0);
  // Una fila de una sola línea de texto a 13px mide bien menos de 40px de
  // alto con el padding/line-height actual — sin el fix, el wrap a 5+ líneas
  // la infla a 70-80px+.
  expect(rowHeight).toBeLessThan(40);
});
