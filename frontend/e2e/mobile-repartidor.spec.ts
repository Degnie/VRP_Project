import { test, expect } from "@playwright/test";
import { createOwnerWithRepartidor } from "./helpers";

const API_BASE = "http://localhost:8000";

test.use({ viewport: { width: 390, height: 844 } });

async function solveAndAssign(
  page: import("@playwright/test").Page,
  ownerToken: string,
  repartidorUserId: string,
  instanciaId: string
) {
  const solveRes = await page.request.post(`${API_BASE}/solve`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: {
      instancia_id: instanciaId,
      coordinates: [[10, 10], [20, 20]],
      demands: [10, 10],
      num_vehicles: 1,
      vehicle_capacity: 100,
      depot_coordinates: [0, 0],
    },
  });
  expect(solveRes.ok()).toBeTruthy();

  const assignRes = await page.request.put(`${API_BASE}/instances/${instanciaId}/assignments`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { assignments: { "0": repartidorUserId } },
  });
  expect(assignRes.ok()).toBeTruthy();
}

async function loginRepartidorInBrowser(
  page: import("@playwright/test").Page,
  email: string,
  password: string
) {
  await page.goto("/");
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill(password);
  await page.getByRole("button", { name: "Entrar" }).click();
}

test("sin ninguna instancia asignada, se avisa en vez de dejar el select vacío sin explicación", async ({ page }) => {
  // Bug real (Ronda 3, ciclo nuevo, repartidor): una carga exitosa con 0
  // instancias asignadas (todavía no le crearon la ruta de hoy) era
  // indistinguible de "la app no cargó bien" — solo se veía el placeholder
  // "Elegí una instancia…" en el select, sin ningún mensaje.
  const { repartidorEmail, repartidorPassword } = await createOwnerWithRepartidor(page);
  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);

  await expect(page.getByText("Todavía no tenés ninguna ruta asignada.")).toBeVisible();
});

test("repartidor en mobile ve RepartidorView, no el sidebar de escritorio", async ({ page }) => {
  const { repartidorEmail, repartidorPassword } = await createOwnerWithRepartidor(page);
  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);

  await expect(page.getByRole("heading", { name: "Mi ruta" })).toBeVisible();
  await expect(page.locator(".app-sidebar")).not.toBeVisible();
  await expect(page.locator("#instancia-id")).not.toBeVisible();
});

test("repartidor en mobile elige instancia, ve paradas y marca una entrega", async ({ page }) => {
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);

  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const firstStop = page.locator(".repartidor-stop").first();
  await firstStop.getByRole("button", { name: "Entregado" }).click();
  await expect(firstStop.getByRole("button", { name: "Entregado" })).toHaveClass(/repartidor-status-btn--active/);
  await expect(firstStop.locator(".stop-save-indicator--saved")).toBeVisible();
});

