import { test, expect } from "@playwright/test";
import fs from "node:fs/promises";
import { createOwnerWithRepartidor } from "./helpers";

const API_BASE = "http://localhost:8000";

async function solveInstanceViaApi(page: import("@playwright/test").Page, token: string, instanciaId: string) {
  const res = await page.request.post(`${API_BASE}/solve`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      instancia_id: instanciaId,
      coordinates: [[10, 10], [20, 20]],
      demands: [10, 10],
      num_vehicles: 1,
      vehicle_capacity: 100,
      depot_coordinates: [0, 0],
    },
  });
  expect(res.ok()).toBeTruthy();
}

test("operario asigna repartidor y el repartidor marca una entrega, visible tras reload", async ({ page }) => {
  const { ownerToken, repartidorToken, repartidorUserId } = await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-lifecycle-${Date.now()}`;

  await solveInstanceViaApi(page, ownerToken, instanciaId);

  const assignRes = await page.request.put(`${API_BASE}/instances/${instanciaId}/assignments`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { assignments: { "0": repartidorUserId } },
  });
  expect(assignRes.ok()).toBeTruthy();

  const statusRes = await page.request.put(`${API_BASE}/instances/${instanciaId}/clients/1/status`, {
    headers: { Authorization: `Bearer ${repartidorToken}` },
    data: { status: "entregado" },
  });
  expect(statusRes.ok()).toBeTruthy();

  const myRouteRes = await page.request.get(`${API_BASE}/instances/${instanciaId}/my-route`, {
    headers: { Authorization: `Bearer ${repartidorToken}` },
  });
  const myRoute = await myRouteRes.json();
  const stop1 = myRoute.stops.find((s: { client_id: number }) => s.client_id === 1);
  expect(stop1.delivery_status).toBe("entregado");
});

test("recargar la página muestra la asignación de repartidor y el estado de entrega ya guardados", async ({ page }) => {
  // Bug real: SolutionSummary arrancaba siempre "Sin asignar" y "Pendiente"
  // sin importar lo que ya estuviera guardado en el backend — no había
  // ningún GET para hidratar assignments/delivery-statuses tras un reload.
  const suffix = `${Date.now()}`;
  const email = `owner-hydrate-${suffix}@test.local`;
  await page.goto("/");
  await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  await page.locator("#account-name").fill(`E2E Hydrate ${suffix}`);
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();

  const ownerToken = await page.evaluate(() => {
    const raw = localStorage.getItem("vrp:auth-token");
    return raw ? JSON.parse(raw).accessToken : null;
  });

  const inviteRes = await page.request.post(`${API_BASE}/auth/users`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { email: `repa-hydrate-${suffix}@test.local`, password: "clave123", role: "repartidor" },
  });
  const repartidorId = (await inviteRes.json()).id;

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
  await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15000 });

  await page.locator(".route-assign select").selectOption(repartidorId);
  await page.getByRole("button", { name: "Guardar asignaciones de repartidor" }).click();
  await expect(page.locator(".stop-save-indicator--saved")).toBeVisible();

  await page.locator(".delivery-status-select").first().selectOption("rechazado");
  await page.locator(".confirm-dialog-note-field textarea").fill("cliente pidió reprogramar");
  await page.getByRole("button", { name: "Confirmar" }).click();

  await page.reload();
  await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15000 });

  await expect(page.locator(".route-assign select")).toHaveValue(repartidorId);
  await expect(page.locator(".delivery-status-select").first()).toHaveValue("rechazado");
  await expect(page.locator(".delivery-status-note").first()).toContainText("cliente pidió reprogramar");
});

test("desasignar un repartidor y guardar persiste la desasignación tras recargar", async ({ page }) => {
  // Bug real: handleSaveAssignments mergeaba `{...latest, ...assignments}`
  // antes de guardar (fix de Ronda 23 para reducir conflictos entre
  // operarios) — pero un vehicle_id ausente en `assignments` local (porque
  // se acababa de desasignar) era indistinguible de "nunca lo toqué", así
  // que el merge resucitaba la asignación desde `latest` el 100% de las
  // veces, incluso sin ningún otro operario involucrado.
  const suffix = `${Date.now()}`;
  const email = `owner-unassign-${suffix}@test.local`;
  await page.goto("/");
  await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  await page.locator("#account-name").fill(`E2E Unassign ${suffix}`);
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();

  const ownerToken = await page.evaluate(() => {
    const raw = localStorage.getItem("vrp:auth-token");
    return raw ? JSON.parse(raw).accessToken : null;
  });

  const inviteRes = await page.request.post(`${API_BASE}/auth/users`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { email: `repa-unassign-${suffix}@test.local`, password: "clave123", role: "repartidor" },
  });
  const repartidorId = (await inviteRes.json()).id;

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
  await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15000 });

  await page.locator(".route-assign select").selectOption(repartidorId);
  await page.getByRole("button", { name: "Guardar asignaciones de repartidor" }).click();
  await expect(page.locator(".stop-save-indicator--saved")).toBeVisible();

  await page.locator(".route-assign select").selectOption("");
  await page.getByRole("button", { name: "Guardar asignaciones de repartidor" }).click();
  await expect(page.locator(".stop-save-indicator--saved")).toBeVisible();

  await page.reload();
  await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15000 });
  await expect(page.locator(".route-assign select")).toHaveValue("");
});

test("si el refresco previo a guardar asignaciones falla, se aborta con error en vez de arriesgar sobreescribir con datos incompletos", async ({ page }) => {
  // Bug real (Ronda 39, dueño): handleSaveAssignments refresca assignments
  // justo antes de guardar (para mergear sobre la base más fresca posible),
  // pero antes hacía `.catch(() => assignments)` — si ese GET fallaba,
  // caía silenciosamente al estado LOCAL, que si el fetch original de
  // montaje también había fallado (misma causa: mala conexión) podía estar
  // vacío. El PUT de abajo reemplaza el mapa COMPLETO en el backend, así que
  // esto podía borrar asignaciones reales ya guardadas sin ningún aviso — el
  // botón igual mostraba "✓ Guardado". Ahora un fallo acá aborta el guardado
  // con error visible.
  const suffix = `${Date.now()}`;
  const email = `owner-assign-refresh-fail-${suffix}@test.local`;
  await page.goto("/");
  await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  await page.locator("#account-name").fill(`E2E Assign Refresh Fail ${suffix}`);
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();

  const ownerToken = await page.evaluate(() => {
    const raw = localStorage.getItem("vrp:auth-token");
    return raw ? JSON.parse(raw).accessToken : null;
  });

  const inviteRes = await page.request.post(`${API_BASE}/auth/users`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { email: `repa-assign-refresh-fail-${suffix}@test.local`, password: "clave123", role: "repartidor" },
  });
  const repartidorId = (await inviteRes.json()).id;

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
  await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15000 });

  // Ahora que el GET de montaje ya resolvió, se fuerza a que falle el
  // próximo GET de assignments — el que dispara handleSaveAssignments justo
  // antes del PUT.
  await page.route("**/assignments", (route) => {
    if (route.request().method() === "GET") {
      route.fulfill({ status: 500, body: "{}" });
      return;
    }
    route.continue();
  });

  await page.locator(".route-assign select").selectOption(repartidorId);
  await page.getByRole("button", { name: "Guardar asignaciones de repartidor" }).click();

  // No debe mostrar éxito, y sí un error visible — el guardado se aborta.
  await expect(page.locator(".stop-save-indicator--saved")).not.toBeVisible();
  await expect(page.locator(".assign-actions .error-message")).toBeVisible();
});

test("dueño ve y cambia el estado de entrega desde la hoja de ruta resuelta", async ({ page }) => {
  const suffix = `${Date.now()}`;
  const email = `owner-ui-${suffix}@test.local`;
  await page.goto("/");
  await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  await page.locator("#account-name").fill(`E2E Lifecycle UI ${suffix}`);
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();

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

  const select = page.locator(".delivery-status-select").first();
  await select.selectOption("entregado");
  await expect(select).toHaveValue("entregado");

  // Volver desde un estado terminal ("entregado") a otro pide confirmación.
  await select.selectOption("pendiente");
  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();
  await page.getByRole("button", { name: "Cancelar" }).click();
  await expect(select).toHaveValue("entregado");

  await select.selectOption("pendiente");
  await page.getByRole("button", { name: "Confirmar" }).click();
  await expect(select).toHaveValue("pendiente");
});

test("una nota de un estado anterior no se arrastra a una transición sin nota, en el panel de dueño/operario", async ({ page }) => {
  // Bug real (Ronda 1, ciclo nuevo, operario): mismo bug ya arreglado en
  // RepartidorView.tsx (Ronda 43) pero nunca aplicado a DeliveryStatusControl
  // (usado acá, en el panel de escritorio de dueño/operario) — onConfirm
  // enviaba noteDraft sin importar si el estado destino admite nota o no, así
  // que la nota vieja de "Rechazado" viajaba en silencio a "Entregado".
  const suffix = `${Date.now()}`;
  const email = `owner-note-leak-${suffix}@test.local`;
  await page.goto("/");
  await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  await page.locator("#account-name").fill(`E2E Note Leak ${suffix}`);
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();

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

  const select = page.locator(".delivery-status-select").first();
  await select.selectOption("rechazado");
  const note = "No atendió, vecino avisado";
  await page.locator(".confirm-dialog-note-field textarea").fill(note);
  await page.getByRole("button", { name: "Confirmar" }).click();
  await expect(page.locator(".delivery-status-note").first()).toContainText(note);

  // Salir de "Rechazado" hacia "Entregado" — no admite nota, el textarea no
  // debe aparecer, y la nota vieja no debe sobrevivir.
  await select.selectOption("entregado");
  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();
  await expect(page.locator(".confirm-dialog-note-field textarea")).not.toBeVisible();
  await page.getByRole("button", { name: "Confirmar" }).click();

  await expect(select).toHaveValue("entregado");
  await expect(page.locator(".delivery-status-note").first()).toHaveCount(0);
});

test("si el PUT de estado se cuelga pero el backend ya lo aplicó, el select se resincroniza en vez de revertir a un valor viejo", async ({ page }) => {
  // Bug real (Ronda 51, repartidor): applyChange revertía SIEMPRE a `previous`
  // ante cualquier error, incluyendo un timeout de red — pero un timeout no
  // significa que el PUT no se haya aplicado (el UPDATE es idempotente, solo
  // tardó más en volver la respuesta que en ejecutarse). El operario veía el
  // valor VIEJO en el select con un mensaje de error, cuando el backend ya
  // tenía el valor nuevo guardado — desincronización silenciosa hasta el
  // próximo refresh completo de la instancia.
  test.setTimeout(45000);
  const suffix = `${Date.now()}`;
  const email = `owner-timeout-resync-${suffix}@test.local`;
  await page.goto("/");
  await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  await page.locator("#account-name").fill(`E2E Timeout Resync ${suffix}`);
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();

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

  const select = page.locator(".delivery-status-select").first();
  const selectAriaLabel = await select.getAttribute("aria-label");
  const clientId = selectAriaLabel?.match(/#(\d+)/)?.[1];

  // El PUT nunca responde (simula un timeout real) pero SÍ deja pasar el GET
  // de delivery-statuses — como si el backend hubiera aplicado el cambio y
  // solo la respuesta del PUT se hubiera perdido en la red.
  await page.route(`**/clients/${clientId}/status`, (route) => {
    if (route.request().method() === "PUT") return; // nunca resuelve
    route.continue();
  });
  await page.route("**/delivery-statuses", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ [clientId!]: { status: "entregado" } }),
    })
  );

  await select.selectOption("entregado");
  await expect(page.locator(".delivery-status-error")).toContainText("tardó demasiado", { timeout: 20000 });
  // Resincronizado con el valor real del backend (entregado), no revertido
  // al valor local previo (pendiente).
  await expect(select).toHaveValue("entregado");
});

test("dueño corrige un dato de un cliente ya resuelto sin re-resolver, y luego elimina la instancia", async ({ page }) => {
  // Bug real: no había forma de corregir un error de tipeo (dirección,
  // teléfono, coordenada) en un cliente ya cargado sin re-resolver la
  // instancia entera desde cero, perdiendo los estados de entrega ya
  // marcados. Tampoco había forma de eliminar una instancia de prueba.
  const suffix = `${Date.now()}`;
  const email = `owner-editclient-${suffix}@test.local`;
  await page.goto("/");
  await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  await page.locator("#account-name").fill(`E2E EditClient ${suffix}`);
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();

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

  await page.locator(".route-stop").first().getByRole("button", { name: "Editar" }).click();
  const editControl = page.locator(".client-edit-control");
  await editControl.locator("input").first().fill("Cliente Corregido");
  await editControl.getByRole("button", { name: "Guardar" }).click();
  await expect(page.locator(".route-stop-name").first()).toContainText("Cliente Corregido");

  await page.getByRole("button", { name: "Eliminar instancia" }).click();
  await expect(page.getByRole("heading", { name: "Eliminar instancia" })).toBeVisible();
  await page.getByRole("button", { name: "Confirmar" }).click();
  await expect(page.locator(".solution-summary")).not.toBeVisible();
});

test("editar la coordenada de un cliente avisa que la ruta quedó desactualizada, incluso en la segunda edición tras resolver de nuevo", async ({ page }) => {
  // Bug real: el aviso de "ruta desactualizada" comparaba contra el
  // `contact` previo del frontend — tras "Resolver ahora"/"Resolver de
  // nuevo", App.tsx limpia `contacts` a null, así que la SEGUNDA vez que se
  // edita una coordenada en la misma sesión, `contact` es undefined y el
  // aviso dejaba de dispararse aunque la ruta mostrada quedara obsoleta de
  // nuevo — exactamente el caso que el aviso debía cubrir.
  const suffix = `${Date.now()}`;
  const email = `owner-stale-route-${suffix}@test.local`;
  await page.goto("/");
  await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  await page.locator("#account-name").fill(`E2E StaleRoute ${suffix}`);
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();

  const ownerToken = await page.evaluate(() => JSON.parse(localStorage.getItem("vrp:auth-token") ?? "{}").accessToken);
  const repaRes = await page.request.post("http://localhost:8000/auth/users", {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { email: `repa-staleroute-${suffix}@test.local`, password: "clave123", role: "repartidor" },
  });
  const repartidorId = (await repaRes.json()).id;

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

  await page.locator(".route-assign select").selectOption(repartidorId);
  await page.getByRole("button", { name: "Guardar asignaciones de repartidor" }).click();
  await expect(page.locator(".stop-save-indicator--saved")).toBeVisible();

  // Primera edición: cambia la coordenada X del primer cliente.
  await page.locator(".route-stop").first().getByRole("button", { name: "Editar" }).click();
  let editControl = page.locator(".client-edit-control");
  await editControl.locator("input").nth(3).fill("-77.08");
  await editControl.getByRole("button", { name: "Guardar" }).click();
  await expect(page.getByText("Corregiste la coordenada", { exact: false })).toBeVisible();

  await page.getByRole("button", { name: "Resolver de nuevo" }).click();
  await expect(page.getByText("Corregiste la coordenada", { exact: false })).not.toBeVisible();

  // Bug real: NN/SA puede recomponer completamente qué clientes caen en
  // cada vehicle_id al re-resolver — la asignación de repartidor de la
  // corrida anterior quedaba viva apuntando a una ruta distinta, sin
  // ningún aviso. El select debe quedar vacío tras el re-solve.
  await expect(page.locator(".route-assign select")).toHaveValue("");

  // Segunda edición, ya con `contacts` limpiado por App.tsx tras resolver —
  // el aviso debe reaparecer igual.
  await page.locator(".route-stop").first().getByRole("button", { name: "Editar" }).click();
  editControl = page.locator(".client-edit-control");
  await editControl.locator("input").nth(3).fill("-77.09");
  await editControl.getByRole("button", { name: "Guardar" }).click();
  await expect(page.getByText("Corregiste la coordenada", { exact: false })).toBeVisible();
});

test("reprogramar y resolver desde la UI, sin retipear clientes a mano", async ({ page }) => {
  // Bug real: reprogramar creaba la instancia nueva correctamente en el
  // backend, pero no había ningún botón/camino en la UI para resolverla —
  // el operario tendría que copiar coordenadas a mano en el formulario de
  // "instancia nueva" para volver a resolver, inviable con volumen real.
  const suffix = `${Date.now()}`;
  const email = `owner-reschedule-ui-${suffix}@test.local`;
  await page.goto("/");
  await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  await page.locator("#account-name").fill(`E2E Reschedule UI ${suffix}`);
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();

  const ownerToken = await page.evaluate(() => JSON.parse(localStorage.getItem("vrp:auth-token") ?? "{}").accessToken);
  const oldRepaRes = await page.request.post("http://localhost:8000/auth/users", {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { email: `repa-old-${suffix}@test.local`, password: "clave123", role: "repartidor" },
  });
  const oldRepartidorId = (await oldRepaRes.json()).id;
  const newRepaRes = await page.request.post("http://localhost:8000/auth/users", {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { email: `repa-new-${suffix}@test.local`, password: "clave123", role: "repartidor" },
  });
  const newRepartidorId = (await newRepaRes.json()).id;

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

  // Asigna y desasigna SIN GUARDAR — deja `explicitlyUnassigned` con esa
  // clave antes de reprogramar/resolver, exactamente el estado que la
  // instancia NUEVA no debería heredar.
  await page.locator(".route-assign select").selectOption(oldRepartidorId);
  await page.locator(".route-assign select").selectOption("");

  // Marcar un cliente entregado, el otro queda pendiente para reprogramar.
  await page.locator(".delivery-status-select").first().selectOption("entregado");

  await page.getByRole("button", { name: "Reprogramar pedidos no entregados" }).click();
  await expect(page.locator(".import-status")).toContainText("Se creó la instancia");

  const solveButton = page.getByRole("button", { name: /^Resolver ".*" ahora$/ });
  await expect(solveButton).toBeVisible();
  const solveButtonLabel = (await solveButton.textContent()) ?? "";
  const newInstanciaId = solveButtonLabel.match(/Resolver "(.*)" ahora/)?.[1];
  await solveButton.click();

  await expect(page.locator(".import-status")).toContainText("resuelta:");
  // Bug real (Ronda 6, ciclo nuevo, dueño): total_cost es distancia en
  // METROS — este mensaje mostraba el número crudo sin convertir ni
  // etiquetar (ej. "costo 45231.7"), inconsistente con el resto de la
  // pantalla, que siempre muestra distancia en km.
  await expect(page.locator(".import-status")).toContainText(/costo [\d.,]+ km/);
  await expect(solveButton).not.toBeVisible();

  // Bug real: `explicitlyUnassigned` (estado de "desasignaciones sin
  // guardar" agregado para el merge de assignments) sobrevivía al cambio de
  // instancia — SolutionSummary no se remonta al recibir la solución de la
  // reprogramada (onSolvedInstanceChange cambia `solution` sin cambiar el
  // componente). Sin resetearlo, esta asignación en la instancia NUEVA
  // podía borrarse a sí misma al guardar, arrastrando la desasignación
  // vieja de `oldRepartidorId` en la instancia ORIGINAL.
  await page.locator(".route-assign select").selectOption(newRepartidorId);
  await page.getByRole("button", { name: "Guardar asignaciones de repartidor" }).click();
  await expect(page.locator(".stop-save-indicator--saved")).toBeVisible();
  await expect(page.locator(".route-assign select")).toHaveValue(newRepartidorId);

  // Bug real: el panel de exportación/asignación se quedaba apuntando a la
  // instancia ORIGINAL tras resolver la reprogramada — sin forma de actuar
  // sobre la instancia nueva sin recargar y buscarla a mano. El nombre del
  // PDF exportado usa solution.instancia_id, así que confirma cuál instancia
  // está activa en el panel tras el fix.
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar PDF" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(`ruta_${newInstanciaId}.pdf`);
});

test("una parada reprogramada muestra un aviso visual en el panel del dueño/operario", async ({ page }) => {
  // Bug real (Ronda 47, operario): reschedule_instance mueve el cliente a
  // una instancia nueva y lo marca delivery_status="reprogramado" en la
  // ORIGINAL, pero route.sequence de la solución ya calculada seguía
  // listándolo como parada activa — sin ninguna marca visual (ETA en verde,
  // selector de repartidor operable como cualquier otra parada), sin ninguna
  // pista de que ya no pertenece a esta ruta.
  const suffix = `${Date.now()}`;
  const email = `owner-reprog-warning-${suffix}@test.local`;
  await page.goto("/");
  await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  await page.locator("#account-name").fill(`E2E Reprog Warning ${suffix}`);
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();

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

  await page.locator(".delivery-status-select").first().selectOption("no_encontrado");
  await page.getByRole("button", { name: "Confirmar" }).click();
  await page.getByRole("button", { name: "Reprogramar pedidos no entregados" }).click();
  await expect(page.locator(".import-status")).toContainText("Se creó la instancia");

  // Sin resolver la nueva instancia ni recargar — el panel sigue mostrando
  // la instancia ORIGINAL, con ambas paradas reprogramadas visibles (el
  // cliente marcado "no_encontrado" y el otro que seguía pendiente, ya que
  // reschedule mueve TODOS los no-terminales, no solo el que se tocó).
  await expect(page.locator(".route-stop--reprogramado")).toHaveCount(2);
  await expect(page.locator(".route-stop-reprogramado-warning").first()).toContainText("ya no forma parte de esta ruta");

  // Bug real (Ronda 48, operario): con TODAS las paradas de la única ruta
  // reprogramadas, el selector de repartidor del vehículo se veía idéntico a
  // una ruta activa, sin ningún aviso de que ese trabajo ya no existe.
  await expect(page.getByText(/Todos los pedidos de esta ruta fueron reprogramados/)).toBeVisible();

  // Bug real (Ronda 49, operario): los botones de export quedaban sin ningún
  // aviso aunque el archivo resultante fuera a salir sin ninguna fila de
  // reparto — un operario que no revisa el contenido podía pensar que el
  // export falló, en vez de entender que ya no queda trabajo pendiente.
  await expect(page.getByText(/el archivo exportado no va a tener filas de reparto/)).toBeVisible();

  // Bug real (Ronda 48, operario): exportar CSV/PDF seguía incluyendo las
  // paradas reprogramadas como si fueran trabajo real — inconsistencia entre
  // lo que ve el operario en pantalla (con el aviso) y lo que se le entrega
  // al repartidor. Con ambos clientes reprogramados, el CSV exportado no
  // debe tener ninguna fila de parada (solo el header).
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar CSV" }).click();
  const download = await downloadPromise;
  const csvPath = await download.path();
  const csvContent = await fs.readFile(csvPath!, "utf-8");
  const dataLines = csvContent.trim().split("\n").slice(1);
  expect(dataLines).toEqual([]);
});

test("reprogramar crea una nueva instancia con los pedidos no entregados", async ({ page }) => {
  const { ownerToken } = await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-reschedule-${Date.now()}`;
  await solveInstanceViaApi(page, ownerToken, instanciaId);

  await page.request.put(`${API_BASE}/instances/${instanciaId}/clients/1/status`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { status: "entregado" },
  });

  const rescheduleRes = await page.request.post(`${API_BASE}/instances/${instanciaId}/reschedule`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
  });
  expect(rescheduleRes.ok()).toBeTruthy();
  const body = await rescheduleRes.json();
  expect(body.rescheduled_client_ids).toEqual([2]);
});
