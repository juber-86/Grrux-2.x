# Reforma de benefactivas: subtipos resultativos y aprendizaje desde la GUI

## Objetivo

Implementa en GRRux una subdivisión semántica de la plantilla ditransitiva
`benefactiva`, que actualmente mezcla obtención, preparación, creación, cambio
de estado y actividades realizadas para un beneficiario. La reforma debe
corregir la EL de casos como:

> Juan prepara pizzas a María todas las mañanas.

Hoy el núcleo generado es:

```text
[[do'(x, Ø)] CAUSE [BECOME have'(x, z)]] PURP [have'(y, z)]
```

Para `preparar`, la representación objetivo es:

```text
[[do'(x, Ø)] CAUSE [BECOME prepared'(z)]] PURP [BECOME have'(y, z)]
```

La salida completa debe conservar normalmente los operadores y wrappers que
correspondan a la oración. Para la oración anterior, por ejemplo, debe poder
producir:

```text
EL léxica:
⟨IF DEC ⟨TNS PRES ⟨every'(mañanas, [[[do'(juan, Ø)] CAUSE
[BECOME prepared'(pizzas)]] PURP [BECOME have'(Maria, pizzas)]])⟩⟩⟩

EL formal:
⟨IF DEC ⟨TNS PRES ⟨every'(mañanas, [[[do'(x, Ø)] CAUSE
[BECOME prepared'(z)]] PURP [BECOME have'(y, z)]])⟩⟩⟩
```

El segundo objetivo es cerrar correctamente el bucle de corrección: una EL
benefactiva corregida desde la GUI debe convertirse en conocimiento estructurado
que permita regenerar esa misma EL en usos futuros del lema. El sistema debe
poder actualizar un verbo conocido o añadir uno nuevo, pero nunca declarar una
corrección “confirmada” sólo porque coincide la etiqueta general
`benefactiva`.

Este es un **prompt ejecutor**. Inspecciona el estado real del repositorio,
implementa los cambios, añade las pruebas, ejecútalas y deja un checkpoint con
evidencia reproducida. No te limites a proponer un diseño.

## Preparación, fuentes y seguridad

Antes de editar:

1. Lee completos:
   - `Notacion_x_y.md`;
   - `CHECKPOINT_NOTACION.md`;
   - `CHECKPOINT_NOTACION_2.md`;
   - `aspect_classifier/ditransitivas.py`;
   - `aspect_classifier/correccion.py`;
   - `aspect_classifier/linking.py`;
   - `aspect_classifier/completeness.py`;
   - `rrg_ls_mapper.py`;
   - las rutas de corrección en `gruxx_motor.py`, `gruxx_server.py` y
     `gui/app.js`;
   - `aspect_classifier/test_ditransitivas.py`,
     `aspect_classifier/test_l5.py`, `test_gruxx_motor.py` y
     `test_gruxx_server.py`.
2. Inspecciona completo el esquema y contenido de
   `aspect_classifier/data/verbos_ditransitivos.xlsx`; no deduzcas su contenido
   sólo de comentarios históricos.
3. Ejecuta `git status --short`. El árbol contiene cambios previos de la
   reforma x/y/z y posiblemente archivos del usuario. Presérvalos; no uses
   `git reset`, `git checkout --`, limpiezas destructivas ni reemplazos masivos.
4. No hagas commit.
5. No uses PUD. No modifiques `ud2rrg.py`, modelos `.joblib`, embeddings,
   clasificadores, `contextual_sentences.csv`, `dataset_clean.csv`, BERTIN,
   Stanza ni `complex sentences/`.
6. LA3 y las oraciones compuestas permanecen pausadas. Esta reforma pertenece
   únicamente a la construcción de EL ditransitivas/benefactivas y a su bucle
   de corrección.
7. No reviertas la notación vigente `x/y/z` ni introduzcas variables `xN`.

Los datos contextuales ya clasifican `preparar` como una realización activa.
Este defecto no es un error del clasificador aspectual: no reentrenes modelos
para resolver una selección determinista de plantilla resultativa.

## Decisiones teóricas obligatorias

### 1. Separar construcción y subtipo semántico

Conserva `benefactiva` como familia de construcción, pero añade un subtipo
resultativo explícito y auditable. No mantengas una sola cadena rígida para
todos los verbos. Como mínimo deben existir estas familias conceptuales:

1. **Obtención/adquisición**, por ejemplo `comprar` y `conseguir`:

   ```text
   [[do'(x, Ø)] CAUSE [BECOME have'(x, z)]]
   PURP [BECOME have'(y, z)]
   ```

