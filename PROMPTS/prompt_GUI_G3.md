# Tarea: GUI de gruxx — Fase G3 (trabajar) + fixes de G2

Proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python` (3.10).
Estado: **G0–G2 CERRADOS** (checkpoint G2 aprobado por Julian, 2026-07-14). Existen:
`gruxx_motor.py` (motor residente, `analizar()`, `serializar_arbol` con orden por hoja
mínima, cache de análisis crudos con `analisis_id`), `gruxx_server.py` (`crear_app(motor=…)`
inyectable; `/estado`, `/analizar`, `/glosario`, `/corregir/{validar-el,clase,el,enrutado}`;
`threading.Lock` compartido), `gui/` (modal de corrección con 3 pestañas, validación EN
VIVO con debounce, diff antes/después con `dibujarArbolEnSvg` compartido, logo/favicon),
lanzador + `.desktop` con icono. Suites: 237 fríos + 2 `@slow` verdes.
Julian commitea a mano — NO hacer commits desde la sesión.

**ADVERTENCIA OOM (12 GB):** una sola instancia del servidor; NO correr suites `--slow`
con el servidor (ni gruxx interactivo) abierto.

**PROHIBIDO tocar el motor** (igual que G0–G2): `rrg_ls_mapper.py`, `nucleo_periferia.py`,
`completeness.py`, `misc_rrg.py`, `pruebas_estructurales.py`, `ditransitivas.py`,
`causatividad.py`, `wrappers_ls.py`, `ud2rrg.py`, `convertir.py`, clasificador/.joblib,
corroborador, `contextual_sentences.csv` (solo lectura), PUD. Terminal (`gruxx_ai1.py`,
3 modos) intacta e idéntica. **Excepción autorizada ESTA fase** en `correccion.py`,
ceñida a §1 y §2 de abajo (lema robusto + `corregir_todo`): la lógica de
validación/persistencia/revert existente NO se altera; todo lo demás de ese archivo,
intocado.

**Pendientes de MOTOR — NO arreglar** (actualizados en G2): "por+ruta" sigue vivo
("Juan corrió por el parque" → "por el parque" se envuelve `because-of'` como razón en
vez de locativo — sirvió de demo de enrutado en G2 y seguirá cayendo a staging hasta que
el motor lo arregle); homógrafos, compuestas/xcomp, operadores, impersonal refleja,
agente-por. ("Juan le da un pastel a María" quedó RESUELTO por fases previas — verificado
en G2, ya no es pendiente.) Nuance documentada de G2 que NO es bug: en "Mario vio la
película completamente" el ADVP-PERI anida dentro de NUC (constituyente discontinuo real
de ud2rrg) — el adverbio se dibuja entre el verbo y el objeto; se acepta tal cual.

---

## §0. Fix visual de G2 (veredicto de Julian, hacer PRIMERO)

**Barras de rasgos**: hoy los números (stat 1.00, pun 0.68…) quedan al extremo opuesto de
la ventana y las barras se ven como espacio muerto. Arreglo (solo `gui/`):
- cada fila compacta: etiqueta + valor JUNTOS ("dinámico 0.78") y al lado la barra con
  **relleno proporcional al valor** (ancho = valor×100% del riel, rango 0.00–1.00);
- el riel completo visible (fondo tenue) para que 0.68 se LEA como 68% lleno, sin zonas
  que parezcan vacías por diseño;
- misma solución en el diff antes/después (comparte render). Captura en el checkpoint.

## §1. Lema robusto en la corrección (excepción autorizada — arregla el bug del checkpoint G2)

Bug diagnosticado en G2: `_lema_de()` cae a `ls_type` cuando la EL léxica no expone el
verbo real primado (ditransitivas: solo `do'`/`have'`/CAUSE; o EL envuelta por wrappers de
la Etapa PERIFERIA ausentes de `_PRED_NO_LEMA`: `because-of'`, `despite'`, `every'`,
`probably'`…) → llegó a persistir el lema "accomplishment" en `verbos_ditransitivos.xlsx`.
Arreglo en dos capas:
1. **Lema explícito inyectado** (la capa que resuelve de verdad): los `corregir_*` (y el
   nuevo `corregir_todo`) aceptan un parámetro opcional `verb_lemma`; cuando viene, manda
   sobre `_lema_de()`. El server lo deriva del cache — dato que YA existe: `root_id` del
   ls crudo + `tokens` del contrato → lema del token raíz. La terminal puede seguir sin
   pasarlo (fallback intacto).
