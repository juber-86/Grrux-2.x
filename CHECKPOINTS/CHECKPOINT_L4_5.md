# Checkpoint — Mini-etapa L4.5 (checker sin falsas alarmas + LDP + agx-lista + EL con Ø + telicidad composicional)

Implementado según `prompt_opus48_linking_L4_5.md`. Cierra la mini-etapa
QUIRÚRGICA que siguió al cierre de la fase LINKING (`CHECKPOINT_L4.md` +
`data/kpi_linking_post_l4.json`). **NO se hizo commit** (orden explícita de
Julian — el repo arrastra el venv y lo resolverá él).

Modificado: `aspect_classifier/completeness.py` (argumentos clausales, LDP,
agx-lista con conteo), `aspect_classifier/nucleo_periferia.py`
(`destacado_inicial`, `_detectar_agx` unificado —dativo/se_pasivo/
se_impersonal/se_aspectual—, nsubj→Undergoer en pasiva refleja,
`tiene_delimitador_nuclear` con objeto desnudo), `aspect_classifier/
misc_rrg.py` (`RRGDetached`, `RRGAgxFuente`, agx-lista en ida y vuelta),
`rrg_ls_mapper.py` (EL con Ø para se-pasivo/impersonal, los 3 gates de
telicidad composicional), `ud2rrg.py` (routing MISC-gated a PrDP para
periferia temporal destacada, "se" aspectual → AGX vía MISC — ambos gated
`language=='es'`, régimen de siempre). Código nuevo:
`aspect_classifier/test_telicidad_l4_5.py`. Prohibiciones respetadas
(clasificador, corroborador MLM, `pruebas_estructurales.py`, `.joblib`,
`contextual_sentences.csv` intactos; `ud2rrg.py` tocado solo en los puntos
gated `es`/MISC del §2/§5).

## 1. Completeness: antes (59.2%) / después + desglose de advertencias restantes

KPI4 sobre AnCora dev, misma muestra n=300 (`data/kpi_linking_post_l4.json`
→ `data/kpi_linking_post_l4_5.json`):

| Métrica | L4 | L4.5 |
|---|---|---|
| Conversión (con MISC real) | 98.0% (294/300) | **98.0%** (294/300) — sin cambio, como pedía la aceptación |
| Acuerdo de periferia por estrato | 46.7% (120/257) | **50.6%** (130/257) — sube (LDP reconocido como anclaje válido) |
| **Tasa de completeness** | 59.2% (174/294) | **80.3%** (236/294) — sube sustancialmente |

Desglose de las 15 advertencias guardadas (muestra, no exhaustivo — el JSON
completo trae 58 oraciones con `ok=False` de 294 con árbol;
`data/kpi_linking_post_l4_5.json` tiene el conteo real):

| Patrón restante | Ocurrencias (de 15) |
|---|---|
| Árbol tiene más nodos AGX que la LS (`agx_arbol_gt_ls`) | 11 |
| Periferia sin wrapper, no verificable (nunca error, informativo) | 8 |
| Periferia envuelta sin rama -PERI/LDP en el árbol | 4 |
| Variable sin id de token rastreable (causativo/ditrans, `no_verificable`) | 1 |

**Mapa para L5**: el patrón dominante (11/15) es "árbol con nodo(s) AGX que
la LS no anticipa" — sugiere que `ud2rrg.py` sigue teniendo un fallback
propio (`is_clitic_pronoun` sin MISC) que detecta AGX en casos donde
`nucleo_periferia._detectar_agx` no lo registra (p.ej. clíticos le/les en
posiciones que `_detectar_agx_dativo` no cubre, o `me/te/nos/os` no
aspectuales). Candidato de mayor prioridad para una futura mini-etapa de
"conciliación agx" antes de tocar la UI de L5.

## 2. Árbol de "Ayer, Juan corrió" — LDP/PrDP

