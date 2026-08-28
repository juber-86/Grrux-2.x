# PROMPT — DEUDA-INFRA (bloque 1 del roadmap 2026-08-17)

> Contrato de implementación para la sesión ejecutora. Léelo entero antes de tocar
> código. Este `.md` es la fuente de verdad del alcance; cualquier duda se resuelve
> **contra este documento**, no ampliándolo por iniciativa.

---

## 0. Contexto (por si arranca sesión nueva)

**GRRux** es el analizador RRG (Van Valin) para español descrito en
`ESTADO_DEL_ARTE_GRUXX.md`. Historial reciente cerrado hasta **BENEFACTIVAS**
(2026-08-12). Roadmap definido 2026-08-17 (ver §8.1 del ESTADO):

1. **DEUDA-INFRA** ← *este prompt*
2. CONFIANZA
3. LOGROS-DIANAS
4. FIX técnicos focales
5. Arquitectura (compuestas / LA3 / migración EL a inglés) — al final

Principio: **estabilizar antes de progresar**. Este hito no toca la arquitectura
de análisis (mapper, clasificador, ud2rrg, EL, linking): solo higieniza el
entorno para que los hitos siguientes tengan menos ruido.

**Git base**: rama `main` en `98d8e4ea`. Trabajar en `main` (o en una rama de
feature si lo prefieres, pero al final merge FF a `main`). Cada sub-hito
cierra con su commit; el bloque cierra con `CHECKPOINTS/CHECKPOINT_DEUDA_INFRA.md`.

---

## 1. Alcance (qué SÍ y qué NO)

### SÍ (los cuatro sub-hitos de este prompt):

- **A · Doc del ejecutor** — crear `docs/DESARROLLO.md` con invariantes §9,
  acceso a GUI local, procedimiento de pruebas aisladas, convención
  CHECKPOINTS/PROMPTS y commit-por-fase. Referenciar desde `README.md`.
- **B · Pruebas GUI aisladas — auditoría** — verificar que todas las pruebas
  del servidor/motor usen `TestClient` + motor STUB o instancia efímera en
  puerto libre, sin depender de una GUI corriendo. Documentar el
  procedimiento en `docs/DESARROLLO.md`. Corregir el gate aislado
  preexistente `timeout 90s ... pytest -q test_gruxx_server.py` (código 124)
  si se puede sin tocar la arquitectura del servidor; si no, dejarlo como
  limitación documentada.
- **C · Legacy separado** — mover los 17 archivos legacy de §2.2 del ESTADO
  (lista abajo) a `legacy/` con `git mv`. Actualizar §2.2 y §1 (mapa de
  archivos) del ESTADO para reflejar la nueva ubicación.
- **D · Rename `gruxx` → `GRRux`** — migración controlada de nombres, plan de
  ejecución detallado abajo. Sub-hito más grande; **antes de arrancar D**,
  pausar y confirmar con Julian el alcance exacto de renames de archivo
  (los cambios de string interna van sin pausa).

### NO (bajo ninguna circunstancia en este bloque):

- **NO tocar `ud2rrg.py`** (invariante §9.3). Aunque contiene la cadena
  `gruxx`, queda intocable. Los cambios que dependen de su cambio se
  documentan como pendientes futuros.
- **NO tocar `contextual_sentences.csv`** ni ningún dato curado.
- **NO tocar** clasificador, corroborador, `.joblib`, modelos.
- **NO** re-correr PUD.
- **NO tocar** archivos en `CHECKPOINTS/` ni `PROMPTS/` (son artefactos
  históricos; los nombres `gruxx` en su contenido se conservan tal cual).
- **NO tocar** los untracked del root que Julian dejó explícitamente:
  `GRUXX_oraciones prueba.xlsx`, `GRUXX_oraciones_250.txt`,
  `GRUXX_oraciones_250.txt.bak`, `GRUXX_oraciones_250_originales.txt`,
  `PENDIENTES_GRRUX.md`, `complex sentences/`.
- **NO** modificar la arquitectura del pipeline. Este hito es
  **puramente estructural/documental/nomenclatural**.

---

## 2. Sub-hito A · `docs/DESARROLLO.md` para el ejecutor

**Crear** `docs/DESARROLLO.md` con esta estructura mínima:

