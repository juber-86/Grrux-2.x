# PROMPT OPUS 4.8 — PERIFERIA COMPLETA (post-L5, pre-GUI)

> **Sesión de IMPLEMENTACIÓN.** Este archivo es el handoff de la sesión de
> diseño. Ejecuta el código y las ediciones descritas. Entorno: usar
> `./venv/bin/python` (Python 3.10). **NO** correr suites `--slow` con una
> instancia interactiva de `gruxx_ai1` abierta (máquina 12 GB, OOM conocido).
> **NO** hacer commits (Julian commitea a mano). **NO** tocar
> `contextual_sentences.csv`, los `.joblib` ni `models/` (esta etapa NO
> reentrena nada). Verificar intactos por `mtime` al cerrar.

---

## 0. OBJETIVO DE UNA FRASE

**Eliminar el tipo de periferia `otro` de gruxx.** En la GRR no existe una
caja "otros" para los adjuntos: cada elemento periférico (a) se ancla al
**estrato** correcto del árbol según su **alcance (scope)** semántico, y (b)
**aparece SIEMPRE en la EL** envuelto como un predicado que toma la LS del
estrato que modifica. Hoy `otro` es ~75 % de la periferia, no lleva wrapper y
no aparece en la EL (bug reportado por Julian en uso real:
"Juan aprende español **los fines de semana**" → `fines(obl/otro)` sale en
Argumentos/Integridad pero **no** en la EL).

Esta etapa va **ANTES de la GUI** y **NO** toca las categorías de fix A/B/C/D/F
(plantilla interna se-pasivo, NPs completos con modificadores, depictivos,
guardas anti-sobredisparo causativo, corregir-todo del bucle). Solo la
**categoría E**: representación en la EL de la periferia tipo "otro" + mejor
tipado + anclaje por estrato correcto.

---

## 1. DOCTRINA GRR (fuente: enseñanza de Julian, 2026-07-13)

Cada estrato de la cláusula tiene **su propia** periferia. Se decide por qué
parte exacta del evento modifica el adjunto:

| Estrato | Qué aloja | Envuelve en la EL |
|---|---|---|
| **NÚCLEO** | Adverbios **aspectuales** de fase/grado: *completamente, continuamente, parcialmente, gradualmente*. Modifican el desarrollo interno del predicado, sin referencia a participantes. | El primitivo de estado/actividad más profundo. |
| **CENTRO** | Adverbios de **manera/ritmo** (*cuidadosamente, elegantemente, rápidamente, lentamente*) + la gran mayoría de **PP de marco espacial y temporal** (*en el parque, a las tres, durante la clase, por tres horas*). | `do'` (manera) o toda la LS central (marco). |
| **CLÁUSULA** | Adverbios **epistémicos/evidenciales** (*probablemente, evidentemente*) + PP de **razón/causa/concesión/condición** (*debido a los insultos, a pesar del mal clima*). Evalúan la proposición completa (postura del hablante, causa general del hecho). | La proposición entera. |

Nota: la Oración (SENTENCE) aloja además posiciones **dislocadas** (LDP/RDP,
PrCS) para tópicos y elementos destacados — ya implementado en L4.5 (temporal
inicial destacado → PrDP). Eso **se mantiene**.

**Cómo se expresan en la EL** (los adjuntos SÍ van dentro de la fórmula,
a diferencia de los operadores que van entre `< >`):

- **Adverbios simples → predicado MONOVALENTE** `adv'( [LS] )`.
  - Temporal: `yesterday'(do'(Juan,[correr'(Juan)]))`
  - Manera (centro): `[elegant'(do'(Pat, Ø))] CAUSE [BECOME closed'(puerta)]`
  - Aspectual (núcleo): `BECOME (complete'(melted'(hielo)))`
  - Epistémico (cláusula): `probably'( [LS] )`
- **PP periféricas → preposición predicativa BIVALENTE** `prep'(x, y)`:
  - `x` = objeto de la preposición (locación, causa, entidad…).
  - `y` = **la LS completa** del estrato modificado.
  - Locativo espacial: `be-in'(parque, [do'(Chris,[correr'(Chris)])])`
    (`be-` reservado SOLO para locación espacial).
  - Razón (cláusula): `because-of'(insultos, [feel'(Chris,[angry'])])`