Fixture con `RRGDetached=si` (Etapa 1 lo marcaría así por "Ayer" inicial +
coma). `PrDP` cuelga de `SENTENCE`, hermana de `CLAUSE` — NO hay
`ADVP-PERI` en ningún lado:

```
                  SENTENCE
          ┌──────────┴──────────────┐
          │                       CLAUSE
          │                         │
         PrDP                      CORE
          │                  ┌──────┴──────┐
         ADVP                NP            │
   ┌──────┴────┐             │             │
CORE_ADV       │           CORE_N          │
   │           │             │             │
NUC_ADV        │           NUC_N          NUC
   │           │             │             │
  ADV          .           N-PROP          V
   │           │             │             │
  Ayer         ,            Juan         corrió
```

Nota operativa confirmada: la heurística sintáctica genérica preexistente
(`precedes_subject`, ajena a L4.5) YA enrutaba a PrDP cuando hay un `nsubj`
hermano de mayor id — por eso "la maquinaria PrDP ya existía". El enrutado
MISC-gated nuevo de L4.5 §2 cubre el HUECO de esa heurística: oraciones
SIN sujeto sintáctico (pro-drop) donde no hay ningún `nsubj` hermano que
comparar — ver `test_ldp_misc_gated_cubre_prodrop_sin_precedes_subject`
("Ayer, corrió", sin sujeto).

## 3. Fixture de doble AGX — Completeness ✓

"Se les prohibió la salida" (dativo "les" + "se" pasivo-reflejo, misma
cláusula, gold-style — el prompt lo pidió como versión mínima de la
oración real de AnCora). 2 entradas en `ls_data['agx']`, 2 nodos `AGX` en
el árbol (ambos hermanos del `NUC` con `PRED>V`):

```
Completeness: ✓ AGX✓×2
```

Antes de L4.5 (agx como dict único) esto habría reportado
`nodo AGX en el árbol pero sin agx en la LS` — falsa alarma, exactamente
el caso que motivó el §3.

## 4. EL de "Se venden casas" — actor Ø

```
formal : [do'(Ø, Ø)] CAUSE [do'(x2, [vender'(x2)])]
léxica : [do'(Ø, Ø)] CAUSE [do'(casas, [vender'(casas)])]
args   : x1:Ø,—,causante inespecificado; x2:casas,nsubj,Undergoer(paciente→PSA)
```

## 5. Path anticausativo — confirmación

**Ya daba `do'(Ø,Ø)` antes de L4.5, sin necesitar ajuste**: "el jarrón se
rompió" (verbo léxicamente causativo-anticausativo, `romper` en
`causative_lexicon.csv`) →

```
formal : [do'(Ø, Ø)] CAUSE [INGR broken'(x2)]
léxica : [do'(Ø, Ø)] CAUSE [INGR broken'(jarrón)]
```

El código NUEVO de L4.5 §4 (detección de `expl:pass`/`expl:impers` →
`args['x1']='Ø'`) cubre el hueco que SÍ existía: verbos NO
causativo-léxicos (`"Se venden casas"`, arriba) y sin sujeto en absoluto
(`"Se vive bien"` → antes disparaba pro-drop `3sg` espurio; ahora no
dispara pro-drop en absoluto, aunque con el parser Stanza en vivo de este
entorno "Se venden casas"/"Se vive bien" caen bajo `expl:pv`, no
`expl:pass`/`expl:impers` — mismo hallazgo ya documentado en
`CHECKPOINT_L4.md` §4, verificado que persiste; el código se validó contra
fixtures gold-style, no contra el parser en vivo, por diseño explícito del
prompt).

## 6. Las 5 dianas de §5 — salida completa + guardarraíl

