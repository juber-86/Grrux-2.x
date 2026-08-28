# CHECKPOINT — DITRANS-CLASE + AVISOS + ENRUTADO-DATIVO (2026-08-19)

Tres defectos encontrados en la misma auditoría que produjo `CHECKPOINT_DITRANS_AGX.md`.
Ninguno toca el análisis: ni `ls_type`, ni el vector, ni la EL, ni el árbol, ni `ud2rrg.py`.
Los tres son **presentación y guardarraíles**: el sistema ya sabía la respuesta y no la decía,
o la escribía en el sitio equivocado.

Commits: `8988dc17` (DITRANS-CLASE + AVISOS) y el de ENRUTADO-DATIVO.

---

## 1. DITRANS-CLASE — la clase visible se deriva de la EL

**Síntoma.** `juan da regalos a los niños` se presentaba como `Tipo: Realización` mientras
la línea siguiente del mismo análisis decía
`EL formal: [do'(juan, Ø)] CAUSE [BECOME have'(niños, regalos)]`.

**Causa.** `display_grr.clase_visible` muestra "Realización causativa" solo si el `ls` trae
`causativo_clase_derivada`, y ese campo lo poblaba **únicamente** la rama de causatividad.
El mapper salta esa rama por diseño cuando dispara la plantilla ditransitiva
(`rrg_ls_mapper.py` §"Construir LS"). Resultado: la etiqueta existía en
`CLASE_CAUSATIVA_LEGIBLE` y era **inalcanzable** para toda ditransitiva de transferencia.

**Cambio.** `ditransitivas.clase_derivada_de_el(formal)` (nuevo, puro): la clase visible se
deriva **de la EL**, no de una lista de plantillas — la EL es la fuente de verdad.
`CAUSE`+`BECOME` → `realizacion_causativa`; `CAUSE`+`INGR` → `logro_causativo`; sin `CAUSE`
→ `None`, que es lo correcto para comunicación y para la benefactiva de subtipo actividad.
La rama ditransitiva del mapper lo usa y lo anota en `aspect_note`
(`derivada=… fuente=EL`), igual que ya hacía la causativa. Flag `clase_causativa_visible`
(invariante §9.6). La rama causativa queda intacta, con nota de que aplica la misma regla
inline (candidata a unificar).

Arregla terminal, `.txt` exportado y GUI de una vez: los tres leen `clase_visible`.

## 2. AVISOS — los diagnósticos dejan de ser datos muertos

**Síntoma.** En `juan le da un beso a maria`, maría desaparecía del análisis sin explicación:
no salía en `Argumentos` ni en `Periferia`.

**Causa.** El mapper **sí** lo diagnosticaba —"argumento 'maria' (obl) sin posición licenciada
en la EL seleccionada"— y lo exponía en `ls['diagnosticos_analisis']`. Ningún consumidor lo
mostraba: ni la terminal, ni el `.txt`, ni la GUI. Datos muertos. Ese aviso apuntaba
directamente al bug de DITRANS-AGX y nadie podía verlo.

**Cambio.** `display_grr.avisos(ls)` (nuevo, puro) los devuelve con prefijo `aviso: `;
`render_bloque` los imprime; `grrux_motor` los hace viajar por el canal `notas` ya existente
— sin clave nueva en el contrato G0.3, así que la GUI los pinta sin tocar el frontend.
Lista vacía en un análisis sano → salida sin cambios.

Además, los tres `except Exception` desnudos de la cabecera de `rrg_ls_mapper.py`
(clasificador, léxico causativo, léxico ditransitivo) degradaban el análisis en **silencio
absoluto**: un `.xlsx` bloqueado por Calc bastaba para desactivar la plantilla ditransitiva
sin una línea en ningún lado. Se conserva la degradación elegante, pero ahora cada fallo
deja constancia vía `_avisos_lexicos()` en `diagnosticos_analisis`.

## 3. ENRUTADO-DATIVO — el bucle de corrección escribía en el sitio equivocado

**Síntoma.** `config.yaml` tenía `dar` dentro de `nucleo_periferia.verbos_movimiento`, con la
marca `# correccion_usuario`. Efecto medido: en cualquier oración con `dar`, todo oblicuo en
`a`/`hacia`/`hasta` ascendía al core como `Meta` — `"Juan dio un discurso a las tres"` daba
`tres/Meta`.

