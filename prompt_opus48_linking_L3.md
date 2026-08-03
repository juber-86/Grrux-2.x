# Tarea: L3 — capa española de ud2rrg.py (XPOS, dativos/AGX, periferia anclada por estrato)

Proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python` (3.10). Entry point:
`python3 gruxx_ai1.py`. Sigue a L0–L2 y L2.5 (COMPLETADAS: ver CHECKPOINT_L0_L2.md y
CHECKPOINT_L2_5_DITRANSITIVAS.md). **Primera etapa que toca `ud2rrg.py`** (3004 líneas; autores
Evang/Bladier/Kallmeyer/Petitjean; motor LTAG: transform_* por POS + dispatch por deprel;
`peri()` ya existe; spec en ESPECIFICACION_TECNICA_DEL_ALGORITMO_CONVERSOR_ud2rrg.txt).

**PASO CERO OBLIGATORIO — red de seguridad**: el repo lleva todo sin commitear y esta etapa
modifica el conversor de terceros. Hacer `git add -A && git commit -m "pre-L3: semántica completa
(L0-L2.5), ud2rrg intacto"` ANTES de tocar nada. Autorizado por Julian.

**PROHIBIDO:** `gruxx_ai1.py` completo; clasificador (`predict.py`, `classifier.py`,
`decision_tree.py`), corroborador MLM, `pruebas_estructurales.py`, `wrappers_ls.py`, los
`.joblib`, `data/contextual_sentences.csv` — intactos. Módulos semánticos tocables SOLO donde se
indica: `nucleo_periferia.py` (§6), `ditransitivas.py` + `misc_rrg.py` (§7, un rename de
etiqueta).

**REGLA DE ORO para ud2rrg.py**: TODO cambio va condicionado (`language=='es'` y/o presencia de
marcas RRG en MISC) — las rutas de en/de/fr/ru/fa no deben alterarse ni un byte de comportamiento.
No hay suite de regresión para esas lenguas: el gating explícito ES la garantía; documentarlo.

## Decisiones nuevas de Julian (2026-07-09/10, NO re-litigar)

1. **Etiqueta POSEEDOR, no "Recipiente"** (ceñirse al continuum de Van Valin): el primer
   argumento de `have'` en transferencia/benefactiva se etiqueta POSEEDOR en args_map y en
   `RRGThemRel`. La comunicación (que no tiene `have'`) mantiene "Receptor" — anotarlo en el
   checkpoint para revisión.
2. **Anclaje de la periferia POR ESTRATO en la proyección de constituyentes**: la flecha lateral
   del diagrama de Van Valin es convención gráfica; la codificación computacional correcta (la de
   RRGbank) es hija del estrato modificado con marca `-PERI`. El bug actual: ud2rrg cuelga TODA
   periferia de CORE al nivel de los argumentos. Lo correcto:
   - periferia TEMPORAL ("ayer", "durante la tarde") → hija de **CLAUSE** (sitúa toda la oración
     en el espacio-tiempo);
   - periferia LOCATIVA y de MODO ("en el parque", "lentamente") → hija de **CORE** (modifican el
     evento predicativo);
   - tipo `otro` → CORE (default conservador).
   Árbol de referencia: "Juan comió pizza ayer" debe dar `ADVP-PERI` bajo CLAUSE, no bajo CORE.
3. Decisiones 1-3 del checkpoint L2.5 confirmadas tal cual (benefactiva=accomplishment,
   convención de comunicación, lookup fijo).

## Contexto técnico ya diagnosticado (de L0; no re-descubrir)

- **Bug XPOS**: `is_verb`/`is_noun`/... priorizan XPOS esperando tagsets en MAYÚSCULA (Penn/STTS
  de en/de); AnCora/Freeling usa minúscula ("vmis3s0") → nunca matchea → NotHandled → **0/300 de
  conversión sobre gold crudo**. El pipeline vive porque `limpiar_conllu_stanza` borra el XPOS
  (fallback a UPOS): con eso, 59.7% (179/300). Baseline en `data/kpi_linking_baseline.json`.
