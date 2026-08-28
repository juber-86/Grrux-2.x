# BENEFACTIVAS-1.5 — Cierre de validación, aislamiento y fidelidad estructural

## Objetivo

Corrige cuatro defectos encontrados durante la revisión independiente de
`prompt_correct_benefactivas.md` y deja la reforma benefactiva realmente
cerrada:

1. impedir que primitivos o wrappers reservados, especialmente `have'`, se
   guarden como predicados resultativos monovalentes;
2. resolver el contrato incoherente `proposito=none`;
3. impedir que pruebas o instancias aisladas escriban en el
   `ditransitivos_candidatos.csv` real;
4. hacer isomorfa la `ls_estructura` de las benefactivas de actividad,
   registrando las dos posiciones de `lema'(x,z)`.

Este es un **prompt ejecutor**. Inspecciona el árbol actual, implementa las
correcciones, añade regresiones, ejecuta los gates y actualiza el checkpoint.
No te limites a describir una solución.

La reforma principal ya funciona y no debe reescribirse. Se reprodujeron como
línea base:

- gate focal: **163 passed, 12 skipped**;
- ditransitivas lentas: **20/20**;
- corrector lento: **49 passed**.

Estos resultados sirven como referencia, no como evidencia del cierre: vuelve
a ejecutar los gates después de modificar el código.

## Preparación y seguridad

Antes de editar:

1. Lee completos:
   - `prompt_correct_benefactivas.md`;
   - `CHECKPOINT_BENEFACTIVAS.md`;
   - `CHECKPOINT_NOTACION_2.md`;
   - `Notacion_x_y.md`;
   - `aspect_classifier/ditransitivas.py`;
   - `aspect_classifier/correccion.py`;
   - `aspect_classifier/linking.py`;
   - `rrg_ls_mapper.py`;
   - `aspect_classifier/test_ditransitivas.py`;
   - `aspect_classifier/test_l5.py`;
   - `test_gruxx_motor.py` y `test_gruxx_server.py`.
2. Ejecuta `git status --short`. El árbol contiene cambios previos legítimos.
   Presérvalos y no uses `git reset`, `git checkout --`, limpieza destructiva
   ni reemplazos masivos.
3. No hagas commit.
4. No uses PUD y no modifiques `ud2rrg.py`, clasificadores, modelos `.joblib`,
   embeddings, BERTIN, Stanza, `contextual_sentences.csv`, `dataset_clean.csv`
   ni `complex sentences/`.
5. LA3 y las oraciones compuestas continúan pausadas.
6. Conserva exclusivamente la notación RRG vigente `x/y/z`; no reintroduzcas
   variables `xN`.
7. No cambies las EL canónicas ya aprobadas para `preparar`, `crear`,
   `comprar` y `reparar`, salvo ajustes internos de `ls_estructura` que no
   alteren su texto.

## Defectos reproducidos

La revisión confirmó que las suites existentes están verdes, pero no cubren
estos casos:

### A. Primitivo monovalente aceptado

Actualmente esta EL se valida como una benefactiva de `cambio_estado`:

```text
[[do'(Juan, Ø)] CAUSE [BECOME have'(pizzas)]]
PURP [have'(María, pizzas)]
```

El reconocedor infiere `predicado_resultado=have'`, el XLSX puede admitirlo y
el generador puede reproducirlo. La confirmación exacta, por tanto, no protege
el léxico.

### B. `proposito=none` incompleto

`PROPOSITOS` y el generador admiten `none`, pero una EL resultativa sin `PURP`
se reconoce como `causativa`, no como benefactiva. Además, al generar una
benefactiva con `none`, `y` desaparece de la EL y de `ls_estructura`, aunque
permanece en `variables`, `id_a_var`, roles y argumentos.

### C. Contaminación del CSV de candidatos

La validación aislada de `amasar` dejó en el archivo real:

```csv
amasar,Juan le amasó pan a María,transferencia
```

El XLSX estaba bajo `/tmp`, pero `rrg_ls_mapper.py` llamó a
`log_candidato_ditrans` con su ruta global predeterminada. El mismo riesgo
existe en pruebas lentas que usan un `data_dir` temporal sólo para el corrector.

### D. Frame incompleto en actividad

Para:

```text
do'(x, [buscar'(x, z)]) PURP [BECOME have'(y, z)]
```

