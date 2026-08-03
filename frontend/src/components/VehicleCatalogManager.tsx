import { useRef, useState } from "react";
import type { VehicleType } from "../lib/types";
import { createLocalVehicleType, importVehicleTypesFromFile } from "../lib/vehicleCatalog";

interface Props {
  vehicleTypes: VehicleType[];
  // Acepta también la forma funcional (updater) — necesaria para que
  // updateType/addType/removeType no partan de la prop "vehicleTypes"
  // (snapshot del último render, potencialmente stale si dos filas cambian
  // casi al mismo tiempo). React garantiza que cada callback pasado a
  // setVehicleTypes recibe el estado más reciente en el momento en que
  // corre, aunque llegaron varios "onChange" en el mismo tick.
  onChange: (update: VehicleType[] | ((prev: VehicleType[]) => VehicleType[])) => void;
  // Se dispara con las filas recién importadas, YA persistidas en el backend
  // (importVehicleTypesFromFile crea cada una vía la API) — el caller debe
  // registrarlas como sincronizadas para que el diff-sync de InstanceForm no
  // las vuelva a crear por duplicado al verlas llegar por onChange.
  onImported?: (types: VehicleType[]) => void;
  // id -> mensaje de error del último intento de guardar esa fila (create o
  // update) que falló — antes esto se tragaba en silencio y la fila se veía
  // "normal" en pantalla aunque nunca se hubiera persistido en el backend.
  syncErrors?: Map<string, string>;
  // Bug real (Ronda 4, ciclo 5, dueño): borrar una fila cuyo POST de
  // creación seguía en vuelo la sacaba de vehicleTypes/synced antes de que
  // el POST resolviera — ni el diff-sync ni el manejo de la respuesta
  // podían encontrarla para borrarla del backend, dejando un tipo de
  // vehículo huérfano persistido que reaparecía al recargar la página.
  creatingIds?: Set<string>;
}

