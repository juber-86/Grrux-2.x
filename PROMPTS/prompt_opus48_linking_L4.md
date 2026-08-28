# Tarea: L4 — checker de completeness ONLINE + medición honesta del KPI + examen final PUD

Proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python` (3.10). Entry point:
`python3 gruxx_ai1.py`. Cierra la fase LINKING (L0–L3 COMPLETADAS: CHECKPOINT_L0_L2.md,
CHECKPOINT_L2_5_DITRANSITIVAS.md, CHECKPOINT_L3.md; commit L3 = `e08b1fb4`).

**PASO CERO**: `git add -A && git commit -m "pre-L4"` antes de tocar nada. Commit final tras
validar.

**CAMBIO DE RÉGIMEN — `gruxx_ai1.py` es LIBREMENTE EDITABLE desde ahora** (Julian lo respaldó;
condición única: el programa debe seguir corriendo y generando EL + árboles en sus tres modos:
interactivo, batch .txt y .conllu directo). Siguen PROHIBIDOS: clasificador (`predict.py`,
`classifier.py`, `decision_tree.py`), corroborador MLM, `pruebas_estructurales.py`, los
`.joblib`, `data/contextual_sentences.csv`. `ud2rrg.py` tocable solo en §3 (mismo régimen L3:
gated `language=='es'`/MISC, otras lenguas ni un byte).

## Contexto crítico (del checkpoint L3 — no re-descubrir)

- Conversión gold crudo 0%→87% (261/300) e idéntica a limpiado. Árboles de dativos existen con
  AGX bajo NUC. Anclaje por estrato: temporal→hija de CLAUSE, locativo/modo/otro→hija de CORE,
  sufijo `-PERI` (SIN nodo PERIPHERY envolvente — las operaciones de composición hacen
  pattern-matching exacto contra SENTENCE/CLAUSE/CORE/NUC; no interponer nodos).
- **La cifra "acuerdo de periferia 28.8%" del checkpoint L3 NO mide el fix**: `kpi_linking.py`
  corre `ud2rrg.transform` sobre el gold SIN inyectar MISC, y el anclaje por estrato es 100%
  MISC-gated. Arreglar esa medición es parte central de esta etapa.
- El MISC lo puebla `misc_rrg.py` (contrato en su docstring) a partir del dict del mapper.
- `kpi_linking.py` ya obtiene el árbol IN-PROCESS (ParentedTree), no parsea ASCII.
- Hallazgos de dispatch pendientes (muestra de 30 gold): `obl:arg`/`obl:agent` bajo cabeza
  NOMINAL o ADJETIVAL (nominalizaciones — `transform_N`/`transform_A` no tienen el dispatch que
  L3 añadió a `transform_V`): 2/30; `expl:pass`/`expl:impers` sin manejo: 4/30.
- Tests preexistentes rotos: `test_lexicon_carga_54_verbos` (Julian curó el xlsx 54→122 verbos;
  el test hardcodea el conteo) — arreglar aquí. `test_slow_blend_sube_pun` (territorio
  corroborador, prohibido) — NO tocar, sigue documentado.
- Nota operativa OOM: NO correr suites `--slow` ni el KPI con instancias interactivas de
  `gruxx_ai1.py` abiertas (máquina de 12 GB; dos copias de Stanza+BERTIN + navegador la agotan).
  Añadir esta advertencia al docstring de los scripts de KPI.

## 1. Checker de completeness (módulo nuevo, p.ej. `aspect_classifier/completeness.py`)

La Restricción de Integridad de la RRG vuelta código. Función pura:
`verificar(ls_data: dict, arbol: ParentedTree | None) -> dict` que compara el dict del mapper
contra el árbol real de ud2rrg:

1. **Argumentos**: cada `x_n` de `variables`/`args_map` ↔ un constituyente argumental (NP/PP no
   `-PERI`) dentro del CORE. REGLAS DE SATISFACCIÓN MORFOLÓGICA (¡no son mismatches!):
   - `actor_implicito` (pro-drop, etiqueta '1sg'/'3sg'...): satisfecho por la morfología verbal —
     no se espera NP.
   - dativo solo-clítico (`agx` con `doblado=False`): satisfecho si hay nodo `AGX` en el árbol —
     no se espera NP/PP pleno.
   - `impersonal`: sin argumento esperado.
2. **Periferia**: cada wrapper aplicado (`wrappers` del dict) ↔ una rama `-PERI` en el ESTRATO
   correcto (temporal→CLAUSE, locativo/modo→CORE). Matching best-effort por tipo + estrato +
   lema del núcleo entre los tokens de la rama. Periferia listada sin wrapper (frecuencia,
   beneficiario no disparado, tipo `otro`) → se verifica solo presencia de rama `-PERI` (estrato
   no exigido), o se reporta como `no_verificable` — nunca como error.
3. **AGX**: clave `agx` presente ↔ nodo `AGX` bajo NUC en el árbol (y viceversa).
4. Sin árbol (oración que ud2rrg no convirtió) → `{'ok': None, 'motivo': 'sin_arbol'}`.

Retorno ESTRUCTURADO (insumo del futuro bucle de corrección de L5 — no solo strings):
`{'ok': bool|None, 'checks': [{'tipo', 'elemento', 'estado': 'ok|falta_en_arbol|falta_en_ls|no_verificable', 'detalle'}], 'resumen': str}`.
El `resumen` es la línea legible para el render (p.ej.
`Completeness: ✓ x1(morf) x2↔NP x3↔PP · for'↔PERI@CLAUSE · AGX✓` o
`⚠ x3 sin constituyente en el árbol`).

