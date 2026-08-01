import type { ClientGroup, Package } from "./types";
import { decodeCsvFile, parseCsvText } from "./csv";

export interface ImportedPackageRow {
  clientId: string;
  x: string;
  y: string;
  weightKg: string;
  lengthCm: string; // vacío si no viene la columna
  widthCm: string;
  heightCm: string;
  customerName: string; // vacío si no viene la columna
  customerPhone: string;
  address: string;
}

// Bug real (Ronda 4, ciclo nuevo, dueño): Excel en configuración regional
// es-* (Perú, España, etc.) exporta decimales con coma ("-12,05"), no punto.
// csv.ts ya detecta y cambia el delimitador de columnas a ";" para ese caso
// (documentado ahí), pero eso no alcanza para convertir el propio valor —
// Number("-12,05") da NaN, así que cada fila con un decimal se descartaba en
// silencio como inválida, pudiendo tirar el import completo si TODAS las
// coordenadas tenían decimales (el caso normal en datos geográficos reales).
// Solo se reemplaza si el string tiene el patrón exacto dígitos,dígitos —
// evita tocar un separador de miles real en cualquier otro dato.
function parseLocaleNumber(value: unknown): number {
  if (typeof value !== "string") return Number(value);
  const normalized = /^-?\d+,\d+$/.test(value) ? value.replace(",", ".") : value;
  return Number(normalized);
}

export interface ImportResult {
  depot: { x: string; y: string } | null;
  rows: ImportedPackageRow[]; // sin agrupar todavía — una fila = un paquete
  skipped: number;
}

type ColumnKey =
  | "clientId"
  | "x"
  | "y"
  | "weightKg"
  | "lengthCm"
  | "widthCm"
  | "heightCm"
  | "customerName"
  | "customerPhone"
  | "address";

const HEADER_ALIASES: Record<string, ColumnKey> = {
  cliente_id: "clientId",
  client_id: "clientId",
  id: "clientId",
  identificador: "clientId",
  x: "x",
  lon: "x",
  longitude: "x",
  longitud: "x",
  y: "y",
  lat: "y",
  latitude: "y",
  latitud: "y",
  demand: "weightKg",
  demanda: "weightKg",
  demandas: "weightKg",
  peso: "weightKg",
  peso_kg: "weightKg",
  "peso (kg)": "weightKg",
  weight: "weightKg",
  weight_kg: "weightKg",
  kg: "weightKg",
  largo: "lengthCm",
  length: "lengthCm",
  length_cm: "lengthCm",
  largo_cm: "lengthCm",
  ancho: "widthCm",
  width: "widthCm",
  width_cm: "widthCm",
  ancho_cm: "widthCm",
  alto: "heightCm",
  height: "heightCm",
  height_cm: "heightCm",
  alto_cm: "heightCm",
  nombre: "customerName",
  cliente: "customerName",
  customer_name: "customerName",
  customer: "customerName",
  name: "customerName",
  destinatario: "customerName",
  telefono: "customerPhone",
  "teléfono": "customerPhone",
  celular: "customerPhone",
  phone: "customerPhone",
  phone_number: "customerPhone",
  whatsapp: "customerPhone",
  direccion: "address",
  "dirección": "address",
  address: "address",
  referencia: "address",
  address_reference: "address",
};

