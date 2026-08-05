import { useEffect, useState } from "react";
import type { DashboardSummary } from "../lib/types";
import { api } from "../lib/api";

interface Props {
  onClose: () => void;
}

const countFormatter = new Intl.NumberFormat();
// Mismo criterio que SolutionSummary.tsx: distancia_total viaja en metros
// (misma unidad cruda de OSRM/euclídea que el resto de la app), no en km.
const distanceFormatter = new Intl.NumberFormat(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const formatDistanceKm = (meters: number) => `${distanceFormatter.format(meters / 1000)} km`;

function todayIsoDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function DashboardView({ onClose }: Props) {
  const [date, setDate] = useState(() => todayIsoDate());
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .getDashboard(date)
      .then(setSummary)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [date]);

  return (
    <div className="dashboard-view">
      <div className="dashboard-header">
        <h2 className="section-title">Dashboard diario</h2>
        <div className="field-group dashboard-date-field">
          <label htmlFor="dashboard-date">Fecha</label>
          <input id="dashboard-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <button type="button" className="btn-secondary" onClick={onClose}>
          Volver a rutas
        </button>
      </div>

      {loading && <p className="import-status">Cargando…</p>}
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}

      {summary && !loading && (
        <div className="summary-stats dashboard-stats">
          <div className="stat">
            <span className="stat-value">{formatDistanceKm(summary.distancia_total)}</span>
            <span className="stat-label">Distancia recorrida</span>
          </div>
          <div className="stat">
            <span className="stat-value">{countFormatter.format(summary.num_entregas)}</span>
            <span className="stat-label">Entregas realizadas</span>
          </div>
          <div className="stat">
            <span className="stat-value">{countFormatter.format(summary.vehiculos_utilizados)}</span>
            <span className="stat-label">Vehículos utilizados</span>
          </div>
          <div className="stat">
            <span className="stat-value">{countFormatter.format(summary.vehiculos_disponibles)}</span>
            <span className="stat-label">Vehículos disponibles</span>
          </div>
        </div>
      )}
    </div>
  );
}