```markdown
# GRRux — Guía de desarrollo (para sesiones de modelo ejecutor)

## Setup local
- Python: `./venv/bin/python`
- Instalar: ver `README.md` (Bazzite/Arch/común).

## Convenciones (invariantes §9 del ESTADO_DEL_ARTE)
1. Cada fase cierra con commit + `CHECKPOINTS/CHECKPOINT_<hito>.md`.
   Los prompts de implementación viven en `PROMPTS/`.
2. `aspect_classifier/data/contextual_sentences.csv` es APPEND-ONLY.
   Nunca regenerar/auto-modificar.
3. `ud2rrg.py` no se toca salvo mandato explícito y gateado
   `language=='es'`/MISC.
4. Clasificador, corroborador y `.joblib` son intocables salvo fase de
   reentrenamiento explícita.
5. PUD: examen a ciegas, no re-correr.
6. Cada capa nueva con flag `enabled` → byte-idéntico con `false`
   (test obligatorio).
7. Gold de dianas: solo alterar con aprobación explícita + tabla
   auditada EL-vieja→EL-nueva.
8. OOM: no correr suites `--slow` con instancias de GRRux/GUI abiertas.
9. Separación de sesiones: DISEÑO redacta `PROMPTS/prompt_<hito>.md`,
   IMPLEMENTACIÓN los ejecuta. El `.md` es el contrato.

## Suites de pruebas
- **Rápida (default)**: `./venv/bin/python -m pytest -q` — sin marcadores
  `slow`. Debe pasar siempre.
- **Focal**: `./venv/bin/python -m pytest -q <archivo>` para módulos
  específicos.
- **Slow**: `RUN_SLOW=1 ./venv/bin/python -m pytest -q <archivo>` —
  activa integración con Stanza/BERTIN. **Nunca** correr con GUI abierta
  (advertencia OOM §9.8).

## Servidor GUI local
- URL: `http://127.0.0.1:8763/` (constante `PORT=8763` en `grrux-gui`).
- Arranque interactivo (usuario): `./grrux-gui` — sondea `/estado`, no
  levanta segunda instancia si ya hay una.
- Cierre: `pkill -f "uvicorn grrux_server:app"`.
- **Sesiones de modelo ejecutor**: NO arrancar el servidor real. Las
  pruebas del servidor usan `TestClient` de FastAPI con motor STUB
  inyectado (ver `test_grrux_server.py`); las del motor usan fixtures
  serializados. Si excepcionalmente hace falta levantar la GUI para
  pruebas exploratorias, usar puerto libre distinto de 8763 y cerrarla
  al terminar.

## Flujo de un hito
1. Leer `ESTADO_DEL_ARTE_GRUXX.md` §7 (historial) y §8 (pendientes).
2. Redactar `PROMPTS/prompt_<hito>.md` (sesión de DISEÑO).
3. Ejecutar (sesión de IMPLEMENTACIÓN): un commit por sub-hito, tests
   pasan al cierre de cada uno.
4. Cierre: `CHECKPOINTS/CHECKPOINT_<hito>.md` con evidencia (tests, EL
   ejemplos, decisiones tomadas). Actualizar §7 y §8 del ESTADO.
