import type { Page } from "@playwright/test";

const API_BASE = "http://localhost:8000";

/** Registra una cuenta de prueba nueva y deja la sesión guardada antes de que App monte. */
export async function loginFreshAccount(page: Page) {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@test.local`;
  await page.goto("/");
  await page.getByRole("button", { name: "¿Primera vez? Crear cuenta de empresa" }).click();
  await page.locator("#account-name").fill(`E2E ${Date.now()}`);
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill("clave123456");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByRole("heading", { name: "Hoja de despacho" }).waitFor();
}

interface OwnerWithRepartidor {
  ownerToken: string;
  repartidorEmail: string;
  repartidorPassword: string;
  repartidorToken: string;
  repartidorUserId: string;
}

/**
 * Crea una cuenta (dueño) + un repartidor dentro de ella directamente vía API
 * (no hay UI todavía para invitar usuarios — eso es trabajo de otra etapa).
 * Devuelve los tokens/ids para que el caller decida cómo usarlos (loguear en
 * el navegador, armar instancias, asignar rutas, etc.) sin forzar un flujo fijo.
 */
export async function createOwnerWithRepartidor(page: Page): Promise<OwnerWithRepartidor> {
  const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const ownerEmail = `owner-${suffix}@test.local`;
  const repartidorEmail = `repartidor-${suffix}@test.local`;
  const password = "clave123456";

  const registerRes = await page.request.post(`${API_BASE}/auth/register`, {
    data: { account_name: `E2E Repartidor ${suffix}`, email: ownerEmail, password },
  });
  const { access_token: ownerToken } = await registerRes.json();

  await page.request.post(`${API_BASE}/auth/users`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { email: repartidorEmail, password, role: "repartidor" },
  });

  const loginRes = await page.request.post(`${API_BASE}/auth/login`, {
    data: { email: repartidorEmail, password },
  });
  const repartidorToken = (await loginRes.json()).access_token;

  const meRes = await page.request.get(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${repartidorToken}` },
  });
  const repartidorUserId = (await meRes.json()).id;

  return { ownerToken, repartidorEmail, repartidorPassword: password, repartidorToken, repartidorUserId };
}

/**
 * Crea una cuenta (dueño) + un repartidor dentro de ella directamente vía API
 * y loguea al repartidor en el navegador.
 */
export async function loginAsRepartidor(page: Page) {
  const { repartidorEmail, repartidorPassword } = await createOwnerWithRepartidor(page);

  await page.goto("/");
  await page.locator("#login-email").fill(repartidorEmail);
  await page.locator("#login-password").fill(repartidorPassword);
  await page.getByRole("button", { name: "Entrar" }).click();
}
