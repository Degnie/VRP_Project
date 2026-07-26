import { useState } from "react";
import type { DeliveryStatus } from "../lib/types";
import { api } from "../lib/api";
import { ConfirmDialog } from "./ConfirmDialog";

const STATUS_LABELS: Record<DeliveryStatus, string> = {
  pendiente: "Pendiente",
  entregado: "Entregado",
  no_encontrado: "No encontrado",
  reprogramado: "Reprogramado",
  rechazado: "Rechazado",
};

// "reprogramado" es un estado DERIVADO del flujo POST /instances/{id}/reschedule
// (que sí crea la instancia de destino y setea rescheduled_to_instancia_id) — nunca
// una acción manual. Seleccionarlo acá dejaba al cliente con delivery_status=
// "reprogramado" pero SIN instancia de destino: bloqueado para siempre (409 en
// cualquier edición futura, excluido de get_pending_clients, así que tampoco vuelve
// a ser candidato a una reprogramación real). Se excluye de las opciones manuales.
const MANUALLY_SELECTABLE_STATUSES: DeliveryStatus[] = ["pendiente", "entregado", "no_encontrado", "rechazado"];

// Revertir uno de estos sin querer (clic accidental) pierde el registro de
// una entrega ya confirmada — se pide confirmación antes de salir de acá.
const TERMINAL_STATUSES: DeliveryStatus[] = ["entregado", "no_encontrado", "reprogramado", "rechazado"];

// Estados donde vale la pena dejar contexto por escrito — el motivo de un
// rechazo o de no encontrar al cliente evita tener que llamar/whatsappear
// para preguntar qué pasó.
const NOTE_PROMPT_STATUSES: DeliveryStatus[] = ["no_encontrado", "rechazado"];

interface Props {
  instanciaId: string;
  clientId: number;
  customerName?: string;
  initialStatus?: DeliveryStatus;
  initialNote?: string;
  // Se usa mientras el estado real todavía se está cargando desde el
  // backend (ej. recién se cambió de instancia) — sin esto, el control
  // asumía "pendiente" por defecto y quedaba operable, mostrando (y
  // dejando editar) un valor de negocio falso sobre un estado que en
  // realidad podía ser terminal (entregado/rechazado/etc.).
  disabled?: boolean;
}

export function DeliveryStatusControl({
  instanciaId,
  clientId,
  customerName,
  initialStatus = "pendiente",
  initialNote,
  disabled,
}: Props) {
  const [status, setStatus] = useState<DeliveryStatus>(initialStatus);
  const [note, setNote] = useState<string | undefined>(initialNote);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingStatus, setPendingStatus] = useState<DeliveryStatus | null>(null);
  const [noteDraft, setNoteDraft] = useState("");

  const applyChange = async (next: DeliveryStatus, nextNote?: string) => {
    const previous = status;
    const previousNote = note;
    setStatus(next);
    setError(null);
    setSaving(true);
    try {
      await api.updateDeliveryStatus(instanciaId, clientId, next, nextNote);
      setNote(nextNote);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (err) {
      const message = (err as Error).message;
      // Bug real (Ronda 51): un timeout (o cualquier fallo de RED, no un
      // rechazo del backend) no significa que el PUT no haya llegado a
      // aplicarse — el UPDATE es idempotente y puede haber tardado más que
      // el timeout del cliente en volver, no en ejecutarse. Revertir
      // ciegamente a `previous` en ese caso dejaba la UI mostrando un
      // estado viejo mientras el backend ya tenía el nuevo, sin ningún
      // resync — el repartidor veía "Pendiente" con un error, cuando en
      // realidad ya estaba "Entregado" del lado del servidor. Se reintenta
      // leer el estado real en vez de asumir que no pasó nada.
      const isNetworkIssue = message.includes("tardó demasiado") || message.includes("Sin conexión");
      if (isNetworkIssue) {
        try {
          const real = await api.getDeliveryStatuses(instanciaId);
          const realEntry = real[clientId];
          setStatus((realEntry?.status as DeliveryStatus) ?? previous);
          setNote(realEntry?.note ?? previousNote);
        } catch {
          setStatus(previous);
          setNote(previousNote);
        }
      } else {
        setStatus(previous);
        setNote(previousNote);
      }
      setError(message);
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (next: DeliveryStatus) => {
    if ((TERMINAL_STATUSES.includes(status) && status !== next) || NOTE_PROMPT_STATUSES.includes(next)) {
      // Precarga la nota existente en vez de arrancar en blanco — evita
      // perderla de vista o pisarla sin querer al re-tocar el mismo estado.
      setNoteDraft(note ?? "");
      setPendingStatus(next);
      return;
    }
    applyChange(next);
  };

  return (
    <span className="delivery-status-control">
      <select
        aria-label={`Estado de entrega del cliente #${clientId}`}
        className={`delivery-status-select delivery-status-select--${status}`}
        value={status}
        disabled={saving || disabled}
        onChange={(e) => handleChange(e.target.value as DeliveryStatus)}
      >
        {status === "reprogramado" && (
          <option value="reprogramado" disabled>
            {STATUS_LABELS.reprogramado} (por reprogramación, no editable acá)
          </option>
        )}
        {MANUALLY_SELECTABLE_STATUSES.map((value) => (
          <option key={value} value={value}>
            {STATUS_LABELS[value]}
          </option>
        ))}
      </select>
      {saving && <span className="stop-save-indicator">Guardando…</span>}
      {saved && <span className="stop-save-indicator stop-save-indicator--saved">✓ Guardado</span>}
      {error && <span className="delivery-status-error">{error}</span>}
      {note && <span className="delivery-status-note">📝 {note}</span>}

      <ConfirmDialog
        open={pendingStatus !== null}
        title="Cambiar estado de entrega"
        message={
          pendingStatus
            ? `¿Seguro que querés cambiar el estado de ${customerName?.trim() || `Cliente #${clientId}`} de "${STATUS_LABELS[status]}" a "${STATUS_LABELS[pendingStatus]}"?`
            : ""
        }
        onCancel={() => setPendingStatus(null)}
        onConfirm={() => {
          if (pendingStatus) applyChange(pendingStatus, noteDraft.trim() || undefined);
          setPendingStatus(null);
        }}
      >
        {pendingStatus && NOTE_PROMPT_STATUSES.includes(pendingStatus) && (
          <label className="confirm-dialog-note-field">
            Nota (opcional)
            <textarea
              value={noteDraft}
              onChange={(e) => setNoteDraft(e.target.value)}
              placeholder="Ej: no había nadie, dejé aviso con el vecino"
              rows={2}
            />
          </label>
        )}
      </ConfirmDialog>
    </span>
  );
}
