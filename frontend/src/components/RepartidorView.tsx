import { useEffect, useRef, useState } from "react";
import type { DeliveryStatus, InstanceSummary, MyRouteResponse } from "../lib/types";
import { api } from "../lib/api";
import { ConfirmDialog } from "./ConfirmDialog";
import { readStored, writeStored, clearStored } from "../lib/storage";

const SELECTED_INSTANCE_KEY = "vrp:repartidor-selected-instance";
// Un cambio de estado con nota en curso (ej. escribiendo el motivo de un
// "No encontrado") se perdía sin aviso si la sesión expiraba a mitad del
// tipeo (App.tsx desmonta RepartidorView entero al reaccionar al 401) o si
// el repartidor volvía atrás con el botón/gesto del navegador — mismo
// mecanismo de persistencia ya usado para selectedId, aplicado acá.
const PENDING_CHANGE_KEY = "vrp:repartidor-pending-change";

interface StoredPendingChange {
  instanciaId: string;
  clientId: number;
  status: DeliveryStatus;
  note: string;
}

const STATUS_LABELS: Record<DeliveryStatus, string> = {
  pendiente: "Pendiente",
  entregado: "Entregado",
  no_encontrado: "No encontrado",
  reprogramado: "Reprogramado",
  rechazado: "Rechazado",
};

// "reprogramado" es un estado DERIVADO del flujo POST /instances/{id}/reschedule
// (solo dueño/operario) — nunca una acción manual del repartidor. Bug real
// (Ronda 15, ciclo nuevo): el botón aparecía habilitado en CADA parada,
// indistinguible de los otros cuatro, sin pedir confirmación (no está en
// TERMINAL_STATUSES como destino) — tocarlo disparaba un PUT inmediato que
// el backend rechaza con 422 (MANUALLY_SETTABLE_DELIVERY_STATUSES lo excluye
// a propósito), mostrando el detail crudo de Python sin traducir.
const MANUALLY_SELECTABLE_STATUSES: DeliveryStatus[] = ["pendiente", "entregado", "no_encontrado", "rechazado"];

// Revertir uno de estos sin querer (toque accidental) pierde el registro de
// una entrega ya confirmada — se pide confirmación antes de salir de acá.
const TERMINAL_STATUSES: DeliveryStatus[] = ["entregado", "no_encontrado", "reprogramado", "rechazado"];

// Estados donde vale la pena dejar contexto por escrito — el motivo de un
// rechazo o de no encontrar al cliente evita tener que llamar/whatsappear
// para preguntar qué pasó.
const NOTE_PROMPT_STATUSES: DeliveryStatus[] = ["no_encontrado", "rechazado"];

const dateFormatter = new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

function formatInstanceLabel(instance: InstanceSummary): string {
  if (!instance.created_at) return instance.id;
  const date = new Date(instance.created_at);
  if (Number.isNaN(date.getTime())) return instance.id;
  return `${instance.id} — ${dateFormatter.format(date)}`;
}

interface Props {
  onLogout: () => void;
}