**La clave anti-"otro":** una PP sin entrada específica **no** cae a "otro":
se representa con la **preposición misma como predicado** (metalenguaje inglés)
envolviendo la LS del estrato → `despite'(clima, [LS])`,
`because-of'(insultos, [LS])`. Un adverbio sin entrada → monovalente con su
lema. Nada queda fuera de la EL.

---

## 2. DECISIONES DE JULIAN (2026-07-13, ya tomadas — implementar tal cual)

1. **Corrección doctrinal del anclaje (rompe la decisión L3).** En L3 se ancló
   `temporal → CLÁUSULA`. La doctrina de Julian dice: los PP de **marco**
   temporal y locativo van a la **periferia del CENTRO**; solo razón/causa/
   concesión/condición + epistémico/evidencial van a la **CLÁUSULA**. ⇒ El
   anclaje debe pasar a ser **scope-driven** (por estrato calculado), NO
   "temporal siempre a cláusula". Los temporales **iniciales destacados**
   siguen yendo a **LDP/PrDP** (sin cambios; eso es L4.5). Este es un cambio
   de comportamiento **medible** → KPI antes/después obligatorio (§7).

2. **Epistémicos/evidenciales: INCLUIRLOS YA** como adverbio monovalente de
   **periferia de CLÁUSULA** que envuelve la proposición (`probably'([LS])`,
   `evidently'([LS])`). Ojo: esto son los **adverbios** léxicos. La
   **modalidad gramatical como OPERADOR** (deóntica vía aux/subjuntivo, EST/
   status, FI) sigue **POSPUESTA** al nivel pragmático — no se toca.

3. **Frecuencia: tipar + wrapper provisional.** *siempre/nunca/frecuentemente/
   a menudo* (advmod) y los NP distributivos *todos los días / cada semana /
   los fines de semana* dejan de ser "otro": se tipan como **temporal-
   frecuencia** y reciben un wrapper **reversible** para que APAREZCAN en la
   EL. Forma provisional propuesta (Julian afina después): monovalente
   `always'/never'/frequently'([LS])` para adverbios; bivalente
   `every'(x, [LS])` para el NP distributivo (x = núcleo: *día/semana/fin*).

4. **Scope en la EL = LS completa ordenada por estrato (Opción A).** Cada
   wrapper envuelve la LS **entera**, anidada por estrato (aspectual más
   interno → … → cláusula más externo). El **anclaje del ÁRBOL sí queda
   exacto** (NUC/CORE/CLAUSE). El targeting exacto dentro de la fórmula
   (aspectual solo sobre el primitivo: `BECOME(complete'(melted'(x)))`; manera
   solo sobre `do'`) queda como **TODO documentado**, NO se implementa ahora.

5. **NO tocar los pronombres de OD** (*lo/la/los/las*): siguen como argumento
   del CORE (decisión de L5, ratificada por Julian ahora). Esta etapa no los
   mira.

---

## 3. ESTADO ACTUAL — puntos de enganche verificados (2026-07-13)

### `aspect_classifier/nucleo_periferia.py`
- `_tipo_periferia(tok, case)` → **líneas 255-267**: devuelve
  `temporal|locativo|modo|otro`. **Aquí** entra la clasificación nueva.
- Tablas **líneas 63-77**: `_NOMBRES_TIEMPO`, `_ADV_TIEMPO`, `_CASE_LOCATIVO`,
  `_CASE_TEMPORAL={"durante"}` (por/antes/después/hasta/desde quedaron FUERA a
  propósito por ambiguos — ahora se reactivan CON estrato explícito, ver §4).
- `PERIFERIA_DEPRELS` **línea 50**: `{obl, advmod, obl:tmod, nmod:tmod, obl:mod, advcl}`.
- El item de periferia se construye ~**líneas 380 y 414-418** con
  `tipo`, `destacado_inicial=(tipo=="temporal")`. ⚠ Ese `destacado_inicial`
  hoy solo se calcula para temporal — mantener la lógica de LDP intacta pero
  desacoplarla del nuevo tipado (ver §5).

### `aspect_classifier/wrappers_ls.py` (232 líneas)
- Tablas DEFAULT (locativos, temporales_simples, adverbios_monovalentes,
  sin_wrapper, frecuencia) + selectores `_elegir_manera/_elegir_locativo/
  _elegir_temporal_bivalente/_elegir_adverbio_monovalente`.
