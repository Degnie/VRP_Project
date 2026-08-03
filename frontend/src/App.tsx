import { lazy, Suspense, useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, SESSION_EXPIRED_EVENT } from "./lib/api";
import type { ClientGroup, InstanceRequest, SolutionResponse } from "./lib/types";
import { readStored, writeStored, clearStored } from "./lib/storage";
import { loadCoverageZone, saveCoverageZone, clearCoverageZone } from "./lib/coverageZone";
import { getSession, clearSession, type AuthSession } from "./lib/auth";
import { HealthBadge } from "./components/HealthBadge";
import { LoginForm } from "./components/LoginForm";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "./App.css";

const RouteMap = lazy(() => import("./components/RouteMap").then((m) => ({ default: m.RouteMap })));
// Bug real (Ronda 4, ciclo nuevo, repartidor): estos componentes (~1800
// líneas + @turf/*) solo los usa el rol dueño/operario, pero al importarlos
// de forma estática quedaban en el mismo chunk que RepartidorView — un
// repartidor en 2G/datos limitados tenía que descargar y parsear código de
// pantallas que su rol nunca renderiza antes de llegar a "Mi ruta".
const RepartidorView = lazy(() => import("./components/RepartidorView").then((m) => ({ default: m.RepartidorView })));
const InstanceForm = lazy(() => import("./components/InstanceForm").then((m) => ({ default: m.InstanceForm })));
const SolutionSummary = lazy(() => import("./components/SolutionSummary").then((m) => ({ default: m.SolutionSummary })));
const CoverageZoneEditor = lazy(() => import("./components/CoverageZoneEditor").then((m) => ({ default: m.CoverageZoneEditor })));
const TeamManagement = lazy(() => import("./components/TeamManagement").then((m) => ({ default: m.TeamManagement })));

const INSTANCE_STORAGE_KEY = "vrp:last-instance";
const SOLUTION_STORAGE_KEY = "vrp:last-solution";
const CONTACTS_STORAGE_KEY = "vrp:last-contacts";

