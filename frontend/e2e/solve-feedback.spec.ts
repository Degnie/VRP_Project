import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loginFreshAccount } from "./helpers";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test.beforeEach(async ({ page }) => {
  await loginFreshAccount(page);
});

test("el badge de salud indica cuál base de datos está caída, no solo 'degradada' genérico", async ({ page }) => {
  // Bug real (Ronda 7, ciclo nuevo, dueño): /health ya distingue postgresql/
  // mongodb por separado, pero HealthBadge solo leía data.status y mostraba
  // "API degradada" sin ninguna pista de cuál base falló — el dueño no podía
  // saber si podía seguir resolviendo rutas o no sin mirar logs del servidor.
  await page.route("**/health", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ status: "degraded", version: "test", postgresql: "ok", mongodb: "unavailable" }),
    })
  );
  await page.reload();
  await expect(page.locator(".health-badge")).toContainText("base de datos de soluciones no disponible");
});

test("resolver sin flota seleccionada muestra un mensaje, no falla en silencio", async ({ page }) => {
  await page.locator("#depot-x").fill("-77.035");
  await page.locator("#depot-y").fill("-12.0464");
  await page.getByRole("button", { name: "+ Agregar tipo de vehículo" }).click();
  await page.getByLabel("Nombre del vehículo").fill("Moto");
  await page.getByLabel("Capacidad de peso en kg").fill("30");
  await page.waitForTimeout(500); // deja que el diff-sync guarde el catálogo

  const firstCard = page.locator(".client-card").first();
  await firstCard.locator(".client-card-summary").click();
  await firstCard.locator(".field-row input").nth(0).fill("-77.03");
  await firstCard.locator(".field-row input").nth(1).fill("-12.05");
  await firstCard.locator('input[placeholder="kg"]').fill("5");

  // Sin cantidad de flota seleccionada (todas en 0) — buildInstanceRequest devuelve null.
  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  await expect(page.locator(".error-message")).toContainText("Seleccioná al menos un vehículo");
});

test("resolver con todos los clientes fuera de cobertura muestra un mensaje", async ({ page }) => {
  // Importar primero: el recálculo de "inCoverage" por cliente ocurre al
  // importar CSV y cuando cambia el polígono (useEffect sobre coveragePoints)
  // — no al editar X/Y a mano — así que dibujar la zona después del import
  // garantiza que el useEffect recalcule "fuera de cobertura" para todos.
  const filePath = path.resolve(__dirname, "../examples/clientes_lima_50.csv");
  await page.locator("#clients-file").setInputFiles(filePath);
  await expect(page.locator(".import-status")).toContainText("Se importaron 50 clientes");

  await page.getByRole("button", { name: "Dibujar zona de cobertura" }).click();
  const map = page.locator(".route-map");
  const box = await map.boundingBox();
  if (box) {
    // Triángulo minúsculo en la esquina superior izquierda — con 50 clientes
    // dispersos por Lima, ninguno cae en un área tan chica.
    await page.mouse.click(box.x + 5, box.y + 5);
    await page.mouse.click(box.x + 25, box.y + 5);
    await page.mouse.click(box.x + 5, box.y + 25);
  }
  await page.getByRole("button", { name: "Cerrar polígono" }).click();
  await expect(page.getByRole("button", { name: "Redibujar zona de cobertura" })).toBeVisible();

  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  await expect(page.locator(".error-message")).toContainText("No hay clientes válidos");
});

test("pedido cuyo peso supera la capacidad de cualquier vehículo muestra un mensaje (modo simple)", async ({ page }) => {
  // Bug real: un pedido de 500kg con N vehiculos de 100kg (total 300kg o
  // 1000kg, da igual) nunca podia asignarse a UN vehiculo — el solver lo
  // ignoraba en silencio (Python) o colgaba (NearestNeighbor C++, while(true)
  // sin salida). Ahora se corta antes de POST /solve.
  await page.locator("#depot-x").fill("-77.035");
  await page.locator("#depot-y").fill("-12.0464");
  await page.locator("#capacity").fill("100");

  const firstCard = page.locator(".client-card").first();
  await firstCard.locator(".client-card-summary").click();
  await firstCard.locator(".field-row input").nth(0).fill("-77.03");
  await firstCard.locator(".field-row input").nth(1).fill("-12.05");
  await firstCard.locator('input[placeholder="kg"]').fill("500");

  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  await expect(page.locator(".error-message")).toContainText("supera la capacidad");
});

test("resolver con datos válidos no muestra ningún mensaje de error", async ({ page }) => {
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
  await expect(page.locator(".error-message")).toHaveCount(0);
});

test("si localStorage está lleno tras resolver, se avisa en vez de perder la ruta en silencio", async ({ page }) => {
  // Bug real (Ronda 3, ciclo nuevo, dueño): igual que saveSession ya avisa si
  // la sesión no persiste, App.tsx ignoraba el valor de retorno de
  // writeStored al guardar instancia/solución/contactos tras resolver — con
  // una instancia grande, el payload puede superar la cuota de localStorage
  // (QuotaExceededError). Sin aviso, la ruta se ve bien en el momento pero
  // desaparece sin explicación al recargar la página más tarde.
  await page.evaluate(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key: string, value: string) {
      if (key.includes("vrp:last-solution")) throw new DOMException("quota exceeded", "QuotaExceededError");
      return original.call(this, key, value);
    };
  });

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
  await expect(page.locator(".error-message")).toContainText("no se pudo guardar localmente");
});

