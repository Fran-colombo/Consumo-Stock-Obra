import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useNotice } from "../components/ui";
import { formatQty } from "../lib/format";

type Rec = Record<string, any>;

export function FormulasPage() {
  const notice = useNotice();
  const [rows, setRows] = useState<Rec[]>([]);
  const [materials, setMaterials] = useState<Rec[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [waste, setWaste] = useState("");
  const [line, setLine] = useState({ material_id: "", coefficient: "" });
  const selected = rows.find((row) => row.id === selectedId) || null;

  function load(keepId?: number | null) {
    api<Rec[]>("/api/formulas").then((data) => {
      setRows(data);
      setSelectedId((current) => keepId ?? current ?? data[0]?.id ?? null);
    });
  }

  useEffect(() => {
    load();
    api<{ items: Rec[] }>("/api/materials?page_size=100").then((data) => setMaterials(data.items));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setWaste(selected.waste_percent && Number(selected.waste_percent) > 0 ? String(Number(selected.waste_percent)) : "");
  }, [selectedId]);

  async function createFormula(event: FormEvent) {
    event.preventDefault();
    try {
      const created = await api<Rec>("/api/formulas", { method: "POST", body: JSON.stringify({ name }) });
      setName("");
      load(created.id);
      notice.ok(`Quedó la fórmula ${created.name}. Ahora cargá cuánto lleva por metro cúbico.`);
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo crear la fórmula.");
    }
  }

  async function saveWaste(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    try {
      const updated = await api<Rec>(`/api/formulas/${selected.id}`, {
        method: "PATCH",
        body: JSON.stringify({ waste_percent: waste || "0" }),
      });
      setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      notice.ok(Number(updated.waste_percent) > 0 ? `El cálculo suma ${formatQty(updated.waste_percent)} % de margen.` : "El cálculo no suma margen.");
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo guardar el margen.");
    }
  }

  async function addLine(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    try {
      const updated = await api<Rec>(`/api/formulas/${selected.id}/lines`, {
        method: "POST",
        body: JSON.stringify({ material_id: Number(line.material_id), coefficient: line.coefficient }),
      });
      setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      setLine({ material_id: "", coefficient: "" });
      notice.ok("Quedó en la fórmula, por cada metro cúbico.");
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo guardar el material.");
    }
  }

  return (
    <section>
      {notice.dialog}
      <div className="page-head">
        <div>
          <h1>Fórmulas para tareas</h1>
          <p>Cada fórmula dice qué materiales lleva un metro cúbico. Al crear la tarea, elegís cuál usar.</p>
        </div>
      </div>
      <div className="grid grid-2">
        <div className="panel">
          <h2>Fórmulas</h2>
          <form className="form-grid" onSubmit={createFormula}>
            <div className="field span-2"><label>Nombre</label><input required value={name} onChange={(event) => setName(event.target.value)} /></div>
            <div className="span-2"><button className="action" type="submit">Crear fórmula</button></div>
          </form>
          <div className="choice" style={{ marginTop: 14 }}>
            {rows.map((row) => (
              <button key={row.id} type="button" className={row.id === selectedId ? "active" : ""} onClick={() => { setSelectedId(row.id); setWaste(row.waste_percent && Number(row.waste_percent) > 0 ? String(Number(row.waste_percent)) : ""); }}>
                <strong>{row.name}</strong>
                <div className="hint">{row.lines?.length ? `${row.lines.length} ${row.lines.length === 1 ? "material" : "materiales"}` : "Sin materiales"}</div>
              </button>
            ))}
          </div>
        </div>
        {selected ? (
          <div className="panel">
            <h2>{selected.name}</h2>
            <p className="hint">Los números los cargás vos, en la unidad de cada material.</p>
            <form className="form-grid" onSubmit={saveWaste}>
              <div className="field"><label>Margen, si hace falta</label><input value={waste} placeholder="0" onChange={(event) => setWaste(event.target.value)} /></div>
              <div><button className="action secondary" type="submit">Guardar margen</button></div>
            </form>
            <h3>Por cada m³</h3>
            {selected.lines?.length ? (
              <ul>{selected.lines.map((item: Rec) => <li key={item.id}>{formatQty(item.coefficient)} {item.unit_name} de {item.material_name}</li>)}</ul>
            ) : <p className="hint">Todavía no tiene materiales.</p>}
            <form className="form-grid" onSubmit={addLine}>
              <div className="field"><label>Material</label>
                <select required value={line.material_id} onChange={(event) => setLine({ ...line, material_id: event.target.value })}>
                  <option value="">Elegir</option>
                  {materials.filter((row) => row.is_active).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                </select>
              </div>
              <div className="field"><label>Cuánto por m³</label><input required value={line.coefficient} onChange={(event) => setLine({ ...line, coefficient: event.target.value })} /></div>
              <div className="span-2"><button className="action secondary" type="submit">Guardar en la fórmula</button></div>
            </form>
          </div>
        ) : <div className="panel"><p className="hint">Creá la primera fórmula.</p></div>}
      </div>
    </section>
  );
}
