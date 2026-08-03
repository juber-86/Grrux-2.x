# Tarea LA2: causativas resultativas visibles + tooltips completos + enrutado con inventario completo

Proyecto **GRRux** (el código conserva temporalmente el prefijo histórico `gruxx`; NO renombrar
archivos en esta etapa). Repo `~/proyectos/ud2rrg`. Python: `./venv/bin/python`.

Esta etapa sigue a `CHECKPOINT_LA1.md` y contiene **exactamente tres entregables**:

1. realización/logro causativo como clase visible y plantilla resultativa correcta para el
   `se` pasivo heurístico;
2. tooltips correctos y completos para los nodos del árbol en la GUI;
3. enrutado del bucle de corrección con el inventario completo de la proyección de
   constituyentes, aunque una opción no esté presente en la oración analizada.

**HACER COMMITS.** La política anterior de “NO hacer commits” quedó revocada. Antes de empezar,
revisar el estado del árbol y preservar cambios ajenos ya existentes. Hacer commits pequeños y
coherentes de LA2; no mezclar ni reformatear trabajo preexistente fuera del alcance. El
checkpoint debe enumerar los commits creados.

**ADVERTENCIA OOM (12 GB):** una sola instancia de GRRux/GUI. No ejecutar suites `--slow` con
el servidor o una sesión interactiva cargada. Cerrar la instancia antes de los tests lentos.

## Límites no negociables

- **PROHIBIDO:** modificar `ud2rrg.py`, el clasificador
  (`predict.py`/`classifier.py`/`decision_tree.py`/`.joblib`), el corroborador MLM,
  `contextual_sentences.csv` o los golds sin autorización expresa. PUD sigue siendo examen a
  ciegas: no volver a correrlo.
- No reentrenar, recalibrar ni cambiar las seis clases que produce BERTIN. Las dos etiquetas
  causativas de LA2 son una **lectura derivada de la EL compuesta**, no clases nuevas del
  clasificador.
- `contextual_sentences.csv` es APPEND-ONLY y en LA2 debe quedar byte-idéntico.
- No abordar la discrepancia #1 de LA1 (pasiva perifrástica ligada por orden de superficie),
  los sintagmas completos en la EL, depictivos, guardas generales anti-sobredisparo,
  “corregir todo”, EVQ/EVID, frecuencia, doble ruta psych, x/y ni oraciones compuestas.
- **Wh + preposición/PrCS está suspendido teóricamente.** PrCS puede aparecer como opción
  explícita del inventario del enrutado, pero LA2 no debe implementar su análisis automático
  ni tocar `ud2rrg.py`; una corrección hacia una ruta aún no automatizable va a staging con un
  mensaje honesto.
- Las EL usan predicados en **español**. Para la diana de esta etapa debe ser `vendido'`, nunca
  `sold'`. La migración de predicados a inglés es futura y queda fuera de LA2.
- Cada cambio de comportamiento debe tener pruebas. Al apagar el flag de la capa afectada, la
  salida debe conservar el contrato previo/byte-idéntico según las invariantes existentes.

---

## §1. Realización/logro causativo visible y estado resultante correcto

### 1.1 Bug que debe desaparecer

Hoy el camino heurístico de la pasiva con `se` puede componer:

```text
[do'(Ø, Ø)] CAUSE [do'(casas, [vender'(casas)])]
```

Eso coloca al paciente como efector de una actividad embebida. Para `"Se venden casas"` la EL
correcta es:

```text
formal : [do'(Ø, Ø)] CAUSE [BECOME vendido'(x2)]
léxica : [do'(Ø, Ø)] CAUSE [BECOME vendido'(casas)]
```

El exterior conserva el causante inespecificado `Ø`; el interior es el **estado resultante**.
En `ls_estructura`, `casas` debe ocupar `arg_estado`, nunca `1_do`. La forma canónica del
predicado es el participio español (`vendido'` en esta diana), sin introducir `sold'`.

