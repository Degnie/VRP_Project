import type { RouteEta, RouteResult } from "./types";

function haversineMeters(a: [number, number], b: [number, number]): number {
  const R = 6371000;
  const [lon1, lat1] = a;
  const [lon2, lat2] = b;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

function cumulativeDistances(geometry: [number, number][]): number[] {
  const acc = [0];
  for (let i = 1; i < geometry.length; i++) {
    acc.push(acc[i - 1] + haversineMeters(geometry[i - 1], geometry[i]));
  }
  return acc;
}

function formatHHMM(minutesFromMidnight: number): string {
  const h = Math.floor(minutesFromMidnight / 60) % 24;
  const m = Math.round(minutesFromMidnight % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function parseTimeToMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

export interface RouteEtaInput {
  route: RouteResult;
  geometry: [number, number][]; // geometría real de calle (OSRM), depósito -> clientes -> depósito
  waypointCoords: [number, number][]; // coords de cada waypoint en el mismo orden que route.sequence + depot al inicio/fin
  durationSeconds: number;
}

/**
 * ETA estimado por parada, prorrateando la duración TOTAL de la ruta por
 * distancia acumulada de la geometría hasta cada waypoint (asume velocidad
 * constante en todo el trayecto — aproximación, no una predicción de tráfico
 * real). El "earliest"/"latest" es la misma estimación puntual +/- un colchón
 * heurístico (10% de la duración acumulada hasta esa parada, mínimo 5 min):
 * no es un intervalo estadístico, es una banda de seguridad declarada así al
 * usuario, para comunicar al cliente un rango en vez de una hora exacta.
 */
export function estimateRouteEtas(
  inputs: RouteEtaInput[],
  departureTime: string,
  serviceMinutes: number
): RouteEta[] {
  const departureMinutes = parseTimeToMinutes(departureTime);

  return inputs.map(({ route, geometry, waypointCoords, durationSeconds }) => {
    const geomDistances = cumulativeDistances(geometry);
    const totalGeomDistance = geomDistances[geomDistances.length - 1] || 1;

    // Para cada waypoint (excluyendo depósito inicial), encontrar el punto de
    // la geometría más cercano y usar su distancia acumulada para prorratear.
    const stops = waypointCoords.slice(1, -1).map((wp, i) => {
      let closestIdx = 0;
      let closestDist = Infinity;
      geometry.forEach((g, gi) => {
        const d = haversineMeters(g, wp);
        if (d < closestDist) {
          closestDist = d;
          closestIdx = gi;
        }
      });
      const fractionOfRoute = geomDistances[closestIdx] / totalGeomDistance;
      const travelMinutes = (durationSeconds / 60) * fractionOfRoute;
      const serviceOffsetMinutes = i * (serviceMinutes / 60); // acumulado de paradas previas, aproximado
      const arrivalMinutes = departureMinutes + travelMinutes + serviceOffsetMinutes;

      const cushion = Math.max(5, arrivalMinutes * 0.1 - departureMinutes * 0.1);
      return {
        clientIndex: route.sequence[i],
        arrivalEarliest: formatHHMM(arrivalMinutes - cushion / 2),
        arrivalLatest: formatHHMM(arrivalMinutes + cushion / 2),
      };
    });

    return { vehicle_id: route.vehicle_id, stops };
  });
}
