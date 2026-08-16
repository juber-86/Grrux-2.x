# GRRUX (incorrectly named "gruxx") — Estado del arte (handoff técnico para modelo IA)

> Documento de traspaso denso. Audiencia: instancia Claude que retoma el desarrollo.
> Fecha de corte: 2026-08-12. Repo: `~/proyectos/ud2rrg`. Python: `./venv/bin/python`.
> No es documentación de usuario; es un snapshot de arquitectura + estado + deuda.

---

## 0. Identidad

**gruxx** (marca interna; el repo se llama `ud2rrg` por su ancestro) es un analizador de
**Gramática del Papel y la Referencia (RRG / Role and Reference Grammar, Van Valin)** para
**español**. Entrada: oración(es) en español. Salida: representación RRG completa de cada
cláusula — árbol de constituyentes por estratos (SENTENCE > CLAUSE > CORE > NUC), Estructura
Lógica (EL/Logical Structure) con clase Aktionsart, macropapeles, operadores, y verificación de
Integridad (Completeness Constraint). Uso previsto: herramienta docente/investigación para
lingüistas RRG (público NO programador; toda la salida usa terminología del glosario en
español).

Base heredada: `ud2rrg.py` (Evang et al. 2021), conversor regla-a-regla UD→RRG para inglés/
alemán. gruxx le añadió (a) una capa semántica española propia aguas arriba y (b) una capa
española dentro de `ud2rrg.py` gateada por `language=='es'` y por marcas MISC.

---

## 1. Pipeline (flujo de una oración)

```
texto ES
  │  Stanza (es) → CoNLL-U con deprels UD
  ▼
ETAPA 1 · SEMÁNTICA (paquete aspect_classifier, orquestado por rrg_ls_mapper.map_sentence_to_ls)
  1. nucleo_periferia.analizar_roles → núcleo vs periferia; args (Actor/Undergoer/NMR);
     pro-drop; clíticos → AGX (dativo/se-pasivo/se-impersonal/se-aspectual/reflexivo);
     inespecificación del actor Ø; periferia tipada (case+lemma) por estrato.
  2. Clasificador Aktionsart (BERTIN congelado + 2 cabezas + árbol de decisión) → clase Vendler/VV.
  3. pruebas_estructurales → coerciones por pruebas Van Valin P1-P5 detectadas en la oración real.
  4. Gates de telicidad composicional (objeto sin determinante→Activity, medida→AA, se-aspectual…).
  5. causatividad.componer_cause (léxico + heurística) y ditransitivas (3 plantillas) → EL compuesta.
  6. build_ls → EL formal + léxica; wrappers_ls.componer_wrappers → periferia en la EL (be-in',
     during', yesterday'…) anidada por fuera; operadores.envolver_ls → ⟨IF ⟨TNS ⟨ASP …⟩⟩⟩ por fuera.
  7. linking.analizar_linking → macropapeles por AUH, PSA, concordancia, traza 5 pasos, round-trip.
  ▼  Todas las decisiones se serializan al canal MISC (col. 10 CoNLL-U) vía misc_rrg.
ETAPA 2 · SINTAXIS (ud2rrg.py con capa española, lee MISC, gateada language=='es')
  → árbol de constituyentes RRG: estratos, nodo AGX bajo NUC, periferia por estrato
    (temporal→CLAUSE, local/modo→CORE), LDP/PrDP para destacados.
  ▼
VERIFICACIÓN · completeness.verificar(ls_data, arbol) → Integridad: cada arg de la EL con su
  constituyente (o satisfecho morfológicamente), cada wrapper su rama, cada AGX su nodo; +
  checks linking_* (round-trip de producción: nº args core, PSA+concordancia, AGX esperado).
  ▼
DISPLAY · display_grr.render_bloque → orden GRR (árbol primero, EL léxica, tipo, EL formal,
  argumentos con papeles, operadores, línea Linking, línea Integridad). --verbose = detalle técnico.
  ▼
INTERACCIÓN · glosario (-help [término]); guardar .txt; bucle_correccion (correccion.py).
```

Dos frontends comparten el pipeline:
- **Terminal**: `gruxx_ai1.py` (entry point real). Modos: oración interactiva / .txt en lote /
  .conllu preanotado.
