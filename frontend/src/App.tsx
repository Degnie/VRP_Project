import { lazy, Suspense, useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "./lib/api";
import type { ClientGroup, InstanceRequest, SolutionResponse } from "./lib/types";
import { readStored, writeStored, clearStored } from "./lib/storage";
import { loadCoverageZone, saveCoverageZone, clearCoverageZone } from "./lib/coverageZone";
import { getSession, clearSession, type AuthSession } from "./lib/auth";
import { InstanceForm } from "./components/InstanceForm";
import { SolutionSummary } from "./components/SolutionSummary";
import { HealthBadge } from "./components/HealthBadge";
import { CoverageZoneEditor } from "./components/CoverageZoneEditor";
import { LoginForm } from "./components/LoginForm";
import { RepartidorView } from "./components/RepartidorView";
import "./App.css";

const RouteMap = lazy(() => import("./components/RouteMap").then((m) => ({ default: m.RouteMap })));

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
      writeStored(INSTANCE_STORAGE_KEY, request);
      writeStored(SOLUTION_STORAGE_KEY, data);
      if (pendingContacts) writeStored(CONTACTS_STORAGE_KEY, pendingContacts);
    },
  });

  const handleSubmit = (request: InstanceRequest, clients: ClientGroup[]) => {
    setInstance(request);
    setSolution(null);
    setPendingContacts(clients);
    solveMutation.mutate(request);
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
    if (coveragePoints.length >= 3) saveCoverageZone({ points: coveragePoints }).catch(() => {});
  };

  const handleRedrawCoverage = () => {
    setCoveragePoints([]);
    clearCoverageZone().catch(() => {});
  };

  const handleLogout = () => {
    clearSession();
    setSession(null);
  };

  if (!session) {
    return <LoginForm onLoggedIn={() => setSession(getSession())} />;
  }

  // El repartidor no arma instancias ni edita catálogo/cobertura — su trabajo es
  // ver su ruta asignada y marcar entregas, en un layout pensado para el celular
  // en la calle, no el sidebar+mapa de escritorio del dueño/operario.
  if (session.role === "repartidor") {
    return <RepartidorView onLogout={handleLogout} />;
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>VRP Solver</h1>
        <div className="app-header-actions">
          {(instance || solution) && (
            <button type="button" className="btn-reset" onClick={handleReset}>
              Limpiar instancia
            </button>
          )}
          <button type="button" className="btn-reset" onClick={handleLogout}>
            Cerrar sesión
          </button>
          <HealthBadge />
        </div>
      </header>

      <div className="app-body">
        <aside className="app-sidebar">
          <CoverageZoneEditor
            editing={editingCoverage}
            hasZone={coveragePoints.length >= 3}
            pointCount={coveragePoints.length}
            onStart={() => setEditingCoverage(true)}
            onClose={handleCloseCoveragePolygon}
            onRedraw={handleRedrawCoverage}
          />

          <InstanceForm onSubmit={handleSubmit} isSolving={solveMutation.isPending} coveragePoints={coveragePoints} />

          {solveMutation.isError && (
            <p className="error-message" role="alert">
              {(solveMutation.error as Error).message}
            </p>
          )}

          {solution && <SolutionSummary solution={solution} instance={instance} contacts={contacts} />}
        </aside>

        <main className="app-main">
          <Suspense fallback={<div className="map-loading">Cargando mapa…</div>}>
            <RouteMap
              instance={instance}
              solution={solution}
              editingCoverage={editingCoverage}
              coveragePoints={coveragePoints}
              onPolygonChange={setCoveragePoints}
            />
          </Suspense>
        </main>
      </div>
    </div>
  );
}

export default App;
