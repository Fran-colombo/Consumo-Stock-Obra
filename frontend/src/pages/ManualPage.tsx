export function ManualPage() {
  return (
    <section className="manual">
      <div className="page-head">
        <div>
          <h1>Manual de uso</h1>
          <p>Qué hace cada pantalla y en qué orden se carga la información.</p>
        </div>
      </div>
      <div className="panel">
        <h2>Índice</h2>
        <nav className="toc">
          <a href="#para-que">Para qué sirve</a>
          <a href="#ingreso">Ingreso y roles</a>
          <a href="#orden">Orden para empezar</a>
          <a href="#obras">Obras</a>
          <a href="#rubros">Rubros, tareas, coeficientes y avances</a>
          <a href="#materiales">Materiales</a>
          <a href="#inventario">Inventario</a>
          <a href="#consumos">Consumos reales</a>
          <a href="#ordenes">Órdenes de compra y recepciones</a>
          <a href="#transferencias">Transferencias</a>
          <a href="#comparacion">Teórico contra real</a>
          <a href="#reportes">Inicio y reportes</a>
          <a href="#configuracion">Configuración</a>
          <a href="#errores">Cómo se corrige un error</a>
        </nav>

        <h2 id="para-que">Para qué sirve</h2>
        <p>
          Consumo Stock en Obra lleva el stock de materiales por ubicación y lo compara con lo que cada tarea debería haber consumido según el avance ejecutado.
          El teórico no sale de una receta precargada: el coeficiente lo carga quien usa el sistema, tarea por tarea.
        </p>
        <p>El stock no se deduce de las compras ni de los pedidos. Cambia solo cuando se confirma un movimiento: una recepción, un consumo, un despacho, la llegada de un traslado o un conteo físico.</p>

        <h2 id="ingreso">Ingreso y roles</h2>
        <p>Se entra con el correo y la contraseña. El ojo al lado de la clave la muestra o la vuelve a ocultar. Cada movimiento queda a nombre de la persona que inició sesión.</p>
        <p>Hay dos roles:</p>
        <ul>
          <li><strong>Operador.</strong> Carga obras, materiales, avances, consumos, compras y traslados. Si se equivoca en un consumo, registra un movimiento de corrección. No borra el registro original.</li>
          <li><strong>Administrador.</strong> Hace lo mismo y, además, puede corregir o anular un documento ya confirmado. Tiene que escribir el motivo. El cambio queda en la auditoría, con el valor anterior. Esa auditoría no se borra.</li>
        </ul>

        <h2 id="orden">Orden para empezar</h2>
        <ol>
          <li>En Configuración, creá el galpón u otras ubicaciones que no sean una obra. Cada obra crea sola su ubicación de stock.</li>
          <li>En Materiales, cargá el catálogo. Es el mismo para el galpón y para todas las obras.</li>
          <li>En Rubros y tareas, creá los rubros. Son compartidos. Las tareas no se crean ahí: se crean dentro de cada obra.</li>
          <li>En Obras, creá la obra y abrila. En la pestaña Rubros y tareas, creá la tarea, cargá el coeficiente de cada material y registrá el avance.</li>
          <li>Cuando el material llega, registrá la recepción de la orden o el traslado. Recién ahí entra al stock.</li>
          <li>En Consumos, cargá lo que se usó de verdad, ligado a la tarea. Eso es el consumo real y es lo que descuenta el stock.</li>
        </ol>

        <h2 id="obras">Obras</h2>
        <p>Una obra es el lugar donde se ejecutan las tareas. Al crearla se le asigna una ubicación de stock propia. El código y el nombre identifican la obra. La dirección, la fecha de inicio y las observaciones son datos de referencia.</p>
        <p>Los estados son Planificada, Activa, Pausada, Finalizada y Cancelada. El estado no bloquea los movimientos: se puede seguir cargando aunque la obra figure pausada o finalizada. Sirve para filtrar y para el conteo de obras activas del inicio.</p>
        <p>Abrir una obra muestra ocho pestañas: Resumen, Rubros y tareas, Consumo teórico, Consumo real, Stock, Órdenes, Transferencias e Historial. Desde ahí se ve esa obra sin mezclarla con las demás.</p>

        <h2 id="rubros">Rubros, tareas, coeficientes y avances</h2>
        <h3>Rubro</h3>
        <p>El rubro agrupa tareas del mismo tipo de trabajo, por ejemplo hormigón o mampostería. El catálogo de rubros es uno solo para todas las obras. Se crea en Rubros y tareas, con nombre y código. La lista de la derecha muestra las tareas ya creadas y se puede filtrar por obra. Esa pantalla no crea la tarea.</p>
        <h3>Tarea</h3>
        <p>La tarea pertenece a una obra. Se crea en la obra, pestaña Rubros y tareas: nombre, rubro, unidad de la tarea y, si se conoce, la cantidad planificada. La unidad de la tarea es la de la ejecución, por ejemplo metro cúbico. No es la unidad del material.</p>
        <h3>Coeficiente</h3>
        <p>
          El coeficiente dice cuánto material corresponde por cada unidad ejecutada de esa tarea. Se carga en la misma tarjeta de la tarea: material, coeficiente y unidad de salida.
          Dejá la unidad de salida en “Unidad de inventario”, que es la unidad con la que el material está en el catálogo.
        </p>
        <p>
          El teórico de un avance es el coeficiente por la cantidad ejecutada. Si cargás 6 bolsas por metro cúbico y después registrás 10 metros cúbicos, el teórico de ese avance queda en 60 bolsas.
          Ese 6 es un número que escribís vos: el sistema no trae coeficientes de construcción.
        </p>
        <p>Cada material se carga una vez por tarea. Si intentás agregarlo de nuevo, el sistema avisa que la regla ya existe. Un avance ya guardado conserva el coeficiente con el que se calculó. Una versión nueva de la regla vale para los avances siguientes y no reescribe los anteriores.</p>
        <h3>Avance</h3>
        <p>El avance es lo ejecutado de la tarea. No descuenta stock. Solo actualiza lo ejecutado y congela las líneas teóricas de ese tramo.</p>
        <ul>
          <li><strong>Cantidad de este avance:</strong> lo que se hizo en esta carga. Se suma a lo ya ejecutado.</li>
          <li><strong>Nuevo total acumulado:</strong> el total que debería figurar hasta hoy. El sistema registra solo la diferencia contra lo ya ejecutado. No completes los dos a la vez.</li>
          <li><strong>Fecha:</strong> el día del avance. Si la dejás vacía, usa la fecha de hoy.</li>
        </ul>
        <p>La pestaña Consumo teórico muestra, por tarea, las líneas calculadas a partir de esos avances. No es el material usado: es lo que correspondía usar.</p>

        <h2 id="materiales">Materiales</h2>
        <p>El catálogo es único. Un cemento cargado ahí se puede comprar, trasladar, tener en el galpón y consumir en cualquier obra. No hace falta duplicarlo por obra.</p>
        <ul>
          <li><strong>Unidad de inventario:</strong> la unidad en la que se cuenta el stock. Las que vienen de inicio son kilogramo, bolsa, metro cúbico, metro cuadrado, metro, litro y unidad. Cada una tiene una cantidad de decimales. Una unidad entera, como la bolsa, no acepta fracciones.</li>
          <li><strong>Categoría y descripción:</strong> sirven para ordenar y buscar. No entran en el cálculo.</li>
          <li><strong>Umbral de stock:</strong> si lo cargás, el inicio avisa cuando el disponible de ese material queda por debajo. Si lo dejás vacío, ese material no entra en “bajo umbral”.</li>
        </ul>

        <h2 id="inventario">Inventario</h2>
        <p>Muestra el stock por material y por ubicación. Las columnas no se suman entre sí:</p>
        <ul>
          <li><strong>Disponible:</strong> lo que está físicamente en esa ubicación. Es lo que se puede consumir o despachar.</li>
          <li><strong>Pendiente:</strong> lo pedido en órdenes confirmadas que todavía no se recibió. No está en el depósito.</li>
          <li><strong>Sale en tránsito:</strong> lo que ya salió del origen en un traslado y todavía no llegó.</li>
          <li><strong>Entra en tránsito:</strong> lo que está viajando hacia esta ubicación.</li>
        </ul>
        <p>El conteo físico corrige el disponible cuando lo contado no coincide con el sistema. Elegís material, ubicación, la cantidad contada y el motivo. El sistema registra la diferencia entre lo que había y lo que contaste. No reemplaza una recepción ni un consumo: es un ajuste, y queda en la lista de ajustes y en los movimientos.</p>

        <h2 id="consumos">Consumos reales</h2>
        <p>El consumo es el material que se usó. Se carga en Consumos, o en la pestaña Consumo real de la obra. Hay que indicar obra, tarea de esa obra, material, ubicación de la que sale y cantidad. Al elegir la obra, la ubicación se completa con la de esa obra; se puede cambiar si el material salió de otro lado.</p>
        <p>Antes de guardar, la pantalla muestra el disponible de ese material en esa ubicación. Si la cantidad supera el disponible, el botón queda deshabilitado. Por defecto no se permite stock negativo. El responsable del registro es quien está conectado.</p>
        <p>Comprar o recibir material no crea un consumo. Si no cargás el consumo, el stock sigue en la ubicación y el teórico no tiene contra qué compararse.</p>

        <h2 id="ordenes">Órdenes de compra y recepciones</h2>
        <p>La orden dice qué se le pidió a un proveedor, cuánto, a qué obra está prevista y en qué ubicación se espera depositarlo. El precio y la moneda son opcionales. Crear la orden la deja en borrador y no suma stock.</p>
        <ol>
          <li>Si el proveedor no está, escribilo arriba y usá Agregar proveedor.</li>
          <li>Completá la orden y usá Crear borrador.</li>
          <li>Abrí el detalle y usá Confirmar orden. Recién confirmada se puede recibir. Lo confirmado y no recibido figura como pendiente.</li>
          <li>En Registrar recepción, indicá la ubicación donde se deposita y la cantidad de cada material. Se puede recibir una parte. Lo que no llega sigue pendiente y no entra al stock.</li>
        </ol>
        <p>Por defecto no se puede recibir más de lo pedido. Esa política se cambia en Configuración, y solo el administrador.</p>

        <h2 id="transferencias">Transferencias</h2>
        <p>Sirven para mover material entre ubicaciones, por ejemplo del galpón a una obra. El galpón se crea en Configuración como depósito. La obra ya tiene su ubicación.</p>
        <ol>
          <li><strong>Registrar traslado</strong> anota origen, destino, material, cantidad y quién autoriza. Todavía no mueve stock. La pantalla muestra el disponible en el origen.</li>
          <li>Abrí el traslado. <strong>Despachar</strong> descuenta el origen y deja la cantidad en tránsito. Si en el origen no alcanza, el despacho no se confirma.</li>
          <li><strong>Recibir</strong> suma en el destino lo que llegó. Se puede recibir de a partes.</li>
        </ol>
        <p>Si llega menos y marcás “Cerrar con diferencia”, el faltante queda identificado. No se asigna solo al origen ni al destino. Después hay que resolverlo con una de estas tres acciones, y un motivo:</p>
        <ul>
          <li><strong>Devolver al origen:</strong> el faltante vuelve al stock de donde salió.</li>
          <li><strong>Recibir el resto:</strong> el destino termina de incorporar lo que faltaba.</li>
          <li><strong>Registrar pérdida:</strong> esa cantidad no vuelve a ninguna ubicación.</li>
        </ul>

        <h2 id="comparacion">Teórico contra real</h2>
        <p>La comparación está en el Resumen de la obra, en Inicio y en Reportes. Para que aparezca una fila hacen falta las tres cosas: la tarea con coeficiente, al menos un avance y el consumo real de ese material en esa tarea.</p>
        <ul>
          <li><strong>Ejecutado:</strong> la suma de los avances confirmados de la tarea.</li>
          <li><strong>Teórico:</strong> la suma de las líneas congeladas en esos avances.</li>
          <li><strong>Real:</strong> la suma de los consumos confirmados de ese material en esa tarea.</li>
          <li><strong>Diferencia:</strong> real menos teórico. Si es positiva, se usó más de lo que correspondía. Si es negativa, se usó menos. Si es cero, coinciden.</li>
          <li><strong>Desvío:</strong> esa diferencia en porcentaje sobre el teórico. Si el teórico es cero, el porcentaje no se calcula. Si además el real no es cero, la fila pide revisión, porque no hay base para el porcentaje.</li>
        </ul>
        <p>En Inicio, los totales de teórico y real se muestran solo cuando todas las filas comparadas usan la misma unidad. Si se mezclan bolsas con metros cúbicos, no hay un total único.</p>

        <h2 id="reportes">Inicio y reportes</h2>
        <p>Inicio resume obras activas, órdenes por recibir, traslados en tránsito, materiales bajo el umbral, el teórico contra el real, y los últimos movimientos. Los filtros de obra y de fechas achican ese resumen. Los gráficos aparecen cuando hay datos para dibujar.</p>
        <p>Reportes muestra la misma comparación y la exporta. El archivo usa los filtros que estén puestos en la pantalla. Hay CSV y Excel del teórico contra el real, y CSV de stock, de órdenes y de movimientos.</p>

        <h2 id="configuracion">Configuración</h2>
        <ul>
          <li><strong>Permitir stock negativo.</strong> Desactivada. Si se activa, un consumo o un despacho puede dejar el disponible debajo de cero.</li>
          <li><strong>Permitir recibir más de lo pedido.</strong> Desactivada. Si se activa, una recepción puede superar la cantidad de la orden. El excedente se marca.</li>
          <li><strong>Unidades.</strong> Lista de las unidades y cuántos decimales admite cada una.</li>
          <li><strong>Ubicaciones.</strong> El galpón y cualquier depósito que no nazca de una obra. El tipo es Depósito u Otra.</li>
          <li><strong>Usuarios.</strong> Solo el administrador. Se cargan con correo, nombre, clave y rol. El ojo de la clave muestra lo que se está escribiendo. La clave tiene al menos 8 caracteres.</li>
          <li><strong>Auditoría.</strong> Quién hizo cada acción, cuándo y con qué motivo. Incluye las correcciones del administrador. No se puede borrar.</li>
        </ul>

        <h2 id="errores">Cómo se corrige un error</h2>
        <p>Un operador no edita un consumo confirmado. En Consumos usa “Corregir con movimiento”: indica la cantidad a revertir y el motivo. Eso deja un movimiento nuevo, de signo contrario, y el original sigue en la historia.</p>
        <p>El administrador ve “Corregir o anular” en avances, recepciones, consumos, ajustes y traslados confirmados. Puede guardar otra cantidad o anular el documento. Las dos acciones piden un motivo. Al corregir, el stock se reconstruye con el valor nuevo y la auditoría guarda el anterior y el nuevo.</p>
        <p>Anular no es borrar: el documento queda anulado y deja de sumar en el stock y en la comparación. El registro de que se anuló permanece.</p>
      </div>
    </section>
  );
}