2. **Preparación**, por ejemplo `preparar`, `cocinar` y `hornear`:

   ```text
   [[do'(x, Ø)] CAUSE [BECOME prepared'(z)]]
   PURP [BECOME have'(y, z)]
   ```

3. **Creación**, por ejemplo `crear` y `fabricar`:

   ```text
   [[do'(x, Ø)] CAUSE [BECOME exist'(z)]]
   PURP [BECOME have'(y, z)]
   ```

4. **Cambio de estado o servicio sobre un objeto existente**, por ejemplo
   `reparar`, `lavar` o `limpiar`. El resultado debe ser un predicado de estado
   monovalente explícito (`repaired'(z)`, `clean'(z)` u otro valor curado), no
   una posesión ficticia de `x`. El propósito puede ser posesión estativa:

   ```text
   [[do'(x, Ø)] CAUSE [BECOME repaired'(z)]]
   PURP [have'(y, z)]
   ```

5. **Actividad benefactiva sin resultado causado garantizado**, necesaria para
   verbos como `buscar`, `elegir`, `pedir`, `reservar`, `guardar` o casos
   semejantes cuando la semántica no licencia afirmar que `x` obtuvo, creó o
   cambió internamente `z`. Usa una plantilla explícita de actividad con
   propósito, por ejemplo:

   ```text
   do'(x, [<lema>'(x, z)]) PURP [BECOME have'(y, z)]
   ```

   No fuerces `CAUSE [BECOME ...]` si el verbo no entraña ese resultado.

Puedes afinar los nombres internos de estos subtipos después de revisar la
arquitectura, pero deben ser estables, legibles, serializables y distinguibles
por el corrector. Documenta cualquier ajuste teórico. No uses una heurística
ciega que derive automáticamente el predicado inglés de cualquier lema
español: emplea un inventario resultativo curado. Los predicados nuevos de este
inventario no autorizan una traducción general de los predicados de GRRux al
inglés.

### 2. Propósito y alcance

Representa por separado el tipo de resultado principal y la forma de la
cláusula `PURP`. Como mínimo, el dato debe poder distinguir:

- `PURP [BECOME have'(y, z)]`: propósito de que el beneficiario llegue a
  poseer/recibir el tema;
- `PURP [have'(y, z)]`: estado de posesión pertinente, especialmente cuando el
  objeto ya pertenece al beneficiario;
- cualquier ausencia de propósito que la arquitectura necesite representar,
  sin inventarlo silenciosamente.

`PURP` introduce un propósito, no una afirmación de que el destinatario llegó
efectivamente a poseer el objeto.

### 3. Variables y posiciones

Mantén en todos los subtipos:

- `x`: efectuador y Actor, primer argumento de `do'`;
- `y`: beneficiario/poseedor, NMR en la construcción española relevante;
- `z`: tema, producto u objeto afectado, normalmente Undergoer;
- `prepared'(z)`, `exist'(z)`, `repaired'(z)`, etc. como predicados de estado
  monovalentes: `z` ocupa `arg_estado`;
- `have'(y,z)` como predicado bivalente: `y` ocupa `1_pred_xy` y `z`,
  `2_pred_xy`.

Una variable puede aparecer en más de un frame semántico sin convertirse en
dos argumentos sintácticos. Linking, completitud, trazas y MISC deben deduplicar
por identidad argumental/token cuando corresponda, pero conservar todas las
posiciones semánticas necesarias para justificar la AUH.

No cambies las plantillas de transferencia o comunicación salvo adaptaciones
internas indispensables y cubiertas por pruebas. En transferencia debe seguir
siendo válido:

```text
[do'(x, Ø)] CAUSE [BECOME have'(y, z)]
```

## 1. Evolución del léxico ditransitivo

Amplía `aspect_classifier/data/verbos_ditransitivos.xlsx` con un esquema capaz
de representar, como mínimo:

- lema;
- familia principal (`transferencia`, `benefactiva`, `comunicacion`);
- subtipo benefactivo;
- predicado resultativo cuando corresponda;
- modalidad del propósito (`become_have`, `have`, `none` o nombres equivalentes
  claramente documentados);
- ambigüedad;
- notas/fuente.

Requisitos:

- La carga debe ser compatible con filas de transferencia/comunicación que no
  necesiten los campos benefactivos.
- Valida enums, combinaciones y predicados al cargar. Una fila incoherente debe
  fallar con un diagnóstico útil, no caer silenciosamente a `have'`.
- Audita **todos** los verbos actualmente etiquetados como benefactivos. No
  asignes en bloque un subtipo por semejanza ortográfica. Registra en notas las
  decisiones ambiguas o conservadoras.
