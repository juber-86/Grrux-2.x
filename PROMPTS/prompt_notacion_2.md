# Hito NOTACIÓN-2 — Validación integral, GUI y cierre documental

## Objetivo

Demostrar que la migración implementada en NOTACIÓN-1 funciona de extremo a
extremo en GRRux, que todos los canales muestran la misma identidad `x/y/z` y
que no se introdujeron regresiones conceptuales ni funcionales. Este hito es de
validación y corrección de defectos encontrados: si una prueba revela un bug de
la migración, arréglalo y vuelve a ejecutar el conjunto afectado.

Este es un **prompt ejecutor**, no una solicitud de diseño. Inspecciona el
repositorio, ejecuta las pruebas, corrige los defectos que pertenezcan a la
migración y completa el cierre documental. No declares terminado el hito a
partir de resultados escritos previamente: toda evidencia de NOTACIÓN-2 debe
reproducirse en esta ejecución.

## Estado de partida verificado

NOTACIÓN-1 ya está implementada en el árbol de trabajo y superó una revisión
independiente. Usa estos resultados como línea base, no como sustituto de las
pruebas de este hito:

- gate relacionado: **151 passed, 13 skipped**;
- matriz end-to-end de `aspect_classifier/test_notacion.py` con modelos:
  **4 passed**;
- suite rápida completa: **374 passed, 36 skipped, 1 warning**.

Hay una inconsistencia documental que debes corregir antes del cierre:

- `CHECKPOINT_NOTACION.md` se titula y declara cerradas NOTACIÓN-1 y
  NOTACIÓN-2, aunque debe ser el checkpoint exclusivo de NOTACIÓN-1;
- `prompt_notacion_1.md` todavía contiene instrucciones residuales para
  continuar automáticamente con NOTACIÓN-2, pese a terminar con `para aquí`;
- `ESTADO_DEL_ARTE_GRUXX.md` marca la reforma completa como cerrada antes del
  gate formal de este segundo hito.

Las pruebas lentas, GUI y auditoría descritas en el checkpoint actual se
consideran **evidencia preliminar**. Reprodúcelas; no copies sus resultados al
checkpoint final sin volver a ejecutarlas.

## Preparación y seguridad

- Lee completamente `Notacion_x_y.md`, `prompt_notacion_1.md`,
  `CHECKPOINT_NOTACION.md`, este prompt y la sección de deuda viva de
  `ESTADO_DEL_ARTE_GRUXX.md` antes de modificar nada.
- Revisa `git status --short` antes de continuar. El árbol puede contener
  cambios del usuario: presérvalos y no reviertas ni sobrescribas trabajo ajeno.
- No borres ni regeneres logs o CSV curados para conseguir una prueba verde.
- No ejecutes suites `--slow` mientras haya una instancia de la GUI/servidor de
  GRRux abierta. Si necesitas iniciar una instancia aislada, ciérrala al acabar.
- No uses PUD: continúa siendo un examen a ciegas y está fuera de este hito.
- No hagas commits salvo instrucción explícita del usuario. Deja el árbol listo
  para revisión y reporta todos los archivos modificados.

## 0. Restablecer la separación de hitos

Haz estas correcciones documentales al comenzar, sin reescribir la historia del
proyecto:

1. En `prompt_notacion_1.md`, elimina la instrucción de ejecutar ambos hitos y
   deja inequívoco que NOTACIÓN-1 termina al superar su gate. Corrige el texto
   residual `aconsjear` y conserva `para aquí` como condición de parada.
2. Convierte `CHECKPOINT_NOTACION.md` en el checkpoint de **NOTACIÓN-1**:
   - título y estado final sólo de NOTACIÓN-1;
   - NOTACIÓN-2 explícitamente pendiente;
   - conserva las decisiones, cambios y pruebas rápidas de NOTACIÓN-1;
   - si mantiene resultados lentos/GUI anteriores, rotúlalos como evidencia
     preliminar que NOTACIÓN-2 debe reproducir, nunca como cierre del hito 2.