- **GUI web local**: `gruxx_server.py` (FastAPI) → `gruxx_motor.py` (serializa el análisis a
  JSON) → `gui/` (index.html + app.js dibuja el árbol como SVG cliente + estilo.css).

---

## 2. Mapa de archivos

### 2.1 Núcleo ACTIVO (lo que hace funcionar gruxx)

**Raíz:**
| archivo | función |
|---|---|
| `gruxx_ai1.py` (813 l) | Entry point terminal. Orquesta Stanza→mapper→display→interacción. `_flujo_guardar_o_corregir` (inyectable). `-help` en todos los prompts. |
| `rrg_ls_mapper.py` (1198 l) | HUB de la Etapa 1. `map_sentence_to_ls`. Integra todos los módulos semánticos, construye EL/estructura, escribe MISC, invoca completeness. |
| `ud2rrg.py` (3258 l) | Conversor UD→RRG heredado + CAPA ESPAÑOLA propia (gateada `language=='es'`/MISC): XPOS vía UPOS, dispatch `obl:arg`, nodo AGX bajo NUC, periferia por estrato, PrDP para `RRGDetached=si`, `expl:pass/impers`→AGX, `_es_conllu_analizado` subordina el fallback si `RRGAnalyzed=si`. **NO tocar salvo mandato explícito.** |
| `gruxx_server.py` (289 l) | Backend FastAPI GUI. Endpoints de análisis + `/corregir/*` (bajo `threading.Lock`). |
| `gruxx_motor.py` (416 l) | Serializa el análisis a JSON para la GUI (`construir_sub_oracion`, `_operadores_de`, `_linking_de`, etc.). Estado global `_nlp` (pipeline Stanza). |
| `test_gruxx_motor.py`, `test_gruxx_server.py`, `test_export_svg.py` | Tests de la GUI/export. |

**Paquete `aspect_classifier/` — cadena del CLASIFICADOR Aktionsart:**
| módulo | función |
|---|---|
| `predict.py` | `AspectClassifier` (fachada, único símbolo exportado por `__init__`). Orquesta extractor→cabezas→árbol. |
| `extractor.py` | `VerbEmbeddingExtractor`: BERTIN (`bertin-project/bertin-roberta-base-spanish`) congelado, capa 8, embeddings. `load_config`. |
| `extractor_contextual.py` | Embeddings del complejo verbal completo (contextual) vs canónico (léxico). |
| `complejo_verbal.py` | `extraer_complejo`/`desde_stanza`: aísla verbo+clíticos+objeto del parse. |
| `classifier.py` | `FeatureClassifiers`: 2 cabezas (léxica + contextual) → 4 rasgos binarios (stat/dyn/tel/pun). |
| `decision_tree.py` | `classify`: 4 rasgos → clase (State/Activity/Accomplishment/Achievement/Semelfactive/Active_Accomplishment). |

**Paquete `aspect_classifier/` — cadena del ANÁLISIS RRG:**
| módulo | función |
|---|---|
| `nucleo_periferia.py` | Etapa 1 base: núcleo/periferia, args, pro-drop, clíticos→AGX (lista con fuente), Ø, periferia tipada, `tiene_delimitador_nuclear`, `objeto_con_numeral_medida`. |
| `pruebas_estructurales.py` | Pruebas Van Valin P1-P5 sobre la oración real; `aplicar_coerciones`; reglas R1/R2. `CUADRO_PRUEBAS` (data). |
| `causatividad.py` | `componer_cause`: causativas léxicas (`causative_lexicon.csv`) + heurística (loguea a `causative_candidates_heuristico.csv`). BECOME/INGR según Aktionsart de la base. |
| `ditransitivas.py` | 3 plantillas (transferencia/benefactiva-PURP/comunicación) desde `verbos_ditransitivos.xlsx`. Recipiente = NMR/POSEEDOR. `construir_el` genera `ls_estructura`. |
| `wrappers_ls.py` | Periferia en la EL: be-in'/during'/for'/yesterday'… Anidamiento por estrato. `cubiertos_por_operador` (suprime tokens que ya son operador). |
| `operadores.py` | Detección de operadores (IF/TNS/ASP/NEG/MOD/STA) con valor+estrato+señal de origen; `envolver_ls` (notación ⟨ ⟩ VV, orden de scope, omite no especificados). |
| `linking.py` | AUH (jerarquía Actor-Undergoer, constante), `asignar_macropapeles`, `seleccionar_psa`, `verificar_concordancia`, `traza_linking` (5 pasos), `expectativas_sintacticas` (round-trip), `reconciliar`/`log_discrepancia`. Helpers de árbol propios (evita ciclo: completeness importa linking). |
| `completeness.py` | Completeness Constraint. `verificar(ls_data, arbol)→dict`. `_chequear_linking`. Estados `ok`/warnings/`linking_*`. |
| `misc_rrg.py` | Canal MISC: escribe `RRGRole/RRGType/RRGWrap/RRGVar/RRGMacrorole/RRGThemRel/RRGAgxFuente/RRGDetached/RRGAnalyzed=si` en TODOS los tokens; `leer_ls_desde_misc` (round-trip). |
| `display_grr.py` | `render_bloque`: orden GRR + traducciones user-friendly (Vector/Completeness/Linking). |
| `correccion.py` | `bucle_correccion`: menú (clase/EL/enrutado/operador), validación 3 niveles, enrutado automático de destino, re-análisis con rollback, log maestro. |
| `glosario.py` | `-help [término]`: búsqueda tolerante (sin acentos/case/parcial), paginado. Fuente `glosario_gruxx.csv`. |

