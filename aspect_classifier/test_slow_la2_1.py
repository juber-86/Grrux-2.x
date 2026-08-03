"""Integración real LA2.1. Ejecutar solo con RUN_SLOW=1 y modelos locales."""

import os

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_SLOW") != "1", reason="requiere Stanza y BERTIN"
)


@pytest.fixture(scope="module")
def nlp():
    import stanza

    recursos = "/home/jbj86/.cache/stanza/1.11.0/resources"
    return stanza.Pipeline(
        "es", processors="tokenize,mwt,pos,lemma,depparse", dir=recursos,
        download_method=None, verbose=False
    )


def _map(nlp, texto):
    import rrg_ls_mapper as mapper

    return mapper.map_sentence_to_ls(nlp(texto).sentences[0])


def test_slow_dianas_causativas_y_logro(nlp):
    se = _map(nlp, "Se venden casas.")
    assert se["causativo_clase_derivada"] == "realizacion_causativa"
    assert se["ls_lexical"] == "[do'(Ø, Ø)] CAUSE [BECOME vendido'(casas)]"
    assert se["linking"]["macropapeles"]["actor"] is None
    assert se["linking"]["macropapeles"]["undergoer"]["texto"] == "casas"
    assert se["linking"]["psa"]["macrorol"] == "Undergoer"
    assert se["linking"]["concordancia"]["ok"] is True

    romper = _map(nlp, "Juan rompió la ventana.")
    assert romper["causativo_clase_derivada"] == "logro_causativo"
    assert romper["ls_lexical"] == "[do'(Juan, Ø)] CAUSE [INGR roto'(ventana)]"
    assert romper["linking"]["macropapeles"]["actor"]["texto"] == "Juan"
    assert romper["linking"]["macropapeles"]["undergoer"]["texto"] == "ventana"
    assert romper["linking"]["psa"]["macrorol"] == "Actor"

    explotar = _map(nlp, "El globo explotó.")
    assert explotar["ls_type"] == "achievement"
    assert explotar["ls_lexical"] == "INGR explotar'(globo)"
    assert explotar["causativo"] is False
    assert "gate=obj_desnudo→Activity" not in explotar["morph_note"]