## 2. Integración ONLINE en `gruxx_ai1.py`

- Para que el checker reciba el ÁRBOL como objeto (no ASCII): pasar la conversión a IN-PROCESS
  (importar `ud2rrg` y llamar a su transform por oración con try/except individual — una oración
  mala no debe tumbar el programa), conservando EXACTAMENTE el formato de salida ASCII actual
  para el render. Si el in-process resulta arriesgado por estado global de ud2rrg, fallback
  aceptable: mantener el subprocess para el display y llamar in-process SOLO para el checker
  (doble coste asumido); documentar la elección.
- Tras generar árbol + LS de cada (sub)oración: correr `verificar()` y mostrar la línea
  `Completeness:` en el render (en `mostrar_resultado`, junto al bloque LS). El dict completo
  del checker se guarda en el resultado (`res['completeness']`) y se incluye en el .txt de
  guardado.
- **Diseño para L5 (NO implementar, dejar preparado)**: aislar el render en funciones (que ya lo
  está: `mostrar_resultado`); el dict del checker + el dict del mapper son la interfaz que
  consumirá el bucle de corrección del usuario (L5: el usuario introduce la EL correcta con los
  formalismos correctos; gruxx la VALIDA y si no es correcta la RECHAZA; aceptada → sus
  componentes van a los CSV/léxicos curados). Dejar comentarios TODO-L5 en los puntos de
  enganche: (a) tras mostrar una advertencia de completeness, (b) donde se aceptaría input del
  usuario, (c) qué archivos curados recibirían cada tipo de corrección. NADA de lógica nueva.

## 3. Flecos de dispatch en `ud2rrg.py` (mismo régimen que L3: gated es/MISC)

1. **`obl:arg`/`obl:agent` bajo cabeza NOMINAL/ADJETIVAL**: replicar en `transform_N` y
   `transform_A` el dispatch que L3 añadió a `transform_V` (MISC primero, fallback es).
2. **`expl:pass`/`expl:impers`** (pasiva refleja e impersonal con `se`): el clítico `se` es
   morfema → nodo `AGX` bajo NUC (mismo análisis y mismo árbol elemental que los dativos de L3;
   coherente con la teoría de Julian: los clíticos se enlazan a AGX). El `nsubj:pass` sigue
   siendo NP argumento del CORE (la Etapa 1 ya lo trata como Undergoer). ANOTAR en el checkpoint
   que la decisión "se pasivo/impersonal → AGX" es interpretación teórica a validar por Julian.
