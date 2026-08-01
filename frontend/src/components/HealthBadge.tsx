import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export function HealthBadge() {
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    retry: false,
    refetchInterval: 30_000,
  });

  const status = isError ? "unavailable" : data?.status ?? "checking";

  // Bug real (Ronda 7, ciclo nuevo, dueño): /health ya distingue qué base
  // específica está caída (postgresql/mongodb por separado), pero el badge
  // solo mostraba "API degradada" genérico — el dueño no podía saber si
  // podía seguir resolviendo rutas (Postgres) o solo le fallaba el guardado
  // de soluciones (Mongo), sin ir a mirar logs del servidor.
  const degradedDetail =
    status === "degraded" && data
      ? data.postgresql === "unavailable" && data.mongodb === "unavailable"
        ? " — bases de datos no disponibles"
        : data.postgresql === "unavailable"
          ? " — base de datos de instancias no disponible"
          : " — base de datos de soluciones no disponible"
      : "";

  return (
    <div className={`health-badge health-badge--${status}`}>
      <span className="health-dot" aria-hidden="true" />
      {status === "ok" && "API conectada"}
      {status === "degraded" && `API degradada${degradedDetail}`}
      {status === "unavailable" && "API no disponible"}
      {status === "checking" && "Verificando…"}
    </div>
  );
}
