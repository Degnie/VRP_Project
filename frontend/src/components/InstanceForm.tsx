import { useEffect, useRef, useState } from "react";
import type { ClientGroup, FleetSelectionEntry, InstanceRequest, Package, VehicleType } from "../lib/types";
import { groupPackagesByClient, importClientsFromFile } from "../lib/importClients";
import { loadVehicleTypes, createVehicleType as apiCreateVehicleType, updateVehicleType, deleteVehicleType } from "../lib/vehicleCatalog";
import { isWithinCoverage } from "../lib/geo";
import { buildInstanceRequest } from "../lib/buildInstance";
import { VehicleCatalogManager } from "./VehicleCatalogManager";
import { FleetSelector } from "./FleetSelector";

const emptyGroup = (id: string): ClientGroup => ({
  clientId: id,
  x: "",
  y: "",
  packages: [{ weightKg: 0, lengthCm: 0, widthCm: 0, heightCm: 0 }],
  inCoverage: true,
});

type ContactField = "customerName" | "customerPhone" | "address";

interface Props {
  onSubmit: (request: InstanceRequest, clients: ClientGroup[]) => void;
  isSolving: boolean;
  coveragePoints: [number, number][];
}

export function InstanceForm({ onSubmit, isSolving, coveragePoints }: Props) {
  const [instanciaId, setInstanciaId] = useState("instancia-1");
  const [depotX, setDepotX] = useState("0");
  const [depotY, setDepotY] = useState("0");
  const [numVehicles, setNumVehicles] = useState("3");
  const [capacity, setCapacity] = useState("100");
  const [groups, setGroups] = useState<ClientGroup[]>([emptyGroup("row-0"), emptyGroup("row-1"), emptyGroup("row-2")]);
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [vehicleTypes, setVehicleTypes] = useState<VehicleType[]>([]);
  const [fleet, setFleet] = useState<FleetSelectionEntry[]>([]);
  const [expandedClientId, setExpandedClientId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Último snapshot confirmado en el backend, por id — usado para diffear altas/ediciones/bajas.
  const syncedRef = useRef<Map<string, VehicleType>>(new Map());

  useEffect(() => {
    loadVehicleTypes()
      .then((types) => {
        syncedRef.current = new Map(types.map((t) => [t.id, t]));
        setVehicleTypes(types);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const synced = syncedRef.current;
    const currentIds = new Set(vehicleTypes.map((t) => t.id));

    const deleted = [...synced.keys()].filter((id) => !currentIds.has(id));
    const toCreate = vehicleTypes.filter((t) => !synced.has(t.id));
    const toUpdate = vehicleTypes.filter((t) => {
      const prev = synced.get(t.id);
      return prev && JSON.stringify(prev) !== JSON.stringify(t);
    });
    if (deleted.length === 0 && toCreate.length === 0 && toUpdate.length === 0) return;

    (async () => {
      for (const id of deleted) {
        await deleteVehicleType(id).catch(() => {});
        synced.delete(id);
      }
      for (const draft of toCreate) {
        const created = await apiCreateVehicleType(draft).catch(() => null);
        if (created) {
          synced.set(created.id, created);
          if (created.id !== draft.id) {
            synced.delete(draft.id);
            setVehicleTypes((prev) => prev.map((t) => (t.id === draft.id ? created : t)));
          }
        }
      }
      for (const t of toUpdate) {
        const saved = await updateVehicleType(t).catch(() => null);
        if (saved) synced.set(saved.id, saved);
      }
    })();
  }, [vehicleTypes]);

  // Recalcula cobertura de todos los clientes cada vez que cambia el polígono
  // guardado (dibujar/redibujar/cerrar en App.tsx), no solo al importar.
  useEffect(() => {
    const zone = coveragePoints.length >= 3 ? { points: coveragePoints } : null;
    setGroups((prev) =>
      prev.map((g) => ({
        ...g,
        inCoverage: g.x === "" || g.y === "" ? true : isWithinCoverage([Number(g.x), Number(g.y)], zone),
      }))
    );
  }, [coveragePoints]);

  const simpleMode = vehicleTypes.length === 0;

  const handleFileImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const { depot, rows, skipped } = await importClientsFromFile(file);
      if (rows.length === 0) {
        setImportStatus("El archivo no tiene filas válidas (se esperan columnas X, Y, Peso, con la primera fila como depósito).");
      } else {
        const zone = coveragePoints.length >= 3 ? { points: coveragePoints } : null;
        const imported = groupPackagesByClient(rows).map((g) => ({
          ...g,
          inCoverage: isWithinCoverage([Number(g.x), Number(g.y)], zone),
        }));
        setGroups(imported);
        if (depot) {
          setDepotX(depot.x);
          setDepotY(depot.y);
        }
        const depotNote = depot ? " (primera fila usada como depósito)" : " (no se pudo leer el depósito, revisá Depósito X/Y)";
        const outOfCoverage = imported.filter((g) => !g.inCoverage).length;
        const coverageNote = outOfCoverage > 0 ? ` — ${outOfCoverage} fuera de zona de cobertura` : "";
        setImportStatus(
          skipped > 0
            ? `Se importaron ${imported.length} clientes${depotNote} — ${skipped} filas omitidas por datos inválidos.${coverageNote}`
            : `Se importaron ${imported.length} clientes${depotNote}.${coverageNote}`
        );
      }
    } catch {
      setImportStatus("No se pudo leer el archivo. Verificá que sea un CSV o Excel válido.");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const updateGroupField = (clientId: string, field: "x" | "y" | ContactField, value: string) => {
    setGroups((prev) => prev.map((g) => (g.clientId === clientId ? { ...g, [field]: value } : g)));
  };

  const updatePackage = (clientId: string, packageIdx: number, field: keyof Package, value: string) => {
    setGroups((prev) =>
      prev.map((g) => {
        if (g.clientId !== clientId) return g;
        const packages = g.packages.map((p, i) => (i === packageIdx ? { ...p, [field]: Number(value) || 0 } : p));
        return { ...g, packages };
      })
    );
  };

  const addPackage = (clientId: string) => {
    setGroups((prev) =>
      prev.map((g) =>
        g.clientId === clientId
          ? { ...g, packages: [...g.packages, { weightKg: 0, lengthCm: 0, widthCm: 0, heightCm: 0 }] }
          : g
      )
    );
  };

  const removePackage = (clientId: string, packageIdx: number) => {
    setGroups((prev) =>
      prev.map((g) => (g.clientId === clientId ? { ...g, packages: g.packages.filter((_, i) => i !== packageIdx) } : g))
    );
  };

  const addRow = () => setGroups((prev) => [...prev, emptyGroup(`row-${prev.length}-${Date.now()}`)]);
  const removeRow = (clientId: string) => setGroups((prev) => prev.filter((g) => g.clientId !== clientId));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const validGroups = groups.filter((g) => g.x !== "" && g.y !== "" && g.inCoverage);
    if (validGroups.length === 0) return;

    if (simpleMode) {
      const request: InstanceRequest = {
        instancia_id: instanciaId,
        coordinates: validGroups.map((g) => [Number(g.x), Number(g.y)]),
        // El backend exige demanda entera (invariante del dominio: Cliente.demanda en backend_python/models).
        demands: validGroups.map((g) => Math.max(1, Math.round(g.packages.reduce((s, p) => s + p.weightKg, 0)))),
        num_vehicles: Number(numVehicles),
        vehicle_capacity: Number(capacity),
        depot_coordinates: [Number(depotX), Number(depotY)],
        contacts: validGroups.map((g) =>
          g.customerName || g.customerPhone || g.address
            ? { customer_name: g.customerName, customer_phone: g.customerPhone, address: g.address }
            : null
        ),
      };
      onSubmit(request, validGroups);
      return;
    }

    const { request } = buildInstanceRequest({
      instanciaId,
      depot: { x: depotX, y: depotY },
      clients: validGroups,
      fleet,
      vehicleTypes,
    });
    if (request) onSubmit(request, validGroups);
  };

  return (
    <form className="instance-form" onSubmit={handleSubmit}>
      <h2>Hoja de despacho</h2>
      <div className="field-group">
        <label htmlFor="instancia-id">ID de instancia</label>
        <input
          id="instancia-id"
          name="instancia-id"
          autoComplete="off"
          value={instanciaId}
          onChange={(e) => setInstanciaId(e.target.value)}
          required
        />
      </div>

      <div className="field-row">
        <div className="field-group">
          <label htmlFor="depot-x">Depósito X</label>
          <input id="depot-x" type="number" step="any" value={depotX} onChange={(e) => setDepotX(e.target.value)} required />
        </div>
        <div className="field-group">
          <label htmlFor="depot-y">Depósito Y</label>
          <input id="depot-y" type="number" step="any" value={depotY} onChange={(e) => setDepotY(e.target.value)} required />
        </div>
      </div>

      <VehicleCatalogManager vehicleTypes={vehicleTypes} onChange={setVehicleTypes} />

      {simpleMode ? (
        <div className="field-row">
          <div className="field-group">
            <label htmlFor="num-vehicles">N° vehículos</label>
            <input id="num-vehicles" type="number" min="1" value={numVehicles} onChange={(e) => setNumVehicles(e.target.value)} required />
          </div>
          <div className="field-group">
            <label htmlFor="capacity">Capacidad por vehículo (kg)</label>
            <input id="capacity" type="number" min="0" step="any" value={capacity} onChange={(e) => setCapacity(e.target.value)} required />
          </div>
        </div>
      ) : (
        <FleetSelector vehicleTypes={vehicleTypes} fleet={fleet} onChange={setFleet} />
      )}

      <fieldset className="clients-fieldset">
        <legend>Clientes</legend>

        <div className="import-row">
          <label htmlFor="clients-file" className="btn-secondary import-label">
            Importar desde archivo (CSV/Excel)
          </label>
          <input
            ref={fileInputRef}
            id="clients-file"
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

        <div className="clients-list">
          <div className="clients-list-head">
            <span>Cliente</span>
            <span>Contacto</span>
            <span>Peso</span>
            <span aria-hidden="true"></span>
          </div>
          {groups.map((group) => {
            const totalWeight = group.packages.reduce((s, p) => s + p.weightKg, 0);
            const isExpanded = expandedClientId === group.clientId;
            return (
              <div
                className={group.inCoverage ? "client-card" : "client-card client-row--out-of-coverage"}
                key={group.clientId}
              >
                <button
                  type="button"
                  className="client-card-summary"
                  onClick={() => setExpandedClientId(isExpanded ? null : group.clientId)}
                  aria-expanded={isExpanded}
                >
                  <span className="client-summary-id">
                    {group.customerName || group.clientId}
                    {!group.inCoverage && <span className="coverage-badge"> · Fuera de cobertura</span>}
                  </span>
                  <span className="client-summary-contact">{group.customerPhone || "sin teléfono"}</span>
                  <span className="client-summary-weight">
                    {totalWeight} kg · {group.packages.length} paquete{group.packages.length === 1 ? "" : "s"}
                  </span>
                  <span className="client-summary-toggle" aria-hidden="true">{isExpanded ? "▾" : "▸"}</span>
                </button>

                {isExpanded && (
                  <div className="client-card-details">
                    <div className="field-row">
                      <div className="field-group">
                        <label htmlFor={`x-${group.clientId}`}>X</label>
                        <input
                          id={`x-${group.clientId}`}
                          type="number"
                          step="any"
                          value={group.x}
                          onChange={(e) => updateGroupField(group.clientId, "x", e.target.value)}
                        />
                      </div>
                      <div className="field-group">
                        <label htmlFor={`y-${group.clientId}`}>Y</label>
                        <input
                          id={`y-${group.clientId}`}
                          type="number"
                          step="any"
                          value={group.y}
                          onChange={(e) => updateGroupField(group.clientId, "y", e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="field-group">
                      <label htmlFor={`name-${group.clientId}`}>Nombre del cliente</label>
                      <input
                        id={`name-${group.clientId}`}
                        value={group.customerName ?? ""}
                        placeholder="Nombre y apellido"
                        onChange={(e) => updateGroupField(group.clientId, "customerName", e.target.value)}
                      />
                    </div>
                    <div className="field-row">
                      <div className="field-group">
                        <label htmlFor={`phone-${group.clientId}`}>Teléfono</label>
                        <input
                          id={`phone-${group.clientId}`}
                          type="tel"
                          value={group.customerPhone ?? ""}
                          placeholder="999 999 999"
                          onChange={(e) => updateGroupField(group.clientId, "customerPhone", e.target.value)}
                        />
                      </div>
                      <div className="field-group">
                        <label htmlFor={`address-${group.clientId}`}>Dirección / referencia</label>
                        <input
                          id={`address-${group.clientId}`}
                          value={group.address ?? ""}
                          placeholder="Av. Ejemplo 123, frente al..."
                          onChange={(e) => updateGroupField(group.clientId, "address", e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="client-packages">
                      <span className="client-packages-summary">Paquetes</span>
                      {group.packages.map((pkg, i) => (
                        <div className="package-row" key={i}>
                          <input
                            aria-label={`Paquete ${i + 1} de ${group.clientId} peso en kg`}
                            type="number"
                            min="0"
                            step="1"
                            placeholder="kg"
                            value={pkg.weightKg || ""}
                            onChange={(e) => updatePackage(group.clientId, i, "weightKg", e.target.value)}
                          />
                          <input
                            aria-label={`Paquete ${i + 1} de ${group.clientId} largo en cm`}
                            type="number"
                            min="0"
                            step="1"
                            placeholder="largo cm"
                            value={pkg.lengthCm || ""}
                            onChange={(e) => updatePackage(group.clientId, i, "lengthCm", e.target.value)}
                          />
                          <input
                            aria-label={`Paquete ${i + 1} de ${group.clientId} ancho en cm`}
                            type="number"
                            min="0"
                            step="1"
                            placeholder="ancho cm"
                            value={pkg.widthCm || ""}
                            onChange={(e) => updatePackage(group.clientId, i, "widthCm", e.target.value)}
                          />
                          <input
                            aria-label={`Paquete ${i + 1} de ${group.clientId} alto en cm`}
                            type="number"
                            min="0"
                            step="1"
                            placeholder="alto cm"
                            value={pkg.heightCm || ""}
                            onChange={(e) => updatePackage(group.clientId, i, "heightCm", e.target.value)}
                          />
                          <button
                            type="button"
                            className="row-remove"
                            onClick={() => removePackage(group.clientId, i)}
                            disabled={group.packages.length <= 1}
                            aria-label={`Eliminar paquete ${i + 1} de ${group.clientId}`}
                          >
                            ×
                          </button>
                        </div>
                      ))}
                      <button type="button" className="btn-tertiary" onClick={() => addPackage(group.clientId)}>
                        + paquete
                      </button>
                    </div>

                    <button
                      type="button"
                      className="btn-secondary client-remove"
                      onClick={() => removeRow(group.clientId)}
                      disabled={groups.length <= 1}
                    >
                      Eliminar cliente
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <button type="button" className="btn-secondary" onClick={addRow}>
          + Agregar cliente
        </button>
      </fieldset>

      <button
        type="submit"
        className={isSolving ? "btn-primary btn-primary--solving" : "btn-primary"}
        disabled={isSolving}
      >
        {isSolving ? "Resolviendo…" : "Resolver instancia"}
      </button>
    </form>
  );
}
