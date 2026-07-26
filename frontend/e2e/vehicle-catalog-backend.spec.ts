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

test("escribir el nombre de un vehículo nuevo letra por letra no pierde caracteres", async ({ page }) => {
  // Bug real: la primera letra tecleada disparaba el POST de creación (el
  // useEffect de diff-sync reacciona a cada cambio de estado). El backend
  // siempre devuelve un id propio (ignora el id local del draft), así que
  // cuando la respuesta llegaba mientras el usuario seguía tipeando, el
  // frontend reemplazaba la fila entera con el snapshot stale de la
  // respuesta — perdiendo cualquier letra tecleada después de la primera.
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();
  const nameInput = page.getByLabel("Nombre del vehículo");
  await nameInput.pressSequentially("CamionSolo", { delay: 30 });
  await expect(nameInput).toHaveValue("CamionSolo");

  // React puede agrupar la última tecla con un PUT en vuelo en vez de
  // disparar uno nuevo — no hay forma confiable de esperar "el último write"
  // por conteo de requests. Se espera a que la cola de escrituras drene
  // (poll de red inactiva) y se confirma el resultado final en el backend.
  await page.waitForLoadState("networkidle");
  await page.reload();
  await expect(page.getByLabel("Nombre del vehículo")).toHaveValue("CamionSolo");
});

test("si el borrado de un vehículo falla en el backend, la fila vuelve con un error visible", async ({ page }) => {
  // Bug real (Ronda 37, dueño): el DELETE fallido se tragaba en silencio y el
  // diff-sync local marcaba el vehículo como "ya reconciliado" igual, así que
  // nunca reintentaba — la fila desaparecía de la UI sin aviso y solo
  // reaparecía sola al recargar (el backend nunca lo había borrado).
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();
  const created = page.waitForResponse(
    (res) => res.url().includes("/vehicle-catalog") && res.request().method() === "POST"
  );
  await page.getByLabel("Nombre del vehículo").fill("Camion a borrar");
  await created;

  await page.route("**/vehicle-catalog/**", (route) => {
    if (route.request().method() === "DELETE") {
      route.fulfill({ status: 500, body: "{}" });
    } else {
      route.continue();
    }
  });

  await page.getByRole("button", { name: /Eliminar vehículo Camion a borrar/ }).click();

  await expect(page.getByLabel("Nombre del vehículo")).toHaveValue("Camion a borrar");
  await expect(page.getByText(/No se pudo eliminar/)).toBeVisible();
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
