# CHECKPOINT_BENEFACTIVAS

Fecha de cierre: 2026-08-12. Alcance: reforma de la construcción ditransitiva
benefactiva y aprendizaje estructurado desde el corrector/GUI. LA3 y las
oraciones compuestas permanecen pausadas.

## Resultado

`benefactiva` sigue siendo la familia de construcción, pero ya no selecciona
una EL rígida. El XLSX curado aporta una especificación serializable con
`subtipo_benefactivo`, `predicado_resultado` y `proposito`; la misma
especificación alimenta la EL textual, `ls_estructura`, los metadatos del
mapper, Linking, Completeness, MISC y el contrato motor/JSON.

Los cinco subtipos cerrados son:

| subtipo | núcleo | clase | propósito habitual |
|---|---|---|---|
| `obtencion` | `[[do'(x, Ø)] CAUSE [BECOME have'(x,z)]]` | accomplishment | `BECOME have'(y,z)` |
| `preparacion` | `[[do'(x, Ø)] CAUSE [BECOME prepared'(z)]]` | accomplishment | `BECOME have'(y,z)` |
| `creacion` | `[[do'(x, Ø)] CAUSE [BECOME exist'(z)]]` | accomplishment | `BECOME have'(y,z)` |
| `cambio_estado` | `[[do'(x, Ø)] CAUSE [BECOME pred'(z)]]` | accomplishment | `have'(y,z)` |
| `actividad` | `do'(x,[lema'(x,z)])` | activity | `BECOME have'(y,z)` |

`proposito` admite `become_have`, `have` y `none`; la ausencia se representa
explícitamente y nunca se inventa. Los predicados resultativos son valores
curados y monovalentes, no traducciones automáticas de lemas españoles.

## Esquema y auditoría del XLSX

Esquema final: `lema`, `plantilla`, `subtipo_benefactivo`,
`predicado_resultado`, `proposito`, `ambiguo`, `notas`, `fuente`. El cargador
exige el esquema migrado, valida enums, combinaciones, duplicados y forma del
predicado, y diagnostica archivo, fila y lema. Transferencia y comunicación
mantienen vacíos los campos exclusivos de benefactivas.

Se preservaron las 122 filas existentes y se auditaron las 30 benefactivas:

| decisión | verbos |
|---|---|
| obtención / `become_have` | comprar, conseguir, recoger, ganar |
| preparación / `prepared'` / `become_have` | cocinar, preparar, hornear |
| creación / `exist'` / `become_have` | hacer, construir, fabricar, dibujar, coser, tejer, crear, inventar |
| cambio / `clean'` / `have` | lavar, limpiar |
| cambio / `painted'` / `have` | pintar |
| cambio / `repaired'` / `have` | arreglar, reparar |
| cambio / `translated'` / `have` | traducir |
| actividad / `become_have` | reservar, elegir, buscar, pedir, leer, organizar, planear, guardar, esconder |

Las decisiones conservadoras quedaron en `notas`. `traducir`, `leer`, `ganar`
y `esconder` conservan `ambiguo=True`; una corrección incompatible sin un
discriminador aplicable se envía a `staging_conflicto` y no sobrescribe la
lectura.

## EL canónicas finales

```text
preparar
[[do'(x, Ø)] CAUSE [BECOME prepared'(z)]] PURP [BECOME have'(y, z)]

crear
[[do'(x, Ø)] CAUSE [BECOME exist'(z)]] PURP [BECOME have'(y, z)]

comprar
[[do'(x, Ø)] CAUSE [BECOME have'(x, z)]] PURP [BECOME have'(y, z)]

reparar
[[do'(x, Ø)] CAUSE [BECOME repaired'(z)]] PURP [have'(y, z)]
```

Para `Juan prepara pizzas a María todas las mañanas`, el mapper real produjo:

```text
EL léxica:
⟨IF DEC ⟨TNS PRES ⟨every'(mañanas, [[[do'(Juan, Ø)] CAUSE
[BECOME prepared'(pizzas)]] PURP [BECOME have'(María, pizzas)]])⟩⟩⟩

EL formal:
⟨IF DEC ⟨TNS PRES ⟨every'(mañanas, [[[do'(x, Ø)] CAUSE
[BECOME prepared'(z)]] PURP [BECOME have'(y, z)]])⟩⟩⟩
```

`ls_estructura` conserva las dos apariciones semánticas de `z`: `arg_estado`
en `prepared'` y `2_pred_xy` en el `have'` de propósito. Linking las deduplica
por identidad variable/token: `Actor=Juan`, `Undergoer=pizzas`, `María=NMR`,
M-transitividad 2. No se duplican argumentos ni fallan Completeness/MISC.

## Aprendizaje y corrector

