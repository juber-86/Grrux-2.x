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

## Auditoría de pruebas GUI aisladas (DEUDA-INFRA.B, 2026-08-18)
- Único archivo que toca el servidor: `test_grrux_server.py` (27 pruebas,
  3 marcadas `test_slow_*`). Todas usan `TestClient` de FastAPI con
  `_MotorStub` inyectado — ninguna hace HTTP real contra
  `127.0.0.1:8763` ni levanta `uvicorn`/subprocess. No hay `conftest.py`
  que arranque servidores (grep amplio de `uvicorn`/`127.0.0.1:8763` en
  todo el árbol activo solo devuelve `grrux_server.py` mismo).
- El límite documentado en `CHECKPOINT_BENEFACTIVAS.md` (`timeout 90s
  ... pytest -q test_grrux_server.py` → código 124, colgado en
  `test_estado_listo_tras_startup` durante el lifespan de `TestClient`)
  **no se reprodujo** al re-ejecutar hoy: `pytest -q test_grrux_server.py`
  corre en ~7-8s (24 passed, 3 skipped, 1 failed, sin timeout). Causa
  probable: algo transitorio de aquella sesión (p.ej. un intento de red
  que ya no ocurre con las cachés locales actuales); no se tocó
  `grrux_server.py`. Si el timeout reaparece en otra máquina/sesión,
  repetir con `pytest -vv -s -x` para localizar el punto exacto antes de
  tocar el servidor.
- Hallazgo nuevo, sin relación con el timeout anterior: el único test que
  falla hoy es `test_exportar_txt_mismo_formato_grr_que_render_bloque` —
  `ModuleNotFoundError: No module named 'discodop'` en
  `grrux_motor.py:423` (`render_txt_grr`, endpoint `/exportar/txt`, fase
  G3). Es un hueco de dependencia del `venv` (probablemente
  `disco-dop` no está compilado/instalado en este entorno), no de la
  arquitectura del servidor ni de la GUI; queda fuera de alcance de
  DEUDA-INFRA (no toca lógica de análisis). Pendiente técnico anotado
  para revisión de instalación/`requirements.txt`.

## Limitaciones conocidas del puente remoto (sesiones vía bridge)

Hallazgo durante la verificación de DEUDA-INFRA.C (2026-08-18), relevante
para cualquier sesión de modelo ejecutor que use un puente remoto (no una
terminal real en la máquina de Julian):

- `./venv/bin/python` resuelto desde el puente **no es el intérprete real
  del venv**: el symlink `venv/bin/python -> python3.10 -> /usr/bin/python3.10`
  apunta a un Python del sistema (3.10.12) distinto del que creó el venv
  (`pyvenv.cfg` dice `version = 3.10.20`). Site-packages sí es el real
  (montado), así que los paquetes puros funcionan, pero **`discodop` (extensión
  compilada) no es importable por esta vía** — `ModuleNotFoundError: No module
  named 'discodop'` en cualquier módulo que lo requiera (`export.py` —
  dependencia de `ud2rrg.py` — y los tests que construyen `ParentedTree`
  directamente: `test_completeness.py`, `test_linking.py`,
  `test_grrux_motor.py`, `test_grrux_server.py::test_exportar_txt_*`,
  gran parte de `test_ud2rrg_es.py`). `venv/bin/pip` falla directamente
  (`bad interpreter`) porque su shebang tiene la ruta absoluta real
  (`/home/jbj86/proyectos/ud2rrg/venv/bin/python3.10`), que no existe dentro
  del puente.
- El puente tampoco tiene acceso de red: pruebas `test_slow_*` que intentan
  una llamada HTTP (p. ej. `aspect_classifier/test_operadores.py`) fallan con
  `requests.exceptions.ProxyError`, no por un problema del código.
- **Ninguno de los dos es un problema real del repo** — son artefactos del
  puente. En la terminal real de Julian, `./venv/bin/python -m pytest -q`
  corre limpio (382 passed, 37 skipped registrado en
  `CHECKPOINT_BENEFACTIVAS.md`). Verificado el 2026-08-18: con
  `pytest -q --continue-on-collection-errors` desde el puente, las únicas
  fallas/errores caen en esas dos categorías (discodop / proxy); **288
  passed** sin ninguna falla de otro tipo — es la señal a usar para
  confirmar que un cambio no rompió nada real cuando se trabaja desde un
  puente sin `discodop`/red.
