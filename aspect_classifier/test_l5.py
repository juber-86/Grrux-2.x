"""Tests de la Fase L5 — §3 (traducción), §4 (glosario), §5 (bucle de
corrección). Puros salvo el manejo de archivos temporales.

Ejecutar:
    python -m aspect_classifier.test_l5
    RUN_SLOW=1 pytest aspect_classifier/test_l5.py
"""

import csv
import os
import shutil
import sys
import tempfile

from . import correccion as c
from . import display_grr as d
from . import glosario as g

RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv

_DATA_REAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


# ═══════════════════════ §3 — traducción user-friendly ════════════════════
def test_linea_rasgos_traduce_vector():
    ls = {"vector": {"stat": 0.02, "dyn": 0.75, "tel": 0.40, "pun": 0.05},
          "confianza": 0.84}
    assert d.linea_rasgos(ls) == ("Rasgos: estático 0.02 · dinámico 0.75 · "
                                  "télico 0.40 · puntual 0.05 · confianza 0.84")


def test_linea_rasgos_none_sin_vector():
    assert d.linea_rasgos({"ls_type": "state"}) is None


def test_traducir_apendices_gate_y_ditrans():
    note = "stat=0.1 gate=obj_medida→AA ditrans=transferencia(léxico)"
    fr = d.traducir_apendices(note)
    assert "corrección: objeto de medida (numeral) → Realización activa" in fr
    assert "construcción: transferencia (léxico)" in fr


def test_integridad_ok_y_alerta():
    comp_ok = {"ok": True, "checks": [
        {"tipo": "argumento", "elemento": "x", "estado": "ok", "detalle": "x(morf)"},
        {"tipo": "agx", "elemento": "AGX", "estado": "ok", "detalle": "AGX✓"}]}
    li = d.linea_integridad(comp_ok)
    assert li.startswith("Integridad: ✓")
    assert "x en la terminación verbal" in li and "concordancia (AGX) ✓" in li

    comp_warn = {"ok": False, "checks": [
        {"tipo": "argumento", "elemento": "y", "estado": "falta_en_arbol",
         "detalle": 'y ("participar") sin constituyente en el árbol'}]}
    lw = d.linea_integridad(comp_warn)
    assert lw.count("⚠") == 1   # un solo símbolo, no duplicado
    assert 'y ("participar") NO aparece como constituyente en el árbol' in lw


def test_render_bloque_orden_grr():
    """Árbol PRIMERO, EL léxica INMEDIATAMENTE DEBAJO, luego el resto."""
    ls = {"ls_type": "activity", "ls_formal": "do'(x,[correr'(x)])",
          "ls_lexical": "do'(Juan,[correr'(Juan)])"}
    out = d.render_bloque(ls, "[arbol]", None, verbose=False)
    i_arbol = out.index("ÁRBOL SINTÁCTICO RRG")
    i_lex = out.index("EL léxica")
    i_tipo = out.index("Tipo")
    assert i_arbol < i_lex < i_tipo


# ═══════════════════════ §4 — glosario / -help ════════════════════════════
def test_glosario_busqueda_tolerante():
    gl = g.cargar_glosario()
    assert [e["termino"] for e in g.buscar("agx", gl)] == ["AGX"]
    assert g.buscar("telico", gl)[0]["termino"] == "télico (tel)"
    assert len(g.buscar("peri", gl)) >= 2   # -PERI, PERI@CORE...


def test_glosario_no_encontrado():
    r = g.respuesta_help("zzz", g.cargar_glosario())
    assert "no encontrado" in r and '"-help"' in r


def test_es_comando_help_formas():
    assert g.es_comando_help("-help") == (True, None)
    assert g.es_comando_help("--ayuda telico") == (True, "telico")
    assert g.es_comando_help("hola") == (False, None)


# ═══════════════════════ §5 — validación de la EL (3 niveles) ═════════════
_TOKS = "Juan le dio un regalo a María".split()


def test_el_valida_transferencia():
    v = c.validar_el("[do'(Juan,Ø)] CAUSE [BECOME have'(María,regalo)]", _TOKS, "dar")
    assert v["ok"] and v["plantilla"] == "ditrans_transferencia"


def test_el_benefactiva_reconoce_subtipo_resultativo_y_wrappers():
    el = ("⟨IF DEC ⟨TNS PRES ⟨every'(mañanas, [[[do'(Juan, Ø)] CAUSE "
          "[BECOME prepared'(pizzas)]] PURP [BECOME have'(María, pizzas)]])⟩⟩⟩")
    v = c.validar_el(el, "Juan prepara pizzas a María todas las mañanas".split(), "preparar")
    assert v["ok"] and v["plantilla"] == "ditrans_benefactiva"
    assert v["especificacion"]["subtipo_benefactivo"] == "preparacion"
    assert v["especificacion"]["predicado_resultado"] == "prepared'"
    assert v["especificacion"]["proposito"] == "become_have"


def test_el_benefactiva_rechaza_aridad_o_coindexacion_incompatible():
    malas = [
        "[[do'(Juan,Ø)] CAUSE [BECOME prepared'(pizzas,María)]] PURP [BECOME have'(María,pizzas)]",
        "[[do'(Juan,Ø)] CAUSE [BECOME prepared'(pizzas)]] PURP [BECOME have'(María,regalo)]",
    ]
    for el in malas:
        v = c.validar_el(el, _TOKS + ["pizzas"], "preparar")
        assert not v["ok"] and v["nivel"] == 3


def test_el_benefactiva_actividad_exige_predicado_del_lema():
    el = "do'(Juan,[buscar'(Juan,regalo)]) PURP [BECOME have'(María,regalo)]"
    v = c.validar_el(el, _TOKS, "amasar")
    assert not v["ok"] and v["nivel"] == 3 and "amasar" in v["error"]


def test_el_rechazo_nivel1_parentesis():
    v = c.validar_el("do'(Juan,[correr'(Juan)]", _TOKS, "dar")
    assert not v["ok"] and v["nivel"] == 1


