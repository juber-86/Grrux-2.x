"""Tests de ditransitivas.py — Fase LINKING, Etapa L2.5.

Ejecutar:
    python -m aspect_classifier.test_ditransitivas          # puros
    python -m aspect_classifier.test_ditransitivas --slow   # + Stanza/BERTIN

Compatible con pytest (los @slow requieren RUN_SLOW=1).
"""

import os
import sys
import tempfile
from pathlib import Path

from .ditransitivas import (cargar_lexicon, construir_ditransitiva,
                            detectar_trigger, elegir_plantilla, log_candidato)
from .nucleo_periferia import analizar_roles

RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv
LEXICON = cargar_lexicon()


def _tok(id_, text, lemma, upos, deprel, head, feats=""):
    return {"id": id_, "text": text, "lemma": lemma, "upos": upos,
            "deprel": deprel, "head": head, "feats": feats}


# "Juan le dio un regalo a María" (doblado)
DIO_REGALO_MARIA = [
    _tok(1, "Juan", "Juan", "PROPN", "nsubj", 3),
    _tok(2, "le", "él", "PRON", "obl:arg", 3, "Case=Dat|Number=Sing|Person=3"),
    _tok(3, "dio", "dar", "VERB", "root", 0,
        "Mood=Ind|Number=Sing|Person=3|Tense=Past"),
    _tok(4, "un", "uno", "DET", "det", 5),
    _tok(5, "regalo", "regalo", "NOUN", "obj", 3),
    _tok(6, "a", "a", "ADP", "case", 7),
    _tok(7, "María", "María", "PROPN", "obl:arg", 3),
]

# misma estructura con "compró"/comprar (benefactiva en el léxico)
COMPRO_REGALO_MARIA = [t if t["id"] != 3 else
                       _tok(3, "compró", "comprar", "VERB", "root", 0,
                            "Mood=Ind|Number=Sing|Person=3|Tense=Past")
                       for t in DIO_REGALO_MARIA]

# "compró un regalo para María" (pro-drop, sin dativo, para en periferia)
COMPRO_PARA_MARIA = [
    _tok(1, "compró", "comprar", "VERB", "root", 0,
        "Mood=Ind|Number=Sing|Person=3|Tense=Past"),
    _tok(2, "un", "uno", "DET", "det", 3),
    _tok(3, "regalo", "regalo", "NOUN", "obj", 1),
    _tok(4, "para", "para", "ADP", "case", 5),
    _tok(5, "María", "María", "PROPN", "obl", 1),
]

# "compró un regalo" (sin dativo ni para)
COMPRO_SIN_NADA = COMPRO_PARA_MARIA[:3]

# "Le dije la verdad" (clítico solo, sin doblar)
DIJE_VERDAD = [
    _tok(1, "Le", "él", "PRON", "obl:arg", 2, "Case=Dat|Number=Sing|Person=3"),
    _tok(2, "dije", "decir", "VERB", "root", 0,
        "Mood=Ind|Number=Sing|Person=1|Tense=Past"),
    _tok(3, "la", "el", "DET", "det", 4),
    _tok(4, "verdad", "verdad", "NOUN", "obj", 2),
]

# "le dije que viniera" (z = ccomp)
DIJE_QUE_VINIERA = [
    _tok(1, "le", "él", "PRON", "obl:arg", 2, "Case=Dat|Number=Sing|Person=3"),
    _tok(2, "dije", "decir", "VERB", "root", 0,
        "Mood=Ind|Number=Sing|Person=1|Tense=Past"),
    _tok(3, "que", "que", "SCONJ", "mark", 4),
    _tok(4, "viniera", "venir", "VERB", "ccomp", 2),
]


def _roles(toks, root_id):
    return analizar_roles(toks, root_id, {})