- Si una sesión ejecutora vía puente necesita confirmar la suite completa
  de verdad (no solo "no rompí nada nuevo"), debe pedirle a Julian que la
  corra en su terminal real, o ceñirse a archivos/tests que no toquen
  `discodop` ni red.

## Flujo de un hito
1. Leer `ESTADO_DEL_ARTE_GRUXX.md` §7 (historial) y §8 (pendientes).
2. Redactar `PROMPTS/prompt_<hito>.md` (sesión de DISEÑO).
3. Ejecutar (sesión de IMPLEMENTACIÓN): un commit por sub-hito, tests
   pasan al cierre de cada uno.
4. Cierre: `CHECKPOINTS/CHECKPOINT_<hito>.md` con evidencia (tests, EL
   ejemplos, decisiones tomadas). Actualizar §7 y §8 del ESTADO.

## Corrección a las limitaciones del puente (2026-08-19)

La nota de arriba (DEUDA-INFRA, 2026-08-18) es correcta en lo de `discodop` y la red, pero
la sesión de DITRANS-AGX asumió además que **Stanza no era ejecutable desde el puente**. Es
falso, y conviene dejarlo escrito para que ninguna sesión futura vuelva a bloquearse por ahí:

- Los modelos de Stanza están **dentro del repo**, en `.stanza_cache/resources/` (1,5 GB,
  `es/` completo). No en `~/stanza_resources`. Ojo: en el puente, `$HOME` es el del sandbox,
  no el de Julian — un `ls ~/stanza_resources` vacío NO significa que no haya modelos.
- `torch`, `stanza` y `transformers` importan bien desde el puente (site-packages está
  montado; solo fallan las extensiones compiladas ausentes del venv, como `discodop`).
- Para correr el parser desde una sesión de puente:

  ```python
  import os
  os.environ["STANZA_RESOURCES_DIR"] = os.path.join(os.getcwd(), ".stanza_cache", "resources")
  import stanza
  nlp = stanza.Pipeline(lang='es', processors='tokenize,mwt,pos,lemma,depparse',
                        verbose=False, download_method=None)   # download_method=None: no intenta red
  ```

  Con esto se puede verificar **toda la cadena determinista** (parse → `nucleo_periferia` →
  `ditransitivas` → EL) contra el parser real, sin fixtures a mano.
- Lo que sigue sin funcionar desde el puente: **BERTIN** (el clasificador aspectual;
  `extractor.py` llama a `from_pretrained` sin `cache_dir`, así que busca en
  `~/.cache/huggingface` de la máquina de Julian, fuera de lo montado, y no hay red para
  descargarlo) y **`discodop`**. Es decir: no se puede correr `grrux_motor.analizar()` de
  punta a punta, pero sí todo lo que no dependa del vector aspectual.

### BERTIN también es alcanzable (con la caché montada)

Si la sesión tiene acceso a `~/.cache/huggingface` de Julian (el puente lo permite pidiendo
la carpeta), el pipeline completo corre sin red:

```python
os.environ["HF_HOME"] = "<ruta montada de ~/.cache/huggingface>"
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["TRANSFORMERS_OFFLINE"] = "1"
```

Con eso `AspectClassifier().load()` funciona y se puede correr `grrux_motor.analizar()` de
punta a punta. Único obstáculo: `grrux_ai1.cargar_pipeline_stanza` llama a `stanza.download()`
ante cualquier fallo del `Pipeline`, y eso muere con proxy 403; se sortea inyectando el
pipeline a mano:

```python
import stanza, grrux_motor
grrux_motor._nlp = stanza.Pipeline(lang='es', processors='tokenize,mwt,pos,lemma,depparse',
                                   verbose=False, download_method=None)
```

Sigue sin funcionar solo `discodop`, así que el árbol RRG in-process cae a `None` — el
análisis semántico (EL, clase, linking) es completo igualmente.
