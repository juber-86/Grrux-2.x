# Tarea: Fase LINKING sintaxis↔semántica — Etapas L0 (baseline), L1 (wrappers en la LS) y L2 (canal MISC)

Proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python` (3.10; torch,
transformers<5, stanza, sklearn, pyyaml). Entry point del usuario: `python3 gruxx_ai1.py`.

**PROHIBIDO en este prompt:**
- `ud2rrg.py` NO se toca (su capa española + nodo AGX en el árbol son la etapa L3, en el
  SIGUIENTE prompt tras el checkpoint).
- `gruxx_ai1.py` intacto SALVO una única excepción quirúrgica autorizada por Julian:
  `inyectar_metadata_rrg()` (líneas ~107-125) en la etapa L2. NADA del render ni del flujo
  interactivo.
- Clasificador (`predict.py`, `classifier.py`, `decision_tree.py`), corroborador MLM
  (`pruebas_clase_aspectual.py`), `pruebas_estructurales.py`, los `.joblib` de `models/` y
  `data/contextual_sentences.csv`: intactos.

## Decisiones de diseño YA TOMADAS por Julian (no re-litigar)

1. **Arquitectura híbrida**: la Etapa 1 (`aspect_classifier/nucleo_periferia.py`) es la ÚNICA
   fuente de verdad core/periferia. Sus veredictos viajarán DENTRO del `.conllu` (columna MISC);
   `ud2rrg.py` (etapa L3 futura) solo aprenderá a leerlos. Nunca duplicar la lógica de periferia
   en dos sitios.
2. **Clíticos de OI = concordancia, no argumentos (nodo AGX)**: en RRG el clítico dativo es un
   morfema de concordancia enlazado a un nodo AGX dependiente directo del NÚCLEO (hermano de
   PRED). En el doblado ("Juan le dio un beso a María") hay UN solo argumento semántico con doble
   materialización: rasgos como "le" en AGX + sintagma pleno "a María" en posición argumental.
   Si el clítico va solo ("Juan le dio un beso"), el argumento se satisface morfológicamente
   (Completeness Constraint). ⇒ La LS lleva SIEMPRE un solo x para el receptor.
3. **Wrappers de periferia en la LS** (inventario §L1; metalenguaje en inglés): locativos
   espaciales con `be-in'/be-at'...` (be- SOLO para locación espacial); temporales/duración como
   preposiciones predicativas bivalentes `prep'(x, [LS])` — `during'`, `for'`, `before'`,
   `after'`; adverbios temporales simples como predicados monovalentes `yesterday'([LS])`.
   Ejemplos canónicos de Julian: "Juan rezó durante la clase" → `[during'(clase, [pray'(Juan)])]`;
   "Pedro corrió por tres horas" → `[for'(tres horas, [do'(Pedro, [run'(Pedro)])])]`.
4. **El modo/modalidad es OPERADOR (<MOD>/<EST>/<FI>), jamás wrapper — y queda POSPUESTO** hasta
   el nivel pragmático. No implementar nada de modalidad.
5. **KPI de la fase**: tasa de coincidencia periferia sintaxis↔semántica + tasa de
   dummy-trees/fallos de ud2rrg, medidas sobre AnCora dev ANTES (este prompt, L0) y DESPUÉS (L4,
   prompt futuro).

## NOTAS DE AUDITORÍA — trabajo ya hecho (2026-07-09, sesión de diseño); retomar desde aquí

**1. Convención del doblado en los treebanks gold** (script desechable: iterar tokens PRON con
forma `le/les`; buscar hermano nominal bajo el mismo head introducido por `case` con lema `a`;
contar deprels):
- **AnCora dev** (`treebanks/spanish/UD_Spanish-AnCora/es_ancora-ud-dev.conllu`): 135 clíticos
  le/les → deprel `{obl:arg: 109, expl: 26}`; 26 casos con doblado, y el sintagma pleno doblado
  sale `{obl:arg: 24, obl: 2}`. **Convención gold AnCora: clítico DOBLADO = `expl`
  (≈ el análisis AGX de la RRG), sintagma pleno = `obl:arg`; clítico SOLO = `obl:arg`.**
- **GSD dev**: inconsistente (clítico `{obl:arg: 54, obj: 5, nsubj: 2, …, expl: 1}`; en el
  doblado AMBOS quedan `obl:arg`). No fiarse de GSD para clíticos.

**2. Stanza en producción NO reproduce el `expl` de AnCora.** Comando corrido (pipeline es del
proyecto, `tokenize,mwt,pos,lemma,depparse`):
- "Le compró un regalo a María." → `Le`=**obl:arg**(head=compró), `María`=**obl:arg**(head=compró)
  — DOS `obl:arg` hermanos, sin `expl`. Ídem "Juan le dio un beso a María."
- "Le dije la verdad." → `Le`=obl:arg único.
⇒ **Consecuencia de diseño**: la detección de doblado NO puede apoyarse en `expl`; hay que
detectarla estructuralmente: PRON átono dativo (`le/les`; considerar `me/te/nos/os` con cuidado)
+ hermano nominal bajo el mismo verbo con `case` = `a` → sintagma pleno = argumento x_n; clítico
= marca de concordancia (clave `agx`), NO argumento. Chequeo blando de concordancia de número
(le↔Sing, les↔Plur) cuando los feats estén disponibles; si no matchea, reportar y no fusionar.

**3. VERIFICACIÓN PENDIENTE (quedó interrumpida — PRIMERA acción de L0):** cómo enruta HOY
`analizar_roles` el deprel `obl:arg`. No está ni en los deprels de core ni en
`PERIFERIA_DEPRELS = {obl, advmod, obl:tmod, nmod:tmod, obl:mod, advcl}` — sospecha: el dativo
cae a periferia (si el dispatch usa startswith('obl')) o se pierde. Snippet listo para correr:

```python
from aspect_classifier.nucleo_periferia import analizar_roles
toks = [
 {'id':1,'text':'Le','lemma':'él','upos':'PRON','deprel':'obl:arg','head':2,'feats':'Case=Dat|Number=Sing|Person=3'},
 {'id':2,'text':'compró','lemma':'comprar','upos':'VERB','deprel':'root','head':0,'feats':'Number=Sing|Person=3|Tense=Past'},
 {'id':3,'text':'un','lemma':'uno','upos':'DET','deprel':'det','head':4,'feats':''},
 {'id':4,'text':'regalo','lemma':'regalo','upos':'NOUN','deprel':'obj','head':2,'feats':''},
 {'id':5,'text':'a','lemma':'a','upos':'ADP','deprel':'case','head':6,'feats':''},
 {'id':6,'text':'María','lemma':'María','upos':'PROPN','deprel':'obl:arg','head':2,'feats':''},
]
r = analizar_roles(toks, 2, {})
print('CORE:', [(c['text'], c['deprel'], c.get('macropapel')) for c in r['core']])
print('PERIFERIA:', [(p['text'], p['deprel'], p['tipo']) for p in r['periferia']])
```

Documentar el resultado en el informe del checkpoint (es parte del baseline: "así estaba antes").

## L0 — Baseline cuantificado (sin tocar código de producción)

Script nuevo `aspect_classifier/kpi_linking.py` (`python -m aspect_classifier.kpi_linking
[--n 300] [--treebank ancora-dev]`), sobre el gold `.conllu` DIRECTO (sin Stanza — así se aísla
el conversor del parser):

1. **Tasa de fallos de ud2rrg**: correr `ud2rrg.py` (mismo subprocess que usa `gruxx_ai1.py`:
   `[sys.executable, 'ud2rrg.py', conllu, 'es']`) sobre la muestra. ANTES de escribir el
   detector, inspeccionar a mano cómo luce un dummy-tree/fallo en el stdout real (la spec dice
   que inyecta un "árbol plano falso"; buscar también "subtree not handled" que ya maneja
   `_dividir_arboles_ud2rrg`). Métricas: % crash, % dummy/plano, % OK.
2. **Tasa de desacuerdo de periferia**: para cada oración, correr `analizar_roles` (solo Etapa 1,
   NO hace falta BERTIN) y comparar contra el árbol bracketed: tokens que Etapa 1 marca como
   periferia pero que en el árbol cuelgan de CORE/NUC sin nodo de periferia intermedio (heurística
   de parseo del bracketed: documentarla; si el formato de salida hace esto poco fiable, medir la
   variante alcanzable y anotar la limitación).
3. **Contadores**: doblados detectados (patrón de la nota 2), `obl:arg` totales, periferia por
   tipo.
4. Guardar `data/kpi_linking_baseline.json` (con fecha, muestra, métricas) + resumen legible por
   stdout. **Este es el ANTES del KPI de la fase.**

## L1 — Wrappers de periferia en la LS + fix del dativo (lado semántico)

### 1a. Fix `obl:arg` y doblado en `nucleo_periferia.py`

- `obl:arg` → CORE (argumento; macropapel `NMR(dativo)` — no-macroargumento receptor).
- Detección de doblado (nota de auditoría 2): clítico átono dativo + hermano `obl:arg`/`iobj`
  nominal con case `a` → el sintagma pleno es el argumento (con su x_n); el clítico NO entra a
  core ni a periferia: va a clave nueva `agx` del dict de retorno
  (`{'clitico': 'le', 'rasgos': '3sg-dat', 'doblado': True/False, 'arg_id': <id del pleno o None>}`).
- Clítico dativo SOLO (sin sintagma pleno) → argumento realizado morfológicamente: entra a core
  con etiqueta de rasgos (`'3sg'`, estilo `actor_implicito`) y `agx.doblado=False`.
- `iobj` (cuando Stanza lo produzca) sigue siendo core; si el `iobj` ES el clítico y hay pleno
  doblado, misma fusión.
- Tests fríos en `test_nucleo_periferia.py` (mantener 7/7 previos): los 3 escenarios de la
  auditoría ("Le compró un regalo a María" → x1 implícito, x2 regalo, x3 María, agx=le doblado;
  "Le dije la verdad" → x3='3sg' morfológico; sin clítico → sin agx).

### 1b. Módulo nuevo `aspect_classifier/wrappers_ls.py` (funciones puras)

`componer_wrappers(ls_formal, ls_lexical, periferia, cfg) -> (formal, lexical, aplicados)`.
Inventario (BORRADOR aprobado por Julian para implementar; las TABLAS van a `config.yaml`,
sección `wrappers_ls`, para que Julian las edite sin tocar código):

- **Locativos espaciales** (periferia tipo `locativo`), bivalentes `be-X'(x, [LS])` con x =
  núcleo del sintagma: `en→be-in'`, `sobre/encima de→be-on'`, `bajo/debajo de→be-under'`,
  `entre→be-between'`, `cerca de→be-near'`, `delante de/ante→be-in-front-of'`,
  `detrás de/tras→be-behind'`, `junto a→be-beside'`; DEFAULT locativo → `be-at'`.
- **Temporales bivalentes** `prep'(x, [LS])`: `durante` → **regla semántica, no léxica**: si el
  complemento es CANTIDAD de tiempo (núcleo en `sustantivos_duracion` de `pruebas_estructurales`
  o con nummod: "tres horas") → `for'`; si es evento/intervalo nombrado ("la clase", "la
  película") → `during'`. `por`+duración → `for'`; `antes de→before'`; `después de→after'`;
  `hasta→until'`; `desde→since'`; `a`/`en` + punto temporal ("a las tres", "en enero") → `at'`;
  duración desnuda en periferia temporal sin case ("tres horas", "toda la noche") → `for'`.
- **Adverbios temporales monovalentes** `adv'([LS])`: `ayer→yesterday'`, `hoy→today'`,
  `mañana(ADV)→tomorrow'`, `anoche→last.night'`, `ahora→now'`; `ya/todavía` → NO wrapper (son
  aspectuales, futuros operadores — dejarlos en periferia listada); DEFAULT adverbio temporal sin
  primitivo inglés claro → lema español + `'` (`anteayer'`).
- **Manera** (periferia tipo `modo`, advmod en -mente): PROVISIONAL, monovalente con el lema
  (`lentamente'([LS])`) y marcado en el informe — el scope fino (sobre el subevento de actividad)
  queda para revisión de Julian. NO confundir con modalidad (operadores, pospuestos).
- **Frecuencia** (siempre, nunca, a menudo, todos los días): NO implementar todavía — dejar en
  periferia listada como hoy y CONTARLOS en el informe (decisión pendiente de Julian).
- **NUNCA envolver**: Meta/origen de verbos de movimiento y `obl:agent` (son CORE, ya resuelto
  por Etapa 1); beneficiario/instrumento/compañía/causa (fase posterior; siguen en periferia
  listada).
- **Anidamiento** con múltiples wrappers, de dentro hacia fuera: locativo → PP temporal →
  adverbio temporal. Ej.: "Ayer Juan corrió tres horas en el parque" →
  `yesterday'(for'(tres horas, be-in'(parque, [do'(Juan, [correr'(Juan)])])))`.

### 1c. Integración en el mapper (`rrg_ls_mapper.py`)

- Tras `build_ls`/`componer_cause`: si `config.wrappers_ls.enabled` (default `true`), envolver
  formal y léxica con `componer_wrappers`. El dict de retorno gana `wrappers` (lista aplicada,
  con tipo y trigger) y `agx` (de 1a). `aspect_note` gana un segmento compacto solo si aplicó
  algo (`wrappers: for'(tres horas)·be-in'(parque)`).
- Con `enabled: false` → salida byte-idéntica a hoy (verificar programáticamente).

### 1d. Tests y CHECKPOINT de dianas

- Tests fríos de `wrappers_ls` (tabla completa: durante cantidad-vs-evento, default `be-at'`,
  monovalentes, anidamiento, frecuencia NO envuelve, ya/todavía NO envuelven).
- **OJO — las 15 dianas comparan la LS gold y los wrappers CAMBIAN la LS esperada de varias**
  ("estudié tres horas anoche" ganará `for'` y `last.night'`). **NO editar el gold en silencio**:
  generar un informe con la LS vieja → LS nueva propuesta por diana y PARAR en el checkpoint para
  que Julian apruebe el gold nuevo. Mientras tanto la suite puede correr con `enabled: false`
  para verificar no-regresión del resto.

## L2 — Canal MISC en el `.conllu`

- Volcar los veredictos del mapper a la columna MISC por token (formato UD estándar
  `Clave=Valor|Clave=Valor`, PRESERVANDO el MISC existente):
  `RRGRole=CoreArg|RRGVar=x2`, `RRGRole=Periphery|RRGType=temporal|RRGWrap=for`,
  `RRGRole=AGX`, `RRGRole=Impersonal`, etc. Diseñar el vocabulario mínimo y documentarlo en un
  comentario del módulo (será el CONTRATO que la capa `es` de ud2rrg leerá en L3).
- **Único toque a `gruxx_ai1.py`**: `inyectar_metadata_rrg()` escribe estas marcas leyéndolas del
  dict del mapper (que ya viaja como `ls_data_por_oracion`). El render y el flujo no se tocan.
- Verificar que `ud2rrg.py` NO se rompe con MISC poblado (hoy lo ignora): correr las dianas
  end-to-end y comparar árboles antes/después (deben ser idénticos).
- Test round-trip: escribir conllu → releer → marcas correctas por token.

## CHECKPOINT FINAL — PARAR aquí (no hay L3/L4 en este prompt)

Entregar a Julian un informe único con: (1) resultado de la verificación `obl:arg` pre-fix,
(2) baseline KPI de L0 (números + limitaciones del parser de bracketed), (3) tabla LS vieja→nueva
de las dianas con wrappers para aprobar el gold, (4) un `.conllu` de ejemplo con MISC poblado,
(5) decisiones pendientes acumuladas (frecuencia, scope de manera, gold nuevo). L3 (capa `es` en
`ud2rrg.py`: leer MISC → `peri()`, clíticos españoles → nodo AGX bajo NÚCLEO) y L4 (checker de
completeness + KPI después) llegan en el siguiente prompt tras la revisión de Julian.

## Restricciones y aceptación

- Suites que deben quedar verdes: `test_nucleo_periferia` (ampliada), `test_pruebas_estructurales`
  25/25, `test_causatividad` 9/9, `test_complejo --slow`, `test_pruebas_aspectuales` 11/11,
  `test_fase2_contextual --slow` (con `wrappers_ls.enabled: false` hasta que Julian apruebe el
  gold nuevo), + tests nuevos de `wrappers_ls` y `kpi_linking`.
- `wrappers_ls.enabled: false` → byte-idéntico (verificado programáticamente).
- Un solo x por argumento doblado; el clítico jamás genera variable propia.
- Baseline KPI guardado con fecha en `data/kpi_linking_baseline.json`.
- Prohibiciones de cabecera respetadas (verificar por mtime al cerrar).
