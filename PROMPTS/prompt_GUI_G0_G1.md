# Tarea: GUI de gruxx — Fases G0 (motor como API) + G1 (ver)

Proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python` (3.10). Entry point
actual: `python3 gruxx_ai1.py` (terminal — SIGUE SIENDO interfaz soportada para siempre).
Estado de partida: post-L5 + Etapa PERIFERIA (CHECKPOINT_PERIFERIA.md, 2026-07-13): periferia
tipada SIN "otro" ({aspectual, manera, locativo, temporal, frecuencia, razon, concesion,
condicion, epistemico, generico}), campo `estrato` ∈ {nucleo, centro, clausula} en cada item,
anclaje del árbol scope-driven vía MISC `RRGStratum`. KPI vigente: conversión 98%, acuerdo por
estrato 67.3%, completeness 96.3%. Suites frías todas verdes. Julian commitea a mano ANTES de
esta fase — NO hacer commits desde la sesión.

**ADVERTENCIA OOM (12 GB):** el servidor carga Stanza+BERTIN residentes (~2 GB) — UNA sola
instancia (`workers=1`); NO correr suites `--slow` con el servidor (ni gruxx interactivo)
abierto.

**PROHIBIDO tocar el motor** — la GUI es SOLO capa de presentación:
- `rrg_ls_mapper.py`, `nucleo_periferia.py`, `completeness.py`, `misc_rrg.py`,
  `pruebas_estructurales.py`, `ditransitivas.py`, `causatividad.py`, `wrappers_ls.py`,
  `ud2rrg.py`, `convertir.py`: CERO cambios.
- Clasificador (`predict.py`/`classifier.py`/`decision_tree.py`/`.joblib`), corroborador,
  `contextual_sentences.csv` (solo lectura), PUD: intocados, como siempre.
- Excepciones quirúrgicas autorizadas: (a) `correccion.py` puede ganar FUNCIONES NUEVAS
  no-interactivas (wrappers finos sobre las piezas existentes — sin duplicar ni alterar la
  lógica de validación/persistencia/revert); (b) `gruxx_ai1.py` puede refactorizarse
  mínimamente para compartir el pipeline con el motor — condición dura: los 3 modos de la
  terminal corren idénticos y todas las suites existentes siguen verdes. Si el riesgo no
  compensa, dejar `gruxx_ai1.py` intacto y que el motor tenga su propia copia del pipeline
  (documentando la duplicación como deuda consciente).
- Los pendientes lingüísticos (homógrafos, compuestas/xcomp, operadores, impersonal refleja,
  agente-por, "por+ruta" locativo, lo/la→AGX) SIGUEN FUERA. La GUI muestra lo que el motor
  produce hoy; si algo se ve mal en pantalla por un pendiente del motor, se ANOTA en el
  checkpoint, no se arregla.

Decisiones de diseño CERRADAS (Julian, 2026-07-13): app web LOCAL (no Qt); frontend JS plano
SIN paso de build y SIN CDN (todo archivo local — la carpeta debe poder copiarse a otra
máquina y funcionar offline); prompt-primero con checkpoint intermedio para aprobar el
contrato JSON antes de construir la UI encima; fases G0→G1 en este prompt, G2 (corrección en
UI) y G3 (lote/exportaciones/panel del curador) en prompts posteriores.

---

## G0 — El motor como API interna

### G0.1 Módulo `gruxx_motor.py` (raíz del repo)

Extraer el pipeline de análisis a un módulo importable, sin Stanza a nivel de import:

- `cargar()` — inicializa y deja RESIDENTES el pipeline Stanza y el clasificador (importar
  `rrg_ls_mapper` ya carga el clasificador; Stanza se crea aquí). Idempotente.
- `analizar(oracion: str) -> dict` — pipeline completo de `gruxx_ai1.procesar_oracion`
  (Stanza → conllu → limpiar → mapper → inyectar MISC → árboles in-process → completeness),
  con DOS cambios respecto a la CLI:
  1. **Archivo `.conllu` temporal POR LLAMADA** (`tempfile`, borrado al terminar) — el motor
     NO pisa `input_estudiante.conllu` (ese queda para la CLI).
  2. **Sin subprocess `convertir.py`**: el árbol para la GUI es el in-process
     (`_arboles_inprocess`, el MISMO `transform` que ya alimenta al checker — verificado en
     L4). El ASCII no se necesita en pantalla. El render ASCII/`.txt` sigue siendo asunto de
     la CLI, intacto.
- `estado() -> dict` — `{listo: bool}` (para que el frontend muestre "cargando modelos…").

### G0.2 Serialización del árbol

`ParentedTree` → dict anidado JSON-able: nodos `{"label": str, "hijos": [...]}`, hojas
`{"token": int}`. OJO documentado en `completeness.py`: las hojas del ParentedTree son
ÍNDICES 0-based de posición (`token_id - 1`), NUNCA texto — el JSON lleva el índice y el
frontend resuelve el texto contra la lista de tokens. Función pura, testeable en frío con
árboles sintéticos (patrón de `test_completeness.py`).

### G0.3 Contrato JSON de `analizar()` (borrador — Julian lo aprueba en el checkpoint G0)

Campos ESTRUCTURADOS (nunca parsear los strings legados `args_map`/`morph_note` en el
frontend — se construyen desde `core`/`id_a_var`/`roles_tematicos`/`vector` del dict del
mapper):

```
{ "oracion": str,
  "sub_oraciones": [ {
      "tokens":     [ {"id": int(1-based), "texto": str, "lema": str} ],
      "arbol":      {nodo anidado de G0.2} | null,        // null = no convirtió
      "el":         { "tipo": str, "tipo_legible": str,   // display_grr.clase_legible
                      "formal": str, "lexical": str },
      "argumentos": [ {"var": "x1", "token_id": int|null, "texto": str,
                       "deprel": str, "papel": str} ],    // papel = macropapel o rol temático
      "rasgos":     { "estatico": f, "dinamico": f, "telico": f, "puntual": f,
                      "confianza": f, "metodo": str } | null,
      "notas":      [str],                                 // display_grr.traducir_apendices
      "causatividad": {"tipo": str, "fuente": str, "confianza": f} | null,
      "integridad": { "ok": bool|null, "checks": [dicts de completeness],
                      "linea": str },                      // display_grr.linea_integridad
      "periferia":  [ {"id": int, "texto": str, "tipo": str, "estrato": str,
                       "wrap": str|null} ],
      "agx":        [ {"clitico": str, "fuente": str, "doblado": bool, "token_id": int} ],
      "actor_implicito": {"etiqueta": str} | null,
      "impersonal": bool,
      "crudo":      { "morph_note": str, "resumen_completeness": str }  // toggle --verbose
  } ],
  "error": str | null }
