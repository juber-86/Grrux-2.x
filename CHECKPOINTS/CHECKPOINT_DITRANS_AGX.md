# CHECKPOINT — DITRANS-AGX (2026-08-19)

**Hito:** el clítico AGX dativo doblado como evidencia de recipiente.
**Origen:** bug de campo reportado por Julian — `juan le da un beso a maria` salía
**Semelfactivo** en la GUI, cuando debe ser una realización causativa.
**Alcance:** `aspect_classifier/ditransitivas.py`, `aspect_classifier/config.yaml`,
`aspect_classifier/test_ditransitivas.py`. Sin tocar el clasificador, el vector, `ud2rrg.py`
ni el árbol (invariantes §9.3 y §9.4 intactos).

---

## 1. Diagnóstico

Sospecha inicial (descartada): que la higiene DEUDA-INFRA hubiera roto el pipeline. Auditoría del
rango `98d8e4ea..HEAD`: cero cambios de lógica, cero archivos de datos tocados, mismo conjunto de
fallas en la suite antes y después. La higiene es inocente.

Causa real, reproducida en frío (sonda sin Stanza, con el `config.yaml` real):

```
"juan le da un beso a maria"
  core     = [('juan','Actor'), ('beso','Undergoer'), ('maria','Meta')]
  periferia= []
  agx      = [('le', fuente='dativo', doblado=True, arg_id=7)]
  ditrans  = None
```

Cadena causal, tres eslabones:

1. Stanza etiquetó el sintagma doblado `a maria` como **`obl`**, no `obl:arg`
   (en `juan da regalos a los niños` sí puso `obl:arg`, y ahí la plantilla dispara).
2. `nucleo_periferia` solo asigna `NMR(dativo)` a `obl:arg`/`iobj`, así que maría no lo recibió.
   Y como `dar` estaba en `verbos_movimiento`, ese `obl` con preposición `a` **ascendió al core como
   `Meta`** — robándole el lugar al recipiente.
3. `ditransitivas.detectar_trigger` solo consulta `macropapel == 'NMR(dativo)'` en core → no disparó →
   la clase la decidió el clasificador BERTIN (`puntual 0.90` → Semelfactivo) y la EL cayó a
   `SEML dar'(juan, beso)`.

Consecuencia colateral observable: maría quedó como tercer participante sin variable libre
(`x`/`y` tomadas por juan y beso) y `_mapear_argumentos_genericos` la mandó a `diagnosticos` —
que no se imprime. Por eso **desapareció de la línea `Argumentos`** del análisis.

**Lo importante:** el sistema ya tenía la respuesta. `roles['agx']` decía literalmente
`le / dativo / doblado=True / arg_id=7`. El trigger tiraba esa evidencia a la basura.

## 2. Cambios

### `ditransitivas.py`

- **`_recipiente_agx_doblado(roles) -> (y, y_periferia_id)`** (nuevo). Busca un AGX de fuente
  `dativo` con `arg_id`; localiza ese token primero en `core` (donde puede estar con un macropapel
  equivocado) y después en `periferia`, devolviendo el id en el segundo caso para que ascienda.
- **`detectar_trigger`**: tercera vía `dativo_agx`, como **último recurso** — después de la ruta
  `dativo` canónica y después de la benefactiva léxica, para no robarles precedencia.
  Flag `fallback_agx_dativo` (§9.6: con `false`, salida byte-idéntica a pre-DITRANS-AGX).
- **`construir_ditransitiva`**: `y_periferia_id` ahora también se propaga desde el trigger
  (antes solo lo poblaba `benefactivo_para`), reutilizando la mecánica de ascenso de la decisión 4.

### `config.yaml`