test("el link de llamada limpia el teléfono a solo dígitos, aunque venga con texto pegado", async ({ page }) => {
  // Bug real (Ronda 6, ciclo nuevo, repartidor): customer_phone es texto
  // libre sin ninguna validación en el pipeline — un dato "sucio" de un
  // import descuidado ("999888777 (casa)") viajaba intacto al href de
  // tel:, arriesgando que el marcador nativo rechace el link completo en
  // vez de ignorar el sufijo. Se limpia a solo dígitos + "+" inicial.
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-phone-clean-${Date.now()}`;
  const solveRes = await page.request.post(`${API_BASE}/solve`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: {
      instancia_id: instanciaId,
      coordinates: [[10, 10], [20, 20]],
      demands: [10, 10],
      num_vehicles: 1,
      vehicle_capacity: 100,
      depot_coordinates: [0, 0],
      contacts: [{ customer_phone: "999888777 (casa)" }, null],
    },
  });
  expect(solveRes.ok()).toBeTruthy();
  await page.request.put(`${API_BASE}/instances/${instanciaId}/assignments`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { assignments: { "0": repartidorUserId } },
  });

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const phoneLink = page.locator(".repartidor-stop-link", { hasText: "999888777" });
  await expect(phoneLink).toHaveText("📞 999888777 (casa)");
  await expect(phoneLink).toHaveAttribute("href", "tel:999888777");
});

test("un teléfono sin ningún dígito no genera un link de llamada roto", async ({ page }) => {
  // Bug real (Ronda 13, ciclo nuevo, repartidor): customer_phone es texto
  // libre — si no tenía NINGÚN dígito (ej. "N/A", "preguntar en portería"),
  // el guard de renderizado (customer_phone no vacío) pasaba igual, pero el
  // resultado saneado a solo dígitos quedaba vacío: el botón se veía como un
  // teléfono válido pero abría "tel:" sin número al tocarlo.
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-phone-no-digits-${Date.now()}`;
  const solveRes = await page.request.post(`${API_BASE}/solve`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: {
      instancia_id: instanciaId,
      coordinates: [[10, 10], [20, 20]],
      demands: [10, 10],
      num_vehicles: 1,
      vehicle_capacity: 100,
      depot_coordinates: [0, 0],
      contacts: [{ customer_phone: "preguntar en portería" }, null],
    },
  });
  expect(solveRes.ok()).toBeTruthy();
  await page.request.put(`${API_BASE}/instances/${instanciaId}/assignments`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { assignments: { "0": repartidorUserId } },
  });

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  await expect(page.getByText("preguntar en portería")).toHaveCount(0);
});

test("no hay botón 'Reprogramado' manual en las paradas — es un estado derivado, no una acción del repartidor", async ({ page }) => {
  // Bug real (Ronda 15, ciclo nuevo, repartidor): STATUS_LABELS incluye
  // "reprogramado" (para el label del estado ya derivado), pero el .map()
  // de botones lo renderizaba igual que los otros cuatro — habilitado, sin
  // pedir confirmación (no es un TERMINAL_STATUSES como destino). Tocarlo
  // disparaba un PUT que el backend rechaza con 422 crudo en inglés
  // (MANUALLY_SETTABLE_DELIVERY_STATUSES lo excluye a propósito).
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-no-reprog-btn-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const firstStop = page.locator(".repartidor-stop").first();
  await expect(firstStop.getByRole("button", { name: "Reprogramado" })).toHaveCount(0);
});

test("una parada sin dirección muestra un placeholder claro en vez de desaparecer", async ({ page }) => {
  // Bug real (Ronda 5, ciclo nuevo, repartidor): {stop.address && (...)} sin
  // fallback hacía desaparecer el bloque entero cuando no había dirección
  // (indistinguible de "no hay nada acá"), inconsistente con customer_name
  // que sí tiene fallback `Cliente #${id}`. Acá solveAndAssign no manda
  // contacts, así que address llega undefined — el caso real más común.
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-no-address-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  await expect(page.getByText("Sin dirección registrada").first()).toBeVisible();
});

test("marcar todas las paradas como entregadas muestra un aviso de ruta completa", async ({ page }) => {
  // Bug real (Ronda 3, ciclo nuevo, repartidor): mismo patrón que el aviso ya
  // existente para "todo reprogramado" (Ronda 47), generalizado al caso más
  // común — terminar la ruta del día se veía igual que una ruta a medio
  // hacer, sin ninguna señal de "ya no queda nada por marcar".
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-complete-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  const stops = page.locator(".repartidor-stop");
  await expect(stops).toHaveCount(2);

  for (let i = 0; i < 2; i++) {
    await stops.nth(i).getByRole("button", { name: "Entregado" }).click();
    await expect(stops.nth(i).getByRole("button", { name: "Entregado" })).toHaveClass(/repartidor-status-btn--active/);
  }

  await expect(page.getByText("Ruta de hoy completa — no quedan paradas pendientes.")).toBeVisible();
});

