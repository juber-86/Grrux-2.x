"""Tests de `grrux_server.py` — Fase GUI, Etapa G1.4.

Rápidos: `TestClient` de FastAPI con un MOTOR STUB inyectado (sin Stanza).
`@slow`: end-to-end real (Stanza + roBERTa cargados) — respeta la
advertencia OOM del checkpoint (una sola instancia; no correr junto al
servidor real ni a GRRux interactivo).

Ejecutar:
    python -m pytest test_grrux_server.py
    RUN_SLOW=1 pytest test_grrux_server.py
"""

import os
import shutil
import sys
import tempfile
import threading
import time

from fastapi.testclient import TestClient

import grrux_server

RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv

_CLAVES_SUB = {"tokens", "arbol", "el", "argumentos", "rasgos", "notas",
              "causatividad", "integridad", "periferia", "agx",
              "actor_implicito", "impersonal", "crudo", "operadores", "linking",
              "inventario_enrutado", "ditransitiva"}


def _ls_default():
    return {"ls_type": "activity", "ls_lexical": "do'(Juan,[dar'(Juan)])",
            "ls_formal": "do'(x,[dar'(x)])", "morph_note": "",
            "core": [], "periferia": [], "agx": []}


def _ls_transferencia_confirmada():
    return {**_ls_default(),
            "ditransitiva": {"plantilla": "transferencia",
                              "subtipo_benefactivo": None,
                              "predicado_resultado": None, "proposito": None},
            "ls_lexical": "[do'(Juan, Ø)] CAUSE [BECOME have'(María, regalo)]",
            "ls_formal": "[do'(x, Ø)] CAUSE [BECOME have'(y, z)]",
            "variables": {"x": "Juan", "y": "María", "z": "regalo"},
            "id_a_var": {1: "x", 5: "z", 7: "y"},
            "ls_estructura": [{"predicado": "do'", "args": []},
                              {"predicado": "have'", "args": []}]}


class _MotorStub:
    """Motor falso: no toca Stanza. `cargar()` marca `listo`; `analizar()`
    devuelve un contrato G0.3 mínimo pero con TODAS las claves, MÁS
    `analisis_id` (G2 §1) resoluble vía `obtener_crudo` — mismo contrato que
    el motor real, para poder ejercitar `/corregir/*` sin Stanza.
    `ls_lista_reanalisis` es inyectable: simula lo que "confirmaría" (o no)
    una corrección en el re-análisis de `corregir_el`/`corregir_enrutado`."""
    def __init__(self):
        self.cargado = False
        self.llamadas = []
        self.ls_lista_reanalisis = None
        self._cache = {}
        self._contador = 0

    def cargar(self):
        self.cargado = True

    def estado(self):
        return {"listo": self.cargado}

    def analizar(self, oracion):
        self.llamadas.append(oracion)
        ls_lista = (self.ls_lista_reanalisis if self.ls_lista_reanalisis is not None
                   else [_ls_default()])
        self._contador += 1
        aid = f"stub{self._contador}"
        self._cache[aid] = {"oracion": oracion, "ls_lista": ls_lista}
        sub_oraciones = [{
            "tokens": [{"id": 1, "texto": "Juan", "lema": "Juan"}],
            "arbol": None,
            "el": {"tipo": ls.get("ls_type"), "tipo_legible": "Estado",
                  "formal": ls.get("ls_formal", ""), "lexical": ls.get("ls_lexical", ""),
                  "formal_ops": ls.get("ls_formal", ""), "lexical_ops": ls.get("ls_lexical", "")},
            "operadores": [],
            "ditransitiva": ls.get("ditransitiva"),
            "linking": ls.get("_contrato_linking"),
            "argumentos": [], "rasgos": None, "notas": [],
            "integridad": {"ok": None, "checks": [], "linea": None},
            "periferia": ls.get("periferia", []), "agx": ls.get("agx", []),
            "causatividad": ls.get("_contrato_causatividad"),
            "actor_implicito": None,
            "impersonal": False, "crudo": {"morph_note": "", "resumen_completeness": ""},
            "inventario_enrutado": [],
        } for ls in ls_lista]
        return {"oracion": oracion, "sub_oraciones": sub_oraciones, "error": None,
                "analisis_id": aid}

    def obtener_crudo(self, analisis_id):
        return self._cache.get(analisis_id)


