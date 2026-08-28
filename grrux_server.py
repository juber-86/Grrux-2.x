"""
grrux_server.py
================
Fase GUI, Etapas G1.1 + G2 §2 — servidor local que expone `grrux_motor` y
el bucle de corrección (`aspect_classifier.correccion`) a la GUI (`gui/`).
PROHIBIDO tocar el motor ni la lógica de corrección: este módulo es SOLO
transporte HTTP.

- `127.0.0.1:8763`, `workers=1` (advertencia OOM del checkpoint: Stanza +
  BERTIN residentes ~2 GB, UNA sola instancia).
- `threading.Lock` alrededor de `analizar` y de los `corregir_*` que pueden
  re-analizar (`/corregir/el`, `/corregir/enrutado`) o escribir en los
  léxicos vivos (`/corregir/clase`) — el motor no es reentrante y una
  corrección nunca debe solaparse con un análisis. `/corregir/validar-el`
  es puro (sin persistir, sin tocar Stanza) y NO usa el lock.
- El motor se INYECTA (`crear_app(motor=...)`) para poder testear con un
  stub sin cargar Stanza (ver `test_grrux_server.py`, patrón G1.4);
  `data_dir`/`config_path` también son inyectables — los `corregir_*` de
  `correccion.py` ya los aceptan para no tocar los léxicos reales en tests.

Dependencias nuevas (venv): fastapi==0.139.0, uvicorn==0.51.0 (arrastran
starlette==1.3.1, pydantic==2.13.4 — versiones exactas anotadas en el
checkpoint G1).

Lanzar (dev, sin el script `grrux-gui`):
    ./venv/bin/uvicorn grrux_server:app --host 127.0.0.1 --port 8763
"""

import csv
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import grrux_motor as _motor_real
from aspect_classifier import correccion, glosario
from aspect_classifier.gui_contract import NODE_GLOSSARY_KEYS, PERI_GLOSSARY_KEYS, ROUTING_BY_KEY

HOST = "127.0.0.1"
PORT = 8763

_GUI_DIR = Path(__file__).parent / "gui"


class OracionIn(BaseModel):
    oracion: str


class ValidarElIn(BaseModel):
    analisis_id: str
    sub_idx: int
    el: str


class ClaseIn(BaseModel):
    analisis_id: str
    sub_idx: int
    clase: str


class ElIn(BaseModel):
    analisis_id: str
    sub_idx: int
    el: str


class EnrutadoIn(BaseModel):
    analisis_id: str
    sub_idx: int
    elemento_id: int | None = None
    destino: str | None = None
    ruta_origen: str | None = None
    ruta_destino: str | None = None


class OperadorIn(BaseModel):
    analisis_id: str
    sub_idx: int
    operador: str                 # IF | TNS | ASP | NEG | MOD | STA
    accion: str                   # cambiar | quitar | anadir
    valor: str | None = None      # None al quitar


class TodoIn(BaseModel):
    analisis_id: str
    sub_idx: int
    el: str
    clase: str


def _respuesta_correccion(resultado: dict, analisis_nuevo: dict | None = None) -> dict:
    detalle = {k: v for k, v in resultado.items() if k != "accion"}
    return {"accion": resultado.get("accion"), "detalle": detalle,
            "analisis_nuevo": analisis_nuevo}


