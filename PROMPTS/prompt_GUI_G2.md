# Tarea: GUI de gruxx — Fase G2 (corregir) + fixes de G1

Proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python` (3.10).
Estado: **G0 y G1 CERRADOS** (Julian confirmó: la GUI corre desde el `.desktop`). Existen:
`gruxx_motor.py` (motor residente, `analizar()`, `serializar_arbol`), `gruxx_server.py`
(`crear_app(motor=...)` inyectable; `GET /estado`, `POST /analizar`, `GET /glosario`;
`threading.Lock` por app), `gui/` (index.html + app.js + estilo.css, JS plano sin
build/CDN), lanzador `gruxx-gui` + `gruxx.desktop`. En `correccion.py` ya existen los
no-interactivos de G0.4: `corregir_clase`, `corregir_el`, `corregir_enrutado`.
Julian commitea a mano — NO hacer commits desde la sesión.

**ADVERTENCIA OOM (12 GB):** una sola instancia del servidor; NO correr suites `--slow`
con el servidor (ni gruxx interactivo) abierto.

**PROHIBIDO tocar el motor** (igual que G0/G1): `rrg_ls_mapper.py`, `nucleo_periferia.py`,
`completeness.py`, `misc_rrg.py`, `pruebas_estructurales.py`, `ditransitivas.py`,
`causatividad.py`, `wrappers_ls.py`, `ud2rrg.py`, `convertir.py`, clasificador/.joblib,
corroborador, `contextual_sentences.csv` (solo lectura), PUD. En `correccion.py` SOLO
ajustes finos a los `corregir_*` de G0.4 si un endpoint lo exige — la lógica de
validación/persistencia/revert NO se toca ni se duplica. Terminal (`gruxx_ai1.py`, 3
modos) intacta e idéntica.

**Pendientes de MOTOR — NO arreglar, están fuera** (lista viva; la GUI los muestra tal
cual y el bucle de corrección es el paliativo diseñado): "Juan le da un pastel a María"
produce EL y clase aspectual incorrectas, y su "a María" cae a periferia siendo argumento
(sospecha: el parse en PRESENTE da otro deprel que el pretérito — si al pasar se VE la
causa, anotarla en el checkpoint con diagnóstico, sin tocar nada). + los históricos
(homógrafos, compuestas/xcomp, operadores, impersonal refleja, agente-por, "por+ruta").

---

## §0. Fixes de G1 (veredictos de Julian, hacer PRIMERO)

1. **ORDEN de constituyentes en el árbol** (bug reproducido: "Juan come pizza" se dibuja
   "come pizza Juan"; "Mario vio la película completamente" se dibuja "película la Mario
   vio completamente"). Los constituyentes agrupan BIEN; solo el orden de dibujo está mal.
   Causa esperable: `ud2rrg.transform` añade hijos en orden de PROCESAMIENTO, no de
   superficie (el render ASCII se veía bien porque `DrawTree` coloca por índice de hoja;
   el frontend dibuja el array tal cual). **Regla de Julian: el árbol sigue el MISMO orden
   lineal de la oración** — con eso el predicado queda donde cae en la oración (centro en
   SVO), que es exactamente lo que pide; NO inventar un centrado artificial del predicado.
   **Fix en `gruxx_motor.serializar_arbol`** (no en JS): ordenar `hijos` RECURSIVAMENTE
   por la hoja mínima de cada subárbol (mín. índice de token). El frontend sigue dibujando
   en el orden del array. Test frío: árbol sintético con hijos desordenados a dos niveles
   → JSON con hojas de izquierda a derecha = 0..n; verificar también el caso NP interno
   ("la película", no "película la").
2. **Logo**: `grrux_logo.png` (raíz del repo) pasa a ser (a) favicon + logo en la cabecera
   de la GUI (servirlo vía el server o copiarlo a `gui/`), (b) `Icon=` del `gruxx.desktop`
   (ruta absoluta al png). Actualizar `docs/GUI.md` si menciona el icono.

## §1. Cache de análisis (prerrequisito del bucle)

Los `corregir_*` consumen el `res` CRUDO del mapper (dict con `ls_lista`), que NO viaja al
navegador. Resolver con un cache en el motor:

- `gruxx_motor` guarda los últimos N análisis crudos (N≈20, dict ordenado, en memoria) bajo
  un `analisis_id` (uuid corto). `analizar()` añade `"analisis_id"` al contrato JSON.
- Los endpoints de corrección reciben `analisis_id` + `sub_idx`, recuperan el crudo del
  cache y llaman al `corregir_*`. Id desconocido/expirado → 404 con mensaje claro
  ("el análisis expiró — vuelve a analizar la oración"), nunca traceback.

## §2. Endpoints de corrección (en `crear_app`, mismo lock que /analizar)

- `POST /corregir/validar-el` `{analisis_id, sub_idx, el}` → resultado de `validar_el`
  (puro, SIN persistir, SIN lock — es la validación en vivo del editor).
- `POST /corregir/clase` `{analisis_id, sub_idx, clase}` → `corregir_clase` (staging).
- `POST /corregir/el` `{analisis_id, sub_idx, el}` → `corregir_el` con
  `reanalizar_fn=motor.analizar-crudo` (CON lock: re-analiza).
- `POST /corregir/enrutado` `{analisis_id, sub_idx, elemento_id, destino}` →
  `corregir_enrutado` (CON lock).
- Respuesta común: `{accion, detalle, analisis_nuevo | null}` — `accion` es la del
  `corregir_*` (`persistido` / `staging_*` / `rechazado(nivel, error)` / `cancelado`);
  `analisis_nuevo` es el CONTRATO COMPLETO del re-análisis (con su propio `analisis_id`)
  cuando lo hubo, para el diff. Errores de oración → en el cuerpo, nunca 500 crudo.

## §3. UI del bucle (gui/, mismo estilo; todo en español, terminología del glosario)

1. **Activación**: el botón "Corregir" de cada (sub)oración se habilita (hoy está
   deshabilitado con tooltip "G2"). Con Integridad ⚠, además, un aviso junto a los chips:
   "¿Análisis incorrecto? Corrígelo aquí". Abre un panel/modal con las 3 vías (pestañas o
   secciones): Clase · Estructura Lógica · Enrutado. Cerrar/Cancelar en CUALQUIER punto =
   cero efectos (garantía Esc de L5).
2. **Clase**: dropdown con las 6 clases en legible ("Estado (state)" …, las de
   `correccion.CLASES`/`CLASE_ES`) → Aplicar → banner ámbar "registrada en STAGING — el
   clasificador no se toca; el curador la promueve a mano" (texto honesto, igual que la
   terminal).
3. **Estructura Lógica**: editor monoespaciado precargado con la EL léxica actual +
   **validación EN VIVO** (debounce ~400 ms → `/corregir/validar-el`): error nivel 1/2/3
   en rojo bajo el editor con la explicación EXACTA del validador; verde "plantilla
   reconocida: X" cuando pasa. Paleta de botones de inserción: `do'` `CAUSE` `BECOME`
   `INGR` `SEML` `PURP` `have'` `Ø` `[ ]`. Botón Aplicar deshabilitado hasta validación ok.
