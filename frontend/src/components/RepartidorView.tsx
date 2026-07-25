import { useEffect, useState } from "react";
import type { DeliveryStatus, InstanceSummary, MyRouteResponse } from "../lib/types";
import { api } from "../lib/api";

const STATUS_LABELS: Record<DeliveryStatus, string> = {
  pendiente: "Pendiente",
  entregado: "Entregado",
  no_encontrado: "No encontrado",
  reprogramado: "Reprogramado",
};

interface Props {
  onLogout: () => void;
}

export function RepartidorView({ onLogout }: Props) {
  const [instances, setInstances] = useState<InstanceSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [route, setRoute] = useState<MyRouteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savingStopId, setSavingStopId] = useState<number | null>(null);

  useEffect(() => {
    api.listInstances().then(setInstances).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setRoute(null);
      return;
    }
    setLoading(true);
    setError(null);
    api
      .getMyRoute(selectedId)
      .then(setRoute)
      .catch((err) => {
        setRoute(null);
        setError((err as Error).message.includes("404") ? "No tenés una ruta asignada en esta instancia." : (err as Error).message);
      })
      .finally(() => setLoading(false));
  }, [selectedId]);

  const handleStatusChange = async (clientId: number, status: DeliveryStatus) => {
    if (!route) return;
    setSavingStopId(clientId);
    try {
      await api.updateDeliveryStatus(route.instancia_id, clientId, status);
      setRoute({
        ...route,
        stops: route.stops.map((s) => (s.client_id === clientId ? { ...s, delivery_status: status } : s)),
      });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSavingStopId(null);
    }
  };

  const handleExportPdf = async () => {
    if (!route) return;
    try {
      const blob = await api.exportSolutionPdf(route.instancia_id, route.vehicle_id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `mi_ruta_${route.instancia_id}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="repartidor-shell">
      <header className="repartidor-header">
        <h1>Mi ruta</h1>
        <button type="button" className="btn-reset" onClick={onLogout}>
          Cerrar sesión
        </button>
      </header>

      <div className="repartidor-body">
        <div className="field-group">
          <label htmlFor="instance-select">Instancia</label>
          <select id="instance-select" value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
            <option value="">Elegí una instancia…</option>
            {instances.map((i) => (
              <option key={i.id} value={i.id}>
                {i.id}
              </option>
            ))}
          </select>
        </div>

        {loading && <p className="import-status">Cargando ruta…</p>}
        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}

        {route && (
          <>
            <button type="button" className="btn-secondary repartidor-export" onClick={handleExportPdf}>
              Exportar mi hoja en PDF
            </button>

            <ol className="repartidor-stops">
              {route.stops.map((stop) => (
                <li key={stop.client_id} className="repartidor-stop">
                  <div className="repartidor-stop-header">
                    <span className="repartidor-stop-sequence">{stop.sequence}</span>
                    <span className="repartidor-stop-name">{stop.customer_name || `Cliente #${stop.client_id}`}</span>
                  </div>
                  {stop.customer_phone && (
                    <a className="repartidor-stop-link" href={`tel:${stop.customer_phone}`}>
                      📞 {stop.customer_phone}
                    </a>
                  )}
                  {stop.address && (
                    <a
                      className="repartidor-stop-link"
                      href={`geo:0,0?q=${encodeURIComponent(stop.address)}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      📍 {stop.address}
                    </a>
                  )}
                  <div className="repartidor-stop-actions">
                    {(Object.keys(STATUS_LABELS) as DeliveryStatus[]).map((status) => (
                      <button
                        key={status}
                        type="button"
                        className={
                          stop.delivery_status === status
                            ? "repartidor-status-btn repartidor-status-btn--active"
                            : "repartidor-status-btn"
                        }
                        disabled={savingStopId === stop.client_id}
                        onClick={() => handleStatusChange(stop.client_id, status)}
                      >
                        {STATUS_LABELS[status]}
                      </button>
                    ))}
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
      </div>
    </div>
  );
}
