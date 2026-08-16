"""Matriz transversal de la migración de variables RRG a x/y/z."""

import os

import pytest

from .misc_rrg import anotaciones_misc
from .rrg_variables import (RRG_VARIABLES, LegacyRRGNotationError,
                            canonical_variables, reject_legacy_notation)


RUN_SLOW = os.environ.get("RUN_SLOW") == "1"


def test_contrato_central_ordena_y_rechaza_legado_sin_convertir():
    assert RRG_VARIABLES == ("x", "y", "z")
    assert canonical_variables({"z": "tema", "x": "actor", "y": "receptor"}) == {
        "x": "actor", "y": "receptor", "z": "tema"
    }
    with pytest.raises(LegacyRRGNotationError, match="notación anterior"):
        reject_legacy_notation("do'(x9, [ver'(x9)])", context="EL")


def test_mapper_generico_pasiva_por_macrorrol_y_tercero_sin_licencia():
    from rrg_ls_mapper import _mapear_argumentos_genericos

    roles = {"core": [
        {"id": 2, "text": "pastel", "deprel": "nsubj:pass",
         "macropapel": "Undergoer"},
        {"id": 6, "text": "Juan", "deprel": "obl:agent",
         "macropapel": "Actor"},
    ], "agx": [], "actor_implicito": None}
    args, ids, meta, diagnosticos = _mapear_argumentos_genericos(roles)
    assert args == {"x": "Juan", "y": "pastel"}
    assert ids == {6: "x", 2: "y"}
    assert meta[0].startswith("x:Juan") and meta[1].startswith("y:pastel")
    assert diagnosticos == []

    roles["core"].append({"id": 7, "text": "extra", "deprel": "obl:arg",
                           "macropapel": "NMR"})
    args, ids, _meta, diagnosticos = _mapear_argumentos_genericos(roles)
    assert "z" not in args and 7 not in ids
    assert diagnosticos == [
        "argumento 'extra' (obl:arg) sin posición licenciada en la EL seleccionada"
    ]


def test_constructores_genericos_y_locativo_exactos():
    from rrg_ls_mapper import build_ls

    mono = build_ls("correr", {"x": "Juan"}, "activity")
    assert mono["formal"] == "do'(x, [correr'(x)])"
    bi = build_ls("comer", {"x": "Juan", "y": "pizza"}, "activity")
    assert bi["formal"] == "do'(x, [comer'(x, y)])"
    loc = build_ls("estar", {
        "x": "biblioteca", "y": "Juan",
        "_loc_info": {"subtype": "locative", "prep_pred": "be-in",
                      "loc_lex": "biblioteca"},
    }, "state")
    assert loc["formal"] == "be-in'(x, y)"
    assert [a["posicion"] for a in loc["estructura"][0]["args"]] == [
        "1_pred_xy", "2_pred_xy"
    ]


@pytest.mark.skipif(not RUN_SLOW, reason="requiere Stanza y modelos locales")
def test_matriz_semantica_end_to_end_xyz():
    import stanza
    import rrg_ls_mapper as mapper

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    def analizar(texto):
        return mapper.map_sentence_to_ls(nlp(texto).sentences[0])

    casos = {
        "Juan corrió": ("do'(x, [correr'(x)])", {"x": "Juan"}),
        "Juan comió pizza": ("do'(x, [comer'(x, y)])",
                              {"x": "Juan", "y": "pizza"}),
        "Juan sabe la respuesta": ("saber'(x, y)",
                                    {"x": "Juan", "y": "respuesta"}),
        "Juan está en la biblioteca": ("be-in'(x, y)",
                                         {"x": "biblioteca", "y": "Juan"}),
        "Juan rompió la ventana": ("[do'(x, Ø)] CAUSE [INGR roto'(y)]",
                                     {"x": "Juan", "y": "ventana"}),
        "El jarrón se rompió": ("[do'(Ø, Ø)] CAUSE [INGR roto'(y)]",
                                  {"x": "Ø", "y": "jarrón"}),
        "Juan le dio flores a María": (
            "[do'(x, Ø)] CAUSE [BECOME have'(y, z)]",
            {"x": "Juan", "y": "María", "z": "flores"}),
            "Juan compró un regalo para María": (
                "[[do'(x, Ø)] CAUSE [BECOME have'(x, z)]] PURP [BECOME have'(y, z)]",
                {"x": "Juan", "y": "María", "z": "regalo"}),
        "Le dije la verdad": ("do'(x, [decir.to.(y)'(x, z)])",
                               {"x": "1sg", "y": "3sg", "z": "verdad"}),
        "Comí pizza": ("do'(x, [comer'(x, y)])",
                         {"x": "1sg", "y": "pizza"}),
    }
    for oracion, (formal, variables) in casos.items():
        ls = analizar(oracion)
        assert ls["ls_formal"] == formal, oracion
        assert ls["variables"] == variables, oracion
        assert not ls["diagnosticos_analisis"], oracion

    pasiva = analizar("El pastel fue comido por Juan")
    assert pasiva["variables"] == {"x": "Juan", "y": "pastel"}
    assert pasiva["id_a_var"] == {6: "x", 2: "y"}

    locativo = analizar("Juan está en la biblioteca")
    misc = anotaciones_misc(locativo)
    assert misc[5]["RRGVar"] == "x" and misc[1]["RRGVar"] == "y"

    impersonal = analizar("Llueve")
    assert impersonal["variables"] == {}
    assert impersonal["id_a_var"] == {}
    assert impersonal["ls_formal"] == "llover'"
