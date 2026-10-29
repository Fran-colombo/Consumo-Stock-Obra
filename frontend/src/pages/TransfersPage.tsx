import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Badge, Empty, ErrorText } from "../components/ui";
import { formatQty } from "../lib/format";

type Rec = Record<string, any>;

export function TransfersPage() {
  const { user } = useAuth();
  const [rows, setRows] = useState<Rec[]>([]);
  const [locations, setLocations] = useState<Rec[]>([]);
  const [materials, setMaterials] = useState<Rec[]>([]);
  const [users, setUsers] = useState<Rec[]>([]);
  const [stock, setStock] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    from_location_id: "",
    to_location_id: "",
    material_id: "",
    quantity: "",
    notes: "",
    authorized_by_user_id: "",
    authorized_operational_name: "",
  });

  function load() {
    api<{ items: Rec[] }>("/api/transfers?page_size=100").then((data) => setRows(data.items));
    api<Rec[]>("/api/locations").then(setLocations);
    api<{ items: Rec[] }>("/api/materials?page_size=100").then((data) => setMaterials(data.items));
    api<Rec[]>("/api/users").then(setUsers);
  }
  useEffect(load, []);
  useEffect(() => {
    if (!form.from_location_id || !form.material_id) { setStock(null); return; }
    api<Rec>(`/api/stock/available?material_id=${form.material_id}&location_id=${form.from_location_id}`).then((row) => setStock(row.on_hand));
  }, [form.from_location_id, form.material_id]);

  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/api/transfers", {
        method: "POST",
        body: JSON.stringify({
          from_location_id: Number(form.from_location_id),
          to_location_id: Number(form.to_location_id),
          notes: form.notes || null,
          authorized_by_user_id: form.authorized_by_user_id ? Number(form.authorized_by_user_id) : null,
          authorized_operational_name: form.authorized_operational_name || null,
          items: [{ material_id: Number(form.material_id), quantity: form.quantity }],
        }),
      });
      setForm({ from_location_id: "", to_location_id: "", material_id: "", quantity: "", notes: "", authorized_by_user_id: "", authorized_operational_name: "" });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear el traslado.");
    }
  }

  const exceeds = stock !== null && form.quantity !== "" && Number(form.quantity) > Number(stock);
  return (
    <section>
      <div className="page-head"><div><h1>Transferencias</h1><p>Registrar no mueve stock. El origen se descuenta al despachar y el destino suma al recibir.</p></div></div>
      {error ? <ErrorText error={error} /> : null}
      <form className="panel form-grid" onSubmit={create}>
        <div className="field"><label>Origen</label>
          <select required value={form.from_location_id} onChange={(event) => setForm({ ...form, from_location_id: event.target.value })}>
            <option value="">Elegir</option>
            {locations.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Destino</label>
          <select required value={form.to_location_id} onChange={(event) => setForm({ ...form, to_location_id: event.target.value })}>
            <option value="">Elegir</option>
            {locations.filter((row) => String(row.id) !== form.from_location_id).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Material</label>
          <select required value={form.material_id} onChange={(event) => setForm({ ...form, material_id: event.target.value })}>
            <option value="">Elegir</option>
            {materials.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Cantidad</label><input required value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></div>
        <div className="field"><label>Quién autoriza (usuario)</label>
          <select value={form.authorized_by_user_id} onChange={(event) => setForm({ ...form, authorized_by_user_id: event.target.value })}>
            <option value="">Sin usuario</option>
            {users.map((row) => <option key={row.id} value={row.id}>{row.full_name}</option>)}
          </select>
        </div>
        <div className="field"><label>Nombre operativo, si no tiene usuario</label><input value={form.authorized_operational_name} onChange={(event) => setForm({ ...form, authorized_operational_name: event.target.value })} /></div>
        <p className="span-2 hint">Disponible en origen: {stock === null ? "elegí origen y material" : formatQty(stock)}. {exceeds ? "Al despachar no va a alcanzar el stock." : ""} Registra {user?.full_name}.</p>
        <div className="span-2"><button className="btn" type="submit">Registrar traslado</button></div>
      </form>
      <div className="panel" style={{ marginTop: 14 }}>
        {rows.length === 0 ? <Empty title="Sin transferencias" text="Creá el galpón en Configuración si todavía no existe, y después registrá el traslado." /> : (
          <table>
            <thead><tr><th>Número</th><th>Origen</th><th>Destino</th><th>Estado</th><th>Registró</th><th></th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.number}</td>
                  <td>{row.from_location_name}</td>
                  <td>{row.to_location_name}</td>
                  <td><Badge value={row.status} /></td>
                  <td>{row.created_by}</td>
                  <td><Link to={`/transferencias/${row.id}`}>Abrir</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