2. **`_PRED_NO_LEMA` ampliado** como red del fallback: añadir los wrappers FIJOS de la
   Etapa PERIFERIA (leer los reales de `wrappers_ls.py`/config — because-of, despite,
   every, probably, etc.); documentar que los `generico` (preposición/lema arbitrario como
   predicado) NO son cubribles por lista estática — por eso la capa 1 es la primaria.
3. **Guardia anti-basura**: si el lema resuelto ∈ nombres de clase aspectual
   (`CLASES`/`CLASE_ES`), NO persistir en léxico vivo — staging con motivo "lema no
   identificable". Nunca más una fila "accomplishment" en un xlsx curado.
- Test que REPRODUCE el caso del checkpoint: EL ditransitiva sin verbo primado + res cuyo
  ls_type es "accomplishment" → con `verb_lemma="dar"` persiste "dar"; sin lema y sin
  primado identificable → staging, jamás fila espuria. Suites existentes verdes.

## §2. "Corregir todo" — EL + clase en UN paso (diseño motivado por Julian)

Razón de Julian (va aquí para que se entienda el porqué): algunas veces se debe corregir 
EL y clase por separado. Pero otra veces se debe corregir tanto la EL como la clase aspectual.
Corregir una frecuentemente exige corregir la otra, porque si la EL no corresponde con la clase
aspectual, la clase también está mal. Hacerlo por separado obliga a DOS correcciones 
(y dos re-análisis) sobre la misma oración. Julian propone una opción extra: EL y clase juntas, 
UN re-análisis. NO elimines las opciones de corregir EL y corregir clase. 
AGREGA la opción "Corregir clase aspectual y EL"  a las ya existentes.

1. **`corregir_todo(res, sub_idx, el_texto, clase_correcta, reanalizar_fn, data_dir=None,
   verb_lemma=None) -> dict`** en `correccion.py`: compone las piezas EXISTENTES —
   staging de clase (lo de `corregir_clase`) + flujo de EL (lo de `corregir_el`) — con
   **UN SOLO re-análisis compartido** para la confirmación. Reglas de persistencia
   intactas: clase → SIEMPRE staging (`correcciones_clase.csv`); EL → léxico vivo o
   staging según la lógica vigente. Log maestro: una fila por componente (auditoría
   completa), `accion` del retorno refleja ambos resultados.
2. **`POST /corregir/todo`** `{analisis_id, sub_idx, el, clase}` → mismo formato de
   respuesta que los demás (`accion`, `detalle`, `analisis_nuevo|null`). Mismo lock.
3. **UI**: la pestaña "Estructura Lógica" del modal gana un dropdown "Clase aspectual"
   con tres estados: "(no cambiar)" (default; el flujo queda idéntico a G2),
   **clase SUGERIDA automáticamente por la plantilla** cuando la validación en vivo
   reconoce una (mapear plantilla→clase: activity→Actividad, accomplishment→Realización,
   ditrans_transferencia→Realización, etc. — completar el mapa con las plantillas de
   `reconocer_plantilla`), o una elegida a mano. Si hay clase elegida → Aplicar llama a
   `/corregir/todo`; si "(no cambiar)" → `/corregir/el` como hasta ahora. La pestaña
   "Clase" sola se conserva (corrección de clase sin tocar la EL sigue siendo válida).
4. Cancelar/cerrar = cero efectos, como siempre.

## §3. Modo lote en la GUI (tabla + filtro ⚠)

1. Nueva vista/pestaña "Lote": textarea multilínea (una oración por línea) Y carga de
   archivo `.txt` (mismo formato que la CLI: líneas, `#` comenta). Análisis SECUENCIAL
   (el lock ya lo impone) con progreso visible "n/N — analizando: «…»".
2. Tabla de resultados: oración · clase (legible) · Integridad (✓/⚠/— sin árbol) ·
   avisos abreviados. **Filtro "solo ⚠"** (el material de trabajo del lingüista). Clic en
   fila → la vista completa de esa oración (árbol+EL+detalles), con su botón Corregir
   operativo (cada fila tiene su `analisis_id`; subir N del cache del motor si hace
   falta, p.ej. a 100, documentando el coste en memoria).