**Offline / auditoría (no en el path de análisis):** `train.py`, `train_contextual.py`,
`calibrate.py`, `load_data.py`, `gen_contextual_sentences.py`, `diagnose.py`, `predict.py`
(CLI), `informe_pruebas_estructurales.py`, `informe_wrappers_dianas.py`,
`informe_linking_dianas.py`, `kpi_linking.py`, `pruebas_clase_aspectual.py`.

**GUI:** `gui/{index.html, app.js, estilo.css, grrux_logo.png}`.
**Docs:** `docs/{diagrama_gruxx.svg, diagrama_gruxx.html, GUI.md}`.

### 2.2 LEGACY / muerto (raíz; NO importado por el núcleo activo — no tocar, no confiar)

`gruxx_ai.py` (viejo entry, importa export/linkage/util/rrg_morph_classifier), `analizador_*`
(×5), `analizar_texto*` (×5), `rrg_interactivo*` (×3), `grrux_fix*` (×2), `rrg_unificado.py`,
`rrg_llm_fallback.py`, `rrg_morph_classifier.py`, `linkage.py`, `convertir.py`, `export.py`,
`debug.py`, `diagnostico.py`, `util.py`, `verbnet.py`, `add_traces_to_rrg_from_ud.py`.
(Sedimento de exploración previa a la arquitectura actual. Candidatos a purga futura.)

---

## 3. Conceptos clave del formalismo (implementados)

- **Aktionsart**: 6 clases (+ causativas). EL por clase: State `pred'(x)`/`pred'(x,y)`;
  Activity `do'(x,[pred'(x)])`; Achievement `INGR pred'`; Semelfactive `SEML pred'`;
  Accomplishment `BECOME pred'`; Active Accomplishment `do'(…) & INGR pred'`; Causative
  `α CAUSE β`.
- **Notación ⟨ ⟩ (operadores)**: corchetes angulares U+27E8/27E9. Orden de scope VV
  `⟨IF ⟨EVID ⟨TNS ⟨STA ⟨NEG ⟨MOD ⟨EVQ ⟨DIR ⟨ASP ⟨LS⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩`. Español implementa
  IF/TNS/ASP/NEG/MOD/STA; EVID/EVQ/DIR omitidos (hueco reservado). No especificado se omite.
- **AUH (linking)**: `arg de DO > 1er arg de do' > 1er arg de pred'(x,y) > 2º arg de pred'(x,y)
  > arg de estado`. Actor=rango más alto no-Ø; Undergoer=más bajo. M-transitividad = nº MR
  (2/1/0; atransitivo=impersonal). PSA: activa→Actor, pasiva/se→Undergoer, impersonal→None.
  PSA rige concordancia.
- **AGX** (índice de concordancia): nodo bajo NUC para clíticos. Fuente única de verdad = lista
  con sources (dativo/acusativo/reflexivo/se_pasivo/se_impersonal/se_aspectual). El fallback de
  clíticos de ud2rrg se subordina vía `RRGAnalyzed=si`.
