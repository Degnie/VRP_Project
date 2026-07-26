import { useEffect, useState } from "react";
import type { ClientGroup, DeliveryStatus, InstanceRequest, RouteEta, SolutionResponse, TeamMember } from "../lib/types";
import { fetchRouteWithDuration } from "../lib/osrm";
import { estimateRouteEtas } from "../lib/eta";
import { downloadRouteCsv } from "../lib/exportCsv";
import { api } from "../lib/api";
import { DeliveryStatusControl } from "./DeliveryStatusControl";
import { ClientEditControl } from "./ClientEditControl";
import { ConfirmDialog } from "./ConfirmDialog";

const ROUTE_COLORS = [
  "#2f6f4f", "#c4622d", "#3a5a9e", "#a3383c", "#7a5c9e", "#2e8b8b", "#b08a1e", "#5c6b73",
];

const countFormatter = new Intl.NumberFormat();
// El backend devuelve la distancia OSRM/euclídea cruda en metros (no es
// dinero, pese a llamarse "costo" internamente) — se muestra en km, con la
// etiqueta correcta, para no inducir al dueño a leerla como un monto.
const distanceFormatter = new Intl.NumberFormat(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const formatDistanceKm = (meters: number) => `${distanceFormatter.format(meters / 1000)} km`;

interface Props {
  solution: SolutionResponse;
  instance: InstanceRequest | null;
  contacts: ClientGroup[] | null;
  // Se dispara al resolver una instancia reprogramada exitosamente — sin
  // esto, "Resolver ahora" actualizaba la solución en el backend pero el
  // panel entero (asignar repartidor, exportar, estados de entrega, mapa)
  // seguía apuntando a la instancia ORIGINAL, dejando al dueño/operario sin
  // forma de actuar sobre la reprogramada recién resuelta.
  onSolvedInstanceChange?: (solution: SolutionResponse) => void;
  // Se dispara tras eliminar la instancia exitosamente — antes no había
  // forma de sacar una instancia de prueba/duplicada de la lista, quedaba
  // visible para siempre en GET /instances.
  onInstanceDeleted?: () => void;
}

export function SolutionSummary({ solution, instance, contacts, onSolvedInstanceChange, onInstanceDeleted }: Props) {
  // Estado local en vez de leer `contacts` directamente: editar un cliente
  // (ClientEditControl) actualiza solo la vista de ESTA instancia sin tener
  // que subir un callback más a App.tsx — se resetea si cambia `contacts`
  // (nueva instancia/solución cargada) para no arrastrar ediciones viejas.
  const [localContacts, setLocalContacts] = useState(contacts);
  useEffect(() => setLocalContacts(contacts), [contacts]);

  // Editar la coordenada de un cliente ya resuelto NO recalcula la ruta —
  // update_client solo corrige la fila del cliente, la ruta/costo/ETA
  // mostrados siguen siendo los de ANTES del cambio. Sin este aviso, el
  // dueño podía terminar despachando sobre una ruta que ya no refleja las
  // ubicaciones reales, sin ninguna señal de que algo quedó desactualizado.
  const [staleRouteWarning, setStaleRouteWarning] = useState(false);
  useEffect(() => setStaleRouteWarning(false), [solution.instancia_id]);

  // contacts[i] corresponde a clientIndex (i+1) — mismo orden en que
  // InstanceForm arma coordinates/demands al construir el InstanceRequest.
  const contactFor = (clientIndex: number) => localContacts?.[clientIndex - 1];
  const [departureTime, setDepartureTime] = useState("09:00");
  const [serviceMinutes, setServiceMinutes] = useState(8);
  const [etas, setEtas] = useState<RouteEta[] | null>(null);
  const [loadingEtas, setLoadingEtas] = useState(false);

  useEffect(() => {
    if (!instance) {
      setEtas(null);
      return;
    }
    let cancelled = false;
    setLoadingEtas(true);

    const idToCoord = new Map<number, [number, number]>();
    idToCoord.set(0, instance.depot_coordinates);
    instance.coordinates.forEach((c, i) => idToCoord.set(i + 1, c));

    Promise.all(
      solution.routes.map(async (route) => {
        const waypointCoords: [number, number][] = [
          instance.depot_coordinates,
          ...route.sequence.map((id) => idToCoord.get(id) ?? instance.depot_coordinates),
          instance.depot_coordinates,
        ];
        const { coordinates, durationSeconds } = await fetchRouteWithDuration(waypointCoords);
        return { route, geometry: coordinates, waypointCoords, durationSeconds };
      })
    ).then((inputs) => {
      if (cancelled) return;
      setEtas(estimateRouteEtas(inputs, departureTime, serviceMinutes));
      setLoadingEtas(false);
    });

    return () => {
      cancelled = true;
    };
    // Se recalcula puramente en el cliente al cambiar hora/servicio, sin volver a /solve.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [solution, instance, departureTime, serviceMinutes]);

  const etaFor = (vehicleId: number) => etas?.find((e) => e.vehicle_id === vehicleId);

  const [exportingPdf, setExportingPdf] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  // --- Asignación de repartidores por vehículo ---
  const [repartidores, setRepartidores] = useState<TeamMember[]>([]);
  const [assignments, setAssignments] = useState<Record<number, string>>({});
  // vehicle_id que este operario desasignó explícitamente en esta sesión de
  // edición — "ausente en `assignments`" es ambiguo (puede significar "nunca
  // lo toqué" o "lo borré a propósito"), y el merge con la copia fresca del
  // servidor necesita distinguir ambos casos para no resucitar una
  // asignación que el usuario acaba de sacar.
  const [explicitlyUnassigned, setExplicitlyUnassigned] = useState<Set<number>>(new Set());
  // Mientras es true, el selector se deshabilita en vez de mostrar "Sin
  // asignar" — sin esto, limpiar `assignments` sincrónicamente al cambiar
  // de instancia (necesario para cerrar el TOCTOU de más abajo) hacía que
  // el dropdown mostrara "Sin asignar" por un instante aunque SÍ hubiera
  // una asignación real guardada, hasta que resolvía el GET.
  const [assignmentsLoading, setAssignmentsLoading] = useState(false);
  const [savingAssignments, setSavingAssignments] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);
  const [assignSaved, setAssignSaved] = useState(false);

  useEffect(() => {
    api
      .listTeam()
      .then((members) => setRepartidores(members.filter((m) => m.role === "repartidor" && m.active)))
      .catch(() => {});
    // Se limpia sincrónicamente ANTES del fetch — sin esto, `assignments`
    // seguía mostrando el mapa de la instancia VIEJA hasta que resolvía el
    // GET de abajo; guardar en esa ventana breve mergeaba assignments de la
    // instancia anterior sobre la nueva si compartían algún vehicle_id.
    // `assignmentsLoading` evita que ese vacío se vea como "Sin asignar".
    setAssignments({});
    setAssignmentsLoading(true);
    setAssignError(null);
    // Hidrata el selector con lo ya guardado — sin esto, recargar la página
    // o volver a una instancia ya asignada mostraba siempre "Sin asignar"
    // aunque el repartidor ya viera la ruta correctamente en "Mi ruta". Un
    // fallo acá (mala conexión) antes se tragaba en silencio — el select se
    // veía "Sin asignar" indistinguible de que genuinamente no hay
    // repartidor, y encima dejaba a `handleSaveAssignments` en riesgo de
    // pisar asignaciones reales (ver comentario ahí). Ahora se avisa.
    api
      .getAssignments(solution.instancia_id)
      .then(setAssignments)
      .catch((err) => setAssignError(`No se pudieron cargar las asignaciones guardadas: ${(err as Error).message}`))
      .finally(() => setAssignmentsLoading(false));
    // Sin esto, una desasignación sin guardar en la instancia ANTERIOR
    // (ej. resolver una reprogramada sin haber guardado assignments todavía)
    // sobrevivía al cambio de instancia — SolutionSummary no se remonta al
    // cambiar `solution` (sin `key` en App.tsx), y el próximo guardado en la
    // instancia NUEVA borraba un vehicle_id que el usuario nunca tocó ahí.
    setExplicitlyUnassigned(new Set());
    // Dependencia en `solution` completo, no solo `instancia_id`: el
    // backend invalida route_assignments en CUALQUIER re-solve exitoso
    // (mismo id o no, ver _solve_and_persist), así que resolver la misma
    // instancia otra vez desde el formulario principal (flujo de
    // "sobreescribir", sin pasar por reprogramar ni "Resolver de nuevo")
    // también debe refrescar — `solution` siempre es un objeto nuevo en
    // cada resolve exitoso (App.tsx nunca reutiliza la referencia vieja).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [solution]);

  // --- Estado de entrega ya guardado (para no arrancar siempre en "pendiente") ---
  const [deliveryStatuses, setDeliveryStatuses] = useState<Record<number, { status: string; note?: string }>>({});
  // Mientras es true, DeliveryStatusControl se deshabilita en vez de asumir
  // "pendiente" — sin esto, vaciar `deliveryStatuses` sincrónicamente (fix
  // de abajo) hacía que un cliente ya "entregado"/"rechazado" se viera
  // momentáneamente como "Pendiente", un valor de negocio falso (peor que
  // el flash de "Sin asignar" en assignments: acá contradice un estado
  // terminal ya confirmado, y el control ni siquiera queda deshabilitado
  // durante ese instante, así que un clic ahí operaría sobre datos viejos).
  const [deliveryStatusesLoading, setDeliveryStatusesLoading] = useState(false);
  const [deliveryStatusesError, setDeliveryStatusesError] = useState<string | null>(null);

  useEffect(() => {
    // Mismo TOCTOU que assignments (Ronda 26): clientId es un índice 1..N
    // por instancia, no un id global, así que sin limpiar sincrónicamente
    // acá, el mapa viejo podía quedar mezclado con el de la instancia nueva
    // durante la ventana breve entre cambiar `solution` y que resuelva este
    // fetch — un cliente #1 "entregado" en la instancia vieja se veía
    // heredado en el cliente #1 de la nueva hasta que llegaba la respuesta.
    setDeliveryStatuses({});
    setDeliveryStatusesLoading(true);
    setDeliveryStatusesError(null);
    // Antes el fallo se tragaba en silencio — un cliente ya "Entregado" se
    // podía ver como "Pendiente" por una falla de red no reportada, sin que
    // el dueño/operario supiera que el dato mostrado no era el real.
    api
      .getDeliveryStatuses(solution.instancia_id)
      .then(setDeliveryStatuses)
      .catch((err) => setDeliveryStatusesError(`No se pudieron cargar los estados de entrega guardados: ${(err as Error).message}`))
      .finally(() => setDeliveryStatusesLoading(false));
  }, [solution.instancia_id]);

  const handleAssignmentChange = (vehicleId: number, repartidorUserId: string) => {
    setAssignments((prev) => {
      const next = { ...prev };
      if (repartidorUserId) next[vehicleId] = repartidorUserId;
      else delete next[vehicleId];
      return next;
    });
    setExplicitlyUnassigned((prev) => {
      const next = new Set(prev);
      if (repartidorUserId) next.delete(vehicleId);
      else next.add(vehicleId);
      return next;
    });
  };

  const handleSaveAssignments = async () => {
    setAssignError(null);
    setSavingAssignments(true);
    try {
      // PUT /assignments reemplaza el mapa COMPLETO — `assignments` acá es
      // el estado local cargado al montar, que puede estar desactualizado
      // si otro operario guardó una asignación distinta mientras esta
      // pantalla estaba abierta. Se refresca justo antes de guardar y se
      // aplican los cambios locales (los vehicle_id que este operario tocó)
      // sobre esa base fresca, en vez de pisar todo con la copia vieja.
      //
      // El spread por sí solo no puede expresar "borrar" — un vehicle_id
      // ausente en `assignments` es ambiguo (¿nunca lo toqué, o lo
      // desasigné a propósito?), así que `explicitlyUnassigned` se aplica
      // DESPUÉS del merge para eliminar esas claves de la base fresca,
      // sin importar si `latest` las trae de vuelta desde el servidor.
      // Bug real: el fallback silencioso a `assignments` (el estado LOCAL) si
      // este GET fallaba significaba que, si TAMBIÉN el fetch original de
      // montaje (línea ~137) había fallado en silencio con mala conexión,
      // `assignments` local podía estar vacío — y el PUT de abajo reemplaza
      // el mapa COMPLETO en el backend, borrando asignaciones reales ya
      // guardadas sin ningún aviso (el botón igual mostraba "✓ Guardado").
      // Ahora un fallo acá aborta el guardado con error visible, en vez de
      // arriesgarse a persistir una base que puede estar incompleta.
      const latest = await api.getAssignments(solution.instancia_id);
      const merged = { ...latest, ...assignments };
      for (const vehicleId of explicitlyUnassigned) delete merged[vehicleId];
      await api.setAssignments(solution.instancia_id, merged);
      setAssignments(merged);
      setExplicitlyUnassigned(new Set());
      setAssignSaved(true);
      setTimeout(() => setAssignSaved(false), 2000);
    } catch (err) {
      setAssignError((err as Error).message);
    } finally {
      setSavingAssignments(false);
    }
  };

  // --- Reprogramar pedidos no entregados ---
  const [rescheduling, setRescheduling] = useState(false);
  const [rescheduleError, setRescheduleError] = useState<string | null>(null);
  const [rescheduleResult, setRescheduleResult] = useState<string | null>(null);
  // Id de la instancia recién creada por reprogramar, pendiente de resolver
  // — antes no había forma de resolverla desde acá: /solve solo aceptaba
  // coordenadas/flota armadas a mano en el body, así que el operario tenía
  // que retipear a mano los clientes reprogramados (inviable con volumen).
  const [rescheduledPendingSolveId, setRescheduledPendingSolveId] = useState<string | null>(null);
  const [solvingRescheduled, setSolvingRescheduled] = useState(false);

  const handleReschedule = async () => {
    setRescheduleError(null);
    setRescheduleResult(null);
    setRescheduledPendingSolveId(null);
    setRescheduling(true);
    try {
      const result = await api.rescheduleInstance(solution.instancia_id);
      setRescheduleResult(
        `Se creó la instancia "${result.new_instancia_id}" con ${result.rescheduled_client_ids.length} pedido(s) pendiente(s).`
      );
      setRescheduledPendingSolveId(result.new_instancia_id);
      // Bug real: reschedule marca delivery_status="reprogramado" en el
      // backend para los clientes movidos, pero sin recargar `deliveryStatuses`
      // acá, el panel seguía mostrando esas paradas como si siguieran activas
      // (sin el aviso visual de "ya no forma parte de esta ruta") hasta que
      // el usuario recargaba la página a mano.
      api.getDeliveryStatuses(solution.instancia_id).then(setDeliveryStatuses).catch(() => {});
    } catch (err) {
      setRescheduleError((err as Error).message);
    } finally {
      setRescheduling(false);
    }
  };

  const handleSolveRescheduled = async () => {
    if (!rescheduledPendingSolveId) return;
    setRescheduleError(null);
    setSolvingRescheduled(true);
    try {
      const solved = await api.solveExistingInstance(rescheduledPendingSolveId);
      setRescheduleResult(
        `Instancia "${solved.instancia_id}" resuelta: ${solved.num_routes} ruta(s), costo ${solved.total_cost.toFixed(1)}. Ya podés asignarle un repartidor abajo.`
      );
      setRescheduledPendingSolveId(null);
      onSolvedInstanceChange?.(solved);
    } catch (err) {
      setRescheduleError((err as Error).message);
    } finally {
      setSolvingRescheduled(false);
    }
  };

  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleDeleteInstance = async () => {
    setDeleteError(null);
    setDeleting(true);
    try {
      await api.deleteInstance(solution.instancia_id);
      setConfirmingDelete(false);
      onInstanceDeleted?.();
    } catch (err) {
      setDeleteError((err as Error).message);
    } finally {
      setDeleting(false);
    }
  };

  const handleExportPdf = async () => {
    setExportError(null);
    setExportingPdf(true);
    try {
      const blob = await api.exportSolutionPdf(solution.instancia_id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `ruta_${solution.instancia_id}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError((err as Error).message);
    } finally {
      setExportingPdf(false);
    }
  };

  const handleResolveStaleRoute = async () => {
    setSolvingRescheduled(true);
    try {
      const solved = await api.solveExistingInstance(solution.instancia_id);
      setStaleRouteWarning(false);
      // El backend invalida route_assignments en cada re-solve (el mapeo
      // vehicle_id→clientes puede recomponerse completamente), pero acá
      // `solved.instancia_id` es el MISMO que antes — a diferencia de
      // resolver una reprogramada, el useEffect de [solution.instancia_id]
      // no vuelve a correr, así que `assignments` quedaba mostrando el
      // mapeo viejo (ya borrado en el servidor) sin ningún aviso.
      setAssignments({});
      setExplicitlyUnassigned(new Set());
      onSolvedInstanceChange?.(solved);
    } catch (err) {
      setRescheduleError((err as Error).message);
    } finally {
      setSolvingRescheduled(false);
    }
  };

  return (
    <div className="solution-summary">
      <h2 className="section-title">Solución</h2>
      {staleRouteWarning && (
        <p className="error-message" role="alert">
          Corregiste la coordenada de un cliente — la ruta, distancia y horarios que ves abajo son los de ANTES del
          cambio.{" "}
          <button type="button" className="btn-tertiary" onClick={handleResolveStaleRoute} disabled={solvingRescheduled}>
            {solvingRescheduled ? "Resolviendo…" : "Resolver de nuevo"}
          </button>
        </p>
      )}
      <div className="summary-stats">
        <div className="stat">
          <span className="stat-value">{formatDistanceKm(solution.total_cost)}</span>
          <span className="stat-label">Distancia total</span>
        </div>
        <div className="stat">
          <span className="stat-value">{countFormatter.format(solution.num_routes)}</span>
          <span className="stat-label">Rutas</span>
        </div>
      </div>

      <div className="export-actions">
        {/* Bug real (Ronda 49, ampliado en Ronda 50): exportar CSV/PDF cuando
            TODAS las paradas de un vehículo fueron reprogramadas generaba una
            página/sección vacía (solo encabezados) sin ningún aviso previo —
            un operario que no revisa el contenido podía pensar que el export
            falló o quedó corrupto. El fix original solo cubría el caso
            extremo de la INSTANCIA COMPLETA vacía; con varios vehículos y
            solo ALGUNOS totalmente reprogramados (el resto con trabajo real
            mixto), la condición `every` sobre toda la solución nunca se
            cumplía y el aviso no aparecía para esos vehículos específicos. */}
        {(() => {
          const emptyVehicleNumbers = solution.routes
            .filter((route) => route.sequence.length > 0 && route.sequence.every((ci) => deliveryStatuses[ci]?.status === "reprogramado"))
            .map((route) => route.vehicle_id + 1);
          if (emptyVehicleNumbers.length === 0) return null;
          const allEmpty = emptyVehicleNumbers.length === solution.routes.length;
          return (
            <p className="route-reprogramado-warning">
              {allEmpty
                ? "Todas las paradas fueron reprogramadas — el archivo exportado no va a tener filas de reparto."
                : `El vehículo ${emptyVehicleNumbers.join(", ")} tiene todas sus paradas reprogramadas — su sección del archivo exportado va a salir sin filas de reparto.`}
            </p>
          );
        })()}
        {/* localContacts, no la prop `contacts` (snapshot original) — sin esto, editar
            nombre/teléfono/dirección de un cliente con ClientEditControl (que sí
            actualiza localContacts, ver onSaved más abajo) exportaba igual el dato
            VIEJO en el CSV, justo el caso de uso para el que existe ese control. */}
        <button
          type="button"
          className="btn-secondary"
          onClick={() => {
            const rescheduledClientIndexes = new Set(
              Object.entries(deliveryStatuses)
                .filter(([, v]) => v.status === "reprogramado")
                .map(([clientIndex]) => Number(clientIndex))
            );
            downloadRouteCsv(solution, localContacts, rescheduledClientIndexes);
          }}
        >
          Exportar CSV
        </button>
        <button type="button" className="btn-secondary" onClick={handleExportPdf} disabled={exportingPdf}>
          {exportingPdf ? "Generando PDF…" : "Exportar PDF"}
        </button>
        <button type="button" className="btn-tertiary" onClick={() => setConfirmingDelete(true)} disabled={deleting}>
          {deleting ? "Eliminando…" : "Eliminar instancia"}
        </button>
      </div>
      {deleteError && (
        <p className="error-message" role="alert">
          {deleteError}
        </p>
      )}

      <ConfirmDialog
        open={confirmingDelete}
        title="Eliminar instancia"
        message={`¿Seguro que querés eliminar la instancia "${solution.instancia_id}"? Se borran también sus clientes, asignaciones y estados de entrega. Esta acción no se puede deshacer.`}
        onCancel={() => setConfirmingDelete(false)}
        onConfirm={handleDeleteInstance}
      />
      {exportError && (
        <p className="error-message" role="alert">
          {exportError}
        </p>
      )}

      <div className="reschedule-actions">
        <button type="button" className="btn-secondary" onClick={handleReschedule} disabled={rescheduling}>
          {rescheduling ? "Reprogramando…" : "Reprogramar pedidos no entregados"}
        </button>
        {rescheduleResult && <p className="import-status" role="status">{rescheduleResult}</p>}
        {rescheduledPendingSolveId && (
          <button type="button" className="btn-secondary" onClick={handleSolveRescheduled} disabled={solvingRescheduled}>
            {solvingRescheduled ? "Resolviendo…" : `Resolver "${rescheduledPendingSolveId}" ahora`}
          </button>
        )}
        {rescheduleError && (
          <p className="error-message" role="alert">
            {rescheduleError}
          </p>
        )}
      </div>

      <div className="eta-controls">
        <div className="field-group">
          <label htmlFor="departure-time">Hora de salida</label>
          <input
            id="departure-time"
            type="time"
            value={departureTime}
            onChange={(e) => setDepartureTime(e.target.value)}
          />
        </div>
        <div className="field-group">
          <label htmlFor="service-minutes">Minutos por parada</label>
          <input
            id="service-minutes"
            type="number"
            min="0"
            step="1"
            value={serviceMinutes}
            onChange={(e) => setServiceMinutes(Math.max(0, Number(e.target.value)))}
          />
        </div>
      </div>
      <p className="eta-disclaimer">
        Horario aproximado, no exacto — asume velocidad constante y {serviceMinutes} min por parada. Usalo como
        referencia para avisarle al cliente un rango, no una hora exacta.
      </p>

      <ul className="route-list">
        {solution.routes.map((route, i) => {
          const eta = etaFor(route.vehicle_id);
          // Bug real (Ronda 48): el aviso de la Ronda 47 solo marca la parada
          // individual — la fila del VEHÍCULO (costo, selector de repartidor)
          // se veía idéntica a una ruta activa aunque todas sus paradas hayan
          // sido reprogramadas, sin ninguna señal de que ese trabajo ya no
          // existe. El costo tampoco se recalcula (solo "Resolver de nuevo"
          // lo hace), así que sigue siendo el de la ruta original completa.
          const allStopsRescheduled =
            route.sequence.length > 0 && route.sequence.every((ci) => deliveryStatuses[ci]?.status === "reprogramado");
          return (
            <li key={route.vehicle_id} className="route-item">
              <span className="route-swatch" style={{ background: ROUTE_COLORS[i % ROUTE_COLORS.length] }} />
              <span className="route-label">Vehículo {route.vehicle_id + 1}</span>
              <span className="route-cost">{formatDistanceKm(route.cost)}</span>
              {allStopsRescheduled && (
                <p className="route-reprogramado-warning">
                  Todos los pedidos de esta ruta fueron reprogramados — ya no hace falta asignarle repartidor
                </p>
              )}
              <label className="route-assign">
                Repartidor
                <select
                  aria-label={`Repartidor asignado al vehículo ${route.vehicle_id + 1}`}
                  value={assignmentsLoading ? "" : assignments[route.vehicle_id] ?? ""}
                  onChange={(e) => handleAssignmentChange(route.vehicle_id, e.target.value)}
                  disabled={assignmentsLoading}
                >
                  <option value="">Sin asignar</option>
                  {repartidores.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.full_name || r.email}
                    </option>
                  ))}
                </select>
              </label>
              <ol className="route-stops">
                {route.sequence.map((clientIndex, si) => {
                  const contact = contactFor(clientIndex);
                  const stopEta = eta?.stops[si];
                  // Bug real (Ronda 47, operario): reschedule_instance mueve el
                  // cliente a una instancia nueva y marca delivery_status como
                  // "reprogramado" en la ORIGINAL, pero route.sequence de la
                  // solución ya calculada sigue listándolo como parada activa
                  // — sin ninguna marca visual, se veía igual que cualquier
                  // otra parada (ETA en verde, selector de repartidor
                  // operable), sin ninguna pista de que ya no pertenece a esta
                  // ruta/instancia.
                  const isRescheduled = deliveryStatuses[clientIndex]?.status === "reprogramado";
                  return (
                    <li key={si} className={isRescheduled ? "route-stop route-stop--reprogramado" : "route-stop"}>
                      {isRescheduled && (
                        <p className="route-stop-reprogramado-warning">Reprogramado a otra instancia — ya no forma parte de esta ruta</p>
                      )}
                      <span className="route-stop-name">{contact?.customerName?.trim() || `Cliente #${clientIndex}`}</span>
                      {contact?.customerPhone && <span className="route-stop-phone">{contact.customerPhone}</span>}
                      {contact?.address && <span className="route-stop-address">{contact.address}</span>}
                      {stopEta && (
                        <span className="route-stop-eta">
                          {stopEta.arrivalEarliest}–{stopEta.arrivalLatest}
                        </span>
                      )}
                      <DeliveryStatusControl
                        // key fuerza remount cuando llega el fetch de estados
                        // ya guardados (initialStatus/initialNote solo se leen
                        // una vez, en useState) — sin esto, un estado marcado
                        // antes de este render (ej. por el repartidor) seguía
                        // mostrando "Pendiente" hasta la próxima interacción.
                        key={deliveryStatuses[clientIndex]?.status ?? "pendiente"}
                        instanciaId={solution.instancia_id}
                        clientId={clientIndex}
                        customerName={contact?.customerName}
                        initialStatus={(deliveryStatuses[clientIndex]?.status as DeliveryStatus) ?? "pendiente"}
                        initialNote={deliveryStatuses[clientIndex]?.note}
                        disabled={deliveryStatusesLoading}
                      />
                      <ClientEditControl
                        instanciaId={solution.instancia_id}
                        clientId={clientIndex}
                        contact={contact}
                        onSaved={(updated) => {
                          // Sin `contact` previo (ej. cliente de una instancia
                          // reprogramada, donde `contacts` queda en null) no
                          // hay con qué comparar — se asume que la coordenada
                          // SÍ cambió en vez de asumir lo contrario, porque el
                          // costo de un aviso de más es mucho menor que el de
                          // una ruta desactualizada sin ninguna señal.
                          const coordChanged =
                            contact === undefined ||
                            Number(contact.x) !== updated.x ||
                            Number(contact.y) !== updated.y;
                          if (coordChanged) setStaleRouteWarning(true);
                          setLocalContacts((prev) => {
                            const next = prev ? [...prev] : [];
                            const existing = next[clientIndex - 1];
                            next[clientIndex - 1] = {
                              clientId: existing?.clientId ?? String(clientIndex),
                              x: String(updated.x),
                              y: String(updated.y),
                              packages: existing?.packages ?? [],
                              inCoverage: existing?.inCoverage ?? true,
                              customerName: updated.customerName,
                              customerPhone: updated.customerPhone,
                              address: updated.address,
                            };
                            return next;
                          });
                        }}
                      />
                    </li>
                  );
                })}
              </ol>
              {loadingEtas && !eta && <span className="route-eta route-eta--loading">Calculando horarios…</span>}
            </li>
          );
        })}
      </ul>

      <div className="assign-actions">
        <button type="button" className="btn-secondary" onClick={handleSaveAssignments} disabled={savingAssignments}>
          {savingAssignments ? "Guardando…" : "Guardar asignaciones de repartidor"}
        </button>
        {assignSaved && <span className="stop-save-indicator stop-save-indicator--saved">✓ Guardado</span>}
        {assignError && (
          <p className="error-message" role="alert">
            {assignError}
          </p>
        )}
      </div>
    </div>
  );
}
