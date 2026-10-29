import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { AdminFix, Empty, ErrorText } from "../components/ui";
import { formatDate, formatQty, labelOf, MOVEMENT_LABELS, newKey } from "../lib/format";

type Rec = Record<string, any>;

export function InventoryPage() {
  const [rows, setRows] = useState<Rec[]>([]);
  const [movements, setMovements] = useState<Rec[]>([]);
  const [materials, setMaterials] = useState<Rec[]>([]);
  const [locations, setLocations] = useState<Rec[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [adjustments, setAdjustments] = useState<Rec[]>([]);
  const [form, setForm] = useState({ material_id: "", location_id: "", counted_qty: "", reason: "" });

  function load() {
    api<Rec[]>(`/api/stock${q ? `?q=${encodeURIComponent(q)}` : ""}`).then(setRows);
    api<{ items: Rec[] }>("/api/movements?page_size=30").then((data) => setMovements(data.items));
    api<{ items: Rec[] }>("/api/materials?page_size=100").then((data) => setMaterials(data.items));
    api<Rec[]>("/api/locations").then(setLocations);
    api<Rec[]>("/api/adjustments").then(setAdjustments);
  }
  useEffect(load, [q]);

  async function adjust(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/api/adjustments", {
        method: "POST",
        idempotencyKey: newKey(),
        body: JSON.stringify({
          material_id: Number(form.material_id),
          location_id: Number(form.location_id),
          counted_qty: form.counted_qty,
          reason: form.reason,
        }),
      });
      setForm({ material_id: "", location_id: "", counted_qty: "", reason: "" });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo registrar el ajuste.");
    }
  }

  return (
    <section>
      <div className="page-head"><div><h1>Inventario</h1><p>El disponible es el stock físico. Lo pendiente de compra y lo en tránsito se muestran aparte y no se suman.</p></div></div>
      {error ? <ErrorText error={error} /> : null}
      <div className="toolbar"><input className="search" aria-label="Buscar stock" placeholder="Buscar material o ubicación" value={q} onChange={(event) => setQ(event.target.value)} /></div>
      <div className="panel table-wrap">
        {rows.length === 0 ? <Empty title="No hay existencias" text="Registrá una recepción o un ajuste de conteo para ver el stock por ubicación." /> : (
          <table>
            <thead><tr><th>Material</th><th>Ubicación</th><th>Disponible</th><th>Pendiente</th><th>Sale en tránsito</th><th>Entra en tránsito</th><th>Último movimiento</th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.material_id}-${row.location_id}`}>
                  <td>{row.material_code} {row.material_name}</td>
                  <td>{row.location_name}</td>
                  <td>{formatQty(row.on_hand)} {row.unit_code}</td>
                  <td>{formatQty(row.pending_receipt)}</td>
                  <td>{formatQty(row.in_transit_out)}</td>
                  <td>{formatQty(row.in_transit_in)}</td>
                  <td>{row.last_movement_type ? `${labelOf(row.last_movement_type, MOVEMENT_LABELS)} · ${formatDate(row.last_movement_at)}` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <form className="panel form-grid" onSubmit={adjust} style={{ marginTop: 14 }}>
        <h2 className="span-2">Conteo físico</h2>
        <div className="field"><label>Material</label>
          <select required value={form.material_id} onChange={(event) => setForm({ ...form, material_id: event.target.value })}>
            <option value="">Elegir</option>
            {materials.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Ubicación</label>
          <select required value={form.location_id} onChange={(event) => setForm({ ...form, location_id: event.target.value })}>
            <option value="">Elegir</option>
            {locations.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </div>
        <div className="field"><label>Cantidad contada</label><input required value={form.counted_qty} onChange={(event) => setForm({ ...form, counted_qty: event.target.value })} /></div>
        <div className="field"><label>Motivo</label><input required value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} /></div>
        <div className="span-2"><button className="btn" type="submit">Registrar ajuste</button></div>
      </form>
      <div className="panel" style={{ marginTop: 14 }}>
        <h2>Ajustes de conteo</h2>
        {adjustments.length === 0 ? <p className="hint">Todavía no hay conteos físicos.</p> : (
          <ul>
            {adjustments.map((row) => (
              <li key={row.id}>
                {row.material_name} en {row.location_name}: contado {formatQty(row.counted_qty)} (antes {formatQty(row.previous_qty)}) · {row.status}
                <AdminFix
                  active={row.status === "CONFIRMADO"}
                  onSaveQty={(quantity, reason) => api(`/api/adjustments/${row.id}`, { method: "PATCH", body: JSON.stringify({ counted_qty: quantity, reason }) }).then(load)}
                  onVoid={(reason) => api(`/api/adjustments/${row.id}/void`, { method: "POST", body: JSON.stringify({ reason }) }).then(load)}
                />
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="panel" style={{ marginTop: 14 }}>
        <h2>Movimientos recientes</h2>
        <table>
          <thead><tr><th>Fecha</th><th>Material</th><th>Tipo</th><th>Ubicación</th><th>Cantidad</th><th>Responsable</th><th>Referencia</th></tr></thead>
          <tbody>
            {movements.map((row) => (
              <tr key={row.id}>
                <td>{formatDate(row.occurred_at)}</td>
                <td>{row.material_name}</td>
                <td>{labelOf(row.movement_type, MOVEMENT_LABELS)}</td>
                <td>{row.location_name}</td>
                <td>{formatQty(row.signed_qty)}</td>
                <td>{row.recorded_by}</td>
                <td>{row.reference_code || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
