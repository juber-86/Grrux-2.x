# CHECKPOINT — Etapa LA1 (el linking algorithm explícito)

Implementa `prompt_LA1.md`. **Sin commits.** `ud2rrg.py` completo, clasificador
(predict/classifier/decision_tree/.joblib), corroborador MLM y
`contextual_sentences.csv` intactos. PUD intocado. Etapa **ADITIVA**: ninguna
clase, EL ni gold cambió — se verificó explícitamente (§5 de este informe).

---

## 1. Traza completa de 5 pasos (ditransitiva + se-pasivo)

### "Juan le dio flores a María." — ditransitiva (ejemplo canónico)

```
EL léxica  : ⟨IF DEC ⟨TNS PAST ⟨[do'(Juan, Ø)] CAUSE [BECOME have'(María, flores)]⟩⟩⟩
Argumentos : x1:Juan,nsubj,Actor(Efectuador); x2:flores,obj,Undergoer(Tema); x3:María,obl:arg,NMR(Poseedor)

Linking: Actor=Juan (1er arg. de do') · Undergoer=flores (2º arg. de have') ·
         María=NMR · M-transitivo=2 · PSA=Actor · concordancia 3sg ✓

  Paso 1 — EL seleccionada: plantilla transferencia (fuente: lexico) · clase aspectual: accomplishment
  Paso 2 — Macropapeles (AUH): Actor=Juan (1er arg. de do') · Undergoer=flores (2º arg. de have') ·
           María=NMR (1er arg. de have') · M-transitivo=2
  Paso 3 — Codificación: PSA=Actor (voz activa) · caso: Juan=nominativo (PSA), flores=acusativo,
           María=dativo ('a') · concordancia esperada: PSA 'Juan' 3sg vs verbo 3sg ✓
  Paso 4 — Plantilla sintáctica: 3 posición(es) core con constituyente propio · posiciones especiales: AGX×1
  Paso 5 — Asignación: x1↔NP · x2↔NP · x3↔PP · AGX✓

Completeness: ✓ x1↔NP x2↔NP x3↔PP · AGX✓ · producción: 3 posición(es) core esperada(s) por la EL,
              3 con constituyente en el árbol · PSA 'Juan' 3sg vs verbo 3sg ✓ ·
              producción: AGX esperado por la EL y presente en el árbol
```

La línea compacta coincide **byte a byte** con el ejemplo del prompt (§4). Verificado con
`test_linking.py::test_slow_linea_compacta_ditransitiva_byte_a_byte`.

### "Se venden casas." — se-pasivo/anticausativo (con hallazgo, ver §2)

```
EL léxica  : ⟨IF DEC ⟨TNS PRES ⟨[do'(Ø, Ø)] CAUSE [do'(casas, [vender'(casas)])]⟩⟩⟩
Argumentos : x1:Ø,—,causante inespecificado; x2:casas,nsubj,Undergoer(paciente→PSA)

Linking: Actor=casas (1er arg. de do') · Undergoer=— · M-transitivo=1 · PSA=—

  Paso 1 — EL seleccionada: plantilla causativa (heuristico_anticausativo_se) (fuente: heuristic) ·
           clase aspectual: activity
  Paso 2 — Macropapeles (AUH): Actor=casas (1er arg. de do') · Undergoer=— · M-transitivo=1
  Paso 3 — Codificación: PSA=— (voz anticausativa) · caso: casas=acusativo ·
           concordancia esperada: sin PSA: no aplica concordancia
  Paso 4 — Plantilla sintáctica: 1 posición(es) core con constituyente propio · posiciones especiales: ninguna
  Paso 5 — Asignación: x1: sin id de token rastreable

CAUSE      : heuristico_anticausativo_se (heuristic, conf. baja)
Completeness: ✓ x1: sin id de token rastreable · producción: 1 posición(es) core esperada(s)
              por la EL, 1 con constituyente en el árbol
```

