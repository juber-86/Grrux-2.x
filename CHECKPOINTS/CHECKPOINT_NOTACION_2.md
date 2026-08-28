# Checkpoint — NOTACIÓN-2

Fecha de cierre: 2026-08-12. Este checkpoint contiene evidencia reproducida
durante la ejecución de `prompt_notacion_2.md`; no reutiliza los resultados
preliminares registrados en NOTACIÓN-1.

## 1. Decisiones teóricas verificadas

- El inventario argumental formal es exclusivamente `x`, `y`, `z`.
- La asignación sigue posiciones semánticas y macropapeles, no el orden
  superficial. En particular, la pasiva mantiene Actor=`x` y Undergoer=`y`.
- Los predicados primitivos son como máximo bivalentes; `z` sólo aparece en
  plantillas compuestas con tres participantes.
- En locativos, `be-in'(x, y)` asigna `x=locación`, `y=figura` y conserva ambos
  argumentos estructurados.
- En causativas, `x` es el causante y `y` el participante afectado; cuando el
  causante es inespecificado se conserva `variables.x=Ø` y el paciente sigue
  siendo `y`.
- En transferencias, `x=efectuador`, `y=poseedor/receptor` y `z=tema/contenido`;
  `y` es NMR y `z` Undergoer cuando corresponde.
- Las entradas heredadas `xN` se rechazan; no se convierten automáticamente.

## 2. EL canónicas antes/después

| Construcción | Notación anterior | Notación vigente |
|---|---|---|
| Actividad monovalente | `do'(x1, [correr'(x1)])` | `do'(x, [correr'(x)])` |
| Actividad bivalente | `do'(x1, [comer'(x1, x2)])` | `do'(x, [comer'(x, y)])` |
| Estado bivalente | `saber'(x1, x2)` | `saber'(x, y)` |
| Locativo | `be-in'(x2, x1)` | `be-in'(x, y)` (`x=locación`, `y=figura`) |
| Causativa activa | `[do'(x1, Ø)] CAUSE [INGR roto'(x2)]` | `[do'(x, Ø)] CAUSE [INGR roto'(y)]` |
| Anticausativa | `[do'(Ø, Ø)] CAUSE [INGR roto'(x2)]` | `[do'(Ø, Ø)] CAUSE [INGR roto'(y)]` |
| Transferencia | `[do'(x1, Ø)] CAUSE [BECOME have'(x3, x2)]` | `[do'(x, Ø)] CAUSE [BECOME have'(y, z)]` |
| Benefactiva | `have'(x1, x2)` / `have'(x3, x2)` | `have'(x, z)` / `have'(y, z)` |
| Comunicación | receptor léxico en la EL formal | `do'(x, [decir.to.(y)'(x, z)])` |

## 3. Contratos comprobados

- `ls_formal`, `args_map`, `variables` e `id_a_var` producen únicamente
  `x/y/z`, con orden canónico y validación compartida.
- MISC acepta `RRGVar`/`RRGArgVar` con `x|y|z`; rechaza valores `xN` tanto en
  esos campos como en comentarios `# rrg_ls`.
- Corrección rechaza EL con `x1`, `x2`, `x3` y el caso genérico `x9` con un
  mensaje de notación anterior que pide regenerar la entrada.
- Motor y API conservan el inventario y el orden en `argumentos[].var`.
- Linking, integridad y GUI consumen las mismas letras. La GUI delimita las
  variables completas, sin convertir letras internas de predicados en spans.
- Los atributos geométricos SVG `x1/x2/y1/y2` permanecen sin cambios.

## 4. Evidencia reproducida

### Pruebas focales y matriz

- Gate focal exacto de `prompt_notacion_2.md`: **151 passed, 13 skipped in
  3.32s**.
- `RUN_SLOW=1 ./venv/bin/python -m pytest -q
  aspect_classifier/test_notacion.py`: **4 passed in 9.39s**.

### Suites lentas, una por una

Ejecutadas con `RUN_SLOW=1`, sin GUI abierta:

- `aspect_classifier/test_ditransitivas.py`: **18 passed**.
- `aspect_classifier/test_causatividad.py`: **9 passed**.
- `aspect_classifier/test_linking.py`: **34 passed**.
- `aspect_classifier/test_misc_rrg.py`: **21 passed**.
- `aspect_classifier/test_nucleo_periferia.py`: **26 passed**.

### Servidor y suite completa

- `timeout 90s ./venv/bin/python -m pytest -q test_gruxx_server.py`: terminó
  por timeout, código **124**, sin salida de pytest.
- Diagnóstico `timeout 90s ./venv/bin/python -m pytest -vv -s -x
  test_gruxx_server.py`: recolectó **28 tests** y quedó esperando en el primero,
  `test_estado_listo_tras_startup`; terminó con código **124**.
- Suite completa posterior: **374 passed, 36 skipped, 1 warning in 32.50s**.
  El warning fue `StarletteDeprecationWarning` de la integración
  Starlette/httpx.

La diferencia entre el aislado y la suite completa reproduce una limitación
preexistente de ciclo de vida/entorno, anterior al análisis semántico. La suite
completa incluye los tests del servidor y quedó verde. No se modificó
`gruxx_server.py`.