def _cliente(data_dir=None, config_path=None):
    motor = _MotorStub()
    app = grrux_server.crear_app(motor=motor, data_dir=data_dir, config_path=config_path)
    return TestClient(app), motor


def _analizar(c, oracion="Juan le dio un regalo a María"):
    r = c.post("/analizar", json={"oracion": oracion})
    return r.json()["analisis_id"]


# ═══════════════════════════════ rápidos (stub) ════════════════════════════
def test_estado_listo_tras_startup():
    cliente, motor = _cliente()
    with cliente as c:
        r = c.get("/estado")
        assert r.status_code == 200
        assert r.json() == {"listo": True}   # lifespan ya llamó a motor.cargar()


def test_analizar_devuelve_contrato_completo():
    cliente, motor = _cliente()
    with cliente as c:
        r = c.post("/analizar", json={"oracion": "Juan corrió"})
        assert r.status_code == 200
        body = r.json()
        assert body["oracion"] == "Juan corrió" and body["error"] is None
        assert set(body["sub_oraciones"][0].keys()) == _CLAVES_SUB
        assert motor.llamadas == ["Juan corrió"]


def test_analizar_recorta_espacios_antes_de_pasar_al_motor():
    cliente, motor = _cliente()
    with cliente as c:
        c.post("/analizar", json={"oracion": "  Juan corrió  "})
        assert motor.llamadas == ["Juan corrió"]


def test_analizar_oracion_vacia_400_no_llama_al_motor():
    cliente, motor = _cliente()
    with cliente as c:
        r = c.post("/analizar", json={"oracion": "   "})
        assert r.status_code == 400
        assert motor.llamadas == []


def test_glosario_completo():
    cliente, motor = _cliente()
    with cliente as c:
        r = c.get("/glosario")
        assert r.status_code == 200
        entradas = r.json()
        assert isinstance(entradas, list) and len(entradas) > 0
        assert {"categoria", "termino", "definicion"} <= set(entradas[0].keys())


def test_glosario_termino_encontrado_tolerante():
    cliente, motor = _cliente()
    with cliente as c:
        r = c.get("/glosario", params={"termino": "agx"})
        assert r.status_code == 200
        entradas = r.json()
        assert len(entradas) >= 1
        assert any("agx" in e["termino"].lower() for e in entradas)


def test_glosario_termino_no_encontrado_devuelve_lista_vacia():
    cliente, motor = _cliente()
    with cliente as c:
        r = c.get("/glosario", params={"termino": "xyzxyzxyz_no_existe_jamas"})
        assert r.status_code == 200
        assert r.json() == []


def test_analizar_incluye_analisis_id():
    cliente, motor = _cliente()
    with cliente as c:
        r = c.post("/analizar", json={"oracion": "Juan corrió"})
        aid = r.json()["analisis_id"]
        assert isinstance(aid, str) and len(aid) > 0
        assert motor.obtener_crudo(aid) == {"oracion": "Juan corrió",
                                            "ls_lista": [_ls_default()]}


def test_api_preserva_confianza_normalizada_y_linking_causal():
    cliente, motor = _cliente()
    linking = {
        "linea": "Linking: Actor=— · Undergoer=casas · PSA=Undergoer",
        "traza": ["Paso 1 — causativa", "Paso 2 — Undergoer=casas"],
        "macropapeles": {"actor": None, "undergoer": {"texto": "casas"},
                         "nmr": [], "m_transitividad": 1},
        "psa": {"macrorol": "Undergoer"}, "voz": "anticausativa",
    }
    motor.ls_lista_reanalisis = [{
        **_ls_default(),
        "_contrato_causatividad": {
            "tipo": "heuristico_anticausativo_se", "fuente": "heuristic",
            "confianza": None, "nivel_confianza": "baja",
            "clase_base": "active_accomplishment",
            "clase_derivada": "realizacion_causativa",
        },
        "_contrato_linking": linking,
    }]
    with cliente as c:
        respuesta = c.post("/analizar", json={"oracion": "Se venden casas"}).json()
    sub = respuesta["sub_oraciones"][0]
    assert sub["causatividad"]["confianza"] is None
    assert sub["causatividad"]["nivel_confianza"] == "baja"
    assert sub["linking"] == linking


