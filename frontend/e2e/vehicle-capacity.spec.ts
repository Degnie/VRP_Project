import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loginFreshAccount } from "./helpers";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test.beforeEach(async ({ page }) => {
  await loginFreshAccount(page);
});

test("el aviso de volumen (no bloqueante) se muestra distinto de un error real que sí bloquea", async ({ page }) => {
  // Bug real (Ronda 9, ciclo nuevo, dueño): el aviso de volumen es solo
  // informativo (el solver es peso-only, no bloquea el submit) pero
  // compartía la misma clase .error-message/role="alert" que los errores
  // que sí bloquean — un dueño con flota mixta lo veía en cada pedido normal
  // (volumen de un cliente > vehículo más chico, cubierto por uno grande),
  // entrenándolo a ignorar carteles rojos.
  await page.locator("#depot-x").fill("-77.035");
  await page.locator("#depot-y").fill("-12.0464");
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();
  await page.getByLabel("Nombre del vehículo").fill("Moto");
  await page.getByLabel("Capacidad de peso en kg").fill("30");
  await page.getByLabel("Capacidad de volumen en metros cúbicos").fill("0.05");
  await page.waitForTimeout(300);
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();
  await page.getByLabel("Nombre del vehículo").nth(1).fill("Camioneta");
  await page.getByLabel("Capacidad de peso en kg").nth(1).fill("500");
  await page.getByLabel("Capacidad de volumen en metros cúbicos").nth(1).fill("5");
  await page.waitForTimeout(300);
  await page.getByLabel(/Cantidad disponible de Moto/).fill("1");
  await page.getByLabel(/Cantidad disponible de Camioneta/).fill("1");

  const firstCard = page.locator(".client-card").first();
  await firstCard.locator(".client-card-summary").click();
  await firstCard.locator(".field-row input").nth(0).fill("-77.03");
  await firstCard.locator(".field-row input").nth(1).fill("-12.05");
  await firstCard.locator('input[placeholder="kg"]').fill("5");
  // Volumen 0.5x0.5x0.5 = 0.125 m³, mayor que la moto (0.05) pero menor que
  // la camioneta (5) — un pedido perfectamente resoluble, no un error real.
  await firstCard.locator('input[placeholder="largo cm"]').fill("50");
  await firstCard.locator('input[placeholder="ancho cm"]').fill("50");
  await firstCard.locator('input[placeholder="alto cm"]').fill("50");

  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  await expect(page.locator(".volume-warning-message").filter({ hasText: "excede la capacidad del vehículo más chico" })).toBeVisible();
  await expect(page.locator(".error-message")).toHaveCount(0);
  await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15_000 });
});

test("un cliente agregado a mano sin X/Y avisa cuántos quedaron fuera de la resolución", async ({ page }) => {
  // Bug real (Ronda 9, ciclo nuevo, operario): a diferencia del import CSV
  // (que sí avisa filas omitidas), un cliente agregado a mano sin X/Y
  // cargados se descartaba del submit en silencio — la fila colapsada no
  // muestra X/Y, así que se ve idéntica a un cliente completo. El operario
  // podía resolver y mandar una ruta con menos pedidos de los que cargó.
  await page.locator("#depot-x").fill("-77.035");
  await page.locator("#depot-y").fill("-12.0464");

  const firstCard = page.locator(".client-card").first();
  await firstCard.locator(".client-card-summary").click();
  await firstCard.locator(".field-row input").nth(0).fill("-77.03");
  await firstCard.locator(".field-row input").nth(1).fill("-12.05");
  await firstCard.locator('input[placeholder="kg"]').fill("5");
  // Las otras 2 filas por defecto (row-1, row-2) quedan sin X/Y cargados.

  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  await expect(page.locator(".volume-warning-message")).toContainText("2 clientes sin X/Y cargados");
  await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15_000 });
});

test("Flota disponible hoy muestra la capacidad EFECTIVA (con margen), no la nominal", async ({ page }) => {
  // Bug real (Ronda 8, ciclo nuevo, dueño): el solver usa la capacidad
  // ajustada por margen de tolerancia (buildInstance.ts hace ese mismo
  // cálculo para vehicle_capacities), pero esta pantalla mostraba la
  // nominal — con un margen de 90%, el dueño veía "1000 kg combinados"
  // cuando el solver en realidad planifica contra 900 kg, sin ningún aviso.
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();
  await page.getByLabel("Nombre del vehículo").fill("Camioneta");
  await page.getByLabel("Capacidad de peso en kg").fill("1000");
  await page.getByLabel("Margen de tolerancia en porcentaje").fill("90");
  await page.waitForTimeout(500);
  await page.getByLabel(/Cantidad disponible de Camioneta/).fill("1");

  await expect(page.locator(".fleet-vehicle-spec")).toContainText("900 kg efectivos");
  await expect(page.locator(".fleet-summary")).toContainText("900 kg efectivos combinados");
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

test("la pantalla de resultados muestra la capacidad del vehículo, no solo su número", async ({ page }) => {
  // Bug real (Ronda 18, ciclo nuevo, operario): con flota heterogénea de 3+
  // tipos, la pantalla de resultados solo mostraba "Vehículo N" sin ningún
  // indicio de qué tipo/capacidad le tocó — imposible saber a ojo cuál ruta
  // es la moto (capacidad chica) para no sobrecargarla al reasignar. El
  // nombre del tipo no llega hasta acá (se aplana a un array de números),
  // pero la capacidad sí — alcanza para distinguir vehículos a ojo.
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();
  await page.getByLabel("Nombre del vehículo").fill("Camioneta");
  await page.getByLabel("Capacidad de peso en kg").fill("200");
  await page.getByLabel(/Cantidad disponible de Camioneta/).fill("1");

  await page.locator("#depot-x").fill("-77.03");
  await page.locator("#depot-y").fill("-12.05");
  const firstCard = page.locator(".client-card").first();
  await firstCard.locator(".client-card-summary").click();
  await firstCard.locator(".field-row input").nth(0).fill("-77.06");
  await firstCard.locator(".field-row input").nth(1).fill("-11.98");
  await firstCard.locator('input[placeholder="kg"]').fill("5");

  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".route-vehicle-capacity")).toHaveText("(180 kg)");
});

