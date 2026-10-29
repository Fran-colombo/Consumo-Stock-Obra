import { FormEvent, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { AdminFix, Badge, ErrorText } from "../components/ui";
import { formatDate, formatQty, newKey } from "../lib/format";

type Rec = Record<string, any>;

export function TransferDetailPage() {
  const { id } = useParams();
  const [row, setRow] = useState<Rec | null>(null);
  const [users, setUsers] = useState<Rec[]>([]);
  const [error, setError] = useState("");
  const [dispatchForm, setDispatchForm] = useState({ executed_by_user_id: "", executed_operational_name: "" });
  const [receiveQty, setReceiveQty] = useState<Record<number, string>>({});
  const [receiver, setReceiver] = useState({ received_by_user_id: "", received_operational_name: "", close_with_difference: false });
  const [resolveReason, setResolveReason] = useState("");

  function load() {
    if (!id) return;
    api<Rec>(`/api/transfers/${id}`).then((data) => {
      setRow(data);
      const next: Record<number, string> = {};
      data.items.forEach((item: Rec) => { next[item.id] = item.in_transit; });
      setReceiveQty(next);
    });
    api<Rec[]>("/api/users").then(setUsers);
  }
  useEffect(load, [id]);

  async function dispatch() {
    try {
      await api(`/api/transfers/${id}/dispatch`, {
        method: "POST",
        idempotencyKey: newKey(),
        body: JSON.stringify({
          executed_by_user_id: dispatchForm.executed_by_user_id ? Number(dispatchForm.executed_by_user_id) : null,
          executed_operational_name: dispatchForm.executed_operational_name || null,
        }),
      });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo despachar.");
    }
  }

  async function receive(event: FormEvent) {
    event.preventDefault();
    if (!row) return;
    try {
      await api(`/api/transfers/${id}/receive`, {
        method: "POST",
        idempotencyKey: newKey(),
        body: JSON.stringify({
          items: row.items.map((item: Rec) => ({ transfer_item_id: item.id, quantity: receiveQty[item.id] || "0" })),
          received_by_user_id: receiver.received_by_user_id ? Number(receiver.received_by_user_id) : null,
          received_operational_name: receiver.received_operational_name || null,
          close_with_difference: receiver.close_with_difference,
        }),
      });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo recibir.");
    }
  }

  async function resolve(discrepancyId: number, action: string) {
    const reason = resolveReason.trim();
    if (reason.length < 3) {
      setError("Indicá el motivo de la resolución.");
      return;
    }
    try {
      await api(`/api/discrepancies/${discrepancyId}/resolve`, { method: "POST", body: JSON.stringify({ action, reason }) });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo resolver la diferencia.");
    }
  }

  if (!row) return <p>Cargando la transferencia…</p>;
  return (
    <section>
      <div className="page-head">
        <div>
          <h1>{row.number}</h1>
          <p>{row.from_location_name} → {row.to_location_name}</p>
        </div>
        <Badge value={row.status} />
      </div>
      {error ? <ErrorText error={error} /> : null}
      <div className="panel">
        <p>Registró: {row.created_by} el {formatDate(row.created_at)}</p>
        <p>Autorizó: {row.authorized_by?.full_name || row.authorized_operational_name || "—"} {row.authorized_at ? `· ${formatDate(row.authorized_at)}` : ""}</p>
        <p>Trasladó: {row.executed_by?.full_name || row.executed_operational_name || "—"} {row.executed_at ? `· ${formatDate(row.executed_at)}` : ""}</p>
        <p>Recibió: {row.received_by?.full_name || row.received_operational_name || "—"} {row.received_at ? `· ${formatDate(row.received_at)}` : ""}</p>
        <table>
          <thead><tr><th>Material</th><th>Enviado</th><th>Recibido</th><th>Devuelto</th><th>En tránsito</th></tr></thead>
          <tbody>
            {row.items.map((item: Rec) => (
              <tr key={item.id}>
                <td>{item.material_name}</td>
                <td>{formatQty(item.qty_sent)} {item.unit_code}</td>
                <td>{formatQty(item.qty_received)}</td>
                <td>{formatQty(item.qty_returned)}</td>
                <td>{formatQty(item.in_transit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {row.items.flatMap((item: Rec) => item.discrepancies).map((item: Rec) => (
          <div key={item.id}>
            <Badge value={item.status} /> Diferencia {formatQty(item.quantity)}
            {item.status === "PENDIENTE" ? (
              <div className="actions">
                <input aria-label="Motivo de la diferencia" placeholder="Motivo" value={resolveReason} onChange={(event) => setResolveReason(event.target.value)} />
                <button className="action secondary" type="button" onClick={() => resolve(item.id, "devolver")}>Devolver al origen</button>
                <button className="action secondary" type="button" onClick={() => resolve(item.id, "recibir")}>Recibir el resto</button>
                <button className="action warn" type="button" onClick={() => resolve(item.id, "perdida")}>Registrar pérdida</button>
              </div>
            ) : null}
          </div>
        ))}
      </div>
      {row.status === "REGISTRADA" ? (
        <div className="panel" style={{ marginTop: 14 }}>
          <h2>Despachar</h2>
          <div className="field"><label>Quién traslada</label>
            <select value={dispatchForm.executed_by_user_id} onChange={(event) => setDispatchForm({ ...dispatchForm, executed_by_user_id: event.target.value })}>
              <option value="">Sin usuario</option>
              {users.map((person) => <option key={person.id} value={person.id}>{person.full_name}</option>)}
            </select>
          </div>
          <div className="field"><label>Nombre operativo</label><input value={dispatchForm.executed_operational_name} onChange={(event) => setDispatchForm({ ...dispatchForm, executed_operational_name: event.target.value })} /></div>
          <button className="action" type="button" onClick={dispatch}>Descontar origen y poner en tránsito</button>
        </div>
      ) : null}
      {row.status === "EN_TRANSITO" || row.status === "RECIBIDA_PARCIAL" ? (
        <form className="panel" style={{ marginTop: 14 }} onSubmit={receive}>
          <h2>Recibir</h2>
          {row.items.map((item: Rec) => (
            <div className="field" key={item.id}>
              <label>{item.material_name} recibido ahora</label>
              <input value={receiveQty[item.id] || ""} onChange={(event) => setReceiveQty({ ...receiveQty, [item.id]: event.target.value })} />
            </div>
          ))}
          <div className="field"><label>Quién recibe</label>
            <select value={receiver.received_by_user_id} onChange={(event) => setReceiver({ ...receiver, received_by_user_id: event.target.value })}>
              <option value="">Sin usuario</option>
              {users.map((person) => <option key={person.id} value={person.id}>{person.full_name}</option>)}
            </select>
          </div>
          <div className="field"><label>Nombre operativo</label><input value={receiver.received_operational_name} onChange={(event) => setReceiver({ ...receiver, received_operational_name: event.target.value })} /></div>
          <label><input type="checkbox" checked={receiver.close_with_difference} onChange={(event) => setReceiver({ ...receiver, close_with_difference: event.target.checked })} /> Cerrar con diferencia si llega menos. El faltante queda identificado y no se asigna solo a ningún lado.</label>
          <div><button className="action" type="submit">Registrar recepción</button></div>
        </form>
      ) : null}
      <AdminFix
        active={row.status !== "CANCELADA"}
        onVoid={(reason) => api(`/api/transfers/${id}/void`, { method: "POST", body: JSON.stringify({ reason }) }).then(load)}
      />
    </section>
  );
}
