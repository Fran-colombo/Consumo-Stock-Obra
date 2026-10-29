import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useNotice } from "../components/ui";
import { formatQty } from "../lib/format";

type Rec = Record<string, any>;

function previewVolume(length: string, width: string, thickness: string) {
  const volume = Number(length) * Number(width) * Number(thickness);
  return Number.isFinite(volume) && volume > 0 ? volume : null;
}

export function RubricsPage() {
  const notice = useNotice();
  const [rows, setRows] = useState<Rec[]>([]);
  const [works, setWorks] = useState<Rec[]>([]);
  const [formulas, setFormulas] = useState<Rec[]>([]);
  const [tasks, setTasks] = useState<Rec[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState({ name: "", code: "" });
  const [formulaId, setFormulaId] = useState("");
  const [job, setJob] = useState({ work_id: "", length_m: "", width_m: "", thickness_m: "" });

  const selected = rows.find((row) => row.id === selectedId) || null;

  function loadRubrics(keepId?: number | null) {
    api<Rec[]>("/api/rubrics").then((data) => {
      setRows(data);
      setSelectedId((current) => keepId ?? current ?? data[0]?.id ?? null);
    });
  }

  useEffect(() => {
    loadRubrics();
    api<Rec[]>("/api/formulas").then(setFormulas);
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
      notice.ok(`Quedó el rubro ${created.name}.`);
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo crear el rubro.");
    }
  }

  async function addTask(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    if (!formulaId) {
      notice.fail("Elegí la fórmula.");
      return;
    }
    try {
      const task = await api<Rec>(`/api/rubrics/${selected.id}/tasks`, {
        method: "POST",
        body: JSON.stringify({
          work_id: Number(job.work_id),
          formula_id: Number(formulaId),
          length_m: job.length_m,
          width_m: job.width_m,
          thickness_m: job.thickness_m,
        }),
      });
      const volume = previewVolume(job.length_m, job.width_m, job.thickness_m);
      setJob({ work_id: "", length_m: "", width_m: "", thickness_m: "" });
      const next = await api<Rec[]>(`/api/tasks?rubric_id=${selected.id}`);
      setTasks(next);
      const needs = (task.needs || []).map((item: Rec) => `${formatQty(item.needed)} ${item.unit_name} de ${item.material_name}`);
      notice.ok(needs.length ? `${task.work_name} quedó pendiente. Son ${formatQty(volume)} m³. Hace falta ${needs.join(", ")}.` : "La tarea quedó pendiente.");
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
          <p>El rubro ordena el trabajo. La fórmula se elige al crear la tarea, y las medidas van en metros.</p>
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
                <div className="hint">{row.code}</div>
              </button>
            ))}
          </div>
        </div>
        {selected ? (
          <div className="panel">
            <h2>{selected.name}</h2>
            <div className="field">
              <label>Fórmula</label>
              <select required value={formulaId} onChange={(event) => setFormulaId(event.target.value)}>
                <option value="">Elegir</option>
                {formulas.filter((row) => row.is_active).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
              <span className="hint">Si no está, cargala en Fórmulas para tareas.</span>
            </div>
            <h3>Tareas</h3>
            {tasks.length === 0 ? <p className="hint">Este rubro todavía no tiene tareas.</p> : tasks.map((task) => (
              <article key={task.id} style={{ marginBottom: 12 }}>
                <strong>{task.work_name}</strong> {task.formula_name ? <span className="hint">· {task.formula_name}</span> : null}
                <p className="hint">{task.length_m ? `${formatQty(task.length_m)} m × ${formatQty(task.width_m)} m × ${formatQty(task.thickness_m)} m = ${formatQty(task.planned_qty)} m³` : `${formatQty(task.planned_qty)} ${task.unit_code || ""}`}</p>
                <ul>{(task.needs || []).map((item: Rec) => <li key={item.material_id}>{formatQty(item.needed)} {item.unit_name} de {item.material_name}</li>)}</ul>
              </article>
            ))}
            <TaskMeasures job={job} setJob={setJob} onSubmit={addTask} works={works} volume={previewVolume(job.length_m, job.width_m, job.thickness_m)} recipe={formulas.find((row) => String(row.id) === formulaId)?.lines || []} waste={formulas.find((row) => String(row.id) === formulaId)?.waste_percent} />
          </div>
        ) : <div className="panel"><p className="hint">Creá el primer rubro.</p></div>}
      </div>
    </section>
  );
}

export function TaskMeasures({
  job,
  setJob,
  onSubmit,
  works,
  volume,
  recipe,
  waste,
  hideWork,
}: {
  job: { work_id: string; length_m: string; width_m: string; thickness_m: string };
  setJob: (value: { work_id: string; length_m: string; width_m: string; thickness_m: string }) => void;
  onSubmit: (event: FormEvent) => void;
  works?: Rec[];
  volume: number | null;
  recipe: Rec[];
  waste?: string | number | null;
  hideWork?: boolean;
}) {
  const margin = Number(waste || 0);
  return (
    <form className="form-grid" onSubmit={onSubmit}>
      {hideWork ? null : (
        <div className="field"><label>Obra</label>
          <select required value={job.work_id} onChange={(event) => setJob({ ...job, work_id: event.target.value })}>
            <option value="">Elegir</option>
            {(works || []).map((work) => <option key={work.id} value={work.id}>{work.name}</option>)}
          </select>
        </div>
      )}
      <div className="field"><label>Largo (m)</label><input required value={job.length_m} onChange={(event) => setJob({ ...job, length_m: event.target.value })} /></div>
      <div className="field"><label>Ancho (m)</label><input required value={job.width_m} onChange={(event) => setJob({ ...job, width_m: event.target.value })} /></div>
      <div className="field"><label>Espesor (m)</label><input required value={job.thickness_m} onChange={(event) => setJob({ ...job, thickness_m: event.target.value })} /></div>
      <p className="span-2 hint">{volume ? `Volumen: ${formatQty(volume)} m³.` : "El volumen es largo por ancho por espesor."}</p>
      {volume && recipe.length ? (
        <ul className="span-2">
          {recipe.map((item) => (
            <li key={item.id}>{formatQty(volume * Number(item.coefficient) * (1 + margin / 100))} {item.unit_name} de {item.material_name}</li>
          ))}
        </ul>
      ) : null}
      <div className="span-2"><button className="action" type="submit">Crear tarea</button></div>
    </form>
  );
}
