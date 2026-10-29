import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { Badge, Empty, ErrorText } from "../components/ui";
import { formatQty } from "../lib/format";

type Rec = Record<string, any>;

export function OrdersPage() {
  const [rows, setRows] = useState<Rec[]>([]);
  const [suppliers, setSuppliers] = useState<Rec[]>([]);
  const [works, setWorks] = useState<Rec[]>([]);
  const [locations, setLocations] = useState<Rec[]>([]);
  const [materials, setMaterials] = useState<Rec[]>([]);
  const [error, setError] = useState("");
  const [supplierName, setSupplierName] = useState("");
  const [form, setForm] = useState({ supplier_id: "", work_id: "", destination_location_id: "", material_id: "", quantity: "", unit_price: "", currency: "" });

  function load() {
    api<{ items: Rec[] }>("/api/purchase-orders?page_size=100").then((data) => setRows(data.items));
    api<Rec[]>("/api/suppliers").then(setSuppliers);
    api<{ items: Rec[] }>("/api/works?page_size=100").then((data) => setWorks(data.items));
    api<Rec[]>("/api/locations").then(setLocations);
    api<{ items: Rec[] }>("/api/materials?page_size=100").then((data) => setMaterials(data.items));
  }
  useEffect(load, []);

  async function addSupplier(event: FormEvent) {
    event.preventDefault();
    const created = await api<Rec>("/api/suppliers", { method: "POST", body: JSON.stringify({ name: supplierName }) });
    setSupplierName("");
    setForm({ ...form, supplier_id: String(created.id) });
    load();
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/api/purchase-orders", {
        method: "POST",
        body: JSON.stringify({
          supplier_id: Number(form.supplier_id),
          work_id: form.work_id ? Number(form.work_id) : null,
          destination_location_id: Number(form.destination_location_id),
          items: [{
            material_id: Number(form.material_id),
            quantity: form.quantity,
            unit_price: form.unit_price || null,
            currency: form.currency || null,
          }],
        }),
      });
      setForm({ supplier_id: "", work_id: "", destination_location_id: "", material_id: "", quantity: "", unit_price: "", currency: "" });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear la orden.");
    }
  }

  return (
    <section>
      <div className="page-head"><div><h1>Órdenes de compra</h1><p>La orden indica lo solicitado. El stock cambia recién cuando se registra la recepción.</p></div></div>
      {error ? <ErrorText error={error} /> : null}
      <form className="toolbar" onSubmit={addSupplier}>
        <input className="search" aria-label="Nuevo proveedor" placeholder="Nuevo proveedor" value={supplierName} onChange={(event) => setSupplierName(event.target.value)} />
        <button className="btn secondary" type="submit">Agregar proveedor</button>
      </form>
      <form className="panel form-grid" onSubmit={create}>
        <div className="field"><label>Proveedor</label>
          <select required value={form.supplier_id} onChange={(event) => setForm({ ...form, supplier_id: event.target.value })}>
            <option value="">Elegir</option>
            {suppliers.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Obra prevista</label>
          <select value={form.work_id} onChange={(event) => setForm({ ...form, work_id: event.target.value })}>
            <option value="">Sin obra</option>
            {works.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Destino previsto</label>
          <select required value={form.destination_location_id} onChange={(event) => setForm({ ...form, destination_location_id: event.target.value })}>
            <option value="">Elegir</option>
            {locations.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Material</label>
          <select required value={form.material_id} onChange={(event) => setForm({ ...form, material_id: event.target.value })}>
            <option value="">Elegir</option>
            {materials.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Cantidad solicitada</label><input required value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></div>
        <div className="field"><label>Precio unitario (opcional)</label><input value={form.unit_price} onChange={(event) => setForm({ ...form, unit_price: event.target.value })} /></div>
        <div className="field"><label>Moneda</label><input value={form.currency} placeholder="ARS" onChange={(event) => setForm({ ...form, currency: event.target.value })} /></div>
        <div className="span-2"><button className="btn" type="submit">Crear borrador</button></div>
      </form>
      <div className="panel" style={{ marginTop: 14 }}>
        {rows.length === 0 ? <Empty title="Sin órdenes" text="Creá una orden en borrador y confirmala antes de recibir materiales." /> : (
          <table>
            <thead><tr><th>Número</th><th>Proveedor</th><th>Obra</th><th>Pedido</th><th>Recibido</th><th>Pendiente</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {rows.map((row) => {
                const ordered = row.items.reduce((sum: number, item: Rec) => sum + Number(item.qty_ordered), 0);
                const received = row.items.reduce((sum: number, item: Rec) => sum + Number(item.qty_received), 0);
                const pending = row.items.reduce((sum: number, item: Rec) => sum + Number(item.qty_pending), 0);
                return (
                  <tr key={row.id}>
                    <td>{row.number}</td>
                    <td>{row.supplier_name}</td>
                    <td>{row.work_name || "—"}</td>
                    <td>{formatQty(ordered)}</td>
                    <td>{formatQty(received)}</td>
                    <td>{formatQty(pending)}</td>
                    <td><Badge value={row.status} /></td>
                    <td><Link to={`/ordenes/${row.id}`}>Detalle</Link></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