test("un PUT de estado que se cuelga (nunca responde) termina en error en vez de 'Guardando…' para siempre", async ({ page }) => {
  // Bug real (Ronda 50, repartidor): fetch() en lib/api.ts no tenía timeout
  // ni AbortController — si el PUT se colgaba (no un error de red, una
  // conexión que nunca cierra: proxy intermedio, backend caído a medias),
  // la promesa no resolvía ni rechazaba nunca. El botón quedaba en
  // "Guardando…" para siempre, sin error, sin forma de reintentar salvo
  // recargar la página. Fix: AbortController con timeout de 15s en request().
  test.setTimeout(30000);
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-hang-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  // El PUT de status nunca responde — page.route sin .fulfill()/.continue()
  // dentro del handler deja la petición pendiente indefinidamente.
  await page.route(`**/instances/${instanciaId}/clients/*/status`, () => {});

  const firstStop = page.locator(".repartidor-stop").first();
  await firstStop.getByRole("button", { name: "Entregado" }).click();
  await expect(firstStop.locator(".stop-save-indicator")).toBeVisible();

  await expect(page.locator(".error-message")).toContainText("tardó demasiado", { timeout: 20000 });
  await expect(firstStop.getByRole("button", { name: "Entregado" })).toBeEnabled();
});

test("si el PUT de estado se cuelga pero el backend ya lo aplicó, la parada se resincroniza en vez de quedar en el valor viejo", async ({ page }) => {
  // Bug real (Ronda 16, ciclo nuevo, repartidor): DeliveryStatusControl.tsx
  // (vista de escritorio) ya resincroniza contra el estado real del backend
  // cuando el error es de red/timeout (el PUT es idempotente, puede haber
  // llegado igual) — RepartidorView.tsx, el componente donde "mala señal"
  // es más probable, no tenía ese mismo manejo: un timeout dejaba la parada
  // mostrando el estado VIEJO sin ningún indicio de que sí se guardó.
  test.setTimeout(30000);
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-resync-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  // El PUT nunca responde al navegador, pero SÍ llega al backend real
  // (route.fetch() dispara la request de verdad antes de colgar la respuesta).
  await page.route(`**/instances/${instanciaId}/clients/*/status`, async (route) => {
    await route.fetch();
    // No fulfill — la respuesta al navegador nunca llega, dispara el timeout.
  });

  const firstStop = page.locator(".repartidor-stop").first();
  await firstStop.getByRole("button", { name: "Entregado" }).click();
  await expect(page.locator(".error-message")).toContainText("tardó demasiado", { timeout: 20000 });

  // El backend YA aplicó el cambio (el fetch real llegó) — la parada debe
  // reflejar "Entregado" real, no revertir al valor viejo mostrado antes del click.
  await expect(firstStop.getByRole("button", { name: "Entregado" })).toHaveClass(/repartidor-status-btn--active/);
});

test("volver de un estado terminal a otro pide confirmación, cancelar no cambia nada", async ({ page }) => {
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-confirm-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const firstStop = page.locator(".repartidor-stop").first();
  await firstStop.getByRole("button", { name: "Entregado" }).click();
  await expect(firstStop.getByRole("button", { name: "Entregado" })).toHaveClass(/repartidor-status-btn--active/);

  // Volver a "Pendiente" desde un estado terminal ("Entregado") pide confirmación.
  await firstStop.getByRole("button", { name: "Pendiente" }).click();
  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();

  await page.getByRole("button", { name: "Cancelar" }).click();
  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).not.toBeVisible();
  await expect(firstStop.getByRole("button", { name: "Entregado" })).toHaveClass(/repartidor-status-btn--active/);

  // Confirmar sí aplica el cambio.
  await firstStop.getByRole("button", { name: "Pendiente" }).click();
  await page.getByRole("button", { name: "Confirmar" }).click();
  await expect(firstStop.getByRole("button", { name: "Pendiente" })).toHaveClass(/repartidor-status-btn--active/);
});

