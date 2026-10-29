import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { Empty, ErrorText } from "../components/ui";
import { formatQty } from "../lib/format";

type Rec = Record<string, any>;

export function MaterialsPage() {
  const [rows, setRows] = useState<Rec[]>([]);
  const [units, setUnits] = useState<Rec[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({ name: "", code: "", unit_id: "", category: "", reorder_point: "", description: "" });

  function load() {
    const params = new URLSearchParams({ page_size: "100" });
    if (q) params.set("q", q);
    api<{ items: Rec[] }>(`/api/materials?${params}`).then((data) => setRows(data.items));
    api<Rec[]>("/api/units").then(setUnits);
  }
  useEffect(load, [q]);

  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/api/materials", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          code: form.code,
          unit_id: Number(form.unit_id),
          category: form.category || null,
          description: form.description || null,
          reorder_point: form.reorder_point || null,
        }),
      });
      setForm({ name: "", code: "", unit_id: "", category: "", reorder_point: "", description: "" });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear el material.");
    }
  }

  return (
    <section>
      <div className="page-head"><div><h1>Materiales</h1><p>Catálogo único para el galpón y todas las obras.</p></div></div>
      {error ? <ErrorText error={error} /> : null}
      <form className="panel form-grid" onSubmit={create}>
        <div className="field"><label htmlFor="mn">Nombre</label><input id="mn" required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></div>
        <div className="field"><label htmlFor="mc">Código</label><input id="mc" required value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} /></div>
        <div className="field"><label htmlFor="mu">Unidad de inventario</label>
          <select id="mu" required value={form.unit_id} onChange={(event) => setForm({ ...form, unit_id: event.target.value })}>
            <option value="">Elegir</option>
            {units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
          </select>
        </div>
        <div className="field"><label htmlFor="mcat">Categoría</label><input id="mcat" value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} /></div>
        <div className="field"><label htmlFor="mth">Umbral de stock</label><input id="mth" value={form.reorder_point} onChange={(event) => setForm({ ...form, reorder_point: event.target.value })} /></div>
        <div className="field"><label htmlFor="md">Descripción</label><input id="md" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
        <div className="span-2"><button className="btn" type="submit">Agregar al catálogo</button></div>
      </form>
      <div className="toolbar" style={{ marginTop: 14 }}>
        <input className="search" aria-label="Buscar material" placeholder="Buscar" value={q} onChange={(event) => setQ(event.target.value)} />
      </div>
      <div className="panel table-wrap">
        {rows.length === 0 ? <Empty title="El catálogo está vacío" text="Cargá los materiales reales de Conkreto. No hay coeficientes precargados." /> : (
          <table>
            <thead><tr><th>Código</th><th>Nombre</th><th>Categoría</th><th>Unidad</th><th>Umbral</th><th>Estado</th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}><td>{row.code}</td><td>{row.name}</td><td>{row.category || "—"}</td><td>{row.unit_name}</td><td>{formatQty(row.reorder_point)}</td><td>{row.is_active ? "Activo" : "Inactivo"}</td></tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