3. En `ESTADO_DEL_ARTE_GRUXX.md`, deja inicialmente: “NOTACIÓN-1 implementada;
   validación NOTACIÓN-2 pendiente”. Sólo cambia a “reforma cerrada” después de
   superar el gate final de este prompt.
4. Reserva `CHECKPOINT_NOTACION_2.md` para los resultados nuevos y verificables
   de esta ejecución. No vuelvas a mezclar los dos checkpoints.

## 1. Matriz semántica de validación

Añade o consolida una batería end-to-end que verifique, como mínimo:

| Construcción | Oración | Contrato formal y de variables |
|---|---|---|
| Actividad intransitiva | `Juan corrió` | `do'(x,[correr'(x)])`; `x=Juan` |
| Actividad transitiva | `Juan comió pizza` | `do'(x,[comer'(x,y)])`; `x=Juan`, `y=pizza` |
| Estado bivalente | `Juan sabe la respuesta` | `saber'(x,y)` |
| Locativo | `Juan está en la biblioteca` | `be-in'(x,y)`; `x=biblioteca`, `y=Juan` |
| Pasiva perifrástica | `El pastel fue comido por Juan` | `x=Juan`, `y=pastel`, sin orden superficial |
| Causativa activa | `Juan rompió la ventana` | causante `x`, paciente `y` |
| Anticausativa | `El jarrón se rompió` | causante `Ø`, paciente `y` |
| Transferencia | `Juan le dio flores a María` | `have'(y,z)`; `x=Juan`, `y=María`, `z=flores` |
| Benefactiva | `Juan compró un regalo para María` | `have'(x,z)` y `have'(y,z)` |
| Comunicación | `Le dije la verdad` | `decir.to.(y)'(x,z)` |
| Pro-drop | `Comí pizza` | Actor morfológico `x`, tema `y` |
| Impersonal | `Llueve` | sin variable argumental inventada |

Para cada caso aplicable comprueba simultáneamente:

- `ls_formal` exacta y `ls_lexical` sin alteraciones indebidas;
- `variables`, `id_a_var` y `args_map` coherentes entre sí;
- `ls_estructura` y AUH con Actor/Undergoer/NMR correctos;
- `RRGVar`/`RRGArgVar` en MISC;
- completitud e integridad;
- contrato del motor `argumentos[].var`;
- salida de terminal y JSON de GUI sin `xN`.

NOTACIÓN-1 añadió la normalización local `llueve→llover` porque el pipeline
local devolvía el lema flexionado e inventaba un Actor pro-drop. Trátala como
una corrección colateral ya existente:

- no la retires para “reducir” el diff;
- conserva una regresión que verifique `Llueve → llover'`, sin `variables` ni
  `id_a_var` inventados;
- no amplíes `LEMA_FIXES` con más formas superficiales salvo que una prueba de
  este hito demuestre otro caso directamente relacionado.

## 2. Pruebas e integración

Ejecuta en este orden. Si un gate falla, diagnostica y corrige antes de avanzar
al siguiente.

### 2.1 Gate focal rápido

Reproduce primero el gate relacionado de NOTACIÓN-1:

```bash
./venv/bin/python -m pytest -q \
  aspect_classifier/test_notacion.py \
  aspect_classifier/test_ditransitivas.py \
  aspect_classifier/test_causatividad.py \
  aspect_classifier/test_linking.py \
  aspect_classifier/test_completeness.py \
  aspect_classifier/test_misc_rrg.py \
  aspect_classifier/test_wrappers_ls.py \
  test_gruxx_motor.py
```

### 2.2 Matriz end-to-end

Ejecuta la matriz con modelos:

```bash
RUN_SLOW=1 ./venv/bin/python -m pytest -q aspect_classifier/test_notacion.py
```

