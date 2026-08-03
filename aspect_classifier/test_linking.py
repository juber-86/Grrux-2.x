"""Tests de linking.py — Fase LINKING, Etapa LA1 (ver prompt_LA1.md).

Ejecutar:
    python -m aspect_classifier.test_linking          # puros (estructuras a mano)
    python -m aspect_classifier.test_linking --slow   # + Stanza/BERTIN end-to-end

Compatible con pytest (los @slow requieren RUN_SLOW=1).

Los tests fríos construyen `ls_estructura` A MANO con las plantillas
TEÓRICAMENTE CORRECTAS (independientes de si el pipeline vivo ya las
produce así) — son tests del ALGORITMO (asignar_macropapeles/seleccionar_psa/
verificar_concordancia), no del pipeline completo. Los @slow corren la
oración real y documentan el estado actual del pipeline, incluidas
discrepancias conocidas (ver CHECKPOINT_LA1.md §2).
"""

import os
import sys
import tempfile
from pathlib import Path

from discodop.tree import ParentedTree

from . import linking
from .linking import (arg, asignar_macropapeles, detectar_voz, enriquecer_ids,
                      expectativas_sintacticas, frame, log_discrepancia,
                      paso_5_asignacion, reconciliar, seleccionar_psa,
                      traza_linking, verificar_concordancia)

RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv


def _arbol(spec):
    """Igual que test_completeness._arbol: ParentedTree a partir de tuplas
    anidadas (label, [hijos]) o (label, hoja_entera 0-based)."""
    label, hijos = spec
    if isinstance(hijos, int):
        return ParentedTree(label, [hijos])
    return ParentedTree(label, [_arbol(h) for h in hijos])


# ---------------------------------------------------------------------------
# §2.1 — asignar_macropapeles (AUH)
# ---------------------------------------------------------------------------
def test_ditransitiva_juan_le_dio_flores_a_maria():
    """'Juan le dio flores a María' → Actor=Juan(1er arg. de do'),
    Undergoer=flores(2º arg. de have'), María=NMR, M=2 (ejemplo canónico
    del prompt, §4)."""
    estructura = [
        frame("do'", arg("Juan", "1_do", )),
        frame("have'", arg("María", "1_pred_xy", nmr=True), arg("flores", "2_pred_xy")),
    ]
    m = asignar_macropapeles(estructura)
    assert m["actor"]["texto"] == "Juan"
    assert m["actor"]["justificacion"] == "1er arg. de do'"
    assert m["undergoer"]["texto"] == "flores"
    assert m["undergoer"]["justificacion"] == "2º arg. de have'"
    assert [n["texto"] for n in m["nmr"]] == ["María"]
    assert m["m_transitividad"] == 2


def test_se_venden_casas_o_bloqueado_para_actor():
    """'Se venden casas' (estructura TEÓRICAMENTE correcta: [do'(Ø,Ø)]
    CAUSE [BECOME sold'(casas)]) → Ø no puede ser Actor, casas (arg. de
    estado) asciende a Undergoer, M=1."""
    estructura = [
        frame("do'", arg("Ø", "1_do")),
        frame("sold'", arg("casas", "arg_estado")),
    ]
    m = asignar_macropapeles(estructura)
    assert m["actor"] is None
    assert m["undergoer"]["texto"] == "casas"
    assert m["undergoer"]["justificacion"] == "arg. de estado sold'"
    assert m["m_transitividad"] == 1
    assert m["inespecificado"][0]["texto"] == "Ø"


def test_llueve_atransitivo():
    """'Llueve' → sin ninguna posición ocupada, M=0 (atransitivo)."""
    m = asignar_macropapeles([])
    assert m["actor"] is None and m["undergoer"] is None
    assert m["m_transitividad"] == 0