- `componer_wrappers(ls_formal, ls_lexical, periferia, cfg)`: anida
  **manera → locativo → temporal → adverbio** y solo el wrapper **más interno**
  mete `[...]`. **`otro` no tiene ningún path → no se envuelve.**
- **Simplificación actual a levantar:** cada selector coge el PRIMER item de su
  categoría; los demás quedan sin envolver. Julian quiere **TODOS** los
  periféricos en la EL → hay que apilar múltiples items por estrato (§6).
- Ejemplo canónico byte-exacto que **DEBE seguir idéntico** cuando no se
  disparan capas nuevas:
  `"Ayer Juan corrió tres horas en el parque"` →
  `yesterday'(for'(tres horas, be-in'(parque, [do'(Juan, [correr'(Juan)])])))`

### `aspect_classifier/rrg_ls_mapper.py`
- Call site **líneas 923-943**: anota `cuantificada` en la periferia desnuda
  que P4 confirmó, luego `componer_wrappers(...)` y añade
  `aspect_note += " wrappers: …"`. `wrappers_ls.enabled` (default True) gatea.

### `aspect_classifier/misc_rrg.py`
- **líneas 112-114**: estampa `RRGRole=Periphery`, `RRGType=p["tipo"]`,
  `RRGDetached`. **línea 196**: el lector inverso usa `RRGType` con default
  `"otro"`. ⇒ Añadir aquí el canal del **estrato** (ver §5, `RRGStratum`).

### `ud2rrg.py` (raíz, gated por `language=='es'` + MISC)
- Bloques de anclaje por estrato que hoy hacen `RRGType=='temporal' → CLAUSE
  else CORE`: **~2696-2707**, **~2503-2504**, **~2703-2706**, y los gemelos en
  `transform_V` **~1386-1399** y **~2193-2206**. Bloque LDP/PrDP:
  **~2689-2695** y **~2495-2497** (RRGDetached=si → PrDP).
- Existe ya un slot de **periferia de NÚCLEO**: `nuc_adv.append(peri(...))`
  (**~1151, ~1350**) — reutilizar para el estrato `nucleo`.
- `peri(tree)` (**~558**) pone el sufijo `-PERI` (decisión L3: sufijo, NO nodo
  PERIPHERY, para no romper el pattern-matching de composición).

### `aspect_classifier/completeness.py` y `display_grr.py`
- `completeness._chequear_periferia` compara cada rama `-PERI` del árbol contra
  la periferia de la EL, **por estrato** (KPI de acuerdo). `display_grr` (líneas
  ~96-98, ~131-143) renderiza "periferia envuelta" y "periferia en {estrato}".
  Ambos deben conocer los estratos nuevos.

### `aspect_classifier/kpi_linking.py`
- Mide **acuerdo de periferia por estrato** y el desglose de tipos
  (contador `otro`). Es la métrica del §7.

---

## 4. NUEVO TIPADO — reglas y tablas (config.yaml)

`_tipo_periferia` deja de existir como está y pasa a devolver **DOS campos**:
`tipo` (fino) y `estrato` (nucleo|centro|clausula). Propuesta de clasificación
(todas las listas van a `config.yaml` para que Julian las edite sin tocar
código; deja DEFAULTS en el módulo como hoy):

**NÚCLEO — `tipo=aspectual`, `estrato=nucleo`** (advmod):
`_ADV_ASPECTUAL = {completamente, totalmente, íntegramente, parcialmente,
continuamente, ininterrumpidamente, incesantemente, constantemente,
gradualmente, paulatinamente, progresivamente}`.
Wrapper monovalente; pred = traducción inglesa
(`completely'/continuously'/partially'/gradually'…`) o el lema si no hay
entrada. **NO** confundir con manera (`-mente` aspectual ≠ `-mente` de modo).

**CENTRO:**
- `tipo=manera`, `estrato=centro` — advmod en `-mente` **no** aspectual y
  **no** epistémico (era el viejo `modo`). Wrapper monovalente (capa manera).
- `tipo=locativo`, `estrato=centro` — `case ∈ _CASE_LOCATIVO`. Wrapper `be-X'`
  (sin cambios salvo el estrato).
