import { useState } from "react";
import type { DeliveryStatus } from "../lib/types";
import { api } from "../lib/api";

const STATUS_LABELS: Record<DeliveryStatus, string> = {
  pendiente: "Pendiente",
  entregado: "Entregado",
  no_encontrado: "No encontrado",
  reprogramado: "Reprogramado",
};

interface Props {
  instanciaId: string;
  clientId: number;
  initialStatus?: DeliveryStatus;
}

export function DeliveryStatusControl({ instanciaId, clientId, initialStatus = "pendiente" }: Props) {
  const [status, setStatus] = useState<DeliveryStatus>(initialStatus);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = async (next: DeliveryStatus) => {
    const previous = status;
    setStatus(next);
    setError(null);
    setSaving(true);
    try {
      await api.updateDeliveryStatus(instanciaId, clientId, next);
    } catch (err) {
      setStatus(previous);
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <span className="delivery-status-control">
      <select
        aria-label={`Estado de entrega del cliente #${clientId}`}
        className={`delivery-status-select delivery-status-select--${status}`}
        value={status}
        disabled={saving}
        onChange={(e) => handleChange(e.target.value as DeliveryStatus)}
      >
        {Object.entries(STATUS_LABELS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      {error && <span className="delivery-status-error">{error}</span>}
    </span>
  );
}
