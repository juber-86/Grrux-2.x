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
- **GUI web local**: `grrux_server.py` (FastAPI) → `grrux_motor.py` (serializa el análisis a
  JSON) → `gui/` (index.html + app.js dibuja el árbol como SVG cliente + estilo.css).

---

## 2. Mapa de archivos

### 2.1 Núcleo ACTIVO (lo que hace funcionar gruxx)

**Raíz:**
| archivo | función |
|---|---|
| `grrux_ai1.py` (813 l) | Entry point terminal. Orquesta Stanza→mapper→display→interacción. `_flujo_guardar_o_corregir` (inyectable). `-help` en todos los prompts. |
| `rrg_ls_mapper.py` (1198 l) | HUB de la Etapa 1. `map_sentence_to_ls`. Integra todos los módulos semánticos, construye EL/estructura, escribe MISC, invoca completeness. |
| `ud2rrg.py` (3258 l) | Conversor UD→RRG heredado + CAPA ESPAÑOLA propia (gateada `language=='es'`/MISC): XPOS vía UPOS, dispatch `obl:arg`, nodo AGX bajo NUC, periferia por estrato, PrDP para `RRGDetached=si`, `expl:pass/impers`→AGX, `_es_conllu_analizado` subordina el fallback si `RRGAnalyzed=si`. **NO tocar salvo mandato explícito.** |
| `grrux_server.py` (289 l) | Backend FastAPI GUI. Endpoints de análisis + `/corregir/*` (bajo `threading.Lock`). |
| `grrux_motor.py` (416 l) | Serializa el análisis a JSON para la GUI (`construir_sub_oracion`, `_operadores_de`, `_linking_de`, etc.). Estado global `_nlp` (pipeline Stanza). |
| `test_grrux_motor.py`, `test_grrux_server.py`, `test_export_svg.py` | Tests de la GUI/export. |

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
| `glosario.py` | `-help [término]`: búsqueda tolerante (sin acentos/case/parcial), paginado. Fuente `glosario_grrux.csv`. |

**Offline / auditoría (no en el path de análisis):** `train.py`, `train_contextual.py`,
`calibrate.py`, `load_data.py`, `gen_contextual_sentences.py`, `diagnose.py`, `predict.py`
(CLI), `informe_pruebas_estructurales.py`, `informe_wrappers_dianas.py`,
`informe_linking_dianas.py`, `kpi_linking.py`, `pruebas_clase_aspectual.py`.

**GUI:** `gui/{index.html, app.js, estilo.css, grrux_logo.png}`.
**Docs:** `docs/{diagrama_grrux.svg, diagrama_grrux.html, GUI.md}`.

### 2.2 Archivos históricos de la raíz

#### 2.2.1 Activos no-core que quedan en raíz (NO mover, NO renombrar)

Estos archivos no forman parte del núcleo activo listado en §2.1, pero
son requeridos por el sistema y no pueden moverse sin romperlo.

**Dependencias exclusivas de `ud2rrg.py`** (invariante §9.3 impide
tocarlas): `export.py`, `linkage.py`, `util.py`, `verbnet.py`,
`add_traces_to_rrg_from_ud.py`. Importadas sin condicionar en la
cabecera de `ud2rrg.py` (líneas 20-36). Ningún otro módulo las usa.

**Utilidad CLI activa**: `convertir.py`. Script standalone que consume
un `.conllu` y llama a `ud2rrg.transform()`. Exigida por
`instalar_estudiantes.sh` (línea 83, `requerir convertir.py`); invocada
por `setup_analizador_stanza.sh`, `ud2rrg_stanza_convertidor_fedora.sh`
y referenciada en `descargar_treebanks_es.sh`.

#### 2.2.2 LEGACY muerto (en `legacy/`, movido en DEUDA-INFRA 2026-08-18)

`gruxx_ai.py` (viejo entry), `analizador_*` (×5), `analizar_texto*` (×5),
`rrg_interactivo*` (×3), `grrux_fix*` (×2), `rrg_unificado.py`,
`rrg_llm_fallback.py`, `rrg_morph_classifier.py`, `debug.py`,
`diagnostico.py`.

