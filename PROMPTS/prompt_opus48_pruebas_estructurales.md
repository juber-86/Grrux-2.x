# Tarea: pruebas de Van Valin ESTRUCTURALES — detector sobre la oración real + coerción aspectual + capa de explicación

Módulo `aspect_classifier` del proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python`
(3.10; torch, transformers<5, sklearn, pandas, pyyaml).

**PROHIBIDO:** tocar `gruxx_ai1.py`; tocar los `.joblib` de `models/` y `models/contextual/`;
reentrenar o modificar el clasificador (`predict.py`, `classifier.py`, `decision_tree.py` quedan
INTACTOS); tocar el corroborador MLM (`pruebas_clase_aspectual.py` queda como está, apagado con λ=0);
regenerar `data/contextual_sentences.csv`.

## Contexto y motivación

Las pruebas de Van Valin (texto fuente: `aspect_classifier/data/reglas_RRG.txt`) son la piedra
angular de las clases aspectuales de la GRR. El intento anterior (corroborador MLM, hoy apagado)
las usó en la dirección equivocada: sintetizaba frames por lema y pedía juicios de aceptabilidad a
BERTIN — contaminados por frecuencia de corpus, y redundantes con un probe ya fuerte.

La dirección correcta, y el patrón que YA funciona en el pipeline: **detectar el entorno de prueba
en la oración real del usuario** y usarlo como evidencia estructural de alta confianza. Prueba
viviente: el gate `AA_sin_delimitador→Activity` ES la Prueba 4 (`tiene_delimitador_nuclear` en
`nucleo_periferia.py:154`); la cascada de causatividad del Paso 4 ES la Prueba 7; y
`detect_aux_aspect` (`rrg_ls_mapper.py:293`) es el embrión de la Prueba 1. Esta tarea completa esa
familia. Asimetría deseada: las señales disparan POCO (no toda oración trae "durante una hora"),
pero cuando disparan son oro — alta precisión, cero costo, cero modelos.

Esto además prepara la siguiente fase (linking sintaxis↔semántica): en la GRR el progresivo es un
operador NUCLEAR y "durante una hora" es periferia del CORE — este detector es el comienzo de la
proyección de operadores.

## Estado actual relevante (leer antes de tocar)

- `nucleo_periferia.analizar_roles` (→ `roles`) ya tipa la periferia: cada item es
  `{id, text, deprel, tipo}` con `tipo ∈ {temporal, locativo, modo, otro}`.
  **OJO: los items de periferia NO llevan `case` ni `lemma`** — el detector los necesita
  ("durante" vs "en" vs "por"; adverbio "lentamente"). Primer paso: extender los dicts de periferia
  con `case` (lema de la preposición, ya se computa en `_case_de`) y `lemma`. Añadir claves es
  retro-compatible; verificar que `test_nucleo_periferia.py` (7 tests) sigue verde.
- Listas ya existentes en `nucleo_periferia.py`: `_NOMBRES_TIEMPO` (hora, minuto, día…),
  `_ADV_TIEMPO`, `_CASE_LOCATIVO`. Nota: "en una hora" ya sale `tipo=temporal` (el nombre de tiempo
  gana sobre `_CASE_LOCATIVO`).
- `detect_aux_aspect(root, words)` en el mapper devuelve `'prog' | 'complet' | None`
  (aux estar → prog).
- Flujo del mapper en `map_sentence_to_ls` (rrg_ls_mapper.py): predict → gate causativo 4D →
  gate AA sin delimitador → `detect_aux_aspect` → construcción de la LS. Las clases internas son
  las de `_ASPECT_TO_LS` (rrg_ls_mapper.py:57): `state, activity, achievement, semelfactive,
  accomplishment, active_accomplishment`.
- La nota visible al usuario es `aspect_note` → clave `morph_note` del dict de retorno; el render
  existente de `gruxx_ai1.py` la muestra. Los gates ya anotan ahí (p.ej.
  `gate=AA_sin_delimitador→Activity`).
- Diana conocida: "estudié tres horas anoche" → Activity (bug histórico arreglado por Etapa 1 +
  gate AA). La duración desnuda ("tres horas", sin preposición) puede parsear como obj u
  obl:tmod/nmod:tmod según Stanza — el detector debe reconocer duración por el NOMBRE de tiempo,
  no solo por la preposición.

## 1. Módulo nuevo: `aspect_classifier/pruebas_estructurales.py`

Funciones PURAS sobre estructuras ya existentes (`toks`, `roles`, `aux_asp`, lemas) — sin Stanza,
sin BERTIN, sin I/O. API propuesta:

```python
def detectar_evidencia(toks, root_id, roles, aux_asp, cfg) -> dict
# → {"evidencias": [{"prueba": "P4", "trigger": "durante una hora",
#                    "rasgo": "durativo", "implica": {...}}, ...],
#    ...}
```

Detecciones (cada una cita su prueba):

- **P4 (durativa)**: periferia `tipo=temporal` con (a) `case ∈ {durante, por}` + nombre de tiempo,
  o (b) duración desnuda (nombre de `_NOMBRES_TIEMPO` con numeral/determinante de cantidad).
  Evidencia: [+duración interna, −télico en esta lectura].
- **P5 (terminativa)**: periferia temporal con `case == en` + nombre de tiempo. Evidencia:
  [+télico, +duración]. (Distinguir de "en" locativo: exigir nombre de tiempo.)
- **P1 (progresivo)**: `aux_asp == 'prog'`. Evidencia: [−estático]; sobre clase puntual → lectura
  iterativa (ver coerciones).
- **P2 (adverbios dinámicos)**: periferia `tipo=modo` con lemma en lista configurable
  {vigorosamente, activamente, enérgicamente, dinámicamente}. Evidencia: [+dinámico].
- **P3 (adverbios de ritmo)**: periferia `tipo=modo` con lemma en {lentamente, rápidamente,
  gradualmente, poco a poco*} (*si parsea como advmod multiword, no complicarse). Evidencia:
  [−puntual, +duración].
- P6 y P7 NO van aquí (P6 no tiene entorno estructural en la oración de entrada; P7 ya la cubre la
  cascada de causatividad del Paso 4 — documentarlo en el docstring).

## 2. Coerciones y avisos en el mapper (gates nuevos, mismo patrón que el gate AA)

En `map_sentence_to_ls`, DESPUÉS de `detect_aux_aspect` y de los gates existentes (el vector del
clasificador NUNCA se toca; solo `verb_class` y las notas). Cada regla con su flag individual en
config y anotación en `aspect_note`:

- **R1 (P1+P4, semelfactivo iterativo)**: `semelfactive` + (progresivo O durativa P4) →
  `activity` con nota `coercion=P1/P4 semelfactive→activity_iterativa` ("tosió durante una hora",
  "está tosiendo"). Es la lectura iterativa del propio Van Valin.
- **R2 (P4, atélico)**: `accomplishment`/`active_accomplishment` + durativa P4 SIN terminativa P5
  → `activity` con nota `coercion=P4 lectura_atélica` ("leyó el libro durante una hora": el evento
  no culmina).
- **R3 (P5, refuerzo télico)**: `activity` + delimitador nuclear + terminativa P5 → NO cambiar
  clase aquí si el clasificador ya decidió, solo nota `P5 confirma télico` (el paso a AA ya lo
  gobiernan el clasificador + gate AA). Conservador a propósito.
- **R4 (conflictos → warning, sin cambio de clase)**: `state` + P2 dinámico; puntual
  (`achievement`/`semelfactive`) + P3 de ritmo; `achievement` + progresivo (lectura
  prospectiva/iterativa posible — solo nota); `achievement` + terminativa P5 ("llegó en una
  hora" = demora hasta el inicio, NO duración del evento — jamás reclasificar por P5 un
  achievement). Formato: `⚠ conflicto=P2 vs State`.

Regla general: default = no hacer nada; solo evidencia presente y unívoca dispara. R1 y R2 cambian
clase (coerción licenciada por la teoría), R3 y R4 solo anotan.

Además, el dict que devuelve `map_sentence_to_ls` gana dos claves nuevas (retro-compatibles,
pensadas como INSUMO de la próxima fase de linking / proyección de operadores):
`pruebas_evidencia` (la salida completa del detector, incl. `aux_asp` como operador nuclear ASP)
y `coerciones` (lista de reglas disparadas con su trigger). Vacías si no hubo evidencia o con
`enabled: false`.

## 3. Capa de explicación: el cuadro 1 como dato

- Codificar la tabla clase→patrón esperado de pruebas (del texto fuente) como constante
  `CUADRO_PRUEBAS` en el módulo nuevo:
  P1: Act ✓, Acc ✓, AA ✓; Sta ✗, Ach ✗(suj. sing.), Sem → iterativo.
  P2: solo Act y AA ✓. P3: Act, Acc, AA ✓ (no aplica a Sta). P4: Sta, Act, Acc, AA ✓; Ach, Sem ✗.
  P5: solo Acc y AA ✓. P6: Ach ✓, Sem ✗. P7 → causatividad.
- En el mapper, añadir a `aspect_note` una línea compacta SOLO cuando hubo evidencia detectada:
  `Pruebas: P4 'durante una hora'→atélico ✓coherente con Activity` o
  `Pruebas: P2 'vigorosamente' ⚠conflicto con State`. La coherencia sale de comparar la evidencia
  contra `CUADRO_PRUEBAS[clase]`. Sin evidencia → sin línea (no ruido).
- Se muestra por el render existente (`morph_note`); `gruxx_ai1.py` no se toca.

## 4. Config (`aspect_classifier/config.yaml`)

Sección nueva:

```yaml
pruebas_estructurales:
  enabled: true          # flag maestro; false = regresión byte-idéntica
  adv_dinamicos: [vigorosamente, activamente, enérgicamente, dinámicamente]
  adv_ritmo: [lentamente, rápidamente, gradualmente]
  prep_durativas: [durante, por]
  prep_terminativa: en
  coerciones:            # flags individuales (todas true por defecto)
    semelfactive_iterativa: true    # R1
    lectura_atelica: true           # R2
  avisos: true           # R3/R4 (solo notas)