Este caso **discrepa** con `args_map` (Ø bloqueado para Actor no aplica aquí porque "casas"
queda del lado equivocado del AUH) — ver diagnóstico completo en §2. El test frío
`test_se_venden_casas_o_bloqueado_para_actor` verifica el ALGORITMO con la estructura
`[do'(Ø,Ø)] CAUSE [BECOME sold'(casas)]` **teóricamente correcta** (la del prompt):
ahí sí da `Actor=None, Undergoer=casas(arg. de estado sold')` como se pide.

---

## 2. Tabla de reconciliación §3 (34 oraciones, batería completa)

Script: `aspect_classifier/informe_linking_dianas.py` (solo lectura, no toca ningún
gold). **3/34 oraciones con discrepancia AUH↔args_map** — las tres son bugs
**preexistentes** de la etapa de composición de EL (categorías ya conocidas por
Julian, ninguna causada ni tocada por LA1):

| # | Oración | AUH dice | args_map dice | Diagnóstico |
|---|---|---|---|---|
| 1 | "el pastel fue comido por Juan" | Actor=pastel, Undergoer=Juan | Undergoer=pastel, Actor=Juan | **x1/x2 ligados por ORDEN DE SUPERFICIE, no por macrorrol.** `map_sentence_to_ls` asigna `args['x1']`/`args['x2']` recorriendo `roles['core']` en orden de id de token — en una pasiva el sujeto (pastel, Undergoer) aparece ANTES que el agente oblicuo (Juan, Actor) en la oración, así que x1=pastel/x2=Juan. La plantilla `do'(x1,[comer'(x1,x2)])` asume x1=agente/x2=paciente POR DISEÑO — para esta pasiva termina prestándole el "1er arg. de do'" (posición Actor) al PACIENTE. `args_map`, en cambio, sí es correcto (deriva el macropapel del `deprel`, independiente del orden). **No es un bug de LA1**: es la primera vez que algo compara ambas vías y lo hace visible. |
| 2 | "Se venden casas" | Actor=casas | Undergoer(paciente→PSA)=casas | **Categoría de fix A, ya reportada por Julian en el feedback post-L5** ("el interior debe ser el ESTADO RESULTANTE, no una actividad con el paciente como efector"). `componer_cause` anida el paciente de un `se`-anticausativo cuya base léxica es Activity dentro de un `do'` EMBEBIDO (`do'(casas,[vender'(casas)])`), así que "casas" cae en "1er arg. de do'" en vez de "arg. de estado". Vender no está en `causative_lexicon.csv`: dispara el heurístico, que no distingue esta plantilla de la de un verdadero anticausativo de cambio de estado. |
| 3 | "Se vende casas" | (ídem) | (ídem) | Mismo caso que #2 (es el fixture del warning de concordancia, ver §3). |

