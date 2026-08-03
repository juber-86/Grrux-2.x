# Tarea: L4.5 (mini-etapa) — checker sin falsas alarmas + LDP + agx como lista + EL con Ø (González Vergara) + telicidad composicional del objeto

Proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python` (3.10). Entry point:
`python3 gruxx_ai1.py`. Sigue al cierre de la fase LINKING (CHECKPOINT_L4.md +
`data/kpi_linking_post_l4.json`). Etapa QUIRÚRGICA: cinco arreglos puntuales, sin features
nuevas. NO hacer commits (orden de Julian; el repo arrastra el venv y lo resolverá él).

**PROHIBIDO:** clasificador (`predict.py`, `classifier.py`, `decision_tree.py`), corroborador
MLM, `pruebas_estructurales.py`, `.joblib`, `contextual_sentences.csv`. `gruxx_ai1.py` editable
(condición: los 3 modos siguen corriendo y generando EL + árboles). `ud2rrg.py` tocable solo en
§3 (régimen de siempre: gated `language=='es'`/MISC; otras lenguas ni un byte).

**FUERA DE ALCANCE (explícito, decisiones de Julian):** oraciones compuestas / `xcomp`
encadenado (la RRG tiene su propia teoría de juntura-nexo — fase muy posterior, aunque sea el
51% de fallos PUD); mostrar operadores; bucle de corrección de usuario (L5); línea Vector/help
(L5); impersonal refleja por animacidad y agente-con-por como cadena causal secundaria (futuros,
solo TODO). **PUD NO se vuelve a correr** (fue examen de una sola vez; re-correrlo lo
convertiría en set de desarrollo).

## Contexto: las falsas alarmas medidas en L4

De los 15 ejemplos de advertencia en `data/kpi_linking_post_l4.json` (kpi4), el patrón dominante
son NO-errores que el checker reporta por mirar estrecho:

1. **Argumentos clausales**: `x2 ("hablar"/"tener"/"guardar"/"impongan") sin constituyente en el
   árbol` — esos x_n son complementos clausales (ccomp/xcomp/csubj) que la Etapa 1 pone como
   argumento del core (correcto) y el árbol SÍ contiene… como juntura CORE/CLAUSE subordinada,
   no como NP. El checker solo acepta NP/PP dentro del CORE.
2. **Temporales iniciales destacados**: `now'/mientras' se esperaba PERI@CLAUSE (sin rama -PERI)`
   en oraciones que abren con "Ahora ," / "Mientras ,". En RRG eso va a la POSICIÓN DISLOCADA
   IZQUIERDA — el propio diagrama de referencia de Van Valin pone "Yesterday," en LDP. La spec de
   ud2rrg ya describe la operación `PRDP-SUB` (crea PrDP como hijo izquierdo de SENTENCE): la
   maquinaria existe.
3. **Doble AGX**: "…a sus cinco miembros se les ha prohibido…" produce dos AGX en el árbol
   (dativo "les" + "se" pasivo) pero `ls_data['agx']` es un dict ÚNICO (solo dativo) → el
   checker reporta `nodo AGX en el árbol pero sin agx en la LS`.

## Teoría nueva validada por Julian (análisis de C. González Vergara) — guía del §4

El "se" pasivo/impersonal es la manifestación morfológica (alojada EXCLUSIVAMENTE en AGX) de un
proceso léxico: la **inespecificación del argumento de mayor jerarquía** en la EL (x→Ø). El Ø no
puede recibir Actor → el argumento de menor jerarquía recibe Padecedor y asciende a PSA
(concuerda con el verbo). Ej.: "Se rompió el jarrón" →
`[do'(Ø, Ø)] CAUSE [INGR broken'(jarrón)]`. Implicación operativa: en estas construcciones la EL
muestra **Ø como actor** — NUNCA un actor implícito pro-drop inventado.

## Tareas

### 1. Checker: aceptar argumentos CLAUSALES (`completeness.py`)

Al buscar el constituyente de un x_n, aceptar además de NP/PP: un subárbol CORE/CLAUSE
(juntura subordinada) cuyos tokens incluyan el núcleo del argumento (el lema/token verbal que
llena esa x). Estado nuevo `ok_clausal` en el dict de checks; en el resumen legible:
`x2↔CLÁUSULA`. La detección de que una x es clausal sale del dict del mapper (el filler proviene
de ccomp/xcomp/csubj — si hoy no se conserva el deprel de origen de cada x_n en `args_map`/
`variables`, propagarlo desde la Etapa 1: es un campo más, retro-compatible).

### 2. LDP para periferia temporal INICIAL destacada

- **Etapa 1** (`nucleo_periferia.py`): item de periferia temporal cuyo token es inicial de la
  oración (o solo precedido por puntuación) y va seguido de coma → marcar
  `destacado_inicial=True`.
- **Canal** (`misc_rrg.py`): clave nueva `RRGDetached=si` (documentar en el contrato del
  docstring).
- **ud2rrg** (gated es+MISC): `RRGRole=Periphery|RRGType=temporal|RRGDetached=si` → enrutar por
  la operación PrDP existente (hijo izquierdo de SENTENCE) en vez de CLAUSE-PERI. Conservar la
  etiqueta que use ud2rrg para esa posición (PrDP/LDP); documentar la equivalencia LDP≡PrDP.
- **Checker**: un wrapper temporal se satisface con rama -PERI@CLAUSE **o** con nodo LDP/PrDP.
- **TODO-futuro** (comentario, no código): la misma ruta de posiciones destacadas servirá para
  PrCS con pronombres interrogativos (qué/quién/cómo — ver árbol de referencia de Julian con
  "qué" en PrCS y "a María" en LDP). Dejar el enrutado extensible.

### 3. `agx` como LISTA (fuente doble: dativo + se)

- `nucleo_periferia.py`/mapper: `ls_data['agx']` pasa de dict|None a **lista** (vacía si no
  hay). Cada entrada: `{'clitico', 'rasgos', 'fuente': 'dativo'|'se_pasivo'|'se_impersonal',
  'doblado', 'arg_id'}`. El dativo actual se convierte en la primera entrada; los `expl:pass`/
  `expl:impers` registran la suya (fuente se_*). `expl:pv` (verbos pronominales/anticausativos)
  NO se registra (su árbol tampoco produce AGX — coherencia).
- Actualizar TODOS los consumidores: trigger de `ditransitivas.py`, `misc_rrg.py` (ida y
  `leer_ls_desde_misc`), checker (§: cada entrada de la lista ↔ un nodo AGX del árbol, y
  viceversa — el conteo debe cuadrar), render/args_map.
- Fixture obligada: la oración real de AnCora "…a sus cinco miembros se les ha prohibido la
  salida…" (o versión mínima "Se les prohibió la salida") → 2 entradas agx, 2 nodos AGX,
  checker ✓ sin `falta_en_ls`.

### 4. EL con actor inespecificado Ø (se pasivo/impersonal)

- Detección: presencia de `expl:pass`/`expl:impers` (deprel del se). Con ella: el actor de la EL
  es **Ø** — construir la EL con Ø en la posición de mayor jerarquía y NO disparar el pro-drop
  (`actor_implicito`) para ese hueco. El `nsubj:pass` (padecedor) ocupa su posición normal y es
  el PSA. `args_map`: `x1:Ø,—,actor inespecificado (se)`.
- Verificar (test) que el path anticausativo del léxico causativo YA produce `do'(Ø, Ø)` ("Se
  rompió el jarrón" con romper en el léxico) — según CHECKPOINT L0-L2 esa composición ya hace
  x→Ø; si es así, solo cubrir el caso expl:pass/expl:impers de verbos NO causativos-léxicos
  ("Se venden casas" en fixture gold-style).
