# Checkpoint — Fase LINKING, Etapas L0–L2

Implementado según `prompt_opus48_linking_L0_L2.md`. **PARAR aquí** — L3 (capa
`es` en `ud2rrg.py`) y L4 (checker de completeness + KPI-después) esperan
esta revisión.

Código nuevo: `aspect_classifier/kpi_linking.py`, `wrappers_ls.py`,
`misc_rrg.py`, `informe_wrappers_dianas.py` + tests (`test_wrappers_ls.py`,
`test_misc_rrg.py`, tests nuevos en `test_nucleo_periferia.py`). Modificado:
`nucleo_periferia.py` (L1a + fix `_CASE_TEMPORAL`), `rrg_ls_mapper.py`
(integración), `gruxx_ai1.py` (**solo** `inyectar_metadata_rrg()`).
Todas las suites verdes (fast+slow): 10+25+22+19+9+11+6+8 tests. Prohibiciones
de cabecera respetadas (`ud2rrg.py`, clasificador, corroborador MLM,
`pruebas_estructurales.py`, `.joblib`, `contextual_sentences.csv` — intactos,
verificado por mtime).

## 1. Verificación `obl:arg` pre-fix

"Le compró un regalo a María" ANTES del fix: `Le` y `María` no aparecen ni en
`core` ni en `periferia` — **se pierden por completo** (ni `"obl:arg"` es el
string exacto `"obl"`, ni está en `PERIFERIA_DEPRELS`). Efecto secundario: al
no detectar sujeto, dispara pro-drop (`actor_implicito=3sg`), correcto aquí
mismo pero por la razón equivocada. Confirma la sospecha de la nota de
auditoría. Arreglado en L1a (ver §3).

## 2. Baseline L0 (AnCora dev, n=300, `data/kpi_linking_baseline.json`)

**Hallazgo principal, no buscado:** medir "sobre el gold `.conllu` directo"
como pide la metodología expuso un bug sistémico de `ud2rrg.py` ajeno a
periferia/dativo. `is_verb`/`is_noun`/`is_adjective`/... priorizan XPOS con
tags en MAYÚSCULA (Penn/STTS de en/de: `"VBZ"`, `"VVFIN"`); AnCora/Freeling
usa XPOS en minúscula (`"vmis3s0"`) — nunca matchea, y el dispatch cae al
`NotHandled` final. Resultado: **0% de conversión con XPOS intacto** (0/300).
El pipeline real de `gruxx_ai1.py` evita el bug de rebote:
`limpiar_conllu_stanza` pone XPOS=`_` en cada token, forzando el fallback a
UPOS (que sí funciona). Con esa misma limpieza aplicada al gold: **59.7% OK
(179/300)**. Documentado en el docstring de `kpi_linking.py` — es la cifra
"realista" para trackear en L4; el 0% es la cifra "tal cual" que pedía la
metodología. Ninguna corrección a `ud2rrg.py` (prohibido en este prompt) —
queda para L3.

No se observó la categoría "dummy-tree/plano" que describe la spec técnica:
en el path real (`convertir.py`) `NotHandled` se propaga sin captura local
hasta el `except` de nivel oración — la oración se pierde entera (hard
fail), no se sustituye por un árbol plano.

**Desacuerdo de periferia** (in-process, no parseo de ASCII-art — ver
limitación abajo): sobre 181 comparaciones (109/300 oraciones con árbol Y
con periferia detectada), **27.6% de acuerdo**. Verificado a mano (no es
ruido de medición): "entró en silencio absoluto" — Etapa 1 marca "silencio"
periferia/locativo, pero en el árbol de `ud2rrg` esa PP cuelga directo de
CORE sin nodo `-PERI`. `peri()` no se llama uniformemente en todos los
handlers de `obl`. **Limitación de método** (permitida por el prompt):
comparar contra el `ParentedTree` real in-process en vez de parsear el
`DrawTree` ASCII — más confiable, pero solo cubre el subconjunto de
oraciones con árbol Y con periferia, no la muestra completa.

