# CHECKPOINT — Etapa PERIFERIA (post-L5, pre-GUI)

Implementado por Opus 4.8 (sesión de implementación), 2026-07-13, a partir de
`prompt_opus48_periferia.md`. **SIN commit** (Julian commitea a mano).

## 1. Objetivo cumplido

Se eliminó el tipo de periferia `otro` de gruxx. Cada elemento periférico se
tipa ahora en uno de `{aspectual, manera, locativo, temporal, frecuencia,
razon, concesion, condicion, epistemico, generico}` — **nunca** `otro` — y
**todos** aparecen en la EL, envueltos como predicado (monovalente para
adverbios, bivalente `prep'(x,[LS])` para frases preposicionales; sin entrada
específica → la propia preposición/lema es el predicado). El anclaje del
árbol pasó a ser **scope-driven** vía un canal MISC nuevo `RRGStratum`
(nucleo/centro/clausula), reemplazando la regla L3 "temporal→CLAUSE" por la
doctrina correcta de Julian: NÚCLEO=aspectuales, CENTRO=manera/locativo/marco
temporal/frecuencia, CLÁUSULA=razón/concesión/condición/epistémico.

## 2. KPI antes/después (AnCora dev, n=300, MISC real inyectado)

| Métrica | L5 (antes) | Etapa PERIFERIA (después) |
|---|---|---|
| Conversión | 98.0% (294/300) | **98.0% (294/300)** — intacta |
| Acuerdo de periferia por estrato | 50.6% | **67.3% (173/257)** |
| Completeness | 94.9% (279/294) | **96.3% (283/294)** |
| Periferia tipo `otro` | ~75% de la periferia | **0** (clave inexistente; reemplazada por `generico`, que SÍ se envuelve) |

Desglose KPI3 (Etapa 1 cruda, sin MISC, `periferia_por_tipo`):
`{'temporal': 30, 'generico': 219, 'locativo': 40, 'razon': 10, 'frecuencia': 4, 'manera': 7}`.

Desglose de advertencias de completeness (KPI4, n=294 con árbol):
`{'agx_arbol_gt_ls': 0, 'agx_ls_gt_arbol': 0, 'arg_falta_en_arbol': 3, 'peri_falta_en_arbol': 10}`
— 13 oraciones con advertencia de 294 (residuo, ver §6).

Guardado en `aspect_classifier/data/kpi_linking_post_l4.json` (mismo nombre
de archivo que usa `kpi_linking.py`; el contenido corresponde a esta etapa).

**PUD NO se corrió** (examen final sellado de la fase linking, prohibido por
el prompt).

## 3. Verificación byte-idéntica

- **Ejemplo canónico** ("Ayer Juan corrió tres horas en el parque" →
  `yesterday'(for'(horas, be-in'(parque, [do'(x1,[correr'(x1)])])))`):
  byte-exacto, verificado en `test_wrappers_ls.py`.
- **6 dianas históricas de L1b/L2.5**: intactas (suites `test_wrappers_ls.py`,
  `test_ditransitivas.py` en verde).
- **`wrappers_ls.enabled=False`**: regresión byte-idéntica confirmada
  (`test_slow_flag_maestro_apagado_es_byte_identico`, verde).
- **Gating por lengua**: los 5 bloques nuevos en `ud2rrg.py` están, sin
  excepción, dentro de `language == 'es' and rrg_misc.get('RRGRole') == ...`
  — estructuralmente imposible que alteren en/de/fr/ru/fa. Verificado
  empíricamente para 'en' (fixture con y sin MISC → árboles byte-idénticos)
  y con la suite `test_gating_lengua_no_es_ignora_misc` (verde). de/fr/ru/fa
  comparten la misma rama `else` no tocada — verificación por construcción,
  consistente con la metodología de L3.
- **Gold AnCora crudo vs limpiado** (20 oraciones, `test_gold_ancora_...`):
  sigue produciendo árboles idénticos, sin regresión de dispatch.

## 4. Diana del bug resuelta