- Nota honesta conocida (de L4): Stanza vivo rara vez produce `expl:pass`/`expl:impers` (tiende
  a `expl:pv` u obj) — esto beneficia sobre todo gold/conllu directo; fixtures a mano como en
  L4, sin perseguir al parser.
- TODO-futuro (comentarios): impersonal refleja por animacidad ("Se acusó a Pedro" → sin PSA,
  verbo congelado 3sg); agente con "por" en pasivas con se = cadena causal secundaria en
  periferia.

### 5. Telicidad COMPOSICIONAL del objeto + "se" aspectual (bug de campo de Julian)

**El bug (reproducido en vivo, 2026-07-10)** — todas en PRESENTE, todas mal clasificadas por
valores de pun ≈ 0.52-0.54 apenas sobre el umbral 0.45 (ruido del probe: el dataset contextual
es pretérito-dominante y el presente habitual es su territorio débil — se arreglará con datos en
paralelo; AQUÍ va la corrección estructural):

| Oración | Hoy | Correcto |
|---|---|---|
| Juan come | SEMELFACTIVE | **Activity** |
| Juan come manzanas | SEMELFACTIVE | **Activity** |
| Juan come manzanas siempre | SEMELFACTIVE | **Activity** |
| Juan se come las manzanas | ACCOMPLISHMENT | **Active_Accomplishment** |
| Juan come la manzana | ACHIEVEMENT | **Active_Accomplishment** |

