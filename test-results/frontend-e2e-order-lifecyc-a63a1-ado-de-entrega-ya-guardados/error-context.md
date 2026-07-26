# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: frontend\e2e\order-lifecycle.spec.ts >> recargar la página muestra la asignación de repartidor y el estado de entrega ya guardados
- Location: frontend\e2e\order-lifecycle.spec.ts:47:1

# Error details

```
Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
Call log:
  - navigating to "/", waiting until "load"

```

# Test source

```ts
  1   | import { test, expect } from "@playwright/test";
  2   | import { createOwnerWithRepartidor } from "./helpers";
  3   | 
  4   | const API_BASE = "http://localhost:8000";
  5   | 
  6   | async function solveInstanceViaApi(page: import("@playwright/test").Page, token: string, instanciaId: string) {
  7   |   const res = await page.request.post(`${API_BASE}/solve`, {
  8   |     headers: { Authorization: `Bearer ${token}` },
  9   |     data: {
  10  |       instancia_id: instanciaId,
  11  |       coordinates: [[10, 10], [20, 20]],
  12  |       demands: [10, 10],
  13  |       num_vehicles: 1,
  14  |       vehicle_capacity: 100,
  15  |       depot_coordinates: [0, 0],
  16  |     },
  17  |   });
  18  |   expect(res.ok()).toBeTruthy();
  19  | }
  20  | 
  21  | test("operario asigna repartidor y el repartidor marca una entrega, visible tras reload", async ({ page }) => {
  22  |   const { ownerToken, repartidorToken, repartidorUserId } = await createOwnerWithRepartidor(page);
  23  |   const instanciaId = `e2e-lifecycle-${Date.now()}`;
  24  | 
  25  |   await solveInstanceViaApi(page, ownerToken, instanciaId);
  26  | 
  27  |   const assignRes = await page.request.put(`${API_BASE}/instances/${instanciaId}/assignments`, {
  28  |     headers: { Authorization: `Bearer ${ownerToken}` },
  29  |     data: { assignments: { "0": repartidorUserId } },
  30  |   });
  31  |   expect(assignRes.ok()).toBeTruthy();
  32  | 
  33  |   const statusRes = await page.request.put(`${API_BASE}/instances/${instanciaId}/clients/1/status`, {
  34  |     headers: { Authorization: `Bearer ${repartidorToken}` },
  35  |     data: { status: "entregado" },
  36  |   });
  37  |   expect(statusRes.ok()).toBeTruthy();
  38  | 
  39  |   const myRouteRes = await page.request.get(`${API_BASE}/instances/${instanciaId}/my-route`, {
  40  |     headers: { Authorization: `Bearer ${repartidorToken}` },
  41  |   });
  42  |   const myRoute = await myRouteRes.json();
  43  |   const stop1 = myRoute.stops.find((s: { client_id: number }) => s.client_id === 1);
  44  |   expect(stop1.delivery_status).toBe("entregado");
  45  | });
  46  | 
  47  | test("recargar la página muestra la asignación de repartidor y el estado de entrega ya guardados", async ({ page }) => {
  48  |   // Bug real: SolutionSummary arrancaba siempre "Sin asignar" y "Pendiente"
  49  |   // sin importar lo que ya estuviera guardado en el backend — no había
  50  |   // ningún GET para hidratar assignments/delivery-statuses tras un reload.
  51  |   const suffix = `${Date.now()}`;
  52  |   const email = `owner-hydrate-${suffix}@test.local`;
> 53  |   await page.goto("/");
      |              ^ Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
  54  |   await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  55  |   await page.locator("#account-name").fill(`E2E Hydrate ${suffix}`);
  56  |   await page.locator("#login-email").fill(email);
  57  |   await page.locator("#login-password").fill("clave123456");
  58  |   await page.getByRole("button", { name: "Crear cuenta" }).click();
  59  |   await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();
  60  | 
  61  |   const ownerToken = await page.evaluate(() => {
  62  |     const raw = localStorage.getItem("vrp:auth-token");
  63  |     return raw ? JSON.parse(raw).accessToken : null;
  64  |   });
  65  | 
  66  |   const inviteRes = await page.request.post(`${API_BASE}/auth/users`, {
  67  |     headers: { Authorization: `Bearer ${ownerToken}` },
  68  |     data: { email: `repa-hydrate-${suffix}@test.local`, password: "clave123", role: "repartidor" },
  69  |   });
  70  |   const repartidorId = (await inviteRes.json()).id;
  71  | 
  72  |   await page.locator("#depot-x").fill("-77.035");
  73  |   await page.locator("#depot-y").fill("-12.0464");
  74  |   const cards = page.locator(".client-card");
  75  |   const coords: [string, string][] = [["-77.06", "-11.98"], ["-77.03", "-12.12"]];
  76  |   for (let i = 0; i < coords.length; i++) {
  77  |     const card = cards.nth(i);
  78  |     await card.locator(".client-card-summary").click();
  79  |     await card.locator(".field-row input").nth(0).fill(coords[i][0]);
  80  |     await card.locator(".field-row input").nth(1).fill(coords[i][1]);
  81  |     await card.locator('input[placeholder="kg"]').fill("5");
  82  |   }
  83  |   await page.getByRole("button", { name: /Resolver instancia/ }).click();
  84  |   await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15000 });
  85  | 
  86  |   await page.locator(".route-assign select").selectOption(repartidorId);
  87  |   await page.getByRole("button", { name: "Guardar asignaciones de repartidor" }).click();
  88  |   await expect(page.locator(".stop-save-indicator--saved")).toBeVisible();
  89  | 
  90  |   await page.locator(".delivery-status-select").first().selectOption("rechazado");
  91  |   await page.locator(".confirm-dialog-note-field textarea").fill("cliente pidió reprogramar");
  92  |   await page.getByRole("button", { name: "Confirmar" }).click();
  93  | 
  94  |   await page.reload();
  95  |   await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15000 });
  96  | 
  97  |   await expect(page.locator(".route-assign select")).toHaveValue(repartidorId);
  98  |   await expect(page.locator(".delivery-status-select").first()).toHaveValue("rechazado");
  99  |   await expect(page.locator(".delivery-status-note").first()).toContainText("cliente pidió reprogramar");
  100 | });
  101 | 
  102 | test("dueño ve y cambia el estado de entrega desde la hoja de ruta resuelta", async ({ page }) => {
  103 |   const suffix = `${Date.now()}`;
  104 |   const email = `owner-ui-${suffix}@test.local`;
  105 |   await page.goto("/");
  106 |   await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  107 |   await page.locator("#account-name").fill(`E2E Lifecycle UI ${suffix}`);
  108 |   await page.locator("#login-email").fill(email);
  109 |   await page.locator("#login-password").fill("clave123456");
  110 |   await page.getByRole("button", { name: "Crear cuenta" }).click();
  111 |   await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();
  112 | 
  113 |   await page.locator("#depot-x").fill("-77.035");
  114 |   await page.locator("#depot-y").fill("-12.0464");
  115 |   const cards = page.locator(".client-card");
  116 |   const coords: [string, string][] = [["-77.06", "-11.98"], ["-77.03", "-12.12"]];
  117 |   for (let i = 0; i < coords.length; i++) {
  118 |     const card = cards.nth(i);
  119 |     await card.locator(".client-card-summary").click();
  120 |     await card.locator(".field-row input").nth(0).fill(coords[i][0]);
  121 |     await card.locator(".field-row input").nth(1).fill(coords[i][1]);
  122 |     await card.locator('input[placeholder="kg"]').fill("5");
  123 |   }
  124 |   await page.getByRole("button", { name: /Resolver instancia/ }).click();
  125 |   await expect(page.locator(".solution-summary")).toBeVisible({ timeout: 15_000 });
  126 | 
  127 |   const select = page.locator(".delivery-status-select").first();
  128 |   await select.selectOption("entregado");
  129 |   await expect(select).toHaveValue("entregado");
  130 | 
  131 |   // Volver desde un estado terminal ("entregado") a otro pide confirmación.
  132 |   await select.selectOption("pendiente");
  133 |   await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();
  134 |   await page.getByRole("button", { name: "Cancelar" }).click();
  135 |   await expect(select).toHaveValue("entregado");
  136 | 
  137 |   await select.selectOption("pendiente");
  138 |   await page.getByRole("button", { name: "Confirmar" }).click();
  139 |   await expect(select).toHaveValue("pendiente");
  140 | });
  141 | 
  142 | test("reprogramar crea una nueva instancia con los pedidos no entregados", async ({ page }) => {
  143 |   const { ownerToken } = await createOwnerWithRepartidor(page);
  144 |   const instanciaId = `e2e-reschedule-${Date.now()}`;
  145 |   await solveInstanceViaApi(page, ownerToken, instanciaId);
  146 | 
  147 |   await page.request.put(`${API_BASE}/instances/${instanciaId}/clients/1/status`, {
  148 |     headers: { Authorization: `Bearer ${ownerToken}` },
  149 |     data: { status: "entregado" },
  150 |   });
  151 | 
  152 |   const rescheduleRes = await page.request.post(`${API_BASE}/instances/${instanciaId}/reschedule`, {
  153 |     headers: { Authorization: `Bearer ${ownerToken}` },
```