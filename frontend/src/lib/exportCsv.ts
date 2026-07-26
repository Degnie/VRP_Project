import type { ClientGroup, SolutionResponse } from "./types";

function csvCell(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** Arma el CSV de la hoja de ruta (todas las paradas de todos los vehículos).
 *
 * `rescheduledClientIndexes`: bug real (Ronda 48) — reprogramar un pedido lo
 * marca "reprogramado" en pantalla (con aviso visible), pero `solution.routes`
 * nunca se recalcula (solo "Resolver de nuevo" lo hace), así que sin este
 * filtro el CSV exportado seguía incluyendo esas paradas como si fueran
 * trabajo real — un repartidor que solo recibe el CSV (no la pantalla) iba a
 * una dirección que ya no le corresponde, sin ninguna marca que lo distinga. */
export function buildRouteCsv(
  solution: SolutionResponse,
  contacts: ClientGroup[] | null,
  rescheduledClientIndexes?: ReadonlySet<number>
): string {
  const header = ["vehiculo", "parada", "cliente", "nombre", "telefono", "direccion"];
  const rows = [header];

  for (const route of solution.routes) {
    let stopNumber = 0;
    route.sequence.forEach((clientIndex) => {
      if (rescheduledClientIndexes?.has(clientIndex)) return;
      stopNumber += 1;
      const contact = contacts?.[clientIndex - 1];
      rows.push([
        String(route.vehicle_id),
        String(stopNumber),
        `Cliente #${clientIndex}`,
        contact?.customerName ?? "",
        contact?.customerPhone ?? "",
        contact?.address ?? "",
      ]);
    });
  }

  return rows.map((row) => row.map(csvCell).join(",")).join("\n");
}

/** Descarga el CSV de la hoja de ruta en el navegador. */
export function downloadRouteCsv(
  solution: SolutionResponse,
  contacts: ClientGroup[] | null,
  rescheduledClientIndexes?: ReadonlySet<number>
): void {
  const csv = buildRouteCsv(solution, contacts, rescheduledClientIndexes);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `ruta_${solution.instancia_id}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}
