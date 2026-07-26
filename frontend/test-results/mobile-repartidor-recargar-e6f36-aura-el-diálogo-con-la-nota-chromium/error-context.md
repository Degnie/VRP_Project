# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: mobile-repartidor.spec.ts >> recargar la página con un cambio de estado sin confirmar restaura el diálogo con la nota
- Location: e2e\mobile-repartidor.spec.ts:185:1

# Error details

```
Error: expect(locator).toHaveClass(expected) failed

Locator: locator('.repartidor-stop').first().getByRole('button', { name: 'Rechazado' })
Expected pattern: /repartidor-status-btn--active/
Received string:  "repartidor-status-btn"
Timeout: 5000ms

Call log:
  - Expect "toHaveClass" with timeout 5000ms
  - waiting for locator('.repartidor-stop').first().getByRole('button', { name: 'Rechazado' })
    13 × locator resolved to <button type="button" class="repartidor-status-btn">Rechazado</button>
       - unexpected value "repartidor-status-btn"

```

```yaml
- button "Rechazado"
```

# Test source

```ts
  112 |   await expect(firstStop.getByRole("button", { name: "Entregado" })).toHaveClass(/repartidor-status-btn--active/);
  113 | 
  114 |   // Volver a "Pendiente" desde un estado terminal ("Entregado") pide confirmación.
  115 |   await firstStop.getByRole("button", { name: "Pendiente" }).click();
  116 |   await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();
  117 | 
  118 |   await page.getByRole("button", { name: "Cancelar" }).click();
  119 |   await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).not.toBeVisible();
  120 |   await expect(firstStop.getByRole("button", { name: "Entregado" })).toHaveClass(/repartidor-status-btn--active/);
  121 | 
  122 |   // Confirmar sí aplica el cambio.
  123 |   await firstStop.getByRole("button", { name: "Pendiente" }).click();
  124 |   await page.getByRole("button", { name: "Confirmar" }).click();
  125 |   await expect(firstStop.getByRole("button", { name: "Pendiente" })).toHaveClass(/repartidor-status-btn--active/);
  126 | });
  127 | 
  128 | test("marcar Rechazado pide confirmación con nota, y la nota queda visible en la parada", async ({ page }) => {
  129 |   const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
  130 |     await createOwnerWithRepartidor(page);
  131 |   const instanciaId = `e2e-mobile-rechazado-${Date.now()}`;
  132 |   await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);
  133 | 
  134 |   await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  135 |   await page.locator("#instance-select").selectOption(instanciaId);
  136 |   await expect(page.locator(".repartidor-stop")).toHaveCount(2);
  137 | 
  138 |   const firstStop = page.locator(".repartidor-stop").first();
  139 |   await firstStop.getByRole("button", { name: "Rechazado" }).click();
  140 |   await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();
  141 | 
  142 |   const note = "No tenía el monto exacto, vuelve mañana";
  143 |   await page.locator(".confirm-dialog-note-field textarea").fill(note);
  144 |   await page.getByRole("button", { name: "Confirmar" }).click();
  145 | 
  146 |   await expect(firstStop.getByRole("button", { name: "Rechazado" })).toHaveClass(/repartidor-status-btn--active/);
  147 |   await expect(firstStop.locator(".repartidor-stop-note")).toContainText(note);
  148 | });
  149 | 
  150 | test("una nota de un estado anterior no se arrastra a una transición que no admite nota", async ({ page }) => {
  151 |   // Bug real (Ronda 43, confirmación): handleStatusChange precarga noteDraft
  152 |   // con la nota YA existente de la parada para no perderla de vista al
  153 |   // reabrir el mismo estado — pero eso incluía transiciones que salen de un
  154 |   // estado terminal hacia uno SIN campo de nota (ej. Rechazado con nota →
  155 |   // Entregado). El textarea no se renderizaba ahí, pero la nota vieja viajaba
  156 |   // igual adjunta al nuevo estado sin que el repartidor la viera ni pudiera
  157 |   // editarla/borrarla.
  158 |   const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
  159 |     await createOwnerWithRepartidor(page);
  160 |   const instanciaId = `e2e-mobile-note-no-arrastre-${Date.now()}`;
  161 |   await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);
  162 | 
  163 |   await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  164 |   await page.locator("#instance-select").selectOption(instanciaId);
  165 |   await expect(page.locator(".repartidor-stop")).toHaveCount(2);
  166 | 
  167 |   const firstStop = page.locator(".repartidor-stop").first();
  168 |   await firstStop.getByRole("button", { name: "Rechazado" }).click();
  169 |   const note = "No atendió, vecino avisado";
  170 |   await page.locator(".confirm-dialog-note-field textarea").fill(note);
  171 |   await page.getByRole("button", { name: "Confirmar" }).click();
  172 |   await expect(firstStop.locator(".repartidor-stop-note")).toContainText(note);
  173 | 
  174 |   // Salir del estado terminal "Rechazado" hacia "Entregado" — no admite nota,
  175 |   // el textarea no debe aparecer, y la nota vieja no debe sobrevivir.
  176 |   await firstStop.getByRole("button", { name: "Entregado" }).click();
  177 |   await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();
  178 |   await expect(page.locator(".confirm-dialog-note-field textarea")).not.toBeVisible();
  179 |   await page.getByRole("button", { name: "Confirmar" }).click();
  180 | 
  181 |   await expect(firstStop.getByRole("button", { name: "Entregado" })).toHaveClass(/repartidor-status-btn--active/);
  182 |   await expect(firstStop.locator(".repartidor-stop-note")).toHaveCount(0);
  183 | });
  184 | 
  185 | test("recargar la página con un cambio de estado sin confirmar restaura el diálogo con la nota", async ({ page }) => {
  186 |   // Bug real: la nota en curso de un cambio de estado (ej. motivo de un
  187 |   // "Rechazado") se perdía sin aviso si la sesión expiraba a mitad del
  188 |   // tipeo o si el repartidor volvía atrás — ambos casos desmontan
  189 |   // RepartidorView. Se simula con un reload, que también desmonta/remonta.
  190 |   const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
  191 |     await createOwnerWithRepartidor(page);
  192 |   const instanciaId = `e2e-mobile-persist-${Date.now()}`;
  193 |   await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);
  194 | 
  195 |   await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  196 |   await page.locator("#instance-select").selectOption(instanciaId);
  197 |   await expect(page.locator(".repartidor-stop")).toHaveCount(2);
  198 | 
  199 |   const firstStop = page.locator(".repartidor-stop").first();
  200 |   await firstStop.getByRole("button", { name: "Rechazado" }).click();
  201 |   await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();
  202 | 
  203 |   const note = "No atendió, vuelvo en la tarde";
  204 |   await page.locator(".confirm-dialog-note-field textarea").fill(note);
  205 | 
  206 |   await page.reload();
  207 | 
  208 |   await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();
  209 |   await expect(page.locator(".confirm-dialog-note-field textarea")).toHaveValue(note);
  210 | 
  211 |   await page.getByRole("button", { name: "Confirmar" }).click();
> 212 |   await expect(page.locator(".repartidor-stop").first().getByRole("button", { name: "Rechazado" })).toHaveClass(
      |                                                                                                     ^ Error: expect(locator).toHaveClass(expected) failed
  213 |     /repartidor-status-btn--active/
  214 |   );
  215 | });
  216 | 
  217 | test("cambiar de instancia con un cambio de estado sin confirmar queda bloqueado hasta resolver el diálogo", async ({ page }) => {
  218 |   // Bug real (evolucionado en dos rondas): primero el pendingChange
  219 |   // restaurado/activo no se validaba contra la ruta cargada — cambiar de
  220 |   // instancia con el diálogo de "Rechazado" abierto en la instancia A dejaba
  221 |   // el diálogo abierto igual sobre la instancia B, referenciando un
  222 |   // client_id que no le pertenece. Luego (Ronda 25) se encontró que incluso
  223 |   // con esa validación, la ventana de carga de la ruta nueva permitía
  224 |   // confirmar contra route=null, descartando la nota en silencio. Fix
  225 |   // final: el selector se bloquea mientras el diálogo está abierto.
  226 |   const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
  227 |     await createOwnerWithRepartidor(page);
  228 |   const instanciaA = `e2e-mobile-switch-a-${Date.now()}`;
  229 |   const instanciaB = `e2e-mobile-switch-b-${Date.now()}`;
  230 |   await solveAndAssign(page, ownerToken, repartidorUserId, instanciaA);
  231 |   await solveAndAssign(page, ownerToken, repartidorUserId, instanciaB);
  232 | 
  233 |   await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  234 |   await page.locator("#instance-select").selectOption(instanciaA);
  235 |   await expect(page.locator(".repartidor-stop")).toHaveCount(2);
  236 | 
  237 |   await page.locator(".repartidor-stop").first().getByRole("button", { name: "Rechazado" }).click();
  238 |   await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).toBeVisible();
  239 |   await expect(page.locator("#instance-select")).toBeDisabled();
  240 | 
  241 |   await page.getByRole("button", { name: "Cancelar" }).click();
  242 |   await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).not.toBeVisible();
  243 |   await expect(page.locator("#instance-select")).toBeEnabled();
  244 | 
  245 |   await page.locator("#instance-select").selectOption(instanciaB);
  246 |   await expect(page.locator(".repartidor-stop")).toHaveCount(2);
  247 |   await expect(page.getByRole("heading", { name: "Cambiar estado de entrega" })).not.toBeVisible();
  248 | });
  249 | 
  250 | test("repartidor en mobile puede exportar su hoja en PDF", async ({ page }) => {
  251 |   const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
  252 |     await createOwnerWithRepartidor(page);
  253 |   const instanciaId = `e2e-mobile-pdf-${Date.now()}`;
  254 |   await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);
  255 | 
  256 |   await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  257 |   await page.locator("#instance-select").selectOption(instanciaId);
  258 |   await expect(page.locator(".repartidor-stop")).toHaveCount(2);
  259 | 
  260 |   const downloadPromise = page.waitForEvent("download");
  261 |   await page.getByRole("button", { name: "Exportar mi hoja en PDF" }).click();
  262 |   const download = await downloadPromise;
  263 |   expect(download.suggestedFilename()).toMatch(/^mi_ruta_.*\.pdf$/);
  264 | });
  265 | 
  266 | test("el selector de instancia del repartidor solo lista las asignadas a él, con fecha legible", async ({ page }) => {
  267 |   const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
  268 |     await createOwnerWithRepartidor(page);
  269 |   const assignedId = `e2e-assigned-${Date.now()}`;
  270 |   const unassignedId = `e2e-unassigned-${Date.now()}`;
  271 |   await solveAndAssign(page, ownerToken, repartidorUserId, assignedId);
  272 | 
  273 |   // Segunda instancia resuelta por el dueño, pero nunca asignada al repartidor.
  274 |   const solveRes = await page.request.post(`${API_BASE}/solve`, {
  275 |     headers: { Authorization: `Bearer ${ownerToken}` },
  276 |     data: {
  277 |       instancia_id: unassignedId,
  278 |       coordinates: [[10, 10]],
  279 |       demands: [10],
  280 |       num_vehicles: 1,
  281 |       vehicle_capacity: 100,
  282 |       depot_coordinates: [0, 0],
  283 |     },
  284 |   });
  285 |   expect(solveRes.ok()).toBeTruthy();
  286 | 
  287 |   await loginRepartidorInBrowser(page, repartidorEmail, repartidorPassword);
  288 |   await page.getByRole("heading", { name: "Mi ruta" }).waitFor();
  289 | 
  290 |   const options = await page.locator("#instance-select option").allTextContents();
  291 |   expect(options.some((o) => o.startsWith(assignedId))).toBe(true);
  292 |   expect(options.some((o) => o.startsWith(unassignedId))).toBe(false);
  293 | 
  294 |   // El label incluye fecha legible, no solo el ID crudo.
  295 |   const assignedOption = options.find((o) => o.startsWith(assignedId));
  296 |   expect(assignedOption).toMatch(/—\s*\d{2}\/\d{2}/);
  297 | });
  298 | 
  299 | test("reintentar la carga de instancias no descarta un cambio de estado sin confirmar en curso", async ({ page }) => {
  300 |   // Bug real (Ronda 39, repartidor): loadInstances (montaje o "Reintentar")
  301 |   // deseleccionaba `selectedId` si la instancia ya no aparecía en la lista
  302 |   // devuelta por el GET — pero eso disparaba el efecto de [selectedId], que
  303 |   // al ver !selectedId limpiaba `route` Y `pendingChange` sin ningún aviso,
  304 |   // aunque el diálogo estuviera abierto con una nota recién escrita en ese
  305 |   // instante. Se simula la lista "sin la instancia actual" directamente por
  306 |   // mock (en vez de reasignar de verdad, que además invalidaría el propio
  307 |   // GET de la ruta con un 403 y confundiría la causa del descarte) para
  308 |   // aislar específicamente el guard de loadInstances.
  309 |   const { ownerToken, repartidorEmail, repartidorPassword, repartidorUserId } =
  310 |     await createOwnerWithRepartidor(page);
  311 |   const instanciaId = `e2e-mobile-reload-reassign-${Date.now()}`;
  312 |   await solveAndAssign(page, ownerToken, repartidorUserId, instanciaId);
```