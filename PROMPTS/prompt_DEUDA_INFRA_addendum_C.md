# ADDENDUM al prompt DEUDA-INFRA — sub-hito C (REV 2)

**Fecha**: 2026-08-18. **Motivos**:
- REV 1: hallazgo del ejecutor — `ud2rrg.py` importa 5 archivos listados
  como legacy.
- REV 2: pregunta de Julian — `convertir.py` también es activo (instalador
  + CLI). Verificación cruzada con `instalar_estudiantes.sh` confirmó la
  lista real de activos.

---

## Hechos (verificados por el planeador)

### A. `ud2rrg.py` (líneas 19-36) importa sin condicionar

```python
import export
import linkage
import util
from verbnet import say_hyponyms, conjecture_hyponyms, care_hyponyms, \
    consider_hyponyms, begin_hyponyms, sustain_hyponyms, stop_hyponyms
from add_traces_to_rrg_from_ud import *
```

Esos 5 son importados **exclusivamente** por `ud2rrg.py` (grep desde
todo el repo confirmó cero hits desde cualquier otro módulo).

### B. `convertir.py` es una utilidad CLI activa

Script standalone: consume un `.conllu` y llama a `ud2rrg.transform()`
directamente. Verificado activo por:

- `instalar_estudiantes.sh` línea 83: `requerir convertir.py "convertir.py"`
  (aborta la instalación si falta).
- `setup_analizador_stanza.sh` línea 66: `os.system(f"python3 convertir.py …")`.
- `ud2rrg_stanza_convertidor_fedora.sh` líneas 92 y 167: crea y ejecuta
  `convertir.py`.
- `descargar_treebanks_es.sh` línea 83: lo referencia en instrucciones
  al usuario.

### C. Lista canónica de "archivos activos requeridos" según el instalador

`instalar_estudiantes.sh` marca como requeridos (líneas 82-99):

```
gruxx_ai1.py, convertir.py, ud2rrg.py, export.py, linkage.py, util.py,
verbnet.py, add_traces_to_rrg_from_ud.py, rrg_ls_mapper.py,
requirements.txt, aspect_classifier/*  (paquete + config + datos).
```

Ningún otro nombre del cuadro legacy aparece en ningún `.sh`, `.desktop`
o script activo (grep verificatorio del planeador).

---

## Decisión (respeta §9.3)

### Se quedan en la raíz (6 archivos, NO mover)

| archivo | motivo |
|---|---|
| `export.py` | dependencia exclusiva de `ud2rrg.py` |
| `linkage.py` | dependencia exclusiva de `ud2rrg.py` |
| `util.py` | dependencia exclusiva de `ud2rrg.py` |
| `verbnet.py` | dependencia exclusiva de `ud2rrg.py` |
| `add_traces_to_rrg_from_ud.py` | dependencia exclusiva de `ud2rrg.py` |
| `convertir.py` | utilidad CLI activa, exigida por el instalador |

### Se mueven a `legacy/` (21 archivos)

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
debug.py
diagnostico.py
```

**Verificado por grep**: ninguno de estos 21 es importado por módulo
activo, ni referenciado por script activo (`.sh`, `.desktop`,
`instalar_*`, `README.md`).

---

## Actualización al ESTADO §2.2

Reescribir §2.2 así:

```markdown
### 2.2 Archivos históricos de la raíz

#### 2.2.1 Activos no-core que quedan en raíz (NO mover, NO renombrar)

Estos archivos no forman parte del núcleo activo listado en §2.1, pero
son requeridos por el sistema y no pueden moverse sin romperlo.

**Dependencias exclusivas de `ud2rrg.py`** (invariante §9.3 impide
tocarlas): `export.py`, `linkage.py`, `util.py`, `verbnet.py`,
`add_traces_to_rrg_from_ud.py`. Importadas sin condicionar en la
cabecera de `ud2rrg.py` (líneas 20-36). Ningún otro módulo las usa.

**Utilidad CLI activa**: `convertir.py`. Script standalone que consume
un `.conllu` y llama a `ud2rrg.transform()`. Exigida por
`instalar_estudiantes.sh` (línea 83, `requerir convertir.py`); invocada
por `setup_analizador_stanza.sh`, `ud2rrg_stanza_convertidor_fedora.sh`
y referenciada en `descargar_treebanks_es.sh`.

#### 2.2.2 LEGACY muerto (en `legacy/`, movido en DEUDA-INFRA 2026-08-XX)

`gruxx_ai.py` (viejo entry), `analizador_*` (×5), `analizar_texto*` (×5),
`rrg_interactivo*` (×3), `grrux_fix*` (×2), `rrg_unificado.py`,
`rrg_llm_fallback.py`, `rrg_morph_classifier.py`, `debug.py`,
`diagnostico.py`.

Sedimento de exploración previa a la arquitectura actual. Verificado por
grep exhaustivo: ninguno importado por módulo activo, ninguno referenciado
por script activo. Candidatos a purga futura desde `legacy/`.
```

---

## Cambios al resto del sub-hito C

- El paso "verificación pre-commit con grep" ahora ya no debería fallar
  con la lista depurada. Si aparece un hit no esperado, PARAR igual y
  avisar (invariante del contrato).
- Mensaje de commit: `DEUDA-INFRA.C: mover legacy §2.2.2 a legacy/ (los
  6 archivos de §2.2.1 quedan en raíz por dependencia de ud2rrg.py o
  del instalador)`.
- Sub-hitos A, B, D del prompt original: sin cambios estructurales.

---

## Nota para el sub-hito D (rename gruxx → GRRux)

El cuadro de renames de archivo NO incluye a los 6 archivos de §2.2.1.
- Los 5 `dependencias-de-ud2rrg` no se renombran (romperían `ud2rrg.py`).
- `convertir.py` no contiene `gruxx` en su nombre, así que no aplica el
  rename de archivo; su contenido (7 líneas de importaciones + código
  Python) tampoco menciona `gruxx`. Sin cambios.

Cualquier símbolo o mención de `gruxx` en el interior de los 5
`dependencias-de-ud2rrg` se queda tal cual y se anota como pendiente
futuro en §8.3 del ESTADO.

---

Fin del addendum REV 2. Continuar con la ejecución bajo estas reglas.
