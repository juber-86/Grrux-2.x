# Tarea OPERATORS_2: EL ortodoxa (fuera pseudo-predicados) + corrección de operadores + fix de exportación SVG/PNG

Proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python`. NO hacer commits.
ADVERTENCIA OOM de siempre. Sigue a CHECKPOINT_OPERATORS.md. Después de esta etapa viene
`prompt_LA1.md` (linking algorithm) — esta etapa le prepara una EL canónica.

**PROHIBIDO:** `ud2rrg.py` completo, clasificador (predict/classifier/decision_tree/.joblib),
corroborador MLM, `contextual_sentences.csv`. Editables: mapper, `wrappers_ls.py`,
`operadores.py`, `completeness.py`, `correccion.py`, `display_grr.py`, motor/GUI, glosario,
tests.

## §1. Eliminar los pseudo-predicados de la EL (decisión de Julian: APROBADA)

**El problema** (§6 del checkpoint OPERATORS): antes de que existieran los operadores, etapas
viejas metieron categorías gramaticales en la EL disfrazadas de predicados. Hoy la información
está DUPLICADA: `⟨ASP PERF ⟨complet(do'(…))⟩⟩`, `⟨NEG ⟨no'([…])⟩⟩`, `⟨STA IRR ⟨maybe'([…])⟩⟩`.
En Van Valin los operadores NO son predicados de la EL: los predicados son contenido LÉXICO
(`be-in'`, `during'`, `comer'`); tiempo/aspecto/negación/modalidad son gramática cerrada y su
lugar es ⟨ ⟩.

**Qué hacer:**
1. INVENTARIO primero: localizar TODOS los envoltorios pseudo-predicativos que duplican
   operadores — conocidos: `complet(…)`/`prog(…)` (de `build_ls` vía aux_asp), `no'(…)`
   (negación tratada como wrapper), `maybe'(…)`/epistémicos (quizá/tal vez como wrappers).
   Reportar el inventario completo en el checkpoint por si aparece alguno más.
2. Eliminarlos de la construcción de la EL: esa información vive SOLO en los operadores
   (`ASP PERF/PROG`, `NEG`, `STA IRR`), que ya se detectan desde las mismas señales.
3. **Los wrappers léxicos legítimos SE QUEDAN**: `yesterday'`, `be-in'`, `during'`, `for'`,
   la manera (`lentamente'`) — la manera NO es operador. La línea divisoria: categoría
   gramatical cerrada → operador; contenido léxico → predicado.
4. `completeness.py`: la negación y los epistémicos ya no esperan wrapper↔rama; se consideran
   cubiertos por su operador (sin advertencias nuevas por esto). El "no" puede seguir
   apareciendo en el árbol como lo ponga ud2rrg (no se toca) — el checker simplemente no lo
   busca como wrapper.
5. **Gold de dianas**: este cambio ALTERA la EL interna de dianas históricas — Julian lo
   aprobó explícitamente PARA ESTE CAMBIO. Actualizar los golds afectados y entregar en el
   checkpoint la TABLA COMPLETA EL-vieja → EL-nueva de cada diana tocada (auditoría). Cualquier
   otra desviación de gold fuera de este cambio → PARAR y reportar, protocolo de siempre.
6. Motivación extra (documentarla en el código): LA1 leerá POSICIONES de la EL para asignar
   macropapeles por la jerarquía Actor-Padecedor — los pseudo-predicados son capas falsas que
   ensuciarían esa lectura.

## §2. Corrección de operadores en el bucle (los TODO-OPERATORS-2 de correccion.py)

- **Menú**: opción `4) Un operador (tiempo, aspecto, negación…)`. Sub-flujo: listar los
  operadores detectados (con su señal de origen) + los ausentes añadibles; acciones: CAMBIAR
  valor (solo valores válidos del operador: IF∈{DEC,INT,IMP}, TNS∈{PAST,PRES,FUT}, …),
  QUITAR ("este operador no debería estar"), AÑADIR. Esc cancela limpio.
- **Destinos (la asimetría del checkpoint, resuelta así):**
  - Si la corrección revela un HUECO LÉXICO sistemático — un adverbio epistémico que falta en
    la lista de STA, una perífrasis modal no cubierta (el log `perifrasis_no_cubiertas.csv` ya
    los junta) — → la lista de config correspondiente, EN VIVO con marca `# correccion_usuario`
    (mismo patrón que el enrutado) + re-análisis confirmatorio.
  - Si es un error de PARSE puntual (el `Mood=Imp` que Stanza no da, un tiempo mal leído) →
    STAGING `data/correcciones_operadores.csv` (fecha, oración, operador, valor_predicho,
    valor_correcto, señal_origen) con mensaje honesto: "registrado para revisión; esta
    corrección no puede automatizarse aún" (un override por-oración en vivo queda como TODO
    documentado — no implementarlo).
  - gruxx decide la ruta AUTOMÁTICAMENTE (el usuario nunca elige archivo, regla de L5).
