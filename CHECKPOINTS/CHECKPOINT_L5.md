# CHECKPOINT L5 — corrección del usuario + conciliación AGX + salida GRR + glosario

Implementó Opus 4.8 (sesión de implementación). **SIN commits** (orden de Julian).
Estado de partida: reentrenamiento habitual aceptado (w=0.55/dyn=0.45/pun=0.40/tel=0.40,
corroborador apagado) — NO revertido. PUD intocado. Prohibiciones respetadas: clasificador
(.joblib/predict/classifier/decision_tree), corroborador MLM, `contextual_sentences.csv`
(solo lectura) — ninguno tocado. `ud2rrg.py` tocado SOLO en la capa gated `language=='es'`/MISC.

Suites frías verdes: nucleo_periferia 25 · misc_rrg 18 · completeness 18 ·
pruebas_estructurales 23 · ditransitivas 16 · causatividad 8 · pruebas_aspectuales 11 ·
wrappers_ls 20 · **l5 17** (nuevo) = 156 tests.

Suites `--slow` (modelo real): telicidad_l4_5 5/5 · nucleo_periferia 26 · misc_rrg 19 ·
ud2rrg_es 16 (+1 skip homógrafo, pre-existente) · l5 18 · ditransitivas 18 ·
pruebas_estructurales 25 · completeness 18. **2 fallos PRE-EXISTENTES** (documentados en
CHECKPOINT_REENTRENAMIENTO_HABITUAL.md, NO causados por L5): `test_slow_cause_por_clase_y_
regresion` ("El perro se sacudió" semelfactive→activity, regresión del reentrenamiento —
sujeto explícito, mis gates no la tocan) y `test_slow_blend_sube_pun` (territorio corroborador).

---

## (1) §0 — dianas restauradas (evidencia + diagnóstico)

Gate nuevo **G-AA-medida** en `rrg_ls_mapper` (`activity` + sujeto agentivo + obj con
`nummod` + lema durativo léxico → `active_accomplishment`, nota `gate=obj_medida→AA`;
helper `nucleo_periferia.objeto_con_numeral_medida`). Además dos redes de seguridad para
las derivas del reentrenamiento (ambas verificadas disparando sobre las formas pro-drop/
impersonales, ver abajo).

Evidencia (clasificador real, tras el reentrenamiento):

| oración | clase cruda | clase final | mecanismo |
|---|---|---|---|
| Juan corrió cinco kilómetros | tel=0.38 (fallaría) | **active_accomplishment** | `gate=obj_medida→AA` |
| Juan empuja el carro | active_accomplishment (tel=0.94) | active_accomplishment | **G-AA-medida NO dispara** (det, sin numeral) ✓ guarda |
| corrió vigorosamente (pro-drop) | **semelfactive** (pun=0.50) | **activity** | `gate=prodrop_durativo→Activity` |
| Juan corrió vigorosamente | activity (pun=0) | activity | el clasificador ya acierta (sujeto explícito) |
| llueve (impersonal) | **active_accomplishment** | **activity** | `gate=impersonal_sin_delimitador→Activity` |
| El pastel fue comido por Juan | active_accomplishment | **active_accomplishment** (GOLD) | clasificador; NO se degrada (tiene padecedor nsubj:pass) |

**Diagnóstico vigorosamente / llueve:** ambas derivas del reentrenamiento SÍ se reproducen
en las formas mínimas (bare `corrió vigorosamente` → semelfactive cruda; `llueve` → AA cruda).
No eran "clase cruda mal reportada": son derivaciones reales del regresor. Los dos gates
nuevos las rescatan estructuralmente:
- `prodrop_durativo`: sujeto pro-drop + verbo durativo léxico + sin delimitador → activity
  (el gate `obj_desnudo` previo exigía sujeto agentivo EXPLÍCITO y no cubría el pro-drop;
  la guarda de clase léxica durativa impide degradar un logro pro-drop genuino como "llegó").
- `impersonal_sin_delimitador`: AA impersonal sin ningún delimitador → activity (Prueba 4 de
  Van Valin); ceñido a `impersonal` para NO tocar la pasiva de AA (`el pastel fue comido`).

`test_telicidad_l4_5`: relajada `test_slow_cinco_dianas...` (clase correcta, nota de gate
OPCIONAL — el clasificador ya acierta 3/5 solo tras el reentrenamiento) + test nuevo
`test_slow_l5_estabilizacion_gates` (5/5 verde con modelo real). Guardarraíl intacto:
`rompió el vaso` → achievement (romper es Achievement léxico).

