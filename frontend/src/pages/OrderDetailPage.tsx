import { FormEvent, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { AdminFix, Badge, ErrorText } from "../components/ui";
import { formatDate, formatQty, newKey } from "../lib/format";

type Rec = Record<string, any>;

export function OrderDetailPage() {
  const { id } = useParams();
  const [order, setOrder] = useState<Rec | null>(null);
  const [receipts, setReceipts] = useState<Rec[]>([]);
  const [locations, setLocations] = useState<Rec[]>([]);
  const [locationId, setLocationId] = useState("");
  const [qty, setQty] = useState<Record<number, string>>({});
  const [error, setError] = useState("");

  function load() {
    if (!id) return;
    api<Rec>(`/api/purchase-orders/${id}`).then((data) => {
      setOrder(data);
      setLocationId(String(data.destination_location_id));
    });
    api<Rec[]>(`/api/purchase-orders/${id}/receipts`).then(setReceipts);
    api<Rec[]>("/api/locations").then(setLocations);
  }
  useEffect(load, [id]);

  async function confirm() {
    try {
      await api(`/api/purchase-orders/${id}/confirm`, { method: "POST" });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo confirmar.");
    }
  }

  async function receive(event: FormEvent) {
    event.preventDefault();
    if (!order) return;
    const items = order.items
      .filter((item: Rec) => qty[item.id] && Number(qty[item.id]) > 0)
      .map((item: Rec) => ({ purchase_order_item_id: item.id, quantity: qty[item.id] }));
    try {
      await api(`/api/purchase-orders/${id}/receipts`, {
        method: "POST",
        idempotencyKey: newKey(),
        body: JSON.stringify({ location_id: Number(locationId), items }),
      });
      setQty({});
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo recibir.");
    }
  }

  if (!order) return <p>Cargando la orden…</p>;
  return (
    <section>
      <div className="page-head">
        <div>
          <h1>{order.number}</h1>
          <p>{order.supplier_name} · Destino previsto {order.destination_name} · Creada por {order.created_by}</p>
        </div>
        <Badge value={order.status} />
      </div>
      {error ? <ErrorText error={error} /> : null}
      <div className="panel table-wrap">
        <table>
          <thead><tr><th>Material</th><th>Solicitado</th><th>Recibido</th><th>Pendiente</th><th>Precio</th></tr></thead>
          <tbody>
            {order.items.map((item: Rec) => (
              <tr key={item.id}>
                <td>{item.material_name}</td>
                <td>{formatQty(item.qty_ordered)} {item.unit_code}</td>
                <td>{formatQty(item.qty_received)}</td>
                <td>{formatQty(item.qty_pending)}</td>
                <td>{item.unit_price ? `${formatQty(item.unit_price)} ${item.currency || ""}` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {order.status === "BORRADOR" ? <button className="action" type="button" onClick={confirm}>Confirmar orden</button> : null}
      </div>
      {order.status !== "BORRADOR" && order.status !== "CANCELADA" ? (
        <form className="panel" onSubmit={receive} style={{ marginTop: 14 }}>
          <h2>Registrar recepción</h2>
          <p className="hint">Podés recibir una parte. Lo pendiente no entra al stock.</p>
          <div className="field"><label>Ubicación donde se deposita</label>
            <select value={locationId} onChange={(event) => setLocationId(event.target.value)}>
              {locations.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </div>
          {order.items.map((item: Rec) => (
            <div className="field" key={item.id}>
              <label>{item.material_name} (pendiente {formatQty(item.qty_pending)})</label>
              <input value={qty[item.id] || ""} onChange={(event) => setQty({ ...qty, [item.id]: event.target.value })} />
            </div>
          ))}
          <button className="action" type="submit">Recibir</button>
        </form>
      ) : null}
      <div className="panel" style={{ marginTop: 14 }}>
        <h2>Recepciones</h2>
        {receipts.length === 0 ? <p className="hint">Todavía no hay entregas.</p> : receipts.map((receipt) => (
          <article key={receipt.id}>
            <strong>{formatDate(receipt.received_at)}</strong> · {receipt.location_name} · {receipt.received_by} · <Badge value={receipt.status} />
            <ul>{receipt.items.map((item: Rec) => (
              <li key={item.id}>
                {item.material_name}: {formatQty(item.quantity)}{item.excedente ? " (excedente)" : ""}
                <AdminFix
                  active={receipt.status === "CONFIRMADO"}
                  onSaveQty={(quantity, reason) => api(`/api/receipt-items/${item.id}`, { method: "PATCH", body: JSON.stringify({ quantity, reason }) }).then(load)}
                  onVoid={(reason) => api(`/api/receipts/${receipt.id}/void`, { method: "POST", body: JSON.stringify({ reason }) }).then(load)}
                />
              </li>
            ))}</ul>
          </article>
        ))}
      </div>
    </section>
  );
}
