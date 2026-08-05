import type {
  Alert,
  AlertRequest,
  ClientDetail,
  CoveragePolygon,
  DashboardSummary,
  DeliveryStatus,
  HealthStatus,
  InstanceRequest,
  InstanceSummary,
  MyRouteResponse,
  RescheduleResponse,
  SolutionResponse,
  TeamMember,
  TokenResponse,
  UpdateClientRequest,
  UserOut,
  VehicleTypeDTO,
} from "./types";
import { getSession, clearSession } from "./auth";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// Evento que App.tsx escucha para volver a la pantalla de login apenas el
// backend rechaza el token (sesión revocada por desactivación, o expirada).
// Sin esto, un usuario desactivado mientras tenía la app abierta se quedaba
// viendo el mensaje crudo del backend ("Invalid or expired token", en
// inglés) en cada intento, sin ninguna salida clara ni indicación de que
// tenía que volver a loguear.
export const SESSION_EXPIRED_EVENT = "vrp:session-expired";

// Bug real (Ronda 50, repartidor): fetch() sin timeout ni AbortController
// dejaba la promesa colgada para siempre si el backend/proxy se quedaba sin
// responder (no un error de red — eso sí lo captura el catch de abajo, sino
// una conexión que nunca cierra). El botón de estado quedaba en "Guardando…"
// indefinidamente, sin error, sin forma de reintentar salvo recargar la
// página (perdiendo el intento en curso en silencio). 15s es generoso para
// una conexión de datos móvil lenta, pero corta antes de que el repartidor
// piense que la app se colgó.
const REQUEST_TIMEOUT_MS = 15000;
// Bug real (Ronda 51, dueño): ese mismo timeout de 15s, al ser global para
// TODA llamada a request(), también cortaba /solve — medido contra el
// backend real: ~11s con 300 clientes, ~25.5s con 500. Con instancias
// grandes (reales en data/), el frontend abortaba una resolución que estaba
// funcionando bien y a punto de terminar, mostrando un error falso y
// arriesgando que el dueño reintentara mientras el cómputo original seguía
// corriendo del lado del servidor (abortar el fetch no cancela el cómputo
// backend). Los endpoints de resolución usan un timeout mucho más generoso.
const SOLVE_TIMEOUT_MS = 120000;

