import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { Badge, Empty, Modal, useNotice } from "../components/ui";

type Work = { id: number; name: string; code: string; address: string | null; status: string; start_date: string | null };

export function WorksPage() {
  const [rows, setRows] = useState<Work[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const notice = useNotice();
  const [form, setForm] = useState({ name: "", code: "", address: "", status: "ACTIVA", start_date: "", notes: "" });

  function load() {
    const params = new URLSearchParams({ page_size: "100" });
    if (q) params.set("q", q);
    if (status) params.set("status", status);
    api<{ items: Work[] }>(`/api/works?${params}`).then((data) => setRows(data.items)).catch(() => setRows([]));
  }
  useEffect(load, [q, status]);

  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/api/works", { method: "POST", body: JSON.stringify({ ...form, start_date: form.start_date || null, address: form.address || null }) });
      setOpen(false);
      setForm({ name: "", code: "", address: "", status: "ACTIVA", start_date: "", notes: "" });
      load();
      notice.ok(`${form.name} quedó creada, con su lugar de stock.`);
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo crear la obra.");
    }
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Obras</h1>
          <p>Cada obra crea su ubicación de stock. El estado no bloquea los movimientos.</p>
        </div>
        <button className="action" type="button" onClick={() => setOpen(true)}>Nueva obra</button>
      </div>
      <div className="toolbar">
        <input className="search" aria-label="Buscar obra" placeholder="Buscar por nombre o código" value={q} onChange={(event) => setQ(event.target.value)} />
        <select className="search" aria-label="Estado" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">Todos los estados</option>
          <option value="PLANIFICADA">Planificada</option>
          <option value="ACTIVA">Activa</option>
          <option value="PAUSADA">Pausada</option>
          <option value="FINALIZADA">Finalizada</option>
          <option value="CANCELADA">Cancelada</option>
        </select>
      </div>
      <div className="panel">
        {rows.length === 0 ? <Empty title="No hay obras" text="Cargá la primera obra para empezar a registrar tareas y materiales." /> : (
          <table>
            <thead><tr><th>Código</th><th>Nombre</th><th>Dirección</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {rows.map((work) => (
                <tr key={work.id}>
                  <td>{work.code}</td>
                  <td>{work.name}</td>
                  <td>{work.address || "—"}</td>
                  <td><Badge value={work.status} /></td>
                  <td><Link to={`/obras/${work.id}`}>Abrir</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {open ? (
        <Modal title="Nueva obra" onClose={() => setOpen(false)}>
          <form onSubmit={create} className="form-grid">
            {notice.dialog}
            <div className="field"><label htmlFor="wn">Nombre</label><input id="wn" required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></div>
            <div className="field"><label htmlFor="wc">Código</label><input id="wc" required value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} /></div>
            <div className="field span-2"><label htmlFor="wa">Dirección</label><input id="wa" value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} /></div>
            <div className="field"><label htmlFor="ws">Estado</label>
              <select id="ws" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
                <option value="PLANIFICADA">Planificada</option>
                <option value="ACTIVA">Activa</option>
                <option value="PAUSADA">Pausada</option>
                <option value="FINALIZADA">Finalizada</option>
                <option value="CANCELADA">Cancelada</option>
              </select>
            </div>
            <div className="field"><label htmlFor="wd">Inicio</label><input id="wd" type="date" value={form.start_date} onChange={(event) => setForm({ ...form, start_date: event.target.value })} /></div>
            <div className="field span-2"><label htmlFor="wnotes">Observaciones</label><textarea id="wnotes" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></div>
            <div className="span-2"><button className="action" type="submit">Crear obra</button></div>
          </form>
        </Modal>
      ) : null}
    </section>
  );
}