test("marcar Rechazado pide confirmación con nota, y la nota queda visible en la parada", async ({ page }) => {
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-rechazado-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const firstStop = page.locator(".repartidor-stop").first();
  await firstStop.getByRole("button", { name: "Rechazado" }).click();
  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();

  const note = "No tenía el monto exacto, vuelve mañana";
  await page.locator(".confirm-dialog-note-field textarea").fill(note);
  await page.getByRole("button", { name: "Confirmar" }).click();

  await expect(firstStop.getByRole("button", { name: "Rechazado" })).toHaveClass(/repartidor-status-btn--active/);
  await expect(firstStop.locator(".repartidor-stop-note")).toContainText(note);
});

test("una nota de un estado anterior no se arrastra a una transición que no admite nota", async ({ page }) => {
  // Bug real (Ronda 43, confirmación): handleStatusChange precarga noteDraft
  // con la nota YA existente de la parada para no perderla de vista al
  // reabrir el mismo estado — pero eso incluía transiciones que salen de un
  // estado terminal hacia uno SIN campo de nota (ej. Rechazado con nota →
  // Entregado). El textarea no se renderizaba ahí, pero la nota vieja viajaba
  // igual adjunta al nuevo estado sin que el repartidor la viera ni pudiera
  // editarla/borrarla.
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-note-no-arrastre-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const firstStop = page.locator(".repartidor-stop").first();
  await firstStop.getByRole("button", { name: "Rechazado" }).click();
  const note = "No atendió, vecino avisado";
  await page.locator(".confirm-dialog-note-field textarea").fill(note);
  await page.getByRole("button", { name: "Confirmar" }).click();
  await expect(firstStop.locator(".repartidor-stop-note")).toContainText(note);

  // Salir del estado terminal "Rechazado" hacia "Entregado" — no admite nota,
  // el textarea no debe aparecer, y la nota vieja no debe sobrevivir.
  await firstStop.getByRole("button", { name: "Entregado" }).click();
  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();
  await expect(page.locator(".confirm-dialog-note-field textarea")).not.toBeVisible();
  await page.getByRole("button", { name: "Confirmar" }).click();

  await expect(firstStop.getByRole("button", { name: "Entregado" })).toHaveClass(/repartidor-status-btn--active/);
  await expect(firstStop.locator(".repartidor-stop-note")).toHaveCount(0);
});

test("tocar fuera del diálogo de confirmación no lo cierra ni descarta la nota", async ({ page }) => {
  // Bug real (Ronda 1, ciclo nuevo, repartidor): el overlay cerraba el
  // diálogo (= Cancelar, sin aplicar el cambio) con un solo tap fuera de la
  // caja central. En mobile, con una mano ocupada, un toque que no acierta
  // el textarea o "Confirmar" caía fuera de la caja y descartaba la nota en
  // silencio, sin ningún aviso.
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-overlay-tap-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const firstStop = page.locator(".repartidor-stop").first();
  await firstStop.getByRole("button", { name: "Rechazado" }).click();
  const note = "No atendió, vuelvo más tarde";
  await page.locator(".confirm-dialog-note-field textarea").fill(note);

  // Tap fuera de la caja del diálogo, dentro del overlay.
  await page.locator(".confirm-dialog-overlay").click({ position: { x: 5, y: 5 } });

  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();
  await expect(page.locator(".confirm-dialog-note-field textarea")).toHaveValue(note);

  await page.getByRole("button", { name: "Confirmar" }).click();
  await expect(firstStop.locator(".repartidor-stop-note")).toContainText(note);
});

test("recargar la página con un cambio de estado sin confirmar restaura el diálogo con la nota", async ({ page }) => {
  // Bug real: la nota en curso de un cambio de estado (ej. motivo de un
  // "Rechazado") se perdía sin aviso si la sesión expiraba a mitad del
  // tipeo o si el repartidor volvía atrás — ambos casos desmontan
  // RepartidorView. Se simula con un reload, que también desmonta/remonta.
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-persist-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const firstStop = page.locator(".repartidor-stop").first();
  await firstStop.getByRole("button", { name: "Rechazado" }).click();
  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();

  const note = "No atendió, vuelvo en la tarde";
  await page.locator(".confirm-dialog-note-field textarea").fill(note);

  await page.reload();

  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();
  await expect(page.locator(".confirm-dialog-note-field textarea")).toHaveValue(note);

  await page.getByRole("button", { name: "Confirmar" }).click();
  await expect(page.locator(".repartidor-stop").first().getByRole("button", { name: "Rechazado" })).toHaveClass(
    /repartidor-status-btn--active/
  );
});

