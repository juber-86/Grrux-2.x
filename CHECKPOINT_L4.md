# Checkpoint — Fase LINKING, Etapa L4 (checker de completeness + medición honesta + examen PUD)

Implementado según `prompt_opus48_linking_L4.md`. **PARAR aquí** — cierra la
fase LINKING (L0→L4). Commit final pendiente (ver nota de higiene al
final).

Modificado: `ud2rrg.py` (obl:arg bajo NOMINAL/ADJETIVAL en `transform_N`/
`transform_A`, `expl:pass`/`expl:impers`→AGX en `transform_V`; todo gated
`language=='es'`, régimen L3 intacto), `gruxx_ai1.py` (ahora libremente
editable: checker de completeness ONLINE en los 3 modos), `aspect_classifier/
kpi_linking.py` (KPI4, pipeline híbrido real), `aspect_classifier/misc_rrg.py`
(`leer_ls_desde_misc`, inverso del canal MISC), `aspect_classifier/
test_ditransitivas.py` (test dinámico), `aspect_classifier/test_ud2rrg_es.py`
(fixtures nuevas + slow end-to-end). Código nuevo: `aspect_classifier/
completeness.py`, `aspect_classifier/test_completeness.py`. Prohibiciones
respetadas (`predict.py`, `classifier.py`, `decision_tree.py`, corroborador
MLM, `pruebas_estructurales.py`, `.joblib`, `contextual_sentences.csv`
intactos).

## 1. KPI — tabla completa L0 → L3 → L4 (AnCora dev, n=300)

| Métrica | L0 (`kpi_linking_baseline.json`) | L3 (`kpi_linking_post_l3.json`) | L4 (`kpi_linking_post_l4.json`) |
|---|---|---|---|
| Conversión (xpos stripped, pipeline real) | 59.7% (179/300) | 87.0% (261/300) | **98.0%** (294/300) — con MISC real inyectado |
| Acuerdo de periferia | 27.6% | 28.8%* | — (ver fila siguiente, KPI2 se mantiene solo como referencia histórica) |
| **Acuerdo de periferia POR ESTRATO (medición honesta, nueva)** | no medido | no medido | **46.7%** (120/257) |
| **Tasa de completeness (nueva, checker §1)** | no medía | no medía | **59.2%** (174/294) |

\* La cifra de L3 (28.8%) **no medía el fix**: `kpi2_desacuerdo_periferia`
corre `ud2rrg.transform` sobre el gold SIN inyectar MISC, y el anclaje por
estrato de L3 es 100% MISC-gated — sigue en el script (renombrada
`kpi2_desacuerdo_periferia_sin_misc`) solo como referencia histórica de
"qué mediría un observador externo que ignora MISC", no como KPI de
progreso. **KPI4 (`kpi4_pipeline_hibrido_l4`) es la medición real de L4**:
por oración, corre Etapa 1 + el mapper completo (roBERTa) sobre la sintaxis
gold, inyecta el MISC resultante, y SOLO ENTONCES convierte — así sí
ejercita el anclaje por estrato.

El salto de conversión 87.0%→98.0% combina dos mejoras de L4: (a) el MISC
real ahora se inyecta antes de convertir (antes ni se probaba), y (b) los
flecos de dispatch del §3 (`obl:arg` bajo cabeza NOMINAL/ADJETIVAL,
`expl:pass`/`expl:impers`→AGX) — verificado manualmente que ambos disparan
sobre gold AnCora real (6/6 oraciones con `expl:pass`/`expl:impers` de una
muestra convirtieron con nodo AGX; ver `test_se_pasiva_refleja_agx_y_nsubj_pass_como_np`
y `test_nominalizacion_obl_arg_bajo_noun_convierte` para las fijaciones
frías correspondientes).

Conteos KPI3 sin cambios de fondo (doblado 9, clítico solo 27, obl:arg
total 126, periferia por tipo ~igual) — la muestra estructural del
treebank no cambia, solo cuánto de ella logra convertir y cuánto de esa
conversión resulta *correcta* (que es justo lo que KPI4 añade a medir).

## 2. Examen final — UD_Spanish-PUD (n=1000, UNA SOLA VEZ)

Corrido al final, con todo lo demás ya validado (suite verde, KPI de
AnCora medido). **No se iteró ni se ajustó nada mirando estos resultados.**
Guardado en `data/kpi_pud_final.json`.

