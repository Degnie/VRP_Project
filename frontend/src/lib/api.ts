import type {
  CoveragePolygon,
  DeliveryStatus,
  HealthStatus,
  InstanceRequest,
  InstanceSummary,
  MyRouteResponse,
  RescheduleResponse,
  SolutionResponse,
  TokenResponse,
  UserOut,
  VehicleTypeDTO,
} from "./types";
import { getSession } from "./auth";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const session = getSession();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (session) headers["Authorization"] = `Bearer ${session.accessToken}`;

  const res = await fetch(`${API_BASE}${path}`, {
    headers: { ...headers, ...(init?.headers as Record<string, string> | undefined) },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  health: () => request<HealthStatus>("/health"),
  solve: (body: InstanceRequest) =>
    request<SolutionResponse>("/solve", { method: "POST", body: JSON.stringify(body) }),
  listInstances: () => request<InstanceSummary[]>("/instances"),
  getSolution: (instanciaId: string) =>
    request<SolutionResponse>(`/solutions/${encodeURIComponent(instanciaId)}`),
  exportSolutionPdf: async (instanciaId: string, vehicleId?: number): Promise<Blob> => {
    const session = getSession();
    const headers: Record<string, string> = {};
    if (session) headers["Authorization"] = `Bearer ${session.accessToken}`;
    const query = vehicleId !== undefined ? `?vehicle_id=${vehicleId}` : "";
    const res = await fetch(`${API_BASE}/solutions/${encodeURIComponent(instanciaId)}/export.pdf${query}`, {
      headers,
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
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

  // --- Catálogo de vehículos ---
  listVehicleCatalog: () => request<VehicleTypeDTO[]>("/vehicle-catalog"),
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
  updateDeliveryStatus: (instanciaId: string, clienteId: number, status: DeliveryStatus) =>
    request<{ status: DeliveryStatus }>(
      `/instances/${encodeURIComponent(instanciaId)}/clients/${clienteId}/status`,
      { method: "PUT", body: JSON.stringify({ status }) }
    ),
  setAssignments: (instanciaId: string, assignments: Record<number, string>) =>
    request<{ assignments: Record<number, string> }>(
      `/instances/${encodeURIComponent(instanciaId)}/assignments`,
      { method: "PUT", body: JSON.stringify({ assignments }) }
    ),
  getMyRoute: (instanciaId: string) =>
    request<MyRouteResponse>(`/instances/${encodeURIComponent(instanciaId)}/my-route`),
  rescheduleInstance: (instanciaId: string) =>
    request<RescheduleResponse>(`/instances/${encodeURIComponent(instanciaId)}/reschedule`, { method: "POST" }),
};