### GUI, DOM y JSON

Se levantó una instancia aislada de un solo worker en
`http://127.0.0.1:8763/`, se inspeccionó con el navegador integrado y se cerró
al terminar. El mecanismo fue **DOM + interacción real de puntero**, no una
captura inventada.

- Bivalente, `Juan comió pizza`: EL formal
  `⟨IF DEC ⟨TNS PAST ⟨do'(x, [comer'(x, y)])⟩⟩⟩`; `x=Juan` Actor,
  `y=pizza` Undergoer; hover de `x` y `y` resaltó sólo su fila homónima.
- Causativa, `Juan rompió la ventana`: EL formal
  `⟨IF DEC ⟨TNS PAST ⟨[do'(x, Ø)] CAUSE [INGR roto'(y)]⟩⟩⟩`; DOM con
  `x/y`, linking e integridad concordantes y sin `xN`.
- Ditransitiva, `Juan le dio flores a María`: EL formal
  `⟨IF DEC ⟨TNS PAST ⟨[do'(x, Ø)] CAUSE [BECOME have'(y, z)]⟩⟩⟩`;
  `x=Juan` Efectuador, `y=María` Poseedor, `z=flores` Tema. Linking confirmó
  Actor=Juan, Undergoer=flores, María=NMR y asignación
  `x↔NP · y↔PP · z↔NP · AGX✓`. El hover de `x`, `y` y `z` resaltó sólo la fila
  correspondiente, sin confundir `y` con `z`.
- Wrappers, `Ayer Juan corrió en el parque`: EL formal
  `⟨IF DEC ⟨TNS PAST ⟨yesterday'(be-in'(parque, [do'(x, [correr'(x)])]))⟩⟩⟩`.
  El DOM conservó `IF DEC` y `TNS PAST` como operadores, `yesterday'` y
  `be-in'` íntegros, y marcó como variables solamente los dos usos de `x`.

En los cuatro resultados hubo cero spans semánticos `xN` y cero letras dentro
de palabras o predicados marcadas como variables. Una petición fresca a
`POST /analizar` para la ditransitiva devolvió `argumentos[].var = x,y,z`, EL
formal/operada con `x/y/z` y ninguna variable numerada.

## 5. Auditoría transversal de restos `xN`

- Código semántico activo: cero valores `xN` emitidos. Las variables locales
  históricamente llamadas `x1_var`/`x2_var` en `rrg_ls_mapper.py` contienen
  literalmente `x`/`y`; son identificadores internos, no variables RRG ni
  salida observable.
- Validación activa: la única regex `x\d+` es `_LEGACY_RE` en
  `aspect_classifier/rrg_variables.py`, que detecta y rechaza el formato
  anterior.
- Pruebas: las apariciones `x1/x2/x3/x9` son entradas negativas de rechazo;
  no hay fixtures activos que esperen salidas numeradas. `120x120` es una
  dimensión de imagen, ajena a RRG.
- GUI: `x1/x2/y1/y2` sólo aparecen como coordenadas de líneas SVG y quedaron
  intactas.
- Documentación viva: glosario, diagrama, estado del arte y checkpoints de la
  reforma usan `x/y/z`. Prompts, checkpoints e informes históricos conservan
  ejemplos `xN` como registro de versiones anteriores.
- `complex sentences/` quedó fuera de alcance e intacta; sus coincidencias son
  atributos geométricos SVG.

## 6. Limitaciones y cambios preexistentes

La espera aislada del servidor es la única limitación reproducida; queda
acotada por la suite completa verde y no motivó cambios de servidor. Se
preservaron sin atribuir a esta ejecución los cambios preexistentes de
`aspect_classifier/data/linking_discrepancias.csv`, `gruxx-gui.log` y los
archivos no rastreados aportados por el usuario.

## 7. Archivos de la reforma

- Código: `rrg_ls_mapper.py`, `gruxx_motor.py`, `gui/app.js` y
  `aspect_classifier/{rrg_variables,causatividad,ditransitivas,linking,misc_rrg,correccion,completeness,display_grr,operadores}.py`.
- Pruebas: `aspect_classifier/test_{notacion,causatividad,completeness,ditransitivas,l5,la2,linking,misc_rrg,nucleo_periferia,operadores,ud2rrg_es,wrappers_ls}.py`,
  `test_gruxx_motor.py` y `test_gruxx_server.py`.
- Documentación viva: `aspect_classifier/data/glosario_gruxx.csv`,
  `docs/diagrama_gruxx.svg`, `prompt_notacion_1.md`,
  `CHECKPOINT_NOTACION.md`, `CHECKPOINT_NOTACION_2.md` y
  `ESTADO_DEL_ARTE_GRUXX.md`.

No se modificaron `ud2rrg.py`, PUD, clasificadores/modelos,
`contextual_sentences.csv`, `gruxx_server.py` ni `complex sentences/`.

## 8. Estado final

El gate de NOTACIÓN-2 queda superado y la reforma `x/y/z` queda cerrada. **LA3
y las oraciones compuestas continúan pausadas.**