def test_pasiva_perifrastica_pastel_comido_por_juan():
    """'El pastel fue comido por Juan' (estructura correcta: Juan=agente/
    comedor, pastel=paciente/comido) → Actor=Juan(1_do), Undergoer=
    pastel(2º arg. de comer'), PSA debe terminar en Undergoer (ver test de
    seleccionar_psa más abajo)."""
    estructura = [
        frame("do'", arg("Juan", "1_do")),
        frame("comer'", arg("pastel", "2_pred_xy")),
    ]
    m = asignar_macropapeles(estructura)
    assert m["actor"]["texto"] == "Juan"
    assert m["undergoer"]["texto"] == "pastel"
    assert m["m_transitividad"] == 2


def test_juan_sabe_la_respuesta_estado_de_dos_lugares():
    """'Juan sabe la respuesta' → Actor=Juan(1er arg. de pred'(x,y)),
    Undergoer=respuesta(2º arg. de pred'(x,y)), M=2 -- estado M-transitivo
    (doble ruta psych de la jerarquía: TODO documentado, no se resuelve
    aquí, ver docstring de asignar_macropapeles)."""
    estructura = [frame("saber'", arg("Juan", "1_pred_xy"), arg("respuesta", "2_pred_xy"))]
    m = asignar_macropapeles(estructura)
    assert m["actor"]["texto"] == "Juan"
    assert m["actor"]["justificacion"] == "1er arg. de saber'"
    assert m["undergoer"]["texto"] == "respuesta"
    assert m["m_transitividad"] == 2


def test_juan_corrio_m_1():
    """'Juan corrió' → un solo macropapel (Actor, arg. de do'), M=1."""
    estructura = [frame("do'", arg("Juan", "1_do"))]
    m = asignar_macropapeles(estructura)
    assert m["actor"]["texto"] == "Juan"
    assert m["undergoer"] is None
    assert m["m_transitividad"] == 1


def test_undergoer_unico_cuando_alone_en_rango_bajo():
    """Un único candidato en rango bajo (arg_estado, p.ej. 'el jarrón se
    rompió') es Undergoer por defecto, no Actor."""
    estructura = [frame("roto'", arg("jarrón", "arg_estado"))]
    m = asignar_macropapeles(estructura)
    assert m["actor"] is None
    assert m["undergoer"]["texto"] == "jarrón"
    assert m["m_transitividad"] == 1


# ---------------------------------------------------------------------------
# §2.2 — voz y PSA
# ---------------------------------------------------------------------------
def test_voz_activa_transitiva_psa_actor():
    m = {"actor": {"texto": "Juan"}, "undergoer": {"texto": "manzana"},
        "nmr": [], "m_transitividad": 2}
    psa = seleccionar_psa(m, "activa")
    assert psa["macrorol"] == "Actor" and psa["arg"]["texto"] == "Juan"


def test_voz_activa_intransitiva_undergoer_unico_es_psa():
    """'Juan llegó' (Achievement no agentivo): sin Actor, el único
    Undergoer ES el PSA -- el macropapel único de un intransitivo se
    realiza como sujeto por defecto, sea Actor o Undergoer."""
    m = {"actor": None, "undergoer": {"texto": "Juan"}, "nmr": [], "m_transitividad": 1}
    psa = seleccionar_psa(m, "activa")
    assert psa["macrorol"] == "Undergoer" and psa["arg"]["texto"] == "Juan"


def test_voz_pasiva_perifrastica_psa_undergoer_no_actor():
    """'El pastel fue comido por Juan' → PSA=Undergoer(pastel),
    Juan=Actor NO-PSA (aunque Actor exista, la pasiva lo excluye del PSA)."""
    m = {"actor": {"texto": "Juan"}, "undergoer": {"texto": "pastel"},
        "nmr": [], "m_transitividad": 2}
    psa = seleccionar_psa(m, "pasiva_perifrastica")
    assert psa["macrorol"] == "Undergoer" and psa["arg"]["texto"] == "pastel"