test("importar catálogo con BOM UTF-8 y una celda en Windows-1252 no rompe la detección de columnas", async ({ page }) => {
  // Bug real (Ronda 46, confirmación): un CSV "UTF-8 con BOM" con alguna
  // celda en bytes Windows-1252 (mixed encoding, típico de un export de
  // Excel con una celda pegada de otra fuente) disparaba el fallback a
  // windows-1252 en decodeCsvFile — pero ese decoder no sabe descartar el
  // BOM UTF-8 (EF BB BF), así que quedaba pegado como "ï»¿" al primer header
  // ("ï»¿peso_kg" en este fixture, con orden de columnas no-default a
  // propósito para que el fallback posicional NO enmascare el bug), sin
  // matchear ningún alias de columna. El header terminaba procesado como
  // fila de datos, y las filas reales se leían con las columnas cruzadas
  // (nombre interpretado como peso, peso interpretado como nombre),
  // corrompiendo el import silenciosamente.
  const filePath = path.resolve(__dirname, "../examples/flota_bom_mixto.csv");
  await page.locator("#vehicles-file").setInputFiles(filePath);
  await expect(page.locator(".import-status")).toContainText("Se importaron 2 tipos de vehículo");
  await expect(page.getByLabel("Nombre del vehículo").first()).toHaveValue("Camión");
  await expect(page.getByLabel("Capacidad de peso en kg").first()).toHaveValue("1000");
});

test("importar catálogo con volumen decimal (ej. 0.15 m³) no bloquea el submit en silencio", async ({ page }) => {
  // Bug real encontrado: el input de volumen tenía step="0.1", así que un
  // valor como 0.15 (común en CSVs reales de flota) lo dejaba "inválido" para
  // el navegador — el <form> nunca disparaba submit, sin ningún mensaje en
  // la UI de React (bloqueo 100% nativo del navegador, antes de handleSubmit).
  const filePath = path.resolve(__dirname, "../examples/flota_vehiculos.csv");
  await page.locator("#vehicles-file").setInputFiles(filePath);
  await expect(page.locator(".import-status")).toContainText("Se importaron 4 tipos de vehículo");

  await page.locator("#depot-x").fill("-77.03");
  await page.locator("#depot-y").fill("-12.05");
  const firstCard = page.locator(".client-card").first();
  await firstCard.locator(".client-card-summary").click();
  await firstCard.locator(".field-row input").nth(0).fill("-77.06");
  await firstCard.locator(".field-row input").nth(1).fill("-11.98");
  await firstCard.locator('input[placeholder="kg"]').fill("5");

  await page.getByLabel(/Cantidad disponible de Moto/).first().fill("2");

  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15000 });
});

test("importar catálogo con una fila que falla en el backend no descarta las filas que sí se guardaron", async ({ page }) => {
  // Bug real (Ronda 38, operario): un `for` con `await` sin try/catch por
  // fila hacía que el POST fallido de una fila intermedia cortara toda la
  // función — las filas anteriores YA quedaban creadas en el backend, pero
  // el throw impedía devolverlas, así que la UI no mostraba ninguna y el
  // mensaje decía "archivo inválido" (falso). Reintentar el mismo archivo
  // duplicaba las filas que sí habían entrado la primera vez.
  let postCount = 0;
  await page.route("**/vehicle-catalog", (route) => {
    if (route.request().method() === "POST") {
      postCount += 1;
      if (postCount === 2) {
        route.fulfill({ status: 500, body: "{}" });
        return;
      }
    }
    route.continue();
  });

  const filePath = path.resolve(__dirname, "../examples/flota_vehiculos.csv");
  await page.locator("#vehicles-file").setInputFiles(filePath);

  // La segunda fila del CSV falla; las demás (1ra, 3ra, 4ta) sí se crean y
  // deben verse en la tabla — no un mensaje genérico de "archivo inválido".
  await expect(page.locator(".import-status")).toContainText("Se importaron 3 tipos de vehículo");
  await expect(page.locator(".import-status")).toContainText("No se pudieron guardar en el servidor");
  await expect(page.getByLabel("Nombre del vehículo")).toHaveCount(3);
});