```

### G0.4 API de corrección no-interactiva (en `correccion.py`, funciones NUEVAS)

Para G2, pero se dejan listas aquí porque el refactor toca el mismo archivo una sola vez:
- `corregir_clase(res, sub_idx, clase_correcta, data_dir=None) -> dict` (staging, como
  `_flujo_clase` sin menú),
- `corregir_el(res, sub_idx, el_texto, reanalizar_fn, data_dir=None) -> dict` (validación 3
  niveles + persistir/confirmar/revertir — reusar `_procesar_el_texto`),
- `corregir_enrutado(res, sub_idx, elemento_id, destino, reanalizar_fn, ...) -> dict`.
Los `_flujo_*` interactivos pasan a LLAMAR a estas funciones (una sola lógica). La terminal
queda idéntica: `test_l5` completo verde sin cambios de aserción (salvo renombres internos).

### G0.5 Tests G0 (fríos) + CHECKPOINT INTERMEDIO — PARAR

- Serialización: árbol sintético → JSON esperado (hojas 0-based, AGX, -PERI).
- Contrato: con un `ls` de fixture (sin modelos), `construir_respuesta(...)` produce todas
  las claves con los tipos correctos; `argumentos` NO viene de parsear `args_map`.
- Corrección no-interactiva: los 3 `corregir_*` con stub de `reanalizar` (patrón exacto de
  `test_l5`), incluido el camino no-confirmado→revert→staging.
- Suites existentes completas verdes (la CLI no se rompió).
- **CHECKPOINT G0 — PARAR AQUÍ**: mostrar el contrato final + el JSON REAL (modelos
  cargados) de 3 oraciones: "Juan le dio flores a María" (AGX+ditransitiva+PP),
  "Probablemente Juan casi terminó la tarea en el parque" (periferia multi-estrato:
  epistémico@clausula + aspectual@nucleo + locativo@centro) y una con Integridad ⚠.
  Julian aprueba o ajusta el contrato ANTES de que exista una línea de frontend.

---

## G1 — Ver (servidor + página única)

### G1.1 Servidor `gruxx_server.py`

- Dependencias NUEVAS en el venv: `fastapi`, `uvicorn` (pip install; anotar versiones
  exactas en el checkpoint). Nada más.
- Lifespan: `gruxx_motor.cargar()` al arrancar (una vez). `threading.Lock` alrededor de
  `analizar` — un análisis a la vez (el motor no es reentrante; máquina de 12 GB).
- Endpoints: `GET /estado` → `{listo}`; `POST /analizar` `{oracion}` → contrato G0 (400 si
  vacía; el error de una oración va en `error`, nunca 500 con traceback al usuario);
  `GET /glosario` y `GET /glosario?termino=` → reusa `aspect_classifier/glosario.py`
  (búsqueda tolerante incluida); estáticos desde `gui/`.
- `127.0.0.1`, puerto fijo **8763**, `workers=1`.

### G1.2 Frontend `gui/` (index.html + app.js + estilo.css — JS plano, cero build, cero CDN)

Página única, en español, terminología del glosario (mismo criterio que la salida de la
terminal — el usuario es lingüista GRR, no técnico):

1. **Cabecera**: caja de oración + botón "Analizar" (deshabilitado con "cargando modelos…"
   hasta que `/estado` dé listo — sondear cada 2 s). Enter = analizar.
2. **Árbol SVG** (la pieza central — layout propio, sin librerías; el layout es computable:
   anchos bottom-up, como ya hace el render ASCII):
   - Estratos de arriba hacia abajo; hojas con el TEXTO real (resuelto vía `tokens`).
   - Nodo `AGX` con badge destacado; `PrDP`/`LDP`/`PrCS` como posiciones destacadas.
   - **Periferia con la convención de Van Valin**: los nodos `-PERI` se dibujan al costado
     y una FLECHA curva entra al nodo de su estrato (el estrato = el PADRE del nodo `-PERI`
     en el árbol: NUC/CORE/CLAUSE — ya viene correcto por `RRGStratum`). Fallback aceptable
     en primera iteración: rama diferenciada (punteada + color) con el ancla resaltada; la
     flecha lateral se itera con capturas en el checkpoint. NO cambiar la estructura del
     árbol para lograr el dibujo — es solo render.
3. **EL léxica** inmediatamente bajo el árbol (orden GRR de L5 §2). **Hover bidireccional**:
   pasar el cursor por `x_n` en la EL formal/argumentos ilumina su constituyente en el árbol
   y viceversa (usar `argumentos[].token_id` + hojas del árbol). Argumento morfológico
   (pro-drop/clítico) ilumina el nodo AGX o el núcleo verbal, con nota "(morfológico)".
4. **Debajo**: tipo legible (badge), EL formal, tabla de argumentos (var·palabra·función
   UD·papel), rasgos como BARRAS 0-1 con su valor, chips de Integridad (verde
   ok/ok_clausal · gris no_verificable · ámbar falta_*), causatividad si hay, y una barra
   de estado con método+confianza.
5. **Glosario omnipresente**: cargar `/glosario` completo una vez; todo término técnico
   renderizado (AGX, NMR, CAUSE, PURP, BECOME, clases, télico…) lleva tooltip con su
   definición. Un panel lateral opcional con buscador (la búsqueda tolerante ya existe en
   el backend).
6. **Toggle "detalle técnico"** (= `--verbose`): muestra `crudo.morph_note` y
   `crudo.resumen_completeness` bajo el bloque traducido.
7. Botón "Corregir" visible pero deshabilitado con tooltip "disponible en la fase G2" —
   marca el camino sin prometer de más.
8. Historial mínimo de la sesión (lista clicable de oraciones ya analizadas, en memoria del
   navegador — nada persistente; el historial rico es G3).

### G1.3 Lanzador

- Script `gruxx-gui` (bash, raíz): si `http://127.0.0.1:8763/estado` no responde, arranca
  `./venv/bin/uvicorn` en background; luego abre el navegador — con `chromium --app=` si
  existe (ventana modo app, sin barra), si no `xdg-open`. NUNCA segunda instancia del
  servidor.
