import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, Line } from "react-chartjs-2";
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, PointElement, LineElement, Tooltip, Legend } from "chart.js";
import { api } from "../api/client";
import { Empty } from "../components/ui";
import { formatDate, formatPercent, formatQty, MOVEMENT_LABELS, labelOf } from "../lib/format";

ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, LineElement, Tooltip, Legend);

type Dash = {
  active_works: number;
  low_stock: { material_id: number; material_name: string; on_hand: string; reorder_point: string; unit_code: string }[];
  pending_orders: number;
  transfers_in_transit: number;
  comparable_totals: boolean;
  total_unit: string | null;
  theoretical_qty: string | null;
  real_qty: string | null;
  absolute_difference: string | null;
  percent_deviation: string | null;
  percent_status: string;
  review_required: boolean;
  by_work: { name: string; theoretical: string; real: string }[];
  by_rubric: { name: string; theoretical: string; real: string }[];
  top_deviations: { material_name: string; task_name: string; absolute_difference: string; percent_status: string; percent_deviation: string | null }[];
  evolution: { period: string; theoretical: string; real: string }[];
  stock_by_location: { name: string; on_hand: string }[];
  recent_movements: { id: number; occurred_at: string; movement_type: string; material_name: string; location_name: string; signed_qty: string; recorded_by: string }[];
};

const colors = { theoretical: "#0f4c5c", real: "#c2410c" };