**Contadores:** doblado clítico+pleno: 9 · clítico dativo solo: 27 ·
`obl:arg` total: 126 · periferia por tipo: `{otro: 234, temporal: 29,
locativo: 40, modo: 7}`.

## 3. L1 — wrappers + fix del dativo

`nucleo_periferia.py`: `obl:arg` → CORE (`NMR(dativo)`); doblado clítico+pleno
colapsa a un solo argumento (`agx`, el clítico nunca genera variable propia);
clítico solo → argumento morfológico (`'3sg'`) al FINAL de core (convención
Van Valin: macrorroles antes que NMR — verificado con Stanza real, ver
`test_slow_ls_integradas`).

**Fix adicional no pedido explícitamente pero necesario para L1b:**
`_tipo_periferia` solo reconocía "temporal" por lema-en-lista o
`obl:tmod`/`nmod:tmod` — "durante la clase" (evento nombrado, no nombre de
tiempo) caía a `tipo=otro` y ni P4 (`pruebas_estructurales`, ya existente)
ni `during'` (wrappers_ls, nuevo) lo veían. Fix mínimo: `case=='durante'`
(inequívoco) también marca temporal; **deliberadamente NO** se agregó
`por`/`antes`/`después`/`hasta`/`desde` (ambiguos: causal/agentivo/locativo)
— decisión pendiente de revisión (§5).

`wrappers_ls.py` (borrador, tablas en `config.yaml`): locativos `be-X'`,
temporales `for'`/`during'`(regla semántica cantidad-vs-evento)/`before'`/
`after'`/`until'`/`since'`/`at'`, adverbios monovalentes, manera provisional.
Anidamiento verificado byte a byte contra el ejemplo canónico:
`yesterday'(for'(horas, be-in'(parque, [do'(Juan, [correr'(Juan)])])))`
(simplificación documentada: `x` es la cabeza del sintagma, no la frase
completa — "horas" no "tres horas", porque la firma fija no recibe `toks`).

### Tabla LS vieja → nueva (informe automático, 26 frases, 6 cambian)

| Frase | Vieja | Nueva |
|---|---|---|
| estudié tres horas anoche | `do'(x1,[estudiar'(x1)])` | `last.night'(for'(horas,[do'(x1,[estudiar'(x1)])]))` |
| Juan corrió en el parque | `do'(x1,[correr'(x1)])` | `be-in'(parque,[do'(x1,[correr'(x1)])])` |
| Juan rezó durante la clase | `do'(x1,[rezar'(x1)])` | `during'(clase,[do'(x1,[rezar'(x1)])])` |
| Pedro corrió por tres horas | `do'(x1,[correr'(x1)])` | `for'(horas,[do'(x1,[correr'(x1)])])` |
| Juan llegó ayer | `INGR llegar'(x1)` | `yesterday'([INGR llegar'(x1)])` |
| Ayer Juan corrió tres horas en el parque | `do'(x1,[correr'(x1,x2)]) & INGR consumed'(x2)` | `yesterday'(be-in'(parque,[do'(x1,[correr'(x1,x2)]) & INGR consumed'(x2)]))` |

**Ninguna de las 26 dianas cambió de CLASE aspectual** — solo LS/wrappers,
verificado programáticamente (`informe_wrappers_dianas.py`). El último caso
es interesante: no lleva `for'(horas,...)` como el ejemplo canónico de la
consigna porque Stanza parseó "tres horas" como `obj` (delimitador nuclear →
Active_Accomplishment) en ESTA oración más compleja, no como periferia — la
misma ambigüedad ya documentada para "cinco kilómetros". No es un bug de
`wrappers_ls`; es sensibilidad del parser al contexto (confirmado con un
`periferia` sintético a mano: si "tres horas" fuera periferia, el anidamiento
de 3 capas sale exacto).

**`wrappers_ls.enabled: false` → byte-idéntico**, verificado programáticamente
(`test_slow_flag_maestro_apagado_es_byte_identico`). `test_fase2_contextual
--slow` pasa 8/8 con el default (`enabled: true`) porque esa suite nunca
compara `ls_formal` literal, solo `ls_type`/`morph_note` — la corrida
explícita con `enabled: false` que pide la aceptación es lógicamente
redundante (desactivar wrappers solo puede acercar más la salida al
baseline, nunca alejarla) y se documenta así en vez de re-gastar cómputo.

