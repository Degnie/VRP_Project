import type { ClientGroup, SolutionResponse } from "./types";

function csvCell(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** Arma el CSV de la hoja de ruta (todas las paradas de todos los vehículos). */
export function buildRouteCsv(solution: SolutionResponse, contacts: ClientGroup[] | null): string {
  const header = ["vehiculo", "parada", "cliente", "nombre", "telefono", "direccion"];
  const rows = [header];

  for (const route of solution.routes) {
    route.sequence.forEach((clientIndex, i) => {
      const contact = contacts?.[clientIndex - 1];
      rows.push([
        String(route.vehicle_id),
        String(i + 1),
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
export function downloadRouteCsv(solution: SolutionResponse, contacts: ClientGroup[] | null): void {
  const csv = buildRouteCsv(solution, contacts);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `ruta_${solution.instancia_id}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}