- Como mínimo, cura explícitamente `comprar`, `conseguir`, `preparar`,
  `cocinar`, `hornear`, `crear`, `fabricar`, `reparar`, `lavar`, `limpiar` y
  los verbos usados en las pruebas nuevas.
- Si un lema tiene lecturas incompatibles que el contexto actual no permite
  distinguir, conserva `ambiguo=True`, registra candidatos y evita que una
  corrección sobrescriba silenciosamente otra lectura. Puedes ampliar la clave
  con un discriminador de construcción disponible (`dativo`, `para`, etc.),
  pero no inventes una desambiguación contextual que GRRux no pueda aplicar.
- Conserva trazabilidad de migración y correcciones del usuario.

## 2. Generación de EL y representación estructurada

Refactoriza `aspect_classifier/ditransitivas.py` para que la EL benefactiva se
construya desde una especificación estructurada, no desde una cadena única
codificada para toda la familia.

La salida de `construir_ditransitiva` y el objeto `ditransitiva` integrado en
el mapper deben exponer, además de lo ya existente, el subtipo, el predicado
resultativo y la modalidad de propósito. Evita duplicar fuentes de verdad.

Actualiza `ls_estructura` para representar realmente:

- el frame `do'` y su efectuador;
- el frame resultativo monovalente (`prepared'`, `exist'`, `repaired'`, etc.)
  cuando exista;
- el frame `have'` de propósito y su NMR cuando exista;
- la posición de `z` en cada frame pertinente.

No dejes una EL textual con `prepared'(z)` acompañada de una estructura interna
que sólo diga `have'(y,z)`. La forma, los metadatos y la estructura deben ser
isomorfos.

Revisa e integra las consecuencias en:

- `rrg_ls_mapper.py`;
- `aspect_classifier/linking.py`;
- `aspect_classifier/completeness.py`;
- `aspect_classifier/misc_rrg.py`;
- `aspect_classifier/display_grr.py`;
- contratos del motor/JSON y GUI que consuman `ditransitiva` o
  `ls_estructura`.

Linking debe seguir dando `Actor=x`, `Undergoer=z`, `y=NMR` en los ejemplos
objetivo. La repetición de `z` en resultado y propósito no debe duplicar la
M-transitividad, generar dos Undergoers, duplicar argumentos en la GUI ni crear
falsos errores de completitud.

## 3. Corrector y aprendizaje controlado desde GRRux GUI

El defecto actual es específico: `reconocer_plantilla` clasifica cualquier EL
con `CAUSE + have' + PURP` como la misma benefactiva; la persistencia guarda
sólo `lema → benefactiva`; y la confirmación comprueba únicamente esa etiqueta.
Elimínalo de raíz.

### 3.1 Reconocimiento semántico

Haz que la validación/reconocimiento de una EL corregida produzca una
especificación estructurada, por ejemplo:

```text
familia=benefactiva
subtipo=preparacion
predicado_resultado=prepared'
aridad_resultado=1
proposito=become_have
```

No basta buscar por substrings. Verifica estructura, alcance, aridad y posición
de variables/argumentos. Deben distinguirse al menos las cinco familias
conceptuales anteriores. Rechaza disposiciones incompatibles con mensajes
explicativos.

Los wrappers y operadores exteriores válidos no deben impedir reconocer y
comparar el núcleo corregido. Reutiliza los mecanismos actuales de composición
o implementa una canonicalización acotada; no escribas un segundo parser
general de RRG si el proyecto ya ofrece helpers reutilizables.

### 3.2 Persistencia como upsert

Sustituye la inserción ciega actual por un **upsert atómico y auditable**:

- verbo conocido + misma clave de construcción: actualiza sus campos
  benefactivos y conserva una nota de cambio;
- verbo desconocido: añade una fila válida completa;
- misma corrección repetida: `no-op`, sin aumentar filas;
- lectura conflictiva sin discriminador suficiente: no destruye la lectura
  anterior; deja el caso en staging o conserva ambas mediante una clave que el
  selector pueda resolver realmente;
- nunca deben quedar dos filas activas indistinguibles para el mismo lema y la
  misma construcción;
- el token de `revert` debe restaurar exactamente la fila anterior o eliminar
  sólo la fila recién añadida.

Actualiza también el léxico cargado en memoria sin reiniciar el proceso, usando
la misma especificación persistida.

### 3.3 Confirmación exacta

Después de persistir, reanaliza la oración una sola vez y confirma como mínimo:

- familia y subtipo;
- predicado resultativo;
- modalidad y alcance de `PURP`;
- EL léxica regenerada equivalente a la corrección tras una normalización
  segura de espacios/wrappers;
