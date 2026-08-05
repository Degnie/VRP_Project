import type { ClientGroup, FleetSelectionEntry, InstanceRequest, VehicleType } from "./types";

export interface BuildInstanceParams {
  instanciaId: string;
  depot: { x: string; y: string };
  clients: ClientGroup[];
  fleet: FleetSelectionEntry[];
  vehicleTypes: VehicleType[];
}

export interface BuildInstanceResult {
  request: InstanceRequest | null;
  excludedOutOfCoverage: number;
  volumeWarnings: string[];
  overCapacityClientIds?: string[];
}

function packageVolumeM3(lengthCm: number, widthCm: number, heightCm: number): number {
  return (lengthCm / 100) * (widthCm / 100) * (heightCm / 100);
}

export function buildInstanceRequest(params: BuildInstanceParams): BuildInstanceResult {
  const { instanciaId, depot, clients, fleet, vehicleTypes } = params;

  const inCoverageClients = clients.filter((c) => c.inCoverage);
  const excludedOutOfCoverage = clients.length - inCoverageClients.length;

  const typeById = new Map(vehicleTypes.map((t) => [t.id, t]));

  // Expandir la selección de flota a una lista plana de capacidades efectivas
  // (capacidad nominal * margen de tolerancia de cada vehículo), ordenada de
  // mayor a menor: los vehículos grandes arrancan primero y absorben los
  // clusters más densos; el solver asigna capacities[i] al vehículo i en orden.
  const flatCapacities: number[] = [];
  for (const entry of fleet) {
    const type = typeById.get(entry.vehicleTypeId);
    if (!type) continue;
    const effective = Math.round(type.weightCapacityKg * type.toleranceMargin);
    for (let i = 0; i < entry.count; i++) {
      flatCapacities.push(effective);
    }
  }
  flatCapacities.sort((a, b) => b - a);

  if (inCoverageClients.length === 0 || flatCapacities.length === 0) {
    return { request: null, excludedOutOfCoverage, volumeWarnings: [] };
  }

  const coordinates: [number, number][] = inCoverageClients.map((c) => [Number(c.x), Number(c.y)]);
  const demands = inCoverageClients.map((c) =>
    Math.max(1, Math.round(c.packages.reduce((sum, p) => sum + p.weightKg, 0)))
  );

  // Un cliente cuyo peso supera el vehículo más grande seleccionado es
  // irresoluble aunque la capacidad TOTAL de la flota alcance — el backend
  // ahora lo rechaza (Instancia.__post_init__), pero conviene avisar acá
  // mismo, antes del POST /solve, en vez de esperar el 400.
  const maxCapacity = flatCapacities[0]; // ya viene ordenado de mayor a menor
  const overCapacityClients = inCoverageClients.filter((_, i) => demands[i] > maxCapacity);
  if (overCapacityClients.length > 0) {
    return {
      request: null,
      excludedOutOfCoverage,
      volumeWarnings: [],
      overCapacityClientIds: overCapacityClients.map((c) => c.clientId),
    };
  }
  const contacts = inCoverageClients.map((c) =>
    c.customerName || c.customerPhone || c.address
      ? { customer_name: c.customerName, customer_phone: c.customerPhone, address: c.address }
      : null
  );

  const minVolumeCapacity = Math.min(
    ...fleet
      .map((entry) => typeById.get(entry.vehicleTypeId))
      .filter((t): t is VehicleType => !!t)
      .map((t) => t.volumeCapacityM3)
  );

  const volumeWarnings: string[] = [];
  inCoverageClients.forEach((client) => {
    const totalVolume = client.packages.reduce(
      (sum, p) => sum + packageVolumeM3(p.lengthCm, p.widthCm, p.heightCm),
      0
    );
    if (Number.isFinite(minVolumeCapacity) && totalVolume > minVolumeCapacity) {
      volumeWarnings.push(
        `Cliente ${client.clientId}: volumen total ${totalVolume.toFixed(2)} m³ excede la capacidad del vehículo más chico seleccionado (${minVolumeCapacity.toFixed(2)} m³).`
      );
    }
  });

  const avgCapacity = Math.round(
    flatCapacities.reduce((sum, c) => sum + c, 0) / flatCapacities.length
  );

  const request: InstanceRequest = {
    // RN-016: trim antes de mandar — sin esto, un ID de solo espacios
    // (borrado accidental del default al escribir rápido) pasaba el POST y
    // quedaba invisible en la lista de instancias, sin colisionar con el
    // chequeo de duplicado (App.tsx compara el string crudo).
    instancia_id: instanciaId.trim(),
    coordinates,
    demands,
    num_vehicles: flatCapacities.length,
    vehicle_capacity: avgCapacity,
    vehicle_capacities: flatCapacities,
    depot_coordinates: [Number(depot.x), Number(depot.y)],
    contacts,
  };

  return { request, excludedOutOfCoverage, volumeWarnings };
}
