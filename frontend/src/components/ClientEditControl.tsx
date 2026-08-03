import { useState } from "react";
import type { ClientGroup } from "../lib/types";
import { api } from "../lib/api";

interface Props {
  instanciaId: string;
  clientId: number;
  contact?: ClientGroup;
  onSaved: (updated: { x: number; y: number; customerName?: string; customerPhone?: string; address?: string }) => void;
}

// Corrige nombre/teléfono/dirección/coordenadas de un cliente ya cargado —
// antes la única forma de arreglar un error de tipeo (ej. en el CSV
// importado) era re-resolver la instancia entera desde cero vía el flujo de
// "sobreescribir", perdiendo los estados de entrega ya marcados ese día.
export function ClientEditControl({ instanciaId, clientId, contact, onSaved }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [x, setX] = useState(contact?.x ?? "");
  const [y, setY] = useState(contact?.y ?? "");
  const [customerName, setCustomerName] = useState(contact?.customerName ?? "");
  const [customerPhone, setCustomerPhone] = useState(contact?.customerPhone ?? "");
  const [address, setAddress] = useState(contact?.address ?? "");
  // Bug real (Ronda 5, ciclo nuevo, dueño): sin esto, dos ediciones desde
  // snapshots distintos (dos pestañas, dos usuarios) se pisaban en silencio
  // — customer_name/phone/address siempre viajan en el payload de guardado
  // (nunca se omiten), así que el backend no tenía forma de detectar que el
  // snapshot local ya estaba obsoleto. Se refresca desde el backend recién
  // al abrir el formulario (no se confía en `contact`, que puede venir de
  // localStorage con un snapshot viejo) y se manda de vuelta al guardar.
  const [updatedAt, setUpdatedAt] = useState<string | undefined>(undefined);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <button
        type="button"
        className="btn-tertiary"
        disabled={loading}
        onClick={async () => {
          setLoading(true);
          setError(null);
          try {
            const fresh = await api.getClient(instanciaId, clientId);
            setX(String(fresh.x));
            setY(String(fresh.y));
            setCustomerName(fresh.customer_name ?? "");
            setCustomerPhone(fresh.customer_phone ?? "");
            setAddress(fresh.address ?? "");
            setUpdatedAt(fresh.updated_at);
            setOpen(true);
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setLoading(false);
          }
        }}
      >
        {loading ? "Cargando…" : "Editar"}
      </button>
    );
  }

  const handleSave = async () => {
    const parsedX = Number(x);
    const parsedY = Number(y);
    if (Number.isNaN(parsedX) || Number.isNaN(parsedY)) {
      setError("Coordenadas inválidas");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await api.updateClient(instanciaId, clientId, {
        x: parsedX,
        y: parsedY,
        // demand se omite: solo se edita contacto/ubicación acá, el backend
        // preserva la demanda ya persistida si no se manda explícitamente.
        //
        // null (no undefined) cuando el campo quedó vacío: el backend
        // distingue "no mandaste este campo" (preservar lo persistido) de
        // "lo mandaste vacío a propósito" (borrarlo) — con undefined, JSON
        // omite la clave y "borrar el teléfono" terminaba sin efecto.
        customer_name: customerName.trim() || null,
        customer_phone: customerPhone.trim() || null,
        address: address.trim() || null,
        updated_at: updatedAt ?? null,
      });
      onSaved({
        x: parsedX,
        y: parsedY,
        customerName: customerName.trim() || undefined,
        customerPhone: customerPhone.trim() || undefined,
        address: address.trim() || undefined,
      });
      setOpen(false);
    } catch (err) {
      const message = (err as Error).message;
      setError(
        message.includes("editado por otra persona")
          ? "Este cliente fue editado por otra persona mientras tanto — cerrá y volvé a abrir Editar para ver los datos actuales."
          : message
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="client-edit-control">
      <label>
        Nombre
        <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} />
      </label>
      <label>
        Teléfono
        <input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} />
      </label>
      <label>
        Dirección
        <input value={address} onChange={(e) => setAddress(e.target.value)} />
      </label>
      <div className="field-row">
        <label>
          X
          <input value={x} onChange={(e) => setX(e.target.value)} />
        </label>
        <label>
          Y
          <input value={y} onChange={(e) => setY(e.target.value)} />
        </label>
      </div>
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      <div className="client-edit-actions">
        <button type="button" className="btn-secondary" onClick={() => setOpen(false)} disabled={saving}>
          Cancelar
        </button>
        <button type="button" className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? "Guardando…" : "Guardar"}
        </button>
      </div>
    </div>
  );
}
