import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loginFreshAccount } from "./helpers";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test.beforeEach(async ({ page }) => {
  await loginFreshAccount(page);
});

test("importa CSV simple (sin cliente_id) sin agrupar filas", async ({ page }) => {
  const filePath = path.resolve(__dirname, "../examples/clientes_lima_50.csv");
  await page.locator("#clients-file").setInputFiles(filePath);
  await expect(page.locator(".import-status")).toContainText("Se importaron 50 clientes");
  await expect(page.locator(".client-card")).toHaveCount(50);
});

test("importa CSV multi-paquete y agrupa cliente repetido", async ({ page }) => {
  const filePath = path.resolve(__dirname, "../examples/clientes_lima_multipaquete.csv");
  await page.locator("#clients-file").setInputFiles(filePath);
  // 4 clientes únicos (c1, c2, c3, c4) — c3 aparece 2 veces en el CSV pero se agrupa.
  await expect(page.locator(".import-status")).toContainText("Se importaron 4 clientes");
  await expect(page.locator(".client-card")).toHaveCount(4);

  // c3 debe mostrar 2 paquetes y 7 kg totales en el resumen colapsado de esa tarjeta.
  const summaries = page.locator(".client-summary-weight");
  await expect(summaries.filter({ hasText: "7 kg · 2 paquetes" })).toHaveCount(1);
});