Es doctrina RRG pura (delimitación composicional, la misma de "corrió cinco kilómetros"): el
objeto DESNUDO (plural/masa sin determinante: "manzanas") no delimita → atélico; el objeto
DELIMITADO (con determinante o cuantificador: "la manzana", "cinco manzanas") delimita
incrementalmente → télico DURATIVO (jamás puntual); el "se" ASPECTUAL/COMPLETIVO ("se come las
manzanas") marca la telicidad explícitamente. NO tocar el clasificador ni sus umbrales (mover
pun ya demostró empeorar Semelfactive): esto son GATES post-clasificador, la familia del gate
AA-sin-delimitador.

- **Refinar `tiene_delimitador_nuclear`** (`nucleo_periferia.py` o donde viva): un obj DESNUDO
  (sin det ni nummod, plural o masa) NO cuenta como delimitador nuclear. Obj con det (definido,
  demostrativo, posesivo, indefinido) o nummod → sí delimita. Meta de movimiento → sigue
  delimitando. (Esto de paso endurece el gate AA existente.)
- **"Se" aspectual — tercer tipo de se del inventario**: clítico se/me/te/nos/os CORREFERENCIAL
  con el sujeto (concordancia de persona/número: "Juan SE come", no confundir con dativo "se lo
  dio", ni anticausativo del léxico causativo `toma_se`, ni expl:pass/impers del §4) + verbo
  TRANSITIVO con obj presente → marcador de telicidad completiva. Registrarlo en la lista `agx`
  del §3 con `fuente='se_aspectual'` (es un clítico: va a AGX, teoría de Julian; hoy el árbol lo
  deja como PRO-CLT genérico — enrutarlo a AGX vía MISC como los demás).
- **Gates (en el mapper, tras el clasificador y los gates existentes, con flags en config):**
  - **G-atélico**: clase ∈ {semelfactive, achievement, accomplishment, active_accomplishment} +
    sujeto agentivo (nsubj activo) + obj DESNUDO (o sin obj, para el caso "Juan come" cuando la
    clase léxica del lema es durativa) + SIN otro delimitador → `activity`. Nota
    `gate=obj_desnudo→Activity`.
  - **G-AA**: clase ∈ {achievement, accomplishment} + sujeto agentivo + obj DELIMITADO +
    **clase LÉXICA del lema durativa** (Activity/Active_Accomplishment en el lexicón semilla /
    cabeza léxica — GUARDA CRÍTICA: "rompió el vaso" tiene obj definido y sujeto agentivo pero
    romper es Achievement léxico → NO dispara) → `active_accomplishment` con su plantilla
    (`do'(x, [pred'(x, y)]) & INGR consumed'(y)`). Nota `gate=obj_delimitado→AA`.
  - **G-se-aspectual**: se aspectual detectado + obj DELIMITADO → `active_accomplishment` (misma
    guarda de clase léxica durativa). Nota `gate=se_aspectual→AA`.
- Las 5 oraciones de la tabla son DIANAS NUEVAS obligatorias (gold de la 2ª columna
  "Correcto"). GUARDARRAÍL: la batería completa previa sin regresión — en particular "rompió el
  vaso"→Achievement, "estudié tres horas anoche"→Activity, "corrió cinco kilómetros"→AA, las 15
  dianas históricas, las 26 de wrappers y la batería ditransitiva (los ditransitivos ya tienen
  su plantilla: los gates NUEVOS no aplican cuando la ditransitiva disparó).
- La EL resultante usa la plantilla de la clase post-gate (build_ls existente); los wrappers de
  periferia siguen componiendo por fuera ("siempre" queda en periferia listada — frecuencia
  sigue pendiente).

## Validación y aceptación

- Tests fríos nuevos/ampliados en `test_completeness.py`, `test_nucleo_periferia.py`,
  `test_misc_rrg.py`, `test_ud2rrg_es.py`, `test_ditransitivas.py` (consumidor de agx-lista):
  argumento clausal satisfecho (`ok_clausal`); "Ayer, Juan corrió" → LDP/PrDP y checker ✓;
  control: "Juan corrió ayer" (no inicial) sigue en PERI@CLAUSE; agx doble; "Se venden casas" →
  EL con Ø + agx(se_pasivo) + árbol con AGX + checker ✓; pro-drop NO dispara con expl:pass;
  gating no-es intacto.
- Tests del §5 (fríos + @slow con Stanza): las 5 dianas nuevas de la tabla; detección del se
  aspectual vs dativo vs anticausativo vs pasivo (4 fixtures mínimas); obj desnudo vs
  delimitado ("manzanas" vs "la manzana" vs "cinco manzanas" vs "unas manzanas" — todos los det
  delimitan); la guarda de clase léxica ("rompe el vaso" NO dispara G-AA); ditransitiva no
  interferida ("le da manzanas a María" mantiene su plantilla).
- **Re-correr KPI4 sobre AnCora dev (mismas n=300)** → `data/kpi_linking_post_l4_5.json`.
  Aceptación: conversión se mantiene (98.0%); tasa de completeness SUBE sustancialmente respecto
  a 59.2% (reportar la cifra y el desglose de advertencias restantes por tipo — esas restantes
  son el mapa real de lo que falta); acuerdo de periferia por estrato no baja de 46.7%.
- Suites completas verdes (las ~140 actuales + nuevos). PUD intocado.

## CHECKPOINT — PARAR aquí

Informe corto: (1) completeness antes (59.2%) / después + desglose de advertencias restantes por
tipo, (2) árbol de "Ayer, Juan corrió" mostrando LDP/PrDP, (3) la fixture de doble AGX con su
línea Completeness ✓, (4) la EL de "Se venden casas" con Ø, (5) confirmación de que el path
anticausativo ya daba do'(Ø,Ø) o qué hubo que ajustar, (6) las 5 dianas del §5 con su salida
completa de gruxx (clase + EL + gate anotado) y confirmación del guardarraíl ("rompió el vaso",
15 dianas, 26 wrappers, ditransitivas). L5 (bucle de corrección + Vector/Completeness legibles +
-help glosario) se diseña aparte — Julian está decidiendo su UI. En PARALELO Julian está curando
un lote de oraciones en PRESENTE para contextual_sentences.csv (arreglo de datos del mismo bug
del §5); el reentrenamiento/recalibración con ese lote NO es parte de este prompt.
