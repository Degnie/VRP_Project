interface Props {
  editing: boolean;
  hasZone: boolean;
  pointCount: number;
  onStart: () => void;
  onClose: () => void;
  onRedraw: () => void;
}

export function CoverageZoneEditor({ editing, hasZone, pointCount, onStart, onClose, onRedraw }: Props) {
  if (editing) {
    return (
      <div className="coverage-editor">
        <p className="coverage-editor-hint">
          Hacé click en el mapa para agregar vértices ({pointCount} agregados). Necesitás al menos 3 para cerrar el polígono.
        </p>
        <button type="button" className="btn-secondary" onClick={onClose} disabled={pointCount < 3}>
          Cerrar polígono
        </button>
      </div>
    );
  }

  return (
    <div className="coverage-editor">
      <button type="button" className="btn-secondary" onClick={onStart}>
        {hasZone ? "Redibujar zona de cobertura" : "Dibujar zona de cobertura"}
      </button>
      {hasZone && (
        <button type="button" className="btn-secondary" onClick={onRedraw}>
          Borrar zona
        </button>
      )}
    </div>
  );
}