Si Stanza intenta escribir en una caché fuera del sandbox, usa el mecanismo
normal de aprobación del entorno; no modifiques rutas del proyecto ni
descargues modelos nuevos si los modelos locales ya existen.

### 2.3 Suites lentas seleccionadas

Ejecútalas una por vez para aislar consumo de memoria y fallos. Usa la forma de
invocación que ya declara cada módulo (`--slow` o `RUN_SLOW=1`). Incluye al
menos:

```bash
./venv/bin/python -m aspect_classifier.test_ditransitivas --slow
./venv/bin/python -m aspect_classifier.test_causatividad --slow
./venv/bin/python -m aspect_classifier.test_linking --slow
./venv/bin/python -m aspect_classifier.test_misc_rrg --slow
./venv/bin/python -m aspect_classifier.test_nucleo_periferia --slow
```

### 2.4 Servidor aislado y suite completa

Ejecuta `test_gruxx_server.py` aisladamente con un límite de 60–90 segundos y,
después, la suite rápida completa:

```bash
timeout 90s ./venv/bin/python -m pytest -q test_gruxx_server.py
./venv/bin/python -m pytest -q
```

Si la suite completa excede memoria o tiempo, no ocultes el hecho. Ejecuta por
grupos, registra exactamente qué grupos pasaron, cuáles se omitieron y por qué.
No atribuyas a esta migración un fallo preexistente sin reproducirlo contra la
línea base o demostrar que no toca la ruta modificada.

Si la suite aislada vuelve a quedar esperando, identifica el test exacto con
`pytest -vv -s` y timeout, diagnostica si hay servidor/hilo sin cerrar y corrige
sólo si el bloqueo fue introducido o está dentro del contrato de esta migración.
Usa para localizarlo:

```bash
timeout 90s ./venv/bin/python -m pytest -vv -s -x test_gruxx_server.py
```

La evidencia previa es aparentemente contradictoria pero reproducible: la
suite aislada llegó a esperar en `test_estado_listo_tras_startup`, mientras que
la suite completa terminó verde. Por eso:

- prueba primero `test_gruxx_server.py` aislado con un límite de 60–90 s;
- si espera, localiza el primer test con `-vv -s`;
- ejecuta después la suite completa;
- si la completa pasa y el aislado sólo falla por ciclo de vida/entorno,
  documéntalo como limitación preexistente;
- no cambies `gruxx_server.py` salvo que demuestres una regresión causada por
  NOTACIÓN-1 o un defecto necesario para validar sus contratos.

## 3. Validación de entradas heredadas

Añade pruebas end-to-end del corte estricto:

- EL corregida con `x1`, `x2`, `x3` y un `x9` genérico;
- CoNLL-U con `RRGVar=x2`;
- CoNLL-U con `RRGArgVar=x3`;
- comentario `# rrg_ls = ...x1...`;
- combinación de MISC válido `x/y/z` y comentario formal heredado.

Todas las entradas heredadas deben fallar de manera determinista antes de
producir un análisis mixto. El mensaje debe explicar que `xN` pertenece a la
notación anterior y que la entrada debe regenerarse con la versión actual. No
reescribas los archivos automáticamente.

## 4. Validación de la GUI

Usa una instancia local aislada en `http://127.0.0.1:8763/`. Verifica al menos
una oración bivalente, una causativa y una ditransitiva.

En cada análisis confirma:

- la EL formal muestra variables `x/y/z` completas y resaltadas;
- el hover de cada variable resalta el argumento correcto;
- `y` y `z` no se confunden en transferencia;
- linking e integridad usan las mismas letras;
- no se resaltan letras dentro de palabras o nombres de predicado;
- operadores y wrappers siguen mostrándose sin corromper el HTML;
- no aparece `x1`, `x2` o `x3` en el DOM semántico ni en la respuesta JSON.