def test_el_rechazo_nivel2_argumento_ajeno():
    v = c.validar_el("do'(Pedro,[dar'(Pedro,regalo)])", _TOKS, "dar")
    assert not v["ok"] and v["nivel"] == 2 and "Pedro" in v["error"]


def test_el_rechaza_notacion_anterior_xn():
    for variable in ("x1", "x2", "x3", "x9"):
        v = c.validar_el(f"do'({variable},[dar'({variable},regalo)])", _TOKS, "dar")
        assert not v["ok"] and v["nivel"] == 2
        assert "notación anterior" in v["error"] and "regenerarse" in v["error"]


def test_el_rechazo_nivel3_plantilla_desconocida():
    # 'correr'' primado, lema presente, pero sin estructura de plantilla.
    v = c.validar_el("dar'", _TOKS, "dar")
    assert not v["ok"] and v["nivel"] == 3


# ═══════════════════════ §5 — orquestador (input inyectado) ═══════════════
class _Entrada:
    """input() falso: devuelve respuestas encoladas; EOFError si se agotan."""
    def __init__(self, respuestas):
        self.r = list(respuestas)

    def __call__(self, _prompt=""):
        if not self.r:
            raise EOFError
        return self.r.pop(0)


def _tmp_data():
    """Copia los léxicos vivos a un dir temporal para no tocar los reales."""
    tmp = tempfile.mkdtemp()
    for f in ("verbos_ditransitivos.xlsx", "causative_lexicon.csv"):
        shutil.copy(os.path.join(_DATA_REAL, f), os.path.join(tmp, f))
    return tmp


def _res(ls_lexical="do'(Juan,[dar'(Juan)])", ls_type="activity", oracion="Juan le dio un regalo a María"):
    return {"oracion": oracion, "ls_lista": [{
        "ls_type": ls_type, "ls_lexical": ls_lexical, "ls_formal": "",
        "morph_note": "stat=0.1", "core": [], "periferia": [], "agx": []}]}


def _ls_transferencia_confirmada():
    return {"ditransitiva": {"plantilla": "transferencia",
                              "subtipo_benefactivo": None,
                              "predicado_resultado": None, "proposito": None},
            "ls_lexical": "[do'(Juan, Ø)] CAUSE [BECOME have'(María, regalo)]",
            "ls_formal": "[do'(x, Ø)] CAUSE [BECOME have'(y, z)]",
            "variables": {"x": "Juan", "y": "María", "z": "regalo"},
            "id_a_var": {1: "x", 5: "z", 7: "y"},
            "ls_estructura": [{"predicado": "do'", "args": []},
                              {"predicado": "have'", "args": []}],
            "core": [], "periferia": [], "agx": []}


def test_correccion_clase_va_a_staging_sin_tocar_contextual():
    tmp = _tmp_data()
    salida = []
    ctx = os.path.join(_DATA_REAL, "contextual_sentences.csv")
    mtime_antes = os.path.getmtime(ctx)
    ent = _Entrada(["1", "2"])   # menú→clase, clase→Actividad(2)
    r = c.bucle_correccion(_res(), lambda o: _res(), sub_idx=0, entrada=ent,
                           salida=salida.append, data_dir=tmp)
    assert r["accion"] == "staging_clase"
    assert os.path.exists(os.path.join(tmp, "correcciones_clase.csv"))
    assert os.path.getmtime(ctx) == mtime_antes   # contextual JAMÁS tocado
    # log maestro escrito
    assert os.path.exists(os.path.join(tmp, "correcciones_log.csv"))
    shutil.rmtree(tmp)


def test_correccion_el_ditransitiva_persiste_con_confirmacion():
    tmp = _tmp_data()
    # el re-análisis confirma: devuelve un res cuya ditransitiva coincide
    def reanalizar(_o):
        return {"oracion": "x", "ls_lista": [_ls_transferencia_confirmada()]}
    ent = _Entrada(["2", "[do'(Juan,Ø)] CAUSE [BECOME have'(María,regalo)]"])
    r = c.bucle_correccion(_res(), reanalizar, sub_idx=0, entrada=ent,
                           salida=lambda *_: None, data_dir=tmp)
    assert r["accion"] == "no-op" and r["plantilla"] == "ditrans_transferencia"
    # La corrección idéntica no duplica ni reescribe la fila existente.
    import pandas as pd
    df = pd.read_excel(os.path.join(tmp, "verbos_ditransitivos.xlsx"))
    assert len(df[df["lema"] == "dar"]) == 1
    shutil.rmtree(tmp)


def test_correccion_el_no_confirmada_cae_a_staging_y_revierte():
    tmp = _tmp_data()
    import pandas as pd
    n_antes = len(pd.read_excel(os.path.join(tmp, "verbos_ditransitivos.xlsx")))
    # re-análisis NO confirma (ditransitiva None)
    def reanalizar(_o):
        return {"oracion": "x", "ls_lista": [{"ditransitiva": None, "ls_lexical": "",
                                              "core": [], "periferia": [], "agx": []}]}
    ent = _Entrada(["2", "[do'(Juan,Ø)] CAUSE [BECOME have'(María,regalo)]"])
    r = c.bucle_correccion(_res(), reanalizar, sub_idx=0, entrada=ent,
                           salida=lambda *_: None, data_dir=tmp)
    assert r["accion"] == "staging_no_confirmado"
    # revert: el xlsx vuelve a su tamaño original (nada en vivo sin confirmar)
    n_despues = len(pd.read_excel(os.path.join(tmp, "verbos_ditransitivos.xlsx")))
    assert n_despues == n_antes
    assert os.path.exists(os.path.join(tmp, "correcciones_el.csv"))
    shutil.rmtree(tmp)


