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

// Devuelve si la sesión efectivamente quedó persistida — si localStorage
// está bloqueado (Safari privado) o sin cuota, el login "funciona" en
// memoria pero desaparece en el próximo reload sin ningún aviso, dejando al
// usuario deslogueado de golpe más tarde sin entender por qué.
export function saveSession(session: AuthSession): boolean {
  return writeStored(TOKEN_KEY, session);
}

export function clearSession(): void {
  clearStored(TOKEN_KEY);
}