export function RepartidorView({ onLogout: onLogoutProp }: Props) {
  // Limpia la instancia seleccionada de esta sesión antes de cerrar — si no,
  // sobrevivía en localStorage y quedaba ahí (sin efecto visible gracias al
  // guard que la descarta si ya no está asignada al usuario logueado, pero
  // es estado obsoleto que no debería sobrevivir a un logout).
  const onLogout = () => {
    clearStored(SELECTED_INSTANCE_KEY);
    clearStored(PENDING_CHANGE_KEY);
    onLogoutProp();
  };
  const [instances, setInstances] = useState<InstanceSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>(() => readStored<string>(SELECTED_INSTANCE_KEY) ?? "");
  const [route, setRoute] = useState<MyRouteResponse | null>(null);
  // Dos escritores async de `route` existen: el efecto de [selectedId] y el
  // refetch de recuperación tras un 403 en applyStatusChange. Sin coordinación,
  // cambiar de instancia (o volver a la misma dos veces) mientras uno está en
  // vuelo puede hacer que una respuesta VIEJA pise una más reciente. Comparar
  // por VALOR de selectedId no alcanza (A → B → A repite el mismo string "A" en
  // dos peticiones distintas) — un contador monotónico compartido identifica la
  // invocación exacta, y solo la respuesta de la última petición disparada por
  // CUALQUIERA de los dos escritores puede aplicar setRoute.
  const routeFetchSeqRef = useRef(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Set en vez de un id escalar: marcar varias paradas casi simultáneamente
  // (dedo rápido llegando a una zona con varias entregas juntas) hacía que
  // solo la última parada mostrara "Guardando…"/"✓ Guardado" — las demás se
  // guardaban bien (el fix de setRoute funcional ya lo garantiza) pero sin
  // ningún feedback visual, generando dudas y toques repetidos innecesarios.
  const [savingStopIds, setSavingStopIds] = useState<Set<number>>(new Set());
  const [savedStopIds, setSavedStopIds] = useState<Set<number>>(new Set());
  // RN-024: "No encuentro la dirección" — mismo patrón de feedback
  // (enviando/enviado) que savingStopIds/savedStopIds, en Sets separados
  // porque son acciones independientes sobre la misma parada.
  const [sendingAlertIds, setSendingAlertIds] = useState<Set<number>>(new Set());
  const [sentAlertIds, setSentAlertIds] = useState<Set<number>>(new Set());
  // RN-025: comprobante fotográfico — se agrega DESPUÉS de marcar "entregado"
  // (no bloquea el toque único existente de ese botón), vía un input de
  // archivo oculto por parada, disparado por un botón visible.
  const [uploadingPhotoIds, setUploadingPhotoIds] = useState<Set<number>>(new Set());
  const [photoUploadedIds, setPhotoUploadedIds] = useState<Set<number>>(new Set());
  const photoInputRefs = useRef<Map<number, HTMLInputElement>>(new Map());
  const [pendingChange, setPendingChange] = useState<
    { instanciaId: string; clientId: number; status: DeliveryStatus } | null
  >(() => {
    const stored = readStored<StoredPendingChange>(PENDING_CHANGE_KEY);
    return stored ? { instanciaId: stored.instanciaId, clientId: stored.clientId, status: stored.status } : null;
  });
  const [noteDraft, setNoteDraft] = useState(
    () => readStored<StoredPendingChange>(PENDING_CHANGE_KEY)?.note ?? ""
  );

  // Si el guardado de la nota en curso falla (localStorage bloqueado/lleno,
  // Safari privado), antes no había ninguna señal — el repartidor escribía
  // el motivo de un "No encontrado" creyendo que sobreviviría a un 401/back-
  // nav/reload, y en realidad se perdía en silencio. Se avisa una sola vez,
  // sin repetir el error en cada tecla.
  const [noteSaveFailed, setNoteSaveFailed] = useState(false);

  useEffect(() => {
    if (pendingChange) {
      const saved = writeStored(PENDING_CHANGE_KEY, { ...pendingChange, note: noteDraft });
      // Solo avisar si el estado realmente tiene campo de nota — en otros
      // casos (ej. "entregado") el textarea ni se renderiza, y el mensaje
      // "no se pudo guardar tu nota" sería falso (no hay ninguna nota).
      setNoteSaveFailed(!saved && NOTE_PROMPT_STATUSES.includes(pendingChange.status));
    } else {
      clearStored(PENDING_CHANGE_KEY);
      setNoteSaveFailed(false);
    }
  }, [pendingChange, noteDraft]);

  const [instancesError, setInstancesError] = useState<string | null>(null);

  // `hasPendingChange` se recibe como parámetro en vez de leer `pendingChange`
  // del closure: los callers que CIERRAN el diálogo (onCancel/onConfirm de
  // más abajo) llaman a loadInstances() en el mismo handler donde acaban de
  // hacer setPendingChange(null) — como los setState no se aplican hasta el
  // próximo render, el closure de esta función seguiría viendo el
  // `pendingChange` VIEJO (no nulo) si se leyera directamente, dejando el
  // guard de abajo sin efecto justo cuando más hace falta revalidar.
  const loadInstances = (hasPendingChange: boolean = pendingChange !== null) => {
    setInstancesError(null);
    api
      .listInstances({ assignedOnly: true })
      .then((list) => {
        setInstances(list);
        // Si la instancia restaurada de una sesión anterior ya no está entre
        // las asignadas (reasignada a otro repartidor, etc.), no la dejamos
        // seleccionada apuntando a algo que ya no existe para este usuario.
        // EXCEPTO si hay un pendingChange activo (diálogo de cambio de
        // estado abierto, posiblemente con una nota siendo escrita en ese
        // instante) — deseleccionar acá dispara el efecto de [selectedId],
        // que al ver !selectedId limpia route Y pendingChange, perdiendo la
        // nota en curso sin ningún aviso (a diferencia de noteSaveFailed,
        // que sí cubre otros casos de pérdida). El propio selector ya se
        // deshabilita mientras pendingChange existe (línea de abajo), así
        // que este guard solo pospone la limpieza hasta que el repartidor
        // resuelva el diálogo, sin dejarlo interactuando con datos huérfanos.
        setSelectedId((current) =>
          current && !hasPendingChange && !list.some((i) => i.id === current) ? "" : current
        );
      })
      .catch((err) => {
        // Antes se tragaba en silencio: con conexión inestable (el caso
        // típico de un repartidor en la calle) el select quedaba vacío,
        // indistinguible de "genuinamente no tenés ninguna instancia
        // asignada" — sin forma de saber si había que esperar, recargar, o
        // si el día no había reparto.
        setInstancesError((err as Error).message);
      });
  };

  useEffect(loadInstances, []);

  useEffect(() => {
    if (selectedId) writeStored(SELECTED_INSTANCE_KEY, selectedId);
  }, [selectedId]);

  useEffect(() => {
    // Bug real (Ronda 1, ciclo nuevo, repartidor): a diferencia de route/
    // pendingChange/error, estos dos Sets no se reseteaban al cambiar de
    // instancia — un client_id de la instancia anterior mostraba "Guardando…"
    // /"✓ Guardado" en la instancia nueva sin que el repartidor hubiera
    // tocado nada ahí (RN-004 solo garantiza ids únicos DENTRO de una
    // instancia, no entre instancias distintas).
    setSavingStopIds(new Set());
    setSavedStopIds(new Set());
    if (!selectedId) {
      setRoute(null);
      // Sin ninguna instancia seleccionada no hay ninguna ruta contra la
      // cual validar un pendingChange restaurado — mismo caso huérfano que
      // el guard de abajo, pero acá no hay route.stops que consultar.
      setPendingChange(null);
      return;
    }
    setLoading(true);
    setError(null);
    const requestSeq = ++routeFetchSeqRef.current;
    api
      .getMyRoute(selectedId)
      .then((newRoute) => {
        // Si esta no es la petición de ruta MÁS RECIENTE disparada (ya sea porque
        // cambió selectedId, o porque se volvió a disparar el mismo selectedId dos
        // veces y esta es la respuesta más vieja de las dos), descartar.
        if (routeFetchSeqRef.current !== requestSeq) return;
        setRoute(newRoute);
        // pendingChange restaurado de localStorage (sesión expirada, reload,
        // back-nav) puede referenciar un clientId de OTRA instancia — sin
        // este guard el diálogo de confirmación se abría igual con datos
        // huérfanos (nombre "Cliente #N" genérico, estado "pendiente" por
        // defecto) y confirmar mandaba un PUT a un cliente que no pertenece
        // a esta ruta. Se descarta si el cliente no está en la ruta recién
        // cargada — mismo criterio que ya se usa para selectedId arriba.
        setPendingChange((current) =>
          current &&
          (current.instanciaId !== newRoute.instancia_id ||
            !newRoute.stops.some((s) => s.client_id === current.clientId))
            ? null
            : current
        );
      })
      .catch((err) => {
        if (routeFetchSeqRef.current !== requestSeq) return;
        setRoute(null);
        // Mismo guard que en el .then de arriba: sin ruta cargada (404 u
        // otro error) no hay contra qué validar un pendingChange restaurado
        // — dejarlo abierto mostraba el diálogo con datos huérfanos
        // ("Cliente #N" genérico) sobre una instancia sin ruta.
        setPendingChange(null);
        setError((err as Error).message.includes("404") ? "No tenés una ruta asignada en esta instancia." : (err as Error).message);
      })
      .finally(() => {
        if (routeFetchSeqRef.current === requestSeq) setLoading(false);
      });
  }, [selectedId]);

  const applyStatusChange = async (clientId: number, status: DeliveryStatus, note?: string) => {
    if (!route) return;
    setSavingStopIds((prev) => new Set(prev).add(clientId));
    setError(null);
    try {
      await api.updateDeliveryStatus(route.instancia_id, clientId, status, note);
      // Forma funcional: marcar varias paradas casi al mismo tiempo (dedo
      // rápido en la calle) dispara varias applyStatusChange en paralelo:
      // cada await resuelve en un orden distinto, y con "route" cerrado del
      // closure cada setRoute partía de la misma copia vieja — la última en
      // resolver pisaba el estado de las que ya habían terminado antes,
      // perdiendo su marca en la UI aunque el PUT ya estuviera confirmado
      // en el backend (bug real reproducido: 3 de 5 paradas quedaban sin
      // reflejar el guardado exitoso).
      setRoute((prev) =>
        prev
          ? {
              ...prev,
              stops: prev.stops.map((s) =>
                s.client_id === clientId ? { ...s, delivery_status: status, delivery_note: note } : s
              ),
            }
          : prev
      );
      setSavedStopIds((prev) => new Set(prev).add(clientId));
      setTimeout(
        () =>
          setSavedStopIds((prev) => {
            const next = new Set(prev);
            next.delete(clientId);
            return next;
          }),
        1500
      );
    } catch (err) {
      const message = (err as Error).message;
      setError(message);
      // Bug real (Ronda 47): si el diálogo de confirmación ya estaba abierto
      // sobre esta parada cuando el dueño/operario la reprogramó a otra
      // instancia, el PUT cae en 409 ("ya fue reprogramado...") — pero antes
      // `route.stops` en memoria se quedaba con el estado VIEJO (ej.
      // "pendiente"), así que ni el aviso ni el disabled de los botones (que
      // dependen de `stop.delivery_status === "reprogramado"`) se activaban.
      // El repartidor podía repetir el mismo 409 indefinidamente sin que la
      // UI reflejara jamás el bloqueo. Se sincroniza localmente apenas se
      // detecta este 409 específico — no hace falta un refetch completo,
      // el único dato que cambió es el estado de ESTA parada.
      if (message.includes("ya fue reprogramado")) {
        setRoute((prev) =>
          prev
            ? { ...prev, stops: prev.stops.map((s) => (s.client_id === clientId ? { ...s, delivery_status: "reprogramado" } : s)) }
            : prev
        );
      }
      // Si el dueño/operario re-resolvió la instancia mientras esta ruta
      // seguía en pantalla, el backend invalida la asignación y este PUT
      // cae en 403 — sin esto, la ruta vieja se quedaba mostrada como si
      // siguiera vigente (paradas y botones totalmente interactivos), y
      // cualquier otro toque repetía el mismo 403 sin que el repartidor
      // entendiera que la ruta entera ya no le pertenece.
      //
      // Se fuerza un refetch en vez de solo limpiar `route` — un simple
      // setRoute(null) dejaba al repartidor sin forma de recuperarse si
      // esta era su única instancia asignada: re-elegirla en el <select>
      // no dispara onChange (el valor no cambió), así que el efecto de
      // [selectedId] nunca volvía a correr. El refetch trae el estado
      // real (una ruta nueva si fue reasignado, o el mismo 403/404 que
      // deja la pantalla vacía con un mensaje claro en vez de congelada).
      // Bug real (Ronda 16, ciclo nuevo, repartidor): DeliveryStatusControl.tsx
      // (vista de escritorio) ya resincroniza contra el estado real del
      // backend cuando el error es de red/timeout, porque el PUT es
      // idempotente y puede haber llegado igual aunque el cliente no
      // recibiera la respuesta a tiempo — acá, el componente donde el
      // escenario "mala señal" es más probable, no tenía ese mismo manejo:
      // un timeout dejaba la parada mostrando el estado VIEJO sin ningún
      // indicio de que el cambio sí pudo haberse guardado en el servidor.
      const isNetworkIssue = message.includes("tardó demasiado") || message.includes("Sin conexión");
      if (isNetworkIssue && route) {
        const requestedId = route.instancia_id;
        api
          .getDeliveryStatuses(requestedId)
          .then((statuses) => {
            const real = statuses[clientId];
            if (!real) return;
            setRoute((prev) =>
              prev
                ? {
                    ...prev,
                    stops: prev.stops.map((s) =>
                      s.client_id === clientId
                        ? { ...s, delivery_status: real.status as DeliveryStatus, delivery_note: real.note }
                        : s
                    ),
                  }
                : prev
            );
          })
          .catch(() => {});
      }
      if (message.includes("No tenés una ruta asignada") && route) {
        const requestedId = route.instancia_id;
        // Mismo contador que el efecto de [selectedId] (una sola secuencia
        // compartida entre los dos escritores de route) — así, si el usuario
        // cambia de instancia mientras este refetch de recuperación está en
        // vuelo, o si se dispara dos veces seguidas, solo la respuesta más
        // reciente de CUALQUIERA de los dos escritores puede aplicar setRoute.
        const requestSeq = ++routeFetchSeqRef.current;
        api
          .getMyRoute(requestedId)
          .then((newRoute) => {
            if (routeFetchSeqRef.current !== requestSeq) return;
            setRoute(newRoute);
          })
          .catch((recoveryErr) => {
            if (routeFetchSeqRef.current !== requestSeq) return;
            setRoute(null);
            // "No encontrada"/404 sí significa reasignación real; cualquier
            // otro fallo (sin señal, timeout) no lo es — mostrar siempre el
            // mensaje de reasignación enmascaraba fallos de red genuinos
            // detrás de un texto que no tenía nada que ver.
            const recoveryMessage = (recoveryErr as Error).message;
            setError(
              recoveryMessage.includes("404") || recoveryMessage.includes("no encontrada")
                ? "Ya no tenés una ruta asignada en esta instancia — es posible que te hayan reasignado."
                : recoveryMessage
            );
          });
      }
    } finally {
      setSavingStopIds((prev) => {
        const next = new Set(prev);
        next.delete(clientId);
        return next;
      });
    }
  };

  // RN-024: notifica al dueño/operador sobre un problema puntual con este
  // pedido — no cambia el estado de entrega, es independiente del flujo de
  // applyStatusChange/handleStatusChange de arriba.
  const handleHelpAlert = async (clientId: number) => {
    if (!route) return;
    setSendingAlertIds((prev) => new Set(prev).add(clientId));
    setError(null);
    try {
      await api.createAlert({
        instancia_id: route.instancia_id,
        cliente_id: clientId,
        motivo: "No encuentro la dirección",
      });
      setSentAlertIds((prev) => new Set(prev).add(clientId));
      setTimeout(
        () =>
          setSentAlertIds((prev) => {
            const next = new Set(prev);
            next.delete(clientId);
            return next;
          }),
        3000
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSendingAlertIds((prev) => {
        const next = new Set(prev);
        next.delete(clientId);
        return next;
      });
    }
  };

  // RN-025: sube el comprobante fotográfico de una parada ya entregada —
  // reenvía el mismo status ("entregado") junto con el Base64, sin tocar la
  // nota existente (no aplica a este estado, ver NOTE_PROMPT_STATUSES).
  const handlePhotoSelected = async (clientId: number, file: File) => {
    if (!route) return;
    setUploadingPhotoIds((prev) => new Set(prev).add(clientId));
    setError(null);
    try {
      const fotoBase64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = () => reject(new Error("No se pudo leer la foto — probá de nuevo."));
        reader.readAsDataURL(file);
      });
      await api.updateDeliveryStatus(route.instancia_id, clientId, "entregado", undefined, fotoBase64);
      setRoute((prev) =>
        prev
          ? { ...prev, stops: prev.stops.map((s) => (s.client_id === clientId ? { ...s, has_photo: true } : s)) }
          : prev
      );
      setPhotoUploadedIds((prev) => new Set(prev).add(clientId));
      setTimeout(
        () =>
          setPhotoUploadedIds((prev) => {
            const next = new Set(prev);
            next.delete(clientId);
            return next;
          }),
        1500
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploadingPhotoIds((prev) => {
        const next = new Set(prev);
        next.delete(clientId);
        return next;
      });
    }
  };

  const handleStatusChange = (clientId: number, status: DeliveryStatus) => {
    if (!route) return;
    const stop = route.stops.find((s) => s.client_id === clientId);
    const leavesTerminal = stop && TERMINAL_STATUSES.includes(stop.delivery_status) && stop.delivery_status !== status;
    if (leavesTerminal || NOTE_PROMPT_STATUSES.includes(status)) {
      // Si ya había una nota (ej. re-tocar "No encontrado" tras un segundo
      // intento), se precarga en vez de arrancar en blanco — evita perderla
      // de vista o pisarla sin querer con un textarea vacío.
      setNoteDraft(stop?.delivery_note ?? "");
      setPendingChange({ instanciaId: route.instancia_id, clientId, status });
      return;
    }
    applyStatusChange(clientId, status);
  };

  const [exportingPdf, setExportingPdf] = useState(false);

  const handleExportPdf = async () => {
    if (!route || exportingPdf) return;
    setExportingPdf(true);
    try {
      const blob = await api.exportSolutionPdf(route.instancia_id, route.vehicle_id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `mi_ruta_${route.instancia_id}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
      // Un export exitoso no debería dejar visible un error viejo de un
      // intento anterior (ej. de una carga de ruta fallida) — con señal
      // metida/con mala conexión el repartidor puede reintentar varias
      // veces antes de que uno funcione.
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setExportingPdf(false);
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
          <select
            id="instance-select"
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            // Cambiar de instancia con el diálogo de confirmación abierto
            // dejaba una ventana (mientras la ruta nueva cargaba) donde
            // tocar "Confirmar" mandaba applyStatusChange con route=null —
            // el guard ahí lo descarta en silencio, perdiendo la nota
            // recién escrita sin ningún aviso. Se bloquea el cambio de
            // instancia hasta que el repartidor resuelva el diálogo actual.
            disabled={pendingChange !== null}
            title={pendingChange !== null ? "Resolvé el cambio de estado pendiente antes de cambiar de instancia" : undefined}
          >
            <option value="">Elegí una instancia…</option>
            {instances.map((i) => (
              <option key={i.id} value={i.id}>
                {formatInstanceLabel(i)}
              </option>
            ))}
          </select>
          {pendingChange !== null && (
            // El `title` (tooltip por hover) no se dispara con touch en
            // mobile — sin este texto visible, el repartidor solo ve el
            // select gris/opaco sin ninguna forma de enterarse de por qué
            // ni qué hacer al respecto.
            <p className="import-status">Resolvé el cambio de estado pendiente antes de cambiar de instancia.</p>
          )}
          {instancesError && (
            <p className="error-message" role="alert">
              No se pudo cargar tus instancias asignadas: {instancesError}{" "}
              <button type="button" className="btn-secondary" onClick={loadInstances}>
                Reintentar
              </button>
            </p>
          )}
          {!instancesError && instances.length === 0 && (
            // Bug real (Ronda 3, ciclo nuevo, repartidor): sin este aviso, una
            // carga exitosa con 0 instancias asignadas (todavía no le crearon
            // la ruta de hoy) era indistinguible de "la app no cargó bien" —
            // el select solo mostraba el placeholder "Elegí una instancia…".
            <p className="import-status">Todavía no tenés ninguna ruta asignada.</p>
          )}
        </div>

        {loading && <p className="import-status">Cargando ruta…</p>}
        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}

        {route && (
          <>
            <button type="button" className="btn-secondary repartidor-export" onClick={handleExportPdf} disabled={exportingPdf}>
              {exportingPdf ? "Generando PDF…" : "Exportar mi hoja en PDF"}
            </button>

            {route.stops.length === 0 && (
              <p className="repartidor-empty">No tenés paradas asignadas en esta instancia.</p>
            )}
            {route.stops.length > 0 && route.stops.every((s) => s.delivery_status === "reprogramado") && (
              // Bug real (Ronda 47): get_my_route sigue devolviendo las
              // paradas reprogramadas (por diseño, para no perder el
              // historial) — sin este aviso, una instancia donde el dueño
              // reprogramó TODO se veía como una ruta normal con N paradas,
              // todas grises, sin ninguna explicación de por qué ninguna es
              // interactuable.
              <p className="repartidor-empty">Todos los pedidos de esta instancia fueron reprogramados a otra instancia.</p>
            )}
            {route.stops.length > 0 && route.stops.every((s) => s.delivery_status !== "pendiente") && (
              // Bug real (Ronda 3, ciclo nuevo, repartidor): mismo patrón que
              // el aviso de "reprogramado" de arriba, generalizado al caso más
              // común — sin esto, terminar la ruta del día (todo entregado/
              // rechazado/no encontrado) se veía igual que una ruta a medio
              // hacer, sin ninguna señal de "ya no queda nada por marcar".
              <p className="repartidor-empty">Ruta de hoy completa — no quedan paradas pendientes.</p>
            )}

            <ol className="repartidor-stops">
              {route.stops.map((stop) => (
                <li key={stop.client_id} className="repartidor-stop">
                  <div className="repartidor-stop-header">
                    <span className="repartidor-stop-sequence">{stop.sequence}</span>
                    <span className="repartidor-stop-name">{stop.customer_name?.trim() || `Cliente #${stop.client_id}`}</span>
                  </div>
                  {(() => {
                    // Bug real (Ronda 6, ciclo nuevo, repartidor):
                    // customer_phone es texto completamente libre, sin
                    // ninguna validación en todo el pipeline (import CSV,
                    // edición manual) — algo como "999888777 (casa)" viajaba
                    // intacto al href, y el marcador nativo podía rechazar
                    // el tel: completo en vez de solo ignorar el sufijo.
                    // Se conservan solo dígitos y un "+" inicial opcional.
                    const digitsOnly = stop.customer_phone?.replace(/(?!^\+)[^\d]/g, "") ?? "";
                    // Bug real (Ronda 13, ciclo nuevo, repartidor): si el
                    // texto no tenía NINGÚN dígito (ej. "N/A", "preguntar en
                    // portería"), el guard de arriba (customer_phone no
                    // vacío) pasaba igual pero el resultado saneado quedaba
                    // vacío — el botón se veía como un teléfono válido pero
                    // al tocarlo abría "tel:" sin número, sin ningún aviso.
                    if (!digitsOnly) return null;
                    return (
                      <a className="repartidor-stop-link" href={`tel:${digitsOnly}`}>
                        📞 {stop.customer_phone}
                      </a>
                    );
                  })()}
                  {stop.address?.trim() ? (
                    <a
                      className="repartidor-stop-link"
                      // geo: solo tiene handler nativo en Android — en iOS
                      // Safari no hace nada (ni error, ni fallback), el
                      // repartidor pierde la función de "cómo llegar" sin
                      // ningún aviso. La URL universal de Google Maps abre
                      // la app nativa en ambas plataformas, y cae al mapa
                      // en el navegador si no hay app instalada.
                      href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(stop.address.trim())}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      📍 {stop.address.trim()}
                    </a>
                  ) : (
                    // Bug real (Ronda 5, ciclo nuevo, repartidor): sin esto,
                    // una dirección vacía/solo-espacios hacía desaparecer el
                    // bloque entero (indistinguible de "no hay nada acá") o,
                    // sin el .trim(), renderizaba un link visible pero roto
                    // (📍 seguido de espacio en blanco, abriendo Google Maps
                    // con query vacío) — inconsistente con customer_name, que
                    // sí tiene fallback explícito.
                    <span className="repartidor-stop-link repartidor-stop-link--missing">📍 Sin dirección registrada</span>
                  )}
                  {stop.delivery_note && <p className="repartidor-stop-note">📝 {stop.delivery_note}</p>}
                  {stop.delivery_status === "reprogramado" && (
                    // Bug real (Ronda 46, confirmación): el dueño/operario puede
                    // reprogramar la instancia mientras el repartidor la tiene
                    // abierta — el pedido queda "reprogramado" en ESTA ruta para
                    // siempre (get_my_route lo sigue devolviendo, ver comentario
                    // en el backend), pero movido de verdad a una instancia
                    // nueva. Sin este aviso, los botones seguían habilitados:
                    // el repartidor pasaba por todo el diálogo de confirmación
                    // creyendo que era una acción válida, y recién al confirmar
                    // se enteraba vía un 409 del backend ("ya fue reprogramado a
                    // otra instancia, no se puede modificar acá").
                    <p className="import-status">Este pedido fue reprogramado a otra instancia — ya no se puede modificar acá.</p>
                  )}
                  <div className="repartidor-stop-actions">
                    {MANUALLY_SELECTABLE_STATUSES.map((status) => (
                      <button
                        key={status}
                        type="button"
                        className={
                          stop.delivery_status === status
                            ? "repartidor-status-btn repartidor-status-btn--active"
                            : "repartidor-status-btn"
                        }
                        disabled={savingStopIds.has(stop.client_id) || stop.delivery_status === "reprogramado"}
                        onClick={() => handleStatusChange(stop.client_id, status)}
                      >
                        {STATUS_LABELS[status]}
                      </button>
                    ))}
                    {savingStopIds.has(stop.client_id) && (
                      <span className="stop-save-indicator" role="status" aria-live="polite">Guardando…</span>
                    )}
                    {savedStopIds.has(stop.client_id) && (
                      <span className="stop-save-indicator stop-save-indicator--saved" role="status" aria-live="polite">✓ Guardado</span>
                    )}
                    <button
                      type="button"
                      className="repartidor-help-btn"
                      disabled={sendingAlertIds.has(stop.client_id)}
                      onClick={() => handleHelpAlert(stop.client_id)}
                    >
                      🆘 No encuentro la dirección
                    </button>
                    {sendingAlertIds.has(stop.client_id) && (
                      <span className="stop-save-indicator" role="status" aria-live="polite">Enviando…</span>
                    )}
                    {sentAlertIds.has(stop.client_id) && (
                      <span className="stop-save-indicator stop-save-indicator--saved" role="status" aria-live="polite">✓ Avisado</span>
                    )}
                    {stop.delivery_status === "entregado" && (
                      <>
                        <input
                          ref={(el) => {
                            if (el) photoInputRefs.current.set(stop.client_id, el);
                            else photoInputRefs.current.delete(stop.client_id);
                          }}
                          type="file"
                          accept="image/*"
                          capture="environment"
                          className="repartidor-photo-input"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) handlePhotoSelected(stop.client_id, file);
                            e.target.value = "";
                          }}
                        />
                        <button
                          type="button"
                          className="repartidor-photo-btn"
                          disabled={uploadingPhotoIds.has(stop.client_id)}
                          onClick={() => photoInputRefs.current.get(stop.client_id)?.click()}
                        >
                          {stop.has_photo ? "📷 Cambiar foto" : "📷 Agregar foto"}
                        </button>
                        {uploadingPhotoIds.has(stop.client_id) && (
                          <span className="stop-save-indicator" role="status" aria-live="polite">Subiendo…</span>
                        )}
                        {photoUploadedIds.has(stop.client_id) && (
                          <span className="stop-save-indicator stop-save-indicator--saved" role="status" aria-live="polite">✓ Foto guardada</span>
                        )}
                      </>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
      </div>

      <ConfirmDialog
        open={pendingChange !== null}
        title="Cambiar estado de entrega"
        message={
          pendingChange
            ? `¿Seguro que querés cambiar el estado de ${
                route?.stops.find((s) => s.client_id === pendingChange.clientId)?.customer_name?.trim() ||
                `Cliente #${pendingChange.clientId}`
              } de "${STATUS_LABELS[route?.stops.find((s) => s.client_id === pendingChange.clientId)?.delivery_status ?? "pendiente"]}" a "${STATUS_LABELS[pendingChange.status]}"?`
            : ""
        }
        onCancel={() => {
          setPendingChange(null);
          // El guard de loadInstances (Ronda 39) pospone deseleccionar la
          // instancia mientras el diálogo está abierto — sin este re-chequeo
          // al cerrarlo, si la instancia dejó de estar asignada MIENTRAS el
          // diálogo estaba abierto, el repartidor quedaba viendo la ruta
          // vieja indefinidamente (select apuntando a un value que ya no
          // está entre las opciones), sin aviso, hasta tocar un botón de
          // estado (que sí dispara la recuperación vía 403 en applyStatusChange).
          // `false` explícito: el diálogo se está cerrando en este mismo
          // handler, así que ya no cuenta como pendiente aunque el closure
          // de `pendingChange` todavía no refleje el setPendingChange de arriba.
          loadInstances(false);
        }}
        onConfirm={() => {
          // Bug real (Ronda 43, confirmación): handleStatusChange precarga
          // noteDraft con la nota YA EXISTENTE de la parada (para no perderla
          // de vista al reabrir el mismo estado con nota), pero eso incluye
          // transiciones que SALEN de un estado terminal hacia uno que no
          // admite nota (ej. Rechazado con nota → Entregado) — el textarea ni
          // se renderiza ahí (NOTE_PROMPT_STATUSES no incluye "entregado"),
          // así que el repartidor no la ve ni puede editarla/borrarla, pero
          // igual viajaba adjunta al nuevo estado sin que nadie la hubiera
          // puesto ahí a propósito.
          if (pendingChange) {
            const note = NOTE_PROMPT_STATUSES.includes(pendingChange.status) ? noteDraft.trim() || undefined : undefined;
            applyStatusChange(pendingChange.clientId, pendingChange.status, note);
          }
          setPendingChange(null);
          loadInstances(false);
        }}
      >
        {pendingChange && NOTE_PROMPT_STATUSES.includes(pendingChange.status) && (
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
        {noteSaveFailed && (
          <p className="error-message" role="alert">
            No se pudo guardar tu nota en este celular (memoria llena o modo privado) — si cerrás esta pantalla antes
            de confirmar, la vas a perder. Confirmá ahora si podés.
          </p>
        )}
      </ConfirmDialog>
    </div>
  );
}
