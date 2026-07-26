import type { VehicleType, VehicleTypeDTO } from "./types";
import { decodeCsvFile, parseCsvText } from "./csv";
import { api } from "./api";

function toDTO(t: Partial<Pick<VehicleType, "id">> & Omit<VehicleType, "id">): VehicleTypeDTO {
  return {
    id: t.id,
    name: t.name,
    weight_capacity_kg: t.weightCapacityKg,
    volume_capacity_m3: t.volumeCapacityM3,
    tolerance_margin: t.toleranceMargin,
  };
}

function fromDTO(dto: VehicleTypeDTO & { id: string }): VehicleType {
  return {
    id: dto.id,
    name: dto.name,
    weightCapacityKg: dto.weight_capacity_kg,
    volumeCapacityM3: dto.volume_capacity_m3,
    toleranceMargin: dto.tolerance_margin,
  };
}

export async function loadVehicleTypes(): Promise<VehicleType[]> {
  const dtos = await api.listVehicleCatalog();
  return dtos.map((d) => fromDTO(d as VehicleTypeDTO & { id: string }));
}

/** Fila en borrador, todavía no persistida (id local — ver createVehicleType para guardarla). */
export function createLocalVehicleType(partial: Omit<VehicleType, "id">): VehicleType {
  return { id: crypto.randomUUID(), ...partial };
}

export async function createVehicleType(
  partial: (Partial<Pick<VehicleType, "id">> & Omit<VehicleType, "id">)
): Promise<VehicleType> {
  const dto = await api.createVehicleCatalogEntry(toDTO(partial));
  return fromDTO(dto as VehicleTypeDTO & { id: string });
}

export async function updateVehicleType(type: VehicleType): Promise<VehicleType> {
  const dto = await api.updateVehicleCatalogEntry(type.id, toDTO(type));
  return fromDTO({ ...dto, id: type.id } as VehicleTypeDTO & { id: string });
}

export async function deleteVehicleType(id: string): Promise<void> {
  await api.deleteVehicleCatalogEntry(id);
}

type VehicleColumnKey = "name" | "weightCapacityKg" | "volumeCapacityM3" | "toleranceMargin";

const HEADER_ALIASES: Record<string, VehicleColumnKey> = {
  nombre: "name",
  name: "name",
  vehiculo: "name",
  tipo: "name",
  peso_kg: "weightCapacityKg",
  "peso (kg)": "weightCapacityKg",
  peso_maximo_kg: "weightCapacityKg",
  capacidad_peso_kg: "weightCapacityKg",
  weight_capacity_kg: "weightCapacityKg",
  volumen_m3: "volumeCapacityM3",
  "volumen (m3)": "volumeCapacityM3",
  capacidad_volumen_m3: "volumeCapacityM3",
  volume_capacity_m3: "volumeCapacityM3",
  margen: "toleranceMargin",
  margen_pct: "toleranceMargin",
  "margen (%)": "toleranceMargin",
  tolerance_margin: "toleranceMargin",
};

export interface VehicleImportRow {
  name: string;
  weightCapacityKg: number;
  volumeCapacityM3: number;
  toleranceMargin: number;
}

export interface VehicleImportResult {
  rows: VehicleImportRow[];
  skipped: number;
}

function vehicleRowsFromMatrix(matrix: string[][]): VehicleImportResult {
  if (matrix.length === 0) return { rows: [], skipped: 0 };

  const header = matrix[0].map((cell) => cell.trim().toLowerCase());
  const colIndex: Partial<Record<VehicleColumnKey, number>> = {};
  header.forEach((name, i) => {
    const key = HEADER_ALIASES[name];
    if (key && colIndex[key] === undefined) colIndex[key] = i;
  });

  const hasHeader = colIndex.name !== undefined && colIndex.weightCapacityKg !== undefined;
  const dataRows = (hasHeader ? matrix.slice(1) : matrix).filter(
    (row) => row.length > 0 && !row.every((c) => c === "")
  );
  const ni = colIndex.name ?? 0;
  const wi = colIndex.weightCapacityKg ?? 1;
  const vi = colIndex.volumeCapacityM3 ?? 2;
  const mi = colIndex.toleranceMargin ?? 3;

  const rows: VehicleImportRow[] = [];
  let skipped = 0;

  for (const row of dataRows) {
    const name = (row[ni] ?? "").trim();
    const weightRaw = Number(row[wi]);
    const volumeRaw = row[vi] !== undefined && row[vi] !== "" ? Number(row[vi]) : 1;
    // Margen puede venir como fracción (0.9) o porcentaje (90) — >1 se interpreta como %.
    const marginRaw = row[mi] !== undefined && row[mi] !== "" ? Number(row[mi]) : 0.9;

    if (!name || Number.isNaN(weightRaw) || weightRaw <= 0 || Number.isNaN(volumeRaw) || Number.isNaN(marginRaw)) {
      skipped += 1;
      continue;
    }

    const toleranceMargin = marginRaw > 1 ? Math.min(1, Math.max(0.5, marginRaw / 100)) : Math.min(1, Math.max(0.5, marginRaw));

    rows.push({
      name,
      weightCapacityKg: weightRaw,
      volumeCapacityM3: volumeRaw > 0 ? volumeRaw : 1,
      toleranceMargin,
    });
  }

  return { rows, skipped };
}

async function parseVehicleImportFile(file: File): Promise<VehicleImportResult> {
  const isCsv = file.name.toLowerCase().endsWith(".csv") || file.type === "text/csv";

  if (isCsv) {
    const text = await decodeCsvFile(file);
    return vehicleRowsFromMatrix(parseCsvText(text));
  }

  const XLSX = await import("xlsx");
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });
  const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
  const matrix = XLSX.utils.sheet_to_json<string[]>(firstSheet, { header: 1, blankrows: false });
  return vehicleRowsFromMatrix(matrix.map((row) => row.map((c) => String(c ?? ""))));
}

export interface VehicleImportOutcome {
  types: VehicleType[];
  skipped: number;
  /** Nombres de filas que sí pasaron el parseo pero el POST al backend falló. */
  failed: string[];
}

/** Importa un archivo y crea cada fila válida en el backend (una llamada por fila). */
export async function importVehicleTypesFromFile(file: File): Promise<VehicleImportOutcome> {
  const { rows, skipped } = await parseVehicleImportFile(file);
  const types: VehicleType[] = [];
  const failed: string[] = [];
  // Bug real: un `for` con `await` sin try/catch por fila hacía que el POST
  // fallido de una fila intermedia (red inestable, 500 puntual) cortara la
  // función entera — las filas ANTERIORES ya habían quedado creadas en el
  // backend, pero el throw impedía retornarlas, así que la UI no mostraba
  // ninguna y el catch genérico del caller decía "archivo inválido" (falso:
  // el archivo se leyó bien, algunas filas sí se persistieron). Reintentar
  // el mismo archivo duplicaba esas filas ya creadas. Ahora cada fila se
  // aísla: las que sí se crean se devuelven igual, las que fallan se listan.
  for (const row of rows) {
    try {
      types.push(await createVehicleType(row));
    } catch {
      failed.push(row.name);
    }
  }
  return { types, skipped, failed };
}