function App() {
  const [session, setSession] = useState<AuthSession | null>(() => getSession());
  const [instance, setInstance] = useState<InstanceRequest | null>(() => readStored(INSTANCE_STORAGE_KEY));
  const [solution, setSolution] = useState<SolutionResponse | null>(() => readStored(SOLUTION_STORAGE_KEY));
  const [contacts, setContacts] = useState<ClientGroup[] | null>(() => readStored(CONTACTS_STORAGE_KEY));
  const [editingCoverage, setEditingCoverage] = useState(false);
  const [coveragePoints, setCoveragePoints] = useState<[number, number][]>([]);
  const [pendingContacts, setPendingContacts] = useState<ClientGroup[] | null>(null);
  const [showTeamManagement, setShowTeamManagement] = useState(false);
  const [overwriteConfirm, setOverwriteConfirm] = useState<{ request: InstanceRequest; clients: ClientGroup[] } | null>(null);
  const [coverageSyncError, setCoverageSyncError] = useState<string | null>(null);
  const [persistWarning, setPersistWarning] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    loadCoverageZone()
      .then((zone) => setCoveragePoints(zone?.points ?? []))
      .catch(() => {});
  }, [session]);

  const solveMutation = useMutation({
    mutationFn: api.solve,
    onSuccess: (data, request) => {
      setSolution(data);
      setContacts(pendingContacts);
      // Persistir solo tras un solve exitoso: guardar en el submit permitía que una
      // instancia inválida (rechazada por el backend) quedara pegada en localStorage
      // y se restaurara en cada carga, incluso tras reiniciar el servidor.
      const instanceOk = writeStored(INSTANCE_STORAGE_KEY, request);
      const solutionOk = writeStored(SOLUTION_STORAGE_KEY, data);
      const contactsOk = pendingContacts ? writeStored(CONTACTS_STORAGE_KEY, pendingContacts) : true;
      // Bug real (Ronda 3, ciclo nuevo, dueño): igual que saveSession ya hace
      // para el login, hay que avisar si esto no persistió — con una
      // instancia grande (el propio repo trae ejemplo_500.vrp/ejemplo_50000.vrp
      // como casos reales) el payload puede superar la cuota de localStorage.
      // Sin este aviso, la ruta se ve bien en el momento pero desaparece sin
      // explicación al volver más tarde o recargar.
      if (!instanceOk || !solutionOk || !contactsOk) {
        setPersistWarning(
          "La ruta se resolvió bien, pero no se pudo guardar localmente para recuperarla si recargás la página (memoria del navegador llena o bloqueada)."
        );
      } else {
        setPersistWarning(null);
      }
    },
  });

  const runSolve = (request: InstanceRequest, clients: ClientGroup[]) => {
    setInstance(request);
    setSolution(null);
    setPendingContacts(clients);
    solveMutation.mutate(request);
  };

  const handleSubmit = async (request: InstanceRequest, clients: ClientGroup[]) => {
    // El campo "ID de instancia" arranca siempre en el mismo valor por
    // defecto ("instancia-1") — resolver dos veces sin cambiarlo pisa la
    // solución/estados de entrega anteriores en silencio (ON CONFLICT DO
    // UPDATE en el backend). Se avisa antes de mandar el POST.
    try {
      const existing = await api.listInstances();
      if (existing.some((i) => i.id === request.instancia_id)) {
        setOverwriteConfirm({ request, clients });
        return;
      }
    } catch {
      // Si no se puede chequear (ej. sin conexión), se sigue con el submit normal.
    }
    runSolve(request, clients);
  };

  const handleReset = () => {
    setInstance(null);
    setSolution(null);
    setContacts(null);
    clearStored(INSTANCE_STORAGE_KEY);
    clearStored(SOLUTION_STORAGE_KEY);
    clearStored(CONTACTS_STORAGE_KEY);
  };

  const handleCloseCoveragePolygon = () => {
    setEditingCoverage(false);
    if (coveragePoints.length >= 3) {
      setCoverageSyncError(null);
      saveCoverageZone({ points: coveragePoints }).catch(() =>
        // Bug real: si el PUT fallaba, el polígono ya se veía dibujado en el
        // mapa (estado local) pero nunca se persistía — el dueño creía que
        // había guardado una zona que en realidad no sobrevivía a un reload.
        setCoverageSyncError("No se pudo guardar la zona de cobertura — revisá tu conexión e intentá de nuevo.")
      );
    }
  };

  // Bug real (Ronda 4, ciclo 4, dueño — RN-COV-004): a diferencia de borrar
  // instancia o desactivar usuario, este botón ejecutaba el borrado directo
  // al click, sin confirmación — y está al lado de "Redibujar zona" (que no
  // borra nada hasta cerrar el nuevo polígono), con riesgo real de click
  // accidental entre ambos. Es irreversible y afecta a toda la cuenta.
  const [confirmingCoverageDelete, setConfirmingCoverageDelete] = useState(false);

  const handleDeleteCoverage = () => {
    // Bug real (Ronda 2, ciclo nuevo, dueño): el polígono se borraba del
    // mapa de forma optimista antes de saber si el DELETE tenía éxito — si
    // fallaba (ej. corte de red), el mapa quedaba sin zona visible mientras
    // el backend todavía la tenía guardada, sin ningún indicio salvo un
    // texto de error fácil de no leer. Se espera la confirmación del
    // borrado, igual que handleCloseCoveragePolygon ya hace con el guardado.
    setCoverageSyncError(null);
    clearCoverageZone()
      .then(() => {
        setCoveragePoints([]);
        setConfirmingCoverageDelete(false);
      })
      .catch(() =>
        setCoverageSyncError("No se pudo borrar la zona de cobertura guardada — revisá tu conexión e intentá de nuevo.")
      );
  };

  const handleLogout = () => {
    // Sin esto, cerrar sesión y loguear con otra cuenta en el mismo
    // navegador restauraba la última instancia/solución/contactos de la
    // sesión anterior desde localStorage — mismo tipo de fuga de estado ya
    // corregido para el selector de instancia del repartidor.
    clearStored(INSTANCE_STORAGE_KEY);
    clearStored(SOLUTION_STORAGE_KEY);
    clearStored(CONTACTS_STORAGE_KEY);
    setInstance(null);
    setSolution(null);
    setContacts(null);
    clearSession();
    setSession(null);
    setSessionExpiredMessage(null);
  };

  // request() en api.ts dispara esto apenas el backend rechaza el token con
  // 401 (usuario desactivado, o token vencido) — vuelve a la pantalla de
  // login en vez de dejar al usuario mirando un error crudo sin salida. El
  // mensaje se guarda acá (no en el componente que hizo el request, que se
  // desmonta antes de poder mostrarlo) para pasárselo a LoginForm.
  const [sessionExpiredMessage, setSessionExpiredMessage] = useState<string | null>(null);
  useEffect(() => {
    const onSessionExpired = () => {
      handleLogout();
      // Después de handleLogout (que limpia sessionExpiredMessage a null,
      // para el caso de un logout manual) — si se seteara antes, quedaría
      // pisado por esa limpieza.
      setSessionExpiredMessage("Tu sesión ya no es válida — volvé a iniciar sesión.");
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onSessionExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onSessionExpired);
  }, []);

  if (!session) {
    return (
      <LoginForm
        onLoggedIn={() => {
          setSessionExpiredMessage(null);
          setSession(getSession());
        }}
        initialError={sessionExpiredMessage}
      />
    );
  }

  // El repartidor no arma instancias ni edita catálogo/cobertura — su trabajo es
  // ver su ruta asignada y marcar entregas, en un layout pensado para el celular
  // en la calle, no el sidebar+mapa de escritorio del dueño/operario.
  if (session.role === "repartidor") {
    return (
      <Suspense fallback={<div className="map-loading">Cargando…</div>}>
        <RepartidorView onLogout={handleLogout} />
      </Suspense>
    );
  }

  return (
    <Suspense fallback={<div className="map-loading">Cargando…</div>}>
      <div className="app-shell">
      <header className="app-header">
        <h1>VRP Solver</h1>
        <div className="app-header-actions">
          {(instance || solution) && !showTeamManagement && (
            <button type="button" className="btn-reset" onClick={handleReset}>
              Limpiar instancia
            </button>
          )}
          <button type="button" className="btn-reset" onClick={() => setShowTeamManagement((v) => !v)}>
            {showTeamManagement ? "Volver a rutas" : "Gestionar equipo"}
          </button>
          <button type="button" className="btn-reset" onClick={handleLogout}>
            Cerrar sesión
          </button>
          <HealthBadge />
        </div>
      </header>

      {showTeamManagement ? (
        <div className="app-body">
          <TeamManagement onClose={() => setShowTeamManagement(false)} currentUserRole={session.role} />
        </div>
      ) : (
        <div className="app-body">
          <aside className="app-sidebar">
            <CoverageZoneEditor
              editing={editingCoverage}
              hasZone={coveragePoints.length >= 3}
              pointCount={coveragePoints.length}
              onStart={() => setEditingCoverage(true)}
              onClose={handleCloseCoveragePolygon}
              onRedraw={() => setConfirmingCoverageDelete(true)}
            />
            {coverageSyncError && (
              <p className="error-message" role="alert">
                {coverageSyncError}
              </p>
            )}

            <InstanceForm onSubmit={handleSubmit} isSolving={solveMutation.isPending} coveragePoints={coveragePoints} />

            {solveMutation.isError && (
              <p className="error-message" role="alert">
                {(solveMutation.error as Error).message}
              </p>
            )}

            {persistWarning && (
              <p className="error-message" role="alert">
                {persistWarning}
              </p>
            )}

            {solution && (
              <SolutionSummary
                solution={solution}
                instance={instance}
                contacts={contacts}
                onSolvedInstanceChange={(newSolution) => {
                  // Sin esto, "Resolver ahora" (SolutionSummary) actualizaba
                  // la solución en el backend pero el panel de asignación,
                  // exportación y estados de entrega seguía apuntando a la
                  // instancia ORIGINAL — instance/contacts no aplican acá
                  // (son coordenadas de OTRA instancia), así que se limpian
                  // en vez de dejarlos desincronizados con la nueva solución.
                  setSolution(newSolution);
                  setInstance(null);
                  setContacts(null);
                  writeStored(SOLUTION_STORAGE_KEY, newSolution);
                  clearStored(INSTANCE_STORAGE_KEY);
                  clearStored(CONTACTS_STORAGE_KEY);
                }}
                onInstanceDeleted={() => {
                  setSolution(null);
                  setInstance(null);
                  setContacts(null);
                  clearStored(SOLUTION_STORAGE_KEY);
                  clearStored(INSTANCE_STORAGE_KEY);
                  clearStored(CONTACTS_STORAGE_KEY);
                }}
              />
            )}
          </aside>

          <main className="app-main">
            <ErrorBoundary label="el mapa">
              <Suspense fallback={<div className="map-loading">Cargando mapa…</div>}>
                <RouteMap
                  instance={instance}
                  solution={solution}
                  editingCoverage={editingCoverage}
                  coveragePoints={coveragePoints}
                  onPolygonChange={setCoveragePoints}
                />
              </Suspense>
            </ErrorBoundary>
          </main>
        </div>
      )}

      <ConfirmDialog
        open={confirmingCoverageDelete}
        title="Borrar zona de cobertura"
        message="¿Seguro que querés borrar la zona de cobertura guardada? Los clientes que estaban excluidos por estar fuera de zona pasan a incluirse en el próximo cálculo. Esta acción no se puede deshacer."
        onCancel={() => setConfirmingCoverageDelete(false)}
        onConfirm={handleDeleteCoverage}
      />

      <ConfirmDialog
        open={overwriteConfirm !== null}
        title="Sobreescribir instancia existente"
        message={
          overwriteConfirm
            ? `Ya existe una solución guardada para "${overwriteConfirm.request.instancia_id}". Si continuás, se reemplaza — se pierde la ruta, los estados de entrega y las asignaciones de repartidor ya cargadas para esa instancia. ¿Continuar?`
            : ""
        }
        onCancel={() => setOverwriteConfirm(null)}
        onConfirm={() => {
          if (overwriteConfirm) runSolve(overwriteConfirm.request, overwriteConfirm.clients);
          setOverwriteConfirm(null);
        }}
      />
    </div>
    </Suspense>
  );
}

export default App;
