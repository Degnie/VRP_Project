export interface ContactInfo {
  customer_name?: string;
  customer_phone?: string;
  address?: string;
}

export interface InstanceRequest {
  instancia_id: string;
  coordinates: [number, number][];
  demands: number[];
  num_vehicles: number;
  vehicle_capacity: number;
  vehicle_capacities?: number[];
  depot_coordinates: [number, number];
  // Mismo índice que coordinates/demands — ver ContactInfo.
  contacts?: (ContactInfo | null)[];
}

export interface RouteResult {
  vehicle_id: number;
  sequence: number[];
  cost: number;
}

export interface SolutionResponse {
  instancia_id: string;
  total_cost: number;
  num_routes: number;
  routes: RouteResult[];
  // Bug real (Ronda 13, ciclo nuevo): si es false, el solver calculó costo y
  // secuencia con distancia euclídea (OSRM no disponible) — total_cost no
  // refleja distancia real de calles.
  used_osrm: boolean;
}

export interface InstanceSummary {
  id: string;
  num_clients: number;
  num_vehicles: number;
  capacity: number;
  created_at?: string;
}

export interface HealthStatus {
  status: "ok" | "degraded";
  version: string;
  postgresql: "ok" | "unavailable";
  mongodb: "ok" | "unavailable";
}

// --- Auth (Etapa 0b/1) ---
export type Role = "dueño" | "operario" | "repartidor";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: Role;
  account_id: string;
}

export interface UserOut {
  id: string;
  account_id: string;
  email: string;
  role: Role;
  full_name?: string;
}

// --- Gestión de equipo (Etapa A de mejoras post-auditoría) ---
export interface TeamMember {
  id: string;
  email: string;
  role: Role;
  full_name?: string;
  active: boolean;
}

// RN-CAT-003: estado operativo del vehículo — uno suspendido (mantenimiento)
// no debería asignarse a una instancia nueva.
export type VehicleStatus = "activo" | "suspendido";

// --- Catálogo de vehículos (persistido en el backend, por cuenta — Etapa 1) ---
export interface VehicleType {
  id: string;
  name: string;
  weightCapacityKg: number;
  volumeCapacityM3: number;
  toleranceMargin: number; // 0..1, ej. 0.90 = usar 90% de la capacidad nominal
  status: VehicleStatus;
}

// Forma exacta que devuelve/espera el backend (snake_case) — se mapea a/desde
// VehicleType (camelCase) en src/lib/vehicleCatalog.ts.
export interface VehicleTypeDTO {
  id?: string;
  name: string;
  weight_capacity_kg: number;
  volume_capacity_m3: number;
  tolerance_margin: number;
  status: VehicleStatus;
}

// Selección de flota disponible "hoy" (vive en el estado del formulario, no persiste)
export interface FleetSelectionEntry {
  vehicleTypeId: string;
  count: number;
}

// --- Paquete individual con dimensiones ---
export interface Package {
  weightKg: number;
  lengthCm: number;
  widthCm: number;
  heightCm: number;
}

// Cliente agrupado (post-import, pre-conversión a InstanceRequest)
export interface ClientGroup {
  clientId: string;
  x: string;
  y: string;
  packages: Package[];
  inCoverage: boolean;
  // Datos de contacto: el solver no los usa (solo coordenadas/peso), pero el
  // repartidor en la calle sí los necesita — sin nombre/teléfono/dirección
  // legible no puede confirmar la entrega ni contactar al cliente si no
  // encuentra el punto exacto. Opcionales: el CSV puede no traerlos.
  customerName?: string;
  customerPhone?: string;
  address?: string;
}

export interface UpdateClientRequest {
  x: number;
  y: number;
  demand?: number;
  // null = borrar el campo a propósito; undefined (omitido) = no tocarlo.
  customer_name?: string | null;
  customer_phone?: string | null;
  address?: string | null;
  // updated_at visto al abrir el formulario (ver ClientDetail) — el backend
  // rechaza con 409 si no coincide con lo persistido (otra edición ganó
  // mientras tanto), en vez de pisarla en silencio.
  updated_at?: string | null;
}

export interface ClientDetail {
  id: number;
  x: number;
  y: number;
  demand: number;
  customer_name?: string;
  customer_phone?: string;
  address?: string;
  updated_at?: string;
}

// --- Zona de cobertura (persistida en el backend, por cuenta — Etapa 1) ---
export interface CoveragePolygon {
  points: [number, number][];
}

// --- Ciclo de vida de pedido (Etapa 4) ---
export type DeliveryStatus = "pendiente" | "entregado" | "no_encontrado" | "reprogramado" | "rechazado";

export interface RouteAssignment {
  vehicleId: number;
  repartidorUserId: string;
}

export interface RouteStop {
  client_id: number;
  sequence: number;
  delivery_status: DeliveryStatus;
  delivery_note?: string;
  customer_name?: string;
  customer_phone?: string;
  address?: string;
  // RN-025: si hay comprobante fotográfico guardado (el Base64 en sí no
  // viaja acá — my-route lista todas las paradas de la ruta).
  has_photo: boolean;
}

export interface MyRouteResponse {
  instancia_id: string;
  vehicle_id: number;
  stops: RouteStop[];
}

export interface RescheduleResponse {
  new_instancia_id: string;
  rescheduled_client_ids: number[];
}

// --- Dashboard diario (RN-023) ---
export interface DashboardSummary {
  fecha: string;
  // En metros — misma unidad cruda de OSRM/euclídea que el resto de la app
  // ya usa (ver SolutionSummary.tsx: formatDistanceKm hace meters/1000).
  distancia_total: number;
  num_entregas: number;
  vehiculos_utilizados: number;
  vehiculos_disponibles: number;
}

// --- Alertas repartidor -> dueño/operario (RN-024) ---
export interface AlertRequest {
  instancia_id: string;
  cliente_id: number;
  motivo: string;
}

export interface Alert {
  id: string;
  instancia_id: string;
  cliente_id: number;
  motivo: string;
  resuelta: boolean;
  created_at: string;
}

// --- ETA estimado (calculado post-solve, no persistido) ---
export interface EtaEstimate {
  clientIndex: number;
  arrivalEarliest: string; // "HH:MM"
  arrivalLatest: string;
}
export interface RouteEta {
  vehicle_id: number;
  stops: EtaEstimate[];
}
