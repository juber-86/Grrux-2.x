# Tarea: Reentrenamiento con el lote `augment_habitual` (presente) + recalibración + segunda oportunidad del corroborador

Proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python` (3.10). NO hacer commits
(orden vigente de Julian). **ADVERTENCIA OOM**: esta tarea extrae embeddings BERTIN de ~536
oraciones y corre suites `--slow` — NO tenerla en paralelo con instancias interactivas de
`gruxx_ai1.py` abiertas (máquina de 12 GB; verificar con `ps` antes de arrancar).

## Contexto

Bug de campo (2026-07-10): "Juan come / come manzanas / come la manzana / se come las manzanas"
salían Semelfactive/Achievement/Accomplishment por pun≈0.52-0.54 (ruido apenas sobre el umbral
0.45) y dyn desplomándose con "se" — causa raíz: el dataset contextual era pretérito-dominante y
el PRESENTE habitual es territorio débil del probe. La corrección ESTRUCTURAL ya está en
producción (gates composicionales de L4.5, checkpoint CHECKPOINT_L4_5.md — las 5 dianas ya salen
bien POR GATE). Esta tarea es la corrección DE DATOS: que el clasificador acierte por sí solo y
los gates queden como cinturón de seguridad.

Julian curó y etiquetó 68 oraciones nuevas en PRESENTE en
`aspect_classifier/data/contextual_sentences.csv` (ids 469–536, `fuente=augment_habitual`;
dataset total 536 filas): 20 Activity habitual (obj desnudo/intransitivo/adverbios), 12
Active_Accomplishment (obj delimitado + pares con se aspectual), 10 State (contrapeso para que
presente≠dinámico no sea atajo), 10 Semelfactive habitual (DECISIÓN DE ETIQUETADO de Julian:
conservan la clase léxica con pun=1 — "El paciente tose sin parar" = Semelfactive; ese es el
gold, no discutirlo), 8 Accomplishment no-agentivo, 8 Achievement. Todo en 3ª persona (evita el
homógrafo "como" SCONJ), sin los 5 lemas excluidos a propósito (nadan/sanan/hipan/palmea/eructa).

## Permisos y prohibiciones DE ESTA TAREA (distintos de las etapas de linking)

- **PERMITIDO** (es el objetivo): re-extraer embeddings contextuales
  (`data/embeddings/embeddings_ctx.npy` + `index_ctx.json`), REENTRENAR la cabeza contextual
  (`models/contextual/*.joblib`), recalibrar `config.yaml` (secciones `fase2`, `decision_tree`,
  `pruebas`).
- **PROHIBIDO**: la cabeza LÉXICA (`models/*.joblib` raíz — la semilla no cambió, no
  reentrenar); `contextual_sentences.csv` es INPUT DE SOLO LECTURA (curado a mano, append-only —
  cero modificaciones, ni "arreglos" de formato); `gruxx_ai1.py`, `ud2rrg.py`,
  `rrg_ls_mapper.py`, módulos de linking, corroborador (`pruebas_clase_aspectual.py` el MÓDULO —
  su config sí puede cambiar en §5), `pruebas_estructurales.py`.

## Pasos

### 1. Re-extracción
`extractor_contextual` sobre el CSV completo (respeta `revisar=True` y lista TODO skip, regla de
higiene existente). Reportar: cuántas de las 68 nuevas se extrajeron limpias y cuáles se
saltaron y por qué (parse de Stanza — verificar en particular que los pares con "se" agrupan el
complejo verbal correctamente). Si alguna nueva falla por parse, NO editarla: reportarla a
Julian en el checkpoint.

### 2. Reentrenar cabeza contextual + CV
`train_contextual` con los embeddings nuevos. CV StratifiedGroupKFold POR LEMA (la regla
antifuga de siempre). Reportar ANTES (números vigentes: State 0.77, stat 0.79, dyn 0.79, AA
0.74, Semelf ~0.82 del held-out) / DESPUÉS por rasgo y por clase — foco: ¿pun y dyn mejoran en
presente sin degradar el resto?

### 3. Recalibrar
`calibrate.py` (barrido w × dyn × pun × tel contra held-out agrupado por lema, fold 1 SGKF seed
42). OJO: el dataset creció 468→536, así que el held-out NO es el mismo de antes — las cifras no
son comparables 1:1 con 0.796; el GUARDARRAÍL se aplica así: sobre el held-out NUEVO, la config
elegida debe ser ≥ que la config vigente (w=0.5, dyn=0.40, pun=0.45, tel=0.35) evaluada en ese
mismo held-out. Documentar ganadores y porqué en `config.yaml` como siempre. Recordatorio de
lecciones previas: tel no puede subir de ~0.39 (frases de medida topan en blend≈0.39); bajar pun
empeoró Semelfactive en el pasado — el barrido decide, pero si mueve umbrales, la batería
completa (§6) es el juez final.

### 4. Las 5 dianas del bug — ¿acierta ya el clasificador SOLO?
Para cada una ("Juan come", "Juan come manzanas", "Juan come manzanas siempre", "Juan se come
las manzanas", "Juan come la manzana"): reportar el vector y la CLASE CRUDA del clasificador
(antes de gates — el mapper ya expone `ls_type_clasificador`) antes/después del reentrenamiento.
Éxito ideal: las 5 correctas sin gate (los gates se quedan en producción igualmente, como
cinturón). Éxito aceptable: pun/dyn se alejan del borde (pun de comer en presente << 0.45)
aunque alguna clase cruda siga dependiendo del gate. Reportar tal cual salga.

### 5. Segunda oportunidad del corroborador Van Valin
El bug de comer es EXACTAMENTE el "hueco real" que se acordó esperar antes de revisitar λ
(CHECKPOINT del corroborador 2026-07-08: se apagó porque no aportaba sobre un held-out
pretérito-céntrico). Ahora el held-out nuevo contiene presentes:
- Re-correr `python -m aspect_classifier.calibrate --pruebas` (barrido λ_pun/λ_tel alto,
  λ_stat/λ_dyn bajo, bias_mask; el caché de pruebas por lema se recalcula para los lemas nuevos
  del held-out). GUARDARRAÍL DURO de siempre: macro-F1 ≥ probe-solo (post-reentrenamiento) en el
  mismo held-out; rasgo que no mejora → λ=0.
- Reportar el veredicto con números: ¿λ_pun ahora gana su lugar (la prueba p1 del progresivo
  debería aplastar el pun espurio de comer: "Juan está comiendo" es perfecto)? Si gana: fijar
  las λ ganadoras en `config.yaml`, verificar que el fast path λ=0 sigue intacto como mecanismo,
  y correr la batería completa con el corroborador ENCENDIDO (asumiendo el coste del MLM por
  predict — documentarlo). Si no gana: dejar λ=0 y documentar el resultado con la misma
  honestidad que la vez anterior.

### 6. Batería completa (el juez final)
Con la config final (reentrenada + recalibrada + corroborador según §5): las 5 dianas nuevas,
las 15 históricas, las 26 de wrappers, la batería ditransitiva, "rompió el vaso"→Achievement,
"corrió cinco kilómetros"→AA, "estudié tres horas anoche"→Activity, y las suites completas (160
no-slow + slow). Si el reentrenamiento mueve alguna diana histórica: PARAR y reportar a Julian
antes de tocar cualquier gold (mismo protocolo de siempre).

## CHECKPOINT — PARAR aquí

Informe: (1) extracción (68 nuevas: limpias/skips con motivo); (2) CV antes/después por rasgo y
clase; (3) config recalibrada con guardarraíl demostrado; (4) tabla de las 5 dianas: vector +
clase cruda antes/después + qué gate disparó (si alguno); (5) veredicto del corroborador con
números (encendido o apagado, y por qué); (6) batería completa verde o qué se movió. Después de
este checkpoint: L5 (conciliación AGX + bucle de corrección + Vector/Completeness legibles +
-help), cuyo diseño Julian repasará antes de implementar.
