const OSRM_URL = import.meta.env.VITE_OSRM_URL ?? "http://localhost:5000";

interface OsrmRouteResponse {
  code: string;
  routes: {
    geometry: { type: "LineString"; coordinates: [number, number][] };
    duration: number; // segundos, ruta completa
  }[];
}

export interface RouteWithDuration {
  coordinates: [number, number][];
  durationSeconds: number; // 0 si OSRM no respondió (fallback a línea recta sin ETA)
}

/**
 * Geometría real de calle para una secuencia de waypoints (vía OSRM /route).
 * Si OSRM no responde o el código no es "Ok", devuelve la polilínea recta
 * original (waypoints tal cual) para que el mapa siga siendo utilizable.
 */
export async function fetchRouteGeometry(waypoints: [number, number][]): Promise<[number, number][]> {
  if (waypoints.length < 2) return waypoints;

  const coordsParam = waypoints.map(([lon, lat]) => `${lon},${lat}`).join(";");
  const url = `${OSRM_URL}/route/v1/driving/${coordsParam}?overview=full&geometries=geojson`;

  try {
    const res = await fetch(url);
    if (!res.ok) return waypoints;
    const data: OsrmRouteResponse = await res.json();
    if (data.code !== "Ok" || !data.routes[0]) return waypoints;
    return data.routes[0].geometry.coordinates;
  } catch {
    return waypoints;
  }
}

/**
 * Igual que fetchRouteGeometry pero además devuelve la duración total de la
 * ruta (segundos). Función separada para no romper el call-site actual de
 * fetchRouteGeometry en RouteMap.tsx.
 */
export async function fetchRouteWithDuration(waypoints: [number, number][]): Promise<RouteWithDuration> {
  if (waypoints.length < 2) return { coordinates: waypoints, durationSeconds: 0 };

  const coordsParam = waypoints.map(([lon, lat]) => `${lon},${lat}`).join(";");
  const url = `${OSRM_URL}/route/v1/driving/${coordsParam}?overview=full&geometries=geojson`;

  try {
    const res = await fetch(url);
    if (!res.ok) return { coordinates: waypoints, durationSeconds: 0 };
    const data: OsrmRouteResponse = await res.json();
    if (data.code !== "Ok" || !data.routes[0]) return { coordinates: waypoints, durationSeconds: 0 };
    return {
      coordinates: data.routes[0].geometry.coordinates,
      durationSeconds: data.routes[0].duration,
    };
  } catch {
    return { coordinates: waypoints, durationSeconds: 0 };
  }
}
