import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { AdminFix, Badge, Empty, ErrorText } from "../components/ui";
import { formatDate, formatQty, newKey } from "../lib/format";

type Rec = Record<string, any>;

export function ConsumptionsPage() {
  const { user } = useAuth();
  const [works, setWorks] = useState<Rec[]>([]);
  const [tasks, setTasks] = useState<Rec[]>([]);
  const [materials, setMaterials] = useState<Rec[]>([]);
  const [locations, setLocations] = useState<Rec[]>([]);
  const [rows, setRows] = useState<Rec[]>([]);
  const [available, setAvailable] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [workId, setWorkId] = useState("");
  const [form, setForm] = useState({ work_id: "", task_id: "", location_id: "", material_id: "", quantity: "", notes: "" });

  function load() {
    api<{ items: Rec[] }>("/api/works?page_size=100").then((data) => setWorks(data.items));
    api<{ items: Rec[] }>("/api/materials?page_size=100").then((data) => setMaterials(data.items));
    api<Rec[]>("/api/locations").then(setLocations);
    const params = new URLSearchParams({ page_size: "50" });
    if (workId) params.set("work_id", workId);
    api<{ items: Rec[] }>(`/api/consumptions?${params}`).then((data) => setRows(data.items));
  }
  useEffect(load, [workId]);
  useEffect(() => {
    if (!form.work_id) { setTasks([]); return; }
    api<Rec[]>(`/api/tasks?work_id=${form.work_id}`).then(setTasks);
    api<Rec>(`/api/works/${form.work_id}`).then((work) => {
      if (work.location_id) setForm((current) => ({ ...current, location_id: String(work.location_id) }));
    });
  }, [form.work_id]);
  useEffect(() => {
    if (!form.material_id || !form.location_id) { setAvailable(null); return; }
    api<Rec>(`/api/stock/available?material_id=${form.material_id}&location_id=${form.location_id}`).then((row) => setAvailable(row.on_hand));
  }, [form.material_id, form.location_id]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/api/consumptions", {
        method: "POST",
        idempotencyKey: newKey(),
        body: JSON.stringify({
          work_id: Number(form.work_id),
          task_id: Number(form.task_id),
          location_id: Number(form.location_id),
          material_id: Number(form.material_id),
          quantity: form.quantity,
          notes: form.notes || null,
        }),
      });
      setForm({ work_id: "", task_id: "", location_id: "", material_id: "", quantity: "", notes: "" });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo registrar el consumo.");
    }
  }

  async function correct(row: Rec) {
    const quantity = window.prompt("Cantidad a revertir");
    const reason = window.prompt("Motivo de la corrección");
    if (!quantity || !reason) return;
    try {
      await api(`/api/consumptions/${row.id}/corrections`, {
        method: "POST",
        idempotencyKey: newKey(),
        body: JSON.stringify({ quantity, reason }),
      });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo corregir.");
    }
  }

  const exceeds = available !== null && form.quantity !== "" && Number(form.quantity) > Number(available);
  return (
    <section>
      <div className="page-head"><div><h1>Consumos</h1><p>El consumo descuenta el stock de la ubicación elegida y queda ligado a la tarea.</p></div></div>
      {error ? <ErrorText error={error} /> : null}
      <form className="panel form-grid" onSubmit={submit}>
        <div className="field"><label>Obra</label>
          <select required value={form.work_id} onChange={(event) => setForm({ ...form, work_id: event.target.value, task_id: "" })}>
            <option value="">Elegir</option>
            {works.map((work) => <option key={work.id} value={work.id}>{work.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Tarea de esa obra</label>
          <select required value={form.task_id} onChange={(event) => setForm({ ...form, task_id: event.target.value })}>
            <option value="">Elegir</option>
            {tasks.map((task) => <option key={task.id} value={task.id}>{task.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Material</label>
          <select required value={form.material_id} onChange={(event) => setForm({ ...form, material_id: event.target.value })}>
            <option value="">Elegir</option>
            {materials.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Ubicación de stock</label>
          <select required value={form.location_id} onChange={(event) => setForm({ ...form, location_id: event.target.value })}>
            <option value="">Elegir</option>
            {locations.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Cantidad</label><input required value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></div>
        <div className="field"><label>Observaciones</label><input value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></div>
        <p className="span-2 hint">Disponible: {available === null ? "elegí material y ubicación" : formatQty(available)}. {exceeds ? "La cantidad supera las existencias." : ""} El responsable del registro es {user?.full_name}.</p>
        <div className="span-2"><button className="btn" disabled={exceeds} type="submit">Registrar consumo</button></div>
      </form>
      <div className="toolbar"><select aria-label="Filtrar obra" value={workId} onChange={(event) => setWorkId(event.target.value)}><option value="">Todas</option>{works.map((work) => <option key={work.id} value={work.id}>{work.name}</option>)}</select></div>
      <div className="panel table-wrap">
        {rows.length === 0 ? <Empty title="Sin consumos" text="Registrá el uso real de materiales. No se calcula solo con las compras." /> : (
          <table>
            <thead><tr><th>Fecha</th><th>Obra</th><th>Tarea</th><th>Material</th><th>Cantidad</th><th>Ubicación</th><th>Responsable</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{formatDate(row.consumed_at)}</td>
                  <td>{row.work_name}</td>
                  <td>{row.task_name}</td>
                  <td>{row.material_name}</td>
                  <td>{formatQty(row.quantity)} {row.unit_code}</td>
                  <td>{row.location_name}</td>
                  <td>{row.recorded_by}</td>
                  <td><Badge value={row.status} /></td>
                  <td>
                    {row.status === "CONFIRMADO" && !row.corrects_consumption_id ? <button className="btn ghost" type="button" onClick={() => correct(row)}>Corregir con movimiento</button> : null}
                    <AdminFix
                      active={row.status === "CONFIRMADO" && !row.corrects_consumption_id}
                      onSaveQty={(quantity, reason) => api(`/api/consumptions/${row.id}`, { method: "PATCH", body: JSON.stringify({ quantity, reason }) }).then(load)}
                      onVoid={(reason) => api(`/api/consumptions/${row.id}/void`, { method: "POST", body: JSON.stringify({ reason }) }).then(load)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