def test_voz_anticausativa_psa_undergoer():
    m = {"actor": None, "undergoer": {"texto": "casas"}, "nmr": [], "m_transitividad": 1}
    psa = seleccionar_psa(m, "anticausativa")
    assert psa["macrorol"] == "Undergoer" and psa["arg"]["texto"] == "casas"


def test_voz_impersonal_sin_psa():
    m = {"actor": None, "undergoer": None, "nmr": [], "m_transitividad": 0}
    psa = seleccionar_psa(m, "impersonal")
    assert psa["macrorol"] is None and psa["arg"] is None


def test_detectar_voz_las_cuatro_fuentes():
    assert detectar_voz({"se_anticausativo": True}, {}, []) == "anticausativa"
    assert detectar_voz({}, {}, [{"fuente": "se_pasivo"}]) == "pasiva_refleja"
    assert detectar_voz({}, {"impersonal": True}, []) == "impersonal"
    assert detectar_voz({}, {}, [{"fuente": "se_impersonal"}]) == "impersonal"
    assert detectar_voz({}, {"core": [{"deprel": "nsubj:pass"}]}, []) == "pasiva_perifrastica"
    assert detectar_voz({}, {"core": [{"deprel": "nsubj"}]}, []) == "activa"


# ---------------------------------------------------------------------------
# §2.3 — concordancia
# ---------------------------------------------------------------------------
def test_concordancia_venden_casas_ok():
    """'Se venden casas' → venden(3pl) ↔ casas(3pl) ✓."""
    psa = {"macrorol": "Undergoer", "arg": {"texto": "casas", "id": 3}}
    c = verificar_concordancia(psa, {"Number": "Plur"}, {"Person": "3", "Number": "Plur"})
    assert c["aplica"] is True and c["ok"] is True
    assert c["corto"] == "3pl"


def test_advertencia_concordancia_demo_se_vende_casas():
    """Fixture del prompt (§5, 'el warning demo'): 'Se vende casas' -- casas
    (3pl) como PSA pero el verbo 'vende' está en singular → ⚠, no ✓."""
    psa = {"macrorol": "Undergoer", "arg": {"texto": "casas", "id": 3}}
    c = verificar_concordancia(psa, {"Number": "Plur"}, {"Person": "3", "Number": "Sing"})
    assert c["aplica"] is True and c["ok"] is False
    assert "✗" in c["detalle"]


def test_concordancia_pro_drop_por_construccion():
    """Actor implícito (pro-drop): concuerda por construcción, siempre ok
    -- no hay id de token, así que no hay nada independiente que contrastar."""
    psa = {"macrorol": "Actor", "arg": {"texto": "3sg", "id": None}}
    c = verificar_concordancia(psa, None, {"Person": "3", "Number": "Sing"})
    assert c["aplica"] is True and c["ok"] is True
    assert c["por_construccion"] is True
    assert c["corto"] == "3sg"


def test_concordancia_sin_psa_no_aplica():
    c = verificar_concordancia({"macrorol": None, "arg": None}, None, None)
    assert c["aplica"] is False and c["ok"] is True


# ---------------------------------------------------------------------------
# §2.4 — traza de 5 pasos
# ---------------------------------------------------------------------------
def test_traza_tiene_cinco_pasos_numerados():
    estructura = [frame("do'", arg("Juan", "1_do"))]
    m = asignar_macropapeles(estructura)
    voz = "activa"
    psa = seleccionar_psa(m, voz)
    c = verificar_concordancia(psa, None, {"Person": "3", "Number": "Sing"})
    traza = traza_linking("activity", m, voz, psa, c, {"nombre": "estándar", "fuente": "roberta"})
    assert len(traza) == 5
    for i, paso in enumerate(traza, start=1):
        assert paso.startswith(f"Paso {i} —")
    assert "pendiente" in traza[4]   # sin comp todavía


