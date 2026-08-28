# CHECKPOINT — DEUDA-INFRA (cierre del bloque)

**Fecha**: 2026-08-18
**Contrato**: `PROMPTS/prompt_DEUDA_INFRA.md` + `PROMPTS/prompt_DEUDA_INFRA_addendum_C.md`
+ `PROMPTS/prompt_DEUDA_INFRA_addendum_D.md`
**Sesión de ejecución**: vía puente remoto (dispositivo de escritorio de Julian,
`device_bash`/`device_stage_files`/`device_commit_files`), no terminal real.
**Base**: `98d8e4ea` (ESTADO §8.5, tras merge local previo a DEUDA-INFRA).

## Alcance

Deuda técnica e infraestructura: separación núcleo activo / sedimento legacy,
documentación para sesiones ejecutoras, auditoría de pruebas GUI aisladas,
migración de nomenclatura `gruxx` → `GRRux`. **Explícitamente NO tocado**:
arquitectura de análisis, `ud2rrg.py` (verificado, ver abajo), datos curados,
clasificador/`.joblib`, PUD.

## Sub-hitos y commits

| sub-hito | commit | contenido |
|---|---|---|
| A | `2947257c` | `docs/DESARROLLO.md` (setup, convenciones §9, suites, servidor GUI, flujo de un hito) + puntero desde `README.md`. |
| B | `4eedb6bc` | Auditoría de pruebas GUI aisladas: único archivo que toca el servidor es `test_gruxx_server.py` (hoy `test_grrux_server.py`), todas vía `TestClient`+stub, sin HTTP real ni subprocess. Timeout de 90s de `CHECKPOINT_BENEFACTIVAS.md` **no reproducido** (~7-8s). Hallazgo nuevo sin relación: falla `ModuleNotFoundError: No module named 'discodop'` en export TXT/GRR — hueco de entorno, no de arquitectura. |
| (prep C) | `6b76e0dc` | Nota en `docs/DESARROLLO.md` sobre limitaciones del puente remoto (ver más abajo), descubiertas al preparar la verificación de C. |
| C | `4d6d5fe5` | Movidos a `legacy/` 21 archivos muertos (ver tabla abajo). Excluidos de la mudanza 6 archivos con dependencia real: 5 de `ud2rrg.py` (`export.py`, `linkage.py`, `util.py`, `verbnet.py`, `add_traces_to_rrg_from_ud.py`) + `convertir.py` (usado por instaladores). `ESTADO_DEL_ARTE_GRUXX.md` §2.2 reestructurada en 2.2.1 (activos no-core que quedan en raíz) / 2.2.2 (legacy movido). |
| D | `7f8a63de` (+ fix `a85601b6`) | Rename `gruxx`→`GRRux`: 11 archivos + sustitución de string interna en ~23 archivos, `__pycache__/` purgado donde el puente lo permitió. Ver tablas abajo. |

### Nota sobre el commit `7f8a63de` y su fix `a85601b6`

Al preparar el `git add` de D, un `git add -A` sin exclusión de pathspec (tras
fallar la sintaxis `':!_to_delete'` por el guion bajo inicial) **incluyó y
comiteó por error** archivos explícitamente prohibidos por el prompt:
`GRUXX_oraciones prueba.xlsx`, `GRUXX_oraciones_250*.txt(.bak)`,
`PENDIENTES_GRRUX.md`, los 3 `PROMPTS/prompt_DEUDA_INFRA*.md`, y todo
`complex sentences/`. Detectado inmediatamente al revisar el resumen de
archivos del propio commit, reportado a Julian, y corregido con un commit
**nuevo** (no amend, por protocolo) `a85601b6` que hace
`git rm --cached -r` de esos paths exactos — el contenido en disco no se
tocó, solo su estado de tracking. Verificado post-fix: todos vuelven a `??`
(untracked) con contenido intacto.

## Cuadro de renames de archivo (sub-hito D, 11 items)

| viejo | nuevo |
|---|---|
| `gruxx_ai1.py` | `grrux_ai1.py` |
| `gruxx_server.py` | `grrux_server.py` |
| `gruxx_motor.py` | `grrux_motor.py` |
| `test_gruxx_motor.py` | `test_grrux_motor.py` |
| `test_gruxx_server.py` | `test_grrux_server.py` |
| `gruxx-gui` | `grrux-gui` |
| `gruxx-gui.log` (untracked) | `grrux-gui.log` |
| `gruxx.desktop` | `grrux.desktop` |
| `docs/diagrama_gruxx.html` | `docs/diagrama_grrux.html` |
| `docs/diagrama_gruxx.svg` | `docs/diagrama_grrux.svg` |
| `aspect_classifier/data/glosario_gruxx.csv` | `aspect_classifier/data/glosario_grrux.csv` |

Consecuencia funcional del último rename: `aspect_classifier/glosario.py`
actualizado (referencia de carga del CSV) — verificado cargando 89 entradas
del glosario directamente en Python tras el cambio.

String interna (`gruxx`→`grrux`/`GRRux` según contexto, límites de palabra)
aplicada en ~23 archivos: los 11 renombrados + `README.md`, `docs/GUI.md`,
`docs/DESARROLLO.md`, `briefing_aspect_classifier.md`, `gui/app.js`,
`gui/index.html`, `instalar_comun.sh`, `instalar_estudiantes.sh`,
`publicar_github_limpio.sh`, y 13 módulos de `aspect_classifier/`. Cambios
reales de código (no solo prosa): `import gruxx_ai1`→`import grrux_ai1`,
`import gruxx_motor as _motor_real`→`import grrux_motor as _motor_real`,
`import gruxx_server`→`import grrux_server`, referencia al CSV del glosario.
Identificadores Python que contienen "gruxx" pegado a otra palabra por guion
bajo (p. ej. `_res_gruxx` en `test_l5.py`) se dejaron intactos a propósito
(no son el nombre de marca, son símbolos internos) — verificado con grep
dirigido tras el sed.

