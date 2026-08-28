# Tarea OPERATORS: operadores en la Estructura Lógica (notación Van Valin ⟨ ⟩) + proyección espejo en la GUI

**Plan en dos sub-prompts (entendido con Julian):** ESTE prompt implementa los operadores
(detección, EL envuelta, GUI, glosario) y deja las interfaces listas; un SEGUNDO sub-prompt
(`prompt_OPERATORS_2.md`, futuro) añadirá la "corrección de operadores" al bucle de corrección.
AQUÍ NO se implementa nada del bucle — solo TODOs en los puntos de enganche. Primero que los
operadores funcionen; luego se vuelven corregibles.

Proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python`. NO hacer commits.
ADVERTENCIA OOM de siempre: nada de suites --slow con instancias de gruxx/GUI abiertas.

**PROHIBIDO:** clasificador (predict/classifier/decision_tree/.joblib), corroborador MLM,
`contextual_sentences.csv`, y **`ud2rrg.py` COMPLETO** — los operadores NO tocan el árbol de
constituyentes: son una proyección aparte que se representa en la EL (y opcionalmente en la
GUI). `gruxx_ai1.py` y la GUI editables donde se indica.

## Teoría (Van Valin — la spec exacta de Julian)

Los operadores (tiempo, aspecto, modalidad, fuerza ilocutiva…) son semánticamente complejos y
NO se les da semántica sustantiva: se les da un LUGAR en la representación, indicando su
alcance sobre la EL. Notación: versalitas dentro de **corchetes angulares ⟨ ⟩** (caracteres
U+27E8/U+27E9 — NO usar `<` `>`). Esquema general de scope, de fuera hacia dentro (2.25):

```
⟨IF … ⟨EVID … ⟨TNS … ⟨STA … ⟨NEG … ⟨MOD … ⟨EVQ … ⟨DIR … ⟨ASP … ⟨LS⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩
```

Los operadores SIN especificación SE OMITEN de la representación. Ejemplo canónico (2.26),
"Has Kim been crying?":

```
⟨IF INT ⟨TNS PRES ⟨ASP PERF PROG ⟨do'(Kim, [cry'(Kim)])⟩⟩⟩⟩
```

Estratos (para el dict y la futura proyección espejo): nucleares = ASP, NEG nuclear, DIR;
centrales = MOD (deóntica), EVQ, NEG interna; clausulares = STA (epistémica), TNS, EVID, IF.
Abreviaturas y valores EN INGLÉS Y VERSALITAS (decisión de Julian, notación del libro).

## Qué detectar en español (todo desde señales que el pipeline YA tiene o son triviales)

| Operador | Fuente | Valores |
|---|---|---|
| **IF** | puntuación ¿?/¡! + Mood del root + interrogativos wh | `DEC` (default, SÍ se muestra), `INT`, `IMP` |
| **TNS** | feats `Tense` del root/aux finito | `PAST` (pretérito e imperfecto), `PRES`, `FUT` |
| **ASP** | `detect_aux_aspect` (haber→`PERF`, estar+ger→`PROG`, combinables: "ha estado llorando"→`PERF PROG`) + feats imperfecto→`IMPF` | `PERF`, `PROG`, `IMPF` (combinables) |
| **NEG** | "no" advmod del verbo | `NEG` (sin subtipo nuclear/interna por ahora — TODO) |
| **MOD** | perífrasis modales deónticas: deber+inf→`OBLG`, poder+inf→`ABIL`, tener que+inf→`OBLG` (verificar cómo parsea Stanza cada perífrasis ANTES de codificar el patrón; ser conservador y loguear los no cubiertos) | `OBLG`, `ABIL` |
| **STA** | Mood=Sub del root → `IRR`; condicional → `IRR`; adverbios epistémicos (quizá, tal vez, probablemente, seguramente — lista en config) → `IRR` (o `REAL` explícito si el adverbio es asertivo; default REAL se omite) | `IRR` |
| EVID, EVQ, DIR | NO implementar (español no los gramaticaliza como los persigue VV) — omitidos siempre; dejar el hueco en el orden de scope documentado | — |

Notas: `ya/todavía` NO son operadores todavía (TODO heredado, no tocar). El imperfecto es
TNS PAST **+** ASP IMPF (dos operadores de un solo feat).

## Implementación

1. **Módulo nuevo `aspect_classifier/operadores.py`** (funciones puras, patrón de siempre):
   `detectar_operadores(toks, root_id, aux_asp, cfg) -> dict`. Cada operador detectado lleva
   TRES cosas: valor, ESTRATO (nuclear/central/clausular) y SEÑAL DE ORIGEN (qué lo disparó,
   legible: `"TNS=PAST ← 'corrió' (Tense=Past)"`, `"ASP=PERF ← auxiliar 'ha'"`), p. ej.:
   `{'IF': {'valor':'DEC','estrato':'clausular','origen':'declarativa (default)'},
     'TNS': {'valor':'PAST','estrato':'clausular','origen':"'corrió' Tense=Past"}, ...}`.
   La señal de origen alimenta los tooltips de la GUI y la futura corrección de operadores.
   Y `envolver_ls(ls: str, ops: dict) -> str` que aplica el anidamiento (2.25) con ⟨ ⟩ y omite
   los no especificados. IF=DEC SÍ se muestra (es el valor por defecto pero informativo).
   NOTA DE NOTACIÓN: nada nuevo debe profundizar la numeración x1/x2/x3 (es un gruxx-ismo; la
   RRG usa x/y por predicado y hay una reforma pendiente) — el dict de operadores y el JSON de
   la GUI no deben referenciar variables numeradas.
2. **Mapper**: tras construir la EL (y sus wrappers de periferia — los operadores envuelven
   POR FUERA de todo: `⟨IF DEC ⟨TNS PAST ⟨yesterday'(be-in'(parque, [do'(…)]))⟩⟩⟩`), calcular
   operadores y añadir al dict: `operadores` (el dict crudo) + `ls_formal_ops`/`ls_lexical_ops`
   (las versiones envueltas). Config: sección `operadores.enabled: true`; con `false` → salida
   byte-idéntica a hoy.
3. **Salida terminal**: la EL léxica y formal se muestran ENVUELTAS (esa es la representación
   RRG completa); línea adicional pequeña `Operadores : IF=DEC · TNS=PAST · ASP=PERF PROG`
   (legible). `--verbose` muestra el dict crudo con estratos.
4. **GUI — proyección espejo de operadores (spec cerrada con Julian, NO es stretch)**:
   - **Motor** (`gruxx_motor.py`): función nueva `_operadores_de(ls)` integrada en
     `construir_sub_oracion` — el JSON por sub-oración gana la clave `operadores` (valor +
     estrato + origen) y las EL envueltas. El servidor no cambia.
   - **Panel de EL**: mostrar la EL léxica/formal ENVUELTAS con ⟨ ⟩.
   - **Proyección espejo** (`gui/app.js`; el layout ya calcula la coordenada x de cada nodo):
     debajo de la fila de palabras, desde la **V del predicado** (misma x que su nodo en el
     árbol de constituyentes) baja una espina invertida `V → NUC → CORE → CLAUSE → SENTENCE`
     — el espejo de la fig. 5.2. A cada estrato se conectan con flechas los operadores
     DETECTADOS (solo esos: la proyección de una declarativa simple es corta): ASP y NEG
     nuclear al NUC; MOD al CORE; TNS/STA/IF a la CLAUSE. Las dos proyecciones convergen
     visualmente SOLO en la V/NUC, como manda la teoría.
   - **Interacción**: hover sobre un operador (en la proyección O en la EL envuelta) → tooltip
     con la definición del glosario + la señal de origen ("de 'corrió', pretérito"), y
     resaltado cruzado EL↔nodo espejo (mismo patrón bidireccional que ya usa la GUI para
     argumento↔constituyente; reutilizar los `<title>`/tooltips SVG existentes).
   - **Toggle** "mostrar proyección de operadores" (default: oculta) para mantener limpia la
     vista; con ella activa, la pantalla muestra las tres representaciones de la RRG
     (constituyentes + operadores + EL) ancladas entre sí — modo presentación.
5. **Glosario** (`data/glosario_gruxx.csv`): categoría NUEVA "Operadores" con estas entradas
   (redacción de la sesión de diseño, sembrar tal cual; Julian edita después):

```
Operadores,operador,"Categoría gramatical cerrada (tiempo, aspecto, modalidad, fuerza ilocutiva…) que modifica un estrato de la cláusula; no es un nodo del árbol sino parte de su propia proyección."
Operadores,⟨ ⟩,"Corchetes angulares: encierran los operadores y su alcance sobre la EL: ⟨IF DEC ⟨TNS PAST ⟨EL⟩⟩⟩. Los operadores sin especificar se omiten."
Operadores,proyección de operadores,"Estructura en espejo de la proyección de constituyentes; ambas convergen únicamente en el núcleo (V). Los nucleares van pegados a la raíz verbal, los clausulares al extremo."
Operadores,IF,"Fuerza ilocutiva (clausular): tipo de acto de habla. Valores: DEC declarativa, INT interrogativa, IMP imperativa."
Operadores,TNS,"Tiempo (clausular). Valores: PAST pasado, PRES presente, FUT futuro. El imperfecto español = TNS PAST + ASP IMPF."
Operadores,ASP,"Aspecto (nuclear). Valores: PERF perfecto ('ha llorado'), PROG progresivo ('está llorando'), IMPF imperfectivo ('lloraba'). Combinables: PERF PROG."
Operadores,NEG,"Negación ('no'). Puede ser nuclear o interna según su alcance (sin subtipo por ahora)."
Operadores,MOD,"Modalidad deóntica (central): obligación, habilidad, permiso. Valores: OBLG ('debe…'), ABIL ('puede…')."
Operadores,STA,"Estatus / modalidad epistémica (clausular): real vs irreal. Valor: IRR (subjuntivo, condicional, 'quizá…'); REAL se omite por defecto."
Operadores,estrato del operador,"Nivel que modifica: nuclear (ASP, NEG nuclear), central (MOD), clausular (STA, TNS, IF). Determina su posición en el anidamiento y su cercanía morfológica a la raíz verbal."
```

6. **Bucle de corrección**: NO SE TOCA en este prompt (acordado con Julian: primero que los
   operadores funcionen). Dejar comentarios `TODO-OPERATORS-2` en los puntos de enganche
   (menú de corrección, enrutado de destinos, re-análisis) — el dict de operadores con
   valor/estrato/origen ES la interfaz que `prompt_OPERATORS_2.md` consumirá para hacerlos
   corregibles.

## Tests + validación

- Fríos (toks a mano): "¿Ha estado llorando Juan?" → `⟨IF INT ⟨TNS PRES ⟨ASP PERF PROG
  ⟨do'(Juan, [llorar'(Juan)])⟩⟩⟩⟩` (el ejemplo canónico 2.26 en español, byte a byte);
  "estudié" → IF DEC + TNS PAST; "Juan corría" → TNS PAST + ASP IMPF; "Juan no corrió" → NEG;
  "Juan debe estudiar" → MOD OBLG (si el parse de Stanza lo permite; si no, fixture gold);
  "Quizá venga" → STA IRR (+ Mood=Sub); "¡Corre!" (imperativo) → IF IMP; omisión correcta de
  operadores no especificados; anidamiento con wrappers por fuera de la EL y operadores por
  fuera de los wrappers.
- @slow: 3-4 oraciones end-to-end (terminal y GUI) mostrando la EL envuelta; las dianas
  históricas NO cambian de clase ni de EL interna (los operadores solo envuelven — verificar
  batería completa con `enabled: true` y byte-idéntico con `false`).
- Suites completas verdes (los 2 preexistentes conocidos documentados).

## CHECKPOINT — PARAR aquí

Informe: (1) salida completa de las oraciones de test (terminal + captura GUI con la
proyección espejo activa); (2) tabla de detección (qué señal disparó cada operador); (3) casos
logueados de perífrasis modales no cubiertas; (4) confirmación batería sin regresión y
byte-idéntico con `enabled: false`; (5) los puntos TODO-OPERATORS-2 dejados para el sub-prompt
de corrección. Después de este checkpoint: `prompt_OPERATORS_2.md` (corrección de operadores
en el bucle) y luego `prompt_LA1.md` (linking algorithm explícito).
