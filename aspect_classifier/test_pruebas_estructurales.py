"""Tests de las pruebas de Van Valin ESTRUCTURALES (P1-P5 sobre la oración real).

Ejecutar:
    python -m aspect_classifier.test_pruebas_estructurales          # puros
    python -m aspect_classifier.test_pruebas_estructurales --slow   # + Stanza/BERTIN

Compatible con pytest (los @slow requieren RUN_SLOW=1).
"""

import os
import sys

from .nucleo_periferia import analizar_roles
from .pruebas_estructurales import (CUADRO_PRUEBAS, aplicar_coerciones,
                                    detectar_evidencia, linea_coherencia,
                                    tiene_prueba)

RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv


def _tok(id_, text, lemma, upos, deprel, head, feats=""):
    return {"id": id_, "text": text, "lemma": lemma, "upos": upos,
            "deprel": deprel, "head": head, "feats": feats}


def _roles(toks, root_id=1):
    return analizar_roles(toks, root_id, {})


# "tosió durante una hora"
TOSIO_DURANTE = [
    _tok(1, "tosió", "toser", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=3|Tense=Past"),
    _tok(2, "durante", "durante", "ADP", "case", 4),
    _tok(3, "una", "uno", "DET", "det", 4),
    _tok(4, "hora", "hora", "NOUN", "obl", 1),
]

# "tosió por una hora"
TOSIO_POR = [t if t["id"] != 2 else _tok(2, "por", "por", "ADP", "case", 4)
             for t in TOSIO_DURANTE]

# "estudié tres horas" (duración desnuda, sin preposición)
ESTUDIE_DESNUDA = [
    _tok(1, "estudié", "estudiar", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=1|Tense=Past"),
    _tok(2, "tres", "tres", "NUM", "nummod", 3),
    _tok(3, "horas", "hora", "NOUN", "obl", 1),
]

# "corrió en una hora" (terminativa)
CORRIO_EN_HORA = [
    _tok(1, "corrió", "correr", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=3|Tense=Past"),
    _tok(2, "en", "en", "ADP", "case", 4),
    _tok(3, "una", "uno", "DET", "det", 4),
    _tok(4, "hora", "hora", "NOUN", "obl", 1),
]

# "Juan corrió en la casa" (locativo: NO debe disparar P4/P5)
CORRIO_EN_CASA = [
    _tok(1, "Juan", "Juan", "PROPN", "nsubj", 2),
    _tok(2, "corrió", "correr", "VERB", "root", 0),
    _tok(3, "en", "en", "ADP", "case", 5),
    _tok(4, "la", "el", "DET", "det", 5),
    _tok(5, "casa", "casa", "NOUN", "obl", 2),
]

# "Juan corre todos los días" (frecuencia habitual, NO duración: "los" es
# artículo definido, det directo de "días"; "todos" cuelga de "los")
CORRE_TODOS_LOS_DIAS = [
    _tok(1, "Juan", "Juan", "PROPN", "nsubj", 2),
    _tok(2, "corre", "correr", "VERB", "root", 0),
    _tok(3, "todos", "todo", "DET", "det", 4),
    _tok(4, "los", "el", "DET", "det", 5),
    _tok(5, "días", "día", "NOUN", "obl", 2),
]

# "Juan corrió cada semana" (distributivo, NO duración)
CORRIO_CADA_SEMANA = [
    _tok(1, "Juan", "Juan", "PROPN", "nsubj", 2),
    _tok(2, "corrió", "correr", "VERB", "root", 0),
    _tok(3, "cada", "cada", "DET", "det", 4),
    _tok(4, "semana", "semana", "NOUN", "obl", 2),
]

# "corrió vigorosamente" / "corrió lentamente"
CORRIO_VIGOROSAMENTE = [
    _tok(1, "corrió", "correr", "VERB", "root", 0),
    _tok(2, "vigorosamente", "vigorosamente", "ADV", "advmod", 1),
]
CORRIO_LENTAMENTE = [
    _tok(1, "corrió", "correr", "VERB", "root", 0),
    _tok(2, "lentamente", "lentamente", "ADV", "advmod", 1),
]


# ---------------------------------------------------------------------------
# Detección de evidencia (P1-P5)
# ---------------------------------------------------------------------------
def test_p4_durante():
    ev = detectar_evidencia(TOSIO_DURANTE, 1, _roles(TOSIO_DURANTE), None, {})
    assert [e["prueba"] for e in ev["evidencias"]] == ["P4"]
    assert ev["evidencias"][0]["rasgo"] == "durativo"
    assert "durante" in ev["evidencias"][0]["trigger"]


def test_p4_por():
    ev = detectar_evidencia(TOSIO_POR, 1, _roles(TOSIO_POR), None, {})
    assert [e["prueba"] for e in ev["evidencias"]] == ["P4"]
    assert "por" in ev["evidencias"][0]["trigger"]


def test_p4_duracion_desnuda():
    ev = detectar_evidencia(ESTUDIE_DESNUDA, 1, _roles(ESTUDIE_DESNUDA), None, {})
    assert [e["prueba"] for e in ev["evidencias"]] == ["P4"]
    assert ev["evidencias"][0]["trigger"] == "horas"


def test_p5_terminativa_en_tiempo():
    ev = detectar_evidencia(CORRIO_EN_HORA, 1, _roles(CORRIO_EN_HORA), None, {})
    assert [e["prueba"] for e in ev["evidencias"]] == ["P5"]
    assert ev["evidencias"][0]["rasgo"] == "terminativo"


def test_p5_no_dispara_con_locativo():
    ev = detectar_evidencia(CORRIO_EN_CASA, 2, _roles(CORRIO_EN_CASA, 2), None, {})
    assert ev["evidencias"] == [], "'en la casa' es locativo, no terminativa"


def test_p4_no_dispara_con_articulo_definido_ni_distributivo():
    """'todos los días' / 'cada semana' son frecuencia habitual, no duración:
    el artículo definido ('los') y el distributivo ('cada') no cuentan como
    determinante de cantidad (a diferencia de 'una hora')."""
    ev = detectar_evidencia(CORRE_TODOS_LOS_DIAS, 2,
                            _roles(CORRE_TODOS_LOS_DIAS, 2), None, {})
    assert ev["evidencias"] == [], ev["evidencias"]

    ev = detectar_evidencia(CORRIO_CADA_SEMANA, 2,
                            _roles(CORRIO_CADA_SEMANA, 2), None, {})
    assert ev["evidencias"] == [], ev["evidencias"]


def test_p1_progresivo():
    ev = detectar_evidencia([], 1, {"periferia": []}, "prog", {})
    assert [e["prueba"] for e in ev["evidencias"]] == ["P1"]
    assert detectar_evidencia([], 1, {"periferia": []}, None, {})["evidencias"] == []
    assert detectar_evidencia([], 1, {"periferia": []}, "complet", {})["evidencias"] == []


def test_p2_adverbio_dinamico():
    ev = detectar_evidencia(CORRIO_VIGOROSAMENTE, 1,
                            _roles(CORRIO_VIGOROSAMENTE), None, {})
    assert [e["prueba"] for e in ev["evidencias"]] == ["P2"]


def test_p3_adverbio_ritmo():
    ev = detectar_evidencia(CORRIO_LENTAMENTE, 1,
                            _roles(CORRIO_LENTAMENTE), None, {})
    assert [e["prueba"] for e in ev["evidencias"]] == ["P3"]


def test_tiene_prueba_helper():
    ev = detectar_evidencia(TOSIO_DURANTE, 1, _roles(TOSIO_DURANTE), None, {})
    assert tiene_prueba(ev, "P4")
    assert not tiene_prueba(ev, "P5")


# ---------------------------------------------------------------------------
# Coerciones R1/R2 (cambian clase) y R3/R4 (solo anotan)
# ---------------------------------------------------------------------------
def test_r1_semelfactivo_iterativo_por_progresivo():
    ev = {"evidencias": [{"prueba": "P1", "trigger": "estar+gerundio",
                          "rasgo": "progresivo", "implica": {}}]}
    r = aplicar_coerciones("semelfactive", ev, False, {})
    assert r["clase"] == "activity"
    assert "coercion=P1/P4 semelfactive→activity_iterativa" in r["notas"]


def test_r1_semelfactivo_iterativo_por_durativa():
    ev = detectar_evidencia(TOSIO_DURANTE, 1, _roles(TOSIO_DURANTE), None, {})
    r = aplicar_coerciones("semelfactive", ev, False, {})
    assert r["clase"] == "activity"


def test_r2_accomplishment_lectura_atelica():
    ev = detectar_evidencia(TOSIO_DURANTE, 1, _roles(TOSIO_DURANTE), None, {})
    r = aplicar_coerciones("accomplishment", ev, False, {})
    assert r["clase"] == "activity"
    assert "coercion=P4 lectura_atélica" in r["notas"]

    r_aa = aplicar_coerciones("active_accomplishment", ev, True, {})
    assert r_aa["clase"] == "activity"


def test_r2_no_dispara_con_terminativa_presente():
    """P4+P5 juntas: el evento SÍ culmina en esta lectura, R2 no coerciona."""
    ev = {"evidencias": [
        {"prueba": "P4", "trigger": "durante una hora", "rasgo": "durativo", "implica": {}},
        {"prueba": "P5", "trigger": "en una hora", "rasgo": "terminativo", "implica": {}},
    ]}
    r = aplicar_coerciones("accomplishment", ev, False, {})
    assert r["clase"] == "accomplishment"


def test_r3_p5_confirma_telico_solo_nota():
    ev = detectar_evidencia(CORRIO_EN_HORA, 1, _roles(CORRIO_EN_HORA), None, {})
    r = aplicar_coerciones("activity", ev, True, {})
    assert r["clase"] == "activity"
    assert "P5 confirma télico" in r["notas"]


def test_r4_conflictos_solo_notas():
    ev_p2 = detectar_evidencia(CORRIO_VIGOROSAMENTE, 1,
                               _roles(CORRIO_VIGOROSAMENTE), None, {})
    r = aplicar_coerciones("state", ev_p2, False, {})
    assert r["clase"] == "state"
    assert any("P2" in n for n in r["notas"])

    ev_p3 = detectar_evidencia(CORRIO_LENTAMENTE, 1,
                               _roles(CORRIO_LENTAMENTE), None, {})
    r = aplicar_coerciones("achievement", ev_p3, False, {})
    assert r["clase"] == "achievement"
    assert any("P3" in n for n in r["notas"])

    ev_p1 = {"evidencias": [{"prueba": "P1", "trigger": "estar+gerundio",
                             "rasgo": "progresivo", "implica": {}}]}
    r = aplicar_coerciones("achievement", ev_p1, False, {})
    assert r["clase"] == "achievement"
    assert any("P1" in n for n in r["notas"])


def test_avisos_apagados_no_generan_notas():
    ev_p2 = detectar_evidencia(CORRIO_VIGOROSAMENTE, 1,
                               _roles(CORRIO_VIGOROSAMENTE), None, {})
    r = aplicar_coerciones("state", ev_p2, False, {"avisos": False})
    assert r["notas"] == []


def test_coerciones_flags_individuales_off():
    ev = detectar_evidencia(TOSIO_DURANTE, 1, _roles(TOSIO_DURANTE), None, {})
    r = aplicar_coerciones("semelfactive", ev, False,
                           {"coerciones": {"semelfactive_iterativa": False}})
    assert r["clase"] == "semelfactive", "R1 desactivada por flag: sin cambio"


def test_sin_evidencia_no_dispara_nada():
    r = aplicar_coerciones("state", {"evidencias": []}, False, {})
    assert r["clase"] == "state" and r["notas"] == []


# ---------------------------------------------------------------------------
# Cuadro 1 y línea de coherencia
# ---------------------------------------------------------------------------
def test_cuadro_pruebas_cubre_las_seis_clases():
    for clase in ("state", "activity", "achievement", "semelfactive",
                  "accomplishment", "active_accomplishment"):
        assert clase in CUADRO_PRUEBAS
        assert set(CUADRO_PRUEBAS[clase]) == {"P1", "P2", "P3", "P4", "P5"}


def test_linea_coherencia_vacia_sin_evidencia():
    assert linea_coherencia("activity", {"evidencias": []}) == ""


def test_linea_coherencia_coherente_e_incoherente():
    ev_p4 = detectar_evidencia(TOSIO_DURANTE, 1, _roles(TOSIO_DURANTE), None, {})
    linea = linea_coherencia("activity", ev_p4)
    assert "P4" in linea and "✓coherente" in linea

    ev_p2 = detectar_evidencia(CORRIO_VIGOROSAMENTE, 1,
                               _roles(CORRIO_VIGOROSAMENTE), None, {})
    linea = linea_coherencia("state", ev_p2)
    assert "P2" in linea and "⚠conflicto" in linea


# ---------------------------------------------------------------------------
# Flag maestro: replica el condicional del mapper (rrg_ls_mapper.py) —
# con enabled=False no se llama a detectar_evidencia/aplicar_coerciones y
# verb_class/notas quedan intactos.
# ---------------------------------------------------------------------------
def test_flag_maestro_apagado_replica_mapper_no_op():
    pe_cfg = {"enabled": False}
    verb_class = "semelfactive"
    evidencia_estructural, coerciones_notas = {"evidencias": []}, []
    if pe_cfg.get("enabled", True):
        evidencia_estructural = detectar_evidencia(
            TOSIO_DURANTE, 1, _roles(TOSIO_DURANTE), None, pe_cfg)
        resultado = aplicar_coerciones(verb_class, evidencia_estructural,
                                       False, pe_cfg)
        verb_class = resultado["clase"]
        coerciones_notas = resultado["notas"]
    assert verb_class == "semelfactive"
    assert evidencia_estructural == {"evidencias": []}
    assert coerciones_notas == []


# ---------------------------------------------------------------------------
# Integración (Stanza + BERTIN) — solo con --slow / RUN_SLOW=1
# ---------------------------------------------------------------------------
def test_slow_integracion_mapper():
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    # R1: semelfactivo + durativa → lectura iterativa (era el caso fuga Semelfactive)
    ls = m.map_sentence_to_ls(nlp("tosió durante una hora").sentences[0])
    assert ls["ls_type"] == "activity", ls["ls_type"]
    assert any("semelfactive→activity_iterativa" in c for c in ls["coerciones"])

    # R1: semelfactivo + progresivo
    ls = m.map_sentence_to_ls(nlp("está tosiendo").sentences[0])
    assert ls["ls_type"] == "activity", ls["ls_type"]

    # R2: accomplishment/AA + durativa sin terminativa → atélico. Con sujeto
    # explícito el clasificador contextual predice active_accomplishment
    # (tel sube de 0.16 a 0.50) y R2 lo coerciona; en pro-drop ("leyó el
    # libro durante una hora") el propio contexto ya da activity sin
    # necesitar coerción — final correcto por dos vías distintas.
    ls = m.map_sentence_to_ls(
        nlp("Juan leyó el libro durante una hora").sentences[0])
    assert ls["ls_type"] == "activity", ls["ls_type"]
    assert any("lectura_atélica" in c for c in ls["coerciones"])

    ls = m.map_sentence_to_ls(nlp("leyó el libro durante una hora").sentences[0])
    assert ls["ls_type"] == "activity", ls["ls_type"]

    # estudié tres horas anoche: gate AA + P4 coherente (dos vías, misma conclusión)
    ls = m.map_sentence_to_ls(nlp("estudié tres horas anoche").sentences[0])
    assert ls["ls_type"] == "activity", ls["ls_type"]

    # sin evidencia → sin ruido en la nota
    ls = m.map_sentence_to_ls(nlp("Juan sabe la respuesta").sentences[0])
    assert ls["pruebas_evidencia"] == []
    assert "Pruebas:" not in ls["morph_note"]


def test_slow_flag_maestro_apagado_es_byte_identico():
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    frases = ["tosió durante una hora", "leyó el libro durante una hora",
             "Juan sabe la respuesta"]

    originales = [m.map_sentence_to_ls(nlp(f).sentences[0]) for f in frases]

    cfg = m._aspect_clf.config["pruebas_estructurales"]
    cfg["enabled"] = False
    try:
        apagados = [m.map_sentence_to_ls(nlp(f).sentences[0]) for f in frases]
    finally:
        cfg["enabled"] = True

    for o, a, f in zip(originales, apagados, frases):
        assert a["pruebas_evidencia"] == [] and a["coerciones"] == [], f
        # la garantía de identidad byte a byte solo aplica cuando NO hubo
        # evidencia estructural: si hubo evidencia sin coerción (p.ej. P4
        # detectada pero el clasificador ya daba activity), la línea de
        # coherencia igual se añade al morph_note con el flag activo, así
        # que apagar el flag SÍ cambia el note aunque `coerciones` esté vacío.
        if not o["pruebas_evidencia"]:
            assert a["ls_type"] == o["ls_type"], f
            assert a["ls_formal"] == o["ls_formal"], f
            assert a["morph_note"] == o["morph_note"], f


if not RUN_SLOW:
    try:
        import pytest
        test_slow_integracion_mapper = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_integracion_mapper)
        test_slow_flag_maestro_apagado_es_byte_identico = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_flag_maestro_apagado_es_byte_identico)
    except ImportError:
        pass


def main():
    rapidos = [
        test_p4_durante, test_p4_por, test_p4_duracion_desnuda,
        test_p5_terminativa_en_tiempo, test_p5_no_dispara_con_locativo,
        test_p4_no_dispara_con_articulo_definido_ni_distributivo,
        test_p1_progresivo, test_p2_adverbio_dinamico, test_p3_adverbio_ritmo,
        test_tiene_prueba_helper,
        test_r1_semelfactivo_iterativo_por_progresivo,
        test_r1_semelfactivo_iterativo_por_durativa,
        test_r2_accomplishment_lectura_atelica,
        test_r2_no_dispara_con_terminativa_presente,
        test_r3_p5_confirma_telico_solo_nota, test_r4_conflictos_solo_notas,
        test_avisos_apagados_no_generan_notas,
        test_coerciones_flags_individuales_off,
        test_sin_evidencia_no_dispara_nada,
        test_cuadro_pruebas_cubre_las_seis_clases,
        test_linea_coherencia_vacia_sin_evidencia,
        test_linea_coherencia_coherente_e_incoherente,
        test_flag_maestro_apagado_replica_mapper_no_op,
    ]
    tests = rapidos + ([test_slow_integracion_mapper,
                        test_slow_flag_maestro_apagado_es_byte_identico]
                       if RUN_SLOW else [])

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