**Causa (dos fallos encadenados).**

1. `correccion._enrutar_core` automatizaba **una sola lectura** del destino "argumento del
   core" —meta/origen de verbo de movimiento— y la aplicaba a **todas**. Una corrección sobre
   un recipiente dativo (`juan le da un regalo a maria`, 2026-07-14) terminaba escribiendo el
   verbo en `verbos_movimiento`.
2. `_confirma_enrutado` daba la corrección por buena con que el elemento apareciera en el
   core, **sin importar con qué macropapel ni si llegaba a la EL**. Con `dar` ya en la lista,
   maría ascendía como `Meta` → el chequeo decía "confirmado" → se persistió. Cuatro intentos
   previos (2026-07-13) sí habían revertido correctamente con motivo *"el re-análisis no
   reflejó la corrección"*; el quinto pasó por este agujero.

**Cambios.**

- `_es_recipiente_dativo(ls, texto)` (nuevo): un AGX de fuente `dativo` cuyo `arg_id` apunta
  al elemento es la señal inequívoca de que se está corrigiendo un **recipiente**, no una meta
  de movimiento. En ese caso `_enrutar_core` **no toca `verbos_movimiento`**: registra en
  staging con el motivo explícito (su ruta es `data/verbos_ditransitivos.xlsx`) y avisa al
  usuario de que hacerlo corrompería el enrutado de todas las oraciones con ese verbo.
  `_enrutar_core` recibe ahora el `ls` (parámetro opcional; ambos llamadores lo pasan).
- `_confirma_enrutado` para `argumento_core`: estar en el core no basta — se exige que el
  re-análisis le haya asignado **posición en la EL** (`id_a_var`). Un argumento del core que
  no ocupa posición no es un argumento; es justo el estado que el mapper diagnostica como
  "sin posición licenciada". Con este criterio, la corrección del 2026-07-14 se habría
  revertido sola.

Nota: con DITRANS-AGX en su sitio, el caso del recipiente ya se resuelve solo y esta
corrección no debería ni hacer falta. El guardarraíl queda igualmente.

---

## 4. Evidencia

- `pytest -q aspect_classifier/test_ditransitivas.py` → **32 passed, 2 skipped**
  (6 tests nuevos de DITRANS-CLASE/AVISOS).
- `pytest -q aspect_classifier/test_l5.py` → **49 passed, 2 skipped**
  (2 tests nuevos de ENRUTADO-DATIVO: el recipiente dativo no contamina `verbos_movimiento`;
  sin posición en la EL no se confirma y se revierte).
- Dos tests existentes actualizados (`test_l5.py` ×2 sitios, `test_grrux_server.py`): sus
  re-análisis simulados ahora traen `id_a_var`, como hace un re-análisis real. Sin eso
  simulaban precisamente el falso positivo que causó el bug.
- Suite completa desde el puente: **303 passed** (288 de línea base + 15 de estos hitos y
  DITRANS-AGX), 32 skipped. Las 20 fallas y 3 errores son el **conjunto exacto** de antes
  (`diff` de la lista idéntico): todas `discodop` y red/proxy, artefactos del puente
  documentados en `docs/DESARROLLO.md`. **Cero regresiones.**

## 5. Pendientes

- **VERIFICADO de punta a punta (2026-08-19)**: `grrux_motor.analizar()` —el camino exacto de
  la GUI, con Stanza y BERTIN reales— devuelve `el.tipo_legible = "Realización causativa"` en
  las dos oraciones, y `morph_note` trae `derivada=realizacion_causativa fuente=EL`. Detalle en
  `CHECKPOINT_DITRANS_AGX.md` §4. Queda solo reiniciar la GUI en la máquina de Julian
  (`pkill -f "uvicorn grrux_server:app"`, luego `./grrux-gui`) para verlo en pantalla.
- Unificar la regla de clase derivada: la rama causativa de `rrg_ls_mapper` mantiene su copia
  inline de `clase_derivada_de_el`.
- Decisión teórica abierta: "dar un beso" es verbo soporte, no transferencia de posesión
  literal; la plantilla de transferencia mete `beso` como tema de `have'`.
- Revisar si hay otras correcciones persistidas por el bucle con el mismo patrón
  (`correcciones_log.csv`, filas con `accion=persistido`).