def test_correccion_enrutado_a_lista_config():
    tmp = _tmp_data()
    cfg = os.path.join(tmp, "config.yaml")
    with open(cfg, "w", encoding="utf-8") as f:
        f.write("nucleo_periferia:\n  verbos_movimiento: [ir, venir]\n")
    ls = {"ls_type": "activity", "ls_lexical": "do'(Juan,[trotar'(Juan)])",
          "core": [], "periferia": [{"id": 3, "text": "cima", "lemma": "cima", "tipo": "otro"}],
          "agx": []}
    res = {"oracion": "Juan trotó hasta la cima", "ls_lista": [ls]}

    def reanalizar(_o):
        nuevo = dict(ls)
        # ENRUTADO-DATIVO (2026-08-19): la confirmación exige que el elemento
        # ocupe de verdad una POSICIÓN en la EL (`id_a_var`), no solo que
        # aparezca en el core — un re-análisis real de "trotó hasta la cima"
        # le asigna variable, y era justo lo que faltaba en el falso positivo
        # que acabó metiendo `dar` en verbos_movimiento.
        nuevo["core"] = [{"id": 3, "text": "cima", "macropapel": "Meta"}]
        nuevo["periferia"] = []
        nuevo["id_a_var"] = {3: "y"}
        return {"oracion": res["oracion"], "ls_lista": [nuevo]}

    # menú→enrutado(3), elemento 'cima'(1), destino argumento_core(1)
    ent = _Entrada(["3", "1", "1"])
    r = c.bucle_correccion(res, reanalizar, sub_idx=0, entrada=ent,
                           salida=lambda *_: None, data_dir=tmp, config_path=cfg)
    assert r["accion"] == "persistido_enrutado"
    with open(cfg, encoding="utf-8") as f:
        contenido = f.read()
    assert "trotar" in contenido and "correccion_usuario" in contenido
    shutil.rmtree(tmp)


# ═══════════════════ G0.4 — API de corrección no-interactiva (GUI) ════════
def test_g0_corregir_clase_staging_sin_menu():
    tmp = _tmp_data()
    ctx = os.path.join(_DATA_REAL, "contextual_sentences.csv")
    mtime_antes = os.path.getmtime(ctx)
    r = c.corregir_clase(_res(), 0, "activity", data_dir=tmp)
    assert r == {"accion": "staging_clase", "clase": "activity"}
    assert os.path.exists(os.path.join(tmp, "correcciones_clase.csv"))
    assert os.path.getmtime(ctx) == mtime_antes
    shutil.rmtree(tmp)


def test_g0_corregir_el_persiste_con_confirmacion():
    tmp = _tmp_data()

    def reanalizar(_o):
        return {"oracion": "x", "ls_lista": [_ls_transferencia_confirmada()]}
    r = c.corregir_el(_res(), 0, "[do'(Juan,Ø)] CAUSE [BECOME have'(María,regalo)]",
                      reanalizar, data_dir=tmp)
    assert r["accion"] == "no-op" and r["plantilla"] == "ditrans_transferencia"
    shutil.rmtree(tmp)


def test_g0_corregir_el_rechazada_nivel1():
    r = c.corregir_el(_res(), 0, "dar'(", lambda o: _res())
    assert r["accion"] == "rechazado" and r["nivel"] == 1


def test_g0_corregir_el_no_confirmada_cae_a_staging():
    tmp = _tmp_data()

    def reanalizar(_o):
        return {"oracion": "x", "ls_lista": [{"ditransitiva": None, "ls_lexical": "",
                                              "core": [], "periferia": [], "agx": []}]}
    r = c.corregir_el(_res(), 0, "[do'(Juan,Ø)] CAUSE [BECOME have'(María,regalo)]",
                      reanalizar, data_dir=tmp)
    assert r["accion"] == "staging_no_confirmado"
    shutil.rmtree(tmp)


def test_g0_corregir_enrutado_por_id_sin_menu():
    tmp = _tmp_data()
    cfg = os.path.join(tmp, "config.yaml")
    with open(cfg, "w", encoding="utf-8") as f:
        f.write("nucleo_periferia:\n  verbos_movimiento: [ir, venir]\n")
    ls = {"ls_type": "activity", "ls_lexical": "do'(Juan,[trotar'(Juan)])",
          "core": [], "periferia": [{"id": 3, "text": "cima", "lemma": "cima", "tipo": "otro"}],
          "agx": []}
    res = {"oracion": "Juan trotó hasta la cima", "ls_lista": [ls]}

    def reanalizar(_o):
        nuevo = dict(ls)
        # ENRUTADO-DATIVO (2026-08-19): la confirmación exige que el elemento
        # ocupe de verdad una POSICIÓN en la EL (`id_a_var`), no solo que
        # aparezca en el core — un re-análisis real de "trotó hasta la cima"
        # le asigna variable, y era justo lo que faltaba en el falso positivo
        # que acabó metiendo `dar` en verbos_movimiento.
        nuevo["core"] = [{"id": 3, "text": "cima", "macropapel": "Meta"}]
        nuevo["periferia"] = []
        nuevo["id_a_var"] = {3: "y"}
        return {"oracion": res["oracion"], "ls_lista": [nuevo]}

    r = c.corregir_enrutado(res, 0, elemento_id=3, destino="argumento_core",
                            reanalizar_fn=reanalizar, data_dir=tmp, config_path=cfg)
    assert r["accion"] == "persistido_enrutado"
    with open(cfg, encoding="utf-8") as f:
        contenido = f.read()
    assert "trotar" in contenido and "correccion_usuario" in contenido
    shutil.rmtree(tmp)