- `gruxx.desktop` de ejemplo + instrucciones de instalación manual en un `docs/GUI.md`
  breve (no instalar automáticamente nada fuera del repo).

### G1.4 Tests G1

- Rápidos: `TestClient` de FastAPI con MOTOR STUB inyectado (el server debe aceptar el motor
  por parámetro/variable para esto): `/estado`, `/glosario` (completo + término + no
  encontrado), `/analizar` con stub (contrato completo), oración vacía → 400.
- `@slow` (end-to-end real, modelos cargados, respetando la advertencia OOM): POST
  "Juan le dio flores a María" → aserciones sobre el JSON: árbol con nodo AGX, ditransitiva
  benefactiva/transferencia, integridad ok, enlaces var↔token coherentes.
- Suites preexistentes todas verdes (2 fallos slow conocidos documentados: sacudió,
  blend_sube_pun — no son de esta fase).

---

## Aceptación + CHECKPOINT final — PARAR aquí

1. `gruxx-gui` arranca servidor+navegador; segunda invocación reusa el servidor.
2. CAPTURAS de pantalla de: (a) la diana ditransitiva con AGX visible y hover x3↔"a María"
   funcionando; (b) una oración con periferia en 2+ estratos mostrando el anclaje (flecha o
   fallback, decir cuál quedó); (c) una oración con ⚠ de Integridad (chips ámbar);
   (d) un tooltip del glosario abierto; (e) el toggle de detalle técnico.
3. La terminal (`python3 gruxx_ai1.py`, 3 modos) corre idéntica a antes.
4. Informe: contrato JSON final aprobado, versiones instaladas, decisiones de dibujo del
   árbol tomadas y su porqué, deuda/pendientes que quedaron para G2/G3 (corrección en UI,
   lote, exportar SVG/PNG, panel del curador), y cualquier fealdad de pantalla causada por
   pendientes del MOTOR (anotar, no arreglar).