- Log maestro `correcciones_log.csv` como siempre. GUI: si el bucle de corrección ya tiene UI,
  añadir la opción 4 ahí también; si el bucle es solo-terminal, dejarlo en terminal y anotar
  TODO-GUI.

## §3. Reparar los 2 fallos preexistentes del propio bucle (ya que se toca correccion.py)

Documentados en CHECKPOINT_OPERATORS §4 como preexistentes:
1. `test_l5::test_slow_correccion_ditransitiva_end_to_end` — `staging_lema_no_identificable`:
   bug de `_lema_de` con ELs compuestas solo de do'/have'/CAUSE (sin predicado léxico con
   apóstrofe reconocible). Diagnosticar y arreglar.
2. `test_gruxx_server::test_slow_corregir_el_real_con_reanalisis` — investigar (probablemente
   el mismo bug aguas arriba; si es independiente, diagnosticar y arreglar o documentar con
   precisión por qué queda fuera).
(El artefacto de orden de `test_estado_antes_de_cargar` tras la suite de servidor: arreglar el
aislamiento del test si es barato — estado global del motor sin reset — o documentarlo.)

## §4. Fix de exportación SVG/PNG (bug reportado por Julian con imagen)

**Síntoma**: los árboles exportados desde la GUI se ven como cajas NEGRAS, VACÍAS y SIN líneas
de conexión al abrirlos fuera (visor de imágenes, LibreOffice). **Causa**: dentro de la GUI el
SVG lo estila `estilo.css` (externo); el export sale sin esos estilos y los visores aplican los
defaults del estándar (rect fill negro, strokes inexistentes, texto invisible).

**Fix**: el SVG exportado debe ser AUTOCONTENIDO — incrustar los estilos al exportar (atributos
inline sobre cada elemento, o un bloque `<style>` embebido con las reglas relevantes; elegir lo
más robusto para visores conservadores — los atributos inline son lo más compatible). El PNG se
genera desde ese SVG ya estilado. Aplica a TODO lo exportable: árbol de constituyentes,
proyección espejo de operadores (respetando el toggle), y cualquier otra vista exportable.

**Validación**: test que verifique que el SVG exportado no depende de clases CSS externas para
fill/stroke/font de nodos, líneas y texto (los elementos críticos llevan estilo embebido);
rasterizar una muestra con inkscape (disponible en el entorno, se usó en el checkpoint
anterior) y verificar programáticamente que la imagen no es mayoritariamente negra y contiene
trazos; captura antes/después en el checkpoint.

## Validación general

- Tests fríos y @slow de cada sección; batería completa de dianas con los golds actualizados
  del §1 (y SOLO esos); byte-idéntico general no aplica al §1 (cambia EL por diseño aprobado)
  pero sí a §2-§4 con sus flags/paths no ejercitados.
- Suites completas verdes; los preexistentes de §3 deben quedar en verde (o justificados con
  precisión); los 3 restantes conocidos (causatividad sacudió, fase2 dianas AA, blend_sube_pun)
  siguen documentados — NO son de esta etapa.
- PUD intocado. Sin commits.

## CHECKPOINT — PARAR aquí

Informe: (1) inventario completo de pseudo-predicados encontrados + tabla EL-vieja→EL-nueva de
TODAS las dianas tocadas; (2) demo de corrección de operador: cambiar valor, quitar, y una que
enrute a lista de config con re-análisis confirmatorio + una de parse a staging; (3) los 2
fallos de §3 en verde con su diagnóstico; (4) SVG y PNG exportados abriendo correctamente fuera
de la GUI (captura antes/después); (5) confirmación de que la EL quedó canónica para LA1.
Después: `prompt_LA1.md`.