# ---------------------------------------------------------------------------
# Léxico
# ---------------------------------------------------------------------------
def test_lexicon_carga_54_verbos():
    # L4: dinámico a propósito -- Julian cura verbos_ditransitivos.xlsx
    # activamente (54 -> 122 y sigue creciendo); un conteo exacto rompe este
    # test cada vez que añade filas. Se comprueban invariantes estructurales,
    # no un tamaño fijo.
    assert len(LEXICON) >= 54
    for lema, entry in LEXICON.items():
        assert set(entry.keys()) == {"plantilla", "ambiguo", "notas"}, lema
        assert entry["plantilla"] in ("transferencia", "benefactiva", "comunicacion"), lema
        assert isinstance(entry["ambiguo"], bool), lema

    assert LEXICON["dar"] == {"plantilla": "transferencia", "ambiguo": False, "notas": ""}
    assert LEXICON["comprar"]["plantilla"] == "benefactiva"
    assert LEXICON["decir"]["plantilla"] == "comunicacion"
    assert LEXICON["escribir"]["ambiguo"] is True

    import pandas as pd
    from .ditransitivas import LEXICON_XLSX
    lemas = pd.read_excel(LEXICON_XLSX)["lema"].astype(str).str.strip().str.lower()
    duplicados = lemas[lemas.duplicated()].tolist()
    assert not duplicados, f"lemas duplicados en {LEXICON_XLSX.name}: {duplicados}"


# ---------------------------------------------------------------------------
# Transferencia
# ---------------------------------------------------------------------------
def test_transferencia_el_exacta_y_un_solo_x3():
    r = construir_ditransitiva(_roles(DIO_REGALO_MARIA, 3), "dar", LEXICON, {})
    assert r["plantilla"] == "transferencia"
    assert r["clase"] == "accomplishment"
    assert r["formal"] == "[do'(x1, Ø)] CAUSE [BECOME have'(x3, x2)]"
    assert r["lexical"] == "[do'(Juan, Ø)] CAUSE [BECOME have'(María, regalo)]"
    assert r["roles_tematicos"] == {1: "Efectuador", 5: "Tema", 7: "Poseedor"}
    # UN solo x3: el clítico "le" (id=2) nunca aparece como variable propia
    assert 2 not in r["id_a_var"]
    assert list(r["id_a_var"].values()).count("x3") == 1


# ---------------------------------------------------------------------------
# Benefactiva (PURP)
# ---------------------------------------------------------------------------
def test_benefactiva_con_dativo_purp():
    r = construir_ditransitiva(_roles(COMPRO_REGALO_MARIA, 3), "comprar", LEXICON, {})
    assert r["plantilla"] == "benefactiva"
    assert r["trigger"] == "dativo"
    assert r["formal"] == "[[do'(x1, Ø)] CAUSE [BECOME have'(x1, x2)]] PURP [have'(x3, x2)]"
    assert r["lexical"] == ("[[do'(Juan, Ø)] CAUSE [BECOME have'(Juan, regalo)]]"
                            " PURP [have'(María, regalo)]")


def test_benefactiva_sin_clitico_asciende_beneficiario():
    roles = _roles(COMPRO_PARA_MARIA, 1)
    assert any(p["case"] == "para" for p in roles["periferia"]), "precondición: para en periferia"
    r = construir_ditransitiva(roles, "comprar", LEXICON, {"benefactiva_para": True})
    assert r["trigger"] == "benefactivo_para"
    assert r["plantilla"] == "benefactiva"
    assert r["lexical"] == ("[[do'(3sg, Ø)] CAUSE [BECOME have'(3sg, regalo)]]"
                            " PURP [have'(María, regalo)]")
    assert r["y_periferia_id"] == 5   # id de "María" en periferia — el mapper la remueve de ahí


def test_benefactiva_para_desactivable_por_config():
    roles = _roles(COMPRO_PARA_MARIA, 1)
    r = construir_ditransitiva(roles, "comprar", LEXICON, {"benefactiva_para": False})
    assert r is None


def test_sin_dativo_ni_para_no_dispara():
    roles = _roles(COMPRO_SIN_NADA, 1)
    r = construir_ditransitiva(roles, "comprar", LEXICON, {})
    assert r is None


# ---------------------------------------------------------------------------
# Comunicación
# ---------------------------------------------------------------------------
def test_comunicacion_clitico_solo():
    r = construir_ditransitiva(_roles(DIJE_VERDAD, 2), "decir", LEXICON, {})
    assert r["plantilla"] == "comunicacion"
    assert r["clase"] == "activity"
    assert r["formal"] == "do'(x1, [decir.to.(3sg)'(x1, x2)])"
    assert r["lexical"] == "do'(1sg, [decir.to.(3sg)'(1sg, verdad)])"


def test_comunicacion_z_es_ccomp():
    r = construir_ditransitiva(_roles(DIJE_QUE_VINIERA, 2), "decir", LEXICON, {})
    assert r["lexical"] == "do'(1sg, [decir.to.(3sg)'(1sg, viniera)])"
    assert "x2:viniera,ccomp,Tema(Contenido)" in r["arg_meta_parts"]