- **`obl:arg` no está en el dispatch de ud2rrg** → "María" en "Le compró un regalo a María"
  lanza NotHandled → **la oración entera se queda sin árbol** (no hay dummy-tree en el path real:
  la excepción sube al except de nivel oración).
- **`is_clitic_pronoun` solo reconoce francés** → el "le" español cae a PRON genérico.
- `peri()` existe pero no se llama uniformemente en los handlers de `obl` (acuerdo periferia
  baseline: 27.6%).
- El MISC ya viene poblado por L2/L2.5 (contrato en el docstring de `misc_rrg.py`):
  `RRGRole=CoreArg|RRGMacrorole=...|RRGVar=x<n>[|RRGThemRel=...]`,
  `RRGRole=Periphery|RRGType=<temporal|locativo|modo|otro>[|RRGWrap=...]`,
  `RRGRole=AGX|RRGDoblado=<si|no>[|RRGArgVar=x<n>]`, `RRGRole=Impersonal`,
  `RRGImplicitActor=<etiqueta>`. **Principio híbrido: el MISC manda** (la inteligencia vive en la
  Etapa 1); las heurísticas dentro de ud2rrg son solo fallback cuando no hay marcas.

## Tareas en ud2rrg.py

### 1. Fix XPOS (gated es)
Para `language=='es'`: decidir POS por UPOS (o tolerar el tagset minúscula de AnCora), de modo que
el gold CRUDO (XPOS intacto) convierta igual que el limpiado. Ninguna otra lengua cambia de
comportamiento.

### 2. `obl:arg` al dispatch
Prioridad MISC: `RRGRole=CoreArg` → NP argumento del CORE (misma operación que nsubj/obj);
`RRGRole=Periphery` → periferia (§4). Fallback sin MISC (es): `obl:arg` → argumento del CORE.

### 3. Clíticos españoles → nodo AGX bajo NUC
- Señal primaria: `RRGRole=AGX` en MISC. Fallback (es, sin MISC): PRON átono dativo/acusativo
  (me, te, se, le, les, lo, la, los, las, nos, os) dependiente del verbo. CUIDADO con `se`: los
  deprel `expl/expl:pv/...` ya tienen manejo — no romperlo; el AGX por fallback solo cuando no
  hay ruta existente que lo consuma.
- Árbol elemental nuevo `(AGX <clítico>)` adjunto bajo el NUC del anfitrión (hermano de PRED),
  según el análisis de Julian: ORACIÓN>CLÁUSULA>CENTRO>NÚCLEO>{AGX, PRED>V}.
- Doblado: el sintagma pleno ("a María") sigue siendo NP argumento del CORE (con §2 ya no
  revienta). Clítico solo: AGX presente y ningún NP (el argumento se satisface
  morfológicamente — Completeness Constraint).
- Resultado esperado: "Le compró un regalo a María" POR FIN genera árbol, con AGX bajo NUC.

### 4. Periferia: `peri()` uniforme + anclaje por estrato
- `RRGRole=Periphery` en MISC → SIEMPRE `peri(...)`, nunca posición argumental.
- Estrato por `RRGType` (decisión 2): temporal → CLAUSE; locativo/modo/otro → CORE. Sin MISC:
  comportamiento actual (no adivinar).
- Representación: conservar la convención de hija con sufijo `-PERI` en el estrato correcto.
  OPCIONAL (solo si no rompe las operaciones de composición/fusión que asumen espina
  SENTENCE/CLAUSE/CORE/NUC): envolver en un nodo explícito `PERIPHERY`; si no es viable,
  documentar por qué y quedarse con `-PERI`.

### 5. NotHandled residual
NO enmascarar errores: los casos aún no cubiertos siguen fallando la oración (visible y
diagnosticable). Si se implementa algún rescate plano, debe ser opt-in por config y contarse
APARTE en el KPI (conversión-limpia vs conversión-con-rescate). Default: sin rescate.

