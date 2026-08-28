# Hito NOTACIÓN-1  — Migración  de x1/x2/x3 a variables RRG x/y/z

## Objetivo

Sustituir transversalmente la numeración interna `x1/x2/x3` por la notación
correcta de RRG `x/y/z`. No hacer un reemplazo textual: las letras deben
derivarse de la posición de cada participante en la Estructura Lógica.

LA3 está pausada. Esta tarea no amplía el linking ni implementa oraciones
compuestas.

Este documento es un **prompt ejecutor de NOTACIÓN-1**. Debes escribir el
código, actualizar las pruebas y ejecutar su gate. No te limites a proponer un
plan. Al superar el gate, cierra NOTACIÓN-1 y detente; NOTACIÓN-2 se ejecuta
separadamente con su propio prompt y evidencia.

Leer antes de modificar:

- `Notacion_x_y.md`
- `ESTADO_DEL_ARTE_GRUXX.md`
- `CHECKPOINT_LA1.md`
- `CHECKPOINT_L2_5_DITRANSITIVAS.md`

## Línea base

Antes de implementar se verificaron las suites rápidas directamente
relacionadas con la notación:

```text
144 passed, 12 skipped
```

La ejecución conjunta que incluía `test_gruxx_server.py` quedó esperando al
final. Esa suite debe ejecutarse aisladamente y con un límite de tiempo para
distinguir un problema de infraestructura preexistente de una regresión.

## Invariantes teóricos

- Los predicados primitivos son monovalentes o bivalentes: `pred'(x)` y
  `pred'(x, y)`.
- No crear predicados primitivos `pred'(x, y, z)`.
- Actividad transitiva: `do'(x, [pred'(x, y)])`.
- Locativo: `be-in'(x, y)`, con `x=locación` y `y=figura`.
- Causativa activa: `[do'(x, Ø)] CAUSE [β(y)]`.
- Si el causante es `Ø`, el argumento resultante conserva `y`:
  `[do'(Ø, Ø)] CAUSE [β(y)]`.
- Transferencia: `[do'(x, Ø)] CAUSE [BECOME have'(y, z)]`.
- Benefactiva:
  `[[do'(x, Ø)] CAUSE [BECOME have'(x, z)]] PURP [have'(y, z)]`.
- Comunicación simplificada:
  `do'(x, [<lema>.to.(y)'(x, z)])`.
- En ditransitivas, `x=efectuador/emisor`, `y=poseedor/receptor` y
  `z=tema/contenido`.
- Las variables se asignan por estructura semántica, nunca por orden
  superficial.
- `z` sólo se permite cuando una plantilla compuesta licencia tres
  participantes.
- La EL léxica conserva los participantes concretos.
- El tercer participante de una ditransitiva no constituye un tercer
  macrorrol: continúa siendo un argumento central no macrorrol cuando así lo
  determine la plantilla.

## Problemas actuales que debe resolver el hito

1. El mapper numera los argumentos recorriendo `roles["core"]`. En pasivas
   esto puede ligar `x1/x2` por orden superficial y no por macrorrol.
2. En ditransitivas, el mapeo ordinal actual es `x1=efectuador`, `x2=tema` y
   `x3=poseedor/receptor`. Por tanto, el cambio correcto es `x1→x`, `x2→z` y
   `x3→y`, no un reemplazo secuencial.
3. Los locativos copulativos imprimen una variable para la locación, pero la
   rama no conserva ambos participantes de manera coherente en `variables` e
   `id_a_var`.
4. La plantilla formal de comunicación introduce actualmente el receptor
   léxico dentro del nombre del predicado. La EL formal debe usar `y`; el
   participante concreto pertenece a la EL léxica.
5. `variables`, `id_a_var`, `args_map`, MISC, completitud, linking, motor y
   GUI comparten las variables numeradas como contrato transversal.

## Implementación

### 1. Contrato central de variables

Añadir una fuente central y reutilizable para:

- el inventario válido `x`, `y`, `z`;
- su orden canónico;
- la detección de variables heredadas `x1/x2/x3` o, en general, `xN`;
- mensajes claros de incompatibilidad;
- validación de los valores que se escriben en `variables`, `id_a_var`,
  `RRGVar` y `RRGArgVar`.