la estructura interna contiene el frame `do'(x)` y un frame `buscar'` con sólo
`z`. Falta la aparición semántica de `x` como primer argumento de `buscar'`.
Linking produce los macropapeles esperados, pero la estructura no es isomorfa
con la EL textual.

## 1. Inventario seguro de predicados resultativos

Implementa una validación compartida para los predicados resultativos
monovalentes. Debe usarse tanto al cargar el XLSX como al reconocer una EL
corregida.

Requisitos mínimos:

- Rechaza como `predicado_resultado`:
  - `do'`;
  - `have'`;
  - predicados de comunicación `.to.`;
  - wrappers espaciales, temporales y aspectuales reconocidos por el proyecto,
    por ejemplo `be-in'`, `for'`, `during'`, `every'`, `yesterday'`;
  - cualquier operador o nombre gramatical no apto para estado resultativo.
- No mantengas dos listas divergentes en `ditransitivas.py` y
  `correccion.py`. Define una fuente compartida o helpers reutilizados por
  ambos módulos sin provocar importaciones circulares.
- Conserva válidos los predicados curados actuales: `prepared'`, `exist'`,
  `clean'`, `painted'`, `repaired'` y `translated'`.
- Conserva la validación de forma y añade la validación de función/aridad.
- Un XLSX contaminado debe fallar al cargar indicando archivo, fila, lema y
  predicado rechazado.
- Una corrección GUI contaminada debe rechazarse en nivel 3 antes de tocar el
  XLSX o el léxico en memoria.

Añade pruebas negativas independientes para `have'(z)`, `do'(z)` y al menos un
wrapper como `be-in'(z)`. Comprueba que el número de filas y los bytes del XLSX
temporal permanecen intactos tras cada rechazo.

## 2. Retirar temporalmente `proposito=none`

Decisión de este hito: **elimina temporalmente `none` del contrato
benefactivo activo**.

Razón teórica: en la implementación actual, `y` se introduce exclusivamente
mediante la relación de propósito. Si se elimina `PURP`, `y` deja de estar en
la EL aunque la sintaxis y los metadatos sigan tratándolo como beneficiario.
No inventes otra relación semántica sólo para conservar el enum.

Implementación requerida:

- `PROPOSITOS` debe admitir únicamente las modalidades realmente cerradas:
  `become_have` y `have`.
- El cargador debe rechazar una fila benefactiva con `proposito=none` y emitir
  un diagnóstico preciso.
- El generador debe rechazar explícitamente `none`; no debe omitir `PURP` ni
  producir una EL sin `y`.
- El corrector debe rechazar una EL benefactiva sin `PURP` como benefactiva
  incompleta. No debe redirigirla silenciosamente a `causativa` cuando la
  oración contiene una construcción benefactiva/dativo y la corrección intenta
  editar esa familia.
- Distingue una causativa legítima de una benefactiva truncada usando el
  contexto disponible en `corregir_el`/la LS original. Si la API pura de
  `validar_el` no tiene suficiente contexto sintáctico, conserva una validación
  general razonable y añade una guardia contextual antes de persistir. No
  rompas las correcciones causativas legítimas.
- `construir_ditransitiva` nunca debe devolver una benefactiva donde `y` esté
  en `variables`/`id_a_var` pero ausente de la EL y de `ls_estructura`.
- Migra/verifica el XLSX: ninguna fila actual usa `none`, por lo que no deben
  perderse ni cambiar de subtipo las 122 entradas.

Actualiza la documentación: elimina del checkpoint y del estado del arte toda
afirmación de que `none` está implementado. Déjalo como posible extensión
futura que requiere una relación explícita para el tercer participante.

## 3. Aislamiento total del log de candidatos

Haz inyectable el destino de `ditransitivos_candidatos.csv` de extremo a
extremo.

Requisitos:

- No dependas de que `log_candidato_ditrans` use siempre
  `CANDIDATOS_CSV` como argumento predeterminado.
- El mapper debe aceptar o resolver una ruta/configuración de candidatos
  compatible con ejecución normal y con pruebas aisladas.
- En producción normal, el comportamiento sigue siendo append/dedupe sobre el
  CSV real.
- En pruebas y GUI aislada, el log debe escribirse en el `data_dir` temporal o
  en una ruta temporal explícita.
- La inyección debe llegar también al reanálisis realizado por el corrector; no
  basta con aislar sólo el primer análisis.
- No introduzcas una variable global mutable que pueda filtrar rutas entre
  pruebas o solicitudes concurrentes.
