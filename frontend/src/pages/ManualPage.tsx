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
          <li>En Rubros y tareas, creá el rubro y elegí en qué se mide, por ejemplo metros cuadrados. Cargá una vez qué usa: 2 baldes de arena, 3 de cemento y 1 de agua por cada unidad. Esos números los escribís vos.</li>
          <li>En el mismo rubro, creá la tarea: obra, cuánto hay que cubrir y por qué queda pendiente. Puede faltar material, haber otras prioridades, o haber que hacer algo antes. El sistema calcula lo que hace falta y no pide la receta otra vez.</li>
        </ol>
        <p>Crear la tarea no mueve stock. El stock cambia cuando el material llega o cuando se marca que se usó.</p>

        <h2>Comprar</h2>
        <p>En Órdenes de compra cargás proveedor, obra, material y cantidad. La orden queda pendiente. En la misma tarjeta está el único paso que sigue:</p>
        <ul>
          <li><strong>Encargar.</strong> Ya se pidió. Todavía no hay stock.</li>
          <li><strong>Llegó.</strong> Entra al stock de la obra. Si anotás una cantidad menor, llega solo esa parte.</li>
          <li><strong>Se usaron.</strong> Elegís la tarea y esa cantidad sale del stock. Si no alcanza, el aviso lo dice y no descuenta.</li>
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