3. Verificar el gating igual que L3 (fixture no-es byte-idéntico).

## 4. Medición honesta + examen final

1. **Arreglar `kpi_linking.py`**: modo pipeline híbrido REAL — para cada oración gold: correr
   Etapa 1 (+ mapper completo con clasificador: es el pipeline real; advertencia OOM en el
   docstring), inyectar MISC vía `misc_rrg`, ENTONCES convertir con ud2rrg. Métricas: (a)
   conversión, (b) acuerdo de periferia POR ESTRATO (la rama -PERI existe Y cuelga del estrato
   correcto), (c) **tasa de completeness** (nueva: % oraciones con `ok=True` del checker §1).
   Reportar AnCora dev n=300 antes (baseline L0 + cifras L3) / después.
2. **Examen final PUD**: correr el KPI completo sobre `treebanks/spanish/UD_Spanish-PUD/es_pud-ud-test.conllu`
   (1000 oraciones) **UNA SOLA VEZ, al final, con todo ya validado**. PROHIBIDO iterar contra
   PUD o ajustar nada mirando sus resultados: es el examen de generalización de la fase. Sus
   convenciones de anotación difieren de AnCora — números más bajos son esperables; reportarlos
   tal cual con desglose de causas de fallo (top deprels/POS de los NotHandled).
3. Guardar `data/kpi_linking_post_l4.json` y `data/kpi_pud_final.json`.

## 5. Higiene

- `test_lexicon_carga_54_verbos` → dinámico: asertar ≥54 filas, columnas requeridas presentes,
  plantillas ∈ {transferencia, benefactiva, comunicacion}, sin lemas duplicados. (El xlsx vivo
  tiene 122 — Julian lo cura activamente; el test no debe volver a romperse por curaduría.)
- Guard de frecuencia con Stanza real: test @slow con "Yo como chocolates todos los días"
  (variante postverbal — la preverbal original cae en el homógrafo "como" SCONJ, que se IGNORA
  en L4 por orden de Julian; L5). Verificar que la periferia degradada/detectada acaba anclada
  a CLAUSE en el árbol.

## Tests + validación

- `test_completeness.py` nuevo (fríos, dict+árbol sintéticos): los 3 checks en ok, mismatch por
  cada lado (falta_en_arbol/falta_en_ls), satisfacción morfológica (pro-drop y clítico-solo NO
  son errores), impersonal, sin árbol → ok=None, periferia no_verificable no es error.
- `test_ud2rrg_es.py` ampliado: fixture de nominalización con `obl:arg` bajo NOUN → convierte;
  "Se venden casas" / "Se vive bien" → árbol con AGX y (en la pasiva) NP del nsubj:pass; gating
  no-es intacto.
- @slow end-to-end: "Le compró un regalo a María" → línea `Completeness: ✓` con AGX y x3↔PP;
  una oración con periferia temporal y locativa → wrappers ↔ ramas en estratos correctos; los
  tres modos de gruxx (interactivo/batch/.conllu) siguen funcionando y el .txt guarda la línea
  de completeness.
- Suites completas verdes (137+nuevos; los 2 fails preexistentes: lexicon queda ARREGLADO aquí,
  blend_sube_pun se queda como está y documentado).

## CHECKPOINT final de la FASE — PARAR aquí

Informe de cierre para Julian: (1) tabla completa del KPI: baseline L0 → L3 → L4 (conversión,
acuerdo de periferia por estrato AHORA SÍ medido, tasa de completeness); (2) resultado del
examen PUD con desglose de causas de fallo (será el insumo para priorizar L5); (3) 3-4 salidas
de gruxx mostrando la línea Completeness (una ✓ limpia, una ⚠ real); (4) la decisión
"se→AGX" para validación teórica de Julian; (5) pendientes que pasan a L5: bucle de corrección
del usuario con validación de EL, homógrafos del parser, wrapper de frecuencia, compuestos
"cerca de", _CASE_TEMPORAL, forma plena de comunicación, fallback probe BERTIN.