def test_enrutado_recipiente_dativo_no_contamina_verbos_movimiento():
    """ENRUTADO-DATIVO (2026-08-19) — regresión del bug del 2026-07-14.

    Corregir "maría → argumento del core" en una ditransitiva metía el verbo
    en `verbos_movimiento` (la única automatización que tenía el destino
    "argumento del core"), y desde entonces todo oblicuo en a/hacia/hasta
    bajo ese verbo ascendía al core como Meta. El clítico dativo doblado es
    la señal inequívoca de que es un RECIPIENTE, no una meta de movimiento.
    """
    tmp = _tmp_data()
    cfg = os.path.join(tmp, "config.yaml")
    with open(cfg, "w", encoding="utf-8") as f:
        f.write("nucleo_periferia:\n  verbos_movimiento: [ir, venir]\n")
    ls = {"ls_type": "semelfactive", "ls_lexical": "SEML dar'(juan, beso)",
          "verb_lemma": "dar",
          "core": [{"id": 1, "text": "juan", "macropapel": "Actor"},
                   {"id": 5, "text": "beso", "macropapel": "Undergoer"}],
          "periferia": [{"id": 7, "text": "maria", "lemma": "maria", "tipo": "generico"}],
          "agx": [{"clitico": "le", "rasgos": "3sg-dat", "fuente": "dativo",
                   "doblado": True, "arg_id": 7, "clitico_id": 2}]}
    res = {"oracion": "juan le da un beso a maria", "ls_lista": [ls]}

    def reanalizar(_o):   # no debería llegar a llamarse
        raise AssertionError("no debe re-analizar: la ruta no es verbos_movimiento")

    r = c.corregir_enrutado(res, 0, elemento_id=7, destino="argumento_core",
                            reanalizar_fn=reanalizar, data_dir=tmp, config_path=cfg,
                            verb_lemma="dar")
    assert r["accion"] == "staging_enrutado"
    with open(cfg, encoding="utf-8") as f:
        contenido = f.read()
    assert "dar" not in contenido and "correccion_usuario" not in contenido
    shutil.rmtree(tmp)


def test_enrutado_sin_posicion_en_la_el_no_se_confirma():
    """Estar en el core no basta: si el re-análisis no le da variable en la
    EL, la corrección no se persiste (y se revierte lo ya escrito)."""
    tmp = _tmp_data()
    cfg = os.path.join(tmp, "config.yaml")
    with open(cfg, "w", encoding="utf-8") as f:
        f.write("nucleo_periferia:\n  verbos_movimiento: [ir, venir]\n")
    ls = {"ls_type": "activity", "ls_lexical": "do'(Juan,[trotar'(Juan)])",
          "core": [], "periferia": [{"id": 3, "text": "cima", "lemma": "cima",
                                     "tipo": "otro"}],
          "agx": []}
    res = {"oracion": "Juan trotó hasta la cima", "ls_lista": [ls]}

    def reanalizar(_o):
        nuevo = dict(ls)
        # entra al core pero SIN posición en la EL: el caso exacto de
        # "argumento sin posición licenciada"
        nuevo["core"] = [{"id": 3, "text": "cima", "macropapel": "Meta"}]
        nuevo["periferia"] = []
        nuevo["id_a_var"] = {}
        return {"oracion": res["oracion"], "ls_lista": [nuevo]}

    r = c.corregir_enrutado(res, 0, elemento_id=3, destino="argumento_core",
                            reanalizar_fn=reanalizar, data_dir=tmp, config_path=cfg)
    assert r["accion"] == "staging_no_confirmado_enrutado"
    with open(cfg, encoding="utf-8") as f:
        assert "trotar" not in f.read()      # revertido
    shutil.rmtree(tmp)


def test_g0_corregir_enrutado_elemento_inexistente():
    r = c.corregir_enrutado(_res(), 0, elemento_id=999, destino="agx",
                            reanalizar_fn=lambda o: _res())
    assert r["accion"] == "cancelado" and "error" in r


def test_g0_corregir_enrutado_destino_desconocido():
    ls = {"ls_type": "activity", "ls_lexical": "", "core": [{"id": 1, "text": "x"}],
          "periferia": [], "agx": []}
    res = {"oracion": "x", "ls_lista": [ls]}
    r = c.corregir_enrutado(res, 0, elemento_id=1, destino="no_existe",
                            reanalizar_fn=lambda o: res)
    assert r["accion"] == "cancelado" and "error" in r


def test_g0_flujo_clase_interactivo_sigue_igual_via_menu():
    """Regresión: el menú interactivo, tras el refactor G0.4, produce
    exactamente la misma acción que antes (llama a la lógica compartida)."""
    tmp = _tmp_data()
    ent = _Entrada(["1", "2"])
    r = c.bucle_correccion(_res(), lambda o: _res(), sub_idx=0, entrada=ent,
                           salida=lambda *_: None, data_dir=tmp)
    assert r["accion"] == "staging_clase" and r["clase"] == "activity"
    shutil.rmtree(tmp)


# ═══════════════════ G3 §1 — lema robusto (los 3 casos del prompt) ════════
# LS "de origen" que reproduce el bug del checkpoint G2: la EL léxica solo
# expone do'/have' (ambos en _PRED_NO_LEMA), sin el verbo real primado en
# ningún lado -> `_lema_de` cae a `ls_type` ("accomplishment", un nombre de
# CLASE, no un verbo).
def _res_sin_verbo_primado():
    return {"oracion": "Juan le dio un regalo a María", "ls_lista": [{
        "ls_type": "accomplishment", "ls_lexical": "do'(Juan,[have'(María,regalo)])",
        "ls_formal": "", "morph_note": "", "core": [], "periferia": [], "agx": []}]}


def _reanalisis_confirma_transferencia(_o):
    return {"oracion": "x", "ls_lista": [_ls_transferencia_confirmada()]}


def test_g3_lema_de_ignora_wrappers_periferia_fijos():
    """§1.2 — con los wrappers FIJOS de periferia (because-of/despite/every/
    probably/…) ahora en `_PRED_NO_LEMA`, `_lema_de` sigue encontrando el
    verbo real envuelto en vez de devolver el predicado del wrapper."""
    ls = {"ls_lexical": "because-of'(lluvia, [do'(Juan,[correr'(Juan)])])"}
    assert c._lema_de(ls) == "correr"
    ls2 = {"ls_lexical": "probably'(despite'(obstaculo, [do'(Ana,[nadar'(Ana)])]))"}
    assert c._lema_de(ls2) == "nadar"