- `tipo=temporal`, `estrato=centro` — marco temporal (nombres de tiempo,
  `_ADV_TIEMPO` no-frecuencia, `obl:tmod/nmod:tmod`, `case ∈ {durante,por,
  antes,después,hasta,desde,a,en-temporal}`). Wrapper `during'/for'/at'/
  before'/after'/until'/since'` (ya existe; reactivar por/antes/después/hasta/
  desde AHORA que el estrato es explícito).

**CLÁUSULA:**
- `tipo=razon`, `estrato=clausula` — `_CASE_RAZON = {debido, "a causa de",
  gracias, por-causal}`. Wrapper bivalente `because-of'/thanks-to'`.
  (⚠ `por` es ambiguo causal/agentivo/temporal: usar `por` causal solo como
  fallback cuando NO haya lectura temporal ni sea `obl:agent`; documentar.)
- `tipo=concesion`, `estrato=clausula` — `_CASE_CONCESION = {"a pesar de",
  pese, "aun con"}`. Wrapper bivalente `despite'`.
- `tipo=condicion`, `estrato=clausula` — `_CASE_CONDICION = {"en caso de"}`.
  Wrapper bivalente `in-case-of'` (provisional; o listar como pendiente si el
  parseo de Stanza es inconsistente — decisión de Opus documentada).
- `tipo=epistemico`, `estrato=clausula` — advmod
  `_ADV_EPISTEMICO = {probablemente, posiblemente, seguramente, quizá, quizás,
  "tal vez", evidentemente, obviamente, aparentemente}`. Wrapper monovalente
  `probably'/possibly'/evidently'…` (decisión §2.2).

**FRECUENCIA (provisional, §2.3):** `tipo=frecuencia`, `estrato=centro`
(marco temporal-cuantificacional; Julian confirma el estrato al revisar).
- advmod: `_ADV_FRECUENCIA = {siempre, nunca, frecuentemente, "a menudo",
  habitualmente, "a veces", "algunas veces"}` → monovalente
  `always'/never'/frequently'…`.
- NP distributivo desnudo con det universal/distributivo (*todos los días,
  cada semana, los fines de semana*): detectar por `nombre_tiempo + det/lema
  {todo, cada}` (¡reusar la lección de `_DET_CANTIDAD` de pruebas_estructurales:
  `uno` = cantidad/duración, `todo/cada/los-definido` = frecuencia!). Wrapper
  bivalente `every'(núcleo, [LS])`.
  ⚠ Esto además **arregla** el guard de "todos los días" mal parseado por
  Stanza como `nsubj`/`obj` (ver memoria [[aspect-classifier-grrux]]): un NP
  temporal desnudo con cuantificador universal es periferia de frecuencia
  AUNQUE venga con deprel nominal.

**GENÉRICO (mata "otro") — `tipo=generico`:**
- PP sin entrada específica → `estrato=centro` (marco) por defecto; si el
  `case` está en las listas de razón/concesión/condición → `clausula`.
  Wrapper bivalente con la **preposición como predicado**: pred = traducción
  del lema de la preposición (tabla `preposiciones_predicativas` en config;
  fallback = lema español + `'`), `x` = objeto de la prep.
  Ej: `con(instrumento)` → `with'(martillo, [LS])`;
  `sin` → `without'`; preposición rara → `<lema>'`.
- Adverbio sin entrada → `estrato=centro`, monovalente con su lema
  (comportamiento `monovalente_default` que ya existe).

`_tipo_periferia` **nunca** devuelve `otro`. El default terminal es `generico`
(estrato `centro`). Elimina la rama `return "otro"`.

---

## 5. CANAL DEL ESTRATO (MISC) Y ANCLAJE EN ud2rrg

- `nucleo_periferia` añade `estrato ∈ {nucleo, centro, clausula}` a cada item.
- `misc_rrg` estampa **`RRGStratum=nucleo|centro|clausula`** junto a
  `RRGType=<tipo fino>`. Mantén `RRGType` (para display/typing) y usa
  `RRGStratum` como **fuente única del anclaje**. El lector inverso (línea 196)
  cambia su default de `"otro"` a `"generico"` y lee también `RRGStratum`
  (default `centro`).