- Si la arquitectura del mapper no permite hoy pasar `data_dir`, introduce el
  cambio más pequeño y explícito en el contrato de análisis/motor/servidor,
  con defaults compatibles. Evita monkeypatches permanentes y cambios de
  `cwd`.
- Retira del archivo real `aspect_classifier/data/ditransitivos_candidatos.csv`
  únicamente la fila artificial exacta de `amasar` mostrada arriba. No borres,
  reordenes ni regeneres el resto del log.

Pruebas obligatorias:

1. Analiza un verbo desconocido con dativo usando una ruta temporal.
2. Comprueba que la fila aparece una sola vez en el CSV temporal.
3. Repite el análisis y comprueba deduplicación.
4. Verifica por hash o bytes que el CSV real no cambió durante la prueba.
5. Ejecuta el flujo lento de alta/corrección de `amasar` y confirma que tampoco
   toca el CSV real.

Las pruebas deben restaurar cualquier estado en memoria mediante `finally`,
incluso si una aserción falla.

## 4. `ls_estructura` isomorfa para actividad

Para el subtipo benefactivo `actividad`, representa el predicado léxico
bivalente completo:

```text
EL: do'(x, [buscar'(x, z)])

frames esperados conceptualmente:
do'       → x en `1_do`
buscar'   → x en `1_pred_xy`, z en `2_pred_xy`
have'     → y en `1_pred_xy` como NMR, z en `2_pred_xy`
```

Requisitos:

- Añade `x` al frame del predicado de actividad con `variable="x"`.
- Conserva `z` con `variable="z"`.
- Linking debe deduplicar correctamente las dos apariciones de `x` y las dos
  de `z`.
- La ocurrencia canónica de `x` debe seguir siendo la posición más agentiva
  (`1_do`); la de `z`, la más afectada pertinente.
- El resultado debe seguir siendo:
  - Actor=`x`;
  - Undergoer=`z`;
  - `y`=NMR;
  - M-transitividad=2;
  - exactamente tres argumentos `x/y/z` en motor/JSON/GUI.
- `posiciones_semanticas` debe conservar para `x` tanto `1_do` como
  `1_pred_xy`, y para `z` las ocurrencias del predicado léxico y del propósito.
- No alteres el texto de la EL canónica ni dupliques constituyentes,
  `args_map`, MISC o comprobaciones de Completeness.

Añade regresiones con `buscar` y con el lema nuevo usado en el corrector
(`amasar` u otro equivalente temporal).

## 5. Fortalecer las pruebas del corrector

Añade o ajusta pruebas para demostrar simultáneamente:

- `BECOME have'(z)` se rechaza y nunca llega a upsert;
- `BECOME do'(z)` y un wrapper resultativo se rechazan;
- un XLSX con esos valores no carga;
- `proposito=none` no pertenece ya al enum activo;
- una fila XLSX con `none` se rechaza;
- el generador no puede construir una benefactiva con `none`;
- una benefactiva truncada no se guarda como causativa por accidente;
- una causativa legítima sigue siendo corregible;
- `ls_estructura` de actividad contiene `x,z` en el frame léxico;
- Linking deduplica sin cambiar macropapeles ni M-transitividad;
- confirmación exacta, `insert`, `update`, `no-op`, conflicto y rollback siguen
  funcionando;
- transferencia, comunicación, preparación, creación, obtención y cambio de
  estado no sufren regresiones;
- las entradas heredadas `x1/x2/x3` siguen rechazándose.

No conformes pruebas con mocks que sólo repitan la salida esperada. Mantén las
pruebas puras para reglas locales y al menos una prueba lenta con mapper real
para aislamiento y estructura.

## 6. Gates de ejecución

Ejecuta en orden. Si un gate falla, diagnostica y corrige antes de continuar.

### 6.1 Reproducción inicial

Antes de cambiar código, añade primero las regresiones mínimas que reproduzcan
los defectos A–D y comprueba que fallan por la razón esperada. Documenta esas
fallas iniciales en el checkpoint sin dejar la suite rota al finalizar.

### 6.2 Gate focal rápido

```bash
./venv/bin/python -m pytest -q \
  aspect_classifier/test_ditransitivas.py \
  aspect_classifier/test_l5.py \
  aspect_classifier/test_linking.py \
  aspect_classifier/test_completeness.py \
  aspect_classifier/test_misc_rrg.py \
  aspect_classifier/test_notacion.py \
  test_gruxx_motor.py
```