Sedimento de exploración previa a la arquitectura actual. Verificado por
grep exhaustivo: ninguno importado por módulo activo, ninguno referenciado
por script activo. Candidatos a purga futura desde `legacy/`.

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
no'/maybe'; corrección de operadores; fix export SVG/PNG) · LA1 (linking algorithm explícito:
AUH, PSA+concordancia, traza 5 pasos, round-trip) · LA2 (causativas resultativas
`[do'(Ø,Ø)] CAUSE [BECOME/INGR pred'(x)]` con clase visible "Realización causativa" /
"Logro causativo"; mapa exacto de tooltips vía `test_mapa_tooltips_exactos_n_v_p_y_cobertura`;
inventario canónico de enrutado en `aspect_classifier/gui_contract.py` servido por
`/contrato/gui`) · LA2.1 (normalización de `confianza` GUI a `float∈[0,1]|null`, cierra
`c.confianza.toFixed is not a function`; auditoría de logros canónicos y corrección del
gate `obj_desnudo→Activity` que degradaba bases léxicas `achievement`) · NOTACIÓN-1/2
(variables `x/y/z` por posición semántica, contratos transversales, rechazo de entradas
`x1/x2/x3`; gate independiente reproducido) · BENEFACTIVAS (2026-08-12: familia
`benefactiva` subdividida en 5 subtipos con EL curada por XLSX, `proposito ∈
{become_have, have, none}` explícito, upsert atómico insert/update/no-op/staging con
rollback por bytes en el corrector) · **DEUDA-INFRA (2026-08-18): 4 sub-hitos
(A `docs/DESARROLLO.md`; B auditoría de pruebas GUI aisladas, timeout histórico de
`CHECKPOINT_BENEFACTIVAS.md` no reproducido; C separación núcleo activo/legacy — 21
archivos movidos a `legacy/`, 6 exclusiones por dependencia de `ud2rrg.py`/scripts de
instalación; D rename `gruxx`→`GRRux` — 11 archivos + string interna, `ud2rrg.py` sin
tocar).** · **DITRANS-AGX + DITRANS-CLASE + AVISOS + ENRUTADO-DATIVO (2026-08-19): a
partir del bug de campo "juan le da un beso a maria → Semelfactivo". Auditoría que
descarta DEUDA-INFRA (cero cambios de lógica en el rango) y localiza cuatro defectos
reales: (1) `detectar_trigger` descartaba la evidencia del clítico AGX dativo doblado, así
que la plantilla ditransitiva no disparaba cuando el parser etiquetaba el sintagma doblado
`obl` en vez de `obl:arg` — nueva vía `dativo_agx` con flag `fallback_agx_dativo`;
(2) ninguna ditransitiva de transferencia podía mostrarse como "Realización causativa"
pese a llevar CAUSE en su EL — `ditransitivas.clase_derivada_de_el`, la clase visible se
deriva de la EL; (3) `diagnosticos_analisis` se calculaba y no lo mostraba nadie, y los
`except Exception` desnudos del mapper degradaban el análisis en silencio —
`display_grr.avisos` + `_avisos_lexicos`; (4) el bucle de corrección persistía cualquier
"argumento del core" en `verbos_movimiento` (así entró `dar` el 2026-07-14, corrompiendo
el enrutado de todo oblicuo en a/hacia/hasta bajo ese verbo) y `_confirma_enrutado` lo
daba por bueno sin exigir posición en la EL — guardarraíl de recipiente dativo +
confirmación por `id_a_var`.** — ÚLTIMA CERRADA.

Convención (a partir de 2026-08-17): los prompts de implementación viven en `PROMPTS/`
(contrato redactado por la sesión de DISEÑO). Cada fase produce
`CHECKPOINTS/CHECKPOINT_<hito>.md`.

---

## 8. PENDIENTES (deuda viva)

### 8.1 Roadmap (definido 2026-08-17)

**Principio**: estabilizar antes de progresar. Los hitos que tocan la arquitectura de
análisis (LA3, oraciones compuestas, migración EL a inglés) van **al final**; primero se
cierran los pendientes pequeños que dejan el sistema más funcional, limpio y estandarizado.