test("cambiar de instancia con un cambio de estado sin confirmar queda bloqueado hasta resolver el diálogo", async ({ page }) => {
  // Bug real (evolucionado en dos rondas): primero el pendingChange
  // restaurado/activo no se validaba contra la ruta cargada — cambiar de
  // instancia con el diálogo de "Rechazado" abierto en la instancia A dejaba
  // el diálogo abierto igual sobre la instancia B, referenciando un
  // client_id que no le pertenece. Luego (Ronda 25) se encontró que incluso
  // con esa validación, la ventana de carga de la ruta nueva permitía
  // confirmar contra route=null, descartando la nota en silencio. Fix
  // final: el selector se bloquea mientras el diálogo está abierto.
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaA = `e2e-mobile-switch-a-${Date.now()}`;
  const instanciaB = `e2e-mobile-switch-b-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaA);
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaB);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaA);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  await page.locator(".repartidor-stop").first().getByRole("button", { name: "Rechazado" }).click();
  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();
  await expect(page.locator("#instance-select")).toBeDisabled();

  await page.getByRole("button", { name: "Cancelar" }).click();
  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).not.toBeVisible();
  await expect(page.locator("#instance-select")).toBeEnabled();

  await page.locator("#instance-select").selectOption(instanciaB);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);
  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).not.toBeVisible();
});

test("repartidor en mobile puede exportar su hoja en PDF", async ({ page }) => {
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-pdf-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar mi hoja en PDF" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^mi_ruta_.*\.pdf$/);
});

test("exportar PDF que se cuelga (nunca responde) termina en error en vez de 'Generando PDF…' para siempre", async ({ page }) => {
  // Bug real (Ronda 2, ciclo nuevo, repartidor): exportSolutionPdf en api.ts
  // usaba un fetch crudo que no pasaba por request(), así que no tenía el
  // mismo timeout/AbortController que el resto de los endpoints — una
  // conexión colgada dejaba el botón en "Generando PDF…" para siempre.
  test.setTimeout(30000);
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-pdf-hang-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  await page.route(`**/solutions/${instanciaId}/export.pdf*`, () => {});

  await page.getByRole("button", { name: "Exportar mi hoja en PDF" }).click();
  await expect(page.locator(".error-message")).toContainText("tardó demasiado", { timeout: 20000 });
});

test("el selector de instancia del repartidor solo lista las asignadas a él, con fecha legible", async ({ page }) => {
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const assignedId = `e2e-assigned-${Date.now()}`;
  const unassignedId = `e2e-unassigned-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, assignedId);

  // Segunda instancia resuelta por el dueño, pero nunca asignada al repartidor.
  const solveRes = await page.request.post(`${API_BASE}/solve`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: {
      instancia_id: unassignedId,
      coordinates: [[10, 10]],
      demands: [10],
      num_vehicles: 1,
      vehicle_capacity: 100,
      depot_coordinates: [0, 0],
    },
  });
  expect(solveRes.ok()).toBeTruthy();

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.getByRole("heading", { name: "Mi ruta" }).waitFor();

  const options = await page.locator("#instance-select option").allTextContents();
  expect(options.some((o) => o.startsWith(assignedId))).toBe(true);
  expect(options.some((o) => o.startsWith(unassignedId))).toBe(false);

  // El label incluye fecha legible, no solo el ID crudo.
  const assignedOption = options.find((o) => o.startsWith(assignedId));
  expect(assignedOption).toMatch(/—\s*\d{2}\/\d{2}/);
});