# ═══════════════════════ G2 §2 — endpoints de corrección ═══════════════════
def _tmp_datos():
    tmp = tempfile.mkdtemp()
    real = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "aspect_classifier", "data")
    for f in ("verbos_ditransitivos.xlsx", "causative_lexicon.csv"):
        shutil.copy(os.path.join(real, f), os.path.join(tmp, f))
    return tmp


def test_corregir_analisis_id_desconocido_da_404_claro():
    cliente, motor = _cliente()
    with cliente as c:
        r = c.post("/corregir/clase",
                   json={"analisis_id": "no-existe", "sub_idx": 0, "clase": "activity"})
        assert r.status_code == 404
        assert "expiró" in r.json()["detail"]


def test_corregir_validar_el_los_3_niveles_y_una_valida():
    cliente, motor = _cliente()
    with cliente as c:
        aid = _analizar(c)
        base = {"analisis_id": aid, "sub_idx": 0}

        r1 = c.post("/corregir/validar-el", json={**base, "el": "do'(Juan,[correr'(Juan)]"})
        j1 = r1.json()
        assert j1["ok"] is False and j1["nivel"] == 1 and "abierto" in j1["error"]

        r2 = c.post("/corregir/validar-el", json={**base, "el": "do'(Pedro,[dar'(Pedro,regalo)])"})
        j2 = r2.json()
        assert j2["ok"] is False and j2["nivel"] == 2 and "Pedro" in j2["error"]

        r3 = c.post("/corregir/validar-el", json={**base, "el": "dar'"})
        j3 = r3.json()
        assert j3["ok"] is False and j3["nivel"] == 3

        r4 = c.post("/corregir/validar-el",
                    json={**base, "el": "[do'(Juan,Ø)] CAUSE [BECOME have'(María,regalo)]"})
        j4 = r4.json()
        assert j4["ok"] is True and j4["plantilla"] == "ditrans_transferencia"

        r5 = c.post("/corregir/validar-el", json={**base, "el":
                    "[[do'(Juan,Ø)] CAUSE [BECOME prepared'(regalo)]] "
                    "PURP [BECOME have'(María,regalo)]"})
        j5 = r5.json()
        assert j5["ok"] is True and j5["plantilla"] == "ditrans_benefactiva"
        assert j5["especificacion"] == {
            "familia": "benefactiva", "plantilla": "ditrans_benefactiva",
            "subtipo_benefactivo": "preparacion",
            "predicado_resultado": "prepared'", "aridad_resultado": 1,
            "proposito": "become_have"}
        # puro: nunca persiste ni re-analiza -- el motor solo vio el /analizar inicial
        assert motor.llamadas.count("Juan le dio un regalo a María") == 1


def test_corregir_clase_staging_y_contextual_intacto():
    tmp = _tmp_datos()
    ctx = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "aspect_classifier", "data", "contextual_sentences.csv")
    mtime_antes = os.path.getmtime(ctx)
    cliente, motor = _cliente(data_dir=tmp)
    try:
        with cliente as c:
            aid = _analizar(c)
            r = c.post("/corregir/clase",
                       json={"analisis_id": aid, "sub_idx": 0, "clase": "activity"})
            assert r.status_code == 200
            body = r.json()
            assert body["accion"] == "staging_clase"
            assert body["detalle"]["clase"] == "activity"
            assert body["analisis_nuevo"] is None
        assert os.path.exists(os.path.join(tmp, "correcciones_clase.csv"))
        assert os.path.getmtime(ctx) == mtime_antes
    finally:
        shutil.rmtree(tmp)