El arreglo debe ser **quirúrgico** para el camino `se` pasivo/anticausativo heurístico que hoy
produce el `do'` embebido incorrecto. No generalizar la heurística causal ni “arreglar” otros
candidatos por intuición; las guardas anti-sobredisparo son deuda posterior.

### 1.2 BECOME frente a INGR

Reutilizar la decisión aspectual que ya conoce `componer_cause`:

- transición gradual/no instantánea → `BECOME pred'(paciente)` =
  **realización causativa**;
- transición instantánea/puntual → `INGR pred'(paciente)` =
  **logro causativo**.

No duplicar umbrales ni volver a clasificar. La etiqueta visible se deriva del operador de
transición que quedó realmente en la EL compuesta:

```text
BECOME → Realización causativa
INGR   → Logro causativo
```

Conservar también la clase base original en el dato técnico para auditoría. Añadir un campo
estructurado estable (nombre a decidir según el contrato existente, documentarlo) para que
terminal, motor y GUI consuman la misma clase causativa derivada; no inferirla por regex en
cada frontend.

La salida normal debe mostrar la clase causativa derivada donde hoy se presenta “Tipo/clase
aspectual”. En `--verbose` y en la traza de linking debe seguir siendo posible ver la clase
base y la fuente de la composición. Actualizar el glosario con “realización causativa” y
“logro causativo” si no existen.

### 1.3 Linking, integridad y regresiones

Para `"Se venden casas"` el resultado esperado después de recomponer la EL es:

- Actor no asignado al `Ø`;
- `casas` = Undergoer/Padecedor por `arg_estado`;
- PSA = Undergoer;
- concordancia `casas 3pl ↔ venden 3pl` correcta;
- `ls_estructura` y la traza de cinco pasos coherentes con la EL;
- desaparece la discrepancia AUH↔`args_map` de esta oración.

Para `"Se vende casas"` se conserva el mismo análisis semántico pero el warning de
concordancia debe seguir visible (`casas 3pl ↔ vende 3sg`).

Volver a ejecutar el informe de reconciliación de LA1: deben desaparecer únicamente las
discrepancias #2/#3 causadas por este bug. La discrepancia #1 de la pasiva perifrástica debe
quedar documentada e intacta. No editar el log histórico para fingir que nunca existieron las
filas previas.

Wrappers y operadores deben seguir envolviendo la nueva EL por fuera, sin cambios de scope.
`causatividad.enabled: false` debe conservar el comportamiento/contrato de capa apagada.

---

## §2. Tooltips completos y exactos para nodos del árbol

### 2.1 Causa del fallo

`gui/app.js` usa actualmente una búsqueda tolerante por `includes` sobre el glosario. Para
etiquetas cortas como `N`, `V` y `P`, ese mecanismo encuentra entradas no relacionadas. Otros
nodos producidos por el árbol no tienen una correspondencia explícita y quedan sin ayuda.

Eliminar la inferencia ambigua para etiquetas de nodos. Un nodo del árbol debe resolverse por
una clave **exacta** en un mapa canónico `etiqueta del árbol → término del glosario` (o una
estructura equivalente). El texto de la definición sigue viniendo del glosario; no duplicar
definiciones largas en JavaScript.

### 2.2 Contrato mínimo y cobertura completa

Como mínimo:

```text
N → sustantivo
V → verbo
P → preposición
```

Preservar los tooltips que ya son correctos para `AGX`, `CORE`, `CLAUSE`, `SENTENCE` y todos
los nodos `*-PERI`. Preservar también los tooltips especiales de operadores: no forman parte
de este bug.

No adivinar el resto del inventario. Obtener las etiquetas reales producidas por el
convertidor español activo a partir de los fixtures/árboles de prueba (por ejemplo `NUC`,
`PRED`, `NP`, `PP`, `ADVP`, `PrDP`, `LDP`, `PrCS`, categorías léxicas y nodos intermedios) y
crear el mapa completo para **toda etiqueta no-hoja renderizable**. Si falta una entrada en
`glosario_gruxx.csv`, añadirla en español con terminología RRG clara.

