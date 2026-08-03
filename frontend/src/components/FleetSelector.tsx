import type { FleetSelectionEntry, VehicleType } from "../lib/types";

// RN-019: mismo Intl.NumberFormat que SolutionSummary.tsx ya usa para
// num_routes/total_cost — sin esto, una flota realista (decenas de
// vehículos, miles de kg) mostraba "18000 kg" en vez de "18.000 kg".
const numberFormatter = new Intl.NumberFormat();

interface Props {
  vehicleTypes: VehicleType[];
  fleet: FleetSelectionEntry[];
  onChange: (fleet: FleetSelectionEntry[]) => void;
}

// Bug real (Ronda 8, ciclo nuevo, dueño): el solver usa esta capacidad
// AJUSTADA por margen de tolerancia (buildInstance.ts hace el mismo cálculo
// para vehicle_capacities), nunca la nominal — esta pantalla mostraba solo
// la nominal, así que un dueño con margen de 90% veía "1000 kg combinados"
// cuando el solver en realidad planifica contra ~900 kg, sin ningún aviso.
function effectiveWeightKg(type: VehicleType): number {
  return Math.round(type.weightCapacityKg * type.toleranceMargin);
}

export function FleetSelector({ vehicleTypes, fleet, onChange }: Props) {
  const countFor = (typeId: string) => fleet.find((f) => f.vehicleTypeId === typeId)?.count ?? 0;

  const setCount = (typeId: string, count: number) => {
    const next = fleet.filter((f) => f.vehicleTypeId !== typeId);
    if (count > 0) next.push({ vehicleTypeId: typeId, count });
    onChange(next);
  };

  const selected = vehicleTypes.filter((t) => countFor(t.id) > 0);
  const totalVehicles = selected.reduce((sum, t) => sum + countFor(t.id), 0);
  const totalWeightKg = selected.reduce((sum, t) => sum + countFor(t.id) * effectiveWeightKg(t), 0);
  const totalVolumeM3 = selected.reduce((sum, t) => sum + countFor(t.id) * t.volumeCapacityM3, 0);
  // RN-020: por capacidad EFECTIVA, no nominal — buildInstance.ts ordena
  // vehicle_capacities así al construir la solicitud real que ve el solver;
  // ordenar por nominal podía mostrar el orden invertido si los tipos
  // seleccionados tienen distinto margen de tolerancia entre sí.
  const order = [...selected].sort((a, b) => effectiveWeightKg(b) - effectiveWeightKg(a));

  return (
    <div className="fleet-selector">
      <h2 className="section-title">Flota disponible hoy</h2>
      <div className="fleet-table" role="table">
        {vehicleTypes.map((type) => (
          <div className="fleet-table-row" role="row" key={type.id}>
            <span className="fleet-vehicle-name">{type.name || "(sin nombre)"}</span>
            <span className="fleet-vehicle-spec">
              {type.toleranceMargin < 1 ? `${effectiveWeightKg(type)} kg efectivos` : `${type.weightCapacityKg} kg`} ·{" "}
              {type.volumeCapacityM3} m³
            </span>
            <input
              aria-label={`Cantidad disponible de ${type.name || "vehículo"}`}
              type="number"
              min="0"
              step="1"
              value={countFor(type.id)}
              onChange={(e) => setCount(type.id, Math.max(0, Number(e.target.value)))}
            />
          </div>
        ))}
      </div>

      {totalVehicles > 0 && (
        <div className="fleet-summary">
          <p>
            {numberFormatter.format(totalVehicles)} vehículo{totalVehicles === 1 ? "" : "s"} seleccionado
            {totalVehicles === 1 ? "" : "s"} · {numberFormatter.format(totalWeightKg)} kg efectivos combinados ·{" "}
            {numberFormatter.format(Number(totalVolumeM3.toFixed(1)))} m³ combinados
          </p>
          <p className="fleet-order-hint">
            Orden de asignación (mayor a menor capacidad): {order.map((t) => t.name || "?").join(" → ")}
          </p>
        </div>
      )}
    </div>
  );
}
