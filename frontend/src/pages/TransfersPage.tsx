import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useNotice } from "../components/ui";

type Rec = Record<string, any>;

export function TransfersPage() {
  const notice = useNotice();
  const [locations, setLocations] = useState<Rec[]>([]);
  const [materials, setMaterials] = useState<Rec[]>([]);
  const [rows, setRows] = useState<Rec[]>([]);
  const [less, setLess] = useState(false);
  const [form, setForm] = useState({
    from_location_id: "",
    to_location_id: "",
    material_id: "",
    quantity: "",
    received_quantity: "",
    shortfall_action: "devolver",
    reason: "",
  });

  function load() {
    api<Rec[]>("/api/locations").then(setLocations);
    api<{ items: Rec[] }>("/api/materials?page_size=100").then((data) => setMaterials(data.items));
    api<{ items: Rec[] }>("/api/transfers?page_size=20").then((data) => setRows(data.items));
  }
  useEffect(load, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (less && !form.reason.trim()) {
      notice.fail("Si llegó menos, escribí qué pasó con el faltante.");
      return;
    }
    const origin = locations.find((row) => String(row.id) === form.from_location_id);
    const destination = locations.find((row) => String(row.id) === form.to_location_id);
    const material = materials.find((row) => String(row.id) === form.material_id);
    try {
      await api("/api/transfers/direct", {
        method: "POST",
        body: JSON.stringify({
          from_location_id: Number(form.from_location_id),
          to_location_id: Number(form.to_location_id),
          material_id: Number(form.material_id),
          quantity: form.quantity,
          received_quantity: less ? form.received_quantity : null,
          shortfall_action: less ? form.shortfall_action : null,
          reason: less ? form.reason : null,
        }),
      });
      setForm({ from_location_id: "", to_location_id: "", material_id: "", quantity: "", received_quantity: "", shortfall_action: "devolver", reason: "" });
      setLess(false);
      load();
      notice.ok(`${material?.name || "El material"} pasó de ${origin?.name || "origen"} a ${destination?.name || "destino"}.`);
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo transferir el stock.");
    }
  }

  return (
    <section>
      {notice.dialog}
      <div className="page-head">
        <div>
          <h1>Transferir stock</h1>
          <p>Elegís origen, destino, material y cantidad. Con un botón el stock se mueve.</p>
        </div>
      </div>
      <form className="panel form-grid" onSubmit={submit}>
        <div className="field"><label>Sale de</label>
          <select required value={form.from_location_id} onChange={(event) => setForm({ ...form, from_location_id: event.target.value })}>
            <option value="">Elegir</option>
            {locations.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Llega a</label>
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
        <label className="span-2"><input type="checkbox" checked={less} onChange={(event) => setLess(event.target.checked)} /> Llegó menos</label>
        {less ? (
          <>
            <div className="field"><label>Cuánto llegó</label><input required value={form.received_quantity} onChange={(event) => setForm({ ...form, received_quantity: event.target.value })} /></div>
            <div className="field"><label>Qué pasó con el faltante</label>
              <select value={form.shortfall_action} onChange={(event) => setForm({ ...form, shortfall_action: event.target.value })}>
                <option value="devolver">Volvió al origen</option>
                <option value="perdida">Se perdió</option>
                <option value="recibir">Llegó igual</option>
              </select>
            </div>
            <div className="field span-2"><label>Motivo</label><input required value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} /></div>
          </>
        ) : null}
        <div className="span-2"><button className="action" type="submit">Transferir stock</button></div>
      </form>
      <div className="panel" style={{ marginTop: 14 }}>
        <h2>Últimos movimientos</h2>
        {rows.length === 0 ? <p className="hint">Todavía no hay traslados.</p> : (
          <ul>{rows.map((row) => <li key={row.id}>{row.number}: {row.from_location_name} → {row.to_location_name}</li>)}</ul>
        )}
      </div>
    </section>
  );
}