Orden acordado:

1. **DEUDA-INFRA — CERRADO (2026-08-18)** — Deuda técnica e infraestructura
   (§"Deuda técnica e infraestructura" de `handoff/PENDIENTES.md`): activos separados
   de sedimento legacy sin nuevas dependencias sobre módulos muertos (ver §2.2 de este
   documento); migración `gruxx`→`GRRux` completa, incluyendo `gruxx_ai1.py`→
   `grrux_ai1.py`; estrategia de pruebas GUI aisladas documentada (sin instancias extra
   abiertas); acceso al servidor local `127.0.0.1:8763/` documentado para el modelo
   ejecutor y las pruebas aisladas; convención commit-por-fase + checkpoint consolidada
   en `docs/DESARROLLO.md`. Ver `CHECKPOINTS/CHECKPOINT_DEUDA_INFRA.md`.
2. **DITRANS-AGX / DITRANS-CLASE / AVISOS / ENRUTADO-DATIVO — CERRADO (2026-08-19)** —
   Bug de campo de las ditransitivas y sus tres defectos vecinos de visibilidad y
   guardarraíles. Ver `CHECKPOINTS/CHECKPOINT_DITRANS_AGX.md` y
   `CHECKPOINTS/CHECKPOINT_VISIBILIDAD_Y_ENRUTADO.md`. Queda anotado como deuda menor:
   unificar la regla de clase derivada (la rama causativa conserva su copia inline) y la
   decisión teórica sobre "dar un beso" como verbo soporte frente a la plantilla de
   transferencia.
3. **CONFIANZA — próximo hito activo** — Confianza y presentación (§6 de
   `handoff/PENDIENTES.md`): mantener
   manejo robusto de valores numéricos de confianza (el bug `c.confianza.toFixed is not
   a function` quedó cerrado por LA2.1 pero sin cobertura visual continua); definir
   convención única para confianza, desacuerdo interno y evidencia de reglas; mostrar
   incertidumbre de forma comprensible sin romper el renderizado cuando falte o cambie
   un valor.
4. **LOGROS-DIANAS** — Logros y realizaciones (§4 de `handoff/PENDIENTES.md`): ampliar
   pruebas de LOGRO (dianas post "El globo explotó" y "La bomba explotó"); verificar la
   frontera actividad/realización/logro en verbos nuevos y en construcciones causativas;
   añadir pares mínimos y contraejemplos al conjunto curado; medir falsos positivos de
   actividad y falsos negativos de logro pre/post-fase.
5. **FIX técnicos focales** (§8.4): FIX-1 (items **B**+**D**+**F**), LOGROS-SLOW (3
   fallos slow del clasificador), OPERADORES-FREQ (EVQ+EVID+wrapper frecuencia+
   `lo`/`la`→AGX).
6. **Arquitectura de análisis** (al final): oraciones compuestas (juntura-nexo, xcomp),
   LA3 (linking bidireccional syn↔sem), migración EL a inglés.

El roadmap se actualiza al cerrar cada bloque.

### 8.2 SUSPENDIDO (decisión de Julian)
- **Wh + preposición en PrCS** ("¿a quién…?"): suspendido, fuentes contradictorias. Arrastra
  la ausencia de maquinaria de interrogativas (que LA1 marcó faltante para su round-trip PrCS).
- **Proyección focal/pragmática** (información estructural, PFD/AFD, foco predicativo/oracional/
  estrecho, nodo Speech Act): APARCADA con diseño completo hecho (señales detectables en texto,
  defaults, modo pregunta-contexto). Ver memoria `linking-sintaxis-semantica-grrux`.

### 8.3 Teórico (requiere decisión/descripción de Julian)
- **Migración de EL a inglés** (broken'/sold'/…): tarea futura; hoy todo en español; curar
  formas inglesas contra las listas de verbos después.
- Periferia tipo "otro" en la EL + notación de wrapper genérico ("los fines de semana"=frecuencia).
- Migración `lo`/`la` → AGX.
- Refinamientos González Vergara: impersonal refleja por animacidad ("Se acusó a Pedro"),
  agente-con-"por" como cadena causal secundaria, cadena causal secundaria ("se escondió por…").
