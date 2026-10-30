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
          <li>En Fórmulas para tareas, elegí en qué se mide: metro, metro cuadrado, metro cúbico, unidad, u otra que crees en Configuración. Hasta que no elijas, la fórmula no calcula. Ahí armás los parámetros, vacíos: cada uno tiene nombre, unidad, y si entra en la cuenta. Un contrapiso en metros cúbicos puede ser Largo, Ancho y Espesor. Una medida lineal puede ser solo Largo. Por unidad, una Cantidad. Si un dato no entra en la cuenta, se anota y no cambia el resultado. Después cargás los materiales: cuánto lleva por cada 1 de esa medida, en la unidad de cada material. Esos números los escribís vos. El margen es opcional: si ponés 10, el cálculo suma un 10 %. Si lo dejás vacío, no suma nada.</li>
          <li>La tarea se crea en Rubros y tareas o en la obra. Elegís la fórmula y completás sus parámetros. La cantidad es el producto de los que entran en la cuenta. Si falta uno, la pantalla lo dice y no calcula materiales. Cada material es su coeficiente por esa cantidad, y por el margen si hay. Queda pendiente.</li>
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