def test_paso_5_se_completa_con_comp():
    comp = {"ok": True, "checks": [{"tipo": "argumento", "elemento": "x1",
                                    "estado": "ok", "detalle": "x1↔NP"}],
           "resumen": "Completeness: ✓ x1↔NP"}
    assert paso_5_asignacion(comp) == "Paso 5 — Asignación: x1↔NP"
    assert paso_5_asignacion(None) != paso_5_asignacion(comp)


# ---------------------------------------------------------------------------
# §3 — reconciliación con args_map
# ---------------------------------------------------------------------------
def test_reconciliar_coincide():
    estructura = [
        frame("do'", arg("Juan", "1_do")),
        frame("have'", arg("María", "1_pred_xy", nmr=True), arg("flores", "2_pred_xy")),
    ]
    m = asignar_macropapeles(estructura)
    args_map = ("x1:Juan,nsubj,Actor(Efectuador); x2:flores,obj,Undergoer(Tema); "
               "x3:María,obl:arg,NMR(Poseedor)")
    r = reconciliar(m, args_map)
    assert r["hay_discrepancia"] is False
    assert all(f["coincide"] for f in r["filas"])


def test_reconciliar_discrepancia_hallazgo_real_pastel_juan():
    """Documenta el hallazgo real de esta etapa (CHECKPOINT_LA1.md §2): el
    pipeline vivo liga x1/x2 por ORDEN DE SUPERFICIE, no por macrorrol, así
    que en una pasiva el AUH (posicional) y args_map (deprel) discrepan --
    exactamente lo que §3 está diseñado para detectar."""
    estructura = [frame("do'", arg("pastel", "1_do")), frame("comer'", arg("Juan", "2_pred_xy"))]
    m = asignar_macropapeles(estructura)
    args_map = "x1:pastel,nsubj:pass,Undergoer; x2:Juan,obl:agent,Actor"
    r = reconciliar(m, args_map)
    assert r["hay_discrepancia"] is True
    assert {f["texto"]: f["coincide"] for f in r["filas"]} == {"pastel": False, "Juan": False}


def test_log_discrepancia_dedupe():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "disc.csv"
        fila = {"texto": "casas", "macrorol_auh": "Actor", "posicion": "1_do",
               "macropapel_previo": "Undergoer(paciente→PSA)"}
        log_discrepancia("vender", "Se venden casas.", fila, p)
        log_discrepancia("vender", "Se venden casas.", fila, p)   # dedupe
        lineas = p.read_text(encoding="utf-8").strip().splitlines()
        assert len(lineas) == 2   # header + 1


# ---------------------------------------------------------------------------
# enriquecer_ids
# ---------------------------------------------------------------------------
def test_enriquecer_ids():
    estructura = [frame("do'", arg("Juan", "1_do")), frame("pred'", arg("Ø", "arg_estado"))]
    enriquecer_ids(estructura, {"Juan": 1})
    assert estructura[0]["args"][0]["id"] == 1
    assert estructura[1]["args"][0]["id"] is None   # "Ø" nunca tiene id


# ---------------------------------------------------------------------------
# §5 — round-trip (expectativas_sintacticas)
# ---------------------------------------------------------------------------
# "Juan le dio flores a María": Juan=0, le=1, dio=2, flores=3, a=4, María=5 (0-based)
ARBOL_DITRANS_OK = _arbol(("CLAUSE", [
    ("CORE", [
        ("NP", [("N", 0)]),
        ("NUC", [("AGX", 1), ("V", 2)]),
        ("NP", [("N", 3)]),
        ("PP", [("P", 4), ("NP", [("N", 5)])]),
    ]),
]))

_MACROPAPELES_DITRANS = {
    "actor": {"texto": "Juan", "posicion": "1_do", "id": 1},
    "undergoer": {"texto": "flores", "posicion": "2_pred_xy", "id": 4},
    "nmr": [{"texto": "María", "posicion": "1_pred_xy", "id": 6, "nmr": True}],
    "m_transitividad": 2,
}
_AGX_DITRANS = [{"clitico": "le", "fuente": "dativo", "doblado": True,
                "arg_id": 6, "clitico_id": 2}]
