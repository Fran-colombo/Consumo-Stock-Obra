import { useEffect, useState } from "react";
import { downloadFile, api } from "../api/client";
import { Empty } from "../components/ui";
import { formatPercent, formatQty } from "../lib/format";

type Rec = Record<string, any>;

export function ReportsPage() {
  const [works, setWorks] = useState<Rec[]>([]);
  const [workId, setWorkId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [rows, setRows] = useState<Rec[]>([]);

  useEffect(() => {
    api<{ items: Rec[] }>("/api/works?page_size=100").then((data) => setWorks(data.items));
  }, []);
  useEffect(() => {
    const params = new URLSearchParams();
    if (workId) params.set("work_id", workId);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    api<Rec[]>(`/api/comparisons?${params}`).then(setRows);
  }, [workId, dateFrom, dateTo]);

  function exportReport(kind: string, format: string) {
    const params = new URLSearchParams({ format });
    if (workId) params.set("work_id", workId);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    downloadFile(`/api/reports/${kind}?${params}`, `${kind}.${format}`);
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Reportes</h1>
          <p>La exportación usa los mismos filtros y cálculos que esta pantalla.</p>
        </div>
      </div>
      <div className="toolbar">
        <select aria-label="Obra" value={workId} onChange={(event) => setWorkId(event.target.value)}>
          <option value="">Todas las obras</option>
          {works.map((work) => <option key={work.id} value={work.id}>{work.name}</option>)}
        </select>
        <input aria-label="Desde" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
        <input aria-label="Hasta" type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
        <button className="action secondary" type="button" onClick={() => exportReport("teorico-real", "csv")}>CSV teórico vs real</button>
        <button className="action secondary" type="button" onClick={() => exportReport("teorico-real", "xlsx")}>Excel teórico vs real</button>
        <button className="action ghost" type="button" onClick={() => exportReport("stock", "csv")}>CSV stock</button>
        <button className="action ghost" type="button" onClick={() => exportReport("ordenes", "csv")}>CSV órdenes</button>
        <button className="action ghost" type="button" onClick={() => exportReport("movimientos", "csv")}>CSV movimientos</button>
      </div>
      <div className="panel table-wrap">
        {rows.length === 0 ? <Empty title="No hay datos para esos filtros" text="Cuando existan avances y consumos, la comparación va a aparecer acá y en el archivo exportado." /> : (
          <table>
            <thead><tr><th>Obra</th><th>Rubro</th><th>Tarea</th><th>Material</th><th>Unidad</th><th>Ejecutado</th><th>Teórico</th><th>Real</th><th>Diferencia</th><th>Desvío</th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.task_id}-${row.material_id}`}>
                  <td>{row.work_name}</td>
                  <td>{row.rubric_name}</td>
                  <td>{row.task_name}</td>
                  <td>{row.material_name}</td>
                  <td>{row.unit_code}</td>
                  <td>{formatQty(row.executed_qty)}</td>
                  <td>{formatQty(row.theoretical_qty)}</td>
                  <td>{formatQty(row.real_qty)}</td>
                  <td>{formatQty(row.absolute_difference)}</td>
                  <td>{formatPercent(row.percent_deviation, row.percent_status)}{row.review_required ? " · Requiere revisión" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