- `ud2rrg.py` (gated `es` + MISC) ancla por `RRGStratum`:
  - `nucleo`  → `nuc_adv` (slot de periferia de núcleo ya existente) → `-PERI` bajo **NUC**.
  - `centro`  → `core2`/`core_adv` → `-PERI` bajo **CORE**.
  - `clausula`→ `clause2` → `-PERI` bajo **CLAUSE**.
  - `RRGDetached=si` → **PrDP** (sin cambios, L4.5).
  Reemplaza el viejo `RRGType=='temporal' → CLAUSE else CORE` en los CINCO
  bloques listados en §3. **Regla de oro:** cada cambio gated `language=='es'`
  y MISC presente; en/de/fr/ru/fa deben salir **byte-idénticos** (verificar,
  como en L3, con un diff sobre un puñado de oraciones por lengua).
- `destacado_inicial`: desacoplarlo del tipo. Hoy es `tipo=="temporal"`; pasa a
  `estrato in {centro, clausula} and tipo in {temporal, epistemico, razon,
  concesion}` **y** posición inicial (la heurística de `_es_destacado_inicial`
  no cambia). Recomendación conservadora: mantener el disparo de LDP **solo
  para temporal inicial** como hoy (no ampliar la casuística de dislocación en
  esta etapa) y anotar el resto como TODO. Decisión de Opus, documentada.

---

## 6. REFACTOR DE `componer_wrappers` (EL, Opción A)

Sustituye los 4 selectores "primer item por categoría" por un pipeline que:

1. Clasifica cada item de `periferia` en `(estrato, forma, pred, x?)` donde
   `forma ∈ {monovalente, bivalente}`. La clasificación reusa `tipo`/`estrato`
   ya calculados por `nucleo_periferia` (no recomputar lingüística aquí; este
   módulo sigue siendo función pura sin toks/Stanza).
2. **Apila TODOS** los items (no solo el primero por capa) respetando el orden
   de anidamiento **de dentro hacia afuera**:
   1. `nucleo` — aspectual
   2. `centro/manera`
   3. `centro/locativo` (`be-X'`)
   4. `centro/temporal-marco` (`for'/during'/at'/before'/…`, bivalente)
   5. `centro/temporal-adverbio` (`yesterday'…`, monovalente)  ·  `centro/frecuencia`
   6. `clausula/frecuencia` (si Julian la sube a cláusula) → hoy en 5
   7. `clausula/razon` · `clausula/concesion` · `clausula/condicion`
   8. `clausula/epistemico` (más externo)
   Dentro de una misma capa con varios items, orden estable por posición en la
   oración (id del token).
3. Conserva la convención de formato **byte-exacta**: solo el wrapper **más
   interno aplicado** mete `[...]` alrededor de la LS original; los siguientes
   embeben la cadena ya formateada sin corchetes extra. El ejemplo canónico de
   §3 y las 6 dianas históricas deben salir **idénticas** (test byte-a-byte).
4. `aplicado=False` para los casos detectados-pero-no-envueltos que queden
   (p.ej. si Julian decide dejar alguna sub-clase sin wrapper): el llamador los
   sigue contando. Mantener el contrato de retorno
   `(formal, lexical, aplicados)` con `aplicados[i]` = `{capa, id, trigger,
   pred, aplicado, estrato}` (añade `estrato`).

**Gating:** con `wrappers_ls.enabled=False` la EL debe salir **byte-idéntica**
a la de hoy-sin-wrappers (test como en L1b). Con `enabled=True` pero sin capas
nuevas disparadas, idéntica al ejemplo canónico.

---

## 7. KPI ANTES/DESPUÉS (obligatorio; NO tocar PUD)

Correr `kpi_linking` sobre **AnCora dev n=300** con el MISC real inyectado
(como en L4: inyectar vía `misc_rrg` antes de `transform`, si no la métrica no
ejercita el anclaje — lección de L3). Reportar en un JSON nuevo
(`data/kpi_periferia_post.json`) y en el checkpoint:

- **conversión** (debe mantenerse en **98 %**; el anclaje no debe tumbar árboles).
- **acuerdo de periferia por estrato** (46.7 %→? tras mover temporal a CORE;
  puede subir o bajar — reportar honesto, con el desglose por estrato).
- **completeness** (94.9 % de L5; no debe empeorar).
- **desglose de tipos**: el contador **`otro` debe caer a 0** (o explicar cada
  residuo). Nuevo desglose por `tipo` fino y por `estrato`.