Ejecuta el servidor por separado y acotado debido al timeout aislado conocido:

```bash
timeout 90s ./venv/bin/python -m pytest -q test_gruxx_server.py
```

Si vuelve a detenerse en `test_estado_listo_tras_startup`, diagnostícalo con
`pytest -vv -s -x` bajo el mismo timeout, documenta la reproducción y continúa
con la suite completa. No modifiques `gruxx_server.py` para ocultar una
limitación preexistente salvo que este hito introduzca una regresión demostrada.

### 6.3 Gates lentos focales

Ejecuta sin otra GUI/servidor abierto:

```bash
./venv/bin/python -m aspect_classifier.test_ditransitivas --slow
RUN_SLOW=1 ./venv/bin/python -m pytest -q aspect_classifier/test_l5.py
RUN_SLOW=1 ./venv/bin/python -m pytest -q aspect_classifier/test_notacion.py
```

Si Stanza necesita crear temporales bajo su caché local, usa el acceso normal
del entorno; no cambies rutas del proyecto ni descargues modelos que ya existen.

Después de cada suite lenta, comprueba que
`aspect_classifier/data/ditransitivos_candidatos.csv` permanece byte-idéntico.

### 6.4 Suite completa

```bash
./venv/bin/python -m pytest -q
```

Si el entorno obliga a dividirla, registra exactamente qué grupos se
ejecutaron y cuáles no. No borres logs, caches o datos curados para conseguir
un resultado verde.

### 6.5 Verificación GUI/JSON

Usa una única instancia aislada y ciérrala al terminar. Verifica:

- `Juan prepara pizzas a María todas las mañanas` conserva su EL aprobada;
- `Juan busca un regalo para María` mantiene el subtipo actividad y estructura
  `x/y/z` sin duplicados;
- una corrección con `BECOME have'(pizzas)` se rechaza antes de persistir;
- una alta temporal de un verbo desconocido se confirma y sólo escribe en el
  XLSX/CSV temporales;
- el CSV y XLSX reales permanecen byte-idénticos durante esta validación.

Inspecciona respuesta JSON y DOM; no basta una captura estática.

## 7. Documentación y entrega

Actualiza `CHECKPOINT_BENEFACTIVAS.md` con una sección
`BENEFACTIVAS-1.5` que incluya:

- los cuatro defectos reproducidos;
- decisiones finales y archivos corregidos;
- inventario de predicados resultativos prohibidos;
- retiro temporal de `proposito=none` y su razón teórica;
- mecanismo final de aislamiento del CSV;
- estructura completa de una benefactiva de actividad;
- pruebas nuevas y resultados reales de todos los gates;
- hashes/bytes del CSV real antes y después de pruebas lentas y GUI;
- confirmación de que la fila artificial de `amasar` fue retirada sin alterar
  las demás;
- limitaciones restantes;
- confirmación de que LA3, oraciones compuestas, modelos, entrenamiento, PUD y
  datos contextuales permanecieron intactos.

Corrige también las afirmaciones correspondientes en
`ESTADO_DEL_ARTE_GRUXX.md`. Sólo conserva “reforma cerrada” si todos los gates
de este prompt pasan.

Al entregar, resume:

- archivos modificados;
- defectos corregidos;
- resultados de pruebas;
- evidencia de aislamiento de datos;
- estado final del hito.

No hagas commit.

## Criterios de cierre

BENEFACTIVAS-1.5 sólo queda cerrado cuando se cumplen simultáneamente:

- ningún primitivo/wrapper reservado puede persistirse como resultado
  monovalente;
- `proposito=none` ya no forma parte del contrato activo ni puede producir
  metadatos sin correlato en la EL;
- pruebas y GUI aisladas no escriben en el CSV/XLSX reales;
- la fila artificial `amasar` desapareció del CSV real y el resto se preservó;
- `ls_estructura` de actividad contiene `lema'(x,z)` completo;
- Linking deduplica `x` y `z` sin alterar Actor, Undergoer, NMR o
  M-transitividad;
- las cuatro EL canónicas aprobadas permanecen iguales;
- notación, transferencia y comunicación no presentan regresiones;
- pasan gate focal, gates lentos y suite completa, salvo la limitación aislada
  del servidor si vuelve a reproducirse y queda documentada con precisión.