export function DashboardPage() {
  const [works, setWorks] = useState<{ items: { id: number; name: string }[] }>({ items: [] });
  const [workId, setWorkId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [data, setData] = useState<Dash | null>(null);

  useEffect(() => {
    api<{ items: { id: number; name: string }[] }>("/api/works?page_size=100").then(setWorks).catch(() => undefined);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams();
    if (workId) params.set("work_id", workId);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    api<Dash>(`/api/dashboard?${params.toString()}`).then(setData).catch(() => setData(null));
  }, [workId, dateFrom, dateTo]);

  if (!data) return <p>Cargando el resumen…</p>;
  const diff = Number(data.absolute_difference);

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Inicio</h1>
          <p>Situación operativa con los datos cargados. Los gráficos aparecen cuando hay movimientos reales.</p>
        </div>
      </div>
      <div className="toolbar">
        <select className="search" aria-label="Obra" value={workId} onChange={(event) => setWorkId(event.target.value)}>
          <option value="">Todas las obras</option>
          {works.items.map((work) => <option key={work.id} value={work.id}>{work.name}</option>)}
        </select>
        <input className="search" aria-label="Desde" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
        <input className="search" aria-label="Hasta" type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
      </div>
      <div className="grid grid-4">
        <article className="card kpi"><span>Obras activas</span><strong>{data.active_works}</strong></article>
        <article className="card kpi"><span>Órdenes por recibir</span><strong>{data.pending_orders}</strong><Link to="/ordenes">Ver órdenes</Link></article>
        <article className="card kpi"><span>Transferencias en tránsito</span><strong>{data.transfers_in_transit}</strong><Link to="/transferencias">Ver traslados</Link></article>
        <article className="card kpi"><span>Materiales bajo umbral</span><strong>{data.low_stock.length}</strong><em>Solo si el material tiene umbral</em></article>
      </div>
      <div className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card kpi"><span>Consumo teórico</span><strong>{formatQty(data.theoretical_qty)}</strong></article>
        <article className="card kpi"><span>Consumo real</span><strong>{formatQty(data.real_qty)}</strong></article>
        <article className="card kpi">
          <span>Diferencia real − teórico</span>
          <strong className={diff > 0 ? "up" : diff < 0 ? "down" : "flat"}>{formatQty(data.absolute_difference)}</strong>
          <em>{formatPercent(data.percent_deviation, data.percent_status)}{data.review_required ? " · Requiere revisión" : ""}</em>
        </article>
      </div>
      {data.low_stock.length > 0 ? (
        <div className="panel" style={{ marginTop: 14 }}>
          <h2>Stock bajo</h2>
          <ul>
            {data.low_stock.map((row) => (
              <li key={row.material_id}>{row.material_name}: {formatQty(row.on_hand)} {row.unit_code} (umbral {formatQty(row.reorder_point)})</li>
            ))}
          </ul>
        </div>
      ) : null}
      {data.by_work.length > 0 && !data.comparable_totals ? (
        <div className="panel" style={{ marginTop: 14 }}>
          <p>Hay materiales con unidades distintas. El detalle por material está en Reportes; no se muestra un total único porque las cantidades no se pueden sumar.</p>
        </div>
      ) : null}
      {data.by_work.length === 0 ? (
        <div className="panel" style={{ marginTop: 14 }}>
          <Empty title="Todavía no hay consumo para comparar" text="Creá una obra, configurá el coeficiente de una tarea y registrá un avance y un consumo." action={<Link className="btn" to="/obras">Ir a obras</Link>} />
        </div>
      ) : data.comparable_totals ? (
        <div className="grid grid-2" style={{ marginTop: 14 }}>
          <div className="panel">
            <h2>Teórico y real por obra</h2>
            <Bar data={{
              labels: data.by_work.map((row) => row.name),
              datasets: [
                { label: "Teórico", data: data.by_work.map((row) => Number(row.theoretical)), backgroundColor: colors.theoretical },
                { label: "Real", data: data.by_work.map((row) => Number(row.real)), backgroundColor: colors.real },
              ],
            }} />
          </div>
          <div className="panel">
            <h2>Por rubro</h2>
            <Bar data={{
              labels: data.by_rubric.map((row) => row.name),
              datasets: [
                { label: "Teórico", data: data.by_rubric.map((row) => Number(row.theoretical)), backgroundColor: colors.theoretical },
                { label: "Real", data: data.by_rubric.map((row) => Number(row.real)), backgroundColor: colors.real },
              ],
            }} />
          </div>
          {data.evolution.length > 0 ? (
            <div className="panel">
              <h2>Evolución por período</h2>
              <Line data={{
                labels: data.evolution.map((row) => row.period),
                datasets: [
                  { label: "Teórico", data: data.evolution.map((row) => Number(row.theoretical)), borderColor: colors.theoretical, backgroundColor: colors.theoretical },
                  { label: "Real", data: data.evolution.map((row) => Number(row.real)), borderColor: colors.real, backgroundColor: colors.real },
                ],
              }} />
            </div>
          ) : null}
          {data.stock_by_location.length > 0 ? (
            <div className="panel">
              <h2>Stock por ubicación</h2>
              <Bar data={{
                labels: data.stock_by_location.map((row) => row.name),
                datasets: [{ label: "Disponible", data: data.stock_by_location.map((row) => Number(row.on_hand)), backgroundColor: "#57534e" }],
              }} />
            </div>
          ) : null}
        </div>
      ) : null}
      <div className="panel" style={{ marginTop: 14 }}>
        <h2>Mayores desvíos absolutos</h2>
        {data.top_deviations.length === 0 ? <p className="hint">Sin diferencias para el filtro elegido.</p> : (
          <table>
            <thead><tr><th>Tarea</th><th>Material</th><th>Diferencia</th><th>Desvío</th></tr></thead>
            <tbody>
              {data.top_deviations.map((row) => (
                <tr key={`${row.task_name}-${row.material_name}`}>
                  <td>{row.task_name}</td>
                  <td>{row.material_name}</td>
                  <td>{formatQty(row.absolute_difference)}</td>
                  <td>{formatPercent(row.percent_deviation, row.percent_status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="hint">Un desvío positivo indica que el consumo real supera al teórico. No implica por sí solo desperdicio ni faltante.</p>
      </div>
      <div className="panel" style={{ marginTop: 14 }}>
        <h2>Últimos movimientos</h2>
        {data.recent_movements.length === 0 ? <p className="hint">Cuando registres una recepción, un consumo o un traslado, van a aparecer acá.</p> : (
          <table>
            <thead><tr><th>Fecha</th><th>Tipo</th><th>Material</th><th>Ubicación</th><th>Cantidad</th><th>Responsable</th></tr></thead>
            <tbody>
              {data.recent_movements.map((row) => (
                <tr key={row.id}>
                  <td>{formatDate(row.occurred_at)}</td>
                  <td>{labelOf(row.movement_type, MOVEMENT_LABELS)}</td>
                  <td>{row.material_name}</td>
                  <td>{row.location_name}</td>
                  <td>{formatQty(row.signed_qty)}</td>
                  <td>{row.recorded_by}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
