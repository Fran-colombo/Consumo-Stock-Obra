import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { Badge, useNotice } from "../components/ui";
import { formatQty } from "../lib/format";

type Rec = Record<string, any>;

export function OrdersPage() {
  const notice = useNotice();
  const [rows, setRows] = useState<Rec[]>([]);
  const [suppliers, setSuppliers] = useState<Rec[]>([]);
  const [works, setWorks] = useState<Rec[]>([]);
  const [materials, setMaterials] = useState<Rec[]>([]);
  const [supplierName, setSupplierName] = useState("");
  const [form, setForm] = useState({ supplier_id: "", work_id: "", material_id: "", quantity: "" });

  function load() {
    api<{ items: Rec[] }>("/api/purchase-orders?page_size=100").then((data) => setRows(data.items));
    api<Rec[]>("/api/suppliers").then(setSuppliers);
    api<{ items: Rec[] }>("/api/works?page_size=100").then((data) => setWorks(data.items));
    api<{ items: Rec[] }>("/api/materials?page_size=100").then((data) => setMaterials(data.items));
  }
  useEffect(load, []);

  async function addSupplier(event: FormEvent) {
    event.preventDefault();
    try {
      const created = await api<Rec>("/api/suppliers", { method: "POST", body: JSON.stringify({ name: supplierName }) });
      setSupplierName("");
      setForm({ ...form, supplier_id: String(created.id) });
      load();
      notice.ok(`Quedó el proveedor ${created.name}.`);
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo agregar el proveedor.");
    }
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    const work = works.find((row) => String(row.id) === form.work_id);
    if (!work?.location_id) {
      notice.fail("Esa obra no tiene un lugar de stock.");
      return;
    }
    try {
      const order = await api<Rec>("/api/purchase-orders", {
        method: "POST",
        body: JSON.stringify({
          supplier_id: Number(form.supplier_id),
          work_id: Number(form.work_id),
          destination_location_id: work.location_id,
          items: [{ material_id: Number(form.material_id), quantity: form.quantity }],
        }),
      });
      setForm({ supplier_id: form.supplier_id, work_id: "", material_id: "", quantity: "" });
      load();
      notice.ok(`${order.number} quedó pendiente. El siguiente paso es encargarla.`);
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo cargar la orden.");
    }
  }

  return (
    <section>
      {notice.dialog}
      <div className="page-head">
        <div>
          <h1>Órdenes de compra</h1>
          <p>Cada orden tiene un solo paso siguiente: encargar, marcar que llegó o marcar que se usó.</p>
        </div>
      </div>
      <form className="toolbar" onSubmit={addSupplier}>
        <input className="search" aria-label="Nuevo proveedor" placeholder="Nuevo proveedor" value={supplierName} onChange={(event) => setSupplierName(event.target.value)} required />
        <button className="action secondary" type="submit">Agregar proveedor</button>
      </form>
      <form className="panel form-grid" onSubmit={create}>
        <div className="field"><label>Proveedor</label>
          <select required value={form.supplier_id} onChange={(event) => setForm({ ...form, supplier_id: event.target.value })}>
            <option value="">Elegir</option>
            {suppliers.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Obra</label>
          <select required value={form.work_id} onChange={(event) => setForm({ ...form, work_id: event.target.value })}>
            <option value="">Elegir</option>
            {works.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Material</label>
          <select required value={form.material_id} onChange={(event) => setForm({ ...form, material_id: event.target.value })}>
            <option value="">Elegir</option>
            {materials.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Cantidad</label><input required value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></div>
        <div className="span-2"><button className="action" type="submit">Cargar orden</button></div>
      </form>
      <div className="panel" style={{ marginTop: 14 }}>
        {rows.length === 0 ? <p className="hint">Todavía no hay órdenes.</p> : rows.map((order) => (
          <OrderCard key={order.id} order={order} onDone={load} onOk={notice.ok} onFail={notice.fail} />
        ))}
      </div>
    </section>
  );
}

function OrderCard({ order, onDone, onOk, onFail }: { order: Rec; onDone: () => void; onOk: (message: string) => void; onFail: (message: string) => void }) {
  const [quantity, setQuantity] = useState("");
  const [tasks, setTasks] = useState<Rec[]>([]);
  const [taskId, setTaskId] = useState("");
  const item = order.items?.[0];
  const pending = Number(item?.qty_pending || 0);
  const received = Number(item?.qty_received || 0);

  useEffect(() => {
    if (!order.work_id || (order.status !== "RECIBIDA" && order.status !== "PARCIAL")) return;
    api<Rec[]>(`/api/tasks?work_id=${order.work_id}`).then(setTasks);
  }, [order.work_id, order.status]);

  async function run(path: string, body: unknown, message: string) {
    try {
      await api(path, { method: "POST", body: JSON.stringify(body) });
      onDone();
      onOk(message);
    } catch (err) {
      onFail(err instanceof ApiError ? err.message : "No se pudo actualizar la orden.");
    }
  }

  return (
    <article className="order-card">
      <div>
        <strong>{order.number}</strong>
        <p className="hint">{item?.material_name} · {formatQty(item?.qty_ordered)} {item?.unit_code} · {order.work_name} · {order.supplier_name}</p>
        <Badge value={order.status} />
      </div>
      <div>
        {order.status === "BORRADOR" ? (
          <button className="action" type="button" onClick={() => run(`/api/purchase-orders/${order.id}/confirm`, {}, `${order.number} quedó encargada.`)}>Encargar</button>
        ) : null}
        {order.status === "CONFIRMADA" || (order.status === "PARCIAL" && pending > 0) ? (
          <div className="field">
            <label>Cuánto llegó</label>
            <input placeholder={pending ? `Pendiente ${formatQty(pending)}` : ""} value={quantity} onChange={(event) => setQuantity(event.target.value)} />
            <button className="action" type="button" onClick={() => run(`/api/purchase-orders/${order.id}/arrive`, { quantity: quantity || null }, `${item?.material_name} llegó a ${order.work_name}.`)}>Llegó</button>
          </div>
        ) : null}
        {(order.status === "RECIBIDA" || (order.status === "PARCIAL" && received > 0)) ? (
          <div className="field">
            <label>Tarea donde se usó</label>
            <select value={taskId} onChange={(event) => setTaskId(event.target.value)}>
              <option value="">Elegir</option>
              {tasks.map((task) => <option key={task.id} value={task.id}>{task.name}</option>)}
            </select>
            <button className="action secondary" type="button" onClick={() => {
              if (!taskId) { onFail("Elegí la tarea donde se usó."); return; }
              run(`/api/purchase-orders/${order.id}/use`, { task_id: Number(taskId) }, `Los materiales de ${order.number} salieron del stock.`);
            }}>Se usaron</button>
          </div>
        ) : null}
      </div>
    </article>
  );
}