Reglas:

- lookup exacto normalizado; nunca coincidencia parcial para una sigla de nodo;
- las hojas que contienen las palabras de la oración no reciben tooltip de categoría;
- un `X-PERI` usa la definición de periferia y conserva su estrato/ancla cuando esté
  disponible;
- una etiqueta desconocida no muestra una definición falsa: falla el test de cobertura y, en
  producción, queda sin tooltip;
- terminal y análisis semántico no cambian por este trabajo de GUI.

Añadir una prueba de cobertura que recoja todas las etiquetas no-hoja de una batería
representativa de árboles y falle si alguna no está mapeada. Añadir pruebas directas que
demuestren que `N`, `V` y `P` devuelven exactamente las definiciones de sustantivo, verbo y
preposición, respectivamente, y no una coincidencia accidental.

---

## §3. Enrutado con el inventario completo, presente o ausente

### 3.1 Decisión de producto

GRRux no decide qué alternativas puede elegir el usuario basándose en lo que ya detectó. En
las dos selecciones:

1. **“¿Qué elemento/posición está mal?”**
2. **“¿Qué debería ser?”**

debe aparecer siempre el inventario completo de destinos de la proyección de constituyentes,
estén presentes o ausentes en la oración. Las opciones presentes muestran sus ocupantes; las
ausentes se muestran explícitamente como `(ausente)`. No filtrar la segunda lista por la
primera ni por el análisis actual.

### 3.2 Fuente única de verdad e inventario

Sustituir los espejos divergentes de Python/JavaScript por una fuente canónica servida por el
backend (en el contrato de análisis o en un endpoint de opciones). Terminal y GUI deben
consumir/derivarse de esa misma fuente.

El inventario canónico debe cubrir, como categorías corregibles:

- argumento del `CORE`;
- núcleo/predicado (`NUC`/`PRED`) cuando corresponda a un elemento léxico;
- clítico/índice de concordancia `AGX`;
- periferia anclada en `NUC`, `CORE` y `CLAUSE`, conservando los subtipos semánticos que el
  sistema activo distingue (temporal, locativo, modo, aspectual, frecuencia, razón,
  concesión, condición, epistémico y cualquier otro vigente);
- posición destacada `PrDP`/`LDP`;
- posición precentral `PrCS`, marcada como ruta teórica disponible pero automatización
  suspendida.

Esta lista es el **mínimo**, no una autorización para omitir categorías reales. Auditar las
etiquetas/rutas que producen `nucleo_periferia`, `wrappers_ls`, `misc_rrg`, el motor y los
árboles de prueba. Toda ruta corregible que exista en el pipeline activo debe tener una clave
estable, etiqueta española, estrato y estado de automatización
(`automatizable`/`solo_staging`). El test de cobertura debe fallar si aparece una ruta activa
sin entrada canónica.

No convertir `SENTENCE` o `CLAUSE` en destinos directos de un token solo porque sean nodos del
árbol: se representan mediante su función corregible (por ejemplo `PERI@CLAUSE` o posición
destacada). La UI debe mostrar terminología comprensible para lingüistas, no claves internas.

### 3.3 Selecciones ausentes y API

El contrato actual exige `elemento_id` y por eso no puede representar una posición ausente.
Extenderlo de forma retrocompatible:

- una instancia presente conserva `elemento_id` y texto;
- una opción ausente lleva su `ruta_origen` canónica y `elemento_id=null`;
- la solicitud siempre lleva `ruta_destino`;
- el backend valida ambas claves contra el inventario único; no confía en valores libres del
  navegador.

Si la corrección puede persistirse en una lista de config existente, mantener el ciclo
actual: cambio → reanálisis → confirmación → persistido o rollback+staging. Si la ruta está
ausente, es PrCS o no existe una automatización segura, registrar la decisión completa en
`correcciones_enrutado.csv` y el log maestro como `solo_staging`, incluyendo origen,
destino, presencia/ausencia y texto/token cuando exista. Nunca inventar un token ni tocar
directamente el árbol.