- `ditransitivas.fallback_agx_dativo: true` (nuevo flag maestro del sub-hito).
- `nucleo_periferia.verbos_movimiento`: **retirado `dar`**. Estaba ahí desde 2026-07-14, persistido
  por el bucle de corrección (`correcciones_log.csv`: *"juan le da un regalo a maria, dar, enrutado,
  persistido, config:verbos_movimiento, maria->argumento del core"*). El enrutador automático mandó
  una corrección de recipiente dativo al destino equivocado. Efecto medido:

  ```
  "Juan dio un discurso a las tres"
    sin 'dar' : core=[Juan/Actor, discurso/Undergoer]             perif=[tres/temporal]   OK
    con 'dar' : core=[Juan/Actor, discurso/Undergoer, tres/Meta]  perif=[]                MAL
  ```

  Nota: retirarlo **no arregla la clase** por sí solo (el trigger seguía sin disparar); solo dejaba
  de esconder el problema. Los dos cambios son independientes y ambos necesarios.

## 3. Evidencia

Sondas en frío con `config.yaml` real:

| caso | trigger | clase | EL |
|---|---|---|---|
| `juan le da un beso a maria` (doblado=`obl`) | `dativo_agx` | accomplishment | `[do'(juan, Ø)] CAUSE [BECOME have'(maria, beso)]` |
| ídem, flag en `false` | — | `None` | (regresión pre-hito) |
| `juan le da un beso a María` (doblado=`obl:arg`) | `dativo` | accomplishment | ídem (sin cambio) |
| `juan da regalos a los niños` | `dativo` | accomplishment | `[do'(juan, Ø)] CAUSE [BECOME have'(niños, regalos)]` (sin cambio) |
| `juan come pizza` | — | `None` | sigue sin disparar |
| `Juan dio un discurso a las tres` | — | `None` | `tres` vuelve a periferia |

Tests: 7 nuevos en `test_ditransitivas.py` (precondición del AGX, disparo, EL + ascenso desde
periferia, regresión con flag apagado, sin-tema, precedencia de las rutas previas, transitiva simple).
`pytest -q aspect_classifier/test_ditransitivas.py` → **26 passed, 2 skipped**.

Suite completa desde el puente remoto: **295 passed** (288 de la línea base + 7 nuevos),
32 skipped. Las 20 fallas y 3 errores son el **mismo conjunto exacto** que antes del cambio
(`diff` de la lista de FAILED/ERROR: idéntico) — todas `discodop` (18) y red/proxy (5), los
artefactos de puente documentados en `docs/DESARROLLO.md`. **Cero regresiones.**

## 4. Limitaciones y pendientes

- **CORRECCIÓN (2026-08-19, posterior a la primera redacción de este checkpoint).** La versión
  inicial afirmaba que Stanza no era ejecutable desde el puente remoto "porque los modelos viven
  fuera de la carpeta montada". Es FALSO: los modelos están en el propio repo, en
  `.stanza_cache/resources/` (1,5 GB, `es/` completo), y `torch`/`stanza`/`transformers` importan
  sin problema desde el puente. Basta `STANZA_RESOURCES_DIR=<repo>/.stanza_cache/resources`.
  La afirmación se dio por buena sin comprobarla, a partir de un `ls ~/stanza_resources` vacío
  —directorio que en el puente es el del *sandbox*, no el de Julian—. Anotado aquí porque el
  error de método importa tanto como el técnico: **una limitación asumida y no medida bloqueó
  la verificación real durante todo el hito**.
- **Verificación con Stanza REAL** (hecha tras la corrección). Confirma el diagnóstico y revela la
  pieza que faltaba: el parse depende de la GRAFÍA.

  ```
  juan le da un beso a maria   ->  maria: NOUN  obl        (perif; agx le/dativo/doblado, arg_id=7)
                                   TRIGGER dativo_agx -> accomplishment
                                   [do'(juan, Ø)] CAUSE [BECOME have'(maria, beso)]
  Juan le da un beso a María   ->  María: PROPN obl:arg    (core, NMR(dativo))
                                   TRIGGER dativo -> accomplishment
  juan da regalos a los niños  ->  niños: NOUN  obl:arg    (core, NMR(dativo))
                                   TRIGGER dativo -> accomplishment
  ```

  En minúsculas y sin acento, Stanza analiza `maria` como nombre común con `obl`; con mayúscula y
  acento, como `PROPN` con `obl:arg`. Por eso el síntoma (GUI, minúsculas) y el diagnóstico inicial
  (mayúscula) parecían contradecirse: **nunca estuvieron mirando el mismo parse**. Es también la
  mejor justificación del fix: la construcción ditransitiva no puede depender de la ortografía de
  la entrada, y el clítico dativo es evidencia inmune a esa variación.
- Lo que sigue SIN poder ejecutarse desde el puente es **BERTIN** (`extractor.py` llama a
  `from_pretrained` sin `cache_dir`, así que busca en `~/.cache/huggingface` de la máquina de
  Julian, fuera de lo montado, y el puente no tiene red) y **`discodop`**. Por eso no se pudo
  correr `grrux_motor.analizar()` de punta a punta ni observar el vector aspectual real. Toda la
  cadena determinista —parse, enrutado, trigger, plantilla, EL— sí quedó verificada contra el
  parser real.
- **VERIFICACIÓN DE PUNTA A PUNTA (2026-08-19).** Con acceso a la caché de HuggingFace de
  Julian (`~/.cache/huggingface`, montada en la sesión) y `HF_HUB_OFFLINE=1`, BERTIN carga sin
  red y el pipeline completo SÍ corre desde el puente. Único obstáculo restante:
  `grrux_ai1.cargar_pipeline_stanza` intenta `stanza.download()` ante cualquier fallo del
  `Pipeline` y eso muere con proxy 403; se sortea inyectando el pipeline con
  `download_method=None` (ver `docs/DESARROLLO.md`). Resultado real de
  `grrux_motor.analizar()` — el mismo camino exacto que ejecuta la GUI:

  ```
  juan le da un beso a maria
    el.tipo         : accomplishment
    el.tipo_legible : Realización causativa
    el.lexical      : [do'(juan, Ø)] CAUSE [BECOME have'(maria, beso)]
    ditransitiva    : transferencia / trigger=dativo_agx / source=lexico
    morph_note      : stat=0.12 dyn=0.75 tel=0.22 pun=0.90 ... ditrans=transferencia(lexico)
                      derivada=realizacion_causativa fuente=EL

  juan da regalos a los niños
    el.tipo         : accomplishment
    el.tipo_legible : Realización causativa
    el.lexical      : [do'(juan, Ø)] CAUSE [BECOME have'(niños, regalos)]
    ditransitiva    : transferencia / trigger=dativo / source=lexico
  ```

  Nótese `pun=0.90` en la primera: el clasificador SIGUE leyendo "dar un beso" como puntual
  —es lo que ganaba antes y producía Semelfactivo—; ahora la plantilla ditransitiva, disparada
  por la vía `dativo_agx`, manda sobre esa lectura. Es la prueba directa del antes/después.
  Los dos hitos de presentación quedan verificados a la vez: `el.tipo_legible` ya no dice
  "Realización" a secas.
- **Hallazgo colateral, sin arreglar (decisión de Julian).** `grrux_ai1.cargar_pipeline_stanza`
  tiene el mismo antipatrón que los `except Exception` de `rrg_ls_mapper`: ante CUALQUIER fallo
  al construir el `Pipeline` llama a `stanza.download(lang)`. En una laptop de estudiante sin
  red (o con los modelos ya presentes pero otro fallo real) el error que ve el usuario es un
  `ProxyError`/timeout de descarga, no la causa verdadera. Candidato a `download_method=None`
  cuando los modelos ya existen localmente.
- Queda confirmar en la máquina de Julian con la GUI real (reiniciar el servidor:
  `pkill -f "uvicorn grrux_server:app"` y `./grrux-gui`), aunque el motor ya está verificado
  por el camino idéntico.
- `beso` entra como tema de `have'` en la plantilla de transferencia. Es coherente con la plantilla,
  pero "dar un beso" es una construcción de **verbo soporte**, no una transferencia de posesión
  literal. Decisión teórica pendiente de Julian; el fix la hace visible, no la resuelve.
- Sigue abierto: la etiqueta de las ditransitivas se muestra como "Realización" y no "Realización
  causativa" pese a que su EL lleva CAUSE (`causativo_clase_derivada` solo lo puebla la rama de
  causatividad, que el mapper salta cuando dispara la plantilla).
- Sigue abierto: el diagnóstico *"sin posición licenciada en la EL seleccionada"* se calcula y se
  descarta sin mostrarse; y los tres `except Exception` desnudos de la cabecera de
  `rrg_ls_mapper.py` pueden degradar el análisis en silencio absoluto.
- Sigue abierto: el enrutado de `correccion.py` para el caso "recipiente dativo" — el bug que
  originó la contaminación de `verbos_movimiento`.