| Oración | Clase | Nota de gate |
|---|---|---|
| Juan come | **Activity** | `gate=obj_desnudo→Activity` |
| Juan come manzanas | **Activity** | `gate=obj_desnudo→Activity` |
| Juan come manzanas siempre | **Activity** | `gate=obj_desnudo→Activity` |
| Juan se come las manzanas | **Active_Accomplishment** | `gate=obj_delimitado→AA` (G-AA se adelanta a G-se-aspectual; ambos son coherentes, ver nota abajo) |
| Juan come la manzana | **Active_Accomplishment** | `gate=obj_delimitado→AA` |

Ejemplo completo ("Juan se come las manzanas"):
```
formal : do'(x1, [comer'(x1, x2)]) & INGR consumed'(x2)
léxica : do'(Juan, [comer'(Juan, manzanas)]) & INGR consumed'(manzanas)
```

Nota sobre el orden de gates: la clase cruda del clasificador para esta
frase ya era `accomplishment` (pertenece al set de clases que G-AA
considera), así que G-AA dispara primero y dicta `active_accomplishment`;
el guard `verb_class != 'active_accomplishment'` en G-se-aspectual evita
una nota de gate duplicada. G-se-aspectual sigue siendo necesario como red
de seguridad independiente para frases donde el clasificador NO devuelva
`achievement`/`accomplishment` (fuera del set de clases de G-AA) pero SÍ
haya "se" aspectual + objeto delimitado.

**Guardarraíl confirmado** (sin regresión):
- `"Juan rompió el vaso"` → sigue **Achievement**
  (`[do'(Juan, Ø)] CAUSE [INGR broken'(vaso)]`, vía el path causativo
  léxico existente — G-AA nunca llega a evaluarse para esta oración porque
  el causativo léxico decide primero; y aunque llegara, la guarda de clase
  léxica de "romper"=Achievement en `VERB_CLASSES` lo bloquearía).
- Dianas históricas re-verificadas sin cambio de clase: "estudié tres
  horas anoche"→Activity, "Juan corrió cinco kilómetros"→
  Active_Accomplishment, "Juan corrió"→Activity, "corrió"→Activity.
- Ditransitiva no interferida: "Le da manzanas a María" sigue dictando su
  propia plantilla (`ls_data['ditransitiva'] is not None`) — estructuralmente
  imposible que los gates nuevos la toquen (la ditransitiva sobreescribe
  `verb_class` DESPUÉS de los gates en `map_sentence_to_ls`).

Todo lo anterior corrido y verificado con Stanza + roBERTa reales
(`aspect_classifier/test_telicidad_l4_5.py`, 4/4 tests `@slow` verdes).

## Higiene y validación

- Suites completas: **160 passed** (no-slow) + los `@slow` re-verificados
  sin regresión (`test_slow_l3_fijaciones_ancladas`,
  `test_slow_l4_completeness_end_to_end`,
  `test_slow_guard_frecuencia_postverbal_anclado_clause` —éste sigue
  saltando con el mismo motivo documentado en L4—,
  `test_slow_ls_integradas`, y los 4 nuevos de
  `test_telicidad_l4_5.py`).
- PUD **intocado** (no se volvió a correr, por orden explícita).
- No se creó commit (orden explícita de Julian).

## Pendientes que quedan fuera de esta mini-etapa (documentados, no implementados)

- Conciliación agx árbol↔LS (§1 de esta sección, el hallazgo dominante del
  desglose de completeness restante).
- Oraciones compuestas / `xcomp` encadenado (juntura-nexo RRG — fase
  posterior, aunque sea el 51% de fallos PUD).
- Mostrar operadores, bucle de corrección de usuario, línea Vector/help
  legible: L5 (Julian está decidiendo su UI).
- Impersonal refleja por animacidad ("Se acusó a Pedro" → sin PSA, verbo
  congelado 3sg); agente con "por" en pasivas con se como cadena causal
  secundaria: quedan como TODO en el código, sin implementar (fuera de
  alcance explícito).
- Reentrenamiento/recalibración del clasificador con el lote de oraciones
  en presente que Julian está curando en paralelo para
  `contextual_sentences.csv`: NO es parte de este prompt.