---

## (2) §1 — conciliación AGX (KPI4 nuevo)

**Completado `_detectar_agx`** (nucleo_periferia): registra me/te/nos/os + le/les en TODAS
sus posiciones, con fuente por deprel — `dativo` (obl:arg/iobj, con arg morfológico cuando
va solo), `acusativo` (obj, Undergoer morfológico), `reflexivo` (expl:pv 1ª/2ª persona,
concordancia sin arg propio). `se` mantiene su manejo propio (se_pasivo/impersonal/aspectual
+ anticausativo-no-AGX); lo/la/los/las siguen como argumento de CORE (ya reconciliaban).

**Fallback de ud2rrg subordinado al MISC** (gated es): `_es_conllu_analizado(udnode)` lee
la marca `RRGAnalyzed=si`, que `misc_rrg`/`kpi` estampan en TODOS los tokens de una oración
analizada (no solo la raíz — para cubrir clíticos de cláusulas EMBEBIDAS). Con MISC presente,
el `is_clitic_pronoun` fallback NO inventa AGX; también se subordinó la rama `expl:pass/
expl:impers` (un "se" pasivo/impersonal de cláusula embebida ya no genera un AGX que la LS
—solo cláusula principal— no anticipa). Sin MISC (conllu crudo de terceros) el fallback se
conserva intacto. Nueva ruta gated en la rama `obj/iobj` para acusativos marcados AGX.
`completeness.agx_clitico_solo` generalizado (dativo/acusativo satisfechos por el nodo AGX).

KPI4 AnCora dev n=300 (`data/kpi_linking_post_l5.json`):

| métrica | L4.5 | **L5** |
|---|---|---|
| conversión (MISC real) | 98.0% | **98.0%** (294/300) |
| tasa de completeness | 80.3% | **94.9%** (279/294) |
| acuerdo periferia por estrato | 50.6% | 50.6% (130/257) |
| **`agx_arbol_gt_ls`** (patrón dominante L4.5) | ~43 | **0** |
| `agx_ls_gt_arbol` (mismatch opuesto) | 0 | **0** (no se creó ninguno) |

Desglose de las 15 advertencias restantes: `arg_falta_en_arbol` 3 · `peri_falta_en_arbol` 12
(argumentos clausales / periferia tipo "otro" — terreno xcomp/wrappers, fuera de L5). El
patrón AGX desaparece por completo.

Fixture fría `test_nucleo_periferia`: "Me dio el libro" → agx dativo 1sg + un solo x3
morfológico; "Me ve" → acusativo; "Me lavo" → reflexivo.

---

## (3) §2/§3 — salida reordenada y traducida

Orden GRR (`display_grr.render_bloque`, usado por los 3 modos + el `.txt`): **árbol
sintáctico PRIMERO**, **EL léxica inmediatamente debajo**, y luego Tipo / EL formal /
Argumentos / Rasgos / Integridad / CAUSE-método. Traducción user-friendly (§3):
- `Rasgos: estático 0.02 · dinámico 0.75 · télico 0.40 · puntual 0.05 · confianza 0.84`.
- apéndices técnicos traducidos: `gate=…→…` → `corrección: …`; `coercion=…` → `coerción: …`;
  `ditrans=…` → `construcción: …`; `CAUSE[…]` → `causatividad: …`; wrappers legibles se dejan.
- `Integridad: ✓ x1 en la terminación verbal · x2 ↔ sintagma nominal · concordancia (AGX) ✓`
  / `Integridad: ⚠ x2 ("participar") NO aparece como constituyente en el árbol`.
- `--verbose` conserva el `Vector`/`Completeness` crudos.

Captura real ("Le compró un regalo a María" — muestra AGX reconciliado + traducción + orden):

```
  ÁRBOL SINTÁCTICO RRG
  ────────────────────────────────────────
  (… SENTENCE>CLAUSE>CORE>NUC>{AGX 'Le', PRED>V 'compró'} … PP 'a María' …)

  EL léxica  : [[do'(3sg, Ø)] CAUSE [BECOME have'(3sg, regalo)]] PURP [have'(María, regalo)]

  Tipo       : Realización
  EL formal  : [[do'(x1, Ø)] CAUSE [BECOME have'(x1, x2)]] PURP [have'(x3, x2)]
  Argumentos : x1:3sg,pro-drop,Actor(Efectuador); x2:regalo,obj,Undergoer(Tema); x3:María,obl:arg,NMR(Poseedor)
  Rasgos: estático 0.05 · dinámico 0.78 · télico 0.94 · puntual 0.07 · confianza 0.88
  construcción: benefactiva (léxico)
  Integridad: ✓ x1 en la terminación verbal · x2 ↔ sintagma nominal · x3 ↔ frase preposicional · concordancia (AGX) ✓
  Método     : contextual (roBERTa)
```