test("el ETA de una parada lejana en la secuencia refleja el tiempo de servicio acumulado real", async ({ page }) => {
  // Bug real (Ronda 5, ciclo nuevo, operario): eta.ts dividía serviceMinutes
  // por 60 antes de sumarlo al acumulado, tratándolo como si estuviera en
  // horas cuando ya está en minutos — el tiempo de servicio acumulado
  // quedaba ~60x más chico del real. Con 8 min/parada, la parada #5 (índice
  // 4) debía sumar 32 min acumulados y solo sumaba ~0.53. Se intercepta OSRM
  // con duration=0 para que el ETA dependa EXCLUSIVAMENTE del acumulado de
  // servicio, sin variables de distancia/tráfico de por medio.
  await page.route("**/route/v1/driving/**", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        code: "Ok",
        routes: [{ geometry: { type: "LineString", coordinates: [] }, duration: 0 }],
      }),
    })
  );

  await page.locator("#depot-x").fill("-77.035");
  await page.locator("#depot-y").fill("-12.0464");
  const cards = page.locator(".client-card");
  const coords: [string, string][] = [
    ["-77.01", "-11.90"], ["-77.02", "-11.95"], ["-77.03", "-12.00"], ["-77.04", "-12.05"], ["-77.05", "-12.10"],
  ];
  for (let i = 0; i < coords.length; i++) {
    await page.getByRole("button", { name: "+ Agregar cliente" }).click();
  }
  for (let i = 0; i < coords.length; i++) {
    const card = cards.nth(i);
    await card.locator(".client-card-summary").click();
    await card.locator(".field-row input").nth(0).fill(coords[i][0]);
    await card.locator(".field-row input").nth(1).fill(coords[i][1]);
    await card.locator('input[placeholder="kg"]').fill("5");
  }

  await page.getByRole("button", { name: /Resolver instancia/ }).click();
  await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15_000 });

  // serviceMinutes por defecto es 8. Salida 09:00. Con durationSeconds=0,
  // arrivalMinutes de la parada de índice i = 540 + i*8 (sin sesgo del bug).
  // La 5ta parada (índice 4) del vehículo: 540 + 32 = 572 min = 09:32,
  // +/- colchón mínimo 2.5 min → ventana 09:30–09:35. Con el bug (división
  // por 60), el acumulado real era ~0.53 min en vez de 32 — la ventana
  // mostrada hubiese sido ~09:00, mucho antes de lo real.
  const stopEtas = page.locator(".route-stop-eta");
  await expect(stopEtas.nth(4)).toHaveText("09:30–09:35");
});

test("si OSRM no responde, se avisa que los horarios no son confiables en vez de mostrarlos como normales", async ({ page }) => {
  // Bug real (Ronda 12, ciclo nuevo, dueño): cuando OSRM no responde (caído,
  // no configurado, lento), fetchRouteWithDuration caía a durationSeconds=0
  // en silencio — eta.ts lo usaba igual, mostrando horarios "normales" con
  // tiempo de viaje CERO, indistinguibles del disclaimer de "aproximado" ya
  // existente (que cubre otra cosa: la aproximación esperada del cálculo).
  await page.route("**/route/v1/driving/**", (route) => route.abort("failed"));

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
  await expect(
    page.locator(".volume-warning-message").filter({ hasText: "no reflejan el tiempo de viaje real" })
  ).toBeVisible();
});

test("si el solve usó distancia euclídea (sin OSRM), se avisa que el costo/rutas son aproximados", async ({ page }) => {
  // Bug real (Ronda 13, ciclo nuevo, dueño y operario, hallado
  // independientemente por ambos): used_osrm=false llegaba en la respuesta
  // de /solve pero SolutionSummary no lo leía — el costo total se mostraba
  // igual que un cálculo con calles reales, sin ningún aviso de que en
  // realidad se calculó en línea recta.
  await page.route("**/solve", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch();
    const body = await response.json();
    body.used_osrm = false;
    await route.fulfill({ response, json: body });
  });

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
  await expect(
    page.locator(".volume-warning-message").filter({ hasText: "no estaba disponible al resolver" })
  ).toBeVisible();
});

test("resolver que tarda más de 15s (pero menos de 2 minutos) no muestra un timeout falso", async ({ page }) => {
  // Bug real (Ronda 51, dueño y operario, medido independientemente por
  // ambos con instancias reales de 400-500 clientes tardando 16-25s): el
  // timeout de 15s de request() era GLOBAL, cortando también /solve — el
  // frontend abortaba una resolución que estaba funcionando bien y a punto
  // de terminar, mostrando un error falso de "tardó demasiado". Fix:
  // SOLVE_TIMEOUT_MS (120s) específico para /solve, solveExistingInstance.
  // Se simula la demora real dejando pasar la request real y retrasando
  // solo el momento de entregar la respuesta al navegador.
  test.setTimeout(40000);
  await page.route("**/solve", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch();
    await new Promise((resolve) => setTimeout(resolve, 16000));
    await route.fulfill({ response });
  });

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
  await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 30000 });
  await expect(page.locator(".error-message")).toHaveCount(0);
});