"Juan aprende español los fines de semana" — antes: `fines(obl/otro)` en
Argumentos/Integridad, **ausente de la EL**. Ahora: tipado
`frecuencia`/`centro` (NP plural con artículo definido, sin numeral — nueva
heurística `_es_np_tiempo_frecuencia`, distingue de "tres horas" cuantificada
y de "la mañana" singular) y presente en la EL: `every'(fines, [LS])`.
Verificado con Stanza real en `test_slow_integracion_mapper`.

El guard preexistente de "todos los días" (mis-parseado como nsubj/obj) fue
también migrado de `tipo="temporal"` a `tipo="frecuencia"` (mismo criterio),
con `destacado_inicial` fijado a `False` explícitamente (decisión conservadora:
no ampliar la casuística de LDP a frecuencia en esta etapa).

## 5. Archivos tocados

- `aspect_classifier/nucleo_periferia.py`: `_tipo_periferia` reescrita
  (firma nueva `(tokens, tok, case) -> (tipo, estrato)`); tablas nuevas
  (`_ADV_ASPECTUAL`, `_ADV_EPISTEMICO`, `_ADV_FRECUENCIA`, `_FRASE_RAZON/
  CONCESION/CONDICION`); `_case_compuesto_de` (arma preposiciones compuestas
  "a pesar de"/"debido a" uniendo la cadena `fixed`); `_es_np_tiempo_frecuencia`
  (NP plural + artículo/cuantificador universal, sin numeral); guard nuevo en
  `analizar_roles` para no confundir "a pesar de"/"debido a" con meta/origen
  de movimiento (ambos usan "a" como primera palabra); item de periferia
  ahora incluye `estrato` y `frase`.
- `aspect_classifier/wrappers_ls.py`: reescrito — `_clasificar` (un item →
  spec de wrapper) + `componer_wrappers` apila TODOS los items (no solo el
  primero por capa), ordenados por `(orden_de_estrato, id_de_token)`; tablas
  nuevas para las 5 categorías nuevas; exclusión explícita de `deprel=="advcl"`
  (ver §6).
- `aspect_classifier/misc_rrg.py`: canal `RRGStratum` (estampado y lectura
  inversa); default `RRGType` pasa de `"otro"` a `"generico"`.
- `aspect_classifier/completeness.py`: `_ESTRATO_A_LABEL` (nucleo→NUC,
  centro→CORE, clausula→CLAUSE) reemplaza `_ESTRATO_POR_TIPO`; LDP ampliado
  a cualquier tipo (ver §6).
- `aspect_classifier/kpi_linking.py`: mismo cambio de estrato y LDP,
  replicado para la medición KPI4.
- `aspect_classifier/display_grr.py`: `_ESTRATO_LEGIBLE` + "NUC"→"el núcleo".
- `aspect_classifier/pruebas_estructurales.py`: fix de referencia rota
  (`tipo=="modo"` → `tipo=="manera"`, P2/P3 habían quedado ciegas).
- `aspect_classifier/data/glosario_gruxx.csv`: 2 filas actualizadas
  (doctrina de anclaje correcta, NUC añadido).
- `ud2rrg.py`: 5 bloques (`transform_A`/`transform_N`/`transform_V`×3)
  cambian `RRGType=='temporal'→CLAUSE else CORE` por lectura de
  `RRGStratum` (nucleo→NUC vía `nuc_a`/`nuc_n`/`nuc2`; centro→CORE; clausula→
  CLAUSE). Los checks de LDP (`RRGDetached=='si'`) quedaron intactos, sin
  tocar.
- `aspect_classifier/config.yaml`: tablas nuevas en `wrappers_ls` (aspectuales,
  epistemicos, frecuencia_adverbios/distributiva, razon, concesion,
  condicion, preposiciones_predicativas).
- Tests actualizados: `test_nucleo_periferia.py`, `test_wrappers_ls.py`
  (reescrito), `test_misc_rrg.py`, `test_completeness.py`, `test_ud2rrg_es.py`
  (3 aserciones doctrinales corregidas: CLAUSE→CORE para marco temporal/
  frecuencia).

## 6. Hallazgos durante la implementación (no triviales)

