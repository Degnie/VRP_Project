import { test, expect } from "@playwright/test";
import { loginFreshAccount } from "./helpers";

test.beforeEach(async ({ page }) => {
  await loginFreshAccount(page);
});

test("el catálogo de vehículos persiste en el backend tras recargar", async ({ page }) => {
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();
  await page.getByLabel("Nombre del vehículo").fill("Camioneta");

  // El diff-sync corre en un useEffect tras cada cambio de estado — la última edición
  // (el peso) es la que dispara el POST/PUT final que hay que esperar; escuchar antes
  // de disparar la acción evita la carrera de que la respuesta llegue antes del listener.
  const catalogWrite = page.waitForResponse(
    (res) => res.url().includes("/vehicle-catalog") && ["POST", "PUT"].includes(res.request().method())
  );
  await page.getByLabel("Capacidad de peso en kg").fill("300");
  await catalogWrite;

  await page.reload();
  await expect(page.getByLabel("Nombre del vehículo")).toHaveValue("Camioneta");
});

test("dos sesiones de la misma cuenta ven el mismo catálogo (no aislado por navegador)", async ({ page, context }) => {
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();
  const catalogWrite = page.waitForResponse(
    (res) => res.url().includes("/vehicle-catalog") && ["POST", "PUT"].includes(res.request().method())
  );
  await page.getByLabel("Nombre del vehículo").fill("Moto reparto");
  await catalogWrite;

  const token = await page.evaluate(() => localStorage.getItem("vrp:auth-token"));

  const second = await context.newPage();
  await second.goto("/");
  await second.evaluate((raw) => localStorage.setItem("vrp:auth-token", raw as string), token);
  await second.reload();

  await expect(second.getByLabel("Nombre del vehículo")).toHaveValue("Moto reparto");
});