| Métrica | AnCora dev (n=300) | PUD test (n=1000) |
|---|---|---|
| Conversión | 98.0% (294/300) | 94.1% (941/1000) |
| Acuerdo de periferia por estrato | 46.7% (120/257) | **65.9%** (650/986) |
| Tasa de completeness | 59.2% (174/294) | 61.8% (582/941) |

Conversión algo más baja en PUD (esperable: convenciones de anotación
distintas — PUD es un treebank multi-dominio traducido, con oraciones más
largas y estructuras (`xcomp` encadenados, aposiciones) menos representadas
en el AnCora de noticias). Curiosamente el acuerdo de periferia por estrato
es **más alto** en PUD, no más bajo — no se investigó por qué (fuera de
alcance: "reportarlos tal cual", no ajustar).

**Desglose de causas de fallo** (de las 1000 oraciones intentadas
in-process con xpos stripped, sin MISC — mismo modo que KPI1/KPI2; 59
fallos, análisis diagnóstico de reporte, no tocó código):

| deprel del nodo que rompe | POS | Ocurrencias |
|---|---|---|
| `xcomp` | VERB (mayormente infinitivo/subjuntivo) | 30 |
| `punct` | PUNCT | 5 |
| (excepción sin nodo UD legible, p.ej. "Cannot insert a subtree that already has a parent") | — | 5 |
| `orphan` | PROPN/NOUN | 4 |
| `fixed` | PRON/VERB | 4 |
| `nummod` | NUM | 3 |
| `vocative` | X | 1 |
| `expl:pv` | — | 1 |
| `case` | — | 1 |
| `flat:name` | — | 1 |

**Causa dominante (30/59, ~51%)**: `xcomp` con head VERB en infinitivo o
subjuntivo — cadenas de complementos clausales que PUD parsea con
profundidad/orden distintos de lo que el dispatch de `xcomp` en
`transform_V`/`transform_A`/`transform_N` espera (ejemplos: "intentar",
"enviar", "resulte", "surgieran" como children `xcomp` de otro verbo, en
oraciones con 2-3 niveles de subordinación). No es un problema de deprels
españoles sin regla — es un problema de la ESTRUCTURA de esas cadenas
concretas en PUD. Insumo directo para priorizar L5.

## 3. Salidas de gruxx con la línea Completeness

**(a) ✓ limpia — "Le compró un regalo a María"** (modo interactivo, pipeline
real Stanza+MISC+ud2rrg):
```
Completeness: ✓ x1(morf) x2↔NP x3↔PP · AGX✓
```

**(b) ✓ limpia con periferia — "Juan le preparó un pastel a su familia en
el parque"** (modo `.conllu` directo, reconstruida desde el canal MISC vía
`leer_ls_desde_misc`):
```
Completeness: ✓ x1↔NP x2↔NP x3↔PP · be-in'↔PERI@CORE · AGX✓
```

**(c) ⚠ real — oración AnCora real** (capturada por KPI4 sobre el pipeline
real; mismo código exacto que usa gruxx):
> "El anterior CNE, elegido también por Miquilena, dimitió en pleno el
> pasado lunes tras soportar una lluvia de críticas por su "falta de
> experiencia" y a sus cinco miembros se les ha prohibido la salida del
> país, mientras son investigados judicialmente por su comportamiento."
```
Completeness: ⚠ x1↔NP · be-in'↔PERI@CORE · "pasado"↔PERI ·
"soportar": periferia sin wrapper, no verificable ·
nodo AGX en el árbol pero sin agx en la LS
```
Este ejemplo es interesante para el punto 4: la oración tiene DOS fuentes
de AGX distintas ("les" dativo y "se" pasivo-reflejo/impersonal, ambas en
el mismo `tras...se les ha prohibido...`). `ls_data['agx']` (poblado por
`nucleo_periferia._detectar_agx_dativo`) modela un **único** agx dativo;
la nueva AGX de `expl:pass`/`expl:impers` (§4) no tiene campo equivalente
en el dict del mapper — el árbol gana un nodo AGX que la LS no anticipa.
**Hallazgo, no bug**: el checker lo reporta honestamente como
`falta_en_ls`; ver pendiente L5 en §5.

