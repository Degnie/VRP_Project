import { useEffect, useState } from "react";
import type { ClientGroup, InstanceRequest, RouteEta, SolutionResponse } from "../lib/types";
import { fetchRouteWithDuration } from "../lib/osrm";
import { estimateRouteEtas } from "../lib/eta";
import { downloadRouteCsv } from "../lib/exportCsv";
import { api } from "../lib/api";
import { DeliveryStatusControl } from "./DeliveryStatusControl";

const ROUTE_COLORS = [
  "#2f6f4f", "#c4622d", "#3a5a9e", "#a3383c", "#7a5c9e", "#2e8b8b", "#b08a1e", "#5c6b73",
];

const costFormatter = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const countFormatter = new Intl.NumberFormat();

interface Props {
  solution: SolutionResponse;
  instance: InstanceRequest | null;
  contacts: ClientGroup[] | null;
}

export function SolutionSummary({ solution, instance, contacts }: Props) {
  // contacts[i] corresponde a clientIndex (i+1) — mismo orden en que
  // InstanceForm arma coordinates/demands al construir el InstanceRequest.
  const contactFor = (clientIndex: number) => contacts?.[clientIndex - 1];
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

  return (
    <div className="solution-summary">
      <h2 className="section-title">Solución</h2>
      <div className="summary-stats">
        <div className="stat">
          <span className="stat-value">{costFormatter.format(solution.total_cost)}</span>
          <span className="stat-label">Costo total</span>
        </div>
        <div className="stat">
          <span className="stat-value">{countFormatter.format(solution.num_routes)}</span>
          <span className="stat-label">Rutas</span>
        </div>
      </div>

      <div className="export-actions">
        <button type="button" className="btn-secondary" onClick={() => downloadRouteCsv(solution, contacts)}>
          Exportar CSV
        </button>
        <button type="button" className="btn-secondary" onClick={handleExportPdf} disabled={exportingPdf}>
          {exportingPdf ? "Generando PDF…" : "Exportar PDF"}
        </button>
      </div>
      {exportError && (
        <p className="error-message" role="alert">
          {exportError}
        </p>
      )}

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
          return (
            <li key={route.vehicle_id} className="route-item">
              <span className="route-swatch" style={{ background: ROUTE_COLORS[i % ROUTE_COLORS.length] }} />
              <span className="route-label">Vehículo {route.vehicle_id}</span>
              <span className="route-cost">{costFormatter.format(route.cost)}</span>
              <ol className="route-stops">
                {route.sequence.map((clientIndex, si) => {
                  const contact = contactFor(clientIndex);
                  const stopEta = eta?.stops[si];
                  return (
                    <li key={si} className="route-stop">
                      <span className="route-stop-name">{contact?.customerName || `Cliente #${clientIndex}`}</span>
                      {contact?.customerPhone && <span className="route-stop-phone">{contact.customerPhone}</span>}
                      {contact?.address && <span className="route-stop-address">{contact.address}</span>}
                      {stopEta && (
                        <span className="route-stop-eta">
                          {stopEta.arrivalEarliest}–{stopEta.arrivalLatest}
                        </span>
                      )}
                      <DeliveryStatusControl instanciaId={solution.instancia_id} clientId={clientIndex} />
                    </li>
                  );
                })}
              </ol>
              {loadingEtas && !eta && <span className="route-eta route-eta--loading">Calculando horarios…</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