def test_g3_corregir_el_verb_lemma_explicito_persiste_lema_real():
    """§1.1 — reproduce el bug del checkpoint: la LS de origen no expone
    verbo primado (fallback a ls_type="accomplishment"). Con `verb_lemma`
    explícito ("dar"), ESE lema gana sobre `_lema_de` y se persiste bien."""
    tmp = _tmp_data()
    r = c.corregir_el(_res_sin_verbo_primado(), 0,
                      "[do'(Juan,Ø)] CAUSE [BECOME have'(María,regalo)]",
                      _reanalisis_confirma_transferencia, data_dir=tmp, verb_lemma="dar")
    assert r["accion"] == "no-op" and r["plantilla"] == "ditrans_transferencia"
    import pandas as pd
    df = pd.read_excel(os.path.join(tmp, "verbos_ditransitivos.xlsx"))
    assert len(df[df["lema"] == "dar"]) == 1
    shutil.rmtree(tmp)


def test_g3_corregir_el_sin_lema_identificable_va_a_staging_nunca_fila_espuria():
    """§1.3 — MISMO escenario SIN `verb_lemma`: `_lema_de` cae a "accomplishment"
    (nombre de clase) -> la guardia anti-basura lo detecta, NUNCA lo persiste
    en verbos_ditransitivos.xlsx; va a staging con motivo explícito."""
    tmp = _tmp_data()
    import pandas as pd
    n_antes = len(pd.read_excel(os.path.join(tmp, "verbos_ditransitivos.xlsx")))
    r = c.corregir_el(_res_sin_verbo_primado(), 0,
                      "[do'(Juan,Ø)] CAUSE [BECOME have'(María,regalo)]",
                      _reanalisis_confirma_transferencia, data_dir=tmp)
    assert r["accion"] == "staging_lema_no_identificable"
    df = pd.read_excel(os.path.join(tmp, "verbos_ditransitivos.xlsx"))
    assert len(df) == n_antes   # jamás una fila espuria
    assert "accomplishment" not in df["lema"].astype(str).str.lower().values
    assert os.path.exists(os.path.join(tmp, "correcciones_el.csv"))
    shutil.rmtree(tmp)


def test_g3_clase_sugerida_por_plantilla_mapa_completo():
    assert c.clase_sugerida_por_plantilla("state") == "state"
    assert c.clase_sugerida_por_plantilla("activity") == "activity"
    assert c.clase_sugerida_por_plantilla("accomplishment") == "accomplishment"
    assert c.clase_sugerida_por_plantilla("achievement") == "achievement"
    assert c.clase_sugerida_por_plantilla("semelfactive") == "semelfactive"
    assert c.clase_sugerida_por_plantilla("causativa") == "accomplishment"
    assert c.clase_sugerida_por_plantilla("ditrans_transferencia") == "accomplishment"
    assert c.clase_sugerida_por_plantilla("ditrans_benefactiva") == "accomplishment"
    assert c.clase_sugerida_por_plantilla("ditrans_comunicacion") == "accomplishment"
    assert c.clase_sugerida_por_plantilla(None) is None
    assert c.clase_sugerida_por_plantilla("no_existe") is None


# ═══════════════════ G3 §2 — "corregir todo" (EL + clase, un solo paso) ════
def test_g3_corregir_todo_clase_staging_y_el_persistida_un_solo_reanalisis():
    tmp = _tmp_data()
    llamadas = []

    def reanalizar(o):
        llamadas.append(o)
        return _reanalisis_confirma_transferencia(o)

    r = c.corregir_todo(_res(), 0, "[do'(Juan,Ø)] CAUSE [BECOME have'(María,regalo)]",
                        "accomplishment", reanalizar, data_dir=tmp)
    assert len(llamadas) == 1   # UN solo re-análisis compartido, nunca dos
    assert r["accion"] == "staging_clase+no-op"
    assert r["clase_resultado"]["accion"] == "staging_clase"
    assert r["el_resultado"]["accion"] == "no-op"
    assert os.path.exists(os.path.join(tmp, "correcciones_clase.csv"))
    shutil.rmtree(tmp)


def test_g3_corregir_todo_el_no_confirmada_igual_stagea_la_clase():
    tmp = _tmp_data()
    llamadas = []

    def reanalizar(o):
        llamadas.append(o)
        return {"oracion": "x", "ls_lista": [{"ditransitiva": None, "ls_lexical": "",
                                              "core": [], "periferia": [], "agx": []}]}

    r = c.corregir_todo(_res(), 0, "[do'(Juan,Ø)] CAUSE [BECOME have'(María,regalo)]",
                        "accomplishment", reanalizar, data_dir=tmp)
    assert len(llamadas) == 1
    assert r["accion"] == "staging_clase+staging_no_confirmado"
    shutil.rmtree(tmp)


def test_g3_corregir_todo_el_rechazada_cero_reanalisis_pero_clase_igual_stagea():
    tmp = _tmp_data()
    llamadas = []
    r = c.corregir_todo(_res(), 0, "dar'(", "state", lambda o: llamadas.append(o), data_dir=tmp)
    assert len(llamadas) == 0   # EL inválida nunca dispara re-análisis
    assert r["accion"] == "staging_clase+rechazado"
    assert os.path.exists(os.path.join(tmp, "correcciones_clase.csv"))
    shutil.rmtree(tmp)


def test_g3_corregir_todo_respeta_verb_lemma_explicito():
    tmp = _tmp_data()
    r = c.corregir_todo(_res_sin_verbo_primado(), 0,
                        "[do'(Juan,Ø)] CAUSE [BECOME have'(María,regalo)]", "accomplishment",
                        _reanalisis_confirma_transferencia, data_dir=tmp, verb_lemma="dar")
    assert r["el_resultado"]["accion"] == "no-op"
    import pandas as pd
    df = pd.read_excel(os.path.join(tmp, "verbos_ditransitivos.xlsx"))
    assert (df["lema"] == "dar").any()
    shutil.rmtree(tmp)