```

Documentar cada regla con un comentario de una línea citando la prueba.

## 5. Tests + validación

- `test_pruebas_estructurales.py` nuevo, tests RÁPIDOS con `toks`/`roles` construidos a mano (sin
  Stanza): P4 con "durante/por/desnuda", P5 "en una hora" vs "en la casa" (locativo NO dispara),
  P1 con aux_asp, P2/P3 por lema, R1 y R2 cambian clase, R3/R4 solo anotan, flag maestro apagado →
  cero efecto.
- `test_nucleo_periferia.py` sigue 7/7 tras añadir `case`/`lemma` a la periferia.
- Integración `@slow` (Stanza real): "tosió durante una hora" → activity (R1, era el caso fuga
  Semelfactive); "leyó el libro durante una hora" → activity (R2); "corrió en una hora hasta la
  cima" o similar → nota P5; "estudié tres horas anoche" → Activity, ahora con nota P4 coherente
  (dos vías: gate AA + P4); "Juan sabe la respuesta" → sin notas (cero ruido).
- Batería de 15 dianas (`python -m aspect_classifier.test_fase2_contextual --slow`): TODAS OK. Si
  alguna diana cambia de clase por una coerción, PARAR y reportar el caso (checkpoint para Julian)
  en vez de forzar el gold.
- Suites existentes verdes: `test_causatividad`, `test_complejo --slow`,
  `test_pruebas_aspectuales`.
- Con `enabled: false`, salida byte-idéntica a hoy (verificarlo sobre 2-3 oraciones).

## Checkpoint

Al terminar, correr un mini-informe (script o modo `--informe`) sobre las 15 dianas + estas frases:
"tosió durante una hora", "está tosiendo", "leyó el libro durante una hora", "la ropa se secó en
una hora", "corrió vigorosamente", "Juan sabe la respuesta", "los invitados llegaron durante una
hora" — listando por frase: clase del clasificador, evidencias detectadas, regla disparada (si
alguna), clase final. Julian revisa ese informe antes de dar por buena la config por defecto.

## Aceptación

- Detector estructural puro (P1/P2/P3/P4/P5) sobre la oración real; periferia con `case`+`lemma`.
- R1/R2 como gates con flags; R3/R4 solo notas; `CUADRO_PRUEBAS` como dato y línea de coherencia
  en la salida solo cuando hay evidencia.
- 15 dianas OK (o checkpoint reportado); regresión byte-idéntica con `enabled: false`; todas las
  suites verdes; `gruxx_ai1.py`, clasificador y corroborador MLM intactos.