test("reintentar la carga de instancias no descarta un cambio de estado sin confirmar en curso", async ({ page }) => {
  // Bug real (Ronda 39, repartidor): loadInstances (montaje o "Reintentar")
  // deseleccionaba `selectedId` si la instancia ya no aparecía en la lista
  // devuelta por el GET — pero eso disparaba el efecto de [selectedId], que
  // al ver !selectedId limpiaba `route` Y `pendingChange` sin ningún aviso,
  // aunque el diálogo estuviera abierto con una nota recién escrita en ese
  // instante. Se simula la lista "sin la instancia actual" directamente por
  // mock (en vez de reasignar de verdad, que además invalidaría el propio
  // GET de la ruta con un 403 y confundiría la causa del descarte) para
  // aislar específicamente el guard de loadInstances.
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-reload-reassign-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const firstStop = page.locator(".repartidor-stop").first();
  await firstStop.getByRole("button", { name: "Rechazado" }).click();
  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();

  const note = "Perro suelto, vuelvo más tarde";
  await page.locator(".confirm-dialog-note-field textarea").fill(note);

  // Próxima carga de instancias devuelve la lista SIN la instancia actual
  // (simula reasignación) — la ruta (`my-route`) sigue intacta, así que el
  // único disparador de la limpieza sería el guard de loadInstances.
  await page.route("**/instances*", (route) => {
    if (route.request().method() === "GET") {
      route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }
    route.continue();
  });

  // loadInstances corre en el montaje — recargar dispara el mock de arriba
  // (lista vacía) mientras selectedId/pendingChange se restauran de
  // localStorage al mismo tiempo, reproduciendo la condición del bug.
  await page.reload();

  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();
  await expect(page.locator(".confirm-dialog-note-field textarea")).toHaveValue(note);
});

test("cerrar el diálogo de cambio de estado revalida si la instancia sigue asignada", async ({ page }) => {
  // Bug real (Ronda 40, repartidor): el guard de loadInstances (Ronda 39)
  // pospone deseleccionar la instancia mientras pendingChange está activo,
  // pero al cerrar el diálogo (confirmar o cancelar) nada volvía a
  // revalidar — si la instancia dejó de estar asignada MIENTRAS el diálogo
  // estaba abierto, el repartidor quedaba viendo la ruta vieja indefinidamente
  // (select con un value que ya no está entre las opciones), sin aviso.
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-dialog-revalidate-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const firstStop = page.locator(".repartidor-stop").first();
  await firstStop.getByRole("button", { name: "Rechazado" }).click();
  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();

  // Mientras el diálogo sigue abierto, el próximo loadInstances() (disparado
  // al cerrar el diálogo) devuelve la lista sin esta instancia — simula que
  // fue reasignada mientras el repartidor estaba escribiendo la nota.
  await page.route("**/instances*", (route) => {
    if (route.request().method() === "GET") {
      route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }
    route.continue();
  });

  await page.getByRole("button", { name: "Cancelar" }).click();

  // La instancia ya no está entre las asignadas — selectedId debe limpiarse
  // (el select vuelve a "Elegí una instancia…") en vez de seguir mostrando
  // la ruta vieja de una instancia que ya no le pertenece.
  await expect(page.locator("#instance-select")).toHaveValue("");
  await expect(page.locator(".repartidor-stop")).toHaveCount(0);
});

