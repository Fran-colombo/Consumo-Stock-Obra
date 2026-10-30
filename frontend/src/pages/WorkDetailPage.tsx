import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { AdminFix, Badge, Empty, Modal, useNotice } from "../components/ui";
import { TaskMeasures, describeTask, plannedFrom } from "./RubricsPage";
import { formatDate, formatPercent, formatQty, labelOf, MOVEMENT_LABELS, newKey } from "../lib/format";

type Rec = Record<string, any>;
const TABS = ["Resumen", "Rubros y tareas", "Consumo teórico", "Consumo real", "Stock", "Órdenes", "Transferencias", "Historial"];

export function WorkDetailPage() {
  const { id } = useParams();
  const [tab, setTab] = useState(TABS[0]);
  const [work, setWork] = useState<Rec | null>(null);
  const [tasks, setTasks] = useState<Rec[]>([]);
  const [materials, setMaterials] = useState<Rec[]>([]);
  const [comparison, setComparison] = useState<Rec[]>([]);
  const notice = useNotice();

  function load() {
    if (!id) return;
    api<Rec>(`/api/works/${id}`).then(setWork);
    api<Rec[]>(`/api/tasks?work_id=${id}`).then(setTasks);
    api<{ items: Rec[] }>("/api/materials?page_size=100").then((data) => setMaterials(data.items));
    api<Rec[]>(`/api/comparisons?work_id=${id}`).then(setComparison);
  }
  useEffect(load, [id]);

  if (!work) return <p>Cargando la obra…</p>;

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>{work.name}</h1>
          <p>{work.code} · {work.address || "Sin dirección"} · Ubicación {work.location_name || "sin ubicación"}</p>
        </div>
        <Badge value={work.status} />
      </div>
      {notice.dialog}
      <div className="tabs" role="tablist">
        {TABS.map((item) => (
          <button key={item} type="button" className={tab === item ? "active" : ""} onClick={() => setTab(item)}>{item}</button>
        ))}
      </div>
      {tab === "Resumen" ? <Summary rows={comparison} /> : null}
      {tab === "Rubros y tareas" ? (
        <TasksPanel workId={id || ""} tasks={tasks} onChange={load} onError={notice.fail} onOk={notice.ok} />
      ) : null}
      {tab === "Consumo teórico" ? <Theoretical tasks={tasks} /> : null}
      {tab === "Consumo real" ? <Real work={work} tasks={tasks} materials={materials} onChange={load} onError={notice.fail} /> : null}
      {tab === "Stock" ? <Stock locationId={work.location_id} /> : null}
      {tab === "Órdenes" ? <Orders workId={work.id} /> : null}
      {tab === "Transferencias" ? <Transfers locationId={work.location_id} /> : null}
      {tab === "Historial" ? <History locationId={work.location_id} /> : null}
    </section>
  );
}