**Excluidos del rename** (decisión explícita, addendum D): `ESTADO_DEL_ARTE_GRUXX.md`
(fase controlada posterior), `GRUXX_oraciones*`/`PENDIENTES_GRRUX.md` (untracked,
material del usuario), los 6 archivos de §2.2.1, todo `CHECKPOINTS/`/`PROMPTS/`/`legacy/`,
`ud2rrg.py`.

## 21 archivos movidos a `legacy/` (sub-hito C)

`gruxx_ai.py`, `analizador_interactivo.py`, `analizador_interactivo1.py`,
`analizador_interactivo3.py`, `analizador_interactivo4.py`,
`analizador_texto_ls.py`, `analizar_texto.py`, `analizar_texto_bucle.py`,
`analizar_texto_ls.py`, `analizar_texto_ls_file.py`,
`analizar_texto_ls_file1.py`, `rrg_interactivo.py`,
`rrg_interactivo_batch.py`, `rrg_interactivotest.py`, `grrux_fix.py`,
`grrux_fix2.py`, `rrg_unificado.py`, `rrg_llm_fallback.py`,
`rrg_morph_classifier.py`, `debug.py`, `diagnostico.py`.

Verificado por grep exhaustivo antes de mover: ninguno importado por módulo
activo ni referenciado por script activo.

## Evidencia de pruebas

- `./venv/bin/python -m pytest -q --continue-on-collection-errors` (vía
  puente, ver limitaciones abajo): **288 passed**, sin ninguna falla fuera
  de las dos categorías de artefacto del puente (`discodop` / proxy de red).
  Misma firma (288 passed, 20 failed, 32 skipped, 3 errors) antes y después
  del rename de D — confirma que D no introdujo regresiones nuevas.
- `./venv/bin/python -m py_compile` sobre los 18 archivos tocados/renombrados
  en D: **OK**, sin errores de sintaxis.
- `test_grrux_server.py` en aislado: pasa igual que `test_gruxx_server.py`
  antes del rename (mismo conteo, mismo único fallo por `discodop`/export TXT,
  no relacionado con el rename).
- `aspect_classifier/glosario.py`: carga funcional de 89 entradas desde
  `glosario_grrux.csv` verificada directamente en Python.
- `git diff --stat 98d8e4ea -- ud2rrg.py`: **vacío** — `ud2rrg.py` no se tocó
  en ningún sub-hito, confirmando la invariante §9.3.

### GUI real: sustitución deliberada del check literal del prompt

El prompt original pide, como parte de la verificación, comprobar que "la
GUI arranca". Por la política que el propio DEUDA-INFRA.A dejó escrita en
`docs/DESARROLLO.md` ("Sesiones de modelo ejecutor: NO arrancar el servidor
real"), esta sesión **no levantó** `./grrux-gui` ni `uvicorn`. Se usó como
equivalente funcional el paso de `test_grrux_server.py` (`TestClient` +
motor stub, incluye `test_estado_listo_tras_startup` y el flujo de análisis
completo vía HTTP simulado). Julian puede correr `./grrux-gui` en su
terminal real si quiere el check literal.

## Limitaciones del puente remoto descubiertas (documentadas en `docs/DESARROLLO.md`)

1. `venv/bin/python` vía puente resuelve a Python de sistema (3.10.12), no al
   intérprete real del venv (3.10.20) — `discodop` (extensión compilada) no
   importable por esta vía. `venv/bin/pip` roto (shebang con ruta absoluta
   real inexistente en el puente).
2. Sin acceso de red en el puente — tests `test_slow_*` que hacen HTTP fallan
   con `ProxyError`, no por bug de código.
3. `device_bash` no puede borrar/mover archivos fuera del árbol montado
   ("Operation not permitted") — cada operación de git que genera locks
   temporales (`.git/index.lock`, `.git/HEAD.lock`,
   `.git/objects/*/tmp_obj_*`) requiere que Julian los borre manualmente en
   su terminal real antes de que el siguiente comando de git funcione.
   Ninguno de estos tres puntos es un problema del repo; son artefactos del
   mecanismo de puente y quedan documentados para la próxima sesión
   ejecutora que trabaje así.

## Pendientes de housekeeping (no bloqueantes, dejados para Julian)

- `_deuda_infra_d.sh` (script de automatización de D, en la raíz del repo,
  untracked): no se pudo borrar ni mover fuera del repo por la limitación
  #3 de arriba. Inocuo, Julian puede borrarlo cuando quiera.
- `__pycache__/`: purgado donde el puente lo permitió; puede quedar algún
  `.pyc` residual regenerable.

## Cierre

Bloque DEUDA-INFRA (sub-hitos A-D) cerrado. `ESTADO_DEL_ARTE_GRUXX.md`
actualizado: §2.1 (nombres de archivo post-rename), §2.2 (activos no-core /
legacy), §7 (historial), §8.1 (DEUDA-INFRA CERRADO, CONFIANZA como próximo
hito activo), §8.3 (línea de migración de nombres retirada, ya cumplida).
Próximo hito del roadmap: **CONFIANZA**.
