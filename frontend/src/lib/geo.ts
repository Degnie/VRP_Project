import { point, polygon } from "@turf/helpers";
import booleanPointInPolygon from "@turf/boolean-point-in-polygon";
import type { CoveragePolygon } from "./types";

/**
 * true si [lon, lat] cae dentro del polígono de cobertura guardado.
 * Un polígono con menos de 3 vértices no delimita nada (sin cobertura
 * configurada aún) — todo se considera dentro por defecto.
 */
export function isWithinCoverage(coord: [number, number], zone: CoveragePolygon | null): boolean {
  if (!zone || zone.points.length < 3) return true;

  const ring = [...zone.points, zone.points[0]]; // turf exige anillo cerrado
  return booleanPointInPolygon(point(coord), polygon([ring]));
}