- Doble ruta psych de la AUH (Experiencer como Actor o Undergoer según construcción).
- Operadores EVQ (para `nunca`=⟨NEG ⟨EVQ⟩⟩) y EVID (para `aparentemente`).
- Wrapper de frecuencia (siempre/todos los días).
- Oraciones compuestas: teoría de juntura-nexo RRG, cadenas de xcomp (grueso del gap de PUD).
- **ADESSE** como respaldo léxico futuro para casos de baja confianza o desacuerdo interno;
  siempre corroboración explicable, nunca sustitución silenciosa. No implementar durante LA3.

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
- **Commits**: se hacen por fase. Últimos: `c3d21657` LA2, `c4e5856f`/`fc67f579`/cierre
  LA2.1, `13b0ec98` NOTACIÓN+BENEFACTIVAS, `4877af1c`/`9f2e82da`/`9b6501fe`
  higiene+roadmap (2026-08-17). `main` sincronizada con `agent/notacion-benefactivas`;
  **higiene GitHub pendiente** — el repo remoto `origin/main` está 16 commits atrás y no
  se ha decidido el estado publicable.
- **GUI local** en `http://127.0.0.1:8763/`. Las pruebas del modelo ejecutor deben ejecutarse
  en una instancia aislada (puerto libre) y cerrarse al terminar para evitar OOM con otras
  instancias abiertas.

### 8.6 LA3 — NO PRIORITARIO (al final del roadmap)

LA3 no es prioridad. Se acomete **después** de cerrar los bloques 1-4 de §8.1 (Deuda
técnica, Confianza, Logros-dianas y FIX técnicos focales). Alcance cuando se retome:

- **syn→sem** (comprensión): partir de la estructura sintáctica, identificar argumentos
  centrales, macrorroles, voz, `se`, caso/adposición y posiciones relevantes; recuperar la LS
  y enlazar todos los argumentos con completitud.
- **sem→syn** (producción): partir de la LS, determinar Actor/Undergoer por AUH, seleccionar
  PSA, asignar codificación morfosintáctica, construir la estructura estratificada.
- **Integración**: representación intermedia común, comprobaciones de consistencia en ambos
  sentidos, trazabilidad visible en la GUI, sin reemplazar silenciosamente el análisis vigente.
- Validación: ida y vuelta `syn→sem→syn` y `sem→syn→sem` con tolerancia para alternancias
  legítimas; regresión de actividades, realizaciones, logros, estados y causativas; dianas
  "El globo explotó", "Se venden casas", "Juan rompió la ventana".
- **Oraciones compuestas** siguen pausadas en paralelo con LA3.

---

## 9. Reglas de trabajo (invariantes del proyecto)

1. **Cada fase cierra con commit y `CHECKPOINTS/CHECKPOINT_<hito>.md`.** Los prompts de
   implementación viven en `PROMPTS/`.
2. **`contextual_sentences.csv` APPEND-ONLY**, nunca regenerar/auto-modificar.
3. **`ud2rrg.py` no se toca** salvo mandato explícito y gateado `language=='es'`/MISC.
4. **Clasificador/corroborador/`.joblib` intocables** salvo fase de reentrenamiento explícita.
5. **PUD**: examen a ciegas, no re-correr.
6. Cada capa con flag `enabled` → **byte-idéntico con `false`** (test obligatorio).
7. **Gold de dianas** solo se altera con aprobación explícita + tabla auditada EL-vieja→EL-nueva.
8. Advertencia **OOM**: no correr suites `--slow` con instancias de gruxx/GUI abiertas; la GUI
   de pruebas se levanta en puerto libre y se cierra al terminar.
9. Separación de sesiones: una sesión de DISEÑO redacta `PROMPTS/prompt_<hito>.md`; una sesión
   de IMPLEMENTACIÓN los ejecuta. El `.md` es el contrato. (En sesiones donde un mismo modelo
   asume ambos roles con acceso a la carpeta, el prompt sigue siendo el contrato explícito
   antes de tocar código.)
