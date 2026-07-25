import { test, expect } from "@playwright/test";
import { loginFreshAccount, loginAsRepartidor } from "./helpers";

test("sin sesión, la app muestra el login en vez del shell principal", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Iniciar sesión" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Hoja de despacho" })).not.toBeVisible();
});

test("dueño ve los controles de escritura completos", async ({ page }) => {
  await loginFreshAccount(page);
  await expect(page.getByRole("heading", { name: "Hoja de despacho" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Dibujar zona de cobertura" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Resolver instancia/ })).toBeVisible();
});

test("repartidor no ve controles de escritura (catálogo, cobertura, formulario) — va a su vista dedicada", async ({ page }) => {
  await loginAsRepartidor(page);
  // Desde Etapa 5, el repartidor no ve un shell recortado del de escritorio,
  // va directo a RepartidorView (mobile-first, solo lectura de su ruta).
  await expect(page.getByRole("heading", { name: "Mi ruta" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Hoja de despacho" })).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Dibujar zona de cobertura" })).not.toBeVisible();
});

test("cerrar sesión vuelve a mostrar el login", async ({ page }) => {
  await loginFreshAccount(page);
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page.getByRole("heading", { name: "Iniciar sesión" })).toBeVisible();
});
