import { test, expect } from "@playwright/test";
import { createOwnerWithRepartidor } from "./helpers";

const API_BASE = "http://localhost:8000";

test.use({ viewport: { width: 390, height: 844 } });

async function solveAndAssign(
  page: import("@playwright/test").Page,
  ownerToken: string,
  repartidorUserId: string,
  instanciaId: string
) {
  const solveRes = await page.request.post(`${API_BASE}/solve`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: {
      instancia_id: instanciaId,
      coordinates: [[10, 10], [20, 20]],
      demands: [10, 10],
      num_vehicles: 1,
      vehicle_capacity: 100,
      depot_coordinates: [0, 0],
    },
  });
  expect(solveRes.ok()).toBeTruthy();

  const assignRes = await page.request.put(`${API_BASE}/instances/${instanciaId}/assignments`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { assignments: { "0": repartidorUserId } },
  });
  expect(assignRes.ok()).toBeTruthy();
}

async function loginRepartidorInBrowser(
  page: import("@playwright/test").Page,
  email: string,
  password: string
) {
  await page.goto("/");
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill(password);
  await page.getByRole("button", { name: "Entrar" }).click();
}

test("repartidor en mobile ve RepartidorView, no el sidebar de escritorio", async ({ page }) => {
  const { repartidorEmail, repartidorPassword } = await createOwnerWithRepartidor(page);
  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);

  await expect(page.getByRole("heading", { name: "Mi ruta" })).toBeVisible();
  await expect(page.locator(".app-sidebar")).not.toBeVisible();
  await expect(page.locator("#instancia-id")).not.toBeVisible();
});

test("repartidor en mobile elige instancia, ve paradas y marca una entrega", async ({ page }) => {
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);

  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const firstStop = page.locator(".repartidor-stop").first();
  await firstStop.getByRole("button", { name: "Entregado" }).click();
  await expect(firstStop.getByRole("button", { name: "Entregado" })).toHaveClass(/repartidor-status-btn--active/);
});

test("repartidor en mobile puede exportar su hoja en PDF", async ({ page }) => {
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-pdf-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar mi hoja en PDF" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^mi_ruta_.*\.pdf$/);
});

test("header de la lista de clientes no se corta en viewport angosto (dueño)", async ({ page }) => {
  const suffix = `${Date.now()}`;
  await page.goto("/");
  await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  await page.locator("#account-name").fill(`E2E Mobile Owner ${suffix}`);
  await page.locator("#login-email").fill(`mobile-owner-${suffix}@test.local`);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();

  const contactHeader = page.locator(".clients-list-head span", { hasText: "Contacto" });
  await expect(contactHeader).toBeVisible();
  const box = await contactHeader.boundingBox();
  const sidebarBox = await page.locator(".app-sidebar").boundingBox();
  expect(box).not.toBeNull();
  expect(sidebarBox).not.toBeNull();
  // El header no debe desbordar el ancho del sidebar (lo que causaba el corte visual).
  expect(box!.x + box!.width).toBeLessThanOrEqual(sidebarBox!.x + sidebarBox!.width + 1);
});