## Tareas fuera de ud2rrg.py

### 6. Guard "todos los días" (`nucleo_periferia.py`) — bug de campo de Julian
"Todos los días yo como chocolates" hoy produce EL corrupta: Stanza parsea "días" como nsubj y la
Etapa 1 lo acepta (x1:días,Actor + x2:yo,Actor). Guard CONSERVADOR: NP con núcleo en nombres de
tiempo + cuantificador universal (todos/cada) parseado como nsubj/obj → degradar a periferia
temporal(frecuencia) SOLO si hay evidencia independiente de que no es el sujeto real: (a) existe
otro nsubj, o (b) los feats de persona del verbo no concuerdan con él pero sí con un pro-drop
("como" 1sg vs "días" 3pl). Si dispara, log + nota. Tests: "Todos los días yo como chocolates"
(caso a), "Todos los días como chocolates" (caso b), y el control "Todos los días son iguales"
(NO degradar: concordancia 3pl y único candidato — "días" ES el sujeto). La periferia degradada
lleva tipo temporal → el MISC la marca y ud2rrg la ancla a CLAUSE (§4). Wrapper de frecuencia
sigue PENDIENTE (no envolver; listar como hoy).

### 7. Rename POSEEDOR (`ditransitivas.py`, `misc_rrg.py`, tests afectados)
Etiqueta del 1er argumento de `have'`: Recipiente → **POSEEDOR** (args_map `NMR(Poseedor)`,
MISC `RRGThemRel=Poseedor`) en transferencia y benefactiva. Comunicación conserva Receptor
(anotar en checkpoint).

## Medición y validación

- **Suite nueva `test_ud2rrg_es.py`** (fixtures .conllu mínimos, generados con Stanza o escritos
  a mano; correr el conversor como lo hace gruxx): (a) "Juan comió pizza ayer" → `ADVP-PERI` bajo
  CLAUSE (no CORE); (b) "Juan corrió en el parque" → `PP-PERI` bajo CORE; (c) "Le compró un
  regalo a María" → árbol existe, AGX bajo NUC, NP de María en CORE; (d) "Le dije la verdad" →
  AGX sin NP pleno; (e) gold AnCora CRUDO (XPOS intacto, unas 20 oraciones) → conversión > 0 e
  igual a la versión limpiada; (f) fixture SIN marcas MISC → mismo output que antes del cambio
  para una oración inglesa o genérica (evidencia del gating).
- **KPI post-L3** con `kpi_linking.py` (misma muestra n=300): reportar antes/después de (1)
  conversión gold crudo (era 0%), (2) conversión gold limpiado (era 59.7% — debe subir: los
  dativos ya no revientan), (3) acuerdo de periferia (era 27.6% — debe subir: anclaje y peri()
  uniforme). El checker de completeness formal es L4, aquí solo estas tres cifras.
- Las 9 suites del proyecto (128 tests) verdes; batería ditransitiva del checkpoint L2.5 intacta
  en el lado semántico y AHORA con árboles del lado sintáctico.
- Commit final tras validar (mensaje descriptivo de L3).

## CHECKPOINT final — PARAR aquí (L4 va en el siguiente prompt)

Informe para Julian: (1) las tres cifras del KPI antes/después; (2) árboles ASCII de las 4
oraciones de la suite nueva (que Julian compare "Juan comió pizza ayer" contra su diagrama de
referencia); (3) decisión tomada sobre nodo PERIPHERY explícito vs sufijo `-PERI` y por qué;
(4) evidencia del gating (fixture sin MISC intacto); (5) disparos del guard de frecuencia si los
hubo; (6) pendientes acumulados (wrapper de frecuencia, compuestos "cerca de", _CASE_TEMPORAL,
forma plena de comunicación, fallback probe, bucle de corrección de usuario). L4 = checker de
completeness (rama PERIPHERY ↔ wrapper en la EL; x_n ↔ NPs del CORE; AGX ↔ dativo satisfecho) +
KPI final contra el baseline.