def test_corregir_el_confirmada_devuelve_persistido_y_analisis_nuevo():
    tmp = _tmp_datos()
    cliente, motor = _cliente(data_dir=tmp)
    try:
        with cliente as c:
            aid = _analizar(c)
            # el re-análisis (disparado por corregir_el) "confirma": el
            # stub, en la SIGUIENTE llamada a analizar(), devuelve una LS
            # con la ditransitiva ya reconocida.
            motor.ls_lista_reanalisis = [_ls_transferencia_confirmada()]
            r = c.post("/corregir/el", json={
                "analisis_id": aid, "sub_idx": 0,
                "el": "[do'(Juan,Ø)] CAUSE [BECOME have'(María,regalo)]"})
            assert r.status_code == 200
            body = r.json()
            assert body["accion"] == "no-op"
            assert body["detalle"]["plantilla"] == "ditrans_transferencia"
            assert body["analisis_nuevo"] is not None
            assert body["analisis_nuevo"]["analisis_id"] != aid
            assert set(body["analisis_nuevo"]["sub_oraciones"][0].keys()) == _CLAVES_SUB
    finally:
        shutil.rmtree(tmp)


def test_corregir_el_no_confirmada_da_staging_no_confirmado_y_revierte():
    tmp = _tmp_datos()
    import pandas as pd
    n_antes = len(pd.read_excel(os.path.join(tmp, "verbos_ditransitivos.xlsx")))
    cliente, motor = _cliente(data_dir=tmp)
    try:
        with cliente as c:
            aid = _analizar(c)
            # el re-análisis NO confirma: sin ditransitiva en la LS nueva
            motor.ls_lista_reanalisis = [{**_ls_default(), "ditransitiva": None}]
            r = c.post("/corregir/el", json={
                "analisis_id": aid, "sub_idx": 0,
                "el": "[do'(Juan,Ø)] CAUSE [BECOME have'(María,regalo)]"})
            assert r.status_code == 200
            body = r.json()
            assert body["accion"] == "staging_no_confirmado"
            assert body["analisis_nuevo"] is not None   # el diff se muestra IGUAL (§3.5)
        n_despues = len(pd.read_excel(os.path.join(tmp, "verbos_ditransitivos.xlsx")))
        assert n_despues == n_antes   # revert: nada quedó en vivo sin confirmar
    finally:
        shutil.rmtree(tmp)


def test_corregir_enrutado_persistido_a_config():
    tmp = _tmp_datos()
    cfg = os.path.join(tmp, "config.yaml")
    with open(cfg, "w", encoding="utf-8") as f:
        f.write("nucleo_periferia:\n  verbos_movimiento: [ir, venir]\n")
    cliente, motor = _cliente(data_dir=tmp, config_path=cfg)
    try:
        with cliente as c:
            ls = {**_ls_default(), "ls_lexical": "do'(Juan,[trotar'(Juan)])",
                 "core": [], "periferia": [{"id": 3, "text": "cima", "lemma": "cima",
                                            "tipo": "otro"}]}
            motor.ls_lista_reanalisis = [ls]   # (usado en la 1ra llamada /analizar)
            aid = _analizar(c, "Juan trotó hasta la cima")
            # confirmación: el re-análisis ahora trae "cima" en el core
            # ENRUTADO-DATIVO (2026-08-19): la confirmación exige POSICIÓN en
            # la EL (`id_a_var`), no solo presencia en el core.
            motor.ls_lista_reanalisis = [{**ls, "core": [{"id": 3, "text": "cima",
                                                          "macropapel": "Meta"}],
                                         "periferia": [], "id_a_var": {3: "y"}}]
            r = c.post("/corregir/enrutado", json={
                "analisis_id": aid, "sub_idx": 0, "elemento_id": 3,
                "destino": "argumento_core"})
            assert r.status_code == 200
            body = r.json()
            assert body["accion"] == "persistido_enrutado"
            assert body["analisis_nuevo"] is not None
        with open(cfg, encoding="utf-8") as f:
            assert "trotar" in f.read()
    finally:
        shutil.rmtree(tmp)


def test_corregir_enrutado_sin_destino_valido_da_staging():
    tmp = _tmp_datos()
    cliente, motor = _cliente(data_dir=tmp)
    try:
        with cliente as c:
            ls = {**_ls_default(), "core": [{"id": 1, "text": "Juan"}]}
            motor.ls_lista_reanalisis = [ls]
            aid = _analizar(c)
            r = c.post("/corregir/enrutado", json={
                "analisis_id": aid, "sub_idx": 0, "elemento_id": 1,
                "destino": "no-es-un-destino-valido"})
            assert r.status_code == 200
            body = r.json()
            assert body["accion"] == "cancelado"
            assert body["analisis_nuevo"] is None
    finally:
        shutil.rmtree(tmp)