test("una parada reprogramada a otra instancia no permite marcar estados ni pide confirmación para nada", async ({ page }) => {
  // Bug real (Ronda 46, confirmación): reprogramar una instancia mueve el
  // pedido a una instancia nueva, pero get_my_route lo sigue devolviendo con
  // delivery_status="reprogramado" en la ruta VIEJA para siempre. Los botones
  // de estado seguían habilitados — el repartidor pasaba por todo el diálogo
  // de confirmación creyendo que era válido, y solo al confirmar se enteraba
  // vía un 409 del backend. Ahora los botones se deshabilitan y se avisa.
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-reprogramado-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  // Marca ambas paradas como no encontradas para que reschedule tenga algo
  // que mover, luego reprograma — la instancia vieja queda con ambos
  // clientes en delivery_status="reprogramado".
  await page.request.put(`${API_BASE}/instances/${instanciaId}/clients/1/status`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { status: "no_encontrado" },
  });
  await page.request.put(`${API_BASE}/instances/${instanciaId}/clients/2/status`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { status: "no_encontrado" },
  });
  const rescheduleRes = await page.request.post(`${API_BASE}/instances/${instanciaId}/reschedule`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
  });
  expect(rescheduleRes.ok()).toBeTruthy();

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const firstStop = page.locator(".repartidor-stop").first();
  await expect(firstStop.getByText(/fue reprogramado a otra instancia/)).toBeVisible();
  await expect(firstStop.getByRole("button", { name: "Entregado" })).toBeDisabled();

  // Bug real (Ronda 47): get_my_route sigue devolviendo las paradas
  // reprogramadas (por diseño), pero cuando TODA la ruta queda así, antes no
  // había ningún mensaje a nivel de ruta — solo N repeticiones del aviso
  // individual, sin explicar por qué la ruta entera se ve gris/inoperable.
  await expect(page.getByText("Todos los pedidos de esta instancia fueron reprogramados a otra instancia.")).toBeVisible();
});

test("confirmar un cambio de estado sobre una parada reprogramada mientras el diálogo ya estaba abierto sincroniza la UI en vez de repetir el 409 en silencio", async ({ page }) => {
  // Bug real (Ronda 47): si el diálogo de confirmación ya estaba abierto
  // sobre una parada CUANDO el dueño/operario la reprogramó, el PUT al
  // confirmar caía en 409 — pero route.stops en memoria se quedaba con el
  // estado viejo, así que ni el aviso ni el disabled de los botones se
  // activaban. El repartidor podía repetir el mismo 409 indefinidamente sin
  // que la UI reflejara jamás el bloqueo.
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-reprog-mid-dialog-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  const firstStop = page.locator(".repartidor-stop").first();
  await firstStop.getByRole("button", { name: "Rechazado" }).click();
  await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();

  // Mientras el diálogo sigue abierto, el cliente se reprograma a otra
  // instancia — el repartidor no lo sabe todavía.
  await page.request.put(`${API_BASE}/instances/${instanciaId}/clients/1/status`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { status: "no_encontrado" },
  });
  await page.request.post(`${API_BASE}/instances/${instanciaId}/reschedule`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
  });

  await page.getByRole("button", { name: "Confirmar" }).click();

  // La UI debe reflejar el bloqueo inmediatamente tras el 409 — sin esto,
  // el botón "Rechazado" seguía habilitado y tocarlo de nuevo repetía el
  // mismo 409 en un loop silencioso.
  await expect(firstStop.getByText(/fue reprogramado a otra instancia/)).toBeVisible();
  await expect(firstStop.getByRole("button", { name: "Rechazado" })).toBeDisabled();
});

test("si falla la carga inicial de instancias asignadas, se muestra un error con botón de reintentar", async ({ page }) => {
  // Bug real (Ronda 38, repartidor): el .catch(() => {}) de la carga inicial
  // se tragaba cualquier fallo de red — con conectividad inestable (el
  // escenario típico del repartidor en la calle) el select quedaba vacío,
  // indistinguible de "genuinamente no tenés ninguna instancia asignada".
  const { repartidorEmail, repartidorPassword } = await createOwnerWithRepartidor(page);

  let shouldFail = true;
  await page.route("**/instances*", (route) => {
    if (route.request().method() === "GET" && shouldFail) {
      shouldFail = false;
      route.fulfill({ status: 500, body: "{}" });
      return;
    }
    route.continue();
  });

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await expect(page.getByText(/No se pudo cargar tus instancias asignadas/)).toBeVisible();

  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(page.getByText(/No se pudo cargar tus instancias asignadas/)).not.toBeVisible();
});

