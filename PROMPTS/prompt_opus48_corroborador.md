# Tarea: corroborador Van Valin — TERMINAR el módulo (edit interrumpido), integrarlo en predict() y calibrarlo

Módulo `aspect_classifier` del proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python`
(3.10; torch, transformers<5, sklearn, pandas, pyyaml).

**PROHIBIDO:** tocar `gruxx_ai1.py`; tocar los `.joblib` de `models/` y `models/contextual/`;
reentrenar el probe; regenerar o sobrescribir `data/contextual_sentences.csv` (curado a mano, append-only).

## Contexto

Pipeline actual: oración → Stanza → `rrg_ls_mapper.py` (Etapa 1 núcleo/periferia + pro-drop;
`AspectClassifier.predict()` = probe por embeddings BERTIN → vector `[stat, dyn, tel, pun]` → árbol de
decisión en `aspect_classifier/decision_tree.py`; causatividad + gates; construcción de la LS) →
`gruxx_ai1.py` renderiza. `aspect_classifier/pruebas_clase_aspectual.py` implementa las pruebas de
clase aspectual de Van Valin como contrastes de pares mínimos con la cabeza MLM de BERTIN
(`bertin-project/bertin-roberta-base-spanish`, `AutoModelForMaskedLM`, sin reentrenar): segunda
opinión ortogonal al probe.

Veredicto empírico del checkpoint (decisiones ya tomadas por Julian — NO re-litigar):

- **p1 (progresivo)**: la señal sólida → señal principal de `pun` (romper 0.01 / estornudar 0.16 vs
  correr 0.92 / estudiar 0.87 en score s1).
- **p45 (en/durante, máscara única)**: ordena bien la telicidad RELATIVA (romper Δ+6.2 > escupir +3.9
  > correr +1.8) pero está descentrada ("en" gana siempre por frecuencia: todos los Δ > 0) → conservar
  con OFFSET DE CENTRADO calibrable.
- **p6 (participio resultativo)**: auxiliar de bajo peso → contribución leve a `tel` (estado
  resultante ≈ telicidad). NO usar como discriminador Achievement-vs-Semelfactive (falla:
  "estornudado" da 0.72).
- **p2 (vigorosamente) y p3 (de repente)**: inútiles → FUERA del vector (p2 no discrimina — todos ≈1,
  saber incluido; p3 gana siempre por frecuencia narrativa). Solo diagnóstico opcional.
- Blend per-rasgo: λ alto en `pun` y `tel` (donde el probe flaquea), ~0 en `stat`/`dyn` (el probe ya
  es bueno ahí).
- Límite honesto asumido: gritar/escupir no suben `pun` por p1 (su progresivo es naturalmente
  iterativo, caveat del propio Van Valin). No perseguirlo.

## Estado EXACTO — un edit quedó interrumpido a mitad

En `aspect_classifier/pruebas_clase_aspectual.py` YA está hecho:

- `_od_de()` y `_sujeto_y_marco()`: OD por lema desde el mapa `OBJ` de `gen_contextual_sentences`
  ("Juan sabe la respuesta", no "Juan sabe el objeto"), fallback "el objeto"; pronominal →
  "El objeto se…".
- `DEFAULTS` ya declara `bias_mask: 0.0` y `peso_p6_en_tel: 0.2` (con sus comentarios).

PERO quedó A MEDIAS (esto es lo primero a terminar):

- `bias_mask` está declarado pero **jamás se aplica**: `_contraste_mask` manda el Δ crudo a la
  sigmoide.
- `peso_p6_en_tel` está declarado pero **el vector no lo usa**.
- El vector de `evaluar()` sigue siendo el VIEJO mapeo composicional: `stat=(1−s1)(1−s2)`,
  `dyn=s2`, `pun=(1−s1)·s2` — todo depende de s2 (p2), que está descartada — y `tel=s45` sin
  centrar y sin p6.
- El docstring de cabecera describe la batería vieja (p2→+dyn, p3→−pun, p6 como
  Achievement-vs-Semelfactive).
- `test_pruebas_aspectuales.py`: **`test_frames_transitivo` YA FALLA** (espera "el objeto";
  con el OD por lema `estudiar` ahora lleva "matemáticas"). 4/5 rápidos en verde.

NO tocados aún para esta tarea: `predict.py`, `calibrate.py`, `rrg_ls_mapper.py`. `config.yaml` ya
tiene la sección `pruebas` con `lambdas: {stat: 0, dyn: 0, tel: 0, pun: 0}` (corroborador apagado →
pipeline sin cambios).

## 1. Terminar `pruebas_clase_aspectual.py`

- `_contraste_mask`: aplicar el offset — `s = sigmoide((Δ − bias_mask) / temperatura_mask)`. El valor
  del bias se fija en la calibración (rango útil visto: Δ ∈ [+1.8, +6.2]).
- Recomponer el vector de `evaluar()` según las decisiones:
  - `pun = 1 − s1` (de p1).
  - `stat`: aporte leve del lado negativo de p1 (misma magnitud `1 − s1`; la atenuación la pone
    λ_stat bajo en el blend, no inventar otra fórmula).
  - `tel = (1 − peso_p6_en_tel) · s45_centrado + peso_p6_en_tel · s6`.
  - `dyn = None` → **SIN SEÑAL**. Representar los rasgos sin señal con `None` en el vector; el blend
    los tratará como λ_f = 0 efectivo.
- p2/p3 fuera del vector: computarlas SOLO bajo un parámetro `evaluar(..., diagnostico=False)` (por
  defecto no se pagan sus 4 PLLs extra); cuando se computen, van al `detalle` como hasta ahora.
- p6: mantener el frame con sujeto genérico "El objeto está {part}." (evita la concordancia
  género/número con el OD específico del lema).
- Actualizar el docstring de cabecera y el de `evaluar()` a la batería real (p1/p45/p6; p2/p3
  diagnóstico).

## 2. Integrar en `predict()` (`aspect_classifier/predict.py`; NO `gruxx_ai1.py`)

- `AspectClassifier` instancia `CorroboradorVanValin` de forma PEREZOSA (property, config
  `pruebas` de `config.yaml`, mismo `model_name` que declara el módulo). Cachear `evaluar()` por
  `(lema, transitivo, pronominal)` en un dict de la instancia.
- Blend per-rasgo tras obtener las probs del probe (léxico o léxico+contextual, como hoy):
  `P_final[f] = (1 − λ_f) · P_probe[f] + λ_f · P_pruebas[f]`, con λ desde
  `config.pruebas.lambdas.{stat,dyn,tel,pun}`. Si `P_pruebas[f] is None` (sin señal) → λ_f = 0
  efectivo para ese rasgo.
- **FAST PATH**: si todas las λ son 0 → NO evaluar el MLM en absoluto (regresión cero también en
  tiempo; salida byte-idéntica a hoy).
- Fallback: si el MLM no carga (excepción en la carga perezosa) → warning y degradar a solo-probe;
  `metodo` SIN el sufijo "+pruebas"; pipeline intacto.
- El árbol de decisión corre sobre `P_final`. El dict de retorno añade: `vector_probe`,
  `vector_pruebas` (con `None` en los rasgos sin señal), `pruebas_detalle`, y `vector` pasa a ser el
  final; `metodo` = `"lexical+pruebas"` / `"contextual+pruebas"` cuando el corroborador participó.

## 3. Mostrar en la salida (mapper; SIN tocar `gruxx_ai1.py`)

En `rrg_ls_mapper.py` (la construcción de `aspect_note`, ~línea 659): si `ac_result` trae
`pruebas_detalle`, añadir un resumen legible construido desde los veredictos, p. ej.:

    Pruebas VV: p1 progresivo✗→puntual · p45 en<durante→atélico · p6 —

(rasgo/prueba sin señal → "—"). Se muestra por el render existente (`morph_note`), sin cambios en
`gruxx_ai1.py`.

## 4. Calibración (extender `calibrate.py` con un modo `--pruebas` o script hermano)

- Mismo held-out que la calibración vigente: fold 1 de `StratifiedGroupKFold(5, seed 42)` sobre los
  embeddings contextuales, agrupado por lema (ver `calibrate.run()`); cabeza contextual reentrenada
  sin los lemas del held-out, cabeza léxica tal cual, `w = fase2.peso_contextual` FIJO en su valor
  actual (0.5) — aquí solo se calibra el corroborador.
- Computar `vec_pruebas` POR LEMA del held-out con el marco del lexicón (`clf._marco_sintactico`) y
  CACHEARLO a disco (json) — son ~n_lemas × ~6 PLLs, no recomputar en cada punto del barrido. OJO:
  el bias de p45 se aplica DESPUÉS, así que cachear los Δ crudos (o los scores por prueba), no solo
  el vector final.
- Barrer: `λ_pun, λ_tel ∈ {0.3, 0.4, 0.5, 0.6, 0.7}`, `λ_stat, λ_dyn ∈ {0.0, 0.1, 0.2}`,
  `bias_mask ∈ {0.0 … 6.0, paso 0.5}`, maximizando macro-F1 del árbol sobre `P_final`.
- **GUARDARRAÍL DURO**: la config elegida no puede dar macro-F1 menor que probe-solo (todas λ=0, la
  config actual). Si un rasgo no mejora → su λ queda en 0.
- Reportar antes/después: macro-F1, F1 por rasgo (foco `tel`, `pun` — el held-out trae las etiquetas
  por rasgo en `index_ctx.json`) y F1 por clase (foco Semelfactive, State, Active_Accomplishment).
- Fijar los ganadores en `config.yaml` (lambdas + `bias_mask` en la sección `pruebas`) documentando
  el porqué en comentarios, como está hecho para `decision_tree`.

## 5. Tests + validación

- Arreglar `test_frames_transitivo` (OD por lema: estudiar → "matemáticas").
- Unit rápidos con STUB del MLM (monkeypatch de `_pll_media`/`_contraste_mask`, o inyección de
  scores): (a) el vector ya no contiene señal de p2/p3 y `dyn is None`; (b) el centrado: con Δ fijo
  conocido, el veredicto télico/atélico cambia según `bias_mask`; (c) el blend de `predict()` con
  corroborador stub: λ altos suben `pun`; rasgo `None` se ignora aunque su λ > 0; (d) fast path:
  con todas λ=0 el MLM ni se carga.
- `@slow` (MLM real): con el bias calibrado, estudiar → atélico y romper → télico en p45; el blend
  sube `pun` en romper/estornudar (donde el probe lo daba bajo).
- Integración `@slow` (BERTIN + Stanza): "estudié tres horas anoche" → Activity confirmado por DOS
  vías (gate estructural de la Etapa 1 + pruebas diciendo atélico); batería de 15 dianas OK
  (`python -m aspect_classifier.test_fase2_contextual --slow`); con λ=0 la salida es idéntica a hoy.
- Suites completas al final: `test_pruebas_aspectuales [--slow]`, `test_fase2_contextual --slow`,
  `test_complejo --slow`, `test_causatividad`, `test_nucleo_periferia` — todas verdes.
- Guardarraíl verificado: con la config calibrada, macro-F1 ≥ probe-solo.

## Aceptación

- Batería del vector = p1/p45/p6 (p2/p3 solo diagnóstico opcional); OD por lema; p45 recentrada con
  `bias_mask` aplicado; `dyn` sin señal (`None`).
- Blend per-rasgo en `predict()` con fast path λ=0, fallback solo-probe con warning, claves nuevas y
  `metodo` "+pruebas"; resumen "Pruebas VV: …" en `aspect_note` vía mapper.
- Calibración con antes/después documentado; macro-F1 no baja (guardarraíl); `tel`/`pun` o las clases
  débiles mejoran; ganadores fijados y comentados en `config.yaml`.
- "estudié tres horas" Activity por dos vías; 15 dianas OK; regresión cero (resultado Y tiempo) con
  λ=0; `gruxx_ai1.py` y los `.joblib` intactos.
