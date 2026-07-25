import { useState } from "react";
import { api } from "../lib/api";
import { saveSession } from "../lib/auth";

interface Props {
  onLoggedIn: () => void;
}

export function LoginForm({ onLoggedIn }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [accountName, setAccountName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const token =
        mode === "login"
          ? await api.login({ email, password })
          : await api.register({ account_name: accountName, email, password, full_name: fullName || undefined });
      saveSession({ accessToken: token.access_token, role: token.role, accountId: token.account_id });
      onLoggedIn();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-shell">
      <form className="instance-form login-form" onSubmit={handleSubmit}>
        <h2>{mode === "login" ? "Iniciar sesión" : "Crear cuenta"}</h2>

        {mode === "register" && (
          <div className="field-group">
            <label htmlFor="account-name">Nombre de la empresa</label>
            <input id="account-name" value={accountName} onChange={(e) => setAccountName(e.target.value)} required />
          </div>
        )}

        <div className="field-group">
          <label htmlFor="login-email">Email</label>
          <input id="login-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>

        {mode === "register" && (
          <div className="field-group">
            <label htmlFor="full-name">Nombre completo (opcional)</label>
            <input id="full-name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
        )}

        <div className="field-group">
          <label htmlFor="login-password">Contraseña</label>
          <input
            id="login-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Un momento…" : mode === "login" ? "Entrar" : "Crear cuenta"}
        </button>

        <button
          type="button"
          className="btn-tertiary"
          onClick={() => {
            setError(null);
            setMode((m) => (m === "login" ? "register" : "login"));
          }}
        >
          {mode === "login" ? "¿Primera vez? Crear cuenta de empresa" : "Ya tengo cuenta, iniciar sesión"}
        </button>
      </form>
    </div>
  );
}
