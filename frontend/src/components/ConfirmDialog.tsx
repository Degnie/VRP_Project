import { useEffect } from "react";
import type { ReactNode } from "react";

interface Props {
  open: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  children?: ReactNode;
}

export function ConfirmDialog({ open, title, message, onConfirm, onCancel, children }: Props) {
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    // Bug real (Ronda 1, ciclo nuevo): el overlay cerraba el diálogo (=
    // Cancelar, sin aplicar el cambio) con un solo tap fuera de la caja. En
    // mobile (repartidor en la calle, con una mano ocupada) un toque que no
    // acierta el textarea o el botón "Confirmar" cae fuera de la caja y
    // descarta la nota recién escrita en silencio, sin ningún aviso — se
    // requiere Cancelar/Confirmar explícito o Escape.
    <div className="confirm-dialog-overlay">
      <div
        className="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
      >
        <h3 id="confirm-dialog-title">{title}</h3>
        <p>{message}</p>
        {children}
        <div className="confirm-dialog-actions">
          <button type="button" className="btn-secondary" onClick={onCancel}>
            Cancelar
          </button>
          <button type="button" className="btn-primary" onClick={onConfirm}>
            Confirmar
          </button>
        </div>
      </div>
    </div>
  );
}