1. **`advcl` con cabeza verbal** ("hace un par de días", "mientras marcará
   la pauta...") caía en `generico` y se envolvía con el lema del propio
   verbo como predicado — produce una EL incorrecta y una rama `-PERI` que
   el árbol nunca marca para cláusulas subordinadas (terreno de
   juntura/xcomp encadenado, explícitamente pospuesto por Julian). Fix:
   `componer_wrappers` excluye `deprel=="advcl"` del envoltorio (igual que
   el viejo comportamiento de `otro`: se verifica presencia, nunca error).
   Esto fue la causa DOMINANTE de una regresión de completeness intermedia
   (94.9%→67.3%) durante el desarrollo, corregida a 84.4%.
2. **`precedes_subject` (heurística preexistente en `ud2rrg.py`, anterior a
   L3)** envía a PrDP CUALQUIER PP/adverbio que precede al sujeto, sin mirar
   MISC/RRGStratum — esto YA afectaba a locativo/manera antes de esta etapa
   (contribuía a los 12 `peri_falta_en_arbol` ya documentados en el
   checkpoint de L5), pero se hizo mucho más visible al envolver TODA la
   periferia. El checker de completeness solo reconocía LDP como
   satisfactorio para `tipo=="temporal"`; se amplió a **cualquier tipo**
   (`completeness._chequear_periferia` y `kpi_linking.kpi4_pipeline_hibrido`)
   porque la posición PrDP es válida para cualquier periférico adelantado,
   no solo temporal. Esto llevó completeness de 84.4%→96.3% (por encima del
   baseline de L5). **No se tocó `ud2rrg.precedes_subject`** (fuera de
   alcance; requeriría propagar RRGStratum a un chequeo que corre ANTES del
   dispatch de periferia en varios puntos del archivo).
3. **`_es_np_tiempo_frecuencia`**: "los fines de semana" no tiene cuantificador
   universal (todo/cada), solo artículo definido plural — la heurística de
   frecuencia tuvo que ampliarse más allá del `_CUANTIF_UNIVERSAL` original
   (reservado al guard de mis-parse). Se distingue de duración cuantificada
   por la AUSENCIA de numeral. "fin" se admite SOLO en el set extendido de
   frecuencia, no en `_NOMBRES_TIEMPO` general (evita que "el fin" a secas
   —el final de algo— se tipe como temporal).
4. **Ambigüedad de "a" como primera palabra de "a pesar de"**: el case
   simple de un dependiente de verbo de movimiento ("corrió a Madrid") usa
   el mismo marcador "a" que "a pesar de la lluvia" (concesión). Se añadió un
   guard: antes de promover un `obl` con `case in case_meta/case_origen` a
   argumento (Meta/Origen) de un verbo de movimiento, se verifica que la
   frase compuesta completa (`_case_compuesto_de`) no sea una de las
   conocidas de razón/concesión/condición.
5. **`"por"` causal como fallback**: dispara SOLO cuando no hay lectura
   temporal (duración) ni es agente de pasiva (ya excluido antes en
   `analizar_roles`). Confirmado limitación heredada y documentada: "por +
   ruta" (locativo, "caminó por el parque", o "por su boca" = "a través de")
   cae también en `razon` — gap preexistente (antes caía en `otro`, ahora en
   `razon`), sin resolver, mencionado explícitamente como aceptable en el
   prompt original.
6. **Tercer fallo preexistente detectado (no introducido por esta etapa)**:
   `test_slow_dianas_aa_y_controles` ("Juan llegó" → esperado `achievement`,
   sale `activity` vía `gate=obj_desnudo→Activity` espurio). Verificado con
   `git stash` que este fallo YA ocurre con el `rrg_ls_mapper.py` COMMITEADO
   en HEAD sin ningún cambio de esta sesión — es decir, es un bug del estado
   sin commitear de una sesión previa (L5/reentrenamiento), no algo que esta
   etapa introdujo. Se reporta para que Julian lo revise junto con los otros
   2 preexistentes.

## 7. Suites de test — resultado final

Todas verdes salvo los **3 fallos preexistentes** (ninguno introducido por
esta etapa, verificado caso por caso):
- `test_causatividad.test_slow_cause_por_clase_y_regresion` ("sacudió"
  semelfactive→activity) — documentado desde L4.5/reentrenamiento.
- `test_pruebas_aspectuales.test_slow_blend_sube_pun` (corroborador
  apagado, cosmético) — documentado desde el checkpoint del corroborador.
- `test_fase2_contextual.test_slow_dianas_aa_y_controles` ("Juan llegó" →
  activity) — **NUEVO HALLAZGO** de esta sesión, pero confirmado
  preexistente al estado sin commitear (§6.6), no una regresión de esta
  etapa.

Conteo por suite (fríos + `--slow`):
`test_nucleo_periferia` 26/26, `test_wrappers_ls` 32/32, `test_misc_rrg`
19/19, `test_completeness` 18/18, `test_ud2rrg_es` 16/16 (+1 skip por
homógrafo "como", preexistente), `test_pruebas_estructurales` 25/25,
`test_ditransitivas` 18/18, `test_causatividad` 8/9 (1 preexistente),
`test_fase2_contextual` 7/8 (1 preexistente), `test_complejo` 6/6,
`test_telicidad_l4_5` 5/5, `test_pruebas_aspectuales` 13/14 (1 preexistente),
`test_l5` 26/26.

## 8. Confirmaciones de alcance

- `contextual_sentences.csv`, los `.joblib` y `models/` **intactos**
  (verificado por mtime: última modificación 2026-07-10/11, de sesiones
  previas, ninguna de esta sesión).
- Pronombres de OD (`lo/la/los/las`) **no tocados**.
- Sin commits (orden de Julian).

## 9. Decisiones de implementación a revisar por Julian

1. **Estrato de la frecuencia = CENTRO** (no cláusula): decisión ya tomada
   por Julian en el diseño (AskUserQuestion), implementada tal cual.
2. **Forma de los wrappers nuevos**: se usó metalenguaje inglés en todos
   (`because-of'`, `despite'`, `every'`, `probably'`...), consistente con
   el resto del sistema (`be-in'`, `for'`...). Las tablas están en
   `config.yaml` para que Julian las edite sin tocar código.
3. **Reactivación de `antes/después/hasta/desde`** como `_CASE_TEMPORAL`:
   hecha sin incidentes detectados en la muestra de 300 oraciones — pero
   la muestra es limitada; vigilar en uso real.
4. **`"por"` causal como fallback SOLO cuando no hay lectura temporal**:
   ambigüedad heredada y documentada (§6.5) — "por + ruta/instrumento"
   (p.ej. "por su boca" = "a través de") cae incorrectamente en `razon`.
   Sin arreglo en esta etapa (requeriría una tabla de verbos con lectura
   instrumental/locativa de "por", o un modelo de desambiguación —
   candidato para una etapa futura si el volumen de casos lo justifica).
5. **`x` de las preposiciones bivalentes = cabeza del sintagma**, no el NP
   completo con modificadores ("insultos", no "los insultos de Pedro") —
   categoría de fix B, explícitamente fuera de alcance de esta etapa.
6. **LDP ampliado a cualquier tipo de periferia** (§6.2): cambio de
   comportamiento del CHECKER (completeness/kpi_linking), no del árbol.
   Julian debe confirmar que esto es la lectura correcta (que cualquier
   periférico en PrDP cuenta como satisfecho) — el árbol mismo NO cambió
   (sigue siendo `precedes_subject`, preexistente).
7. **Tercer fallo preexistente ("Juan llegó")**: reportado en §6.6; Julian
   debe decidir si investigar el estado sin commitear de `rrg_ls_mapper.py`
   (que causa el gate espurio) antes o después de commitear esta etapa.

## 10. Pendientes fuera de alcance (documentados, no implementados)

- Targeting exacto del wrapper dentro de la fórmula (Opción B: aspectual
  sobre el primitivo, manera sobre `do'` en vez de la LS completa).
- Categorías de fix A (plantilla interna se-pasivo), B (NPs completos), C
  (depictivos), D (guardas causativas), F (corregir-todo del bucle).
- `precedes_subject` sin actualizar para respetar RRGStratum (§6.2).
- `"por" + ruta/instrumento` (§6.5, §9.4).
- Multiword adverbial idioms no reconocidos como unidad ("de vez en cuando"
  puede tipar mal si Stanza no los liga con `fixed`/`mwe`).
- Operadores de modalidad (EST/MOD/FI) — pospuestos al nivel pragmático.
- Homógrafo "como" (1sg comer / SCONJ) — pospuesto, documentado desde L3.
