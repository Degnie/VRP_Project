import { readStored, writeStored, clearStored } from "./storage";

const TOKEN_KEY = "vrp:auth-token";

export type Role = "dueño" | "operario" | "repartidor";

export interface AuthSession {
  accessToken: string;
  role: Role;
  accountId: string;
}

// El JWT en sí es el único dato sensible que corresponde guardar en
// localStorage — es exactamente para esto (persistir sesión entre reloads
// sin volver a pedir credenciales), a diferencia del catálogo/cobertura que
// ahora viven en el backend (Etapa 1).
export function getSession(): AuthSession | null {
  return readStored<AuthSession>(TOKEN_KEY);
}

export function saveSession(session: AuthSession): void {
  writeStored(TOKEN_KEY, session);
}

export function clearSession(): void {
  clearStored(TOKEN_KEY);
}