**(d) ⚠ real — mismatch de argumento** (capturada por KPI4, ilustra
`falta_en_arbol` puro):
> "Gutiérrez no se arrepiente de haber participado en la insurrección
> contra Mahuad y está seguro que la actitud de los oficiales se debió a
> el elevado grado de corrupción que dice hubo durante la anterior
> administración."
```
Completeness: ⚠ x1↔NP x2 ("participado") sin constituyente en el árbol ·
"no"↔PERI
```

## 4. Decisión "se → AGX": pendiente de validación teórica por Julian

Implementada en `transform_V` (`ud2rrg.py`): el clítico "se" en
`expl:pass` (pasiva refleja: "se venden casas") y `expl:impers`
(impersonal: "se vive bien") se enlaza a un nodo `AGX` bajo `NUC` —
**mismo análisis y mismo árbol elemental que los dativos de L3** (el
clítico es morfema de concordancia, no argumento sintáctico). El
`nsubj:pass` de la pasiva refleja (p.ej. "casas" en "se venden casas")
sigue como `NP` argumento del `CORE` — Etapa 1 ya lo trata como Undergoer,
sin tocar.

Verificado sobre gold AnCora real (213 ocurrencias de `expl:pass`/
`expl:impers` en `es_ancora-ud-dev.conllu`; 6/6 de una muestra convirtieron
con nodo AGX, ver §1). **Hallazgo operativo importante**: con la versión de
Stanza de este entorno, las construcciones reflejo-pasivas/impersonales
reales ("Se venden casas", "Se vive bien") casi nunca salen parseadas con
`expl:pass`/`expl:impers` — Stanza tiende a usar `expl:pv` (que ya se
trataba como NP normal desde L3, sin cambios) o incluso deprels de objeto
directo. La decisión "se→AGX" por tanto se ejercita con fuerza sobre gold
AnCora (y presumiblemente PUD/otros gold treebanks con la misma
convención) pero **rara vez con el parser en vivo de gruxx** — coherente
con que el propio prompt pidió fixtures a mano para testear esto (§3.2 y
`test_se_pasiva_refleja_agx_y_nsubj_pass_como_np`/`test_se_impersonal_agx`
en `test_ud2rrg_es.py`), no un test `@slow` con Stanza.

**Pide validación teórica de Julian**: ¿es correcto que TODO `expl:pass`/
`expl:impers` se enlace a AGX, incluyendo cuando coexiste con un dativo
`le`/`les` propio (ver ejemplo (c) de §3, donde una misma cláusula produce
dos AGX de fuentes distintas)? Y si es correcto, ¿debería `ls_data['agx']`
dejar de ser un único dict y pasar a ser una lista, para que el checker de
completeness pueda verificarlos todos sin falsos `falta_en_ls`?

## 5. Pendientes que pasan a L5

1. **Bucle de corrección del usuario con validación de EL** — puntos de
   enganche ya dejados como comentarios `TODO-L5 (a)/(b)/(c)` en
   `gruxx_ai1.py` (tras mostrar la advertencia de completeness; donde se
   aceptaría el input del usuario; qué archivos curados recibe cada tipo
   de corrección). Ningún código nuevo de lógica, solo el diseño.
2. **`ls_data['agx']` como lista, no dict único`** — nuevo hallazgo de esta
   etapa (§4): necesario para que el checker cubra sentencias con más de
   una fuente de AGX (dativo + se-reflejo/impersonal en la misma cláusula).
3. **Homógrafos del parser**: "como" (SCONJ vs. 1sg de "comer") sigue
   descarrilando tanto la variante preverbal (L3) como la POSTVERBAL
   (nuevo hallazgo de L4, `test_slow_guard_frecuencia_postverbal_anclado_clause`
   — se salta con motivo documentado, no se fuerza).
4. **`xcomp` encadenado** — causa dominante de fallos en PUD (30/59, §2):
   cadenas de complementos clausales en infinitivo/subjuntivo con 2-3
   niveles de subordinación. Candidato de mayor prioridad para L5 según
   este examen.
5. **Wrapper de frecuencia**: sigue sin implementar (heredado de L3).
6. **Compuestos "cerca de"/"delante de"**, expansión de `_CASE_TEMPORAL`,
   forma plena de comunicación, fallback probe BERTIN: heredados de
   L0-L2.5, sin resolver.
7. **Higiene pendiente**: el commit final de esta etapa (`PASO CERO`/commit
   de cierre) no se ejecutó en esta sesión — no había identidad git
   configurada en el entorno (ni local ni global) y Julian pidió continuar
   sin commitear; hacerlo manualmente antes de iniciar L5.