# ---------------------------------------------------------------------------
# Verbo desconocido / ambiguo → default + log
# ---------------------------------------------------------------------------
def test_verbo_desconocido_default_transferencia():
    roles = _roles(DIO_REGALO_MARIA, 3)
    r = construir_ditransitiva(roles, "garabatear", LEXICON, {})
    assert r["plantilla"] == "transferencia"
    assert r["source"] == "default"
    assert r["ambiguo"] is False


def test_verbo_ambiguo_usa_su_default_y_se_marca():
    roles = _roles(DIO_REGALO_MARIA, 3)
    r = construir_ditransitiva(roles, "escribir", LEXICON, {})
    assert r["plantilla"] == "comunicacion"   # el default indicado en el xlsx
    assert r["source"] == "lexico"
    assert r["ambiguo"] is True


def test_default_plantilla_configurable():
    roles = _roles(DIO_REGALO_MARIA, 3)
    r = construir_ditransitiva(roles, "garabatear", LEXICON,
                               {"default_plantilla": "comunicacion"})
    assert r["plantilla"] == "comunicacion"


def test_log_candidato_dedupe():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "cand.csv"
        log_candidato("garabatear", "Juan le garabateó algo a María", "transferencia", p)
        log_candidato("garabatear", "Juan le garabateó algo a María", "transferencia", p)
        lineas = p.read_text(encoding="utf-8").strip().splitlines()
        assert len(lineas) == 2   # header + 1 (dedupe funcionó)
        assert lineas[0] == "lema,oracion,plantilla"


# ---------------------------------------------------------------------------
# detectar_trigger / elegir_plantilla en aislado
# ---------------------------------------------------------------------------
def test_detectar_trigger_tipo_dativo():
    t = detectar_trigger(_roles(DIO_REGALO_MARIA, 3), "dar", LEXICON, {})
    assert t["disparo"] and t["tipo"] == "dativo"


def test_detectar_trigger_sin_disparo():
    t = detectar_trigger(_roles(COMPRO_SIN_NADA, 1), "comprar", LEXICON, {})
    assert not t["disparo"] and t["tipo"] is None


def test_elegir_plantilla_benefactivo_para_siempre_benefactiva():
    p = elegir_plantilla("cualquierverbo", "benefactivo_para", LEXICON, {})
    assert p == {"plantilla": "benefactiva", "source": "lexico", "ambiguo": False}


# ---------------------------------------------------------------------------
# Flag maestro: replica el condicional del mapper (rrg_ls_mapper.py)
# ---------------------------------------------------------------------------
def test_flag_maestro_apagado_replica_mapper_no_op():
    ditrans_cfg = {"enabled": False}
    ditrans = None
    if ditrans_cfg.get("enabled", True):
        ditrans = construir_ditransitiva(_roles(DIO_REGALO_MARIA, 3), "dar",
                                         LEXICON, ditrans_cfg)
    assert ditrans is None


# ---------------------------------------------------------------------------
# Integración (Stanza + BERTIN) — solo con --slow / RUN_SLOW=1
# ---------------------------------------------------------------------------
def test_slow_integracion_mapper():
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    ls = m.map_sentence_to_ls(nlp("Juan le dio un regalo a María").sentences[0])
    assert ls["ls_type"] == "accomplishment"
    assert ls["ls_formal"] == "[do'(x1, Ø)] CAUSE [BECOME have'(x3, x2)]"
    assert ls["ditransitiva"] == {"plantilla": "transferencia", "trigger": "dativo",
                                  "source": "lexico", "ambiguo": False}
    assert not ls["causativo"], "no debe pasar también por la cascada de causatividad"

    ls = m.map_sentence_to_ls(nlp("Juan le compró un regalo a María").sentences[0])
    assert "PURP" in ls["ls_formal"]

    ls = m.map_sentence_to_ls(nlp("compró un regalo para María").sentences[0])
    assert "PURP" in ls["ls_formal"]
    assert "Periferia:" not in ls["args_map"], "María asciende, no debe listarse también en periferia"

    ls = m.map_sentence_to_ls(nlp("compró un regalo").sentences[0])
    assert ls["ditransitiva"] is None
    assert "PURP" not in ls["ls_formal"]

    ls = m.map_sentence_to_ls(nlp("Le dije la verdad").sentences[0])
    assert ls["ls_formal"] == "do'(x1, [decir.to.(3sg)'(x1, x2)])"

    # wrappers componen POR FUERA de la plantilla ditransitiva
    ls = m.map_sentence_to_ls(nlp("Ayer le dio flores a María en el parque").sentences[0])
    assert ls["ls_formal"] == ("yesterday'(be-in'(parque, "
                               "[[do'(x1, Ø)] CAUSE [BECOME have'(x3, x2)]]))")

    # MISC: RRGVar=x3 + RRGThemRel=Poseedor para María (L3: renombrado desde
    # "Recipiente", ver ditransitivas._ROLES_POR_PLANTILLA)
    from aspect_classifier.misc_rrg import anotaciones_misc
    ls = m.map_sentence_to_ls(nlp("Juan le dio un regalo a María").sentences[0])
    anot = anotaciones_misc(ls)
    maria_id = next(k for k, v in ls["roles_tematicos"].items() if v == "Poseedor")
    assert anot[maria_id]["RRGVar"] == "x3"
    assert anot[maria_id]["RRGThemRel"] == "Poseedor"

    # L3: ud2rrg YA convierte "le" (obl:arg ahora en el dispatch, AGX bajo
    # NUC) — antes de L3 esta oración fallaba entera (ver CHECKPOINT_L0_L2).
    import gruxx_ai1 as g
    res = g.procesar_oracion(nlp, "Juan le dio un regalo a María")
    assert "Convertidas: 1 | Fallidas: 0" in res["stdout"]
    arbol = g._extraer_arbol(res["stdout"])
    assert "AGX" in arbol