function Summary({ rows }: { rows: Rec[] }) {
  if (rows.length === 0) return <div className="panel"><Empty title="Sin comparación todavía" text="Configurá una tarea, registrá el avance y el consumo real para ver la diferencia." /></div>;
  return (
    <div className="panel table-wrap">
      <table>
        <thead><tr><th>Rubro</th><th>Tarea</th><th>Material</th><th>Ejecutado</th><th>Teórico</th><th>Real</th><th>Diferencia</th><th>Desvío</th><th>Stock</th></tr></thead>
        <tbody>
          {rows.map((row) => {
            const diff = Number(row.absolute_difference);
            return (
              <tr key={`${row.task_id}-${row.material_id}`}>
                <td>{row.rubric_name}</td>
                <td>{row.task_name}</td>
                <td>{row.material_name}</td>
                <td>{formatQty(row.executed_qty)}</td>
                <td>{formatQty(row.theoretical_qty)}</td>
                <td>{formatQty(row.real_qty)}</td>
                <td className={diff > 0 ? "up" : diff < 0 ? "down" : "flat"}>{formatQty(row.absolute_difference)}</td>
                <td>{formatPercent(row.percent_deviation, row.percent_status)}{row.review_required ? " · Requiere revisión" : ""}</td>
                <td>{formatQty(row.stock_on_hand)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function TasksPanel({ workId, tasks, onChange, onError, onOk }: { workId: string; tasks: Rec[]; onChange: () => void; onError: (value: string) => void; onOk: (value: string) => void }) {
  const [rubrics, setRubrics] = useState<Rec[]>([]);
  const [formulas, setFormulas] = useState<Rec[]>([]);
  const [rubricId, setRubricId] = useState("");
  const [formulaId, setFormulaId] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  useEffect(() => {
    api<Rec[]>("/api/rubrics").then((data) => setRubrics(data.filter((row) => row.is_active)));
    api<Rec[]>("/api/formulas").then((data) => setFormulas(data.filter((row) => row.is_active)));
  }, [tasks]);
  const formula = formulas.find((row) => String(row.id) === formulaId);

  async function addTask(event: FormEvent) {
    event.preventDefault();
    if (!rubricId || !formula) {
      onError("Elegí el rubro y la fórmula.");
      return;
    }
    const plan = plannedFrom(formula.parameters || [], values);
    if (!formula.measure_unit_id || plan.missing) {
      onError(formula.measure_unit_id ? plan.missing || "Falta completar los parámetros." : "Elegí en qué se mide esta fórmula.");
      return;
    }
    try {
      const task = await api<Rec>(`/api/rubrics/${rubricId}/tasks`, {
        method: "POST",
        body: JSON.stringify({
          work_id: Number(workId),
          formula_id: Number(formulaId),
          parameters: (formula.parameters || []).map((row: Rec) => ({ parameter_id: row.id, value: values[row.id] || null })),
        }),
      });
      setValues({});
      const needs = (task.needs || []).map((item: Rec) => `${formatQty(item.needed)} ${item.unit_name} de ${item.material_name}`);
      onOk(needs.length ? `Quedó pendiente. Son ${formatQty(task.planned_qty)} ${task.unit_name || task.unit_code}. Hace falta ${needs.join(", ")}.` : "La tarea quedó pendiente.");
      onChange();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "No se pudo crear la tarea.");
    }
  }

  return (
    <div className="grid">
      <div className="panel">
        <h2>Nueva tarea</h2>
        <div className="field">
          <label>Rubro</label>
          <select required value={rubricId} onChange={(event) => setRubricId(event.target.value)}>
            <option value="">Elegir</option>
            {rubrics.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Fórmula</label>
          <select required value={formulaId} onChange={(event) => { setFormulaId(event.target.value); setValues({}); }}>
            <option value="">Elegir</option>
            {formulas.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        {formula ? (
          <TaskMeasures
            workId={workId}
            setWorkId={() => undefined}
            values={values}
            setValues={setValues}
            onSubmit={addTask}
            formula={formula}
            hideWork
          />
        ) : <p className="hint">Elegí la fórmula. Si no está, cargala en Fórmulas para tareas.</p>}
      </div>
      {tasks.length === 0 ? <div className="panel"><Empty title="Esta obra no tiene tareas" text="Elegí el rubro y la fórmula." /></div> : tasks.map((task) => (
        <TaskCard key={task.id} task={task} onChange={onChange} onError={onError} onOk={onOk} />
      ))}
    </div>
  );
}

const TASK_STATES = [
  ["EN_CURSO", "En proceso"],
  ["TRABAJANDO", "Trabajando"],
  ["FINALIZADA", "Completado"],
] as const;

function taskStatusLabel(status: string) {
  return TASK_STATES.find(([value]) => value === status)?.[1] || (status === "PENDIENTE" ? "Pendiente" : labelOf(status));
}

function TaskCard({ task, onChange, onError, onOk }: { task: Rec; onChange: () => void; onError: (value: string) => void; onOk: (value: string) => void }) {
  const [rules, setRules] = useState<Rec[]>([]);
  const [executions, setExecutions] = useState<Rec[]>([]);
  const [advance, setAdvance] = useState({ quantity_delta: "", new_total: "", execution_date: "" });
  const [pendingUse, setPendingUse] = useState<Rec[] | null>(null);
  useEffect(() => {
    api<Rec[]>(`/api/tasks/${task.id}/rules`).then(setRules);
    api<Rec[]>(`/api/tasks/${task.id}/executions`).then(setExecutions);
  }, [task.id, task.executed_qty]);

  function advanceQty() {
    if (advance.quantity_delta) return Number(advance.quantity_delta);
    if (advance.new_total) return Number(advance.new_total) - Number(task.executed_qty || 0);
    return Number.NaN;
  }

  function usageFor(qty: number) {
    if (!(qty > 0)) return [];
    if (task.needs?.length) {
      return task.needs.map((item: Rec) => ({ material_name: item.material_name, quantity: qty * Number(item.coefficient), unit_name: item.unit_name }));
    }
    return rules
      .filter((item) => Number(item.current?.coefficient) > 0)
      .map((item) => ({ material_name: item.material_name, quantity: qty * Number(item.current.coefficient), unit_name: item.unit_code }));
  }

  async function setStatus(status: string, label: string) {
    try {
      await api(`/api/tasks/${task.id}`, { method: "PATCH", body: JSON.stringify({ status }) });
      onOk(`La tarea quedó ${label.toLowerCase()}.`);
      onChange();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "No se pudo cambiar el estado.");
    }
  }

  async function saveAdvance(consume: boolean) {
    try {
      await api(`/api/tasks/${task.id}/executions`, {
        method: "POST",
        idempotencyKey: newKey(),
        body: JSON.stringify({
          quantity_delta: advance.quantity_delta || null,
          new_total: advance.new_total || null,
          execution_date: advance.execution_date || null,
          consume_materials: consume,
        }),
      });
      setAdvance({ quantity_delta: "", new_total: "", execution_date: "" });
      setPendingUse(null);
      onOk(consume ? "Quedó el avance y se descontaron los materiales del stock de la obra." : "Quedó el avance.");
      onChange();
    } catch (err) {
      setPendingUse(null);
      onError(err instanceof ApiError ? err.message : "No se pudo registrar el avance.");
    }
  }

  function addAdvance(event: FormEvent) {
    event.preventDefault();
    const lines = usageFor(advanceQty());
    if (lines.length) {
      setPendingUse(lines);
      return;
    }
    saveAdvance(false);
  }
  return (
    <article className="panel">
      <div className="page-head">
        <div>
          <h2>{task.name}</h2>
          <p>{task.rubric_name} · {describeTask(task)} · Ejecutado {formatQty(task.executed_qty)} {task.unit_code}</p>
        </div>
        <span className={`badge ${task.status === "FINALIZADA" ? "ok" : task.status === "PENDIENTE" ? "warn" : "info"}`}>{taskStatusLabel(task.status)}</span>
      </div>
      <div className="toolbar">
        {TASK_STATES.map(([value, label]) => (
          <button key={value} className={task.status === value ? "action" : "action secondary"} type="button" onClick={() => setStatus(value, label)}>{label}</button>
        ))}
      </div>
      <h3>Va a hacer falta</h3>
      {(task.needs || []).length > 0 ? (
        <ul>{task.needs.map((item: Rec) => <li key={item.material_id}>{formatQty(item.needed)} {item.unit_name} de {item.material_name}</li>)}</ul>
      ) : rules.length === 0 ? <p className="hint">Esta tarea no tiene fórmula.</p> : (
        <ul>{rules.map((item) => <li key={item.id}>{formatQty(Number(task.planned_qty || 0) * Number(item.current?.coefficient || 0))} {item.unit_code} de {item.material_name}</li>)}</ul>
      )}
      {pendingUse ? (
        <Modal title="Se van a utilizar los siguientes materiales" onClose={() => setPendingUse(null)}>
          <ul>{pendingUse.map((item) => <li key={item.material_name}>{formatQty(item.quantity)} {item.unit_name} de {item.material_name}</li>)}</ul>
          <div className="toolbar">
            <button className="action" type="button" onClick={() => saveAdvance(true)}>Usar estos materiales</button>
            <button className="action secondary" type="button" onClick={() => setPendingUse(null)}>Volver</button>
          </div>
        </Modal>
      ) : null}
      <h3>Registrar avance</h3>
      <p className="hint">Si completás el nuevo total, el sistema registra solo la diferencia respecto de lo ya ejecutado. Si la tarea tiene materiales, se descuentan del stock de la obra.</p>
      <form className="form-grid" onSubmit={addAdvance}>
        <div className="field"><label>Cantidad de este avance</label><input value={advance.quantity_delta} onChange={(event) => setAdvance({ ...advance, quantity_delta: event.target.value, new_total: "" })} /></div>
        <div className="field"><label>O nuevo total acumulado</label><input value={advance.new_total} onChange={(event) => setAdvance({ ...advance, new_total: event.target.value, quantity_delta: "" })} /></div>
        <div className="field"><label>Fecha</label><input type="date" value={advance.execution_date} onChange={(event) => setAdvance({ ...advance, execution_date: event.target.value })} /></div>
        <div><button className="action" type="submit">Guardar avance</button></div>
      </form>
      {executions.length > 0 ? (
        <ul>
          {executions.map((item) => (
            <li key={item.id}>
              {item.execution_date}: {formatQty(item.quantity_delta)} {task.unit_code} · <Badge value={item.status} />
              <AdminFix
                active={item.status === "CONFIRMADO"}
                onSaveQty={(quantity, reason) => api(`/api/executions/${item.id}`, { method: "PATCH", body: JSON.stringify({ quantity_delta: quantity, reason }) }).then(onChange)}
                onVoid={(reason) => api(`/api/executions/${item.id}/void`, { method: "POST", body: JSON.stringify({ reason }) }).then(onChange)}
              />
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

function Theoretical({ tasks }: { tasks: Rec[] }) {
  const [views, setViews] = useState<Rec[]>([]);
  useEffect(() => {
    Promise.all(tasks.map((task) => api<Rec>(`/api/tasks/${task.id}/theoretical`).then((view) => ({ ...view, name: task.name, unit: task.unit_code })))).then(setViews);
  }, [tasks]);
  if (views.length === 0) return <div className="panel"><Empty title="Sin tareas" text="El consumo teórico se calcula al registrar avances." /></div>;
  return (
    <div className="grid">
      {views.map((view) => (
        <article className="panel" key={view.task_id}>
          <h2>{view.name}</h2>
          <p>Ejecutado {formatQty(view.executed_qty)} {view.unit}</p>
          {view.materials.length === 0 ? <p className="hint">Todavía no hay líneas teóricas. Registrá un avance con una regla vigente.</p> : (
            <table>
              <thead><tr><th>Material</th><th>Teórico acumulado</th></tr></thead>
              <tbody>{view.materials.map((row: Rec) => <tr key={row.material_id}><td>{row.material_name}</td><td>{formatQty(row.theoretical_qty)} {row.unit_code}</td></tr>)}</tbody>
            </table>
          )}
          {view.projection?.length > 0 ? <p className="hint">Proyección de lo planificado, separada del historial: {view.projection.map((row: Rec) => `${row.material_name} ${formatQty(row.quantity)}`).join(", ")}.</p> : null}
        </article>
      ))}
    </div>
  );
}

function Real({ work, tasks, materials, onChange, onError }: { work: Rec; tasks: Rec[]; materials: Rec[]; onChange: () => void; onError: (value: string) => void }) {
  const [rows, setRows] = useState<Rec[]>([]);
  const [form, setForm] = useState({ task_id: "", material_id: "", quantity: "", notes: "" });
  const [available, setAvailable] = useState<string | null>(null);
  const [ruled, setRuled] = useState<Set<number>>(new Set());
  useEffect(() => {
    api<{ items: Rec[] }>(`/api/consumptions?work_id=${work.id}&page_size=100`).then((data) => setRows(data.items));
  }, [work.id, tasks]);
  useEffect(() => {
    if (!form.material_id || !work.location_id) return;
    api<Rec>(`/api/stock/available?material_id=${form.material_id}&location_id=${work.location_id}`).then((row) => setAvailable(row.on_hand));
  }, [form.material_id, work.location_id]);
  useEffect(() => {
    Promise.all(tasks.map((task) => api<Rec[]>(`/api/tasks/${task.id}/rules`))).then((groups) => {
      const next = new Set<number>();
      groups.forEach((items) => items.forEach((item) => next.add(item.material_id)));
      setRuled(next);
    });
  }, [tasks]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/api/consumptions", {
        method: "POST",
        idempotencyKey: newKey(),
        body: JSON.stringify({
          work_id: work.id,
          task_id: Number(form.task_id),
          location_id: work.location_id,
          material_id: Number(form.material_id),
          quantity: form.quantity,
          notes: form.notes || null,
        }),
      });
      setForm({ task_id: "", material_id: "", quantity: "", notes: "" });
      onChange();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "No se pudo registrar el consumo.");
    }
  }
  const exceeds = available !== null && form.quantity !== "" && Number(form.quantity) > Number(available);
  return (
    <div className="grid">
      <form className="panel form-grid" onSubmit={submit}>
        <div className="field"><label>Tarea</label>
          <select required value={form.task_id} onChange={(event) => setForm({ ...form, task_id: event.target.value })}>
            <option value="">Elegir</option>
            {tasks.map((task) => <option key={task.id} value={task.id}>{task.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Material</label>
          <select required value={form.material_id} onChange={(event) => setForm({ ...form, material_id: event.target.value })}>
            <option value="">Elegir</option>
            {materials.map((row) => <option key={row.id} value={row.id}>{row.name}{ruled.has(row.id) ? " · con regla" : ""}</option>)}
          </select>
        </div>
        <div className="field"><label>Cantidad</label><input required value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></div>
        <div className="field"><label>Ubicación</label><input readOnly value={work.location_name || ""} /></div>
        <p className="span-2 hint">Disponible en la obra: {available === null ? "elegí un material" : formatQty(available)}. {exceeds ? "La cantidad supera el stock." : ""}</p>
        <div className="span-2"><button className="action" type="submit" disabled={exceeds}>Registrar consumo</button></div>
      </form>
      <div className="panel table-wrap">
        {rows.length === 0 ? <Empty title="Sin consumos" text="El consumo real no se deduce de las compras. Se carga acá." /> : (
          <table>
            <thead><tr><th>Fecha</th><th>Tarea</th><th>Material</th><th>Cantidad</th><th>Responsable</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{formatDate(row.consumed_at)}</td>
                  <td>{row.task_name}</td>
                  <td>{row.material_name}</td>
                  <td>{formatQty(row.quantity)} {row.unit_code}{row.corrects_consumption_id ? " (corrección)" : ""}</td>
                  <td>{row.recorded_by}</td>
                  <td><Badge value={row.status} /></td>
                  <td>
                    <AdminFix
                      active={row.status === "CONFIRMADO" && !row.corrects_consumption_id}
                      onSaveQty={(quantity, reason) => api(`/api/consumptions/${row.id}`, { method: "PATCH", body: JSON.stringify({ quantity, reason }) }).then(onChange)}
                      onVoid={(reason) => api(`/api/consumptions/${row.id}/void`, { method: "POST", body: JSON.stringify({ reason }) }).then(onChange)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Stock({ locationId }: { locationId: number | null }) {
  const [rows, setRows] = useState<Rec[]>([]);
  useEffect(() => {
    if (!locationId) return;
    api<Rec[]>(`/api/stock?location_id=${locationId}`).then(setRows);
  }, [locationId]);
  if (!locationId) return <div className="panel"><Empty title="Sin ubicación" text="Esta obra no tiene una ubicación de stock." /></div>;
  return (
    <div className="panel table-wrap">
      {rows.length === 0 ? <Empty title="Sin stock en la obra" text="Las recepciones y las transferencias van a mostrar el disponible, separado de lo pendiente y lo en tránsito." /> : (
        <table>
          <thead><tr><th>Material</th><th>Disponible</th><th>Pendiente de recibir</th><th>En tránsito</th><th>Último movimiento</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.material_id}`}>
                <td>{row.material_name}</td>
                <td>{formatQty(row.on_hand)} {row.unit_code}</td>
                <td>{formatQty(row.pending_receipt)}</td>
                <td>{formatQty(row.in_transit_in)}</td>
                <td>{row.last_movement_type ? `${labelOf(row.last_movement_type, MOVEMENT_LABELS)} · ${formatDate(row.last_movement_at)}` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function Orders({ workId }: { workId: number }) {
  const [rows, setRows] = useState<Rec[]>([]);
  useEffect(() => {
    api<{ items: Rec[] }>(`/api/purchase-orders?work_id=${workId}&page_size=100`).then((data) => setRows(data.items));
  }, [workId]);
  return (
    <div className="panel">
      <Link className="action" to="/ordenes">Nueva orden</Link>
      {rows.length === 0 ? <Empty title="Sin órdenes de esta obra" text="Emitir una orden no suma stock. El stock cambia con la recepción." /> : (
        <table>
          <thead><tr><th>Número</th><th>Proveedor</th><th>Estado</th><th></th></tr></thead>
          <tbody>{rows.map((row) => <tr key={row.id}><td>{row.number}</td><td>{row.supplier_name}</td><td><Badge value={row.status} /></td><td><Link to={`/ordenes/${row.id}`}>Detalle</Link></td></tr>)}</tbody>
        </table>
      )}
    </div>
  );
}

function Transfers({ locationId }: { locationId: number | null }) {
  const [rows, setRows] = useState<Rec[]>([]);
  useEffect(() => {
    api<{ items: Rec[] }>("/api/transfers?page_size=100").then((data) => {
      setRows(data.items.filter((row) => row.from_location_id === locationId || row.to_location_id === locationId));
    });
  }, [locationId]);
  return (
    <div className="panel">
      <Link className="action" to="/transferencias">Nuevo traslado</Link>
      {rows.length === 0 ? <Empty title="Sin transferencias" text="Podés mover material entre el galpón y esta obra." /> : (
        <table>
          <thead><tr><th>Número</th><th>Origen</th><th>Destino</th><th>Estado</th><th></th></tr></thead>
          <tbody>{rows.map((row) => <tr key={row.id}><td>{row.number}</td><td>{row.from_location_name}</td><td>{row.to_location_name}</td><td><Badge value={row.status} /></td><td><Link to={`/transferencias/${row.id}`}>Detalle</Link></td></tr>)}</tbody>
        </table>
      )}
    </div>
  );
}

function History({ locationId }: { locationId: number | null }) {
  const [rows, setRows] = useState<Rec[]>([]);
  useEffect(() => {
    if (!locationId) return;
    api<{ items: Rec[] }>(`/api/movements?location_id=${locationId}&page_size=100`).then((data) => setRows(data.items));
  }, [locationId]);
  return (
    <div className="panel table-wrap">
      {rows.length === 0 ? <Empty title="Sin movimientos" text="El historial muestra entradas y salidas confirmadas de esta ubicación." /> : (
        <table>
          <thead><tr><th>Fecha</th><th>Tipo</th><th>Material</th><th>Cantidad</th><th>Responsable</th><th>Referencia</th><th>Estado</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{formatDate(row.occurred_at)}</td>
                <td>{labelOf(row.movement_type, MOVEMENT_LABELS)}</td>
                <td>{row.material_name}</td>
                <td>{formatQty(row.signed_qty)}</td>
                <td>{row.recorded_by}</td>
                <td>{row.reference_code || row.document_type}</td>
                <td><Badge value={row.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