def test_lock_compartido_analizar_y_correccion_no_se_solapan():
    """G2 §4: la corrección nunca se solapa con un análisis en curso --
    ambos endpoints comparten el mismo `threading.Lock` de la app. Se
    instrumenta la ejecución REAL bajo el lock en ambos lados (no solo el
    tiempo de ida y vuelta HTTP, que por diseño se solapa mientras el
    segundo hilo espera el candado) con un contador de secciones activas:
    si el lock protege de verdad, nunca hay más de 1 a la vez."""
    import aspect_classifier.correccion as correccion_mod

    activos = {"n": 0, "max_visto": 0}
    activos_lock = threading.Lock()

    def _entrar():
        with activos_lock:
            activos["n"] += 1
            activos["max_visto"] = max(activos["max_visto"], activos["n"])

    def _salir():
        with activos_lock:
            activos["n"] -= 1

    class _MotorLento(_MotorStub):
        def analizar(self, oracion):
            _entrar()
            try:
                time.sleep(0.1)
                return super().analizar(oracion)
            finally:
                _salir()

    corregir_clase_original = correccion_mod.corregir_clase

    def _corregir_clase_lento(*args, **kwargs):
        _entrar()
        try:
            time.sleep(0.1)
            return corregir_clase_original(*args, **kwargs)
        finally:
            _salir()

    tmp = _tmp_datos()
    motor = _MotorLento()
    app = grrux_server.crear_app(motor=motor, data_dir=tmp)
    cliente = TestClient(app)
    correccion_mod.corregir_clase = _corregir_clase_lento
    try:
        with cliente as c:
            aid = _analizar(c)

            def hacer_correccion():
                c.post("/corregir/clase",
                      json={"analisis_id": aid, "sub_idx": 0, "clase": "activity"})

            def hacer_analizar():
                c.post("/analizar", json={"oracion": "Otra oración distinta"})

            t_a = threading.Thread(target=hacer_analizar)
            t_c = threading.Thread(target=hacer_correccion)
            t_a.start()
            time.sleep(0.02)   # deja que "analizar" tome el lock primero
            t_c.start()
            t_a.join()
            t_c.join()
    finally:
        correccion_mod.corregir_clase = corregir_clase_original
        shutil.rmtree(tmp)

    assert activos["max_visto"] == 1, "el lock no impidió que ambos corrieran a la vez"


# ═══════════════════════ G3 §2 — POST /corregir/todo ═══════════════════════
def test_corregir_todo_persiste_el_y_stagea_clase_un_solo_reanalisis():
    tmp = _tmp_datos()
    cliente, motor = _cliente(data_dir=tmp)
    try:
        with cliente as c:
            aid = _analizar(c)
            motor.ls_lista_reanalisis = [_ls_transferencia_confirmada()]
            r = c.post("/corregir/todo", json={
                "analisis_id": aid, "sub_idx": 0,
                "el": "[do'(Juan,Ø)] CAUSE [BECOME have'(María,regalo)]",
                "clase": "accomplishment"})
            assert r.status_code == 200
            body = r.json()
            assert body["accion"] == "staging_clase+no-op"
            assert body["detalle"]["clase_resultado"]["accion"] == "staging_clase"
            assert body["detalle"]["el_resultado"]["accion"] == "no-op"
            assert body["analisis_nuevo"] is not None
            # el ÚNICO re-análisis que dispara /corregir/todo es el de la EL
            # (persistir_ditransitiva -> _confirmar_persistencia): 1 llamada
            # del /analizar inicial + 1 de la confirmación = 2 en total.
            assert motor.llamadas.count("Juan le dio un regalo a María") == 2
        assert os.path.exists(os.path.join(tmp, "correcciones_clase.csv"))
    finally:
        shutil.rmtree(tmp)