**PROHIBIDO** correr PUD (es el examen final sellado de la fase linking).

---

## 8. TESTS

- `test_nucleo_periferia.py`: nuevas aserciones de tipado/estrato para
  aspectual, manera, locativo, temporal-marco, frecuencia (adv + NP
  distributivo), razón, concesión, epistémico, genérico. Diana obligatoria del
  bug: **"Juan aprende español los fines de semana"** → periferia
  `tipo=frecuencia, estrato=centro` (NO `otro`, NO `nsubj`).
- `test_wrappers_ls.py`: 
  - ejemplo canónico byte-exacto **intacto**;
  - "los fines de semana" **aparece en la EL** (`every'(fin, [LS])` o la forma
    que Julian fije);
  - aspectual → `complete'` en la capa de núcleo (Opción A: envuelve la LS
    completa, más interno);
  - epistémico → `probably'` como capa más externa;
  - razón/concesión → `because-of'`/`despite'` bivalentes;
  - PP genérica → preposición-como-predicado;
  - **múltiples** adjuntos del mismo estrato se apilan (no se pierde ninguno);
  - `enabled=False` → EL byte-idéntica (regresión).
- `test_ud2rrg_es.py`: anclaje por estrato — aspectual bajo **NUC**,
  manera/locativo/temporal-marco bajo **CORE**, razón/concesión/epistémico bajo
  **CLAUSE**, temporal inicial destacado en **PrDP**. Gating byte-idéntico
  en/de/fr/ru/fa.
- `test_misc_rrg.py`: `RRGStratum` en el estampado y en el lector inverso.
- Suites completas (frías; slow sin gruxx interactivo abierto) deben quedar
  verdes salvo los 2 fallos PREEXISTENTES ya documentados (`sacudió`
  semelfactive→activity; `blend_sube_pun`) — NO investigarlos aquí.

---

## 9. CHECKPOINT (entregable al terminar)

Escribir `CHECKPOINT_PERIFERIA.md` en la raíz con:
1. KPI antes/después (las 4 cifras del §7 + desglose por estrato y tipo;
   confirmar `otro=0`).
2. Verificación byte-idéntica: ejemplo canónico, 6 dianas históricas,
   gating `enabled=False`, gating en/de/fr/ru/fa.
3. La diana del bug ("los fines de semana") resuelta en árbol **y** EL.
4. Confirmación de que `contextual_sentences.csv`, `.joblib`, `models/` están
   intactos (mtime) y de que **no** se tocaron los pronombres de OD.
5. **Decisiones de implementación a revisar por Julian** (§ propio), como
   mínimo: (a) estrato definitivo de la frecuencia (centro vs cláusula);
   (b) forma final de los wrappers de frecuencia/epistémico/razón/concesión
   (¿traducción inglesa o lema español?); (c) reactivación de `por/antes/
   después/hasta/desde` como temporales — verificar que no roban lecturas
   causales/agentivas; (d) alcance del LDP (¿solo temporal inicial, o también
   razón/concesión/epistémico iniciales?); (e) qué `x` usar en la PP predicativa
   (núcleo vs NP completo — enlaza con la categoría B, fuera de scope hoy).
6. TODOs documentados que quedan FUERA a propósito: targeting exacto en la
   fórmula (Opción B: aspectual sobre el primitivo, manera sobre `do'`);
   categorías de fix A/B/C/D/F; operadores de modalidad; múltiples adjuntos con
   scope solapado.

---

## 10. NOTA DE CONTEXTO PARA OPUS

El proyecto viene de cerrar la fase linking L0–L5 (ver `CHECKPOINT_L5.md` y la
memoria). La periferia ya está **tipada, canalizada por MISC y anclada por
estrato** — esta etapa **refina** ese sistema, no lo crea: (1) parte el viejo
`otro` en tipos finos + estrato, (2) corrige el anclaje temporal (CLAUSE→CORE),
(3) mete TODA la periferia en la EL, (4) añade el canal `RRGStratum`. Trabaja
sobre lo existente; no reescribas de cero. La terminal `gruxx_ai1.py` es el
entry point real (`./venv/bin/python gruxx_ai1.py`); L5 dejó `analizar()`
inyectable, así que puedes probar oraciones sueltas sin la carga de 30 s si
reusas una instancia del clasificador.
