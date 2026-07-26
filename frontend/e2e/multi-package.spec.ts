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

test("importa CSV con delimitador ; (Excel es-*) en vez de ,", async ({ page }) => {
  const filePath = path.resolve(__dirname, "../examples/clientes_lima_semicolon.csv");
  await page.locator("#clients-file").setInputFiles(filePath);
  // Formato sin cliente_id (igual que clientes_lima_50.csv): la primera fila
  // de datos se usa como depósito, el resto son clientes.
  await expect(page.locator(".import-status")).toContainText("Se importaron 2 clientes");
  await expect(page.locator(".client-card")).toHaveCount(2);
});

test("importa CSV en Windows-1252 sin corromper ñ/tildes en nombre de cliente", async ({ page }) => {
  // Bug real (Ronda 43, confirmación): Blob.text() decodifica siempre como
  // UTF-8, sin sniffear encoding — un CSV real en Latin-1/Windows-1252
  // (típico de un Excel guardado como "CSV" en Windows es-*) producía "�" en
  // nombre/dirección de cliente, con el import reportando éxito igual, sin
  // ningún aviso. Fixture generado con bytes reales Windows-1252 (María
  // Ñáñez, José Muñoz), no una simulación en UTF-8.
  const filePath = path.resolve(__dirname, "../examples/clientes_latin1.csv");
  await page.locator("#clients-file").setInputFiles(filePath);
  await expect(page.locator(".import-status")).toContainText("Se importaron 2 clientes");

  const firstCard = page.locator(".client-card").first();
  await firstCard.locator(".client-card-summary").click();
  await expect(firstCard.getByLabel("Nombre del cliente")).toHaveValue("María Ñáñez");
});

test("importa CSV en UTF-16 (export real de Excel) sin producir basura binaria", async ({ page }) => {
  // Bug real (Ronda 44): Excel en Windows ofrece "Guardar como CSV UTF-16
  // (delimitado por tabulaciones)" — un flujo de export real. La heurística
  // original de decodeCsvFile (solo mirar si aparece "�" y asumir
  // windows-1252) veía "�" en un archivo UTF-16 (por los bytes nulos entre
  // caracteres ASCII) y lo re-decodificaba como windows-1252, produciendo
  // basura peor que el original (cada byte como carácter separado) — ni
  // siquiera el header hacía match para detectar columnas. Fix: detectar el
  // BOM UTF-16 (FF FE / FE FF) ANTES de la heurística de "�" y decodificar
  // con el encoding correcto directamente.
  const filePath = path.resolve(__dirname, "../examples/clientes_utf16.csv");
  await page.locator("#clients-file").setInputFiles(filePath);
  await expect(page.locator(".import-status")).toContainText("Se importaron 2 clientes");

  const firstCard = page.locator(".client-card").first();
  await firstCard.locator(".client-card-summary").click();
  await expect(firstCard.getByLabel("Nombre del cliente")).toHaveValue("Peña");
});

test("un CSV genuinamente UTF-8 con un solo glifo � legítimo no se corrompe por reintento de encoding", async ({ page }) => {
  // Bug real (Ronda 44): la heurística original re-decodificaba TODO el
  // archivo como windows-1252 apenas veía un solo "�" en el texto UTF-8 — un
  // archivo bien formado que por casualidad tuviera ese glifo como dato
  // legítimo (ej. pegado de otra fuente) terminaba con cada tilde/ñ
  // corrompida por el reintento innecesario. Fix: exigir más de un "�" y una
  // proporción mínima antes de asumir que el archivo está mal decodificado.
  const filePath = path.resolve(__dirname, "../examples/clientes_glifo_legitimo.csv");
  await page.locator("#clients-file").setInputFiles(filePath);
  await expect(page.locator(".import-status")).toContainText("Se importaron 2 clientes");

  const firstCard = page.locator(".client-card").first();
  await firstCard.locator(".client-card-summary").click();
  await expect(firstCard.getByLabel("Nombre del cliente")).toHaveValue("Camión Grande �");
});

test("importa CSV Windows-1252 grande con pocas filas acentuadas sin corromper ñ/tildes", async ({ page }) => {
  // Bug real (Ronda 45): la heurística anterior de decodeCsvFile (contar "�"
  // y exigir una proporción mínima sobre el total de caracteres) fallaba en
  // un CSV grande mayormente ASCII (nombres sin tilde, común en datasets
  // reales) con solo un puñado de filas acentuadas — la proporción se
  // diluía por debajo de cualquier umbral fijo aunque el archivo estuviera
  // objetivamente mal decodificado. Fixture: 500 filas, solo 3 nombres con
  // ñ/tilde. Fix definitivo: en vez de contar/proporcionar apariciones de
  // "�", se usa `TextDecoder("utf-8", {fatal: true})` — lanza excepción si
  // el buffer no es UTF-8 válido (lo que SÍ pasa con bytes Windows-1252
  // reales, sin importar cuántos haya en el archivo), sin depender de
  // ningún umbral por tamaño.
  const filePath = path.resolve(__dirname, "../examples/clientes_latin1_diluido.csv");
  await page.locator("#clients-file").setInputFiles(filePath);
  await expect(page.locator(".import-status")).toContainText("Se importaron 499 clientes");

  const lastCard = page.locator(".client-card").last();
  await lastCard.locator(".client-card-summary").click();
  // Se espera "Peña Vasquez" pero el bug produce "Pe�a Vasquez" (encoding
  // corrupto, sin ningún aviso al usuario).
  await expect(lastCard.getByLabel("Nombre del cliente")).toHaveValue("Peña Vasquez");
});

test("importa CSV con columna id al final y celdas faltantes sin fusionar clientes distintos", async ({ page }) => {
  // Bug real (Ronda 39, operario): con `id` como última columna, una fila más
  // corta que el header (celda de id vacía/omitida, común sin coma trailing)
  // hacía que row[ci] fuera undefined → String(undefined) === "undefined"
  // (no vacío) — dos filas así compartían el mismo clientId "undefined" y se
  // fusionaban en un solo ClientGroup, perdiendo un cliente entero del import.
  const filePath = path.resolve(__dirname, "../examples/clientes_lima_id_final_faltante.csv");
  await page.locator("#clients-file").setInputFiles(filePath);
  // 2 clientes distintos, ninguno con id (ambos deberían caer en row-N, no colisionar).
  await expect(page.locator(".import-status")).toContainText("Se importaron 2 clientes");
  await expect(page.locator(".client-card")).toHaveCount(2);
});
