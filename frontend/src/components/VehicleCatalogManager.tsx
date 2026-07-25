import { useRef, useState } from "react";
import type { VehicleType } from "../lib/types";
import { createLocalVehicleType, importVehicleTypesFromFile } from "../lib/vehicleCatalog";

interface Props {
  vehicleTypes: VehicleType[];
  onChange: (types: VehicleType[]) => void;
}

export function VehicleCatalogManager({ vehicleTypes, onChange }: Props) {
  const [open, setOpen] = useState(vehicleTypes.length === 0);
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const { types, skipped } = await importVehicleTypesFromFile(file);
      if (types.length === 0) {
        setImportStatus("El archivo no tiene filas válidas (se esperan columnas Nombre, Peso, Volumen, Margen).");
      } else {
        onChange([...vehicleTypes, ...types]);
        setImportStatus(
          skipped > 0
            ? `Se importaron ${types.length} tipos de vehículo — ${skipped} filas omitidas por datos inválidos.`
            : `Se importaron ${types.length} tipos de vehículo.`
        );
      }
    } catch {
      setImportStatus("No se pudo leer el archivo. Verificá que sea un CSV o Excel válido.");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const updateType = (id: string, field: keyof VehicleType, value: string) => {
    onChange(
      vehicleTypes.map((t) => {
        if (t.id !== id) return t;
        if (field === "name") return { ...t, name: value };
        if (field === "toleranceMargin") return { ...t, toleranceMargin: Math.min(1, Math.max(0.5, Number(value) / 100)) };
        return { ...t, [field]: Number(value) };
      })
    );
  };

  const addType = () => {
    onChange([
      ...vehicleTypes,
      createLocalVehicleType({ name: "", weightCapacityKg: 100, volumeCapacityM3: 1, toleranceMargin: 0.9 }),
    ]);
  };

  const removeType = (id: string) => {
    onChange(vehicleTypes.filter((t) => t.id !== id));
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
            {vehicleTypes.map((type) => (
              <div className="vehicle-table-row" role="row" key={type.id}>
                <input
                  aria-label="Nombre del vehículo"
                  value={type.name}
                  placeholder="Moto, camioneta…"
                  onChange={(e) => updateType(type.id, "name", e.target.value)}
                />
                <input
                  aria-label="Capacidad de peso en kg"
                  type="number"
                  min="1"
                  step="1"
                  value={type.weightCapacityKg}
                  onChange={(e) => updateType(type.id, "weightCapacityKg", e.target.value)}
                />
                <input
                  aria-label="Capacidad de volumen en metros cúbicos"
                  type="number"
                  min="0.1"
                  step="0.1"
                  value={type.volumeCapacityM3}
                  onChange={(e) => updateType(type.id, "volumeCapacityM3", e.target.value)}
                />
                <input
                  aria-label="Margen de tolerancia en porcentaje"
                  type="number"
                  min="50"
                  max="100"
                  step="1"
                  value={Math.round(type.toleranceMargin * 100)}
                  onChange={(e) => updateType(type.id, "toleranceMargin", e.target.value)}
                />
                <button
                  type="button"
                  className="row-remove"
                  onClick={() => removeType(type.id)}
                  aria-label={`Eliminar vehículo ${type.name || "sin nombre"}`}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
          <button type="button" className="btn-secondary" onClick={addType}>
            + Agregar tipo de vehículo
          </button>
        </>
      )}
    </fieldset>
  );
}
