La Gramática del Papel y la Referencia (RRG) utiliza de manera predeterminada la notación binaria de argumentos **`x, y`** debido a que su sistema de **descomposición léxica** postula que todos los verbos se definen a partir de predicados de estado y de actividad básicos que son, como máximo, bivalentes (de dos lugares). RRG no asume la existencia de predicados primitivos triargumentales (trivalentes) como `vender'(x, y, z)` o `dar'(x, y, z)`.

Cuando nos encontramos con verbos de tres argumentos (como *dar*, *mostrar* o *vender*), RRG los analiza como **estructuras causativas complejas** formadas por la unión de predicados de actividad y de estado mediante el operador conectivo **`CAUSE`**. En estas estructuras compuestas es donde sí se puede observar la notación `x, y, z`, pero estas variables no pertenecen a un único predicado primitivo, sino que se distribuyen en diferentes subpredicados. Por ejemplo, la Estructura Lógica (EL) de *dar* (*give*) se representa como **`[do' (x, Ø)] CAUSE [BECOME have' (y, z)]`**, donde:
*   **`x`** es el argumento de la actividad causante (`do'`).
*   **`y`** y **`z`** son los argumentos del predicado de estado de dos lugares resultante (`have'`).

---

### El Continuum de Relaciones Temáticas de Van Valin

Este diseño se fundamenta en el **continuum de relaciones temáticas (thematic relations continuum)** de Van Valin. En RRG, los roles temáticos tradicionales (como agente, paciente, tema, etc.) no son etiquetas arbitrarias guardadas en el lexicón, sino que **se definen estrictamente a partir de la posición que ocupa un argumento en la Estructura Lógica**.

Este continuum (representado en la Figura 2.3 de la teoría) organiza todas las relaciones semánticas en **cinco posiciones argumentales básicas** derivadas únicamente de predicados monovalentes y bivalentes:

1.  **Argumento de `DO`**: Corresponde al rol de **Agente** (el participante que actúa con voluntad, intención y control).
2.  **Primer argumento de `do' (x, ...)`**: Corresponde al rol de **Efector** y sus subtipos (movedor, creador, ejecutante, emisor de luz/sonido, etc.).
3.  **Primer argumento de `pred' (x, y)`**: Define roles como el de **Poseedor, Experimentador, Cognoscente, Perceptor o Locación**. Estos participantes se sitúan en el centro del continuum porque, aunque no son agentes puros, involucran cierta actividad interna (perceptual, mental o emocional) que los hace más "activos" o "responsables" que sus contrapartes.
4.  **Segundo argumento de `pred' (x, y)`**: Define roles como el de **Tema, Estímulo, Contenido, Deseo o Poseído**. Son entidades que se colocan, perciben o transfieren, pero que no sufren un cambio en su integridad o estado interno (por ello son menos afectados que un paciente).
5.  **Argumento de un predicado de estado de un solo lugar `pred' (x)`**: Corresponde al rol de **Paciente** o **Entidad**. Se ubica en el extremo derecho de máxima afectación debido a que representa a la entidad que experimenta un cambio drástico de estado o condición interna (ser roto, destruido, muerto, etc.).

### Conclusión

Dado que todas las relaciones semánticas de la gramática universal se reducen a estas **cinco posiciones estructurales** basadas en predicados de uno o dos lugares, la notación de RRG es intrínsecamente binaria (`x, y`) a nivel micro-estructural.

Esto se alinea también con la interfaz sintáctica de la teoría, que **rechaza la postulación de un tercer macrorole** (como un "destinatario" o "beneficiario" en el mismo nivel que el Actor y Undergoer). El tercer argumento de un verbo ditransitivo es tratado simplemente como un argumento central directo o indirecto que no recibe macrorole (Non-Macrorole Argument), manteniendo la elegante simetría binaria de la interfaz sintaxis-semántica.



## Estructura Lógica (EL) de los verbos de tres argumentos (tradicionalmente ditransitivos) en la RRG.