_CONCORDANCIA_OK = {"aplica": True, "ok": True, "corto": "3sg",
                    "detalle": "PSA 'Juan' 3sg vs verbo 3sg ✓"}


def test_roundtrip_conteo_core_y_agx_ok():
    checks = expectativas_sintacticas(_MACROPAPELES_DITRANS, _AGX_DITRANS,
                                      ARBOL_DITRANS_OK, _CONCORDANCIA_OK)
    por_elemento = {c["elemento"]: c["estado"] for c in checks}
    assert por_elemento["conteo_core"] == "linking_ok"
    assert por_elemento["concordancia"] == "linking_ok"
    assert por_elemento["agx"] == "linking_ok"
    assert all(c["estado"].startswith("linking_") for c in checks)


def test_roundtrip_agx_esperado_pero_ausente():
    """Árbol SIN el nodo AGX (le nunca llegó a marcarse) -- round-trip debe
    detectarlo como falta, ángulo distinto (producción) del que ya cubre
    completeness._chequear_agx."""
    arbol_sin_agx = _arbol(("CLAUSE", [
        ("CORE", [
            ("NP", [("N", 0)]), ("NUC", [("V", 2)]), ("NP", [("N", 3)]),
            ("PP", [("P", 4), ("NP", [("N", 5)])]),
        ]),
    ]))
    checks = expectativas_sintacticas(_MACROPAPELES_DITRANS, _AGX_DITRANS,
                                      arbol_sin_agx, _CONCORDANCIA_OK)
    agx_check = next(c for c in checks if c["elemento"] == "agx")
    assert agx_check["estado"] == "linking_falta_en_arbol"


def test_roundtrip_concordancia_error_se_propaga():
    concordancia_mal = {"aplica": True, "ok": False, "corto": "3sg",
                        "detalle": "PSA 'casas' 3pl vs verbo 'vende' 3sg ✗"}
    checks = expectativas_sintacticas(_MACROPAPELES_DITRANS, [], ARBOL_DITRANS_OK,
                                      concordancia_mal)
    c = next(c for c in checks if c["elemento"] == "concordancia")
    assert c["estado"] == "linking_concordancia_error"


def test_roundtrip_sin_arbol_sin_checks():
    assert expectativas_sintacticas(_MACROPAPELES_DITRANS, [], None, _CONCORDANCIA_OK) == []


# ---------------------------------------------------------------------------
# Validación opcional de coherencia (§2.1) contra el continuum xlsx
# ---------------------------------------------------------------------------
def test_auh_coherente_con_continuum_xlsx():
    """Las 5 posiciones de AUH deben corresponder 1:1, en el MISMO orden, a
    las 5 columnas de data/continuum_de_relaciones_tematicas.xlsx (Van
    Valin 2005:58, la misma tabla que usa ditransitivas.cargar_continuum)."""
    import pandas as pd

    path = Path(__file__).parent / "data" / "continuum_de_relaciones_tematicas.xlsx"
    columnas = list(pd.read_excel(path, header=2).columns)
    assert len(linking.AUH) == len(columnas) == 5
    assert "DO" in columnas[0]
    assert "do'" in columnas[1]
    assert "Primer" in columnas[2] and "pred'" in columnas[2]
    assert "Segundo" in columnas[3] and "pred'" in columnas[3]
    assert "estado" in columnas[4]


