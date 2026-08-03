import { useEffect, useState } from "react";
import type { Role, TeamMember } from "../lib/types";
import { api } from "../lib/api";
import { ConfirmDialog } from "./ConfirmDialog";

const ROLE_LABELS: Record<Role, string> = {
  dueño: "Dueño",
  operario: "Operario",
  repartidor: "Repartidor",
};

interface Props {
  onClose: () => void;
  currentUserRole: Role;
}

const PAGE_SIZE = 50;

export function TeamManagement({ onClose, currentUserRole }: Props) {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);

  useEffect(() => {
    api.me().then((u) => setCurrentUserId(u.id)).catch(() => {});
  }, []);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<Role>("repartidor");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);

  // Bug real (Ronda 2, ciclo 3, dueño): 0.7.7 agregó limit/offset al backend
  // (equipo, catálogo, instancias) porque una cuenta con historial largo no
  // tenía forma de acotar la respuesta — pero ningún caller del frontend lo
  // usaba, así que el fix nunca tenía efecto real. Acá se pagina de a
  // PAGE_SIZE con "cargar más" en vez de traer la tabla entera de una vez.
  const loadTeam = () => {
    setLoading(true);
    api
      .listTeam({ limit: PAGE_SIZE, offset: 0 })
      .then((page) => {
        setMembers(page);
        setHasMore(page.length === PAGE_SIZE);
      })
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  };

  const loadMore = () => {
    setLoadingMore(true);
    api
      .listTeam({ limit: PAGE_SIZE, offset: members.length })
      .then((page) => {
        setMembers((prev) => [...prev, ...page]);
        setHasMore(page.length === PAGE_SIZE);
      })
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoadingMore(false));
  };

  useEffect(loadTeam, []);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteError(null);
    setInviting(true);
    try {
      await api.createUser({ email, password, full_name: fullName || undefined, role });
      setEmail("");
      setPassword("");
      setFullName("");
      setRole("repartidor");
      loadTeam();
    } catch (err) {
      setInviteError((err as Error).message);
    } finally {
      setInviting(false);
    }
  };

  // Bug real (Ronda 5, ciclo 3, dueño — RN-017): desactivar corta el acceso
  // de esa persona de inmediato con un solo click en la fila equivocada, sin
  // el mismo paso de confirmación que ya tienen borrar/sobreescribir
  // instancia — reactivar no tiene ese riesgo, así que solo se confirma al
  // desactivar a alguien activo.
  const [confirmingDeactivate, setConfirmingDeactivate] = useState<TeamMember | null>(null);

  const handleToggleActive = async (member: TeamMember) => {
    setError(null);
    try {
      await api.setUserActive(member.id, !member.active);
      setConfirmingDeactivate(null);
      loadTeam();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleActionClick = (member: TeamMember) => {
    if (member.active) {
      setConfirmingDeactivate(member);
    } else {
      handleToggleActive(member);
    }
  };

  return (
    <div className="team-management">
      <div className="team-management-header">
        <h2 className="section-title">Gestionar equipo</h2>
        <button type="button" className="btn-secondary" onClick={onClose}>
          Volver
        </button>
      </div>

      <form className="instance-form team-invite-form" onSubmit={handleInvite}>
        <h3>Invitar a alguien</h3>
        <div className="field-row">
          <div className="field-group">
            <label htmlFor="invite-email">Email</label>
            <input id="invite-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="field-group">
            <label htmlFor="invite-password">Contraseña inicial</label>
            <input
              id="invite-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
        </div>
        <div className="field-row">
          <div className="field-group">
            <label htmlFor="invite-full-name">Nombre completo (opcional)</label>
            <input id="invite-full-name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div className="field-group">
            <label htmlFor="invite-role">Rol</label>
            <select id="invite-role" value={role} onChange={(e) => setRole(e.target.value as Role)}>
              <option value="repartidor">Repartidor</option>
              <option value="operario">Operario</option>
            </select>
          </div>
        </div>
        {inviteError && (
          <p className="error-message" role="alert">
            {inviteError}
          </p>
        )}
        <button type="submit" className="btn-primary" disabled={inviting}>
          {inviting ? "Invitando…" : "Invitar"}
        </button>
      </form>

      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}

      {loading ? (
        <p className="import-status">Cargando equipo…</p>
      ) : (
        <table className="team-table" role="table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Nombre</th>
              <th>Rol</th>
              <th>Estado</th>
              <th aria-hidden="true"></th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.id} className={m.active ? "" : "team-row--inactive"}>
                <td>{m.email}</td>
                <td>{m.full_name || "—"}</td>
                <td>{ROLE_LABELS[m.role]}</td>
                <td>{m.active ? "Activo" : "Inactivo"}</td>
                <td>
                  {m.id !== currentUserId && (m.role !== "dueño" || currentUserRole === "dueño") && (
                    <button type="button" className="btn-secondary" onClick={() => handleActionClick(m)}>
                      {m.active ? "Desactivar" : "Reactivar"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!loading && hasMore && (
        <button type="button" className="btn-secondary" onClick={loadMore} disabled={loadingMore}>
          {loadingMore ? "Cargando…" : "Cargar más"}
        </button>
      )}

      <ConfirmDialog
        open={confirmingDeactivate !== null}
        title="Desactivar usuario"
        message={`¿Seguro que querés desactivar a "${confirmingDeactivate?.email}"? Pierde acceso a la cuenta de inmediato.`}
        onCancel={() => setConfirmingDeactivate(null)}
        onConfirm={() => confirmingDeactivate && handleToggleActive(confirmingDeactivate)}
      />
    </div>
  );
}
