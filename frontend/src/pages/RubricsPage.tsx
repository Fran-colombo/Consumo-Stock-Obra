import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useNotice } from "../components/ui";
import { formatQty } from "../lib/format";

type Rec = Record<string, any>;

export function plannedFrom(parameters: Rec[], values: Record<string, string>) {
  const counting = (parameters || []).filter((row) => row.counts);
  if (!counting.length) return { qty: null as number | null, missing: "Agregá un parámetro que entre en la cuenta." };
  const missing = counting.filter((row) => values[row.id] === undefined || values[row.id] === "" || Number(values[row.id]) <= 0);
  if (missing.length) return { qty: null as number | null, missing: `Falta completar ${missing.map((row) => row.name).join(", ")}.` };
  const qty = counting.reduce((total, row) => total * Number(values[row.id]), 1);
  return { qty: Number.isFinite(qty) && qty > 0 ? qty : null, missing: null as string | null };
}

export function describeTask(task: Rec) {
  if (task.parameters?.length) {
    const parts = task.parameters.filter((row: Rec) => row.counts && row.value != null).map((row: Rec) => `${formatQty(row.value)} ${row.unit_code || ""}`.trim());
    const notes = task.parameters.filter((row: Rec) => !row.counts && row.value != null).map((row: Rec) => `${row.name}: ${formatQty(row.value)} ${row.unit_code || ""}`.trim());
    const main = parts.length ? `${parts.join(" × ")} = ${formatQty(task.planned_qty)} ${task.unit_name || task.unit_code || ""}`.trim() : `${formatQty(task.planned_qty)} ${task.unit_name || task.unit_code || ""}`.trim();
    return notes.length ? `${main}. ${notes.join(". ")}` : main;
  }
  if (task.length_m) return `${formatQty(task.length_m)} m × ${formatQty(task.width_m)} m × ${formatQty(task.thickness_m)} m = ${formatQty(task.planned_qty)} m³`;
  return `${formatQty(task.planned_qty)} ${task.unit_code || ""}`.trim();
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
  const [workId, setWorkId] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});

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
    const formula = formulas.find((row) => String(row.id) === formulaId);
    if (!formula) {
      notice.fail("Elegí la fórmula.");
      return;
    }
    const plan = plannedFrom(formula.parameters || [], values);
    if (!formula.measure_unit_id || plan.missing) {
      notice.fail(formula.measure_unit_id ? plan.missing || "Falta completar los parámetros." : "Elegí en qué se mide esta fórmula.");
      return;
    }
    try {
      const task = await api<Rec>(`/api/rubrics/${selected.id}/tasks`, {
        method: "POST",
        body: JSON.stringify({
          work_id: Number(workId),
          formula_id: Number(formulaId),
          parameters: (formula.parameters || []).map((row: Rec) => ({ parameter_id: row.id, value: values[row.id] || null })),
        }),
      });
      setWorkId("");
      setValues({});
      const next = await api<Rec[]>(`/api/tasks?rubric_id=${selected.id}`);
      setTasks(next);
      const needs = (task.needs || []).map((item: Rec) => `${formatQty(item.needed)} ${item.unit_name} de ${item.material_name}`);
      notice.ok(needs.length ? `${task.work_name} quedó pendiente. Son ${formatQty(task.planned_qty)} ${task.unit_name || task.unit_code}. Hace falta ${needs.join(", ")}.` : "La tarea quedó pendiente.");
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
          <p>El rubro ordena el trabajo. La fórmula se elige al crear la tarea, y los parámetros se completan ahí.</p>
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
              <select required value={formulaId} onChange={(event) => { setFormulaId(event.target.value); setValues({}); }}>
                <option value="">Elegir</option>
                {formulas.filter((row) => row.is_active).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
              <span className="hint">Si no está, cargala en Fórmulas para tareas.</span>
            </div>
            <h3>Tareas</h3>
            {tasks.length === 0 ? <p className="hint">Este rubro todavía no tiene tareas.</p> : tasks.map((task) => (
              <article key={task.id} style={{ marginBottom: 12 }}>
                <strong>{task.work_name}</strong> {task.formula_name ? <span className="hint">· {task.formula_name}</span> : null}
                <p className="hint">{describeTask(task)}</p>
                <ul>{(task.needs || []).map((item: Rec) => <li key={item.material_id}>{formatQty(item.needed)} {item.unit_name} de {item.material_name}</li>)}</ul>
              </article>
            ))}
            <TaskMeasures workId={workId} setWorkId={setWorkId} values={values} setValues={setValues} onSubmit={addTask} works={works} formula={formulas.find((row) => String(row.id) === formulaId) || null} />
          </div>
        ) : <div className="panel"><p className="hint">Creá el primer rubro.</p></div>}
      </div>
    </section>
  );
}

export function TaskMeasures({
  workId,
  setWorkId,
  values,
  setValues,
  onSubmit,
  works,
  formula,
  hideWork,
}: {
  workId: string;
  setWorkId: (value: string) => void;
  values: Record<string, string>;
  setValues: (value: Record<string, string>) => void;
  onSubmit: (event: FormEvent) => void;
  works?: Rec[];
  formula: Rec | null;
  hideWork?: boolean;
}) {
  const parameters = formula?.parameters || [];
  const plan = formula?.measure_unit_id ? plannedFrom(parameters, values) : { qty: null, missing: null };
  const margin = Number(formula?.waste_percent || 0);
  const recipe = formula?.lines || [];
  const hint = !formula
    ? "Elegí la fórmula."
    : !formula.measure_unit_id
      ? "Elegí en qué se mide esta fórmula."
      : !parameters.length
        ? "Esta fórmula todavía no tiene parámetros."
        : plan.missing || (plan.qty != null ? `${formatQty(plan.qty)} ${formula.measure_unit_name || ""}.` : "Falta completar los parámetros.");
  return (
    <form className="form-grid" onSubmit={onSubmit}>
      {hideWork ? null : (
        <div className="field"><label>Obra</label>
          <select required value={workId} onChange={(event) => setWorkId(event.target.value)}>
            <option value="">Elegir</option>
            {(works || []).map((work) => <option key={work.id} value={work.id}>{work.name}</option>)}
          </select>
        </div>
      )}
      {parameters.map((row: Rec) => (
        <div className="field" key={row.id}>
          <label>{row.name} ({row.unit_name}){row.counts ? "" : " · no entra en la cuenta"}</label>
          <input value={values[row.id] || ""} onChange={(event) => setValues({ ...values, [row.id]: event.target.value })} />
        </div>
      ))}
      <p className="span-2 hint">{hint}</p>
      {plan.qty != null && recipe.length ? (
        <ul className="span-2">
          {recipe.map((item: Rec) => (
            <li key={item.id}>{formatQty(plan.qty! * Number(item.coefficient) * (1 + margin / 100))} {item.unit_name} de {item.material_name}</li>
          ))}
        </ul>
      ) : null}
      <div className="span-2"><button className="action" type="submit">Crear tarea</button></div>
    </form>
  );
}
