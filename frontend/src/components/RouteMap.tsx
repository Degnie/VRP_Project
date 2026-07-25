import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { InstanceRequest, SolutionResponse } from "../lib/types";
import { fetchRouteGeometry } from "../lib/osrm";

const ROUTE_COLORS = [
  "#2f6f4f", "#c4622d", "#3a5a9e", "#a3383c", "#7a5c9e", "#2e8b8b", "#b08a1e", "#5c6b73",
];

interface Props {
  instance: InstanceRequest | null;
  solution: SolutionResponse | null;
  editingCoverage?: boolean;
  coveragePoints?: [number, number][];
  onPolygonChange?: (points: [number, number][]) => void;
}

export function RouteMap({ instance, solution, editingCoverage, coveragePoints, onPolygonChange }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const onPolygonChangeRef = useRef(onPolygonChange);
  onPolygonChangeRef.current = onPolygonChange;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let map: maplibregl.Map | null = null;
    try {
      map = new maplibregl.Map({
        container,
        style: {
          version: 8,
          sources: {
            osm: {
              type: "raster",
              tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              attribution: "© OpenStreetMap contributors",
            },
          },
          layers: [
            {
              id: "osm",
              type: "raster",
              source: "osm",
              paint: { "raster-saturation": -0.3, "raster-brightness-max": 0.95 },
            },
          ],
        },
        center: [-77.03, -12.05],
        zoom: 11,
      });
      // MapLibre dispara "error" también por fallos de un solo tile (red
      // intermitente del servidor público de OSM) — esos son transitorios y
      // MapLibre los reintenta solo. Solo tratamos como fatal un error sin
      // fuente asociada (p. ej. fallo de estilo/WebGL), no un tile suelto.
      // sourceId no está en el tipo público de ErrorEvent pero MapLibre lo
      // adjunta a runtime para errores de tile.
      map.on("error", (e) => {
        if ((e as { sourceId?: string }).sourceId) return;
        setMapError(e.error?.message ?? "Error desconocido al cargar el mapa");
      });
      mapRef.current = map;
      setMapError(null);
    } catch (err) {
      setMapError(err instanceof Error ? err.message : "No se pudo inicializar el mapa");
    }

    // MapLibre mide el tamaño del contenedor en el instante de new Map(). Con
    // React.lazy/Suspense el montaje puede correr antes de que el navegador
    // asiente el layout del padre (.app-main), dejando el canvas en 0x0 para
    // siempre. ResizeObserver corrige el tamaño apenas el contenedor lo tenga.
    const resizeObserver = new ResizeObserver(() => map?.resize());
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      map?.remove();
      if (mapRef.current === map) mapRef.current = null;
    };
  }, []);

  // Modo edición de zona de cobertura: cada click agrega un vértice.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !editingCoverage) return;

    const handleClick = (e: maplibregl.MapMouseEvent) => {
      const next = [...(coveragePoints ?? []), [e.lngLat.lng, e.lngLat.lat] as [number, number]];
      onPolygonChangeRef.current?.(next);
    };

    map.on("click", handleClick);
    map.getCanvas().style.cursor = "crosshair";

    return () => {
      map.off("click", handleClick);
      map.getCanvas().style.cursor = "";
    };
  }, [editingCoverage, coveragePoints]);

  // Dibuja el polígono de cobertura (en edición o ya guardado).
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const draw = () => {
      const points = coveragePoints ?? [];
      if (!map.getSource("coverage-polygon")) {
        map.addSource("coverage-polygon", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.addLayer({
          id: "coverage-polygon-fill",
          type: "fill",
          source: "coverage-polygon",
          filter: ["==", "$type", "Polygon"],
          paint: { "fill-color": "#c4622d", "fill-opacity": 0.12 },
        });
        map.addLayer({
          id: "coverage-polygon-line",
          type: "line",
          source: "coverage-polygon",
          paint: { "line-color": "#c4622d", "line-width": 2, "line-dasharray": [2, 1] },
        });
      }

      const features: GeoJSON.Feature[] = [];
      if (points.length >= 3) {
        features.push({
          type: "Feature",
          properties: {},
          geometry: { type: "Polygon", coordinates: [[...points, points[0]]] },
        });
      } else if (points.length >= 2) {
        features.push({
          type: "Feature",
          properties: {},
          geometry: { type: "LineString", coordinates: points },
        });
      }

      (map.getSource("coverage-polygon") as maplibregl.GeoJSONSource | undefined)?.setData({
        type: "FeatureCollection",
        features,
      });
    };

    if (map.isStyleLoaded()) draw();
    else map.once("load", draw);
  }, [coveragePoints]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !instance) return;
    let cancelled = false;

    const ensureLayers = () => {
      if (!map.getSource("depot-point")) {
        map.addSource("depot-point", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
        map.addLayer({
          id: "depot-point",
          type: "circle",
          source: "depot-point",
          paint: {
            "circle-radius": 9,
            "circle-color": "#c4622d",
            "circle-stroke-width": 2,
            "circle-stroke-color": "#faf7f0",
          },
        });
      }
      if (!map.getSource("client-points")) {
        map.addSource("client-points", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
        map.addLayer({
          id: "client-points",
          type: "circle",
          source: "client-points",
          paint: {
            "circle-radius": 5,
            "circle-color": "#2f6f4f",
            "circle-stroke-width": 1.5,
            "circle-stroke-color": "#faf7f0",
          },
        });
      }
      if (!map.getSource("route-lines")) {
        map.addSource("route-lines", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
        map.addLayer({
          id: "route-lines",
          type: "line",
          source: "route-lines",
          paint: {
            "line-color": ["get", "color"],
            "line-width": 3,
            "line-opacity": 0.85,
          },
        });
      }
    };

    const draw = () => {
      if (cancelled) return;
      ensureLayers();

      const clientCoords = instance.coordinates;
      const [depotX, depotY] = instance.depot_coordinates;

      (map.getSource("depot-point") as maplibregl.GeoJSONSource).setData({
        type: "Feature",
        properties: {},
        geometry: { type: "Point", coordinates: [depotX, depotY] },
      });

      (map.getSource("client-points") as maplibregl.GeoJSONSource).setData({
        type: "FeatureCollection",
        features: clientCoords.map(([x, y], i) => ({
          type: "Feature",
          properties: { id: i + 1 },
          geometry: { type: "Point", coordinates: [x, y] },
        })),
      });

      if (solution) {
        const idToCoord = new Map<number, [number, number]>();
        idToCoord.set(0, [depotX, depotY]);
        clientCoords.forEach(([x, y], i) => idToCoord.set(i + 1, [x, y]));

        const waypointsByRoute = solution.routes.map((route) => [
          [depotX, depotY] as [number, number],
          ...route.sequence.map((id): [number, number] => idToCoord.get(id) ?? [depotX, depotY]),
          [depotX, depotY] as [number, number],
        ]);

        // Línea recta de inmediato para no dejar el mapa sin rutas mientras
        // se espera la geometría real de calle.
        const straightFeatures = solution.routes.map((route, i) => ({
          type: "Feature" as const,
          properties: { vehicle_id: route.vehicle_id, color: ROUTE_COLORS[i % ROUTE_COLORS.length] },
          geometry: { type: "LineString" as const, coordinates: waypointsByRoute[i] },
        }));
        (map.getSource("route-lines") as maplibregl.GeoJSONSource).setData({
          type: "FeatureCollection",
          features: straightFeatures,
        });

        // Reemplazar por geometría real de calle (vía OSRM) apenas llegue cada tramo.
        Promise.all(waypointsByRoute.map((wp) => fetchRouteGeometry(wp))).then((geometries) => {
          if (cancelled) return;
          const routedFeatures = solution.routes.map((route, i) => ({
            type: "Feature" as const,
            properties: { vehicle_id: route.vehicle_id, color: ROUTE_COLORS[i % ROUTE_COLORS.length] },
            geometry: { type: "LineString" as const, coordinates: geometries[i] },
          }));
          const source = map.getSource("route-lines") as maplibregl.GeoJSONSource | undefined;
          source?.setData({ type: "FeatureCollection", features: routedFeatures });
        });
      } else {
        (map.getSource("route-lines") as maplibregl.GeoJSONSource).setData({
          type: "FeatureCollection",
          features: [],
        });
      }

      const allCoords = [instance.depot_coordinates, ...clientCoords];
      const bounds = allCoords.reduce(
        (b, [x, y]) => b.extend([x, y]),
        new maplibregl.LngLatBounds(allCoords[0], allCoords[0])
      );
      map.fitBounds(bounds, { padding: 60, maxZoom: 15, duration: 0 });
    };

    if (map.isStyleLoaded()) draw();
    else map.once("load", draw);

    return () => {
      cancelled = true;
    };
  }, [instance, solution]);

  return (
    <div className="route-map-wrap">
      <div ref={containerRef} className="route-map" role="img" aria-label="Mapa de rutas de la instancia VRP" />
      {mapError && (
        <div className="route-map-empty route-map-error" role="alert">
          No se pudo cargar el mapa: {mapError}
        </div>
      )}
      {!mapError && !instance && (
        <div className="route-map-empty" aria-hidden="true">
          Cargá una instancia para ver los clientes y rutas en el mapa
        </div>
      )}
    </div>
  );
}
