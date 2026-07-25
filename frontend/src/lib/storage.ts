export function readStored<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export function writeStored<T>(key: string, value: T): void {
  localStorage.setItem(key, JSON.stringify(value));
}

export function clearStored(key: string): void {
  localStorage.removeItem(key);
}
