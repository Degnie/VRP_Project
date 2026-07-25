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

  return (
    <div className={`health-badge health-badge--${status}`}>
      <span className="health-dot" aria-hidden="true" />
      {status === "ok" && "API conectada"}
      {status === "degraded" && "API degradada"}
      {status === "unavailable" && "API no disponible"}
      {status === "checking" && "Verificando…"}
    </div>
  );
}