def test_corregir_todo_el_rechazada_clase_igual_stagea_sin_reanalisis():
    tmp = _tmp_datos()
    cliente, motor = _cliente(data_dir=tmp)
    try:
        with cliente as c:
            aid = _analizar(c)
            llamadas_antes = len(motor.llamadas)
            r = c.post("/corregir/todo", json={
                "analisis_id": aid, "sub_idx": 0, "el": "dar'(", "clase": "state"})
            assert r.status_code == 200
            body = r.json()
            assert body["accion"] == "staging_clase+rechazado"
            assert body["analisis_nuevo"] is None
            assert len(motor.llamadas) == llamadas_antes   # EL inválida -> cero re-análisis
        assert os.path.exists(os.path.join(tmp, "correcciones_clase.csv"))
    finally:
        shutil.rmtree(tmp)


# ═══════════════════════ G3 §4 — exportaciones ═════════════════════════════
def test_exportar_txt_expirado_da_404():
    cliente, motor = _cliente()
    with cliente as c:
        r = c.get("/exportar/txt", params={"analisis_id": "no-existe"})
        assert r.status_code == 404


def test_exportar_conllu_expirado_da_404():
    cliente, motor = _cliente()
    with cliente as c:
        r = c.get("/exportar/conllu", params={"analisis_id": "no-existe"})
        assert r.status_code == 404


def test_exportar_conllu_devuelve_texto_cacheado_o_vacio_sin_lanzar():
    cliente, motor = _cliente()
    with cliente as c:
        aid = _analizar(c)
        # el stub no cachea "conllu_texto" -- ausente = "" (nunca 500)
        r = c.get("/exportar/conllu", params={"analisis_id": aid})
        assert r.status_code == 200
        assert r.text == ""


def test_exportar_txt_mismo_formato_grr_que_render_bloque():
    cliente, motor = _cliente()
    with cliente as c:
        aid = _analizar(c)
        r = c.get("/exportar/txt", params={"analisis_id": aid})
        assert r.status_code == 200
        # el stub no cachea arboles/tokens_por_sub -> cae a "sin árbol" (nunca
        # lanza) pero conserva la EL léxica, igual que la terminal.
        assert "sin árbol" in r.text
        assert _ls_default()["ls_lexical"] in r.text


# ═══════════════════════ G3 §5 — GET /curador/staging ══════════════════════
def test_curador_staging_contadores_sobre_fixture():
    tmp = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmp, "correcciones_clase.csv"), "w", encoding="utf-8", newline="") as f:
            f.write("fecha,oracion,lema,clase_predicha,clase_correcta,vector,fuente\n")
            f.write("2026-01-01 00:00:00,x,dar,activity,accomplishment,,correccion_usuario\n")
        with open(os.path.join(tmp, "correcciones_log.csv"), "w", encoding="utf-8", newline="") as f:
            f.write("fecha,oracion,lema,tipo,accion,destino,detalle,fuente\n")
            f.write("2026-01-01 00:00:00,x,dar,clase,staging,correcciones_clase.csv,"
                   "activity->accomplishment,correccion_usuario\n")
            f.write("2026-01-01 00:00:01,y,correr,EL,persistido,verbos_ditransitivos.xlsx,"
                   "transferencia,correccion_usuario\n")
        # correcciones_el.csv / correcciones_enrutado.csv AUSENTES a propósito:
        # deben dar 0 filas, nunca un error.
        cliente, motor = _cliente(data_dir=tmp)
        with cliente as c:
            r = c.get("/curador/staging")
            assert r.status_code == 200
            j = r.json()
            assert j["correcciones_clase"]["total"] == 1
            assert j["correcciones_el"] == {"filas": [], "total": 0}
            assert j["correcciones_enrutado"] == {"filas": [], "total": 0}
            assert j["log_maestro"]["total"] == 2
            assert j["log_maestro"]["por_accion"] == {"staging": 1, "persistido": 1}
    finally:
        shutil.rmtree(tmp)