def _leer_csv(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def crear_app(motor=_motor_real, data_dir=None, config_path=None) -> FastAPI:
    """Fábrica de la app — `motor` inyectable (stub en tests, `grrux_motor`
    real en producción). Un `threading.Lock` por app, no global: cada test
    con su propio stub tiene su propio candado. `data_dir`/`config_path` se
    reenvían tal cual a los `corregir_*` (tests: dir temporal; producción:
    `None` = los léxicos/config reales, igual que la CLI)."""
    lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        motor.cargar()
        yield

    app = FastAPI(title="GRRux GUI", lifespan=lifespan)

    @app.middleware("http")
    async def _sin_cache_navegador(request, call_next):
        """Bug real reportado por Julian tras G3: `StaticFiles` no manda
        `Cache-Control`, así que el navegador cachea `gui/*` por heurística
        (basada en `Last-Modified`) y sirve HTML/JS/CSS de una fase anterior
        sin revalidar -- ni un refresh normal lo nota. Fuerza revalidación
        SIEMPRE (herramienta local de un solo usuario: el costo es un 304
        instantáneo en localhost, nunca recarga de más)."""
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache"
        return response

    def _res_o_404(analisis_id: str) -> dict:
        res = motor.obtener_crudo(analisis_id)
        if res is None:
            raise HTTPException(status_code=404,
                                detail="el análisis expiró — vuelve a analizar la oración")
        return res

    def _fabrica_reanalizar():
        """`reanalizar_fn` para `corregir_el`/`corregir_enrutado`: UN solo
        pipeline real vía `motor.analizar` (que ya cachea el crudo bajo un
        `analisis_id` nuevo) — se recupera ESE crudo para la confirmación
        de `correccion.py` en vez de correr el pipeline dos veces. El
        contrato completo (para `analisis_nuevo`, el diff de la GUI) queda
        en `caja` — un dict fresco POR REQUEST (no una variable compartida
        del módulo/app): sin eso, dos correcciones concurrentes pisarían el
        mismo casillero antes de que cada una leyera su propio resultado."""
        caja: dict = {}

        def reanalizar(oracion: str) -> dict:
            caja["nuevo"] = motor.analizar(oracion)
            aid = caja["nuevo"].get("analisis_id")
            crudo = motor.obtener_crudo(aid) if aid else None
            return crudo or {"oracion": oracion, "ls_lista": []}

        return reanalizar, caja

    @app.get("/estado")
    def estado():
        return motor.estado()

    @app.post("/analizar")
    def analizar(body: OracionIn):
        oracion = (body.oracion or "").strip()
        if not oracion:
            raise HTTPException(status_code=400, detail="la oración está vacía")
        # El motor NUNCA lanza (ver grrux_motor.analizar): cualquier fallo
        # del pipeline ya viene reportado en el campo "error" del contrato,
        # nunca como 500 con traceback al usuario.
        with lock:
            return motor.analizar(oracion)

    @app.get("/glosario")
    def glosario_endpoint(termino: str | None = None):
        entradas = glosario.cargar_glosario()
        if termino is None:
            return entradas
        return glosario.buscar(termino, entradas)

    @app.get("/contrato/gui")
    def contrato_gui():
        """Claves canónicas consumidas por la GUI; no duplica definiciones."""
        return {"tooltips": NODE_GLOSSARY_KEYS, "peri": PERI_GLOSSARY_KEYS,
                "rutas": list(ROUTING_BY_KEY.values())}

    @app.post("/corregir/validar-el")
    def corregir_validar_el(body: ValidarElIn):
        res = _res_o_404(body.analisis_id)
        return correccion.validar_el_en_vivo(res, body.sub_idx, body.el)

    @app.post("/corregir/clase")
    def corregir_clase_endpoint(body: ClaseIn):
        res = _res_o_404(body.analisis_id)
        with lock:
            resultado = correccion.corregir_clase(
                res, body.sub_idx, body.clase, data_dir=data_dir,
                verb_lemma=_motor_real.lema_raiz(res, body.sub_idx))
        return _respuesta_correccion(resultado)

    @app.post("/corregir/el")
    def corregir_el_endpoint(body: ElIn):
        res = _res_o_404(body.analisis_id)
        reanalizar, caja = _fabrica_reanalizar()
        with lock:
            resultado = correccion.corregir_el(
                res, body.sub_idx, body.el, reanalizar, data_dir=data_dir,
                verb_lemma=_motor_real.lema_raiz(res, body.sub_idx))
        return _respuesta_correccion(resultado, caja.get("nuevo"))

    @app.post("/corregir/enrutado")
    def corregir_enrutado_endpoint(body: EnrutadoIn):
        res = _res_o_404(body.analisis_id)
        reanalizar, caja = _fabrica_reanalizar()
        with lock:
            resultado = correccion.corregir_enrutado(
                res, body.sub_idx, body.elemento_id, body.ruta_destino or body.destino,
                reanalizar, data_dir=data_dir, config_path=config_path,
                verb_lemma=_motor_real.lema_raiz(res, body.sub_idx),
                ruta_origen=body.ruta_origen)
        return _respuesta_correccion(resultado, caja.get("nuevo"))

    @app.post("/corregir/operador")
    def corregir_operador_endpoint(body: OperadorIn):
        """OPERATORS_2 §2. Mismo candado que las demás correcciones que pueden
        re-analizar y/o escribir en config: GRRux decide SOLO si la corrección
        va a una lista de config EN VIVO (hueco léxico) o a staging (error de
        parse) — el usuario nunca elige archivo."""
        res = _res_o_404(body.analisis_id)
        reanalizar, caja = _fabrica_reanalizar()
        with lock:
            resultado = correccion.corregir_operador(
                res, body.sub_idx, body.operador, body.accion, body.valor,
                reanalizar, data_dir=data_dir, config_path=config_path)
        return _respuesta_correccion(resultado, caja.get("nuevo"))

    @app.post("/corregir/todo")
    def corregir_todo_endpoint(body: TodoIn):
        """G3 §2 — EL + clase en un solo paso, un solo re-análisis compartido
        (ver `correccion.corregir_todo`); mismo candado que las demás
        correcciones que pueden re-analizar."""
        res = _res_o_404(body.analisis_id)
        reanalizar, caja = _fabrica_reanalizar()
        with lock:
            resultado = correccion.corregir_todo(
                res, body.sub_idx, body.el, body.clase, reanalizar, data_dir=data_dir,
                verb_lemma=_motor_real.lema_raiz(res, body.sub_idx))
        return _respuesta_correccion(resultado, caja.get("nuevo"))

    @app.get("/exportar/txt")
    def exportar_txt_endpoint(analisis_id: str):
        """G3 §4.3 — MISMO formato GRR que la terminal (ver
        `grrux_motor.render_txt_grr`). Puro: no usa el lock (no toca Stanza
        ni persiste nada)."""
        res = _res_o_404(analisis_id)
        return PlainTextResponse(_motor_real.render_txt_grr(res))

    @app.get("/exportar/conllu")
    def exportar_conllu_endpoint(analisis_id: str):
        """G3 §4.4 — el `.conllu` anotado tal cual lo cacheó `analizar()`
        (insumo del modo `.conllu` de la CLI y de terceros)."""
        res = _res_o_404(analisis_id)
        return PlainTextResponse(res.get("conllu_texto") or "")

    @app.get("/curador/staging")
    def curador_staging_endpoint():
        """G3 §5 — SOLO LECTURA: cuenta y expone las filas de staging + el
        log maestro. Nunca escribe nada -- la promoción a léxicos vivos /
        `contextual_sentences.csv` sigue siendo edición MANUAL de Julian."""
        base = Path(data_dir) if data_dir else (Path(__file__).parent / "aspect_classifier" / "data")
        archivos = {"correcciones_clase": "correcciones_clase.csv",
                   "correcciones_el": "correcciones_el.csv",
                   "correcciones_enrutado": "correcciones_enrutado.csv"}
        salida = {}
        for clave, nombre in archivos.items():
            filas = _leer_csv(base / nombre)
            salida[clave] = {"filas": filas, "total": len(filas)}
        log = _leer_csv(base / "correcciones_log.csv")
        por_accion: dict = {}
        for fila in log:
            a = fila.get("accion", "")
            por_accion[a] = por_accion.get(a, 0) + 1
        salida["log_maestro"] = {"filas": log, "total": len(log), "por_accion": por_accion}
        return salida

    if _GUI_DIR.exists():
        app.mount("/", StaticFiles(directory=str(_GUI_DIR), html=True), name="gui")

    return app


app = crear_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, workers=1)
