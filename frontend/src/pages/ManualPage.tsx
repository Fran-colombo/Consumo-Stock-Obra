export function ManualPage() {
  return (
    <section className="manual">
      <div className="page-head">
        <div>
          <h1>Manual de uso</h1>
          <p>Cada cosa se hace en un solo lugar. Si algo sale bien o mal, aparece un aviso y hay que cerrarlo.</p>
        </div>
      </div>
      <div className="panel">
        <h2>Cómo se empieza</h2>
        <ol>
          <li>En Materiales, cargá lo que se usa. “Avisar cuando quede menos de” no es lo que hay: es el mínimo. Si el disponible baja de ese número, Inicio lo marca. Lo que hay se ve en Inventario.</li>
          <li>En Fórmulas para tareas elegís el caso. Ya vienen cargados un muro, un revoque, un hormigón H21 y un contrapiso de cascote, con la dosificación publicada. Si un número no te sirve, lo cambiás. Cada caso dice en qué se mide y qué hay que completar: lo que multiplica entra en la cuenta, lo que resta se descuenta y lo que se anota no cambia el resultado. El espesor del volumen se escribe en centímetros. El margen es aparte: si dice 10, la lista suma un 10 %. No hay precios.</li>
          <li>La tarea se crea en Rubros y tareas o en la obra. Elegís el caso y completás sus medidas. Arriba ves la superficie o el volumen neto, y debajo cuánto haría falta de cada material. Si falta una medida que multiplica, lo dice y no calcula. El margen de esa tarea se puede cambiar. Queda pendiente.</li>
        </ol>
        <p>Crear la tarea no mueve stock. Al registrar un avance, si la tarea tiene materiales, aparece un aviso con lo que se va a usar y, al confirmar, eso sale del stock de la obra. También podés pasar la tarea a en proceso, trabajando o completado.</p>

        <h2>Comprar</h2>
        <p>En Órdenes de compra cargás proveedor, obra y una o varias líneas de material y cantidad. La orden queda pendiente. En la misma tarjeta está el paso que sigue, y vale para todos los materiales:</p>
        <ul>
          <li><strong>Encargar.</strong> Ya se pidió. Todavía no hay stock.</li>
          <li><strong>Llegó.</strong> Entra al stock de la obra. Si la orden tiene un solo material, podés anotar cuánto llegó. Si tiene varios, llega lo pedido de cada uno.</li>
          <li><strong>Se usaron.</strong> Elegís la tarea y sale del stock lo que llegó de cada material. Si no alcanza, el aviso lo dice y no descuenta.</li>
        </ul>

        <h2>Transferir stock</h2>
        <p>Origen, destino, material y cantidad. Un botón mueve el stock. Si no llegó todo, marcá “Llegó menos” y decí si el faltante volvió, se perdió o llegó igual.</p>

        <h2>Contar lo que hay</h2>
        <p>En Inventario, el conteo físico deja el disponible en la cantidad que contaste. El aviso dice cuánto quedó y dónde. Si no se puede, el aviso dice por qué.</p>

        <h2>Quién puede corregir</h2>
        <p>El operador deja un movimiento nuevo si se equivoca. El administrador puede corregir o anular un documento confirmado, con un motivo. Eso queda en Configuración, en la auditoría, y no se borra.</p>
      </div>
    </section>
  );
}