"Juan corrió cinco kilómetros" muestra `corrección: objeto de medida (numeral) → Realización
activa` (el gate G-AA-medida traducido). Ejemplo con ⚠ traducida:

```
  Integridad: ⚠ x1 ↔ sintagma nominal · x2 ("participar") NO aparece como constituyente en el árbol
```

---

## (4) §4 — glosario / -help

`data/glosario_gruxx.csv` sembrado (62 términos, 7 categorías) — editable por Julian.
`aspect_classifier/glosario.py` + wiring en gruxx: `-help/--help/-ayuda/--ayuda` sin arg →
glosario completo paginado por categorías; `-help <término>` → búsqueda tolerante
(sin acentos/mayúsculas, parcial); anuncio del comando al arrancar y tras cada análisis;
aceptado también como línea del batch.

```
>>> -help agx
  AGX  [Árbol sintáctico]  Índice de concordancia bajo el núcleo: ahí se enlazan los clíticos (le/les/se) y la concordancia verbal.
>>> -help telico
  télico (tel)  [Rasgos]  0-1: si la situación tiene un punto final natural (culminación).
>>> -help peri
  -PERI                    [Árbol sintáctico]  Marca de periferia: adjunto que modifica al estrato del que cuelga …
  PERI@CORE / PERI@CLAUSE  [Notación de gruxx]  Dónde ancla la periferia en el árbol: al centro … o a la cláusula …
>>> -help zzz
  término «zzz» no encontrado — escribe "-help" para ver el glosario completo
```

`-help` (sin arg) vuelca las 7 categorías (Clases aspectuales, Rasgos, Estructura Lógica,
Participantes, Árbol sintáctico, Análisis, Notación de gruxx) paginadas.

---

## (5) §5 — bucle de corrección (demo)

`aspect_classifier/correccion.py`. Activación: prompt de guardado
`¿Guardar en .txt? (s/n) — o (c) para corregir el análisis` + pista con ⚠ cuando la
Integridad falla; en batch se ofrece al final por número de oración. Menú clase / EL /
enrutado; Esc/vacío cancela limpio en cualquier punto.

- **(1) Clase** → STAGING `data/correcciones_clase.csv` (contextual_sentences.csv JAMÁS se
  toca — verificado por mtime en test). Si la clase implica ditransitiva/causativa ausente,
  ofrece registrar el lema (flujo de la opción 2).
- **(2) EL** → validación 3 niveles con rechazo explicado: nivel 1 sintaxis del formalismo
  (paréntesis/corchetes, primitivos), nivel 2 consistencia con la oración (argumentos ∈
  tokens/Ø/x<n>/morf; lema del verbo salvo plantillas abstractas), nivel 3 plantilla
  reconocible (6 clases + causativa + 3 ditransitivas + wrappers). Aceptada → gruxx DERIVA
  el destino: ditransitiva → `verbos_ditransitivos.xlsx` directo (fuente en notas);
  causativa → `causative_lexicon.csv` directo; clase implícita → staging. RE-ANÁLISIS
  confirmatorio: si el análisis no lo refleja, revierte el archivo vivo y cae a staging.
- **(3) Enrutado** → sub-menú elemento→destino; persiste a lista de config
  (`verbos_movimiento`/`adv_dinamicos`…) con `# correccion_usuario`, o staging
  `data/correcciones_enrutado.csv` si no hay lista; re-análisis confirmatorio.
- Log maestro `data/correcciones_log.csv` para toda corrección. Todo lo vivo lleva
  `fuente=correccion_usuario` (auditable/reversible).

Tests `test_l5` (cold, input inyectado): las 3 plantillas / los 3 rechazos por nivel /
staging de clase con contextual intacto por mtime / enrutado a config / re-análisis
confirmatorio en éxito Y en no-confirmación (→ revierte + staging) / Esc sin efectos / log.
Test `@slow` end-to-end con Stanza+mapper reales (dir temporal, restaura `_DITRANS_LEXICON`).

---

## (6) Pendientes que siguen FUERA (documentados)