- EL formal coherente con la vinculación `x/y/z`;
- estructura semántica y argumentos sin divergencias.

Comparar solamente `ditransitiva.plantilla == "benefactiva"` está prohibido.
Si la EL exacta no se reproduce, revierte el léxico vivo y guarda en staging la
corrección completa y la razón concreta de la no confirmación.

### 3.4 Auditoría y GUI

El log y/o staging debe conservar suficiente información para reconstruir la
decisión:

- oración y lema;
- EL anterior y EL propuesta;
- familia/subtipo/predicado/proposito inferidos;
- acción (`insert`, `update`, `no-op`, `staging_conflicto`, `revert`, etc.);
- destino y fuente `correccion_usuario`;
- motivo de rechazo o falta de confirmación.

Mantén el flujo de la GUI sencillo para el lingüista: escribe la EL correcta y
GRRux deriva el destino. No añadas una selección manual de archivo. La respuesta
de API y el mensaje GUI deben informar qué conocimiento se añadió o actualizó
y sólo usar “aplicada y verificada” después de la confirmación exacta.

La corrección de una oración con un lema no presente debe demostrar que el
siguiente análisis del mismo patrón usa la nueva subdivisión. Una corrección de
un lema ya presente debe actualizarlo sin duplicarlo.

## 4. Compatibilidad y migración de datos

- Migra el libro existente sin perder filas, notas ni marcas de ambigüedad.
- No uses el orden de las filas como lógica de selección.
- Conserva transferencias y comunicaciones byte-semánticamente equivalentes.
- Si mantienes compatibilidad temporal con filas benefactivas antiguas, el
  fallback debe ser explícito, diagnosticable y tener una prueba. Al terminar
  la migración no debe quedar ninguna fila benefactiva activa sin decisión de
  subtipo o marca inequívoca de revisión.
- No conviertas `correcciones_el.csv` ni `contextual_sentences.csv` en una
  fuente ejecutable automática sin validación. El primero sigue siendo staging;
  el segundo sigue siendo curado y append-only fuera de este hito.

## 5. Pruebas obligatorias

Añade pruebas unitarias, de integración y del corrector. Usa comparaciones
exactas de EL donde el contrato sea canónico.

### 5.1 Generación y semántica

Cubre como mínimo:

1. `Juan prepara pizzas a María`:
   - subtipo preparación;
   - `BECOME prepared'(z)`;
   - `PURP [BECOME have'(y,z)]`;
   - nunca `BECOME have'(x,z)`.
2. Una construcción equivalente con `para María`, si el análisis UD la trata
   como benefactiva.
3. `cocinar`: resultado de preparación, sin posesión de `x` como resultado
   principal.
4. `crear`: `BECOME exist'(z)`.
5. `comprar`: conserva obtención `BECOME have'(x,z)` y añade/verifica
   `PURP [BECOME have'(y,z)]`.
6. Un cambio de estado o servicio, preferentemente `reparar`: resultado
   monovalente curado y propósito estativo cuando corresponda.
7. Una actividad benefactiva sin resultado entrañado, como `buscar`, para
   demostrar que no se inventa `BECOME have'(x,z)`.
8. Transferencia (`dar`) y comunicación (`decir`) sin regresiones.
9. Wrappers temporales y operadores: `todas las mañanas`, tiempo y fuerza
   ilocutiva permanecen por fuera y no alteran el núcleo.

En cada caso pertinente verifica `ls_formal`, `ls_lexical`, `variables`,
`id_a_var`, `args_map`, `ls_estructura`, macropapeles, NMR, M-transitividad,
completitud, MISC, contrato del motor y JSON.

### 5.2 Léxico y corrección

Cubre con directorios/archivos temporales, sin contaminar los datos reales:

- carga y validación del esquema nuevo;
- migración de las filas existentes;
- corrección de `preparar` a preparación;
- alta de un verbo desconocido mediante una EL benefactiva válida;
- reanálisis posterior que usa el conocimiento nuevo;
- upsert de un verbo conocido sin duplicar filas;
- repetición idéntica como `no-op`;
- conflicto polisémico que no sobrescribe silenciosamente;
- rechazo de predicado/aridad/variables incompatibles;
- fallo de confirmación exacta que revierte y manda la EL completa a staging;
- comprobación de que el antiguo falso positivo —misma familia pero EL
  regenerada distinta— ya no puede devolver `persistido`;
- corrección con notación heredada `x1/x2/x3` rechazada;
- log de auditoría con antes/después y especificación inferida.

### 5.3 GUI y servidor

Amplía las pruebas del endpoint existente de validación/corrección y, si hace
falta, el contrato JS. Comprueba que:

- la EL con `prepared'` se valida y reconoce como el subtipo correcto;
- la API devuelve insert/update/no-op/staging de forma inequívoca;
- la GUI muestra el resultado real de la confirmación;
- un reanálisis fresco devuelve la EL corregida;
- no se duplica el lema en el xlsx;
- el JSON conserva `x/y/z` y los nuevos metadatos.

No dependas exclusivamente de mocks que devuelvan el subtipo esperado: añade
al menos una prueba lenta end-to-end con el mapper real y los modelos locales.

## 6. Gates de ejecución

Ejecuta en orden y corrige cualquier regresión de este hito antes de avanzar.
No copies resultados de checkpoints anteriores como si fueran una ejecución
nueva.

### 6.1 Gate focal rápido

```bash
./venv/bin/python -m pytest -q \
  aspect_classifier/test_ditransitivas.py \
  aspect_classifier/test_l5.py \
  aspect_classifier/test_linking.py \
  aspect_classifier/test_completeness.py \
  aspect_classifier/test_misc_rrg.py \
  aspect_classifier/test_notacion.py \
  test_gruxx_motor.py
```

Ejecuta el servidor por separado y acotado:

```bash
timeout 90s ./venv/bin/python -m pytest -q test_gruxx_server.py
```

Si vuelve a bloquearse al ejecutarse aislado, identifica el test con
`pytest -vv -s -x` bajo el mismo timeout y registra la limitación conocida; no
ocultes el timeout ni cambies el servidor salvo que esta reforma haya
introducido la regresión.

### 6.2 Pruebas lentas focales

Ejecuta una por una, sin una GUI/servidor adicional abierto:

```bash
./venv/bin/python -m aspect_classifier.test_ditransitivas --slow
RUN_SLOW=1 ./venv/bin/python -m pytest -q aspect_classifier/test_l5.py
RUN_SLOW=1 ./venv/bin/python -m pytest -q aspect_classifier/test_notacion.py
```

Incluye la nueva prueba end-to-end de `preparar` y la prueba real del bucle de
corrección por el mecanismo `--slow`/`RUN_SLOW=1` coherente con el módulo.

### 6.3 Suite rápida completa

```bash
./venv/bin/python -m pytest -q
```

Si el consumo de recursos exige dividirla, documenta exactamente los grupos,
resultados y omisiones. No borres caches, logs o datos curados para conseguir
un resultado verde.

### 6.4 Verificación GUI/JSON

Con una instancia aislada de GRRux, comprueba al menos:

- `Juan prepara pizzas a María todas las mañanas`;
- `Juan compró un regalo para María`;
- una corrección que añada un lema desconocido en un directorio de datos de
  prueba o entorno aislado, sin contaminar el léxico curado real.

Inspecciona respuesta JSON y DOM. Detén la instancia al terminar.

## 7. Documentación y entrega

Crea `CHECKPOINT_BENEFACTIVAS.md` con:

- decisiones teóricas y esquema final;
- tabla de verbos auditados y subtipo asignado;
- EL canónicas finales;
- funcionamiento del aprendizaje desde GUI;
- comportamiento de upsert, conflictos y revert;
- archivos modificados;
- comandos y resultados reales de pruebas;
- validación GUI/JSON;
- limitaciones o casos enviados a staging;
- confirmación explícita de que no se tocaron modelos, entrenamiento, PUD,
  `contextual_sentences.csv`, `ud2rrg.py`, LA3 ni oraciones compuestas.

Actualiza `ESTADO_DEL_ARTE_GRUXX.md` sólo después de superar los gates. Mantén
LA3 y oraciones compuestas como pausadas.

Al finalizar, entrega un resumen conciso con las EL resultantes de `preparar`,
`crear`, `comprar` y `reparar`, resultados de pruebas, archivos cambiados y
cualquier limitación. No hagas commit.

## Criterios de cierre

El hito sólo está completo si se cumplen simultáneamente estas condiciones:

- `preparar` ya no genera posesión de `x` como resultado;
- los subtipos benefactivos se seleccionan desde datos curados;
- texto, estructura, Linking, Completeness, MISC, motor y GUI concuerdan;
- una corrección GUI puede actualizar un lema conocido o añadir uno nuevo;
- la confirmación compara la semántica/EL específica regenerada;
- los upserts no duplican filas y los conflictos no destruyen lecturas;
- transferencia y comunicación no sufren regresiones;
- la notación permanece exclusivamente en `x/y/z`;
- pasan los gates focales y la suite completa, o queda documentada con
  precisión cualquier limitación ambiental preexistente.