def test_upsert_ditransitivo_insert_update_noop_conflicto_y_revert():
    import pandas as pd
    tmp = _tmp_data()
    ruta = os.path.join(tmp, "verbos_ditransitivos.xlsx")
    spec = {"familia": "benefactiva", "subtipo_benefactivo": "preparacion",
            "predicado_resultado": "prepared'", "proposito": "become_have"}
    try:
        n0 = len(pd.read_excel(ruta))
        ins = c.persistir_ditransitiva("amasar", spec, tmp)
        assert ins["accion"] == "insert" and len(pd.read_excel(ruta)) == n0 + 1
        assert ins["anterior"] is None and ins["nueva"]["subtipo_benefactivo"] == "preparacion"
        nop = c.persistir_ditransitiva("amasar", spec, tmp)
        assert nop["accion"] == "no-op" and len(pd.read_excel(ruta)) == n0 + 1
        assert nop["anterior"] == nop["nueva"]

        # Verbo conocido no ambiguo: actualización in-place, nunca duplicado.
        reparacion = {"familia": "benefactiva", "subtipo_benefactivo": "cambio_estado",
                      "predicado_resultado": "repaired'", "proposito": "have"}
        upd = c.persistir_ditransitiva("amasar", reparacion, tmp)
        assert upd["accion"] == "update"
        assert upd["anterior"]["subtipo_benefactivo"] == "preparacion"
        assert upd["nueva"]["subtipo_benefactivo"] == "cambio_estado"
        df = pd.read_excel(ruta)
        assert len(df[df["lema"] == "amasar"]) == 1
        assert df[df["lema"] == "amasar"].iloc[0]["predicado_resultado"] == "repaired'"

        conflicto = c.persistir_ditransitiva("traducir", spec, tmp)
        assert conflicto["accion"] == "staging_conflicto"

        antes_revert = open(ruta, "rb").read()
        cambio = c.persistir_ditransitiva("amasar", spec, tmp)
        assert cambio["accion"] == "update"
        c.revert(cambio)
        assert open(ruta, "rb").read() == antes_revert
    finally:
        shutil.rmtree(tmp)


def test_confirmacion_benefactiva_exige_semantica_exacta_no_solo_familia():
    spec = {"familia": "benefactiva", "subtipo_benefactivo": "preparacion",
            "predicado_resultado": "prepared'", "proposito": "become_have"}
    propuesta = ("[[do'(Juan, Ø)] CAUSE [BECOME prepared'(pizzas)]] "
                 "PURP [BECOME have'(María, pizzas)]")
    ls = {"ditransitiva": {"plantilla": "benefactiva", **spec},
          "ls_lexical": propuesta,
          "ls_formal": "[[do'(x, Ø)] CAUSE [BECOME prepared'(z)]] PURP [BECOME have'(y, z)]",
          "variables": {"x": "Juan", "y": "María", "z": "pizzas"},
          "id_a_var": {1: "x", 3: "z", 5: "y"},
          "ls_estructura": [{"predicado": "prepared'", "args": []}]}
    assert c._confirmar_ditransitiva(ls, propuesta, spec)
    ls_mal = {**ls, "ditransitiva": {**ls["ditransitiva"],
                                      "predicado_resultado": "repaired'"}}
    assert not c._confirmar_ditransitiva(ls_mal, propuesta, spec)


def test_correccion_esc_cancela_sin_efectos():
    tmp = _tmp_data()
    antes = sorted(os.listdir(tmp))
    ent = _Entrada(["esc"])   # cancela en el menú
    r = c.bucle_correccion(_res(), lambda o: _res(), sub_idx=0, entrada=ent,
                           salida=lambda *_: None, data_dir=tmp)
    assert r["accion"] == "cancelado"
    assert sorted(os.listdir(tmp)) == antes   # ningún archivo nuevo
    shutil.rmtree(tmp)


# ═══════ Fix 2026-07-12 — -help en prompts post-análisis (nunca se traga) ══
# Bug reproducido por Julian: el prompt "¿Guardar en .txt? (s/n) — o (c)…"
# ignoraba -help y el input caía al prompt siguiente ("Oración (o 'salir')").
# `correccion._pedir` (usado por TODO el menú de corrección y sus sub-menús)
# y `grrux_ai1._flujo_guardar_o_corregir` (extraído del bucle inline de
# main() para poder testearse aquí) ahora responden -help y VUELVEN A
# MOSTRAR el mismo prompt, sin abortar ni tragarse el flujo.
def test_pedir_ayuda_con_termino_responde_y_repregunta():
    """§5 item 4: -help agx dentro de un sub-menú responde y re-muestra el
    MISMO prompt (no cuenta como respuesta, no cancela)."""
    salida = []
    ent = _Entrada(["-help agx", "3"])
    val = c._pedir("  Elige [1/2/3]:", ent, salida.append)
    assert val == "3"   # la respuesta real (tras el -help) sí se procesa
    texto = "\n".join(salida)
    assert "AGX" in texto   # el glosario respondió el término
    assert salida.count("  Elige [1/2/3]:") == 2   # el prompt se repitió


def test_pedir_ayuda_sin_termino_vuelca_glosario_completo():
    salida = []
    ent = _Entrada(["-help", "1"])
    val = c._pedir("  Elige [1/2/3]:", ent, salida.append)
    assert val == "1"
    assert any("Clases aspectuales" in s for s in salida)   # categoría real


def test_pedir_ayuda_termino_no_encontrado_luego_esc_cancela():
    salida = []
    ent = _Entrada(["-help zzz", "esc"])
    val = c._pedir("  Elige [1/2/3]:", ent, salida.append)
    assert val is c._CANCEL   # Esc sigue cancelando limpio TRAS el -help
    assert any("no encontrado" in s for s in salida)


