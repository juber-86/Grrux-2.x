# Checkpoint — NOTACIÓN-1

Fecha de cierre de NOTACIÓN-1: 2026-08-12. **NOTACIÓN-2 queda pendiente de su
gate independiente.** LA3 y las oraciones compuestas continúan pausadas. No se
ejecutó PUD y no se modificaron `ud2rrg.py`, clasificadores, corroborador,
modelos `.joblib` ni `contextual_sentences.csv`.

## 1. Decisiones teóricas aplicadas

- Inventario argumental único: `x`, `y`, `z`, en ese orden canónico.
- Las variables se asignan por posición de la EL y macropapel, no por orden de
  tokens. La pasiva conserva `x=Actor`, `y=Undergoer`.
- Los predicados primitivos siguen siendo como máximo bivalentes. `z` sólo se
  licencia en plantillas compuestas con tres participantes.
- Locativos: `be-in'(x, y)`, con `x=locación`, `y=figura`.
- Causativas: causante `x`, resultado `y`; con causante inespecificado la EL es
  `[do'(Ø, Ø)] CAUSE [β(y)]` y el contrato conserva `variables.x=Ø`.
- Ditransitivas: `x=efectuador/emisor`, `y=poseedor/receptor`,
  `z=tema/contenido`; `y` continúa como NMR y `z` como Undergoer cuando
  corresponde.
- No existe conversión automática `xN→letra`: el detector de legado rechaza la
  entrada y exige regenerarla.

## 2. EL canónicas: antes/después

| Construcción | Antes | Después |
|---|---|---|
| Actividad monovalente | `do'(x1, [correr'(x1)])` | `do'(x, [correr'(x)])` |
| Actividad bivalente | `do'(x1, [comer'(x1, x2)])` | `do'(x, [comer'(x, y)])` |
| Estado bivalente | `saber'(x1, x2)` | `saber'(x, y)` |
| Locativo | `be-in'(x2, x1)` (campos incompletos) | `be-in'(x, y)`; `x=locación`, `y=figura` |
| Causativa activa | `[do'(x1, Ø)] CAUSE [INGR roto'(x2)]` | `[do'(x, Ø)] CAUSE [INGR roto'(y)]` |
| Anticausativa | `[do'(Ø, Ø)] CAUSE [INGR roto'(x2)]` | `[do'(Ø, Ø)] CAUSE [INGR roto'(y)]` |
| Transferencia | `[do'(x1, Ø)] CAUSE [BECOME have'(x3, x2)]` | `[do'(x, Ø)] CAUSE [BECOME have'(y, z)]` |
| Benefactiva | `have'(x1, x2)` / `have'(x3, x2)` | `have'(x, z)` / `have'(y, z)` |
| Comunicación | receptor léxico en el predicado formal | `do'(x, [decir.to.(y)'(x, z)])` |

La EL léxica conserva las formas concretas en todos los casos.

## 3. Contratos migrados

- `aspect_classifier/rrg_variables.py`: inventario, orden, validación y rechazo
  de legado.
- `rrg_ls_mapper.py`: mapas por plantilla/macropapel; ramas copulativa,
  causativa y ditransitiva autocontenidas; diagnóstico de argumentos sin
  posición licenciada.
- `ls_formal`, `args_map`, `variables`, `id_a_var`: emiten sólo `x/y/z`.
- MISC: `RRGVar`/`RRGArgVar` validan `x|y|z`; lectura directa rechaza MISC y
  comentarios formales `xN`.
- Correcciones: una EL con `x1`, `x2`, `x3` o `x9` falla en consistencia con
  mensaje de notación anterior y regeneración.
- Linking/completitud/paso 5: reconcilian las letras nuevas.
- Motor/API: `argumentos[].var` se valida y se ordena canónicamente.
- GUI: regex de variables completas `x/y/z`; hover comprobado; glosario vivo
  actualizado. Los atributos geométricos SVG `x1/x2/y1/y2` siguen intactos.

## 4. Casos de aceptación de NOTACIÓN-1