El reconocimiento de EL devuelve una especificación estructurada y comprueba
alcance, aridad y coindexación. Los wrappers y operadores exteriores se
normalizan de forma acotada. Las formas heredadas `x1/x2/x3`, un resultado
bivalente, un `z` no coindexado o un predicado de actividad distinto del lema
se rechazan.

El upsert del XLSX es atómico:

- lema nuevo: `insert`;
- lema conocido no ambiguo: `update` en la misma fila;
- repetición exacta: `no-op`;
- lectura ambigua incompatible: `staging_conflicto`;
- cualquier fallo de confirmación restaura exactamente los bytes anteriores,
  recarga el léxico en memoria y registra `revert` + `staging_no_confirmado`.

El log maestro conserva oración, lema, EL propuesta, especificación, acción,
destino, fuente y los valores `antes`/`despues` (o el intento revertido). La
confirmación exige familia, subtipo, predicado, propósito, EL léxica exacta tras
normalización segura, notación formal `x/y/z`, estructura no vacía e identidad
de argumentos; coincidir sólo en `benefactiva` ya no confirma nada.

La GUI muestra separadamente `insert`, `update`, `no-op`, conflicto y falta de
confirmación. Sólo las tres primeras, tras la comparación exacta, usan el
mensaje "verificado".

## Evidencia de pruebas reproducida

Estado final:

```text
gate focal exacto del prompt:
163 passed, 12 skipped in 4.20s

./venv/bin/python -m aspect_classifier.test_ditransitivas --slow
20 tests pasaron

RUN_SLOW=1 ./venv/bin/python -m pytest -q aspect_classifier/test_l5.py
49 passed in 13.08s

RUN_SLOW=1 ./venv/bin/python -m pytest -q aspect_classifier/test_notacion.py
4 passed in 9.97s

suite completa (acceso normal a cachés locales):
382 passed, 37 skipped, 1 warning in 35.37s
```

La suite completa dentro del sandbox de sólo lectura falló inicialmente en
seis pruebas que intentaban crear temporales de Stanza bajo
`~/.cache/stanza`; repetida con acceso normal a las cachés, quedó verde.

El gate aislado del servidor conserva una limitación ambiental preexistente:
`timeout 90s ... pytest -q test_gruxx_server.py` termina con código 124. El
diagnóstico `pytest -vv -s -x` bajo el mismo timeout se detiene en el primer
test, `test_estado_listo_tras_startup`, durante el lifespan de `TestClient`.
Esos tests pasan dentro de la suite completa; no se alteró el servidor para
ocultar el bloqueo aislado.

## Validación GUI/JSON aislada

Se levantó una sola instancia en `127.0.0.1:8764` (8763 ya estaba ocupado),
con una copia del XLSX bajo `/tmp`, y se inspeccionó el DOM real:

- `preparar` mostró `prepared'(z)`, wrappers `IF/TNS/every'`, argumentos
  `x/y/z`, NMR y M-transitividad 2;
- `comprar` mostró obtención de `x` y `PURP [BECOME have'(y,z)]`;
- la GUI validó una corrección de `amasar` como subtipo `actividad`, respondió
  "Conocimiento añadido y verificado" y habilitó el nuevo análisis;
- un análisis fresco de `Juan amasa masa para Ana` produjo
  `do'(x,[amasar'(x,z)]) PURP [BECOME have'(y,z)]`, metadatos de actividad y
  una sola fila `amasar` en el XLSX temporal (123 filas frente a 122);
- el SHA-256 del XLSX curado real permaneció
  `2d808b99ba7b41dd0025e8078905991953b586b99ade41a6aa674d65f822b9ca`.

La pestaña y la instancia aislada se cerraron al terminar.

## Archivos de este hito

- `aspect_classifier/data/verbos_ditransitivos.xlsx`
- `aspect_classifier/ditransitivas.py`
- `aspect_classifier/linking.py`
- `aspect_classifier/correccion.py`
- `rrg_ls_mapper.py`
- `gruxx_motor.py`
- `gui/app.js`
- `aspect_classifier/test_ditransitivas.py`
- `aspect_classifier/test_l5.py`
- `aspect_classifier/test_notacion.py`
- `test_gruxx_motor.py`
- `test_gruxx_server.py`
- `CHECKPOINT_BENEFACTIVAS.md`
- `ESTADO_DEL_ARTE_GRUXX.md`

`completeness.py`, `misc_rrg.py` y `display_grr.py` consumen la estructura
compartida y no necesitaron una bifurcación benefactiva adicional.

No se hizo commit. No se tocaron modelos, entrenamiento, embeddings, PUD,
Stanza, BERTIN, `contextual_sentences.csv`, `dataset_clean.csv`, `ud2rrg.py`,
`complex sentences/`, LA3 ni oraciones compuestas.