function rowsFromMatrix(matrix: unknown[][]): ImportResult {
  if (matrix.length === 0) return { depot: null, rows: [], skipped: 0 };

  const header = matrix[0].map((cell) => String(cell).trim().toLowerCase());
  const colIndex: Partial<Record<ColumnKey, number>> = {};
  header.forEach((name, i) => {
    const key = HEADER_ALIASES[name];
    if (key && colIndex[key] === undefined) colIndex[key] = i;
  });

  const hasHeader = colIndex.x !== undefined && colIndex.y !== undefined;
  const dataRows = (hasHeader ? matrix.slice(1) : matrix).filter(
    (row) => row.length > 0 && !row.every((c) => c === "" || c === undefined || c === null)
  );
  const xi = colIndex.x ?? 0;
  const yi = colIndex.y ?? 1;
  const wi = colIndex.weightKg ?? 2;
  const ci = colIndex.clientId; // undefined si no hay columna → cada fila es un cliente distinto
  const li = colIndex.lengthCm;
  const wdi = colIndex.widthCm;
  const hi = colIndex.heightCm;
  const cni = colIndex.customerName;
  const cpi = colIndex.customerPhone;
  const ai = colIndex.address;

  // Primera fila de datos = depósito (convención del importador, no del backend).
  const [depotRow, ...clientRows] = dataRows;
  let depot: { x: string; y: string } | null = null;
  if (depotRow) {
    const dx = parseLocaleNumber(depotRow[xi]);
    const dy = parseLocaleNumber(depotRow[yi]);
    if (!Number.isNaN(dx) && !Number.isNaN(dy)) depot = { x: String(dx), y: String(dy) };
  }

  const rows: ImportedPackageRow[] = [];
  let skipped = depot ? 0 : dataRows.length > 0 ? 1 : 0;

  clientRows.forEach((row, idx) => {
    const x = row[xi];
    const y = row[yi];
    const weight = row[wi];
    const xNum = parseLocaleNumber(x);
    const yNum = parseLocaleNumber(y);
    const weightRaw = weight === undefined || weight === "" ? 0 : parseLocaleNumber(weight);

    if (Number.isNaN(xNum) || Number.isNaN(yNum) || Number.isNaN(weightRaw)) {
      skipped += 1;
      return;
    }

    // Bug real: sin el `?? ""` (a diferencia de las columnas hermanas de
    // abajo), una fila más corta que el header por una celda de "id" final
    // vacía/omitida (común al no usar coma trailing en CSV) daba
    // `row[ci] === undefined` → `String(undefined)` === "undefined" (string
    // literal, no vacío) — no caía en el fallback `clientId || row-${idx}`
    // de más abajo. Dos filas así en el mismo archivo terminaban con el
    // mismo clientId "undefined" y groupPackagesByClient las fusionaba en
    // un solo cliente, perdiendo silenciosamente al segundo (y su x/y reales).
    const clientId = ci !== undefined ? String(row[ci] ?? "").trim() : `row-${idx}`;
    const lengthCm = li !== undefined ? String(row[li] ?? "").trim() : "";
    const widthCm = wdi !== undefined ? String(row[wdi] ?? "").trim() : "";
    const heightCm = hi !== undefined ? String(row[hi] ?? "").trim() : "";
    const customerName = cni !== undefined ? String(row[cni] ?? "").trim() : "";
    const customerPhone = cpi !== undefined ? String(row[cpi] ?? "").trim() : "";
    const address = ai !== undefined ? String(row[ai] ?? "").trim() : "";

    rows.push({
      clientId: clientId || `row-${idx}`,
      x: String(xNum),
      y: String(yNum),
      weightKg: String(weightRaw),
      lengthCm,
      widthCm,
      heightCm,
      customerName,
      customerPhone,
      address,
    });
  });

  return { depot, rows, skipped };
}

/**
 * Agrupa filas de paquete por clientId en puntos de entrega únicos.
 * Filas con el mismo clientId comparten coordenadas — si difieren, se usa
 * la de la primera fila del grupo (no bloquea el import por una
 * inconsistencia de datos, el usuario corrige en la tabla editable).
 */
export function groupPackagesByClient(rows: ImportedPackageRow[]): ClientGroup[] {
  const groups = new Map<string, ClientGroup>();

  for (const row of rows) {
    const weightKg = Number(row.weightKg) || 0;
    const lengthCm = Number(row.lengthCm) || 0;
    const widthCm = Number(row.widthCm) || 0;
    const heightCm = Number(row.heightCm) || 0;
    const pkg: Package = { weightKg, lengthCm, widthCm, heightCm };

    const existing = groups.get(row.clientId);
    if (existing) {
      existing.packages.push(pkg);
    } else {
      groups.set(row.clientId, {
        clientId: row.clientId,
        x: row.x,
        y: row.y,
        packages: [pkg],
        inCoverage: true,
        customerName: row.customerName || undefined,
        customerPhone: row.customerPhone || undefined,
        address: row.address || undefined,
      });
    }
  }

  return Array.from(groups.values());
}

export async function importClientsFromFile(file: File): Promise<ImportResult> {
  const isCsv = file.name.toLowerCase().endsWith(".csv") || file.type === "text/csv";

  if (isCsv) {
    const text = await decodeCsvFile(file);
    return rowsFromMatrix(parseCsvText(text));
  }

  const XLSX = await import("xlsx");
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });
  const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
  const matrix = XLSX.utils.sheet_to_json<unknown[]>(firstSheet, { header: 1, blankrows: false });
  return rowsFromMatrix(matrix);
}
