import { test, expect } from "@playwright/test";
import { loginFreshAccount } from "./helpers";

test.beforeEach(async ({ page }) => {
  await loginFreshAccount(page);
});

test("flota heterogénea envía vehicle_capacities ordenada de mayor a menor", async ({ page }) => {
  // El catálogo vacío empieza expandido — no hace falta togglear la sección.
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();

  const nameInputs = page.getByLabel("Nombre del vehículo");
  await nameInputs.nth(0).fill("Camioneta");
  await nameInputs.nth(1).fill("Moto");

  const weightInputs = page.getByLabel("Capacidad de peso en kg");
  await weightInputs.nth(0).fill("200");
  await weightInputs.nth(1).fill("50");

  // Seleccionar flota: 1 camioneta + 2 motos
  const camionetaQty = page.getByLabel("Cantidad disponible de Camioneta");
  const motoQty = page.getByLabel("Cantidad disponible de Moto");
  await camionetaQty.fill("1");
  await motoQty.fill("2");

  // Llenar depósito y al menos un cliente (los 3 rows por defecto empiezan vacíos,
  // colapsados — hay que expandir la tarjeta para ver los inputs de X/Y/peso).
  await page.locator("#depot-x").fill("-77.03");
  await page.locator("#depot-y").fill("-12.05");
  const firstCard = page.locator(".client-card").first();
  await firstCard.locator(".client-card-summary").click();
  await firstCard.locator(".field-row input").nth(0).fill("-77.06");
  await firstCard.locator(".field-row input").nth(1).fill("-11.98");
  await firstCard.locator('input[placeholder="kg"]').fill("5");

  const solveRequest = page.waitForRequest((req) => req.url().includes("/solve") && req.method() === "POST");
  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  const request = await solveRequest;
  const body = request.postDataJSON();

  expect(body.vehicle_capacities).toBeDefined();
  expect(body.vehicle_capacities.length).toBe(3);
  // Ordenado de mayor a menor: camioneta (200*0.9=180) primero, luego motos (50*0.9=45)
  expect(body.vehicle_capacities[0]).toBeGreaterThanOrEqual(body.vehicle_capacities[1]);
  expect(body.vehicle_capacities[1]).toBeGreaterThanOrEqual(body.vehicle_capacities[2]);
});