3. Errores por oración (motor devuelve `error`) se muestran en su fila sin tumbar el lote.

## §4. Exportaciones

1. **SVG** del árbol: descarga del SVG ya dibujado (cliente, sin servidor).
2. **PNG** del árbol: rasterizar el mismo SVG en canvas (cliente). Fondo blanco.
3. **`.txt`** del análisis: endpoint `GET /exportar/txt?analisis_id=` — el motor compone
   el MISMO formato GRR de la terminal (reusar `display_grr.render_bloque`; árbol ASCII
   vía `DrawTree` de discodop IN-PROCESS, como hace `convertir.py` — sin subprocess).
4. **`.conllu` anotado**: el motor conserva en el cache el conllu con MISC de cada
   análisis; `GET /exportar/conllu?analisis_id=` lo devuelve tal cual (es el insumo del
   modo `.conllu` de la CLI y de terceros).
5. Botonera de exportación en la vista de análisis (y por fila del lote). Nombres de
   archivo: patrón de la CLI (`analisis_<primeras-palabras>.<ext>`).

## §5. Panel del curador (SOLO lectura)

1. Vista "Curación": tablas de `correcciones_clase.csv`, `correcciones_el.csv`,
   `correcciones_enrutado.csv` y el log maestro `correcciones_log.csv`, con contadores
   por archivo y por acción (persistido/staging/rechazado).
2. **Sin promover desde la UI** — decisión de diseño (anti-contaminación de L5): la
   promoción a léxicos vivos/`contextual_sentences.csv` sigue siendo edición MANUAL de
   Julian. El panel muestra y cuenta; no escribe nada. Endpoint `GET /curador/staging`.
3. Nota visible en el panel explicando exactamente eso (honestidad del flujo).

## §6. Historial persistente + stretch

1. Historial de oraciones analizadas persistido en `localStorage` (solo cliente, sin
   archivos nuevos del lado servidor): oración + fecha + clase + integridad. Clic →
   **re-analiza** (los léxicos pueden haber cambiado desde entonces — es lo honesto), no
   resucita el resultado viejo. Botón limpiar historial.
2. *Stretch opcional* (deuda de G2): seleccionar el elemento a enrutar clicando su nodo
   en el árbol SVG. Si complica, la lista clicable de G2 sigue cumpliendo — anotar.

## §7. Tests

- Fríos: `corregir_todo` (ambos componentes con stub — clase→staging + EL
  confirmada/no-confirmada con UN solo re-análisis: contar llamadas al stub), lema robusto
  (§1: los 3 casos, incluida la guardia anti-basura), mapa plantilla→clase sugerida.
- Rápidos (TestClient + motor stub, staging a `data_dir` temporal): `/corregir/todo`
  ambas ramas; lote (N oraciones con una errónea → tabla completa, error aislado);
  `/exportar/txt` y `/exportar/conllu` (contenido esperado con stub; id expirado→404);
  `/curador/staging` (contadores correctos sobre CSVs de fixture).
- `@slow` (OOM: servidor cerrado): un lote real pequeño (3 oraciones) end-to-end + una
  exportación .txt real (comparar orden GRR con la salida de la terminal).
- Suites preexistentes completas verdes; `gruxx_ai1.py` y motor prohibido: cero diffs.

## Aceptación + CHECKPOINT final — PARAR aquí

1. §0: captura de las barras rellenas (antes/después del fix).
2. §1: demo del caso del checkpoint G2 — la misma EL ditransitiva ya NO persiste
   "accomplishment"; fila correcta con lema real (y la guardia disparando en el caso sin
   lema).
3. §2: demo "corregir todo" — una oración con EL y clase mal, corregidas en UN paso, con
   su único re-análisis y el diff; captura del dropdown con la clase sugerida por la
   plantilla.
4. §3: captura del lote con la tabla, el filtro ⚠ activo, y una fila con error aislado.
5. §4: los 4 exports descargados de una misma oración (adjuntar el .txt y el .conllu al
   checkpoint; verificar que el .txt calca el orden GRR de la terminal).
6. §5: captura del panel del curador con datos reales de staging.
7. Informe: decisiones tomadas, si el stretch entró, deuda restante (¿G4 o cierre de la
   fase GUI?), y pendientes de MOTOR observados (anotar, no tocar).