# ---------------------------------------------------------------------------
# Integración (Stanza + BERTIN) -- solo con --slow / RUN_SLOW=1
# ---------------------------------------------------------------------------
def test_slow_linea_compacta_ditransitiva_byte_a_byte():
    """El ejemplo canónico del prompt (§4), byte a byte, end-to-end."""
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    ls = m.map_sentence_to_ls(nlp("Juan le dio flores a María.").sentences[0])
    assert ls["linking"]["macropapeles"]["m_transitividad"] == 2
    linea = linking.linea_compacta(ls["linking"]["macropapeles"], ls["linking"]["psa"],
                                   ls["linking"]["concordancia"])
    assert linea == ("Linking: Actor=Juan (1er arg. de do') · "
                     "Undergoer=flores (2º arg. de have') · María=NMR · "
                     "M-transitivo=2 · PSA=Actor · concordancia 3sg ✓")


def test_slow_se_pasivo_hallazgo_documentado():
    """LA2: se pasivo resultativo, AUH y args_map ya concilian."""
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    ls = m.map_sentence_to_ls(nlp("Se venden casas.").sentences[0])
    assert ls["linking"]["reconciliacion"]["hay_discrepancia"] is False
    assert ls["ls_lexical"] == "[do'(Ø, Ø)] CAUSE [BECOME vendido'(casas)]"
    assert ls["linking"]["psa"]["macrorol"] == "Undergoer"


def test_slow_pasiva_perifrastica_y_estado_dos_lugares():
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    ls = m.map_sentence_to_ls(nlp("Juan sabe la respuesta.").sentences[0])
    assert ls["linking"]["macropapeles"]["actor"]["texto"] == "Juan"
    assert ls["linking"]["macropapeles"]["undergoer"]["texto"] == "respuesta"
    assert ls["linking"]["psa"]["macrorol"] == "Actor"
    assert ls["linking"]["concordancia"]["ok"] is True


def test_slow_concordancia_real_llego_los_invitados():
    """Demostración REAL (sin fixture, oración real por Stanza) del warning
    de concordancia: 'Llegó los invitados' (verbo singular, sujeto plural,
    único macropapel Undergoer/Actor según clase -> PSA) debe dar ⚠;
    'Llegaron los invitados' (concuerda) debe dar ✓."""
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    mal = m.map_sentence_to_ls(nlp("Llegó los invitados.").sentences[0])
    bien = m.map_sentence_to_ls(nlp("Llegaron los invitados.").sentences[0])
    assert mal["linking"]["concordancia"]["ok"] is False
    assert bien["linking"]["concordancia"]["ok"] is True


def test_slow_bateria_sin_regresion_de_clase_ni_el():
    """Etapa ADITIVA (§ cabecera del prompt): las mismas dianas históricas
    deben dar la MISMA clase y la MISMA EL que sin LA1 -- linking no debe
    tocar ls_type/ls_formal/ls_lexical/args_map."""
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    dianas = ["Juan corrió.", "Juan comió la pizza.", "El vaso se rompió.",
             "Juan llegó tarde.", "Juan estudió tres horas anoche.",
             "Se venden casas baratas."]
    cfg = m._aspect_clf.config
    previo = dict(cfg.get("linking", {}))
    con = [m.map_sentence_to_ls(nlp(f).sentences[0]) for f in dianas]
    try:
        cfg["linking"] = {**previo, "enabled": False}
        sin = [m.map_sentence_to_ls(nlp(f).sentences[0]) for f in dianas]
    finally:
        cfg["linking"] = previo
    for c, s, f in zip(con, sin, dianas):
        assert c["ls_type"] == s["ls_type"], f
        assert c["ls_formal"] == s["ls_formal"], f
        assert c["ls_lexical"] == s["ls_lexical"], f
        assert c["args_map"] == s["args_map"], f