# ═══════════════════════ G3 §3 — capacidad de la que depende el lote ═══════
def test_lote_n_oraciones_con_una_erronea_via_analizar_secuencial():
    """El modo lote de la GUI es JS puro: llama a /analizar N veces
    SECUENCIALMENTE (sin endpoint propio; el lock del servidor ya impone el
    orden). Esta prueba confirma la capacidad servidor de la que depende:
    una oración que dispara error() no tumba el resto del lote."""
    cliente, motor = _cliente()
    with cliente as c:
        original = motor.analizar

        def analizar_con_fallo(oracion):
            if oracion == "ERROR_FORZADO":
                motor.llamadas.append(oracion)
                return {"oracion": oracion, "sub_oraciones": [], "error": "fallo simulado",
                       "analisis_id": None}
            return original(oracion)
        motor.analizar = analizar_con_fallo

        oraciones = ["Juan corrió", "ERROR_FORZADO", "María cantó"]
        resultados = [c.post("/analizar", json={"oracion": o}).json() for o in oraciones]

        assert resultados[0]["error"] is None and resultados[0]["analisis_id"]
        assert resultados[1]["error"] == "fallo simulado" and resultados[1]["analisis_id"] is None
        assert resultados[2]["error"] is None and resultados[2]["analisis_id"]


_PUROS = [
    test_estado_listo_tras_startup,
    test_analizar_devuelve_contrato_completo,
    test_analizar_recorta_espacios_antes_de_pasar_al_motor,
    test_analizar_oracion_vacia_400_no_llama_al_motor,
    test_glosario_completo,
    test_glosario_termino_encontrado_tolerante,
    test_glosario_termino_no_encontrado_devuelve_lista_vacia,
    test_analizar_incluye_analisis_id,
    test_corregir_analisis_id_desconocido_da_404_claro,
    test_corregir_validar_el_los_3_niveles_y_una_valida,
    test_corregir_clase_staging_y_contextual_intacto,
    test_corregir_el_confirmada_devuelve_persistido_y_analisis_nuevo,
    test_corregir_el_no_confirmada_da_staging_no_confirmado_y_revierte,
    test_corregir_enrutado_persistido_a_config,
    test_corregir_enrutado_sin_destino_valido_da_staging,
    test_lock_compartido_analizar_y_correccion_no_se_solapan,
    test_corregir_todo_persiste_el_y_stagea_clase_un_solo_reanalisis,
    test_corregir_todo_el_rechazada_clase_igual_stagea_sin_reanalisis,
    test_exportar_txt_expirado_da_404,
    test_exportar_conllu_expirado_da_404,
    test_exportar_conllu_devuelve_texto_cacheado_o_vacio_sin_lanzar,
    test_exportar_txt_mismo_formato_grr_que_render_bloque,
    test_curador_staging_contadores_sobre_fixture,
    test_lote_n_oraciones_con_una_erronea_via_analizar_secuencial,
]


# ═══════════════════════ @slow — end-to-end real ═══════════════════════════
def test_slow_analizar_real_ditransitiva_agx():
    """Motor REAL (Stanza + roBERTa cargados): AGX en el árbol, ditransitiva
    benefactiva/transferencia, integridad ok, enlaces var<->token_id
    coherentes con `tokens`."""
    cliente = TestClient(grrux_server.app)
    with cliente as c:
        r = c.post("/analizar", json={"oracion": "Juan le dio flores a María"})
        assert r.status_code == 200
        body = r.json()
        assert body["error"] is None
        sub = body["sub_oraciones"][0]
        assert sub["integridad"]["ok"] is True

        def _tiene_agx(nodo):
            if not isinstance(nodo, dict) or "label" not in nodo:
                return False
            if nodo["label"] == "AGX":
                return True
            return any(_tiene_agx(h) for h in nodo.get("hijos", []))
        assert _tiene_agx(sub["arbol"])

        ids_tokens = {t["id"] for t in sub["tokens"]}
        for a in sub["argumentos"]:
            if a["token_id"] is not None:
                assert a["token_id"] in ids_tokens
        assert any(a["papel"] in ("Poseedor", "Efectuador", "Tema")
                  for a in sub["argumentos"])