La batería `aspect_classifier/test_notacion.py` cubre actividad intransitiva y
transitiva, estado bivalente, locativo, pasiva, causativa, anticausativa,
transferencia, benefactiva, comunicación, pro-drop e impersonal. NOTACIÓN-1
dejó además la regresión `llueve→llover`, necesaria porque el pipeline local
devolvía el lema flexionado e inventaba un Actor pro-drop.

Argumentos detectados sin posición licenciada: **ninguno en las 12 dianas
end-to-end**. El contrato se probó además con un tercer argumento genérico
artificial: no recibe `z` y produce el diagnóstico
`argumento 'extra' (obl:arg) sin posición licenciada en la EL seleccionada`.

## 5. Resultados propios de NOTACIÓN-1

- Línea base obligatoria antes de editar: **144 passed, 12 skipped**.
- Gate rápido obligatorio tras la migración y sus cuatro rechazos nuevos:
  **148 passed, 12 skipped**.
- Gate ampliado de cierre de NOTACIÓN-1 (incluye matriz fría, rechazo,
  corrección y motor): **151 passed, 13 skipped**.

Las cifras de suites lentas, suite completa, servidor y GUI obtenidas durante
la implementación fueron evidencia preliminar. **No cierran NOTACIÓN-2** y
deben reproducirse bajo `prompt_notacion_2.md` antes de trasladarse a
`CHECKPOINT_NOTACION_2.md`.

## 6. Evidencia preliminar para NOTACIÓN-2

Durante NOTACIÓN-1 se hizo una inspección preliminar en una instancia aislada
de `127.0.0.1:8763`, cerrada al terminar:

- bivalente: `do'(x, [comer'(x, y)])`, tabla `x=Juan`, `y=pizza`;
- causativa: `[do'(x, Ø)] CAUSE [INGR roto'(y)]`;
- ditransitiva: `[do'(x, Ø)] CAUSE [BECOME have'(y, z)]`, tabla
  `x=Juan`, `y=María`, `z=flores`;
- hover de `x` y `y`: sólo se resaltó la fila homónima; `y` no resaltó `z`;
- cero `xN` en el DOM semántico y en el JSON de `/analizar`;
- linking e integridad mostraron `x↔NP · y↔PP · z↔NP` coherentes.

## 7. Auditoría de restos

- Código semántico activo: cero literales/regex `xN`; la única regex ordinal
  es `_LEGACY_RE`, detector explícito de entradas anteriores.
- Pruebas activas: `x1/x2/x3/x9` sólo aparecen en tests de rechazo.
- GUI: `gui/app.js` conserva `x1/x2/y1/y2` exclusivamente como coordenadas del
  estándar SVG.
- Documentación viva: glosario y diagrama migrados.
- Históricos preservados: prompts, checkpoints, informes y sesiones anteriores
  conservan sus ejemplos numerados como registro de la versión antigua.
- `complex sentences/`: fuera de alcance e intacta.

## 8. Archivos modificados por el hito

Código principal: `rrg_ls_mapper.py`, `gruxx_motor.py`, `gui/app.js`,
`aspect_classifier/{rrg_variables,causatividad,ditransitivas,linking,misc_rrg,correccion,completeness,display_grr,operadores}.py`.

Pruebas: `aspect_classifier/test_{notacion,causatividad,completeness,ditransitivas,l5,la2,linking,misc_rrg,nucleo_periferia,operadores,ud2rrg_es,wrappers_ls}.py`,
`test_gruxx_motor.py`, `test_gruxx_server.py`.

Documentación viva: `aspect_classifier/data/glosario_gruxx.csv`,
`docs/diagrama_gruxx.svg`, `ESTADO_DEL_ARTE_GRUXX.md` y este checkpoint.

Cambios preexistentes preservados y no atribuidos a este hito:
`aspect_classifier/data/linking_discrepancias.csv`, `gruxx-gui.log` y la
ampliación ya presente de `ESTADO_DEL_ARTE_GRUXX.md`, además de los archivos no
rastreados aportados por el usuario.

## 9. Estado final de NOTACIÓN-1

NOTACIÓN-1 queda cerrada. **NOTACIÓN-2 sigue pendiente** y debe reproducir las
pruebas lentas, servidor, suite completa, GUI/DOM/JSON y auditoría antes de
cerrar la reforma. LA3 y oraciones compuestas permanecen pausadas.