export function VehicleCatalogManager({ vehicleTypes, onChange, onImported, syncErrors, creatingIds }: Props) {
  const [open, setOpen] = useState(vehicleTypes.length === 0);
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const { types, skipped, failed } = await importVehicleTypesFromFile(file);
      if (types.length === 0 && failed.length === 0) {
        setImportStatus("El archivo no tiene filas válidas (se esperan columnas Nombre, Peso, Volumen, Margen).");
      } else {
        // Las filas que sí se crearon en el backend se registran igual,
        // aunque otras hayan fallado — perderlas de la UI local mientras
        // quedan persistidas en el servidor es lo que causaba duplicados al
        // reintentar el mismo archivo completo.
        if (types.length > 0) {
          onImported?.(types);
          onChange((prev) => [...prev, ...types]);
        }
        const parts = [
          types.length > 0 ? `Se importaron ${types.length} tipos de vehículo.` : null,
          skipped > 0 ? `${skipped} filas omitidas por datos inválidos.` : null,
          failed.length > 0
            ? `No se pudieron guardar en el servidor: ${failed.join(", ")} — no reintentés el archivo completo (ya duplicaría las filas que sí se guardaron), agregalas a mano o probá de nuevo solo esas filas.`
            : null,
        ].filter(Boolean);
        setImportStatus(parts.join(" "));
      }
    } catch {
      setImportStatus("No se pudo leer el archivo. Verificá que sea un CSV o Excel válido.");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const updateType = (id: string, field: keyof VehicleType, value: string) => {
    onChange((prev) =>
      prev.map((t) => {
        if (t.id !== id) return t;
        if (field === "name") return { ...t, name: value };
        if (field === "toleranceMargin") return { ...t, toleranceMargin: Math.min(1, Math.max(0.5, Number(value) / 100)) };
        return { ...t, [field]: Number(value) };
      })
    );
  };

  const addType = () => {
    // El id (crypto.randomUUID()) se genera UNA vez, afuera del updater —
    // un updater de setState debe ser puro (React puede invocarlo más de
    // una vez, ej. en StrictMode). Generar el id adentro hacía que cada
    // invocación creara una fila con identidad distinta, resultando en 2
    // filas nuevas por un solo click bajo StrictMode, además de robarle el
    // foco a cualquier input que estuviera recibiendo tecleo en simultáneo.
    const newRow = createLocalVehicleType({ name: "", weightCapacityKg: 100, volumeCapacityM3: 1, toleranceMargin: 0.9 });
    onChange((prev) => [...prev, newRow]);
  };

  const removeType = (id: string) => {
    onChange((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <fieldset className="vehicle-catalog-fieldset">
      <legend>
        <button type="button" className="section-toggle" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          Catálogo de vehículos {open ? "▾" : "▸"}
        </button>
      </legend>

      {open && (
        <>
          <div className="import-row">
            <label htmlFor="vehicles-file" className="btn-secondary import-label">
              Importar catálogo (CSV/Excel)
            </label>
            <input
              ref={fileInputRef}
              id="vehicles-file"
              type="file"
              accept=".csv,.xlsx,.xls,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={handleFileImport}
              className="import-input"
            />
          </div>
          {importStatus && (
            <p className="import-status" role="status" aria-live="polite">
              {importStatus}
            </p>
          )}

          <div className="vehicle-table" role="table">
            <div className="vehicle-table-head" role="row">
              <span role="columnheader">Nombre</span>
              <span role="columnheader">Peso (kg)</span>
              <span role="columnheader">Volumen (m³)</span>
              <span role="columnheader">Margen (%)</span>
              <span role="columnheader" aria-hidden="true"></span>
            </div>
            {vehicleTypes.map((type) => {
              const syncError = syncErrors?.get(type.id);
              return (
              <div className="vehicle-table-row-wrap" key={type.id}>
              <div className="vehicle-table-row" role="row">
                <input
                  aria-label="Nombre del vehículo"
                  value={type.name}
                  placeholder="Moto, camioneta…"
                  className={type.name.trim() === "" ? "input-needs-name" : syncError ? "input-sync-error" : undefined}
                  onChange={(e) => updateType(type.id, "name", e.target.value)}
                />
                <input
                  aria-label="Capacidad de peso en kg"
                  type="number"
                  min="1"
                  step="any"
                  value={type.weightCapacityKg}
                  className={type.weightCapacityKg <= 0 ? "input-needs-name" : undefined}
                  onChange={(e) => updateType(type.id, "weightCapacityKg", e.target.value)}
                />
                {/* step="any": datos importados de CSV/Excel (ej. volumen 0.15 m³) no
                    calzan con un step="0.1" fijo — un valor "inválido" para el navegador
                    bloquea el submit del <form> de forma silenciosa (sin pasar por React
                    ni mostrar ningún mensaje en la UI), dejando el botón "Resolver
                    instancia" sin reaccionar y sin explicación visible. */}
                <input
                  aria-label="Capacidad de volumen en metros cúbicos"
                  type="number"
                  min="0.01"
                  step="any"
                  value={type.volumeCapacityM3}
                  className={type.volumeCapacityM3 <= 0 ? "input-needs-name" : undefined}
                  onChange={(e) => updateType(type.id, "volumeCapacityM3", e.target.value)}
                />
                <input
                  aria-label="Margen de tolerancia en porcentaje"
                  type="number"
                  min="50"
                  max="100"
                  step="any"
                  value={Math.round(type.toleranceMargin * 100)}
                  onChange={(e) => updateType(type.id, "toleranceMargin", e.target.value)}
                />
                <button
                  type="button"
                  className="row-remove"
                  onClick={() => removeType(type.id)}
                  disabled={creatingIds?.has(type.id)}
                  aria-label={`Eliminar vehículo ${type.name || "sin nombre"}`}
                  title={creatingIds?.has(type.id) ? "Guardando… esperá a que termine para eliminar" : undefined}
                >
                  ×
                </button>
              </div>
              {syncError && (
                <p className="vehicle-sync-error" role="alert">
                  No se pudo guardar: {syncError}
                </p>
              )}
              </div>
              );
            })}
          </div>
          <button type="button" className="btn-secondary" onClick={addType}>
            + Agregar tipo de vehículo
          </button>
        </>
      )}
    </fieldset>
  );
}