homógrafos del parser ("como" comer/SCONJ); compuestas/xcomp encadenado (la RRG tiene su
teoría de juntura-nexo — el residuo de `agx_arbol_gt_ls` y de argumentos clausales vive
aquí); operadores en display (nivel pragmático); impersonal refleja con animacidad;
complemento agente-por en pasiva con se (cadena causal secundaria periférica); wrapper de
frecuencia (siempre/nunca); lote de contrapeso de medidas (opcional, refuerzo de tel por
datos además del gate G-AA-medida).

## Decisiones de implementación para revisar con Julian

1. **Alcance de `_detectar_agx`** ceñido a me/te/nos/os/le/les (lo/la/los/las siguen como
   argumento de CORE, que ya reconciliaban en ambos lados; "se" con su manejo propio). Evita
   una reescritura corpus-wide de acusativos de 3ª persona de alto riesgo.
2. **`fuente=correccion_usuario`** se graba en la columna `notas` de los léxicos vivos (xlsx/
   csv) para no romper sus esquemas; la auditoría/reversión formal vive en el log maestro.
3. **Reversión del "aplicar → confirmar"**: la corrección se escribe en vivo, se re-analiza y,
   si NO confirma, se revierte y cae a staging (nunca queda en vivo algo no confirmado).

---

## Addendum (2026-07-12) — fix: `-help` en el prompt post-análisis

Bug reproducido por Julian en uso real: tras un análisis, gruxx muestra el anuncio del
glosario e inmediatamente el prompt `¿Guardar en .txt? (s/n) — o (c) para corregir el
análisis:` — pero ese input crudo NO aceptaba `-help`, lo ignoraba y el término caía al
prompt siguiente (`Oración (o 'salir'):`), justo cuando el usuario acaba de ver terminología
desconocida y necesita el glosario.

**Fix quirúrgico** (`prompt_fix_help_post_analisis.md`):
- `gruxx_ai1.py`: el bucle inline de guardar/corregir se extrajo a
  `_flujo_guardar_o_corregir(oracion, res, reanalizar, entrada=input, salida=print)`
  (inyectable, patrón de `aspect_classifier.correccion`) — misma lógica de antes, más el
  chequeo de `-help` al principio de cada vuelta (vía `_manejar_help`, ahora también
  inyectable). `_imprimir_glosario`/`_manejar_help` ganan parámetros `entrada`/`salida`
  (default `input`/`print`, sin cambio de comportamiento real).
- `aspect_classifier/correccion.py`: `_pedir` (usado por el menú de corrección Y sus 3
  sub-menús: clase/EL/enrutado) ahora es un bucle que responde `-help [término]` y vuelve a
  mostrar el MISMO prompt, en vez de devolver la línea cruda como respuesta.
- Regla general aplicada: en NINGÚN input interactivo de gruxx debe `-help` tragarse la
  respuesta o abortar el flujo. El modo batch y el prompt `Oración (o 'salir'):` (que ya
  aceptaba `-help`) no se tocaron.

**Tests nuevos** (`aspect_classifier/test_l5.py`, 8 tests, cold/frío con input inyectado):
`-help agx`/`-help`/`-help zzz` dentro de `_pedir` y del menú de corrección (responde,
re-muestra el prompt, Esc sigue cancelando limpio después); y en
`_flujo_guardar_o_corregir`: secuencia 1 (`-help agx`→`s` guarda), secuencia 2 (`-help`→`n`
no guarda), secuencia 3 (`-help zzz`→`c` abre el menú de corrección normal), regresión
(`s`/`n`/vacío/`salir` directos). 25/25 tests de `test_l5.py` verdes (17 preexistentes + 8
nuevos); resto de suites frías sin regresión (156→164 tests fríos totales).

**Transcripción de sesión simulada** (pipeline real: Stanza + mapper + ud2rrg, oración "Le
compró un regalo a María" → `-help agx` → `-help` → `s`):

```
¿Guardar en .txt? (s/n) — o (c) para corregir el análisis: -help agx

  AGX  [Árbol sintáctico]  Índice de concordancia bajo el núcleo: ahí se enlazan los
  clíticos (le/les/se) y la concordancia verbal.

¿Guardar en .txt? (s/n) — o (c) para corregir el análisis: -help

Clases aspectuales
──────────────────
  State (Estado)  Situación estática sin dinámica interna: saber, amar, estar roto...
  [... 7 categorías, 62 términos ...]

¿Guardar en .txt? (s/n) — o (c) para corregir el análisis: s
[OK] Guardado en: analisis_le_compro_un_regalo_a.txt
```

El prompt NUNCA se pierde ni salta al siguiente — cada `-help` responde y vuelve a preguntar,
tal como debía funcionar desde el principio.