4. **Enrutado**: lista clicable de constituyentes y periferia de la (sub)oración (texto +
   dónde está hoy: core/periferia·tipo·estrato) → dropdown de destinos (los de
   `_DESTINOS_ENRUTADO`, en legible) → Aplicar. *Stretch opcional*: seleccionar el
   elemento clicando su nodo en el árbol SVG (si complica, la lista basta — anotar).
5. **Diff confirmatorio** (tras `/corregir/el` o `/corregir/enrutado` con re-análisis):
   vista lado a lado ANTES / DESPUÉS (árbol SVG + EL léxica de ambos) + banner:
   - verde "✓ Corrección aplicada y verificada → «archivo»" (acción `persistido`), botón
     "Usar el nuevo análisis" que reemplaza la vista principal y el `analisis_id` activo;
   - ámbar "⚠ Registrada para revisión (staging) — el análisis aún no la refleja"
     (acción `staging_no_confirmado`): se muestra el diff igualmente, la vista principal
     NO cambia (el motor sigue produciendo lo mismo — honestidad ante todo).
6. **Anti-contaminación**: es LA MISMA lógica de L5 (los `corregir_*`), cero duplicación —
   `contextual_sentences.csv` jamás, `fuente=correccion_usuario`, log maestro, revert si
   no confirma. La UI no añade ningún camino de escritura propio.
7. **Opcional "corregir todo"** (clase+EL en un formulario): SOLO si sale como dos
   llamadas encadenadas a los `corregir_*` existentes, sin lógica nueva en
   `correccion.py`. Si pide lógica nueva → anotar para G3 y no hacer.

## §4. Tests

- Fríos (serializador §0): hijos ordenados recursivamente, hojas 0..n, caso NP interno.
- Rápidos (TestClient + motor STUB, patrón de los tests de G1; staging a `data_dir`
  TEMPORAL — los `corregir_*` ya lo aceptan): cache (analisis_id válido/expirado→404);
  `/corregir/validar-el` con un rechazo de CADA nivel + una válida; `/corregir/clase` →
  staging + log, `contextual_sentences.csv` intacto por mtime; `/corregir/el` confirmada
  (stub confirma → `persistido` + `analisis_nuevo`) y NO confirmada (→
  `staging_no_confirmado`, revert verificado); `/corregir/enrutado` ambas ramas; el lock
  se comparte (no hay corrección concurrente con análisis).
- `@slow` (end-to-end real, respetando OOM): UNA corrección de EL real con re-análisis.
- Suites preexistentes completas verdes; terminal idéntica (los 3 modos corren).

## Aceptación + CHECKPOINT final — PARAR aquí

1. §0 verificado con capturas: "Juan come pizza" y "Mario vio la película completamente"
   dibujadas EN ORDEN; logo visible en cabecera + favicon + icono del `.desktop`.
2. **Demo con la oración problema REAL** "Juan le da un pastel a María" (el motor la
   analiza mal HOY — es el caso de uso del bucle, no arreglar el motor):
   (a) enrutado de "a María" periferia→argumento vía UI — si el re-análisis no confirma
   y cae a staging, MOSTRARLO tal cual (es el comportamiento diseñado);
   (b) corrección de clase → staging con su banner;
   (c) EL correcta (p.ej. `[do'(Juan,Ø)] CAUSE [BECOME have'(María,pastel)]`) tecleada en
   el editor: capturas de un rechazo de cada nivel EN VIVO y de la aceptación con su diff.
3. Capturas del diff confirmatorio en verde Y en ámbar; adónde fue cada corrección
   (archivo vivo / staging / log maestro, con las filas reales).
4. Informe: decisiones de UI tomadas, si el stretch (clic en árbol) entró o no, deuda para
   G3 (lote con tabla y filtro ⚠, exportar SVG/PNG/conllu/txt, panel del curador,
   historial persistente), y cualquier pendiente de MOTOR observado (con diagnóstico si
   se vio la causa, SIN tocarla).
