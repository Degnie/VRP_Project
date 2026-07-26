import { test, expect } from "@playwright/test";
import { loginFreshAccount } from "./helpers";

test.beforeEach(async ({ page }) => {
  await loginFreshAccount(page);
});

test("dueño invita un operario y un repartidor desde la UI y los ve en la lista", async ({ page }) => {
  await page.getByRole("button", { name: "Gestionar equipo" }).click();
  await expect(page.getByRole("heading", { name: "Gestionar equipo" })).toBeVisible();

  const suffix = Date.now();
  await page.locator("#invite-email").fill(`operario-${suffix}@test.local`);
  await page.locator("#invite-password").fill("clave123456");
  await page.locator("#invite-role").selectOption("operario");
  await page.getByRole("button", { name: "Invitar" }).click();

  await expect(page.getByText(`operario-${suffix}@test.local`)).toBeVisible();

  await page.locator("#invite-email").fill(`repartidor-${suffix}@test.local`);
  await page.locator("#invite-password").fill("clave123456");
  await page.locator("#invite-role").selectOption("repartidor");
  await page.getByRole("button", { name: "Invitar" }).click();

  await expect(page.getByText(`repartidor-${suffix}@test.local`)).toBeVisible();
  // El dueño (quien se registró) también debe aparecer en la lista.
  await expect(page.locator(".team-table tbody tr")).toHaveCount(3);
});

test("dueño desactiva a un miembro y ese usuario ya no puede loguear", async ({ page }) => {
  await page.getByRole("button", { name: "Gestionar equipo" }).click();

  const email = `desactivar-${Date.now()}@test.local`;
  await page.locator("#invite-email").fill(email);
  await page.locator("#invite-password").fill("clave123456");
  await page.locator("#invite-role").selectOption("repartidor");
  await page.getByRole("button", { name: "Invitar" }).click();
  await expect(page.getByText(email)).toBeVisible();

  const row = page.locator(".team-table tbody tr", { hasText: email });
  await row.getByRole("button", { name: "Desactivar" }).click();
  await expect(row).toHaveClass(/team-row--inactive/);
  await expect(row.getByText("Inactivo")).toBeVisible();

  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Iniciar sesión" })).toBeVisible();
});

test("botón Gestionar equipo vuelve a mostrar las rutas al hacer click de nuevo", async ({ page }) => {
  await page.getByRole("button", { name: "Gestionar equipo" }).click();
  await expect(page.getByRole("heading", { name: "Gestionar equipo" })).toBeVisible();

  await page.getByRole("button", { name: "Volver a rutas" }).click();
  await expect(page.getByRole("heading", { name: "Hoja de despacho" })).toBeVisible();
});