- **se español (González Vergara)**: se-pasiva `do'(Ø,Ø) CAUSE [INGR/BECOME pred'(paciente)]`;
  se→AGX; actor inespecificado Ø. 4 tipos de se manejados (pasivo/impersonal/aspectual/reflexivo).
- **Ditransitivas**: recipiente = NMR con `RRGThemRel=Poseedor` (decisión: Poseedor, no
  Recipiente, por continuo Van Valin).
- **Periferia**: wrappers por estrato. Temporal→CLAUSE; local/modo→CORE. Adverbios monovalentes
  `yesterday'([LS])`.

---

## 4. Config (`aspect_classifier/config.yaml`)

Secciones: `data`, `extractor`, `nucleo_periferia`, `wrappers_ls`, `operadores`,
`ditransitivas`, `pruebas_estructurales`, `pruebas`, `linking`, `decision_tree`.
Calibración vigente: `peso_contextual=0.55`, `dyn=0.45`, `pun=0.40`, `tel=0.40`; corroborador
MLM **λ=0 (deshabilitado — verificado 2× mismo veredicto)**. Cada capa nueva tiene flag
`enabled`; con `false` → salida byte-idéntica (tests dedicados por etapa).

---

## 5. Datos curados (`aspect_classifier/data/`)

- `contextual_sentences.csv` (536 filas) — **CURADO A MANO. APPEND-ONLY. NUNCA regenerar,
  NUNCA auto-modificar.** Semilla de entrenamiento contextual.
- `conjunto_verbos_semilla_clase_aspectual.xlsx`, `dataset_clean.csv` — semilla léxica.
- `verbos_ditransitivos.xlsx` (122 verbos) — léxico ditransitivo estructurado;
  las 30 benefactivas llevan subtipo, predicado resultativo, propósito y trazabilidad.
- `causative_lexicon.csv` + `causative_candidates_heuristico.csv` (log append-only) — causativas.
- `glosario_gruxx.csv` (~62+ términos, categorías incl. "Operadores" y "Linking") — editable Julian.
- `continuum_de_relaciones_tematicas.xlsx`, `jerarquia_semantica_a_gramatical.xlsx` — AUH/temáticas.
- `correcciones_{clase,el,enrutado,operadores}.csv` (staging) + `correcciones_log.csv` (maestro).
- `linking_discrepancias.csv`, `perifrasis_no_cubiertas.csv`, `ditransitivos_candidatos.csv` — logs.
- `kpi_linking_post_l*.json`, `kpi_pud_final.json` — métricas por fase.
- `reglas_RRG.txt` — spec de pruebas Van Valin.

---

## 6. Métricas (KPI)

- Conversión: **98% AnCora / 94.1% PUD** (PUD = examen a ciegas, una vez, NO re-correr).
- Integridad (Completeness): **94.9%**. `agx_arbol_gt_ls = 0`.
- PUD periferia 65.9%, completeness 61.8% (peor por compuestas/xcomp no cubiertas).
- Suite rápida completa post-benefactivas: **382 passed, 37 skipped**. Gates lentos
  focales: ditransitivas **20/20**, corrector **49/49**, notación **4/4**.

---

## 7. Historial de fases (todas cerradas con checkpoint)

L0-L2.5 (linking base + ditransitivas) · L3 (capa española ud2rrg: XPOS, obl:arg, AGX,
periferia por estrato) · L4 (gruxx_ai1 editable, flecos) · L4.5 (gates telicidad composicional
+ reentrenamiento habitual: 68 oraciones presente) · L5 (bucle de corrección: 3 niveles,
enrutado auto, rollback) · GUI G0-G3 (motor/server/gui, exports) · OPERATORS (operadores en EL
⟨ ⟩ + proyección espejo GUI) · OPERATORS_2 (EL ortodoxa: fuera pseudo-predicados complet/prog/
no'/maybe'; corrección de operadores; fix export SVG/PNG) · **LA1 (linking algorithm explícito:
AUH, PSA+concordancia, traza 5 pasos, round-trip) — ÚLTIMA CERRADA.**

Prompts de implementación en la raíz (`prompt_*.md`) son el HANDOFF a la sesión Opus 4.8.
Cada fase produjo `CHECKPOINT_*.md`.

---

## 8. PENDIENTES (deuda viva)

