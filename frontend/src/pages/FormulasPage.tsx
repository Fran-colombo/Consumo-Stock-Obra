import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useNotice } from "../components/ui";
import { formatQty } from "../lib/format";

type Rec = Record<string, any>;

export function FormulasPage() {
  const notice = useNotice();
  const [rows, setRows] = useState<Rec[]>([]);
  const [materials, setMaterials] = useState<Rec[]>([]);
  const [units, setUnits] = useState<Rec[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [waste, setWaste] = useState("");
  const [line, setLine] = useState({ material_id: "", coefficient: "" });
  const [parameter, setParameter] = useState({ name: "", unit_id: "", counts: true });
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
    api<Rec[]>("/api/units").then(setUnits);
  }, []);

  useEffect(() => {
    if (!selected) return;
    setWaste(selected.waste_percent && Number(selected.waste_percent) > 0 ? String(Number(selected.waste_percent)) : "");
  }, [selectedId]);

  function replace(updated: Rec) {
    setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)));
  }

  async function createFormula(event: FormEvent) {
    event.preventDefault();
    try {
      const created = await api<Rec>("/api/formulas", { method: "POST", body: JSON.stringify({ name }) });
      setName("");
      load(created.id);
      notice.ok(`Quedó la fórmula ${created.name}. Elegí en qué se mide y armá los parámetros.`);
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo crear la fórmula.");
    }
  }

  async function saveMeasure(measureUnitId: string) {
    if (!selected) return;
    try {
      const updated = await api<Rec>(`/api/formulas/${selected.id}`, {
        method: "PATCH",
        body: JSON.stringify({ measure_unit_id: measureUnitId ? Number(measureUnitId) : null }),
      });
      replace(updated);
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo guardar la medida.");
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
      replace(updated);
      notice.ok(Number(updated.waste_percent) > 0 ? `El cálculo suma ${formatQty(updated.waste_percent)} % de margen.` : "El cálculo no suma margen.");
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo guardar el margen.");
    }
  }

  async function addParameter(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    try {
      const updated = await api<Rec>(`/api/formulas/${selected.id}/parameters`, {
        method: "POST",
        body: JSON.stringify({ name: parameter.name, unit_id: Number(parameter.unit_id), counts: parameter.counts }),
      });
      replace(updated);
      setParameter({ name: "", unit_id: "", counts: true });
      notice.ok(parameter.counts ? `${parameter.name} entra en la cuenta.` : `${parameter.name} se anota y no cambia la cuenta.`);
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo agregar el parámetro.");
    }
  }

  async function removeParameter(parameterId: number) {
    if (!selected) return;
    try {
      const updated = await api<Rec>(`/api/formulas/${selected.id}/parameters/${parameterId}`, { method: "DELETE" });
      replace(updated);
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo sacar el parámetro.");
    }
  }

  async function addLine(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    if (!selected.measure_unit_id) {
      notice.fail("Elegí en qué se mide esta fórmula.");
      return;
    }
    try {
      const updated = await api<Rec>(`/api/formulas/${selected.id}/lines`, {
        method: "POST",
        body: JSON.stringify({ material_id: Number(line.material_id), coefficient: line.coefficient }),
      });
      replace(updated);
      setLine({ material_id: "", coefficient: "" });
      notice.ok(`Quedó en la fórmula, por cada ${selected.measure_unit_name}.`);
    } catch (err) {
      notice.fail(err instanceof ApiError ? err.message : "No se pudo guardar el material.");
    }
  }

  const measureName = selected?.measure_unit_name as string | undefined;

  return (
    <section>
      {notice.dialog}
      <div className="page-head">
        <div>
          <h1>Fórmulas para tareas</h1>
          <p>Elegís en qué se mide y armás los parámetros vacíos. Cada material es cuánto lleva por cada 1 de esa medida.</p>
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
                <div className="hint">{row.measure_unit_name || "Sin medida"}</div>
              </button>
            ))}
          </div>
        </div>
        {selected ? (
          <div className="panel">
            <h2>{selected.name}</h2>
            <div className="field">
              <label>Se mide en</label>
              <select value={selected.measure_unit_id || ""} onChange={(event) => saveMeasure(event.target.value)}>
                <option value="">Elegir</option>
                {units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
              </select>
              <span className="hint">{measureName ? `La cuenta da ${measureName}.` : "Hasta que no elijas la medida, la fórmula no calcula. Si falta una unidad, creala en Configuración."}</span>
            </div>
            <h3>Parámetros</h3>
            <p className="hint">Cada uno tiene nombre y unidad. Si entra en la cuenta, multiplica. Si no, se anota y el resultado no cambia.</p>
            {selected.parameters?.length ? (
              <ul>
                {selected.parameters.map((item: Rec) => (
                  <li key={item.id}>
                    {item.name} ({item.unit_name}) {item.counts ? "· entra en la cuenta" : "· solo se anota"}
                    {" "}
                    <button className="action ghost" type="button" onClick={() => removeParameter(item.id)}>Sacar</button>
                  </li>
                ))}
              </ul>
            ) : <p className="hint">Todavía no tiene parámetros.</p>}
            <form className="form-grid" onSubmit={addParameter}>
              <div className="field"><label>Nombre</label><input required value={parameter.name} onChange={(event) => setParameter({ ...parameter, name: event.target.value })} /></div>
              <div className="field"><label>Unidad</label>
                <select required value={parameter.unit_id} onChange={(event) => setParameter({ ...parameter, unit_id: event.target.value })}>
                  <option value="">Elegir</option>
                  {units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
                </select>
              </div>
              <label className="check span-2"><input type="checkbox" checked={parameter.counts} onChange={(event) => setParameter({ ...parameter, counts: event.target.checked })} /> Entra en la cuenta</label>
              <div className="span-2"><button className="action secondary" type="submit">Agregar parámetro</button></div>
            </form>
            <form className="form-grid" onSubmit={saveWaste}>
              <div className="field"><label>Margen, si hace falta</label><input value={waste} placeholder="0" onChange={(event) => setWaste(event.target.value)} /></div>
              <div><button className="action secondary" type="submit">Guardar margen</button></div>
            </form>
            <h3>{measureName ? `Por cada ${measureName}` : "Materiales"}</h3>
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
              <div className="field"><label>Cuánto por cada 1</label><input required value={line.coefficient} onChange={(event) => setLine({ ...line, coefficient: event.target.value })} /></div>
              <div className="span-2"><button className="action secondary" type="submit">Guardar en la fórmula</button></div>
            </form>
          </div>
        ) : <div className="panel"><p className="hint">Creá la primera fórmula.</p></div>}
      </div>
    </section>
  );
}