```

**Actualizar `README.md`** con un puntero al final de la sección de instalación:

> Para desarrollar sobre GRRux, ver `docs/DESARROLLO.md` (convenciones,
> pruebas, servidor local).

**Verificación**: `ls docs/DESARROLLO.md` existe; `grep DESARROLLO README.md` retorna una línea.

**Commit**: `DEUDA-INFRA.A: docs/DESARROLLO.md para el modelo ejecutor`.

---

## 3. Sub-hito B · Pruebas GUI aisladas — auditoría

Ejecutar este orden:

1. **Inventariar pruebas que tocan el servidor**:
   ```
   grep -rln "TestClient\|127.0.0.1:8763\|uvicorn\|grrux_server\|gruxx_server" \
     --include="test_*.py" --include="*_test.py"
   ```

2. **Para cada test**, verificar:
   - Usa `TestClient` (bien) → sin acción.
   - Hace HTTP contra `127.0.0.1:8763` (mal) → refactorizar a
     `TestClient` o marcar con `@pytest.mark.slow` y documentar por qué
     necesita instancia real (razón fuerte, no "es más fácil").
   - Levanta uvicorn/subprocess (mal) → mismo tratamiento.

3. **Diagnóstico conocido — CHECKPOINT_BENEFACTIVAS lo registra**:
   > El gate aislado del servidor conserva una limitación ambiental
   > preexistente: `timeout 90s ... pytest -q test_gruxx_server.py`
   > termina con código 124. `pytest -vv -s -x` se detiene en
   > `test_estado_listo_tras_startup`, durante el lifespan de
   > `TestClient`. Esos tests pasan dentro de la suite completa.

   Investigar la causa. Hipótesis: el lifespan del `TestClient` bloquea
   porque `motor.cargar()` intenta descargar Stanza. Si el motor STUB
   ya reemplaza esto, verificar la inyección. Si el problema es el
   startup event, considerar un fixture `session-scoped` que evite
   re-inicializar. **Si el arreglo requiere tocar `grrux_server.py` de
   forma no trivial**, documentar como pendiente y no arreglar en este
   sub-hito.

4. **Documentar el procedimiento aprobado** en `docs/DESARROLLO.md`
   (la sección "Servidor GUI local" ya tiene un puntero; ampliarlo si
   la auditoría descubre patrones).

**Verificación**: `./venv/bin/python -m pytest -q test_grrux_server.py` pasa
sin timeout (o queda documentada la razón de skip). Suite rápida completa
sigue verde.

**Commit**: `DEUDA-INFRA.B: auditoría pruebas GUI aisladas` (con lista de
tests inspeccionados en el mensaje de commit).

---

## 4. Sub-hito C · Legacy separado

**Archivos a mover a `legacy/`** (los 17 de §2.2 del ESTADO — el grep confirmó
que ninguno se importa desde el core activo):

```
gruxx_ai.py
analizador_interactivo.py
analizador_interactivo1.py
analizador_interactivo3.py
analizador_interactivo4.py
analizador_texto_ls.py
analizar_texto.py
analizar_texto_bucle.py
analizar_texto_ls.py
analizar_texto_ls_file.py
analizar_texto_ls_file1.py
rrg_interactivo.py
rrg_interactivo_batch.py
rrg_interactivotest.py
grrux_fix.py
grrux_fix2.py
rrg_unificado.py
rrg_llm_fallback.py
rrg_morph_classifier.py
linkage.py
convertir.py
export.py
debug.py
diagnostico.py
util.py
verbnet.py
add_traces_to_rrg_from_ud.py
```

(Nota: son ~27, no 17 — la lista de §2.2 estaba resumida. Confirmar cada uno
con `git ls-files <archivo>` antes de mover; si alguno no está tracked, mover
con `mv` directo, no `git mv`.)

**Procedimiento**:
```bash
mkdir -p legacy
git mv <archivo> legacy/<archivo>   # uno por uno o glob
```

**Verificar antes de commit** que ningún test o script activo importa desde
esos módulos (repetir el grep del sub-hito A del prompt de investigación):
```bash
for legacy in <cada nombre sin .py>; do
  grep -rl "^\(from\|import\) $legacy\b" \
    gruxx_ai1.py grrux_ai1.py grruxc_*.py aspect_classifier/*.py 2>/dev/null
done
```

Debe retornar vacío. Si aparece algo, PARAR y avisar (rompe la premisa).

**Actualizar `ESTADO_DEL_ARTE_GRUXX.md` §2.2** — reemplazar la ubicación
(raíz) por `legacy/` y añadir nota "movido en DEUDA-INFRA (2026-08-XX)".

**Commit**: `DEUDA-INFRA.C: mover legacy §2.2 a legacy/`.

---

## 5. Sub-hito D · Rename `gruxx` → `GRRux`

**⚠ ANTES DE ARRANCAR D**: pausar y confirmar con Julian los renames
de archivo (los cambios de string interna van sin pausa; solo los renames
de archivo requieren su OK).

**Alcance de renames de archivo**:

| viejo | nuevo | tipo |
|---|---|---|
| `gruxx_ai1.py` | `grrux_ai1.py` | módulo |
| `gruxx_server.py` | `grrux_server.py` | módulo |
| `gruxx_motor.py` | `grrux_motor.py` | módulo |
| `test_gruxx_motor.py` | `test_grrux_motor.py` | test |
| `test_gruxx_server.py` | `test_grrux_server.py` | test |
| `gruxx-gui` (launcher) | `grrux-gui` (launcher) | script |
| `gruxx-gui.log` | `grrux-gui.log` | log (en `.gitignore`) |
| `gruxx.desktop` | `grrux.desktop` | desktop file |

**Alcance de string interna** (sí sin pausa):

- Todos los `import gruxx_*` / `from gruxx_* import ...` → `import grrux_*`.
- Referencias a `gruxx_server:app` en `grrux-gui` y en cualquier script.
- Nombres de proceso en `pkill -f "uvicorn gruxx_server:app"` → `uvicorn grrux_server:app`.
- Referencias en HTML/JS/CSS (`gui/index.html`, `gui/app.js`) — títulos, IDs
  cosméticos. NO cambiar clases CSS o data-attrs que dependan tests puedan
  matchear.
- `gruxx.desktop`: campo `Exec=` y `Icon=` referencian al launcher renombrado.
- Install scripts (`instalar_*.sh`, `publicar_github_limpio.sh`): rutas y
  nombres de proceso.
- Docs: `README.md`, `docs/GUI.md`, `docs/DESARROLLO.md`,
  `docs/diagrama_gruxx.html` (renombrar también → `diagrama_grrux.html`),
  `briefing_aspect_classifier.md`.
- Strings de análisis en módulos activos (`aspect_classifier/*.py`,
  `rrg_ls_mapper.py`): reemplazar `gruxx` por `GRRux` **solo en mensajes
  al usuario / docstrings / comentarios**. NO tocar identificadores Python
  como nombres de variables/funciones que contengan `gruxx` (podrían ser
  parte de contratos API).

**NO tocar**:

- `ud2rrg.py` — invariante §9.3.
- `ESTADO_DEL_ARTE_GRUXX.md` — el nombre del archivo se conserva por
  ahora (Julian decidió aplazar el rename del handoff a fase controlada
  posterior — ver aplazado en §8.3 del ESTADO). Cambiar solo el título
  interno si aún dice "gruxx" y no "GRRux".
- `PENDIENTES_GRRUX.md` — untracked, no tocar.
- `CHECKPOINTS/*` y `PROMPTS/*` — artefactos históricos; el contenido
  conserva `gruxx` original.
- `GRUXX_oraciones_*.txt`, `GRUXX_oraciones prueba.xlsx` — untracked, no tocar.

**Procedimiento**:

1. **Rename de archivos** (uno a uno con `git mv`):
   ```bash
   git mv gruxx_ai1.py grrux_ai1.py
   # ... para cada archivo del cuadro
   ```
2. **Actualizar imports** con `sed` restringido a archivos específicos
   (NO con `sed -i` global — riesgo de tocar `ud2rrg.py`):
   ```bash
   for f in grrux_ai1.py grrux_server.py grrux_motor.py \
            test_grrux_motor.py test_grrux_server.py \
            aspect_classifier/*.py rrg_ls_mapper.py; do
     [ -f "$f" ] && sed -i 's/\bgruxx_ai1\b/grrux_ai1/g; s/\bgruxx_server\b/grrux_server/g; s/\bgruxx_motor\b/grrux_motor/g' "$f"
   done
   ```
   **Verificar** que `ud2rrg.py` NO cambió:
   ```bash
   git diff --stat ud2rrg.py   # debe estar vacío
   ```
3. **Actualizar launcher y scripts**:
   - `grrux-gui`: `PORT=8763` intacto, cambiar `uvicorn gruxx_server:app` → `uvicorn grrux_server:app`, cambiar `LOG=...gruxx-gui.log` → `LOG=...grrux-gui.log`, cambiar `[gruxx-gui]` prefijos.
   - `.gitignore`: cambiar `/gruxx-gui.log` → `/grrux-gui.log`.
   - `grrux.desktop`: `Exec=` apunta a `grrux-gui`, `Icon=` a `grrux_logo.png` (mantener `.png` si ya está renombrado, no lo estaba en el listado — verificar). Título/nombre visible → "GRRux".
   - `instalar_*.sh`, `publicar_github_limpio.sh`: rutas y nombres.
4. **Actualizar docs**: `README.md`, `docs/GUI.md`, `docs/DESARROLLO.md`,
   `briefing_aspect_classifier.md`, y renombrar `docs/diagrama_gruxx.html` → `docs/diagrama_grrux.html`.
5. **Actualizar HTML/JS**: `gui/index.html` título/copy, `gui/app.js` copy.
6. **Actualizar mensajes al usuario** en `aspect_classifier/*.py`,
   `rrg_ls_mapper.py`: reemplazar `gruxx` por `GRRux` **solo** en docstrings,
   comentarios y strings visibles. Identificadores Python intactos.

**Verificación exhaustiva** al terminar:

```bash
# 1. Suite rápida completa verde
./venv/bin/python -m pytest -q
# 2. Suite lenta focal verde
RUN_SLOW=1 ./venv/bin/python -m pytest -q aspect_classifier/test_l5.py
RUN_SLOW=1 ./venv/bin/python -m pytest -q aspect_classifier/test_notacion.py
./venv/bin/python -m aspect_classifier.test_ditransitivas --slow
# 3. GUI arranca y sirve /estado
./grrux-gui &
sleep 15 && curl -s http://127.0.0.1:8763/estado
pkill -f "uvicorn grrux_server:app"
# 4. ud2rrg.py intacto
git diff --stat ud2rrg.py    # vacío
# 5. No queda 'gruxx' fuera de: CHECKPOINTS/, PROMPTS/, ud2rrg.py,
#    ESTADO_DEL_ARTE_GRUXX.md (nombre), PENDIENTES_GRRUX.md, y los
#    GRUXX_oraciones*.
grep -rl "gruxx" --include="*.py" --include="*.md" --include="*.sh" \
     --include="*.desktop" --include="*.html" --include="*.js" --include="*.css" \
     | grep -v -E "^(CHECKPOINTS|PROMPTS|ud2rrg\.py|ESTADO_DEL_ARTE_GRUXX|PENDIENTES_GRRUX|GRUXX_oraciones|legacy/)"
```

La última query debe retornar cero líneas.

**Commit**: `DEUDA-INFRA.D: rename gruxx → GRRux (módulos, launcher, docs, GUI)`.

---

## 6. Cierre del bloque

**Crear** `CHECKPOINTS/CHECKPOINT_DEUDA_INFRA.md` con:

- Fecha, alcance, decisiones.
- Cuadros de renames aplicados (archivo/línea).
- Evidencia de pruebas (suite rápida verde, gates focales, GUI arranca).
- Confirmación de que `ud2rrg.py` no fue tocado (diff vacío).
- Lista de archivos legacy movidos y verificación de que nadie los importa.

**Actualizar** `ESTADO_DEL_ARTE_GRUXX.md`:
- §7: añadir DEUDA-INFRA a la cronología como cerrada.
- §8.1: marcar DEUDA-INFRA como CERRADO; el próximo hito activo es CONFIANZA.
- §2.1/§2.2: reflejar renames de archivo y la nueva ubicación `legacy/`.
- §8.3: quitar la línea "Migración de nombres `gruxx` → `GRRux`, incluido
  `gruxx_ai1.py` → `grrux_ai1.py`" (queda hecha).

**Commit final**: `DEUDA-INFRA: cierre + CHECKPOINT`.

**Higiene git**: al terminar, `main` debe apuntar al último commit y el árbol
de trabajo debe estar limpio (los untracked que Julian dejó explícitos siguen
untracked, sin cambios).

---

## 7. Salidas fuera de alcance (registrar como pendiente, NO ejecutar aquí)

- Rename de `ESTADO_DEL_ARTE_GRUXX.md` → `ESTADO_DEL_ARTE.md` (Julian decidió
  fase controlada posterior).
- Purga física de la carpeta `legacy/` (solo la aísla, no la borra).
- Rename de `ud2rrg.py` o su capa española.
- Cualquier cambio a lógica de análisis (mapper, clasificador, EL, linking).

---

## 8. Rollback

Si algún sub-hito rompe pruebas y la causa no es obvia en <15 min, hacer
`git reset --hard <SHA anterior>` al sub-hito, avisar a Julian con el error
específico, y NO continuar con los sub-hitos posteriores. La convención del
proyecto es que un hito o cierra limpio con tests verdes o no cierra.

---

Fin del contrato.
