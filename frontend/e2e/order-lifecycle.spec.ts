import { test, expect } from "@playwright/test";
import { createOwnerWithRepartidor } from "./helpers";

const API_BASE = "http://localhost:8000";

async function solveInstanceViaApi(page: import("@playwright/test").Page, token: string, instanciaId: string) {
  const res = await page.request.post(`${API_BASE}/solve`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      instancia_id: instanciaId,
      coordinates: [[10, 10], [20, 20]],
      demands: [10, 10],
      num_vehicles: 1,
      vehicle_capacity: 100,
      depot_coordinates: [0, 0],
    },
  });
  expect(res.ok()).toBeTruthy();
}

test("operario asigna repartidor y el repartidor marca una entrega, visible tras reload", async ({ page }) => {
  const { ownerToken, repartidorToken, repartidorUserId } = await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-lifecycle-${Date.now()}`;

  await solveInstanceViaApi(page, ownerToken, instanciaId);

  const assignRes = await page.request.put(`${API_BASE}/instances/${instanciaId}/assignments`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { assignments: { "0": repartidorUserId } },
  });
  expect(assignRes.ok()).toBeTruthy();

  const statusRes = await page.request.put(`${API_BASE}/instances/${instanciaId}/clients/1/status`, {
    headers: { Authorization: `Bearer ${repartidorToken}` },
    data: { status: "entregado" },
  });
  expect(statusRes.ok()).toBeTruthy();

  const myRouteRes = await page.request.get(`${API_BASE}/instances/${instanciaId}/my-route`, {
    headers: { Authorization: `Bearer ${repartidorToken}` },
  });
  const myRoute = await myRouteRes.json();
  const stop1 = myRoute.stops.find((s: { client_id: number }) => s.client_id === 1);
  expect(stop1.delivery_status).toBe("entregado");
});

test("dueño ve y cambia el estado de entrega desde la hoja de ruta resuelta", async ({ page }) => {
  const suffix = `${Date.now()}`;
  const email = `owner-ui-${suffix}@test.local`;
  await page.goto("/");
  await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  await page.locator("#account-name").fill(`E2E Lifecycle UI ${suffix}`);
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();

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

  const select = page.locator(".delivery-status-select").first();
  await select.selectOption("entregado");
  await expect(select).toHaveValue("entregado");
});

test("reprogramar crea una nueva instancia con los pedidos no entregados", async ({ page }) => {
  const { ownerToken } = await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-reschedule-${Date.now()}`;
  await solveInstanceViaApi(page, ownerToken, instanciaId);

  await page.request.put(`${API_BASE}/instances/${instanciaId}/clients/1/status`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { status: "entregado" },
  });

  const rescheduleRes = await page.request.post(`${API_BASE}/instances/${instanciaId}/reschedule`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
  });
  expect(rescheduleRes.ok()).toBeTruthy();
  const body = await rescheduleRes.json();
  expect(body.rescheduled_client_ids).toEqual([2]);
});