test("header de la lista de clientes no se corta en viewport angosto (dueño)", async ({ page }) => {
  const suffix = `${Date.now()}`;
  await page.goto("/");
  await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  await page.locator("#account-name").fill(`E2E Mobile Owner ${suffix}`);
  await page.locator("#login-email").fill(`mobile-owner-${suffix}@test.local`);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();

  const contactHeader = page.locator(".clients-list-head span", { hasText: "Contacto" });
  await expect(contactHeader).toBeVisible();
  const box = await contactHeader.boundingBox();
  const sidebarBox = await page.locator(".app-sidebar").boundingBox();
  expect(box).not.toBeNull();
  expect(sidebarBox).not.toBeNull();
  // El header no debe desbordar el ancho del sidebar (lo que causaba el corte visual).
  expect(box!.x + box!.width).toBeLessThanOrEqual(sidebarBox!.x + sidebarBox!.width + 1);
});

test("si el dueño re-resuelve la instancia mientras el repartidor la tiene abierta, la ruta se limpia al intentar marcar una entrega", async ({ page }) => {
  // Bug real: el dueño re-resolviendo la instancia invalida la asignación
  // del repartidor en el servidor (route_assignments se borra en cada
  // re-solve), pero el repartidor que ya tenía la ruta cargada en pantalla
  // seguía viendo todas las paradas totalmente interactivas — tocar
  // "Entregado" caía en un 403 sin que la UI comunicara que la ruta entera
  // ya no le pertenece, dejando la pantalla en un estado engañoso.
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-invalidated-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  // El dueño re-resuelve la MISMA instancia — invalida la asignación en el
  // servidor sin que el repartidor recargue la página.
  const resolveRes = await page.request.post(`${API_BASE}/instances/${instanciaId}/solve`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
  });
  expect(resolveRes.ok()).toBeTruthy();

  await page.locator(".repartidor-stop").first().getByRole("button", { name: "Entregado" }).click();

  await expect(page.getByText("No tenés una ruta asignada", { exact: false })).toBeVisible();
  await expect(page.locator(".repartidor-stop")).toHaveCount(0);
});

test("tras la invalidación, si el dueño vuelve a asignar al repartidor, marcar una entrega dispara un refetch que recupera la ruta sin recargar la página", async ({ page }) => {
  // Bug real (regresión del fix anterior): un simple `setRoute(null)` dejaba
  // al repartidor sin forma de recuperarse si esa era su única instancia
  // asignada — re-elegirla en el <select> no dispara onChange (el valor no
  // cambió), así que nunca se refrescaba sin recargar toda la página. El
  // fix hace un refetch directo de getMyRoute en el mismo catch, así que
  // si el dueño reasigna al repartidor, el siguiente toque en una parada
  // (aunque falle esa primera vez) trae la ruta real sin depender del select.
  const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
    await createOwnerWithRepartidor(page);
  const instanciaId = `e2e-mobile-recover-${Date.now()}`;
  await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);

  await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  await page.locator("#instance-select").selectOption(instanciaId);
  await expect(page.locator(".repartidor-stop")).toHaveCount(2);

  // Re-resuelve (invalida la asignación) y la reasigna de nuevo — simula
  // al dueño corrigiendo algo y reasignando enseguida.
  await page.request.post(`${API_BASE}/instances/${instanciaId}/solve`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
  });
  await page.request.put(`${API_BASE}/instances/${instanciaId}/assignments`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { assignments: { "0": repartidorUserId } },
  });

  // El repartidor todavía tiene la ruta vieja en pantalla — el primer toque
  // dispara el 403 (la asignación anterior a este PUT ya no era válida en
  // el momento del click), pero el refetch en el catch debe traer la ruta
  // real ya restaurada, sin que el repartidor tenga que recargar.
  await page.locator(".repartidor-stop").first().getByRole("button", { name: "Entregado" }).click();
  await expect(page.locator(".repartidor-stop")).toHaveCount(2, { timeout: 10_000 });
});
