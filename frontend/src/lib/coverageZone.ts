import type { CoveragePolygon } from "./types";
import { api } from "./api";

export function loadCoverageZone(): Promise<CoveragePolygon | null> {
  return api.getCoverageZone();
}

export function saveCoverageZone(polygon: CoveragePolygon): Promise<CoveragePolygon> {
  return api.setCoverageZone(polygon);
}

export function clearCoverageZone(): Promise<void> {
  return api.deleteCoverageZone();
}
