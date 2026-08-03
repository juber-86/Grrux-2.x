# Tarea LA1: el linking algorithm explícito (macropapeles por AUH, PSA + concordancia, traza de 5 pasos, round-trip)

Proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python`. NO hacer commits.
ADVERTENCIA OOM de siempre. Sigue a CHECKPOINT_OPERATORS_2.md — **la EL ya es canónica** (solo
contenido léxico dentro, operadores ⟨ ⟩ fuera): esa era la precondición de esta etapa.

**PROHIBIDO:** `ud2rrg.py` completo, clasificador (predict/classifier/decision_tree/.joblib),
corroborador MLM, `contextual_sentences.csv`. PUD intocado. Editables: mapper y constructores
de EL (`build_ls`/`ditransitivas.py`/`componer_cause`), `completeness.py`, `display_grr.py`,
motor/servidor/GUI, glosario, config, tests. **Esta etapa es ADITIVA**: no cambia clases, ni
EL, ni golds — añade el análisis del linking encima. Con `linking.enabled: false` (config) →
ninguna clave nueva, salida byte-idéntica (test dedicado).

## Teoría (fig. 5.1 de Van Valin — resumen del sistema de linking; spec de Julian)

- **Jerarquía Actor-Padecedor (AUH)**, de mayor a menor rango:
  `arg. de DO > 1er arg. de do'(x,…) > 1er arg. de pred'(x,y) > 2º arg. de pred'(x,y) > arg. de estado pred'(x)`.
  **Actor** = el argumento de rango MÁS ALTO; **Undergoer** = el de rango MÁS BAJO (default).
- **M-transitividad** = número de macropapeles: transitivo=2, intransitivo=1, **atransitivo=0**
  (los impersonales tipo "llueve" — por fin con su nombre teórico).
- **PSA** (Argumento Sintáctico Privilegiado): en español (lengua acusativa), voz activa →
  Actor; pasiva perifrástica y pasiva refleja → Undergoer/Padecedor (González Vergara, ya
  implementado semánticamente); impersonal → SIN PSA (verbo congelado en 3sg). **El PSA rige
  la concordancia verbal** (persona/número).
- El algoritmo es **bidireccional**: sintaxis→semántica (comprensión — lo que gruxx ya hace) y
  semántica→sintaxis (producción, 5 pasos: EL → macropapeles → codificación PSA/caso/
  concordancia → plantilla sintáctica → asignación con AGX/PrCS/LDP). La Completeness
  Constraint rige ambas. Esta etapa NO genera oraciones: usa la dirección de producción como
  RE-DERIVACIÓN VERIFICADORA (round-trip).
- El dativo español es NMR (argumento central sin macropapel) — decisión ya tomada, no cambia.
- Ø (argumento inespecificado) NO puede recibir Actor → el de menor rango recibe Padecedor y
  asciende a PSA (ya es el comportamiento del se-pasivo; ahora se declara formalmente).

## §1. Representación ESTRUCTURADA de la EL (la base de todo)

NO parsear los strings de EL (frágil). Los constructores de EL YA SABEN qué posición ocupa
cada argumento al construir la cadena: que lo registren. Clave nueva `ls_estructura` en el
dict del mapper, generada por `build_ls`, `ditransitivas.construir_el` y `componer_cause`:

```python
[{'predicado': "do'",   'args': [{'texto': 'Juan',   'posicion': '1_do'}]},
 {'predicado': "have'", 'args': [{'texto': 'María',  'posicion': '1_pred_xy'},
                                 {'texto': 'flores', 'posicion': '2_pred_xy'}]}]
