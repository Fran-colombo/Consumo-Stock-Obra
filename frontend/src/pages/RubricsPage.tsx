import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useNotice } from "../components/ui";
import { formatQty, labelOf } from "../lib/format";

type Rec = Record<string, any>;

const REASONS = [
  ["FALTAN_MATERIALES", "Faltan materiales"],
  ["OTRAS_PRIORIDADES", "Hay otras prioridades"],
  ["HAY_QUE_HACER_ANTES", "Hay que hacer algo antes"],
];

export function RubricsPage() {
  const notice = useNotice();
  const [rows, setRows] = useState<Rec[]>([]);
  const [units, setUnits] = useState<Rec[]>([]);
  const [materials, setMaterials] = useState<Rec[]>([]);
  const [works, setWorks] = useState<Rec[]>([]);
  const [tasks, setTasks] = useState<Rec[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState({ name: "", code: "" });
  const [line, setLine] = useState({ material_id: "", coefficient: "" });
  const [job, setJob] = useState({ work_id: "", quantity: "", pending_reason: "FALTAN_MATERIALES" });

  const selected = rows.find((row) => row.id === selectedId) || null;

  function loadRubrics(keepId?: number | null) {
    api<Rec[]>("/api/rubrics").then((data) => {
      setRows(data);
      setSelectedId((current) => keepId ?? current ?? data[0]?.id ?? null);
    });
  }

  useEffect(() => {
    loadRubrics();
    api<Rec[]>("/api/units").then(setUnits);
    api<{ items: Rec[] }>("/api/materials?page_size=100").then((data) => setMaterials(data.items));
    api<{ items: Rec[] }>("/api/works?page_size=100").then((data) => setWorks(data.items));
  }, []);

  useEffect(() => {
    if (!selectedId) { setTasks([]); return; }
    api<Rec[]>(`/api/tasks?rubric_id=${selectedId}`).then(setTasks);
  }, [selectedId]);

  async function createRubric(event: FormEvent) {
    event.preventDefault();
    try {
      const created = await api<Rec>("/api/rubrics", { method: "POST", body: JSON.stringify({ ...form, description: null }) });
      setForm({ name: "", code: "" });
      loadRubrics(created.id);
      notice.ok(`Quedó el rubro ${created.name}. Ahora cargá qué materiales usa.`);
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo crear el rubro.");
    }
  }

  async function saveUnit(unitId: string) {
    if (!selected) return;
    try {
      const updated = await api<Rec>(`/api/rubrics/${selected.id}`, {
        method: "PATCH",
        body: JSON.stringify({ coverage_unit_id: Number(unitId) }),
      });
      setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      notice.ok(`${updated.name} se mide en ${updated.coverage_unit_name}.`);
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo guardar la unidad.");
    }
  }

  async function addLine(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    try {
      const updated = await api<Rec>(`/api/rubrics/${selected.id}/recipe`, {
        method: "POST",
        body: JSON.stringify({ material_id: Number(line.material_id), coefficient: line.coefficient }),
      });
      setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      setLine({ material_id: "", coefficient: "" });
      notice.ok("La receta quedó guardada. No hace falta volver a cargarla en cada tarea.");
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo guardar la receta.");
    }
  }

  async function addTask(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    try {
      const task = await api<Rec>(`/api/rubrics/${selected.id}/tasks`, {
        method: "POST",
        body: JSON.stringify({
          work_id: Number(job.work_id),
          quantity: job.quantity,
          pending_reason: job.pending_reason,
        }),
      });
      setJob({ work_id: "", quantity: "", pending_reason: "FALTAN_MATERIALES" });
      const next = await api<Rec[]>(`/api/tasks?rubric_id=${selected.id}`);
      setTasks(next);
      const needs = (selected.recipe || []).map((item: Rec) => `${formatQty(Number(job.quantity) * Number(item.coefficient))} ${item.unit_name} de ${item.material_name}`);
      notice.ok(needs.length ? `${task.work_name} quedó pendiente. Hace falta ${needs.join(", ")}.` : "La tarea quedó pendiente.");
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo crear la tarea.");
    }
  }

  return (
    <section>
      {notice.dialog}
      <div className="page-head">
        <div>
          <h1>Rubros y tareas</h1>
          <p>La mezcla se carga una vez. Después solo decís la obra y cuánto hay que cubrir.</p>
        </div>
      </div>
      <div className="grid grid-2">
        <div className="panel">
          <h2>Rubros</h2>
          <form onSubmit={createRubric} className="form-grid">
            <div className="field"><label htmlFor="rn">Nombre</label><input id="rn" required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></div>
            <div className="field"><label htmlFor="rc">Código</label><input id="rc" required value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} /></div>
            <div className="span-2"><button className="action" type="submit">Crear rubro</button></div>
          </form>
          <div className="choice" style={{ marginTop: 14 }}>
            {rows.map((row) => (
              <button key={row.id} type="button" className={row.id === selectedId ? "active" : ""} onClick={() => setSelectedId(row.id)}>
                <strong>{row.name}</strong>
                <div className="hint">{row.code}{row.recipe?.length ? ` · ${row.recipe.length} materiales` : " · sin receta"}</div>
              </button>
            ))}
          </div>
        </div>
        {selected ? (
          <div className="panel">
            <h2>{selected.name}</h2>
            <div className="field">
              <label htmlFor="unit">Se mide en</label>
              <select id="unit" value={selected.coverage_unit_id || ""} onChange={(event) => saveUnit(event.target.value)}>
                <option value="">Elegir</option>
                {units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
              </select>
              <span className="hint">Por ejemplo metros cuadrados o cúbicos. Es la medida de lo que hay que cubrir.</span>
            </div>
            <h3>Qué usa, por cada uno</h3>
            {selected.recipe?.length ? (
              <ul>{selected.recipe.map((item: Rec) => <li key={item.id}>{formatQty(item.coefficient)} {item.unit_name} de {item.material_name}</li>)}</ul>
            ) : <p className="hint">Todavía no tiene materiales.</p>}
            <form className="form-grid" onSubmit={addLine}>
              <div className="field"><label>Material</label>
                <select required value={line.material_id} onChange={(event) => setLine({ ...line, material_id: event.target.value })}>
                  <option value="">Elegir</option>
                  {materials.filter((row) => row.is_active).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                </select>
              </div>
              <div className="field"><label>Cuánto por cada unidad</label><input required value={line.coefficient} onChange={(event) => setLine({ ...line, coefficient: event.target.value })} /></div>
              <div className="span-2"><button className="action secondary" type="submit">Guardar en la receta</button></div>
            </form>
            <h3>Tareas</h3>
            {tasks.length === 0 ? <p className="hint">Este rubro todavía no tiene tareas.</p> : tasks.map((task) => (
              <article key={task.id} style={{ marginBottom: 12 }}>
                <strong>{task.work_name}</strong>
                <p className="hint">{formatQty(task.planned_qty)} {task.unit_code} · {labelOf(task.pending_reason)}</p>
                <ul>
                  {(selected.recipe || []).map((item: Rec) => (
                    <li key={item.id}>{formatQty(Number(task.planned_qty) * Number(item.coefficient))} {item.unit_name} de {item.material_name}</li>
                  ))}
                </ul>
              </article>
            ))}
            <form className="form-grid" onSubmit={addTask}>
              <div className="field"><label>Obra</label>
                <select required value={job.work_id} onChange={(event) => setJob({ ...job, work_id: event.target.value })}>
                  <option value="">Elegir</option>
                  {works.map((work) => <option key={work.id} value={work.id}>{work.name}</option>)}
                </select>
              </div>
              <div className="field"><label>Cuánto hay que cubrir</label><input required value={job.quantity} onChange={(event) => setJob({ ...job, quantity: event.target.value })} /></div>
              <div className="field span-2"><label>Por qué queda pendiente</label>
                <select value={job.pending_reason} onChange={(event) => setJob({ ...job, pending_reason: event.target.value })}>
                  {REASONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </div>
              <div className="span-2"><button className="action" type="submit">Crear tarea</button></div>
            </form>
          </div>
        ) : <div className="panel"><p className="hint">Creá el primer rubro.</p></div>}
      </div>
    </section>
  );
}
