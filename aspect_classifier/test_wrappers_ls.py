"""Tests de wrappers_ls.py — Fase LINKING, Etapa L1b (reescrito en la Etapa
PERIFERIA, 2026-07-13 — ver prompt_opus48_periferia.md).

Ejecutar:
    python -m aspect_classifier.test_wrappers_ls          # puros
    python -m aspect_classifier.test_wrappers_ls --slow   # + Stanza/BERTIN

Compatible con pytest (los @slow requieren RUN_SLOW=1).
"""

import os
import sys

from .wrappers_ls import componer_wrappers

RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv

BASE_FORMAL = "do'(x, [correr'(x)])"
BASE_LEXICAL = "do'(Juan, [correr'(Juan)])"


def _peri(id_, text, deprel, tipo, estrato="centro", case=None, lemma=None, **extra):
    d = {"id": id_, "text": text, "deprel": deprel, "tipo": tipo, "estrato": estrato,
        "case": case, "lemma": lemma or text.lower()}
    d.update(extra)
    return d


# ---------------------------------------------------------------------------
# Locativos
# ---------------------------------------------------------------------------
def test_locativo_en_be_in():
    p = [_peri(1, "parque", "obl", "locativo", case="en")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "be-in'(parque, [do'(x, [correr'(x)])])"
    assert ap == [{"capa": "locativo", "id": 1, "trigger": "parque",
                  "pred": "be-in'", "aplicado": True, "estrato": "centro"}]


def test_locativo_default_be_at():
    p = [_peri(1, "algúnsitio", "obl", "locativo", case="hacia")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f.startswith("be-at'(algúnsitio, ")


def test_locativo_tabla_configurable():
    p = [_peri(1, "casa", "obl", "locativo", case="tras")]
    cfg = {"locativos": {"tras": "be-behind"}}
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, cfg)
    assert f.startswith("be-behind'(casa, ")


# ---------------------------------------------------------------------------
# Temporales bivalentes: durante cantidad-vs-evento
# ---------------------------------------------------------------------------
def test_durante_cantidad_de_tiempo_da_for():
    p = [_peri(1, "hora", "obl", "temporal", case="durante", lemma="hora")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "for'(hora, [do'(x, [correr'(x)])])"


def test_durante_evento_nombrado_da_during():
    p = [_peri(1, "clase", "obl", "temporal", case="durante", lemma="clase")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "during'(clase, [do'(x, [correr'(x)])])"


def test_por_duracion_da_for():
    p = [_peri(1, "horas", "obl", "temporal", case="por", lemma="hora")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f.startswith("for'(horas, ")


def test_temporales_simples_before_after_until_since():
    casos = {"antes": "before", "después": "after",
            "hasta": "until", "desde": "since"}
    for case, pred in casos.items():
        p = [_peri(1, "reunión", "obl", "temporal", case=case, lemma="reunión")]
        f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
        assert f.startswith(f"{pred}'(reunión, "), (case, f)


def test_en_punto_temporal_da_at():
    p = [_peri(1, "enero", "obl", "temporal", case="en", lemma="enero")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f.startswith("at'(enero, ")


def test_duracion_desnuda_cuantificada_da_for():
    p = [_peri(1, "horas", "obl", "temporal", lemma="hora", cuantificada=True)]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "for'(horas, [do'(x, [correr'(x)])])"


def test_duracion_desnuda_sin_cuantificada_no_envuelve():
    """Sin la anotación 'cuantificada' (que solo el mapper calcula con toks
    via P4), la duración desnuda cae al fallback de duración por defecto
    (for', conservador) -- Etapa PERIFERIA: NUNCA queda sin envolver."""
    p = [_peri(1, "horas", "obl", "temporal", lemma="hora")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "for'(horas, [do'(x, [correr'(x)])])"


# ---------------------------------------------------------------------------
# Adverbios monovalentes
# ---------------------------------------------------------------------------
def test_adverbio_monovalente_ayer():
    p = [_peri(1, "ayer", "advmod", "temporal", lemma="ayer")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "yesterday'([do'(x, [correr'(x)])])"


def test_adverbio_manana_solo_via_advmod():
    p = [_peri(1, "mañana", "advmod", "temporal", lemma="mañana")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f.startswith("tomorrow'(")


def test_adverbio_default_lema_espanol():
    p = [_peri(1, "anteayer", "advmod", "temporal", lemma="anteayer")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f.startswith("anteayer'(")


def test_ya_todavia_no_envuelven():
    for lemma in ("ya", "todavía"):
        p = [_peri(1, lemma, "advmod", "temporal", lemma=lemma)]
        f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
        assert f == BASE_FORMAL, lemma
        assert ap == [{"capa": "temporal", "id": 1, "trigger": lemma,
                      "pred": None, "aplicado": False, "razon": "sin_wrapper",
                      "estrato": "centro"}]


# ---------------------------------------------------------------------------
# Frecuencia (Etapa PERIFERIA: YA implementado -- antes "no_implementada")
# ---------------------------------------------------------------------------
def test_frecuencia_adverbio_se_envuelve():
    casos = {"siempre": "always", "nunca": "never"}
    for lemma, pred in casos.items():
        p = [_peri(1, lemma, "advmod", "frecuencia", lemma=lemma)]
        f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
        assert f == f"{pred}'([do'(x, [correr'(x)])])", (lemma, f)
        assert ap[0]["aplicado"] is True and ap[0]["pred"] == f"{pred}'"


def test_frecuencia_np_distributivo_every():
    """'los fines de semana' / 'todos los días' (ya tipados como frecuencia
    por nucleo_periferia): every'(x, [LS])."""
    p = [_peri(1, "fines", "obl", "frecuencia", lemma="fin")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "every'(fines, [do'(x, [correr'(x)])])"


# ---------------------------------------------------------------------------
# Manera (provisional) -- antes tipo "modo", renombrado a "manera"
# ---------------------------------------------------------------------------
def test_manera_provisional_monovalente():
    p = [_peri(1, "lentamente", "advmod", "manera", lemma="lentamente")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "lentamente'([do'(x, [correr'(x)])])"
    assert ap[0]["capa"] == "manera"


# ---------------------------------------------------------------------------
# Aspectual (NÚCLEO) -- nuevo en la Etapa PERIFERIA
# ---------------------------------------------------------------------------
def test_aspectual_completamente_nucleo():
    p = [_peri(1, "completamente", "advmod", "aspectual", estrato="nucleo",
               lemma="completamente")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "completely'([do'(x, [correr'(x)])])"
    assert ap[0]["estrato"] == "nucleo"


# ---------------------------------------------------------------------------
# Epistémico / razón / concesión / condición (CLÁUSULA) -- nuevos
# ---------------------------------------------------------------------------
def test_epistemico_probablemente_clausula():
    p = [_peri(1, "probablemente", "advmod", "epistemico", estrato="clausula",
               lemma="probablemente")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "probably'([do'(x, [correr'(x)])])"


def test_razon_debido_a_because_of():
    p = [_peri(1, "insultos", "obl", "razon", estrato="clausula",
               case="debido", lemma="insulto", frase="debido a")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "because-of'(insultos, [do'(x, [correr'(x)])])"


def test_razon_gracias_a_thanks_to():
    p = [_peri(1, "ayuda", "obl", "razon", estrato="clausula",
               case="gracias", lemma="ayuda", frase="gracias a")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "thanks-to'(ayuda, [do'(x, [correr'(x)])])"


def test_concesion_a_pesar_de_despite():
    p = [_peri(1, "lluvia", "obl", "concesion", estrato="clausula",
               case="a", lemma="lluvia", frase="a pesar de")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "despite'(lluvia, [do'(x, [correr'(x)])])"


def test_condicion_en_caso_de():
    p = [_peri(1, "lluvia", "obl", "condicion", estrato="clausula",
               case="en", lemma="lluvia", frase="en caso de")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "in-case-of'(lluvia, [do'(x, [correr'(x)])])"


# ---------------------------------------------------------------------------
# Genérico -- mata "otro" (antes NO se envolvía; ahora SIEMPRE se envuelve)
# ---------------------------------------------------------------------------
def test_generico_pp_preposicion_como_predicado():
    p = [_peri(1, "martillo", "obl", "generico", case="con", lemma="martillo")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "with'(martillo, [do'(x, [correr'(x)])])"


def test_generico_pp_sin_entrada_usa_la_preposicion_misma():
    p = [_peri(1, "silla", "obl", "generico", case="bajo la mesa", lemma="silla")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "bajo la mesa'(silla, [do'(x, [correr'(x)])])"


def test_generico_adverbio_sin_entrada_usa_el_lema():
    p = [_peri(1, "también", "advmod", "generico", lemma="también")]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == "también'([do'(x, [correr'(x)])])"


# ---------------------------------------------------------------------------
# Anidamiento — el ejemplo canónico de Julian (byte-exacto, sin cambios)
# ---------------------------------------------------------------------------
def test_anidamiento_completo_manera_locativo_temporal_adverbio():
    p = [
        _peri(1, "ayer", "advmod", "temporal", lemma="ayer"),
        _peri(2, "horas", "obl", "temporal", lemma="hora", cuantificada=True),
        _peri(3, "parque", "obl", "locativo", case="en", lemma="parque"),
    ]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == ("yesterday'(for'(horas, be-in'(parque, "
                "[do'(x, [correr'(x)])])))")
    capas = [w["capa"] for w in ap]
    assert capas == ["locativo", "temporal", "temporal"]


def test_anidamiento_con_manera():
    p = [
        _peri(1, "lentamente", "advmod", "manera", lemma="lentamente"),
        _peri(2, "parque", "obl", "locativo", case="en", lemma="parque"),
    ]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == ("be-in'(parque, lentamente'([do'(x, [correr'(x)])]))")
    assert [w["capa"] for w in ap] == ["manera", "locativo"]


def test_anidamiento_todos_los_estratos():
    """Aspectual (núcleo) → manera → locativo → temporal → frecuencia →
    razón → epistémico (cláusula, más externo) -- todos apilados."""
    p = [
        _peri(1, "completamente", "advmod", "aspectual", estrato="nucleo",
             lemma="completamente"),
        _peri(2, "lentamente", "advmod", "manera", lemma="lentamente"),
        _peri(3, "parque", "obl", "locativo", case="en", lemma="parque"),
        _peri(4, "hora", "obl", "temporal", case="durante", lemma="hora"),
        _peri(5, "siempre", "advmod", "frecuencia", lemma="siempre"),
        _peri(6, "insultos", "obl", "razon", estrato="clausula", case="debido",
             lemma="insulto", frase="debido a"),
        _peri(7, "probablemente", "advmod", "epistemico", estrato="clausula",
             lemma="probablemente"),
    ]
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, p, {})
    assert f == (
        "probably'(because-of'(insultos, always'(for'(hora, "
        "be-in'(parque, lentamente'(completely'([do'(x, [correr'(x)])])))))))"
    )
    assert [w["capa"] for w in ap] == ["aspectual", "manera", "locativo",
                                      "temporal", "frecuencia", "razon", "epistemico"]


# ---------------------------------------------------------------------------
# Sin evidencia → sin cambios
# ---------------------------------------------------------------------------
def test_sin_periferia_no_cambia_nada():
    f, l, ap = componer_wrappers(BASE_FORMAL, BASE_LEXICAL, [], {})
    assert f == BASE_FORMAL and l == BASE_LEXICAL and ap == []


# ---------------------------------------------------------------------------
# Integración (Stanza + BERTIN) — solo con --slow / RUN_SLOW=1
# ---------------------------------------------------------------------------
def test_slow_integracion_mapper():
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    # ejemplo canónico locativo
    ls = m.map_sentence_to_ls(nlp("Juan corrió en el parque").sentences[0])
    assert "be-in'(parque" in ls["ls_formal"]

    # durante evento nombrado → during'
    ls = m.map_sentence_to_ls(nlp("Juan rezó durante la clase").sentences[0])
    assert "during'(clase" in ls["ls_formal"]

    # por duración → for'
    ls = m.map_sentence_to_ls(nlp("Pedro corrió por tres horas").sentences[0])
    assert "for'(" in ls["ls_formal"]

    # duración desnuda cuantificada (P4) → for' (el bug histórico de Etapa 1,
    # ahora con wrapper)
    ls = m.map_sentence_to_ls(nlp("estudié tres horas anoche").sentences[0])
    assert "for'(horas" in ls["ls_formal"]
    assert "last.night'(" in ls["ls_formal"]
    assert ls["ls_type"] == "activity"

    # bug histórico de Julian: "los fines de semana" -- YA aparece en la EL
    ls = m.map_sentence_to_ls(nlp("Juan aprende español los fines de semana").sentences[0])
    assert "every'(" in ls["ls_formal"], ls["ls_formal"]

    # periferia sin envolver ya NO existe: cualquier oración con periferia
    # detectada trae al menos un wrapper.
    ls = m.map_sentence_to_ls(nlp("Juan sabe la respuesta").sentences[0])
    assert ls["wrappers"] == []
    assert "wrappers:" not in ls["morph_note"]


def test_slow_flag_maestro_apagado_es_byte_identico():
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    frases = ["Juan corrió en el parque", "Juan rezó durante la clase",
             "Juan sabe la respuesta"]

    originales = [m.map_sentence_to_ls(nlp(f).sentences[0]) for f in frases]

    cfg = m._aspect_clf.config["wrappers_ls"]
    cfg["enabled"] = False
    try:
        apagados = [m.map_sentence_to_ls(nlp(f).sentences[0]) for f in frases]
    finally:
        cfg["enabled"] = True

    for o, a, f in zip(originales, apagados, frases):
        assert a["wrappers"] == [], f
        if not o["wrappers"]:
            assert a["ls_formal"] == o["ls_formal"], f
            assert a["ls_lexical"] == o["ls_lexical"], f
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
        test_locativo_en_be_in, test_locativo_default_be_at,
        test_locativo_tabla_configurable,
        test_durante_cantidad_de_tiempo_da_for,
        test_durante_evento_nombrado_da_during,
        test_por_duracion_da_for,
        test_temporales_simples_before_after_until_since,
        test_en_punto_temporal_da_at,
        test_duracion_desnuda_cuantificada_da_for,
        test_duracion_desnuda_sin_cuantificada_no_envuelve,
        test_adverbio_monovalente_ayer, test_adverbio_manana_solo_via_advmod,
        test_adverbio_default_lema_espanol, test_ya_todavia_no_envuelven,
        test_frecuencia_adverbio_se_envuelve, test_frecuencia_np_distributivo_every,
        test_manera_provisional_monovalente,
        test_aspectual_completamente_nucleo,
        test_epistemico_probablemente_clausula,
        test_razon_debido_a_because_of, test_razon_gracias_a_thanks_to,
        test_concesion_a_pesar_de_despite, test_condicion_en_caso_de,
        test_generico_pp_preposicion_como_predicado,
        test_generico_pp_sin_entrada_usa_la_preposicion_misma,
        test_generico_adverbio_sin_entrada_usa_el_lema,
        test_anidamiento_completo_manera_locativo_temporal_adverbio,
        test_anidamiento_con_manera,
        test_anidamiento_todos_los_estratos,
        test_sin_periferia_no_cambia_nada,
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