No implementar una conversión automática `xN→letra`, porque el mapeo depende
de la plantilla semántica.

### 2. Refactor del mapper

- Eliminar el contador `x{idx}` como fuente de identidad semántica.
- Construir explícitamente `variables`, `id_a_var` y `args_map` según la
  plantilla seleccionada.
- En construcciones bivalentes, asignar las letras según las posiciones de
  la EL y la AUH, no según el orden de tokens.
- Corregir la pasiva perifrástica para que Actor y Undergoer conserven la
  misma identidad que en la voz activa correspondiente.
- En construcciones monovalentes no causativas usar `x`.
- En una causativa conservar `x` para el causante y `y` para el argumento de
  la estructura resultante. Si el causante es `Ø`, el resultado continúa
  siendo `y` por decisión del proyecto.
- No asignar `z` a un tercer argumento de una plantilla genérica. Si un
  argumento explícito no tiene una posición licenciada en la EL, emitir un
  diagnóstico de análisis incompleto en lugar de inventar un predicado
  trivalente.
- Cada rama especial —copulativa, causativa y ditransitiva— debe devolver su
  propio mapa estructurado completo, sin depender del `args` ordinal creado
  antes de conocer la plantilla.

### 3. Constructores de EL

Migrar y probar:

- estados, actividades, logros, realizaciones, semelfactivos y realizaciones
  activas;
- copulativas atributivas;
- locativos `be-in'/be-at'/...`, conservando `x=locación` y `y=figura` tanto
  en la cadena formal como en los campos estructurados;
- causativas activas y anticausativas/pasivas con causante `Ø`;
- transferencia con `have'(y, z)`;
- benefactiva con `have'(x, z)` y `have'(y, z)`;
- comunicación simplificada con receptor formal `y` y contenido `z`.

Los wrappers de periferia sólo deben envolver la EL resultante; no deben
renombrar variables ni crear `z`.

### 4. Contratos y consumidores

Actualizar conjuntamente:

- `args_map` y su parser de reconciliación;
- `variables` e `id_a_var`;
- linking, trazas y paso 5;
- completitud e integridad;
- MISC `RRGVar` y `RRGArgVar`;
- lectura directa de CoNLL-U;
- validación de EL corregidas;
- contrato JSON del motor (`argumentos[].var`);
- resaltado de variables en la GUI;
- textos user-friendly que todavía muestren ejemplos `x1/x2/x3`.

El resaltado de la GUI debe reconocer únicamente variables completas
`x`, `y`, `z`; no debe marcar letras dentro de predicados o palabras.

No renombrar los atributos geométricos SVG `x1`, `x2`, `y1`, `y2` de
`gui/app.js`: pertenecen al estándar SVG y no son variables RRG.

### 5. Corte estricto con la notación anterior

No mantener un modo mixto ni convertir silenciosamente archivos antiguos.

- Una EL corregida que contenga `xN` debe rechazarse en el nivel de
  consistencia con un mensaje que indique que usa la notación anterior.
- Un CoNLL-U con `RRGVar=xN`, `RRGArgVar=xN` o comentarios de EL formal con
  variables numeradas debe rechazarse claramente.
- Las nuevas salidas sólo pueden emitir `x`, `y`, `z`.
- No reescribir automáticamente archivos históricos.

## Interfaces resultantes

- `ls_formal`: sólo `x/y/z`.
- `args_map`: entradas encabezadas por `x:`, `y:` o `z:`.
- `variables`: diccionario ordenado canónicamente por `x`, `y`, `z`.
- `id_a_var`: valores limitados a `x`, `y`, `z`.
- MISC: `RRGVar=x|y|z` y `RRGArgVar=x|y|z`.
- GUI/API: `argumentos[].var` limitado a `x`, `y`, `z`.

La EL léxica no debe sustituirse por variables: continúa mostrando los
participantes concretos.

## Casos de aceptación