def test_bucle_correccion_ayuda_en_menu_no_aborta_esc_cancela_despues():
    """§5 item 4 completo: dentro del menú de corrección, -help responde SIN
    cerrar el menú; Esc a continuación cancela limpio (sin efectos)."""
    tmp = _tmp_data()
    antes = sorted(os.listdir(tmp))
    salida = []
    ent = _Entrada(["-help agx", "esc"])
    r = c.bucle_correccion(_res(), lambda o: _res(), sub_idx=0, entrada=ent,
                           salida=salida.append, data_dir=tmp)
    assert r["accion"] == "cancelado"
    assert sorted(os.listdir(tmp)) == antes   # -help no contaminó nada
    texto = "\n".join(salida)
    assert "AGX" in texto
    assert "¿Qué está mal en el análisis?" in texto
    shutil.rmtree(tmp)


def _res_gruxx(oracion="Juan corrió"):
    return {"oracion": oracion,
            "ls_lista": [{"ls_type": "activity", "ls_lexical": "do'(Juan,[correr'(Juan)])",
                          "ls_formal": "do'(x,[correr'(x)])", "morph_note": "stat=0.0",
                          "core": [], "periferia": [], "agx": []}],
            "stdout": "--- Oración 1 ---\n┌ SENTENCE\nConvertidas: 1 | Fallidas: 0\n",
            "completeness": [{"ok": True, "checks": [], "resumen": "Completeness: ✓"}]}


def _entrada_contando(respuestas):
    """entrada() falso que además cuenta cuántas veces se lo llamó (para
    verificar que el prompt de guardar/corregir se re-mostró tras -help)."""
    cola = list(respuestas)
    llamadas = []

    def _e(prompt=""):
        llamadas.append(prompt)
        if not cola:
            raise EOFError
        return cola.pop(0)
    _e.llamadas = llamadas
    return _e


def test_flujo_guardar_ayuda_termino_luego_guarda():
    """1. -help agx → glosario responde → re-prompt → s → guarda normal."""
    import grrux_ai1 as g
    tmp, cwd = tempfile.mkdtemp(), os.getcwd()
    os.chdir(tmp)
    try:
        salida = []
        ent = _entrada_contando(["-help agx", "s"])
        resultado = g._flujo_guardar_o_corregir(
            "Juan corrió", _res_gruxx(), lambda o: _res_gruxx(),
            entrada=ent, salida=salida.append)
        assert resultado == "guardado"
        assert len(ent.llamadas) == 2   # el prompt se pidió DOS veces
        assert any("AGX" in s for s in salida)
        assert os.path.exists(g._nombre_archivo("Juan corrió"))
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp)


def test_flujo_guardar_ayuda_completa_luego_no_guarda():
    """2. -help (completo) → re-prompt → n → no guarda, flujo sigue."""
    import grrux_ai1 as g
    salida = []
    ent = _entrada_contando(["-help", "n"])
    resultado = g._flujo_guardar_o_corregir(
        "Juan corrió", _res_gruxx(), lambda o: _res_gruxx(),
        entrada=ent, salida=salida.append)
    assert resultado == "no_guardado"
    assert len(ent.llamadas) == 2
    assert any("Clases aspectuales" in s for s in salida)   # glosario completo


def test_flujo_guardar_ayuda_no_encontrado_luego_corrige():
    """3. -help zzz → 'no encontrado' → re-prompt → c → el menú de
    corrección abre normal (mismo flujo, sin abortar)."""
    import grrux_ai1 as g
    salida = []
    ent = _entrada_contando(["-help zzz", "c"])
    resultado = g._flujo_guardar_o_corregir(
        "Juan corrió", _res_gruxx(), lambda o: _res_gruxx(),
        entrada=ent, salida=salida.append)
    texto = "\n".join(salida)
    assert "no encontrado" in texto
    assert "¿Qué está mal en el análisis?" in texto   # el menú SÍ abrió
    # la entrada se agota dentro del menú (EOF) -> cancela -> vuelve a
    # ofrecer guardar -> EOF también -> no_guardado (nunca revienta)
    assert resultado == "no_guardado"


def test_flujo_guardar_regresion_s_n_salir_directos():
    """5. Regresión: s/n/salir directos (sin -help de por medio) funcionan
    igual que antes del fix."""
    import grrux_ai1 as g

    tmp, cwd = tempfile.mkdtemp(), os.getcwd()
    os.chdir(tmp)
    try:
        assert g._flujo_guardar_o_corregir(
            "Juan corrió", _res_gruxx(), lambda o: _res_gruxx(),
            entrada=_Entrada(["s"]), salida=lambda *_: None) == "guardado"
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp)

    assert g._flujo_guardar_o_corregir(
        "Juan corrió", _res_gruxx(), lambda o: _res_gruxx(),
        entrada=_Entrada(["n"]), salida=lambda *_: None) == "no_guardado"
    assert g._flujo_guardar_o_corregir(
        "Juan corrió", _res_gruxx(), lambda o: _res_gruxx(),
        entrada=_Entrada([""]), salida=lambda *_: None) == "no_guardado"
    assert g._flujo_guardar_o_corregir(
        "Juan corrió", _res_gruxx(), lambda o: _res_gruxx(),
        entrada=_Entrada(["salir"]), salida=lambda *_: None) == "salir"


