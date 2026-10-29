import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { Empty, ErrorText } from "../components/ui";

type Rec = Record<string, any>;

export function RubricsPage() {
  const [rows, setRows] = useState<Rec[]>([]);
  const [works, setWorks] = useState<Rec[]>([]);
  const [tasks, setTasks] = useState<Rec[]>([]);
  const [workId, setWorkId] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({ name: "", code: "", description: "" });

  function load() {
    api<Rec[]>("/api/rubrics").then(setRows);
    api<{ items: Rec[] }>("/api/works?page_size=100").then((data) => setWorks(data.items));
    api<Rec[]>(`/api/tasks${workId ? `?work_id=${workId}` : ""}`).then(setTasks);
  }
  useEffect(load, [workId]);

  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/api/rubrics", { method: "POST", body: JSON.stringify(form) });
      setForm({ name: "", code: "", description: "" });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear el rubro.");
    }
  }

  return (
    <section>
      <div className="page-head"><div><h1>Rubros y tareas</h1><p>Los rubros son un catálogo compartido. Las tareas y sus coeficientes pertenecen a cada obra.</p></div></div>
      {error ? <ErrorText error={error} /> : null}
      <form className="panel form-grid" onSubmit={create}>
        <div className="field"><label htmlFor="rn">Nombre</label><input id="rn" required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></div>
        <div className="field"><label htmlFor="rc">Código</label><input id="rc" required value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} /></div>
        <div className="field span-2"><label htmlFor="rd">Descripción</label><input id="rd" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
        <div><button className="btn" type="submit">Crear rubro</button></div>
      </form>
      <div className="grid grid-2" style={{ marginTop: 14 }}>
        <div className="panel">
          <h2>Rubros</h2>
          {rows.length === 0 ? <Empty title="Sin rubros" text="Creá los rubros que usa Conkreto. No hay una lista cerrada." /> : (
            <ul>{rows.map((row) => <li key={row.id}>{row.code} — {row.name}{row.is_active ? "" : " (inactivo)"}</li>)}</ul>
          )}
        </div>
        <div className="panel">
          <h2>Tareas</h2>
          <select aria-label="Filtrar por obra" value={workId} onChange={(event) => setWorkId(event.target.value)}>
            <option value="">Todas las obras</option>
            {works.map((work) => <option key={work.id} value={work.id}>{work.name}</option>)}
          </select>
          {tasks.length === 0 ? <p className="hint">No hay tareas para ese filtro.</p> : (
            <table>
              <thead><tr><th>Tarea</th><th>Rubro</th><th>Ejecutado</th></tr></thead>
              <tbody>{tasks.map((task) => <tr key={task.id}><td>{task.name}</td><td>{task.rubric_name}</td><td>{task.executed_qty} {task.unit_code}</td></tr>)}</tbody>
            </table>
          )}
        </div>
      </div>
    </section>
  );
}