1. `Juan comió pizza`
   - formal: `do'(x, [comer'(x, y)])`;
   - `x=Juan`, `y=pizza`.
2. `Juan corrió`
   - formal: `do'(x, [correr'(x)])`;
   - `x=Juan`.
3. `El pastel fue comido por Juan`
   - Actor `Juan=x`;
   - Undergoer `pastel=y`;
   - resultado independiente del orden superficial.
4. `Juan está en la biblioteca`
   - formal locativa con `x=biblioteca`, `y=Juan`;
   - ambos participantes presentes en `variables` e `id_a_var` cuando
     tengan token rastreable.
5. `Juan rompió la ventana`
   - causante `x=Juan`;
   - paciente `y=ventana`.
6. `El jarrón se rompió`
   - causante `Ø`;
   - paciente formal `y=jarrón`.
7. `Juan le dio flores a María`
   - `[do'(x, Ø)] CAUSE [BECOME have'(y, z)]`;
   - `x=Juan`, `y=María`, `z=flores`;
   - `y` continúa como NMR/Poseedor y `z` como Undergoer/Tema.
8. `Juan compró un regalo para María`
   - plantilla benefactiva;
   - `x=Juan`, `y=María`, `z=regalo`.
9. `Le dije la verdad`
   - formal: `do'(x, [decir.to.(y)'(x, z)])`;
   - emisor pro-drop `x`, receptor morfológico `y`, contenido `z`.
10. Una EL con `x1` y un CoNLL-U con `RRGVar=x2` se rechazan explícitamente.

## Pruebas rápidas obligatorias

Añadir o actualizar pruebas exactas para:

- constructores monovalentes y bivalentes;
- actividad transitiva;
- locativo con ambos argumentos estructurados;
- pasiva perifrástica independiente del orden superficial;
- causativa activa y causante `Ø`;
- transferencia, benefactiva y comunicación;
- pro-drop y AGX;
- MISC write/read con `x/y/z`;
- rechazo de MISC, comentarios CoNLL-U y EL con `xN`;
- completitud, linking, reconciliación, motor y contrato GUI;
- wrappers y operadores sin alteración semántica.

Ejecutar al menos:

```bash
./venv/bin/python -m pytest -q \
  aspect_classifier/test_ditransitivas.py \
  aspect_classifier/test_causatividad.py \
  aspect_classifier/test_linking.py \
  aspect_classifier/test_completeness.py \
  aspect_classifier/test_misc_rrg.py \
  aspect_classifier/test_wrappers_ls.py \
  test_gruxx_motor.py
```

Ejecutar `test_gruxx_server.py` por separado y con límite de tiempo. Comparar
los resultados con la línea base de `144 passed, 12 skipped` y documentar
cualquier diferencia.

Hacer una auditoría final con `rg` para localizar restos semánticos de
`x1/x2/x3`. Clasificar los resultados en:

- código activo que debe migrarse;
- pruebas que deben actualizarse;
- documentación histórica que debe conservarse;
- coordenadas SVG que no deben tocarse.

## Prohibiciones

- No tocar `ud2rrg.py`.
- No modificar clasificadores, corroborador, `.joblib` ni datasets curados.
- No modificar `contextual_sentences.csv`.
- No ejecutar PUD.
- No reescribir checkpoints, prompts o sesiones históricas.
- No iniciar LA3 ni implementar oraciones compuestas.
- No ejecutar pruebas lentas con la GUI abierta.
- No hacer reemplazos masivos sin revisar la función semántica de cada
  variable.

## Cierre del hito

Entregar:

1. código activo migrado a `x/y/z`;
2. pruebas rápidas verdes;
3. tabla antes/después de las EL canónicas;
4. lista de argumentos detectados sin posición licenciada;
5. evidencia de que no quedan variables numeradas en código semántico activo;
6. resultado aislado de `test_gruxx_server.py`.

El gate para continuar es: suites rápidas relacionadas verdes, rechazo estricto
de entradas heredadas probado y auditoría sin `xN` semánticos en código activo.
Si el gate se cumple, aconsejar ejecutar NOTACIÓN-2 en una sesión separada.

para aquí
---