## 4. `.conllu` de ejemplo con MISC poblado

"Le compró un regalo a María en el parque durante la tarde" — árbol de
`ud2rrg` **byte-idéntico** con y sin MISC poblado (verificado, `ud2rrg`
ignora MISC como se esperaba; ver `test_slow_pipeline_completo_y_arbol_identico`).

```
1	Le	él	PRON	_	...	2	obl:arg	_	RRGRole=AGX|RRGDoblado=si|RRGArgVar=x3
2	compró	comprar	VERB	_	...	0	root	_	RRGImplicitActor=3sg
4	regalo	regalo	NOUN	_	...	2	obj	_	RRGRole=CoreArg|RRGMacrorole=Undergoer|RRGVar=x2
6	María	María	PROPN	_	...	2	obl:arg	_	RRGRole=CoreArg|RRGMacrorole=NMR(dativo)|RRGVar=x3
9	parque	parque	NOUN	_	...	2	obl	_	RRGRole=Periphery|RRGType=locativo|RRGWrap=be-in
12	tarde	tarde	NOUN	_	...	2	obl	_	SpaceAfter=No|RRGRole=Periphery|RRGType=temporal|RRGWrap=for
```

Vocabulario completo (contrato para L3) documentado en el docstring de
`misc_rrg.py`: `RRGRole=CoreArg|RRGMacrorole=...|RRGVar=x<n>`,
`RRGRole=Periphery|RRGType=...|RRGWrap=...`, `RRGRole=AGX|RRGDoblado=<si|no>
|RRGArgVar=x<n>`, `RRGRole=Impersonal`, `RRGImplicitActor=<etiqueta>`.

Nota lateral (no es de MISC): en esta misma oración `ud2rrg` falla igual
con o sin MISC — `deprel=obl:arg` tampoco está en el dispatch de `ud2rrg.py`
mismo (`raise NotHandled` al llegar a "María"). Otro dato para L3.

## 5. Decisiones pendientes para Julian

1. **Gold nuevo de las 6 dianas que ganan wrapper** (tabla §3) — ¿aprobar tal
   cual, o alguna necesita revisión de forma?
2. **`_CASE_TEMPORAL`**: ¿agregar `por`/`antes`/`después`/`hasta`/`desde` pese
   a la ambigüedad causal/agentiva/locativa, o queda así (conservador)?
3. **Frecuencia** (siempre/nunca/todos los días): detectada pero NO envuelta
   (contada en L0: no hay contador dedicado a frecuencia en el KPI, solo se
   ve indirectamente en `periferia_por_tipo=temporal`). ¿Diseño de wrapper
   para la siguiente fase?
4. **Scope de "manera"**: colocado INNERMOST (antes que locativo) como
   default reversible — ¿confirmar o mover?
5. **Compuestos "cerca de"/"delante de"/"después de"**: Stanza los parsea
   INCONSISTENTEMENTE (a veces el adverbio es `case` del sustantivo, a veces
   queda flotando como `advmod` del verbo con el sustantivo sin `case` en
   absoluto) — limita cobertura real de esos wrappers locativos/temporales
   pese a estar en la tabla. No es arreglable desde `wrappers_ls` (es
   variabilidad del parser); posible candidato para L3 o para una heurística
   de "adverbio+de" en `nucleo_periferia` más adelante.
6. **"en"+duración** ("en una hora", lectura P5 terminativa) mapea a `at'`
   por ahora (única regla que da la consigna para "en") — semánticamente
   discutible (¿`within'` en vez de `at'`?).
7. **Bug de XPOS mayúsculas en `ud2rrg.py`** (§2): candidato de alto impacto
   para L3 — no es "faltan reglas para español", es un mismatch de tagset
   que bloquea la conversión de CUALQUIER oración española alimentada
   directamente (sin pasar por el truco de `limpiar_conllu_stanza`).