async function request<T>(path: string, init?: RequestInit, timeoutMs: number = REQUEST_TIMEOUT_MS): Promise<T> {
  const session = getSession();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (session) headers["Authorization"] = `Bearer ${session.accessToken}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { ...headers, ...(init?.headers as Record<string, string> | undefined) },
      signal: controller.signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") {
      throw new Error("La conexión tardó demasiado — probá de nuevo.");
    }
    // fetch() rechaza con un TypeError genérico ("Failed to fetch") cuando no
    // hay conexión — mensaje técnico en inglés, sin sentido para alguien en
    // la calle con mala señal tratando de guardar un estado de entrega.
    throw new Error("Sin conexión — no se pudo guardar. Probá de nuevo.");
  } finally {
    clearTimeout(timeoutId);
  }
  if (!res.ok) {
    if (res.status === 401 && session) {
      // Distingue "nunca logueaste" (no había session — dejalo pasar como
      // error normal, ej. login con credenciales incorrectas) de "tu sesión
      // ya no vale" (SÍ había session pero el backend la rechazó — token
      // vencido, o usuario desactivado en medio de su uso).
      clearSession();
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
      throw new Error("Tu sesión ya no es válida — volvé a iniciar sesión.");
    }
    const body = await res.json().catch(() => null);
    // Un HTTPException manual da detail: string, pero un 422 de validación
    // de Pydantic da detail: [{msg, loc, ...}] — sin este chequeo, un error
    // de validación (ej. coordenada fuera de rango) se mostraba como
    // "[object Object]" en vez del mensaje real.
    const detail = Array.isArray(body?.detail)
      ? body.detail.map((e: { msg?: string }) => e.msg).filter(Boolean).join(" — ")
      : body?.detail;
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  health: () => request<HealthStatus>("/health"),
  solve: (body: InstanceRequest) =>
    request<SolutionResponse>("/solve", { method: "POST", body: JSON.stringify(body) }, SOLVE_TIMEOUT_MS),
  listInstances: (opts?: { assignedOnly?: boolean; limit?: number; offset?: number }) => {
    const params = new URLSearchParams();
    if (opts?.assignedOnly) params.set("assigned_only", "true");
    if (opts?.limit !== undefined) {
      params.set("limit", String(opts.limit));
      params.set("offset", String(opts?.offset ?? 0));
    }
    const qs = params.toString();
    return request<InstanceSummary[]>(`/instances${qs ? `?${qs}` : ""}`);
  },
  getSolution: (instanciaId: string) =>
    request<SolutionResponse>(`/solutions/${encodeURIComponent(instanciaId)}`),
  exportSolutionPdf: async (instanciaId: string, vehicleId?: number): Promise<Blob> => {
    const session = getSession();
    const headers: Record<string, string> = {};
    if (session) headers["Authorization"] = `Bearer ${session.accessToken}`;
    const query = vehicleId !== undefined ? `?vehicle_id=${vehicleId}` : "";

    // Bug real (Ronda 2, ciclo nuevo, repartidor): este fetch no pasaba por
    // request(), así que le faltaban las mismas dos protecciones que Rondas
    // 50-51 ya dieron a todo lo demás — sin timeout, una conexión colgada
    // (no un error inmediato) dejaba "Generando PDF…" para siempre; y sin
    // traducir el error, un repartidor offline real veía el "Failed to
    // fetch" crudo de fetch() en vez de un mensaje en español.
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/solutions/${encodeURIComponent(instanciaId)}/export.pdf${query}`, {
        headers,
        signal: controller.signal,
      });
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        throw new Error("La conexión tardó demasiado — probá de nuevo.");
      }
      throw new Error("Sin conexión — no se pudo exportar el PDF. Probá de nuevo.");
    } finally {
      clearTimeout(timeoutId);
    }
    if (!res.ok) {
      // Mismo parseo de `detail` que request() — sin esto, un 404 (ej. el
      // dueño borró la instancia mientras el repartidor tenía la ruta
      // abierta) se mostraba como el string crudo "404 Not Found" en vez
      // del mensaje real del backend ("Instance not found"/"Solution not found").
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || `${res.status} ${res.statusText}`);
    }
    return res.blob();
  },

  // --- Auth ---
  register: (body: { account_name: string; email: string; password: string; full_name?: string }) =>
    request<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: () => request<UserOut>("/auth/me"),
  createUser: (body: { email: string; password: string; full_name?: string; role: string }) =>
    request<UserOut>("/auth/users", { method: "POST", body: JSON.stringify(body) }),
  listTeam: (opts?: { limit?: number; offset?: number }) =>
    request<TeamMember[]>(
      `/auth/users${opts?.limit !== undefined ? `?limit=${opts.limit}&offset=${opts?.offset ?? 0}` : ""}`
    ),
  setUserActive: (userId: string, active: boolean) =>
    request<TeamMember>(`/auth/users/${encodeURIComponent(userId)}`, {
      method: "PATCH",
      body: JSON.stringify({ active }),
    }),

  // --- Catálogo de vehículos ---
  listVehicleCatalog: (opts?: { limit?: number; offset?: number }) =>
    request<VehicleTypeDTO[]>(
      `/vehicle-catalog${opts?.limit !== undefined ? `?limit=${opts.limit}&offset=${opts?.offset ?? 0}` : ""}`
    ),
  createVehicleCatalogEntry: (body: VehicleTypeDTO) =>
    request<VehicleTypeDTO>("/vehicle-catalog", { method: "POST", body: JSON.stringify(body) }),
  updateVehicleCatalogEntry: (id: string, body: VehicleTypeDTO) =>
    request<VehicleTypeDTO>(`/vehicle-catalog/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteVehicleCatalogEntry: (id: string) =>
    request<void>(`/vehicle-catalog/${encodeURIComponent(id)}`, { method: "DELETE" }),

  // --- Zona de cobertura ---
  getCoverageZone: () => request<CoveragePolygon | null>("/coverage-zone"),
  setCoverageZone: (body: CoveragePolygon) =>
    request<CoveragePolygon>("/coverage-zone", { method: "PUT", body: JSON.stringify(body) }),
  deleteCoverageZone: () => request<void>("/coverage-zone", { method: "DELETE" }),

  // --- Ciclo de vida de pedido ---
  updateDeliveryStatus: (
    instanciaId: string,
    clienteId: number,
    status: DeliveryStatus,
    note?: string,
    fotoBase64?: string
  ) =>
    request<{ status: DeliveryStatus; note?: string }>(
      `/instances/${encodeURIComponent(instanciaId)}/clients/${clienteId}/status`,
      { method: "PUT", body: JSON.stringify({ status, note, foto_base64: fotoBase64 }) }
    ),
  setAssignments: (instanciaId: string, assignments: Record<number, string>) =>
    request<{ assignments: Record<number, string> }>(
      `/instances/${encodeURIComponent(instanciaId)}/assignments`,
      { method: "PUT", body: JSON.stringify({ assignments }) }
    ),
  getAssignments: (instanciaId: string) =>
    request<Record<number, string>>(`/instances/${encodeURIComponent(instanciaId)}/assignments`),
  getDeliveryStatuses: (instanciaId: string) =>
    request<Record<number, { status: DeliveryStatus; note?: string }>>(
      `/instances/${encodeURIComponent(instanciaId)}/delivery-statuses`
    ),
  getMyRoute: (instanciaId: string) =>
    request<MyRouteResponse>(`/instances/${encodeURIComponent(instanciaId)}/my-route`),
  rescheduleInstance: (instanciaId: string) =>
    request<RescheduleResponse>(`/instances/${encodeURIComponent(instanciaId)}/reschedule`, { method: "POST" }),
  solveExistingInstance: (instanciaId: string) =>
    request<SolutionResponse>(`/instances/${encodeURIComponent(instanciaId)}/solve`, { method: "POST" }, SOLVE_TIMEOUT_MS),
  getClient: (instanciaId: string, clientId: number) =>
    request<ClientDetail>(`/instances/${encodeURIComponent(instanciaId)}/clients/${clientId}`),
  updateClient: (instanciaId: string, clientId: number, body: UpdateClientRequest) =>
    request<{ id: number; x: number; y: number; demand: number }>(
      `/instances/${encodeURIComponent(instanciaId)}/clients/${clientId}`,
      { method: "PATCH", body: JSON.stringify(body) }
    ),
  deleteInstance: (instanciaId: string) =>
    request<{ deleted: boolean }>(`/instances/${encodeURIComponent(instanciaId)}`, { method: "DELETE" }),

  // --- Dashboard diario ---
  getDashboard: (date?: string) => request<DashboardSummary>(`/dashboard${date ? `?date=${date}` : ""}`),

  // --- Alertas repartidor -> dueño/operario ---
  createAlert: (body: AlertRequest) => request<Alert>("/alerts", { method: "POST", body: JSON.stringify(body) }),
  listAlerts: () => request<Alert[]>("/alerts"),
};
