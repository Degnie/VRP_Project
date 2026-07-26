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
  const [depotX, setDepotX] = useState("");
  const [depotY, setDepotY] = useState("");
  const [numVehicles, setNumVehicles] = useState("3");
  const [capacity, setCapacity] = useState("100");
  const [groups, setGroups] = useState<ClientGroup[]>([emptyGroup("row-0"), emptyGroup("row-1"), emptyGroup("row-2")]);
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [vehicleTypes, setVehicleTypes] = useState<VehicleType[]>([]);
  const [fleet, setFleet] = useState<FleetSelectionEntry[]>([]);
  const [expandedClientId, setExpandedClientId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Último snapshot confirmado en el backend, por id — usado para diffear altas/ediciones/bajas.
  const syncedRef = useRef<Map<string, VehicleType>>(new Map());
  // IDs con un POST de creación todavía en vuelo — el useEffect de abajo corre
  // de nuevo por cada tecla mientras el usuario completa nombre/peso/volumen;
  // si el primer POST no terminó todavía, "synced" aún no tiene el id y el
  // draft se re-detecta como "toCreate", disparando un segundo POST para el
  // mismo vehículo (duplicado real, visto de forma intermitente en CI).
  const creatingRef = useRef<Set<string>>(new Set());
  // id -> JSON del último payload que falló al guardar (create/update). Sin
  // esto, un error del backend (ej. nombre demasiado largo) se tragaba en
  // silencio (.catch(() => null)) y el efecto reintentaba el MISMO payload
  // inválido en cada render subsiguiente para siempre, sin que el usuario
  // supiera que su cambio nunca se guardó. Comparar contra el draft actual
  // permite reintentar automáticamente apenas el usuario corrige algo.
  const failedRef = useRef<Map<string, string>>(new Map());
  const [catalogSyncErrors, setCatalogSyncErrors] = useState<Map<string, string>>(new Map());
  // Contador para IDs de filas agregadas a mano ("row-3", "row-4"...) — arranca
  // después de las 3 filas por defecto (row-0..row-2) para no colisionar, y
  // reemplaza el timestamp ilegible que tenía antes (row-3-1721937482013).
  const nextRowNumber = useRef(3);

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

    // Sin nombre no se sincroniza al backend todavía — evita las filas
    // fantasma "(sin nombre)" que quedaban creadas ni bien se agregaba una
    // fila nueva, antes de que el usuario llegara a escribir el nombre.
    const named = (t: VehicleType) => t.name.trim() !== "";

    // No reintentar un draft cuyo payload exacto ya falló la última vez —
    // evita el bucle infinito de requests contra un dato inválido.
    const notPreviouslyFailed = (t: VehicleType) => failedRef.current.get(t.id) !== JSON.stringify(t);

    const deleted = [...synced.keys()].filter((id) => !currentIds.has(id));
    const toCreate = vehicleTypes.filter(
      (t) => named(t) && !synced.has(t.id) && !creatingRef.current.has(t.id) && notPreviouslyFailed(t)
    );
    const toUpdate = vehicleTypes.filter((t) => {
      if (!named(t)) return false;
      const prev = synced.get(t.id);
      return prev && JSON.stringify(prev) !== JSON.stringify(t) && notPreviouslyFailed(t);
    });
    if (deleted.length === 0 && toCreate.length === 0 && toUpdate.length === 0) return;

    (async () => {
      for (const id of deleted) {
        const deletedRow = synced.get(id);
        const ok = await deleteVehicleType(id).then(
          () => true,
          () => false
        );
        if (ok) {
          synced.delete(id);
        } else if (deletedRow) {
          // Bug real: si el DELETE fallaba (red caída, 500), "synced" se
          // borraba igual — en la siguiente pasada del efecto el vehículo ya
          // no estaba en vehicleTypes NI en synced, así que nunca volvía a
          // aparecer como "deleted" a reintentar. El dueño veía la fila
          // desaparecer sin aviso, y reaparecía sola recién al recargar la
          // página (loadVehicleTypes la traía de vuelta del backend, donde
          // nunca se había borrado). Se restaura la fila localmente con el
          // error visible, en vez de fingir que el borrado se aplicó.
          setVehicleTypes((prev) => (prev.some((t) => t.id === id) ? prev : [...prev, deletedRow]));
          setCatalogSyncErrors((prev) => new Map(prev).set(id, "No se pudo eliminar — revisá tu conexión e intentá de nuevo."));
        }
      }
      for (const draft of toCreate) {
        creatingRef.current.add(draft.id);
        const created = await apiCreateVehicleType(draft).catch((err: Error) => {
          failedRef.current.set(draft.id, JSON.stringify(draft));
          setCatalogSyncErrors((prev) => new Map(prev).set(draft.id, err.message));
          return null;
        });
        if (created) {
          failedRef.current.delete(draft.id);
          setCatalogSyncErrors((prev) => {
            if (!prev.has(draft.id)) return prev;
            const next = new Map(prev);
            next.delete(draft.id);
            return next;
          });
          // El id local (crypto.randomUUID(), createLocalVehicleType) viaja
          // en el POST y el backend lo respeta — created.id === draft.id en
          // el caso normal, así que la fila nunca cambia de key/id a mitad
          // de edición. Igual se arma a partir del draft más reciente (leído
          // vía el updater de setVehicleTypes, no el "vehicleTypes" cerrado
          // en este efecto) en vez de "created" tal cual: si por lo que sea
          // el backend devolviera un id distinto, no se pierde ninguna
          // edición hecha mientras el POST estaba en vuelo (bug real que
          // pasaba antes de que el backend aceptara el id del cliente).
          setVehicleTypes((prev) =>
            prev.map((t) => {
              if (t.id !== draft.id) return t;
              const withNewId = t.id === created.id ? t : { ...t, id: created.id };
              synced.set(withNewId.id, withNewId);
              return withNewId;
            })
          );
          if (created.id !== draft.id) synced.delete(draft.id);
        }
        // Se borra recién acá, después de registrar en "synced" — si no,
        // había una ventana entre el fin del await y el setVehicleTypes
        // (ambos async/microtask) donde ni creatingRef ni synced todavía
        // tenían el id, y una tecla presionada en ese instante hacía que el
        // efecto re-disparara y re-detectara el draft como toCreate de
        // nuevo — un segundo POST duplicado para la misma fila (bug real:
        // terminaba creando 2-3 filas separadas en vez de una).
        creatingRef.current.delete(draft.id);
      }
      for (const t of toUpdate) {
        const saved = await updateVehicleType(t).catch((err: Error) => {
          failedRef.current.set(t.id, JSON.stringify(t));
          setCatalogSyncErrors((prev) => new Map(prev).set(t.id, err.message));
          return null;
        });
        if (saved) {
          synced.set(saved.id, saved);
          failedRef.current.delete(t.id);
          setCatalogSyncErrors((prev) => {
            if (!prev.has(t.id)) return prev;
            const next = new Map(prev);
            next.delete(t.id);
            return next;
          });
        }
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

  // Un tipo de vehículo sin nombre todavía no cuenta como "flota real" — evita
  // que aparezca seleccionable como "(sin nombre)" en Flota disponible hoy
  // mientras el usuario todavía lo está completando.
  const namedVehicleTypes = vehicleTypes.filter((t) => t.name.trim() !== "");
  const simpleMode = namedVehicleTypes.length === 0;

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
        // Reacomoda el contador de "+ Agregar cliente" para no repetir un
        // clientId que el import ya usó (el CSV sin columna de ID también
        // genera row-0, row-1... — mismo esquema que las filas manuales).
        nextRowNumber.current = imported.length;
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

  const addRow = () => {
    const nextId = `row-${nextRowNumber.current}`;
    nextRowNumber.current += 1;
    setGroups((prev) => [...prev, emptyGroup(nextId)]);
  };
  const removeRow = (clientId: string) => setGroups((prev) => prev.filter((g) => g.clientId !== clientId));

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    // Si algún input numérico quedó con un valor que el navegador considera
    // inválido (ej. un dato importado de CSV que no calza con el step de un
    // campo — ya pasó con volumen 0.15 vs step 0.1), el navegador bloquea el
    // submit *antes* de que este handler pueda reaccionar, sin mostrar nada
    // en la UI de React. reportValidity() fuerza el tooltip nativo del
    // navegador a aparecer sobre el campo exacto, en vez de un botón que
    // simplemente no hace nada.
    if (!e.currentTarget.checkValidity()) {
      e.currentTarget.reportValidity();
      setSubmitError("Hay un dato inválido en el formulario — revisá los campos resaltados en rojo.");
      return;
    }

    const validGroups = groups.filter((g) => g.x !== "" && g.y !== "" && g.inCoverage);
    if (validGroups.length === 0) {
      setSubmitError(
        "No hay clientes válidos para resolver — revisá que tengan X/Y cargados y estén dentro de la zona de cobertura."
      );
      return;
    }

    if (simpleMode) {
      const demands = validGroups.map((g) =>
        Math.max(1, Math.round(g.packages.reduce((s, p) => s + p.weightKg, 0)))
      );
      const capacityNum = Number(capacity);
      const overCapacity = validGroups.filter((_, i) => demands[i] > capacityNum);
      if (overCapacity.length > 0) {
        setSubmitError(
          `El pedido de ${overCapacity.map((g) => g.customerName || g.clientId).join(", ")} supera la capacidad por vehículo (${capacityNum} kg) — ningún vehículo puede llevarlo solo.`
        );
        return;
      }
      setSubmitError(null);
      const request: InstanceRequest = {
        instancia_id: instanciaId,
        coordinates: validGroups.map((g) => [Number(g.x), Number(g.y)]),
        // El backend exige demanda entera (invariante del dominio: Cliente.demanda en backend_python/models).
        demands,
        num_vehicles: Number(numVehicles),
        vehicle_capacity: capacityNum,
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

    const { request, overCapacityClientIds, volumeWarnings } = buildInstanceRequest({
      instanciaId,
      depot: { x: depotX, y: depotY },
      clients: validGroups,
      fleet,
      vehicleTypes: namedVehicleTypes,
    });
    if (overCapacityClientIds && overCapacityClientIds.length > 0) {
      setSubmitError(
        `El pedido de ${overCapacityClientIds.join(", ")} supera la capacidad del vehículo más grande seleccionado — ningún vehículo puede llevarlo solo.`
      );
      return;
    }
    if (!request) {
      setSubmitError(
        "Seleccioná al menos un vehículo en 'Flota disponible hoy' antes de resolver."
      );
      return;
    }
    // Volumen es informativo (el solver no lo usa, solo peso) — se avisa pero
    // no bloquea, para no impedir instancias que sí son resolubles por peso.
    setSubmitError(volumeWarnings.length > 0 ? volumeWarnings.join(" ") : null);
    onSubmit(request, validGroups);
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
          <input
            id="depot-x"
            type="number"
            step="any"
            placeholder="-77.03 (Lima)"
            value={depotX}
            onChange={(e) => setDepotX(e.target.value)}
            required
          />
        </div>
        <div className="field-group">
          <label htmlFor="depot-y">Depósito Y</label>
          <input
            id="depot-y"
            type="number"
            step="any"
            placeholder="-12.05 (Lima)"
            value={depotY}
            onChange={(e) => setDepotY(e.target.value)}
            required
          />
        </div>
      </div>

      <VehicleCatalogManager
        vehicleTypes={vehicleTypes}
        onChange={setVehicleTypes}
        onImported={(imported) => {
          for (const t of imported) syncedRef.current.set(t.id, t);
        }}
        syncErrors={catalogSyncErrors}
      />

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
        <FleetSelector vehicleTypes={namedVehicleTypes} fleet={fleet} onChange={setFleet} />
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

      {submitError && (
        <p className="error-message" role="alert">
          {submitError}
        </p>
      )}

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