def test_slow_flag_apagado_byte_identico():
    """`linking.enabled: false` → ninguna clave nueva, cero cambios en el
    resto del dict (a diferencia de OPERATORS, esta etapa no está acoplada
    a ningún otro mecanismo -- byte-idéntico en el sentido fuerte)."""
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    frases = ["Juan le dio flores a María.", "Se venden casas.",
             "El pastel fue comido por Juan.", "Llueve.", "Juan es médico."]
    cfg = m._aspect_clf.config
    previo = dict(cfg.get("linking", {}))
    con = [m.map_sentence_to_ls(nlp(f).sentences[0]) for f in frases]
    try:
        cfg["linking"] = {**previo, "enabled": False}
        sin = [m.map_sentence_to_ls(nlp(f).sentences[0]) for f in frases]
    finally:
        cfg["linking"] = previo

    for c, s, f in zip(con, sin, frases):
        assert "linking" not in s, f
        assert "ls_estructura" not in s, f
        c_sin_linking = {k: v for k, v in c.items() if k not in ("linking", "ls_estructura")}
        assert c_sin_linking == s, f


if not RUN_SLOW:
    try:
        import pytest
        test_slow_linea_compacta_ditransitiva_byte_a_byte = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_linea_compacta_ditransitiva_byte_a_byte)
        test_slow_se_pasivo_hallazgo_documentado = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_se_pasivo_hallazgo_documentado)
        test_slow_pasiva_perifrastica_y_estado_dos_lugares = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_pasiva_perifrastica_y_estado_dos_lugares)
        test_slow_concordancia_real_llego_los_invitados = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_concordancia_real_llego_los_invitados)
        test_slow_bateria_sin_regresion_de_clase_ni_el = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_bateria_sin_regresion_de_clase_ni_el)
        test_slow_flag_apagado_byte_identico = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_flag_apagado_byte_identico)
    except ImportError:
        pass


def main():
    rapidos = [
        test_ditransitiva_juan_le_dio_flores_a_maria,
        test_se_venden_casas_o_bloqueado_para_actor,
        test_llueve_atransitivo,
        test_pasiva_perifrastica_pastel_comido_por_juan,
        test_juan_sabe_la_respuesta_estado_de_dos_lugares,
        test_juan_corrio_m_1,
        test_undergoer_unico_cuando_alone_en_rango_bajo,
        test_voz_activa_transitiva_psa_actor,
        test_voz_activa_intransitiva_undergoer_unico_es_psa,
        test_voz_pasiva_perifrastica_psa_undergoer_no_actor,
        test_voz_anticausativa_psa_undergoer,
        test_voz_impersonal_sin_psa,
        test_detectar_voz_las_cuatro_fuentes,
        test_concordancia_venden_casas_ok,
        test_advertencia_concordancia_demo_se_vende_casas,
        test_concordancia_pro_drop_por_construccion,
        test_concordancia_sin_psa_no_aplica,
        test_traza_tiene_cinco_pasos_numerados,
        test_paso_5_se_completa_con_comp,
        test_reconciliar_coincide,
        test_reconciliar_discrepancia_hallazgo_real_pastel_juan,
        test_log_discrepancia_dedupe,
        test_enriquecer_ids,
        test_roundtrip_conteo_core_y_agx_ok,
        test_roundtrip_agx_esperado_pero_ausente,
        test_roundtrip_concordancia_error_se_propaga,
        test_roundtrip_sin_arbol_sin_checks,
        test_auh_coherente_con_continuum_xlsx,
    ]
    lentos = [test_slow_linea_compacta_ditransitiva_byte_a_byte,
             test_slow_se_pasivo_hallazgo_documentado,
             test_slow_pasiva_perifrastica_y_estado_dos_lugares,
             test_slow_concordancia_real_llego_los_invitados,
             test_slow_bateria_sin_regresion_de_clase_ni_el,
             test_slow_flag_apagado_byte_identico]
    tests = rapidos + (lentos if RUN_SLOW else [])

    fallos = 0
    for t in tests:
        try:
            t()
            print(f"  [OK]   {t.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"  [FAIL] {t.__name__}: {e}")
    if not RUN_SLOW:
        print("  (integración omitida; usa --slow)")
    if fallos:
        sys.exit(1)
    print(f"\n{len(tests)} tests pasaron.")


if __name__ == "__main__":
    main()