### 8.1 Próximo prompt planificado (LA2, sin redactar aún)
1. **Realización/logro causativo** como clase visible. Arreglar plantilla del se-pasivo
   heurístico: hoy `componer_cause` anida el paciente en un `do'` EMBEBIDO
   (`do'(casas,[vender'(casas)])`) → debe ser `[do'(Ø,Ø)] CAUSE [BECOME vendido'(casas)]`
   (estado resultante; el paciente en arg. de estado). **Predicado en ESPAÑOL (participio):
   `vendido'`, NO `sold'` — decisión Julian 2026-07-12, la forma inglesa se cura después.**
   BECOME (cambio gradual) vs INGR (instantáneo) según Aktionsart de la base. Arregla de paso
   las discrepancias #2/#3 de LA1.
2. **Fix tooltips de nodos del árbol (GUI)**: N/V/P muestran info equivocada (deben ser
   N=sustantivo, V=verbo, P=preposición) y los demás nodos NO muestran nada. AGX/CORE/CLAUSE/
   SENTENCE/*-PERI ya correctos. Necesita mapa completo nodo→definición (desde glosario).
3. **Enrutado del bucle con TODAS las opciones**: hoy la lista de elemento-incorrecto y la de
   "¿qué debería ser?" están limitadas a lo presente en la oración; deben ofrecer el inventario
   COMPLETO de la proyección de constituyentes, esté presente o no (decisión del usuario, no de
   gruxx).

### 8.2 SUSPENDIDO (decisión de Julian)
- **Wh + preposición en PrCS** ("¿a quién…?"): suspendido, fuentes contradictorias. Arrastra
  la ausencia de maquinaria de interrogativas (que LA1 marcó faltante para su round-trip PrCS).
- **Proyección focal/pragmática** (información estructural, PFD/AFD, foco predicativo/oracional/
  estrecho, nodo Speech Act): APARCADA con diseño completo hecho (señales detectables en texto,
  defaults, modo pregunta-contexto). Ver memoria `linking-sintaxis-semantica-grrux`.

### 8.3 Teórico (requiere decisión/descripción de Julian)
- **Reforma notación x/y/z: CERRADA (2026-08-12).** Variables por posición
  semántica, contratos transversales y rechazo de entradas anteriores
  implementados y validados. Ver `CHECKPOINT_NOTACION.md` (NOTACIÓN-1) y
  `CHECKPOINT_NOTACION_2.md` (gate independiente reproducido).
  Los ejemplos `x1/x2/x3` en checkpoints e informes históricos reflejan
  versiones anteriores de GRRux y no se reescriben.
- **Migración de EL a inglés** (broken'/sold'/…): tarea futura; hoy todo en español; curar
  formas inglesas contra las listas de verbos después.
- Periferia tipo "otro" en la EL + notación de wrapper genérico ("los fines de semana"=frecuencia).
- Migración lo/la → AGX.
- Refinamientos González Vergara: impersonal refleja por animacidad ("Se acusó a Pedro"),
  agente-con-"por" como cadena causal secundaria, cadena causal secundaria ("se escondió por…").
- Doble ruta psych de la AUH (Experiencer como Actor o Undergoer según construcción).
- Operadores EVQ (para `nunca`=⟨NEG ⟨EVQ⟩⟩) y EVID (para `aparentemente`).
- Wrapper de frecuencia (siempre/todos los días).
- Oraciones compuestas: teoría de juntura-nexo RRG, cadenas de xcomp (grueso del gap de PUD).

### 8.4 Técnico (sin decisión pendiente — categorías del feedback post-L5 sin etapa)
- **B**: sintagmas completos en la EL ("casas baratas", no solo "casas").
- **C**: depictivos a periferia ("duerme enroscado").
- **D**: guardas anti-sobredisparo de causatividad.
- **F**: "corregir todo" (EL+clase juntas) en el bucle.
- Discrepancia #1 de LA1 (pasivas por orden superficial): **CERRADA por
  NOTACIÓN-1**; Actor/Undergoer se asignan por macropapel. Ver checkpoint citado.
- 3 fallos slow conocidos (clasificador, no de EL): "el perro se sacudió" (activity vs
  semelfactive; sospecha: `pun≥0.5` hardcodeado en gate 4D vs umbral recalibrado 0.40),
  "Juan llegó" (dianas AA), `blend_sube_pun` (corroborador, Δ0.0036, cosmético).
- Etiqueta literal "Agent" en rama copulativa (inconsistencia terminológica).
- TODO-OPERATORS-3: override por-oración para correcciones de operador de origen parse.
- Homógrafos del parser ("como"). Fallback probe verbos desconocidos. Forma plena comunicación.

### 8.5 Infraestructura
- **hacer commits** 

---

## 9. Reglas de trabajo (invariantes del proyecto)

1. **start doing commits** .
2. **`contextual_sentences.csv` APPEND-ONLY**, nunca regenerar/auto-modificar.
3. **`ud2rrg.py` no se toca** salvo mandato explícito y gateado `language=='es'`/MISC.
4. **Clasificador/corroborador/`.joblib` intocables** salvo fase de reentrenamiento explícita.
5. **PUD**: examen a ciegas, no re-correr.
6. Cada capa con flag `enabled` → **byte-idéntico con `false`** (test obligatorio).
7. **Gold de dianas** solo se altera con aprobación explícita + tabla auditada EL-vieja→EL-nueva.
8. Advertencia **OOM**: no correr suites `--slow` con instancias de gruxx/GUI abiertas.
9. Separación de sesiones: una sesión de DISEÑO redacta `prompt_*.md`; una sesión de
   IMPLEMENTACIÓN los ejecuta. El `.md` es el contrato.

## Actualización posterior a LA2.1

LA2.1 queda implementado. Se corrigió el enrutado de correcciones para que las opciones de nodos correspondan únicamente a la oración analizada y no reutilicen opciones de análisis anteriores. También se incorporaron las correcciones y pruebas relacionadas con confianza, causatividad y la clasificación de logros; estas áreas deben mantenerse bajo regresión.

### Próxima fase: LA3 (PAUSADA)

El siguiente bloque es la implementación del linking bidireccional de RRG:

- **syn→sem**: partir de la estructura sintáctica, identificar argumentos centrales, macrorroles, voz, `se`, caso/adposición y posiciones relevantes, recuperar la LS y enlazar todos los argumentos conforme a la completitud.
- **sem→syn**: partir de la LS, determinar actor y undergoer mediante la AUH, seleccionar el argumento sintáctico privilegiado, asignar codificación morfosintáctica y construir la estructura estratificada de la cláusula.
- **Integración**: ambos algoritmos deben compartir las mismas representaciones de LS y estructura estratificada, producir trazabilidad explicable y señalar conflictos o enlaces incompletos sin ocultarlos.

La validación de LA3 deberá incluir pruebas de ida y vuelta y regresión para actividades, realizaciones, logros, estados y causativas, con especial atención a ejemplos como «El globo explotó», «Se venden casas» y «Juan rompió la ventana».

LA3 y las oraciones compuestas siguen expresamente en pausa. El hito cerrado
posterior es la reforma de benefactivas; ver `CHECKPOINT_BENEFACTIVAS.md`.

### Reforma de benefactivas (CERRADA, 2026-08-12)

La familia `benefactiva` se subdivide desde datos curados en obtención,
preparación, creación, cambio de estado y actividad. EL textual,
`ls_estructura`, Linking, Completeness, MISC, motor y JSON comparten la misma
especificación. El corrector realiza upsert atómico insert/update/no-op,
protege lecturas ambiguas, revierte por bytes y sólo confirma equivalencia
semántica exacta. Gate focal: 163 passed; suite completa: 382 passed.

### Infraestructura de pruebas GUI

La GUI local de GRRux se sirve en `http://127.0.0.1:8763/`. Las pruebas del modelo ejecutor deben ejecutarse en una instancia aislada y cerrarse al terminar para evitar consumir memoria junto con otras instancias abiertas. El procedimiento de acceso y captura debe quedar documentado en la configuración de lanzamiento del entorno de pruebas.

### Pendientes y decisiones aplazadas

- Reforzar la normalización y presentación de valores de confianza para evitar regresiones de interfaz como `c.confianza.toFixed is not a function`.
- Mantener la corrección de opciones de nodos limitada a la oración actual.
- ADESSE queda como posible respaldo léxico futuro para casos de baja confianza o desacuerdo interno; no se implementa en LA3.
- Se mantienen por ahora los predicados de la EL en español; la migración al inglés es futura.
- Wh + preposición continúa suspendido.
- La migración de nombres `gruxx` → `GRRux`, incluido `gruxx_ai1.py` → `grrux_ai1.py`, queda para una fase controlada posterior.
