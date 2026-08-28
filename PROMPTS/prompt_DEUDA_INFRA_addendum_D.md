# ADDENDUM al prompt DEUDA-INFRA — sub-hito D (rename gruxx → GRRux)

**Fecha**: 2026-08-18. **Motivo**: pausa exigida por el prompt antes de
arrancar D — confirmación de Julian sobre el cuadro de renames, con
verificación del planeador que agregó 3 archivos omitidos.

---

## Cuadro CANÓNICO de renames de archivo (11 items, OK de Julian)

| viejo | nuevo | tipo |
|---|---|---|
| `gruxx_ai1.py` | `grrux_ai1.py` | módulo |
| `gruxx_server.py` | `grrux_server.py` | módulo |
| `gruxx_motor.py` | `grrux_motor.py` | módulo |
| `test_gruxx_motor.py` | `test_grrux_motor.py` | test |
| `test_gruxx_server.py` | `test_grrux_server.py` | test |
| `gruxx-gui` | `grrux-gui` | shell launcher |
| `gruxx-gui.log` | `grrux-gui.log` | log (actualizar `.gitignore`) |
| `gruxx.desktop` | `grrux.desktop` | desktop file |
| `docs/diagrama_gruxx.html` | `docs/diagrama_grrux.html` | doc |
| `docs/diagrama_gruxx.svg` | `docs/diagrama_grrux.svg` | doc |
| `aspect_classifier/data/glosario_gruxx.csv` | `aspect_classifier/data/glosario_grrux.csv` | data curada |

**Consecuencia crítica de renombrar `glosario_gruxx.csv`**: hay que
actualizar `aspect_classifier/glosario.py` (que lo carga) y cualquier
test que hardcodeé el path. El CONTENIDO del CSV no se toca — solo
filename. Verificable al cierre con:
```bash
grep -r "glosario_gruxx" --include="*.py" --include="*.md" --include="*.sh"
```
Debe retornar cero hits fuera de CHECKPOINTS/, PROMPTS/, legacy/.

## Exclusiones explícitas (NO renombrar)

- `ESTADO_DEL_ARTE_GRUXX.md` — decisión de Julian, fase controlada posterior.
- `GRUXX_oraciones prueba.xlsx`, `GRUXX_oraciones_250*.txt` — untracked,
  material de trabajo local del usuario.
- `PENDIENTES_GRRUX.md` — untracked, ya usa la convención nueva.
- Los 6 archivos de §2.2.1 (5 dependencias de `ud2rrg.py` + `convertir.py`).
- Todo bajo `CHECKPOINTS/`, `PROMPTS/`, `legacy/`.
- `ud2rrg.py` (§9.3).
- `__pycache__/*.pyc` — regenerables; ver housekeeping abajo.

## Housekeeping del bytecode

Después de todos los renames de archivo y antes del commit final del
sub-hito D:

```bash
rm -rf __pycache__/ aspect_classifier/__pycache__/
```

(Los .pyc viejos apuntan a nombres desaparecidos y romperían imports
si algún runtime los reutiliza. Regeneran solos al importar.)

## String interna (sin pausa)

Todo lo del prompt original sección D "Alcance de string interna"
sigue vigente: imports, referencias en scripts, HTML/JS/CSS, docs,
mensajes al usuario. Sin cambios estructurales.

**Añadir** una comprobación específica para el glosario:
- `aspect_classifier/glosario.py` — buscar la línea de load (probablemente
  `Path(...) / "glosario_gruxx.csv"` o similar) y actualizar la referencia.
- Tests de `glosario.py` si existen.

## Verificación final del sub-hito D (query grep del prompt original, corregida)

```bash
grep -rl "gruxx" \
     --include="*.py" --include="*.md" --include="*.sh" \
     --include="*.desktop" --include="*.html" --include="*.js" --include="*.css" \
     --include="*.csv" --include="*.yaml" --include="*.yml" \
  | grep -v -E "^(CHECKPOINTS/|PROMPTS/|legacy/|ud2rrg\.py|ESTADO_DEL_ARTE_GRUXX|PENDIENTES_GRRUX|GRUXX_oraciones)"
```

Debe retornar cero líneas. Si aparece algo del glosario o de los diagramas
de docs, faltó el rename.

## Commit del sub-hito D

`DEUDA-INFRA.D: rename gruxx → GRRux (11 archivos + string interna, --pycache--/ purgado)`

Si prefieres separar en dos commits (uno para renames de archivo, otro
para string interna), está bien; en ese caso los mensajes serían
`DEUDA-INFRA.D.1: rename de archivos` y `DEUDA-INFRA.D.2: string interna`.

---

Fin del addendum. Ejecutar D con este cuadro.