# ═══════════════════════ @slow — bucle real end-to-end ════════════════════
def test_slow_correccion_ditransitiva_end_to_end():
    """Pipeline real (Stanza + mapper): corregir 'Juan le dio flores a María'
    a la plantilla de transferencia y confirmar por re-análisis. Usa un dir
    temporal para no tocar los léxicos reales; restaura _DITRANS_LEXICON."""
    import stanza
    import rrg_ls_mapper as m
    tmp = _tmp_data()
    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    def procesar(oracion):
        sent = nlp(oracion).sentences[0]
        return {"oracion": oracion, "ls_lista": [m.map_sentence_to_ls(sent)]}

    backup = dict(m._DITRANS_LEXICON) if m._DITRANS_LEXICON is not None else None
    try:
        oracion = "Juan le dio flores a María"
        res = procesar(oracion)
        ent = _Entrada(["2", "[do'(Juan,Ø)] CAUSE [BECOME have'(María,flores)]"])
        r = c.bucle_correccion(res, procesar, sub_idx=0, entrada=ent,
                               salida=lambda *_a: None, data_dir=tmp)
        assert r["accion"] in ("insert", "update", "no-op", "staging_no_confirmado")
    finally:
        if backup is not None:
            m._DITRANS_LEXICON.clear()
            m._DITRANS_LEXICON.update(backup)
        shutil.rmtree(tmp)


def test_slow_correccion_benefactiva_nueva_reanalisis_exacto():
    """Alta real de lema desconocido: el siguiente análisis usa el subtipo."""
    import stanza
    import rrg_ls_mapper as m
    tmp = _tmp_data()
    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    def procesar(oracion):
        return {"oracion": oracion,
                "ls_lista": [m.map_sentence_to_ls(nlp(oracion).sentences[0])]}

    backup = dict(m._DITRANS_LEXICON) if m._DITRANS_LEXICON is not None else None
    try:
        oracion = "Juan le amasó pan a María"
        res = procesar(oracion)
        propuesta = ("do'(Juan, [amasar'(Juan, pan)]) "
                     "PURP [BECOME have'(María, pan)]")
        r = c.corregir_el(res, 0, propuesta, procesar, data_dir=tmp,
                          verb_lemma="amasar")
        assert r["accion"] == "insert"
        nuevo = procesar(oracion)["ls_lista"][0]
        assert nuevo["ditransitiva"]["subtipo_benefactivo"] == "actividad"
        assert nuevo["ls_lexical"] == propuesta
    finally:
        if backup is not None:
            m._DITRANS_LEXICON.clear()
            m._DITRANS_LEXICON.update(backup)
        shutil.rmtree(tmp)


_PUROS = [test_linea_rasgos_traduce_vector, test_linea_rasgos_none_sin_vector,
          test_traducir_apendices_gate_y_ditrans, test_integridad_ok_y_alerta,
          test_render_bloque_orden_grr, test_glosario_busqueda_tolerante,
          test_glosario_no_encontrado, test_es_comando_help_formas,
          test_el_valida_transferencia, test_el_benefactiva_reconoce_subtipo_resultativo_y_wrappers,
          test_el_benefactiva_rechaza_aridad_o_coindexacion_incompatible,
          test_el_benefactiva_actividad_exige_predicado_del_lema,
          test_el_rechazo_nivel1_parentesis,
          test_el_rechazo_nivel2_argumento_ajeno, test_el_rechazo_nivel3_plantilla_desconocida,
          test_correccion_clase_va_a_staging_sin_tocar_contextual,
          test_correccion_el_ditransitiva_persiste_con_confirmacion,
          test_correccion_el_no_confirmada_cae_a_staging_y_revierte,
          test_correccion_enrutado_a_lista_config,
          test_correccion_esc_cancela_sin_efectos,
          test_pedir_ayuda_con_termino_responde_y_repregunta,
          test_pedir_ayuda_sin_termino_vuelca_glosario_completo,
          test_pedir_ayuda_termino_no_encontrado_luego_esc_cancela,
          test_bucle_correccion_ayuda_en_menu_no_aborta_esc_cancela_despues,
          test_flujo_guardar_ayuda_termino_luego_guarda,
          test_flujo_guardar_ayuda_completa_luego_no_guarda,
          test_flujo_guardar_ayuda_no_encontrado_luego_corrige,
          test_flujo_guardar_regresion_s_n_salir_directos,
          test_g0_corregir_clase_staging_sin_menu,
          test_g0_corregir_el_persiste_con_confirmacion,
          test_g0_corregir_el_rechazada_nivel1,
          test_g0_corregir_el_no_confirmada_cae_a_staging,
          test_g0_corregir_enrutado_por_id_sin_menu,
          test_enrutado_recipiente_dativo_no_contamina_verbos_movimiento,
          test_enrutado_sin_posicion_en_la_el_no_se_confirma,
          test_g0_corregir_enrutado_elemento_inexistente,
          test_g0_corregir_enrutado_destino_desconocido,
          test_g0_flujo_clase_interactivo_sigue_igual_via_menu,
          test_g3_lema_de_ignora_wrappers_periferia_fijos,
          test_g3_corregir_el_verb_lemma_explicito_persiste_lema_real,
          test_g3_corregir_el_sin_lema_identificable_va_a_staging_nunca_fila_espuria,
          test_g3_clase_sugerida_por_plantilla_mapa_completo,
          test_g3_corregir_todo_clase_staging_y_el_persistida_un_solo_reanalisis,
          test_g3_corregir_todo_el_no_confirmada_igual_stagea_la_clase,
          test_g3_corregir_todo_el_rechazada_cero_reanalisis_pero_clase_igual_stagea,
          test_g3_corregir_todo_respeta_verb_lemma_explicito,
          test_upsert_ditransitivo_insert_update_noop_conflicto_y_revert,
          test_confirmacion_benefactiva_exige_semantica_exacta_no_solo_familia]

if not RUN_SLOW:
    try:
        import pytest
        test_slow_correccion_ditransitiva_end_to_end = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(
            test_slow_correccion_ditransitiva_end_to_end)
        test_slow_correccion_benefactiva_nueva_reanalisis_exacto = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(
            test_slow_correccion_benefactiva_nueva_reanalisis_exacto)
    except ImportError:
        pass


def main():
    tests = _PUROS + ([test_slow_correccion_ditransitiva_end_to_end,
                       test_slow_correccion_benefactiva_nueva_reanalisis_exacto]
                      if RUN_SLOW else [])
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