```

Posiciones válidas: `arg_de_DO | 1_do | 1_pred_xy | 2_pred_xy | arg_estado` (las 5 de la
fig. 5.1). Los Ø y los argumentos morfológicos ('3sg') se registran igual (con su marca). Los
wrappers de periferia y operadores NO entran (no son argumentos del evento). GUARDA DE
NOTACIÓN: usar posiciones nombradas y texto — NO profundizar la numeración x1/x2/x3 (reforma
x/y pendiente).

## §2. Módulo nuevo `aspect_classifier/linking.py` (puro)

1. `asignar_macropapeles(estructura, cfg) -> dict`: aplica la AUH (escala de 5 posiciones como
   CONSTANTE documentada citando fig. 5.1; validación opcional de coherencia contra
   `data/jerarquia_semantica_a_gramatical.xlsx` en un test, no en runtime). Actor = rango más
   alto NO-Ø; Undergoer = rango más bajo; dativo → NMR (excluido de la competencia de MR);
   M-transitividad = conteo de MR. Devuelve también la JUSTIFICACIÓN posicional de cada
   asignación ("Actor=Juan ← 1er arg. de do'").
2. `seleccionar_psa(macropapeles, voz) -> dict`: activa→Actor; pasiva (perifrástica o
   refleja)→Undergoer; impersonal/atransitivo→None. La voz ya la conoce el mapper
   (nsubj:pass/expl:pass/agx se_pasivo/impersonal).
3. `verificar_concordancia(psa, feats_verbo_finito) -> check`: persona/número del PSA vs verbo
   finito (OJO lección de OPERATORS: leer el FINITO, no el participio). Pro-drop: el
   actor_implicito viene de la morfología → concuerda por construcción (marcarlo así).
   Discrepancia → advertencia en Integridad (`⚠ concordancia: PSA 'casas' 3pl vs verbo
   'vende' 3sg`).
4. `traza_linking(...) -> list`: los 5 pasos de producción, legibles:
   - Paso 1: EL seleccionada (plantilla + clase aspectual + fuente léxico/clasificador).
   - Paso 2: macropapeles con justificación posicional + M-transitividad.
   - Paso 3: codificación — PSA elegido y por qué (voz), caso esperado (nominativo PSA,
     acusativo Undergoer no-PSA, dativo "a" para NMR), concordancia esperada.
   - Paso 4: plantilla sintáctica — cuántas posiciones core exige (argumentos − satisfechos
     morfológicamente) + posiciones especiales requeridas (AGX por clíticos, LDP/PrCS si hay
     destacados/interrogativos).
   - Paso 5: asignación — qué constituyente real recibió cada elemento (reutilizar las
     correspondencias que `completeness` ya calcula).
5. **Round-trip** `expectativas_sintacticas(estructura, macropapeles, psa, agx, …) -> checks`:
   desde la EL, re-derivar qué DEBERÍA haber en el árbol (nº de argumentos core, PSA con su
   concordancia, nodos AGX, LDP/PrCS) y comparar contra el árbol real. Los checks se INTEGRAN
   al informe de Integridad existente (mismo dict estructurado, estados nuevos con prefijo
   `linking_`) — es la Completeness Constraint operando en la dirección de producción.

## §3. Reconciliación con los macropapeles existentes

`args_map` ya trae Actor/Undergoer/NMR asignados por vía deprel/plantilla. La asignación AUH
debe COINCIDIR. Comparar en cada análisis: si coinciden (esperado), `args_map` gana la cita
posicional (`Actor(Efectuador ← 1er arg. de do')`); si NO coinciden → advertencia
`linking_discrepancia` en Integridad + fila en un log `data/linking_discrepancias.csv` — NO
cambiar el gold ni la asignación vieja en silencio: el checkpoint reporta las discrepancias
encontradas sobre la batería para decisión de Julian (probablemente indican bugs de una de
las dos vías).

## §4. Salida

- Terminal: línea nueva compacta
  `Linking: Actor=Juan (1er arg. de do') · Undergoer=flores (2º arg. de have') · María=NMR ·
  M-transitivo=2 · PSA=Actor · concordancia 3sg ✓`
  y la TRAZA completa de 5 pasos con `--verbose`.
- GUI: panel/pestaña "Linking" con los 5 pasos (numerados, legibles — es la feature
  pedagógica: el algoritmo de la RRG mostrado en vivo); hover de términos → glosario;
  los checks `linking_*` aparecen en la línea de Integridad como los demás.
- Glosario: entradas nuevas/actualizadas — jerarquía Actor-Padecedor (AUH), M-transitividad,
  atransitivo, caso (nominativo/acusativo/dativo), traza del linking, producción vs
  comprensión, y las 5 posiciones de la escala.

## §5. Tests + validación

- Fríos (estructuras a mano): "Juan le dio flores a María" → Actor=Juan(1_do),
  Undergoer=flores(2_pred_xy), María=NMR, M=2, PSA=Actor, concordancia dio(3sg)↔Juan ✓;
  "Se venden casas" → Ø bloqueado para Actor, casas=Undergoer=PSA, concordancia
  venden(3pl)↔casas ✓; **"Se vende casas"** (fixture) → ⚠ concordancia (el warning demo);
  "llueve" → M=0 atransitivo, PSA=None, sin warnings; "El pastel fue comido por Juan" →
  PSA=Undergoer(pastel), Juan=Actor no-PSA; "Juan sabe la respuesta" → Actor=Juan(1_pred_xy),
  Undergoer=respuesta(2_pred_xy), M=2 (estado M-transitivo; la doble ruta psych
  Actor/Undergoer de la jerarquía queda como TODO documentado); "Juan corrió" → M=1;
  round-trip: nº args esperados vs árbol, AGX esperado presente/ausente.
- @slow: 3-4 oraciones end-to-end con la línea Linking y la traza; batería completa de dianas
  SIN regresión (etapa aditiva: 0 cambios de clase/EL/gold); `linking.enabled: false` →
  byte-idéntico; los 3 fallos conocidos de clase aspectual siguen documentados (no son de
  esta etapa).
- Suites completas verdes.

## CHECKPOINT — PARAR aquí

Informe: (1) traza completa de 5 pasos de 2-3 oraciones (incluida la ditransitiva y el
se-pasivo); (2) tabla de reconciliación §3 sobre la batería (discrepancias encontradas, si
las hay, con diagnóstico); (3) el warning de concordancia real demostrado; (4) captura GUI del
panel Linking; (5) suites. Pendientes que esta etapa deja listos para después: doble ruta
psych de la jerarquía, reforma de notación x/y, dirección de producción generativa real
(generar oración desde EL — futuro lejano).
