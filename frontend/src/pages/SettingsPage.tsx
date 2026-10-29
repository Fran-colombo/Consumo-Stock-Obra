import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorText } from "../components/ui";
import { formatDate } from "../lib/format";

type Rec = Record<string, any>;

export function SettingsPage() {
  const { user } = useAuth();
  const [settings, setSettings] = useState({ allow_negative_stock: false, allow_over_receipt: false });
  const [locations, setLocations] = useState<Rec[]>([]);
  const [units, setUnits] = useState<Rec[]>([]);
  const [audit, setAudit] = useState<Rec[]>([]);
  const [users, setUsers] = useState<Rec[]>([]);
  const [error, setError] = useState("");
  const [location, setLocation] = useState({ name: "", code: "", location_type: "DEPOSITO" });
  const [account, setAccount] = useState({ username: "", full_name: "", password: "", role: "OPERADOR" });

  function load() {
    api<typeof settings>("/api/settings").then(setSettings);
    api<Rec[]>("/api/locations").then(setLocations);
    api<Rec[]>("/api/units").then(setUnits);
    api<{ items: Rec[] }>("/api/audit?page_size=20").then((data) => setAudit(data.items));
    api<Rec[]>("/api/users").then(setUsers);
  }
  useEffect(load, []);

  async function savePolicy(key: "allow_negative_stock" | "allow_over_receipt", value: boolean) {
    try {
      const next = await api<typeof settings>("/api/settings", { method: "PUT", body: JSON.stringify({ [key]: value }) });
      setSettings(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar la política.");
    }
  }

  async function createLocation(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/api/locations", { method: "POST", body: JSON.stringify(location) });
      setLocation({ name: "", code: "", location_type: "DEPOSITO" });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear la ubicación.");
    }
  }

  async function createUser(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/api/users", { method: "POST", body: JSON.stringify(account) });
      setAccount({ username: "", full_name: "", password: "", role: "OPERADOR" });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear el usuario.");
    }
  }

  return (
    <section>
      <div className="page-head"><div><h1>Configuración</h1><p>Unidades, ubicaciones y las dos políticas que cambian la integridad del stock.</p></div></div>
      {error ? <ErrorText error={error} /> : null}
      <div className="grid grid-2">
        <div className="panel">
          <h2>Políticas</h2>
          <p className="hint">Por defecto están desactivadas. Solo el administrador puede cambiarlas.</p>
          <label><input type="checkbox" disabled={user?.role !== "SYSADMIN"} checked={settings.allow_negative_stock} onChange={(event) => savePolicy("allow_negative_stock", event.target.checked)} /> Permitir stock negativo</label>
          <label><input type="checkbox" disabled={user?.role !== "SYSADMIN"} checked={settings.allow_over_receipt} onChange={(event) => savePolicy("allow_over_receipt", event.target.checked)} /> Permitir recibir más de lo pedido</label>
        </div>
        <div className="panel">
          <h2>Unidades</h2>
          <ul>{units.map((unit) => <li key={unit.id}>{unit.name} ({unit.code}), {unit.decimal_places} decimales</li>)}</ul>
        </div>
      </div>
      <form className="panel form-grid" onSubmit={createLocation} style={{ marginTop: 14 }}>
        <h2 className="span-2">Nueva ubicación</h2>
        <div className="field"><label>Nombre</label><input required value={location.name} onChange={(event) => setLocation({ ...location, name: event.target.value })} /></div>
        <div className="field"><label>Código</label><input required value={location.code} onChange={(event) => setLocation({ ...location, code: event.target.value })} /></div>
        <div className="field"><label>Tipo</label>
          <select value={location.location_type} onChange={(event) => setLocation({ ...location, location_type: event.target.value })}>
            <option value="DEPOSITO">Depósito</option>
            <option value="OTRO">Otra</option>
          </select>
        </div>
        <div><button className="btn" type="submit">Crear</button></div>
        <ul className="span-2">{locations.map((row) => <li key={row.id}>{row.name} · {row.location_type}{row.work_name ? ` · ${row.work_name}` : ""}</li>)}</ul>
      </form>
      {user?.role === "SYSADMIN" ? (
        <form className="panel form-grid" onSubmit={createUser} style={{ marginTop: 14 }}>
          <h2 className="span-2">Usuarios</h2>
          <div className="field"><label>Usuario</label><input required value={account.username} onChange={(event) => setAccount({ ...account, username: event.target.value })} /></div>
          <div className="field"><label>Nombre</label><input required value={account.full_name} onChange={(event) => setAccount({ ...account, full_name: event.target.value })} /></div>
          <div className="field"><label>Clave</label><input required type="password" value={account.password} onChange={(event) => setAccount({ ...account, password: event.target.value })} /></div>
          <div className="field"><label>Rol</label>
            <select value={account.role} onChange={(event) => setAccount({ ...account, role: event.target.value })}>
              <option value="OPERADOR">Operador</option>
              <option value="SYSADMIN">Administrador</option>
            </select>
          </div>
          <div className="span-2"><button className="btn" type="submit">Crear usuario</button></div>
          <ul className="span-2">{users.map((row) => <li key={row.id}>{row.full_name} · {row.username} · {row.role}</li>)}</ul>
        </form>
      ) : null}
      <div className="panel" style={{ marginTop: 14 }}>
        <h2>Auditoría</h2>
        <p className="hint">Este registro no se borra. El administrador puede corregir un documento confirmado y el cambio queda acá, con el valor anterior.</p>
        <table>
          <thead><tr><th>Fecha</th><th>Persona</th><th>Acción</th><th>Motivo</th></tr></thead>
          <tbody>
            {audit.map((row) => (
              <tr key={row.id}><td>{formatDate(row.at)}</td><td>{row.user_name}</td><td>{row.action}</td><td>{row.reason || "—"}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