La terminal debe ofrecer el mismo inventario y permitir cancelar con `Esc`/vacío sin efectos.
La GUI debe:

- mostrar todas las categorías, con ocupantes o `(ausente)`;
- permitir expandir una categoría con varias instancias;
- mostrar siempre todos los destinos;
- explicar visualmente qué opciones solo pueden registrarse para revisión;
- conservar el diff y los banners honestos del flujo G2/G3.

### 3.4 Pruebas de aceptación del enrutado

- Oración mínima sin periferia: ambas listas siguen mostrando `PERI@NUC`, `PERI@CORE`,
  `PERI@CLAUSE`, `PrDP/LDP`, `PrCS`, `AGX`, argumento core y las demás rutas canónicas.
- Oración con argumento, dos periferias y AGX: las mismas opciones aparecen una sola vez como
  categorías y muestran correctamente todas sus instancias.
- Elegir una ruta ausente → petición válida, staging estructurado, cero mutación del árbol.
- Elegir PrCS → staging honesto; no se modifica `ud2rrg.py` ni se afirma que la interrogativa
  quedó implementada.
- Destino desconocido → rechazo claro del backend.
- Corrección automatizable existente → sigue pasando por reanálisis confirmatorio y rollback
  si no se refleja.
- Terminal y GUI exponen exactamente las mismas claves y etiquetas.
- Cancelar en cualquier punto → cero archivos/config/logs modificados.

---

## §4. Suites y regresión

Tests fríos obligatorios:

1. composición BECOME y composición INGR con `ls_estructura`;
2. `"Se venden casas"` con EL española exacta, clase visible “Realización causativa”, AUH,
   PSA, concordancia e Integridad correctos;
3. `"Se vende casas"` conserva el warning de concordancia;
4. informe LA1 sin discrepancias #2/#3 y con #1 intacta;
5. mapa de tooltips con cobertura total y casos exactos `N`/`V`/`P`;
6. inventario de enrutado único, completo y no filtrado;
7. rutas ausentes/PrCS a staging, rutas automatizables con confirmación y rollback;
8. contratos de motor/servidor y GUI actualizados;
9. flags apagados respetan los contratos byte-idénticos existentes;
10. archivos prohibidos verificados sin cambios atribuibles a LA2.

Después, suites rápidas completas. Ejecutar solo las pruebas `@slow` necesarias y al final,
con la precaución OOM. Los tres fallos lentos conocidos de LA1 pertenecen al clasificador y
no autorizan cambios en él:

- `"el perro se sacudió"` (activity vs semelfactive);
- `"Juan llegó"` (activity vs achievement);
- `blend_sube_pun` (Δ0.0036).

Si siguen exactamente iguales, documentarlos; cualquier fallo lento nuevo es regresión de
LA2 y debe resolverse antes del checkpoint.

---

## CHECKPOINT — PARAR aquí

Crear `CHECKPOINT_LA2.md` y detenerse. Debe incluir:

1. antes/después exacto de `"Se venden casas"` (EL formal/léxica, clase visible,
   `ls_estructura`, Linking e Integridad);
2. demostración BECOME→realización causativa e INGR→logro causativo;
3. tabla de reconciliación LA1 mostrando que desaparecieron solo #2/#3;
4. tabla completa `nodo del árbol → entrada de glosario` y prueba de `N`/`V`/`P`;
5. captura de la GUI con al menos un tooltip corregido y otra con el inventario completo de
   enrutado, incluidas opciones ausentes;
6. tabla canónica de rutas con estrato, subtipos, automatización y comportamiento de staging;
7. resultados de suites rápidas/lentas, regresiones conocidas y verificación de prohibiciones;
8. archivos modificados y commits de LA2.

No continuar con LA3 ni con ninguna deuda fuera de los tres entregables.