def test_slow_26_dianas_casi_todas_sin_regresion():
    """Las 26 frases del informe de wrappers (L0-L2): el prompt asume que
    "ninguna es ditransitiva", pero DOS (agregadas en L1d para probar
    wrappers, no dianas históricas) sí tienen dativo y SÍ deben disparar
    — verificado, es el fix deseado, no una regresión:
      - "Le compró un regalo a María": comprar+dativo → benefactiva PURP
        (cambia de `do'(3sg,[comprar'(3sg,regalo)]) & INGR consumed'(regalo)`,
        el mismo patrón de bug del reporte original, solo que con "comprar").
      - "Le dije la verdad": decir+dativo → comunicación simple (YA es el
        caso de prueba explícito de test_slow_integracion_mapper arriba).
    Se separan de la aserción "sin cambio" y se verifica que SÍ disparan
    correctamente. Las otras 24 no deben moverse."""
    import stanza
    import rrg_ls_mapper as m

    from .informe_wrappers_dianas import DIANAS, NUEVAS_WRAPPERS

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    excepciones = {
        "Le compró un regalo a María": "benefactiva",
        "Le dije la verdad": "comunicacion",
    }
    todas = DIANAS + NUEVAS_WRAPPERS

    for frase, plantilla_esperada in excepciones.items():
        ls = m.map_sentence_to_ls(nlp(frase).sentences[0])
        assert ls["ditransitiva"] is not None, frase
        assert ls["ditransitiva"]["plantilla"] == plantilla_esperada, frase

    for frase in todas:
        if frase in excepciones:
            continue
        ls = m.map_sentence_to_ls(nlp(frase).sentences[0])
        assert ls["ditransitiva"] is None, f"{frase} no debería disparar ditransitivas"


if not RUN_SLOW:
    try:
        import pytest
        test_slow_integracion_mapper = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_integracion_mapper)
        test_slow_26_dianas_casi_todas_sin_regresion = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_26_dianas_casi_todas_sin_regresion)
    except ImportError:
        pass


def main():
    rapidos = [
        test_lexicon_carga_54_verbos,
        test_transferencia_el_exacta_y_un_solo_x3,
        test_benefactiva_con_dativo_purp,
        test_benefactiva_sin_clitico_asciende_beneficiario,
        test_benefactiva_para_desactivable_por_config,
        test_sin_dativo_ni_para_no_dispara,
        test_comunicacion_clitico_solo, test_comunicacion_z_es_ccomp,
        test_verbo_desconocido_default_transferencia,
        test_verbo_ambiguo_usa_su_default_y_se_marca,
        test_default_plantilla_configurable,
        test_log_candidato_dedupe,
        test_detectar_trigger_tipo_dativo, test_detectar_trigger_sin_disparo,
        test_elegir_plantilla_benefactivo_para_siempre_benefactiva,
        test_flag_maestro_apagado_replica_mapper_no_op,
    ]
    tests = rapidos + ([test_slow_integracion_mapper, test_slow_26_dianas_casi_todas_sin_regresion]
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