Como mencionamos, el modelo de Van Valin rechaza la existencia de predicados primitivos triargumentales directos (es decir, no existe en el lexicón algo como vender'(x, y, z))
. En su lugar, se analizan como estructuras causativas complejas donde el operador CAUSE conecta un evento de actividad (causa) con un evento de estado o cambio de estado (resultado)
.
Aquí tienes el desglose y la distribución de sus variables en la cadena causativa para vender y cargar.

1. El Verbo Vender (Transferencia de Posesión)
El verbo vender implica que un vendedor realiza una acción que causa que un comprador pase a poseer un objeto a cambio de una transacción. Semánticamente, es una variante de dar (give)
Estructura Lógica (EL): [do' (x, Ø)] CAUSE [BECOME have' (y, z)]

Distribución de las Variables:

x (Vendedor): Es el primer argumento de la actividad causante (do' (x, Ø)). En el continuum de roles temáticos, ocupa la posición de Efector (y por inferencia racional, de Agente si actúa con voluntad y control). Recibe el macrorole de Actor.

y (Comprador): Es el primer argumento del predicado de estado de dos lugares resultante (have' (y, z)). Su rol temático es el de Poseedor (o Recipiente).

z (Objeto vendido / Tema): Es el segundo argumento de la relación de posesión (have' (y, z)). Su rol temático es el de Tema (la entidad que se transfiere sin sufrir un cambio interno).

Interfaz Sintaxis-Semántica (Asignación de Macroroles):
En español, vender tiene un alineamiento rígido donde el Tema (z) es el Padecedor (Undergoer) predeterminado. El comprador (y) no califica para macrorole y se introduce en el Centro (Core) de la cláusula mediante una marca de caso o preposición de dativo (a): Oración: Juan (x: Actor) vendió el carro (z: Padecedor/Tema) a María (y: No-Macrorole).


2. El Verbo Cargar (Alternancia Locativa)
Este es el ejemplo representativo en lingüística para mostrar cómo una misma Estructura Lógica puede proyectar dos configuraciones sintácticas distintas (la Alternancia Locativa) según qué argumento seleccionemos como Padecedor.
Estructura Lógica (EL): [do' (x, Ø)] CAUSE [BECOME be-in' (y, z)]
Distribución de las Variables:

x (Cargador): El primer argumento de la actividad. Es el Efector/Actor.

y (Destino / Locación): El primer argumento del estado locativo resultante (be-in' (y, z)). Su rol es el de Locación (el camión, la mesa, etc.).

z (Carga / Tema): El segundo argumento del estado locativo. Su rol es el de Tema (las cajas, las olivas, etc.).

La Alternancia en la Sintaxis:
Alineamiento A (Selección de Undergoer por defecto / Tema):
Fórmula: [do' (Juan, Ø)] CAUSE [BECOME be-in' (camión, cajas)]

Alineación: El tema (z: cajas) es el argumento más a la derecha en la EL, por lo que recibe el macrorole de Padecedor (Undergoer). El camión (y) queda como un argumento no-macrorole marcado con preposición locativa (en).

Oración: Juan cargó las cajas en el camión.
Alineamiento B (Selección marcada de Undergoer / Locación):
Fórmula: [do' (Juan, Ø)] CAUSE [BECOME be-in' (camión, cajas)] — U = y
Alineación: La teoría permite de forma marcada que el argumento de locación (y: camión) sea promovido a Padecedor (Undergoer). Al ocurrir esto, el tema (z: cajas) queda fuera de los macroroles. La regla de asignación preposicional de la RRG le asigna obligatoriamente la preposición con (with).

Oración: Juan cargó el camión con las cajas.
Representación Gráfica de la Cadena Causativa
Para visualizar cómo se cruzan las tres variables (x, y, z) entre el nivel semántico profundo y la jerarquía de macroroles, la interfaz se estructura así:

  <div style="display:flex;justify-content:center;background:white;padding:20px;overflow-x:auto;"><div style="position:relative;width:75ch;height:260px;font-family:monospace;font-size:14px;color:black;"><div style="position:absolute;top:0;left:0;">NIVEL SEMÁNTICO (Estructura Lógica)</div><div style="position:absolute;top:30px;left:4ch;">[ do' (x, &Oslash;) ]</div><div style="position:absolute;top:30px;left:25ch;">CAUSE</div><div style="position:absolute;top:30px;left:40ch;">[ BECOME pred' (y, z) ]</div><div style="position:absolute;top:50px;left:11.5ch;width:1px;height:40px;border-left:1px dashed black;"></div><div style="position:absolute;top:50px;left:45.5ch;width:11ch;height:20px;border-bottom:1px dashed black;border-right:1px dashed black;"></div><div style="position:absolute;top:70px;left:45.5ch;width:1px;height:20px;border-left:1px dashed black;"></div><div style="position:absolute;top:50px;left:59.5ch;width:1px;height:40px;border-left:1px dashed black;"></div><div style="position:absolute;top:90px;left:7ch;">(EFECTOR)</div><div style="position:absolute;top:90px;left:41ch;">(LOC/POS)</div><div style="position:absolute;top:90px;left:56.5ch;">(TEMA)</div><div style="position:absolute;top:110px;left:11.5ch;width:1px;height:40px;border-left:1px dashed black;"></div><div style="position:absolute;top:110px;left:45.5ch;width:1px;height:90px;border-left:1px dashed black;"></div><div style="position:absolute;top:110px;left:59.5ch;width:1px;height:80px;border-left:1px dashed black;"></div><div style="position:absolute;top:160px;left:0;">NIVEL DE INTERFAZ (Jerarquía Actor-Padecedor)</div><div style="position:absolute;top:190px;left:7ch;">[ ACTOR ]</div><div style="position:absolute;top:190px;left:53ch;">[ UNDERGOER ]</div><div style="position:absolute;top:190px;left:16ch;width:37ch;display:flex;align-items:center;height:20px;"><div style="line-height:1;">&lt;</div><div style="flex-grow:1;height:1px;border-top:1px dashed black;margin:0;"></div><div style="line-height:1;">&gt;</div></div><div style="position:absolute;top:220px;left:6ch;">(Siempre x)</div><div style="position:absolute;top:220px;left:47ch;">(Alternancia entre y / z)</div></div></div>

Esta elegante solución binaria (x, y) a nivel micro-estructural demuestra que la sintaxis no necesita complicadas "reglas de movimiento" ni un tercer macrorole ("objeto indirecto")
. Todo el comportamiento sintáctico y de marcas de caso de estas oraciones se deriva de la posición que cada variable ocupa dentro de sus respectivos subpredicados en la EL.

# ATENCIÓN!!

En el inventario abstracto de plantillas del lexicón, el predicado de estado de posesión se define de manera básica como **`have' (x, y)`**, donde el primer argumento (`x`) es el **poseedor** y el segundo argumento (`y`) es el **tema o poseído**.

¿Por qué entonces la RRG escribe **`[do' (x, Ø)] CAUSE [BECOME have' (y, z)]`** para verbos como *dar* o *vender*?

La respuesta radica en la **evitación del conflicto o choque de variables (*variable clashing*)** cuando se pasa de la plantilla abstracta a la representación de una cláusula con tres participantes distintos:

### 1. El escenario de dos participantes (¿Qué pasa si usamos `have' (x, y)`?)
Si en la Estructura Lógica (EL) unificada de la oración usáramos estrictamente solo dos variables (`x` e `y`), la fórmula quedaría así:
`[do' (x, Ø)] CAUSE [BECOME have' (x, y)]`

En la lógica de la RRG, repetir la variable `x` significa que **el mismo participante que realiza la actividad causante es el que termina poseyendo el objeto**. Esta estructura es semánticamente perfecta y correcta, pero **no para *dar* o *vender*, sino para verbos de obtención o toma (como *tomar*, *adquirir* o *quedarse con*)**:
*   *Ejemplo (*tomar*):* Juan (`x`) actúa, causando que Juan (`x`) posea el libro (`y`).

### 2. El escenario de tres participantes (La necesidad de `z`)
Para verbos de transferencia como *dar*, *vender* oRegalar*, intervienen **tres entidades distintas en el mundo real**. Al necesitar tres variables diferentes en la misma fórmula para evitar que el receptor se coindexe con el dador, la RRG introduce una tercera variable (`z`) y realiza una **sustitución de variables de la plantilla base**:

*   El primer argumento de `have'` (el poseedor/recipiente) se mapea con la variable **`y`**.
*   El segundo argumento de `have'` (el tema/objeto transferido) se mapea con la variable **`z`**.

De esta manera, en la fórmula global de tres argumentos, **`have' (y, z)` sigue manteniendo la misma relación interna exacta que `have' (x, y)`** (donde el primer elemento de la derecha es el poseedor y el segundo es el tema), pero usando las letras `y` y `z` para reservar la `x` exclusivamente al causante original.

Por lo tanto: **`z` es efectivamente el tema (el objeto transferido y equivalente al "poseído")**, y en la microestructura de la posesión ocupa la segunda posición argumental, que es la que convencionalmente se asocia con el rol de Padecedor o Tema en la jerarquía.