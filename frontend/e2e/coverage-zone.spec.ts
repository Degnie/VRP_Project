import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loginFreshAccount } from "./helpers";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test.beforeEach(async ({ page }) => {
  await loginFreshAccount(page);
});

test("dibujar polígono de cobertura excluye clientes fuera de él del POST /solve", async ({ page }) => {
  const filePath = path.resolve(__dirname, "../examples/clientes_lima_50.csv");
  await page.locator("#clients-file").setInputFiles(filePath);
  await expect(page.locator(".import-status")).toContainText("Se importaron 50 clientes");

  await page.getByRole("button", { name: "Dibujar zona de cobertura" }).click();

  const map = page.locator(".route-map");
  const box = await map.boundingBox();
  if (!box) throw new Error("mapa sin bounding box");

  // Dibuja un triángulo que cubre la mitad izquierda del mapa: con 50
  // clientes distribuidos por toda Lima, algunos quedan dentro y otros
  // afuera (evita el caso degenerado de excluir a todos, que no dispara /solve).
  await page.mouse.click(box.x + box.width * 0.1, box.y + box.height * 0.1);
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.1);
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.9);
  await page.mouse.click(box.x + box.width * 0.1, box.y + box.height * 0.9);

  await page.getByRole("button", { name: "Cerrar polígono" }).click();

  const solveRequest = page.waitForRequest((req) => req.url().includes("/solve") && req.method() === "POST");
  await page.locator("#depot-x").fill("-77.03");
  await page.locator("#depot-y").fill("-12.05");
  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  const request = await solveRequest;
  const body = request.postDataJSON();

  // El polígono cubre solo parte del mapa: no deberían llegar los 50 clientes completos.
  expect(body.coordinates.length).toBeGreaterThan(0);
  expect(body.coordinates.length).toBeLessThan(50);
});

test("el polígono de cobertura persiste tras recargar la página", async ({ page }) => {
  await page.getByRole("button", { name: "Dibujar zona de cobertura" }).click();
  const map = page.locator(".route-map");
  const box = await map.boundingBox();
  if (!box) throw new Error("mapa sin bounding box");

  await page.mouse.click(box.x + 20, box.y + 20);
  await page.mouse.click(box.x + 120, box.y + 20);
  await page.mouse.click(box.x + 70, box.y + 120);
  await page.getByRole("button", { name: "Cerrar polígono" }).click();

  await page.reload();
  await expect(page.getByRole("button", { name: "Redibujar zona de cobertura" })).toBeVisible();
});