Si el entorno no permite inspección interactiva, ejecuta las pruebas DOM/JS
disponibles y documenta esa limitación de forma explícita; no inventes una
captura o validación visual.

No aceptes como evidencia suficiente que el checkpoint anterior diga que la
GUI fue revisada. Registra en `CHECKPOINT_NOTACION_2.md` qué mecanismo usaste,
qué oraciones analizaste y si la comprobación fue visual, DOM o sólo contractual.

## 5. Auditoría transversal final

Ejecuta búsquedas separadas en código, pruebas y documentación. Revisa cada
coincidencia; no uses un reemplazo masivo ciego.

La auditoría debe demostrar:

- cero `xN` como variable RRG en código activo;
- cero regex, mensajes o validadores que todavía exijan `x\d+`, salvo el
  detector explícito de legado;
- cero fixtures activos con salidas numeradas;
- documentación viva actualizada a `x/y/z`;
- checkpoints, prompts y sesiones históricas preservados;
- atributos SVG `x1/x2/y1/y2` intactos;
- archivos de la carpeta `complex sentences/` fuera de alcance salvo que una
  referencia puramente documental requiera aclaración.

## 6. Checkpoint y actualización del estado

Mantén `CHECKPOINT_NOTACION.md` como checkpoint corregido de NOTACIÓN-1 y crea
`CHECKPOINT_NOTACION_2.md` con:

1. decisiones teóricas aplicadas;
2. tabla antes/después de las EL canónicas;
3. cambios de contratos (`ls_formal`, `args_map`, `variables`, `id_a_var`,
   MISC, motor y GUI);
4. resultados exactos de pruebas rápidas, lentas, servidor y GUI;
5. auditoría de restos `xN` clasificada;
6. fallos preexistentes o limitaciones, si existen;
7. lista de archivos modificados;
8. declaración explícita de que LA3 y oraciones compuestas continúan pausadas.

Sólo después de superar el gate final, actualizar la sección de deuda viva de
`ESTADO_DEL_ARTE_GRUXX.md` para marcar la reforma de notación como cerrada y
enlazar **ambos** checkpoints. No reescribir los resultados históricos: añadir
una nota breve indicando que sus ejemplos `x1/x2/x3` reflejan la versión
anterior de GRRux.

## Gate final de aceptación

La tarea sólo queda terminada si se cumplen todos estos puntos:

- GRRux emite exclusivamente variables RRG `x/y/z` en todos sus canales;
- las variables se asignan por posición semántica, no por orden superficial;
- ditransitivas usan `x=efectuador`, `y=poseedor/receptor`, `z=tema/contenido`;
- causativas con causante `Ø` conservan `y` para el paciente;
- locativos conservan ambos argumentos estructurados;
- entradas `xN` se rechazan explícitamente;
- suites rápidas relacionadas verdes;
- pruebas lentas seleccionadas ejecutadas y documentadas;
- GUI o su sustituto DOM verificado honestamente;
- auditoría final sin restos semánticos numerados;
- `CHECKPOINT_NOTACION.md` corregido como NOTACIÓN-1;
- `CHECKPOINT_NOTACION_2.md` creado con evidencia reproducida;
- estado del arte actualizado sólo después del gate final;
- no se tocó `ud2rrg.py`, PUD, modelos ni datos curados.

## Entrega final del modelo ejecutor

Responder con un informe breve y verificable que incluya:

- resultado funcional alcanzado;
- archivos principales modificados;
- conteos exactos de pruebas y cualquier omisión;
- resultado de GUI/DOM;
- enlaces o rutas a `CHECKPOINT_NOTACION.md` y
  `CHECKPOINT_NOTACION_2.md`;
- cualquier riesgo residual real.

No declares éxito parcial como cierre. Si un gate no puede cumplirse, deja el
repositorio en un estado coherente, conserva toda evidencia obtenida y explica
con precisión el bloqueo.
