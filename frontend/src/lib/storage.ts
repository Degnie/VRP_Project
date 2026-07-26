export function readStored<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

// Devuelve si la escritura tuvo éxito — la mayoría de los callers son
// best-effort y lo ignoran, pero algunos (ej. guardar la sesión al loguear)
// necesitan saber si falló para avisar al usuario en vez de seguir como si
// nada, ya que sin localStorage esa sesión desaparece en el próximo reload.
export function writeStored<T>(key: string, value: T): boolean {
  // Sin try/catch, un QuotaExceededError (Safari privado bloquea
  // localStorage por completo, o cuota llena) tira una excepción síncrona
  // no capturada — varios callers escriben en cada keystroke (ej. la nota
  // de un cambio de estado en RepartidorView), así que sin esto el
  // repartidor podía perder la app entera a mitad de tipear en la calle.
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function clearStored(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    // Ídem writeStored: best-effort, no debe tirar la app.
  }
}