def test_slow_corregir_el_real_con_reanalisis():
    """G2 §4: UNA corrección de EL real (Stanza + roBERTa cargados) con
    re-análisis -- motor REAL (`grrux_motor`, no un stub) pero `data_dir`
    TEMPORAL (nunca toca los léxicos de producción). "Juan le dio flores a
    María" ya es ditransitiva de transferencia en el léxico semilla: la EL
    corregida coincide con lo que el motor ya produce, así que el
    re-análisis debe CONFIRMAR (persistido) y traer un `analisis_nuevo`
    completo con su propio id."""
    import grrux_motor
    tmp = _tmp_datos()
    app = grrux_server.crear_app(motor=grrux_motor, data_dir=tmp)
    cliente = TestClient(app)
    try:
        with cliente as c:
            r0 = c.post("/analizar", json={"oracion": "Juan le dio flores a María"})
            assert r0.status_code == 200
            aid = r0.json()["analisis_id"]
            assert aid

            el_correcta = "[do'(Juan,Ø)] CAUSE [BECOME have'(María,flores)]"
            rv = c.post("/corregir/validar-el",
                       json={"analisis_id": aid, "sub_idx": 0, "el": el_correcta})
            assert rv.status_code == 200 and rv.json()["ok"] is True

            r1 = c.post("/corregir/el",
                       json={"analisis_id": aid, "sub_idx": 0, "el": el_correcta})
            assert r1.status_code == 200
            body = r1.json()
            assert body["accion"] in ("insert", "update", "no-op", "staging_no_confirmado")
            assert body["analisis_nuevo"] is not None
            assert body["analisis_nuevo"]["analisis_id"] != aid
            assert set(body["analisis_nuevo"]["sub_oraciones"][0].keys()) == _CLAVES_SUB
    finally:
        shutil.rmtree(tmp)


def test_slow_lote_real_pequeno_y_exportacion_txt():
    """G3 §7 (@slow): un lote real de 3 oraciones end-to-end (motor REAL,
    Stanza + roBERTa cargados; el modo lote de la GUI es JS puro que llama a
    /analizar N veces secuencialmente) + una exportación .txt real cuyo
    orden GRR (árbol -> EL léxica -> resto) calca el de la terminal (mismo
    `display_grr.render_bloque`, ver `grrux_motor.render_txt_grr`) + un
    .conllu real con los metadatos rrg_* anotados."""
    cliente = TestClient(grrux_server.app)
    with cliente as c:
        oraciones = ["Juan corrió por el parque.", "María cantó una canción.",
                    "Juan le dio flores a María."]
        ids = []
        for o in oraciones:
            r = c.post("/analizar", json={"oracion": o})
            assert r.status_code == 200
            body = r.json()
            assert body["error"] is None
            ids.append(body["analisis_id"])
        assert all(ids)

        r_txt = c.get("/exportar/txt", params={"analisis_id": ids[0]})
        assert r_txt.status_code == 200
        texto = r_txt.text
        i_arbol = texto.index("ÁRBOL SINTÁCTICO RRG")
        i_lex = texto.index("EL léxica")
        i_tipo = texto.index("Tipo")
        assert i_arbol < i_lex < i_tipo   # mismo orden GRR que la terminal

        r_conllu = c.get("/exportar/conllu", params={"analisis_id": ids[0]})
        assert r_conllu.status_code == 200
        assert "# rrg_ls_type =" in r_conllu.text


if not RUN_SLOW:
    try:
        import pytest
        test_slow_analizar_real_ditransitiva_agx = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_analizar_real_ditransitiva_agx)
        test_slow_corregir_el_real_con_reanalisis = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_corregir_el_real_con_reanalisis)
        test_slow_lote_real_pequeno_y_exportacion_txt = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_lote_real_pequeno_y_exportacion_txt)
    except ImportError:
        pass


def main():
    tests = _PUROS + ([test_slow_analizar_real_ditransitiva_agx,
                      test_slow_corregir_el_real_con_reanalisis,
                      test_slow_lote_real_pequeno_y_exportacion_txt] if RUN_SLOW else [])
    fallos = 0
    for t in tests:
        try:
            t()
            print(f"  [OK]   {t.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"  [FAIL] {t.__name__}: {e}")
        except Exception as e:
            fallos += 1
            print(f"  [ERR]  {t.__name__}: {type(e).__name__}: {e}")
    if fallos:
        sys.exit(1)
    print(f"\n{len(tests)} tests pasaron.")


if __name__ == "__main__":
    main()