**Ninguna otra de las 34 oraciones discrepa** — incluida la propia ditransitiva
(transferencia/benefactiva/comunicación, 3 verbos), las 6 causativas léxicas
transitivas (asustar/destrozar/secar/destellar/rodar/pasear), el anticausativo
léxico correcto ("el jarrón se rompió"), el estado de 2 lugares ("Juan sabe la
respuesta"), la G-AA-medida ("Juan corrió cinco kilómetros" → Undergoer=kilómetros)
y las 3 copulativas (sin §3 por diseño, ver más abajo). Esto es una validación
fuerte de que el algoritmo AUH está bien calibrado contra el resto del pipeline.

**Hallazgo adicional, menor, dependiente de configuración** (no en la tabla porque
no aparece con la config por defecto en una sola oración): al correr la suite
completa se registró una discrepancia para "tosió durante una hora" (Undergoer
según AUH vs "Actor(implícito)" que la etiqueta de pro-drop pone SIEMPRE, sin
mirar la clase verbal) — reproducible solo si `pruebas_estructurales` no llega a
coercionar Semelfactive→Activity antes de construir la EL (en ese caso "toser"
queda de clase base Semelfactive, un solo argumento en "arg. de estado", que el
AUH lee correctamente como Undergoer aunque la etiqueta de pro-drop diga
"Actor(implícito)" sin condicionarse a la clase). Con la configuración normal
(§5, batería sin regresión) esta oración da M=1/Actor/coincide, como se ve en la
tabla — se deja documentado por si reaparece.

**Copulativas SIN reconciliación §3** (decisión de alcance, no un hueco):
`arg_meta` en esa rama etiqueta el macropapel con el literal `"Agent"` (no
`"Actor"`/`"Undergoer"` — inconsistencia terminológica preexistente de esa rama,
ajena a LA1); comparar contra eso solo generaría ruido. `linking.py` sí calcula
macropapeles/PSA/concordancia normalmente para copulativas (ver "Juan es médico"
→ Undergoer=Juan(arg. de estado be'), PSA=Undergoer, en la batería).

Las 4 filas de discrepancia real quedaron en `data/linking_discrepancias.csv`
(append-only, deduplicado por lema+oración+texto — mismo patrón que
`causative_candidates_heuristico.csv`/`ditransitivos_candidatos.csv`).

---

## 3. El warning de concordancia — demostrado con oración real

Sin fixture: `"Llegó los invitados."` (verbo singular, sujeto plural) vs
`"Llegaron los invitados."` (concuerda):

```
Llegó los invitados.
  Linking: Actor=invitados (1er arg. de do') · Undergoer=— · M-transitivo=1 ·
           PSA=Actor · concordancia 3sg ⚠
  Paso 3 — Codificación: ... concordancia esperada: PSA 'invitados' 3pl vs verbo 3sg ✗
  Completeness: ⚠ x1↔NP · producción: 1/1 con constituyente · PSA 'invitados' 3pl vs verbo 3sg ✗

Llegaron los invitados.
  Linking: Actor=invitados (1er arg. de do') · Undergoer=— · M-transitivo=1 ·
           PSA=Actor · concordancia 3pl ✓
  Completeness: ✓ x1↔NP · producción: 1/1 con constituyente · PSA 'invitados' 3pl vs verbo 3pl ✓
```

El ⚠ se propaga correctamente hasta el símbolo GLOBAL de Integridad (antes ✓,
ahora ⚠) — confirma que el chequeo de concordancia (§5, round-trip) está
integrado al informe existente, no es un dato suelto. Verificado también en frío
con el fixture literal del prompt ("Se vende casas" → PSA 'casas' 3pl vs verbo
'vende' 3sg ✗) en `test_advertencia_concordancia_demo_se_vende_casas`, y en vivo
en `test_slow_concordancia_real_llego_los_invitados`.

---

## 4. Captura GUI del panel Linking

Verificado en vivo contra `gruxx-gui` (servidor real, Stanza+BERTIN cargados) con
la oración ditransitiva. El panel "Linking" aparece entre "Causatividad" y
"Notas", con la línea compacta y los 5 pasos numerados por el propio `<ol>`
(sin duplicar el número en el texto — se recorta el prefijo "Paso N —"):

- DOM (`textContent`), verificado carácter a carácter:
  `Linking: Actor=Juan (1er arg. de do') · Undergoer=flores (2º arg. de have') ·
  María=NMR · M-transitivo=2 · PSA=Actor · concordancia 3sg ✓` — idéntico a la
  línea de terminal.
- Los 8 términos (`Actor`, `Undergoer`, `PSA`, `NMR`, `M-transitivo`,
  `concordancia`, `AGX`, `nominativo/acusativo/dativo`) salen envueltos en
  `<span class="linking-term" title="...">` con la definición del glosario —
  confirmado por color computado `rgb(255, 138, 101)` (`--linking`, el mismo
  naranja reservado para esta etapa) y borde punteado a juego.
- Captura visual (`preview_start` + `computer screenshot`, ventana 1280×1600):
  se ve el bloque "LINKING" completo con los términos resaltados en naranja y
  los 5 pasos listados, justo debajo de "INTEGRIDAD" (que ya muestra los chips
  verdes `producción: 3 posición(es) core esperada(s)...`, `concordancia: PSA
  'Juan' 3sg vs verbo 3sg ✓`, `producción: AGX esperado...`).
- El glosario lateral recibió las 13 entradas nuevas (categoría "Linking") y
  aparecen correctamente agrupadas y con hover funcionando.

(Nota: el mecanismo de screenshot de este entorno tuvo hipos intermitentes con
posiciones de scroll intermedias — se resolvió agrandando la ventana; la
verificación de CONTENIDO se hizo por triplicado: `get_page_text`,
`read_page` accesible y `textContent`/`getComputedStyle` vía JS, las tres
formas coinciden.)

---

## 5. Suites

- **Rápidas** (`pytest`, sin `--slow`): **351 passed, 34 skipped** (0 fallos).
  Incluye `test_linking.py` (28 fríos).
- **Lentas** (`RUN_SLOW=1 pytest`): **381 passed, 1 skipped, 3 failed** — los
  **3 fallos son EXACTAMENTE los mismos ya documentados como preexistentes**
  desde `CHECKPOINT_OPERATORS_2.md` §5 (territorio clasificador/corroborador,
  no de EL ni de linking):
  - `test_causatividad::test_slow_cause_por_clase_y_regresion` ("el perro se
    sacudió": activity vs semelfactive esperado)
  - `test_fase2_contextual::test_slow_dianas_aa_y_controles` ("Juan llegó":
    activity vs achievement esperado)
  - `test_pruebas_aspectuales::test_slow_blend_sube_pun` (corroborador,
    diferencia de 0.0036 en el vector `pun`)

  `test_linking.py --slow` (6 pruebas): **todas verdes**, incluida
  `test_slow_bateria_sin_regresion_de_clase_ni_el` (6 dianas históricas,
  `ls_type`/`ls_formal`/`ls_lexical`/`args_map` byte-idénticos con y sin LA1) y
  `test_slow_flag_apagado_byte_identico` (con `linking.enabled: false`, CERO
  claves nuevas — `ls_estructura` y `linking` ausentes — y el resto del dict
  byte-idéntico, verificado por comparación de dict completo, no solo por
  spot-checks).
- Dos tests de **contrato de la GUI** (`test_gruxx_motor.py`,
  `test_gruxx_server.py`) se actualizaron para incluir la clave nueva
  `linking` en el set esperado — mismo mantenimiento que hizo OPERATORS_2 con
  `_CLAVES_SUB`/`operadores`.
- `causative_candidates_heuristico.csv` ganó 4 filas ("vender" vía heurístico,
  disparadas por las oraciones de prueba de esta etapa) — mecanismo
  preexistente, append-only, ninguna fila falsa.

---

## 6. Diseño (resumen para referencia rápida)

- **`aspect_classifier/linking.py`** (nuevo, puro): `AUH` (constante, 5
  posiciones, verificada 1:1 contra `continuum_de_relaciones_tematicas.xlsx`),
  `asignar_macropapeles`, `detectar_voz`, `seleccionar_psa`,
  `verificar_concordancia`, `traza_linking`/`paso_5_asignacion`,
  `expectativas_sintacticas` (round-trip, helpers de árbol propios —
  deliberadamente duplicados de `completeness.py` para evitar el ciclo de
  import, `completeness.py` es quien importa `linking.py`, no al revés),
  `reconciliar`/`log_discrepancia` (§3), `enriquecer_ids`/`frame`/`arg`
  (helpers de `ls_estructura`).
- **`ls_estructura`**: generada por `build_ls`, `causatividad.componer_cause`
  y `ditransitivas.construir_el` — texto + posición AUH (`arg_de_DO | 1_do |
  1_pred_xy | 2_pred_xy | arg_estado`), sin ids (los constructores de EL no
  los conocen). El mapper la enriquece con ids DESPUÉS, cruzando
  `id_a_var`/`toks` — necesario porque `variables`/`core` pueden quedar
  obsoletos tras causatividad/ditransitivas (mismo fenómeno que ya documenta
  `completeness.py` sobre esas dos claves).
- **Regla de M=1** (un solo macropapel): rango arg_de_DO/1_do/1_pred_xy →
  Actor; rango 2_pred_xy/arg_estado → Undergoer. Cubre tanto intransitivos
  agentivos ("Juan corrió") como no-agentivos/unaccusative ("Juan llegó", "el
  jarrón se rompió", las copulativas). **TODO documentado**: la doble ruta
  psych de la jerarquía (verbos de percepción/emoción) no se resuelve — es
  el default no marcado, tal como anticipa el prompt.
- **PSA**: activa → Actor si existe, si no el Undergoer único (intransitivos
  no agentivos); pasiva/anticausativa → Undergoer siempre (aunque haya
  Actor, p.ej. agente de pasiva); impersonal/M=0 → sin PSA.
- **NMR "oblicuo"** (extensión de alcance no pedida explícitamente, pero
  necesaria para que las locativas no compitan por macropapel): el objeto de
  un predicado `be-X'` se marca `nmr=True` igual que el dativo, con caso
  "oblicuo (locativo)" en vez de "dativo ('a')" en el paso 3 de la traza.
- **`completeness.py`**: `_chequear_linking` nuevo, llama a
  `linking.expectativas_sintacticas` cuando `ls_data['linking']` existe;
  extiende `checks` con estados `linking_ok` / `linking_falta_en_arbol` /
  `linking_concordancia_error`; `ok` global ahora también depende de esos dos
  últimos. Vacío (sin tocar nada) si la etapa está apagada.

---

## 7. Pendientes que esta etapa deja listos para después

(los mismos tres que anticipa el prompt, más los hallazgos de §2)

1. **Doble ruta psych de la jerarquía** — verbos de percepción/emoción con
   Actor/Undergoer intercambiables según construcción; hoy resuelto por el
   default no marcado (documentado en `asignar_macropapeles`).
2. **Reforma de notación x/y** — NO tocada (guardada explícitamente: LA1 usa
   solo texto y posiciones nombradas, nunca profundiza x1/x2/x3).
3. **Dirección de producción GENERATIVA real** (generar oración desde la
   EL) — futuro lejano; esta etapa usa la dirección de producción solo como
   re-derivación verificadora (round-trip) sobre el árbol que ya existe.
4. **Las 3 discrepancias de §2** — categorías A (se-pasivo, ya reportada) y
   la nueva (x1/x2 por orden de superficie en pasivas perifrásticas) quedan
   para que Julian decida si se abre una etapa de arreglo — LA1 no las toca.
5. **PrCS** (interrogativas) no se implementó en el round-trip — mencionado
   en el prompt (§5) junto con AGX/LDP, pero no hay maquinaria de detección
   de interrogativas en el resto del pipeline todavía (el propio LDP para
   temporales destacados sí se reutiliza vía `periferia[].destacado_inicial`
   en el paso 4 de la traza).

---

## 8. Archivos tocados

**Nuevos**: `aspect_classifier/linking.py`, `aspect_classifier/test_linking.py`,
`aspect_classifier/informe_linking_dianas.py`,
`aspect_classifier/data/linking_discrepancias.csv`, `CHECKPOINT_LA1.md`.

**Modificados**: `rrg_ls_mapper.py` (`build_ls` +`estructura` por rama,
wiring de `linking.analizar_linking`/reconciliación/log, copulativas
incluidas), `aspect_classifier/causatividad.py` (`componer_cause`
+`estructura`), `aspect_classifier/ditransitivas.py` (`construir_el`
+`estructura`, NMR en el recipiente/receptor), `aspect_classifier/completeness.py`
(`_chequear_linking`, `ok` extendido), `aspect_classifier/display_grr.py`
(`linea_linking`, `traza_linking`, wireado en `render_bloque`),
`gruxx_motor.py` (`_linking_de`, clave `linking` en `construir_sub_oracion`),
`aspect_classifier/config.yaml` (`linking.enabled`),
`aspect_classifier/data/glosario_gruxx.csv` (+13 entradas, categoría
"Linking"), `gui/index.html` + `gui/app.js` + `gui/estilo.css` (panel
Linking, hover de términos, chips `linking_*`), `test_gruxx_motor.py` +
`test_gruxx_server.py` (contrato +`linking`).
