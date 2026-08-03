"""Tests de operadores.py — Etapa OPERATORS (ver prompt_OPERATORS.md).

Ejecutar:
    python -m aspect_classifier.test_operadores          # puros (toks a mano)
    python -m aspect_classifier.test_operadores --slow   # + Stanza end-to-end

Compatible con pytest (los @slow requieren RUN_SLOW=1).

Los tests fríos construyen los `toks` A MANO con los rasgos que Stanza
produce REALMENTE (verificados con una sonda sobre el pipeline español en
esta etapa) — así el test no depende del modelo pero tampoco inventa parses
que el pipeline nunca vería.
"""

import os
import sys

from .operadores import (detectar_operadores, envolver_ls, etiqueta,
                         linea_operadores, perifrasis_no_cubiertas,
                         verbo_finito)

RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv

CFG = {
    "enabled": True,
    "modales": {"deber": "OBLG", "poder": "ABIL"},
    "perifrasis_tener_que": True,
    "perifrasis_vigiladas": ["soler", "querer", "ir"],
    "adv_epistemicos_irreal": ["quizá", "tal vez", "probablemente", "seguramente"],
    "adv_epistemicos_real": ["ciertamente", "sin duda"],
}


def _t(id_, text, lemma, upos, deprel, head, feats=""):
    return {"id": id_, "text": text, "lemma": lemma, "upos": upos,
            "deprel": deprel, "head": head, "feats": feats}


# ---------------------------------------------------------------------------
# Ejemplo canónico 2.26, en español: "¿Ha estado llorando Juan?"
# ---------------------------------------------------------------------------
def _toks_ha_estado_llorando():
    """Parse REAL de Stanza (sonda de esta etapa): la raíz es el gerundio
    'llorando' (sin Tense) y el tiempo vive en el auxiliar finito 'Ha'."""
    return [
        _t(1, "¿", "¿", "PUNCT", "punct", 4, "PunctSide=Ini|PunctType=Qest"),
        _t(2, "Ha", "haber", "AUX", "aux", 4,
           "Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin"),
        _t(3, "estado", "estar", "AUX", "aux", 4,
           "Gender=Masc|Number=Sing|Tense=Past|VerbForm=Part"),
        _t(4, "llorando", "llorar", "VERB", "root", 0, "VerbForm=Ger"),
        _t(5, "Juan", "Juan", "PROPN", "nsubj", 4, ""),
        _t(6, "?", "?", "PUNCT", "punct", 4, "PunctSide=Fin|PunctType=Qest"),
    ]


def test_canonico_2_26_deteccion():
    ops = detectar_operadores(_toks_ha_estado_llorando(), 4, "complet", CFG)
    assert list(ops) == ["IF", "TNS", "ASP"], list(ops)
    assert ops["IF"]["valor"] == "INT"
    assert ops["TNS"]["valor"] == "PRES"      # del auxiliar finito, no del gerundio
    assert ops["ASP"]["valor"] == "PERF PROG"  # combinados: haber + estar-gerundio


def test_canonico_2_26_envuelta_byte_a_byte():
    """El ejemplo 2.26 del libro, en español, carácter por carácter."""
    ops = detectar_operadores(_toks_ha_estado_llorando(), 4, "complet", CFG)
    envuelta = envolver_ls("do'(Juan, [llorar'(Juan)])", ops)
    assert envuelta == ("⟨IF INT ⟨TNS PRES ⟨ASP PERF PROG "
                        "⟨do'(Juan, [llorar'(Juan)])⟩⟩⟩⟩"), envuelta


def test_canonico_estratos_y_origen():
    ops = detectar_operadores(_toks_ha_estado_llorando(), 4, "complet", CFG)
    assert ops["TNS"]["estrato"] == "clausular"
    assert ops["ASP"]["estrato"] == "nuclear"
    assert "Ha" in ops["TNS"]["origen"]
    assert "estado" in ops["ASP"]["origen"]


# ---------------------------------------------------------------------------
# TNS / ASP
# ---------------------------------------------------------------------------
def test_estudie_declarativa_pasado():
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 2, ""),
        _t(2, "estudió", "estudiar", "VERB", "root", 0,
           "Mood=Ind|Number=Sing|Person=3|Tense=Past|VerbForm=Fin"),
        _t(3, ".", ".", "PUNCT", "punct", 2, "PunctType=Peri"),
    ]
    ops = detectar_operadores(toks, 2, None, CFG)
    assert ops["IF"]["valor"] == "DEC"
    assert ops["TNS"]["valor"] == "PAST"
    assert "ASP" not in ops
    assert linea_operadores(ops) == "IF=DEC · TNS=PAST"


def test_imperfecto_es_past_mas_impf():
    """Dos operadores de un solo feat morfológico (Tense=Imp)."""
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 2, ""),
        _t(2, "corría", "correr", "VERB", "root", 0,
           "Mood=Ind|Number=Sing|Person=3|Tense=Imp|VerbForm=Fin"),
    ]
    ops = detectar_operadores(toks, 2, None, CFG)
    assert ops["TNS"]["valor"] == "PAST"
    assert ops["ASP"]["valor"] == "IMPF"


def test_pluscuamperfecto_perf_impf():
    """'había estudiado': el participio raíz lleva Tense=Past pero el tiempo
    real está en el auxiliar finito (Tense=Imp) — PERF + IMPF, TNS PAST."""
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 3, ""),
        _t(2, "había", "haber", "AUX", "aux", 3,
           "Mood=Ind|Number=Sing|Person=3|Tense=Imp|VerbForm=Fin"),
        _t(3, "estudiado", "estudiar", "VERB", "root", 0,
           "Gender=Masc|Number=Sing|Tense=Past|VerbForm=Part"),
    ]
    ops = detectar_operadores(toks, 3, "complet", CFG)
    assert ops["TNS"]["valor"] == "PAST"
    assert ops["ASP"]["valor"] == "PERF IMPF"


def test_condicional_sin_tns_y_con_sta_irr():
    """'habría estudiado': el condicional NO lleva Tense → TNS se omite; el
    participio raíz (Tense=Past) no debe colarse como tiempo de la cláusula."""
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 3, ""),
        _t(2, "habría", "haber", "AUX", "aux", 3,
           "Mood=Cnd|Number=Sing|Person=3|VerbForm=Fin"),
        _t(3, "estudiado", "estudiar", "VERB", "root", 0,
           "Gender=Masc|Number=Sing|Tense=Past|VerbForm=Part"),
    ]
    ops = detectar_operadores(toks, 3, "complet", CFG)
    assert "TNS" not in ops, ops.get("TNS")
    assert ops["STA"]["valor"] == "IRR"
    assert ops["ASP"]["valor"] == "PERF"


def test_futuro():
    toks = [_t(1, "Juan", "Juan", "PROPN", "nsubj", 2, ""),
            _t(2, "estudiará", "estudiar", "VERB", "root", 0,
               "Mood=Ind|Number=Sing|Person=3|Tense=Fut|VerbForm=Fin")]
    assert detectar_operadores(toks, 2, None, CFG)["TNS"]["valor"] == "FUT"


def test_verbo_finito_es_el_auxiliar_cuando_la_raiz_no_lo_es():
    toks = _toks_ha_estado_llorando()
    assert verbo_finito(toks, 4)["text"] == "Ha"


# ---------------------------------------------------------------------------
# NEG
# ---------------------------------------------------------------------------
def test_negacion():
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 3, ""),
        _t(2, "no", "no", "ADV", "advmod", 3, "Polarity=Neg"),
        _t(3, "corrió", "correr", "VERB", "root", 0,
           "Mood=Ind|Number=Sing|Person=3|Tense=Past|VerbForm=Fin"),
    ]
    ops = detectar_operadores(toks, 3, None, CFG)
    assert ops["NEG"]["valor"] == "NEG"
    assert ops["NEG"]["estrato"] == "nuclear"


def test_neg_no_se_duplica_en_la_etiqueta():
    """Van Valin escribe ⟨NEG …⟩, nunca ⟨NEG NEG …⟩."""
    assert etiqueta("NEG", {"valor": "NEG"}) == "NEG"
    ops = {"NEG": {"valor": "NEG", "estrato": "nuclear", "origen": "x"}}
    assert envolver_ls("correr'(Juan)", ops) == "⟨NEG ⟨correr'(Juan)⟩⟩"


# ---------------------------------------------------------------------------
# MOD
# ---------------------------------------------------------------------------
def test_modal_deber_oblg():
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 3, ""),
        _t(2, "debe", "deber", "AUX", "aux", 3,
           "Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin"),
        _t(3, "estudiar", "estudiar", "VERB", "root", 0, "VerbForm=Inf"),
    ]
    ops = detectar_operadores(toks, 3, None, CFG)
    assert ops["MOD"]["valor"] == "OBLG"
    assert ops["MOD"]["estrato"] == "central"
    assert ops["TNS"]["valor"] == "PRES"   # el tiempo lo lleva el modal finito


def test_modal_poder_abil():
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 3, ""),
        _t(2, "puede", "poder", "AUX", "aux", 3,
           "Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin"),
        _t(3, "correr", "correr", "VERB", "root", 0, "VerbForm=Inf"),
    ]
    assert detectar_operadores(toks, 3, None, CFG)["MOD"]["valor"] == "ABIL"


def test_modal_deberia_es_oblg_mas_irr():
    """'debería estudiar' = obligación (MOD) + irrealis (STA), Mood=Cnd."""
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 3, ""),
        _t(2, "debería", "deber", "AUX", "aux", 3,
           "Mood=Cnd|Number=Sing|Person=3|VerbForm=Fin"),
        _t(3, "estudiar", "estudiar", "VERB", "root", 0, "VerbForm=Inf"),
    ]
    ops = detectar_operadores(toks, 3, None, CFG)
    assert ops["MOD"]["valor"] == "OBLG"
    assert ops["STA"]["valor"] == "IRR"


def test_tener_que_patron_propio():
    """Stanza NO analiza 'tener que' como auxiliar: la raíz es 'tiene' y el
    infinitivo cuelga como `conj` con su propio `cc` ('que')."""
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 4, ""),
        _t(2, "tiene", "tener", "VERB", "root", 0,
           "Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin"),
        _t(3, "que", "que", "SCONJ", "cc", 4, ""),
        _t(4, "estudiar", "estudiar", "VERB", "conj", 2, "VerbForm=Inf"),
    ]
    ops = detectar_operadores(toks, 2, None, CFG)
    assert ops["MOD"]["valor"] == "OBLG"
    assert "tener que" in ops["MOD"]["origen"]


def test_perifrasis_vigiladas_se_reportan_sin_cambiar_nada():
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 3, ""),
        _t(2, "suele", "soler", "AUX", "aux", 3,
           "Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin"),
        _t(3, "correr", "correr", "VERB", "root", 0, "VerbForm=Inf"),
    ]
    assert "MOD" not in detectar_operadores(toks, 3, None, CFG)
    no_cubiertas = perifrasis_no_cubiertas(toks, 3, CFG)
    assert [p["lema"] for p in no_cubiertas] == ["soler"]


def test_perifrasis_vigilada_como_raiz_con_xcomp():
    """Cómo parsea Stanza DE VERDAD 'suele correr': 'suele' es la RAÍZ y el
    infinitivo cuelga como `xcomp`. Sin este patrón la lista de vigiladas
    quedaba inerte (no se logueaba nunca nada)."""
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 2, ""),
        _t(2, "suele", "soler", "VERB", "root", 0,
           "Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin"),
        _t(3, "correr", "correr", "VERB", "xcomp", 2, "VerbForm=Inf"),
    ]
    no_cubiertas = perifrasis_no_cubiertas(toks, 2, CFG)
    assert [p["lema"] for p in no_cubiertas] == ["soler"]
    assert no_cubiertas[0]["deprel"] == "root+xcomp"


def test_verbo_vigilado_sin_infinitivo_no_se_loguea():
    """'Juan va al parque' no es perífrasis: sin xcomp infinitivo, no hay
    nada que reportar (el logueo debe ser señal, no ruido)."""
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 2, ""),
        _t(2, "va", "ir", "VERB", "root", 0,
           "Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin"),
        _t(3, "parque", "parque", "NOUN", "obl", 2, "Gender=Masc|Number=Sing"),
    ]
    assert perifrasis_no_cubiertas(toks, 2, CFG) == []


# ---------------------------------------------------------------------------
# STA
# ---------------------------------------------------------------------------
def test_quiza_subjuntivo_irr():
    toks = [
        _t(1, "Quizá", "quizá", "ADV", "advmod", 2, ""),
        _t(2, "venga", "venir", "VERB", "root", 0,
           "Mood=Sub|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin"),
        _t(3, "María", "María", "PROPN", "nsubj", 2, ""),
    ]
    ops = detectar_operadores(toks, 2, None, CFG)
    assert ops["STA"]["valor"] == "IRR"
    assert "Mood=Sub" in ops["STA"]["origen"]
    assert "quizá" in ops["STA"]["origen"]


def test_tal_vez_es_multipalabra_fixed():
    """'tal vez' parsea como NOUN('tal') + `fixed`('vez'), no un solo token."""
    toks = [
        _t(1, "Tal", "tal", "NOUN", "advmod", 4, ""),
        _t(2, "vez", "vez", "NOUN", "fixed", 1, ""),
        _t(3, "Juan", "Juan", "PROPN", "nsubj", 4, ""),
        _t(4, "estudie", "estudiar", "VERB", "root", 0,
           "Mood=Sub|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin"),
    ]
    ops = detectar_operadores(toks, 4, None, CFG)
    assert "tal vez" in ops["STA"]["origen"], ops["STA"]["origen"]


def test_adverbio_asertivo_hace_real_explicito():
    toks = [
        _t(1, "Ciertamente", "ciertamente", "ADV", "advmod", 3, ""),
        _t(2, "Juan", "Juan", "PROPN", "nsubj", 3, ""),
        _t(3, "corrió", "correr", "VERB", "root", 0,
           "Mood=Ind|Number=Sing|Person=3|Tense=Past|VerbForm=Fin"),
    ]
    assert detectar_operadores(toks, 3, None, CFG)["STA"]["valor"] == "REAL"


def test_sin_adverbio_no_hay_sta():
    toks = [_t(1, "Juan", "Juan", "PROPN", "nsubj", 2, ""),
            _t(2, "corrió", "correr", "VERB", "root", 0,
               "Mood=Ind|Number=Sing|Person=3|Tense=Past|VerbForm=Fin")]
    assert "STA" not in detectar_operadores(toks, 2, None, CFG)


# ---------------------------------------------------------------------------
# IF
# ---------------------------------------------------------------------------
def test_imperativo_por_forma_de_la_oracion():
    """Stanza no etiqueta Mood=Imp en español: '¡Corre!' sale Mood=Ind
    Person=3. IMP se infiere de ¡! + verbo finito sin sujeto expreso."""
    toks = [
        _t(1, "¡", "¡", "PUNCT", "punct", 2, "PunctSide=Ini|PunctType=Excl"),
        _t(2, "Corre", "correr", "VERB", "root", 0,
           "Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin"),
        _t(3, "!", "!", "PUNCT", "punct", 2, "PunctSide=Fin|PunctType=Excl"),
    ]
    assert detectar_operadores(toks, 2, None, CFG)["IF"]["valor"] == "IMP"


def test_exclamativa_con_sujeto_no_es_imperativa():
    """'¡Qué bonito es el parque!' — raíz ADJ con cópula: no es imperativo."""
    toks = [
        _t(1, "¡", "¡", "PUNCT", "punct", 3, "PunctSide=Ini|PunctType=Excl"),
        _t(2, "Qué", "qué", "DET", "det", 3, "PronType=Int"),
        _t(3, "bonito", "bonito", "ADJ", "root", 0, "Gender=Masc|Number=Sing"),
        _t(4, "es", "ser", "AUX", "cop", 3,
           "Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin"),
        _t(5, "parque", "parque", "NOUN", "nsubj", 3, "Gender=Masc|Number=Sing"),
        _t(6, "!", "!", "PUNCT", "punct", 3, "PunctSide=Fin|PunctType=Excl"),
    ]
    ops = detectar_operadores(toks, 3, None, CFG)
    assert ops["IF"]["valor"] == "DEC"
    assert ops["TNS"]["valor"] == "PRES"   # el tiempo lo lleva la cópula


def test_interrogativa_wh():
    toks = [
        _t(1, "¿", "¿", "PUNCT", "punct", 3, "PunctSide=Ini|PunctType=Qest"),
        _t(2, "Quién", "quién", "PRON", "nsubj", 3, "Number=Sing|PronType=Int"),
        _t(3, "corrió", "correr", "VERB", "root", 0,
           "Mood=Ind|Number=Sing|Person=3|Tense=Past|VerbForm=Fin"),
        _t(4, "?", "?", "PUNCT", "punct", 3, "PunctSide=Fin|PunctType=Qest"),
    ]
    assert detectar_operadores(toks, 3, None, CFG)["IF"]["valor"] == "INT"


# ---------------------------------------------------------------------------
# Notación: omisión, orden de scope, wrappers
# ---------------------------------------------------------------------------
def test_operadores_no_especificados_se_omiten():
    ops = {"IF": {"valor": "DEC", "estrato": "clausular", "origen": ""},
           "TNS": {"valor": "PAST", "estrato": "clausular", "origen": ""}}
    assert envolver_ls("correr'(Juan)", ops) == "⟨IF DEC ⟨TNS PAST ⟨correr'(Juan)⟩⟩⟩"


def test_orden_de_scope_completo():
    """El anidamiento sigue 2.25 aunque el dict llegue desordenado."""
    ops = {"ASP": {"valor": "PERF"}, "IF": {"valor": "DEC"},
           "MOD": {"valor": "OBLG"}, "TNS": {"valor": "PRES"},
           "NEG": {"valor": "NEG"}, "STA": {"valor": "IRR"}}
    envuelta = envolver_ls("P", ops)
    assert envuelta == (
        "⟨IF DEC ⟨TNS PRES ⟨STA IRR ⟨NEG ⟨MOD OBLG ⟨ASP PERF ⟨P⟩⟩⟩⟩⟩⟩⟩"), envuelta
    # 6 operadores + el par que encierra la EL: corchetes balanceados
    assert envuelta.count("⟨") == envuelta.count("⟩") == 7


def test_sin_operadores_la_el_no_se_toca():
    assert envolver_ls("do'(Juan, [correr'(Juan)])", {}) == "do'(Juan, [correr'(Juan)])"


def test_operadores_envuelven_por_fuera_de_los_wrappers():
    """Los wrappers de periferia ya están DENTRO de la cadena que se envuelve:
    los operadores son la capa más externa de toda la representación."""
    con_wrappers = "yesterday'(be-in'(parque, [do'(Juan, [correr'(Juan)])]))"
    ops = {"IF": {"valor": "DEC"}, "TNS": {"valor": "PAST"}}
    assert envolver_ls(con_wrappers, ops) == (
        "⟨IF DEC ⟨TNS PAST ⟨yesterday'(be-in'(parque, "
        "[do'(Juan, [correr'(Juan)])]))⟩⟩⟩")


def test_notacion_usa_corchetes_angulares_no_menor_mayor():
    """U+27E8/U+27E9, nunca `<` `>` (colisionarían con el HTML de la GUI)."""
    envuelta = envolver_ls("P", {"IF": {"valor": "DEC"}})
    assert "<" not in envuelta and ">" not in envuelta
    assert envuelta.startswith("⟨") and envuelta.endswith("⟩")


def test_dict_no_referencia_variables_numeradas():
    """Nada nuevo profundiza la numeración x1/x2/x3 (gruxx-ismo con reforma
    pendiente): el dict de operadores habla de valores, estratos y señales."""
    ops = detectar_operadores(_toks_ha_estado_llorando(), 4, "complet", CFG)
    for spec in ops.values():
        assert set(spec) == {"valor", "estrato", "origen", "origen_ids"}
        assert "x1" not in spec["origen"] and "x2" not in spec["origen"]


def test_toks_vacios_no_rompe():
    assert detectar_operadores([], None, None, CFG) == {}
    assert detectar_operadores([], 1, None, CFG) == {}


# ---------------------------------------------------------------------------
# @slow — integración end-to-end con el mapper
# ---------------------------------------------------------------------------
def test_slow_integracion_mapper():
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    ls = m.map_sentence_to_ls(nlp("¿Ha estado llorando Juan?").sentences[0])
    ops = ls["operadores"]
    assert ops["IF"]["valor"] == "INT"
    assert ops["TNS"]["valor"] == "PRES"
    assert ops["ASP"]["valor"] == "PERF PROG"
    assert ls["ls_lexical_ops"].startswith("⟨IF INT ⟨TNS PRES ⟨ASP PERF PROG ⟨")
    # la EL interna NO se toca: las envueltas viajan en claves nuevas
    assert "⟨" not in ls["ls_formal"] and "⟨" not in ls["ls_lexical"]

    ls = m.map_sentence_to_ls(nlp("Juan corría.").sentences[0])
    assert ls["operadores"]["TNS"]["valor"] == "PAST"
    assert ls["operadores"]["ASP"]["valor"] == "IMPF"

    ls = m.map_sentence_to_ls(nlp("Juan no corrió.").sentences[0])
    assert ls["operadores"]["NEG"]["valor"] == "NEG"

    ls = m.map_sentence_to_ls(nlp("Juan debe estudiar.").sentences[0])
    assert ls["operadores"]["MOD"]["valor"] == "OBLG"

    ls = m.map_sentence_to_ls(nlp("Quizá venga María.").sentences[0])
    assert ls["operadores"]["STA"]["valor"] == "IRR"

    ls = m.map_sentence_to_ls(nlp("¡Corre!").sentences[0])
    assert ls["operadores"]["IF"]["valor"] == "IMP"

    # operadores POR FUERA de los wrappers de periferia
    ls = m.map_sentence_to_ls(
        nlp("Ayer Juan corrió tres horas en el parque.").sentences[0])
    envuelta = ls["ls_lexical_ops"]
    assert envuelta.startswith("⟨IF DEC ⟨TNS PAST ⟨")
    assert "yesterday'(" in envuelta


def test_slow_flag_maestro_apagado_no_deja_rastro_de_la_etapa():
    """Con `operadores.enabled: false` la etapa desaparece por completo: ni
    claves nuevas ni ⟨ ⟩ en la EL.

    OJO — el flag YA NO significa "EL byte-idéntica a con-operadores": desde
    OPERATORS_2 §1 la supresión de pseudo-predicados está ACOPLADA al flag, y
    debe estarlo. Si los operadores no corren, nadie representa la negación ni
    el epistémico, así que sus wrappers (`no'`, `maybe'`) tienen que volver:
    apagar la etapa nunca puede PERDER información, solo devolverla a la forma
    vieja. Lo que no vuelve es `prog()`/`complet()`: se eliminaron por diseño
    aprobado (§1), no son reversibles por flag.
    """
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    frases = ["¿Ha estado llorando Juan?", "Juan no corrió.",
              "Ayer Juan corrió tres horas en el parque.",
              "María le dio flores a Pedro."]

    cfg = m._aspect_clf.config
    previo = dict(cfg.get("operadores", {}))
    con = [m.map_sentence_to_ls(nlp(f).sentences[0]) for f in frases]
    try:
        cfg["operadores"] = {**previo, "enabled": False}
        sin = [m.map_sentence_to_ls(nlp(f).sentences[0]) for f in frases]
    finally:
        cfg["operadores"] = previo

    for c, s in zip(con, sin):
        assert "operadores" not in s
        assert "ls_formal_ops" not in s and "ls_lexical_ops" not in s
        assert "⟨" not in s["ls_formal"] and "⟨" not in s["ls_lexical"]
        assert c["ls_type"] == s["ls_type"]      # la clase NUNCA depende del flag

    # la negación no se pierde al apagar: vuelve como wrapper léxico
    assert "no'(" in sin[1]["ls_lexical"]
    assert "no'(" not in con[1]["ls_lexical"]
    assert con[1]["operadores"]["NEG"]["valor"] == "NEG"


# ---------------------------------------------------------------------------
# OPERATORS_2 §1 — la EL no lleva pseudo-predicados de operador
# ---------------------------------------------------------------------------
def test_slow_el_canonica_sin_pseudo_predicados():
    """Ni `complet(…)`/`prog(…)`, ni `no'(…)`, ni los epistémicos: esa
    información vive SOLO en ⟨ ⟩. Precondición de LA1, que leerá posiciones
    de la EL para asignar macropapeles."""
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    casos = {
        "Juan ha estudiado.":        ("ASP", "PERF"),
        "Juan está corriendo.":      ("ASP", "PROG"),
        "Juan no corrió.":           ("NEG", "NEG"),
        "Quizá venga María.":        ("STA", "IRR"),
        "Probablemente Juan corrió.": ("STA", "IRR"),
        "Obviamente Juan corrió.":   ("STA", "REAL"),
    }
    prohibidos = ("complet(", "prog(", "no'(", "maybe'(", "probably'(",
                  "surely'(", "obviously'(", "tal'(")
    for frase, (op, valor) in casos.items():
        ls = m.map_sentence_to_ls(nlp(frase).sentences[0])
        for p in prohibidos:
            assert p not in ls["ls_lexical"], f"{frase}: quedó '{p}' en {ls['ls_lexical']}"
        assert ls["operadores"][op]["valor"] == valor, frase


def test_slow_supresion_es_por_operador_no_por_lista_de_lemas():
    """LOSSLESS: solo se suprime lo que REALMENTE disparó un operador.

    'aparentemente' es evidencial y EVID no está implementado → no dispara
    nada → conserva su wrapper. 'nunca' fusiona negación y cuantificación de
    evento → no dispara NEG (ver `_detectar_neg`) → conserva `never'`. Si la
    supresión fuera por lista de lemas, estas dos oraciones habrían perdido
    información."""
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    ls = m.map_sentence_to_ls(nlp("Aparentemente Juan corrió.").sentences[0])
    assert "apparently'(" in ls["ls_lexical"]
    assert "STA" not in ls["operadores"]

    ls = m.map_sentence_to_ls(nlp("Juan nunca corrió.").sentences[0])
    assert "never'(" in ls["ls_lexical"]
    assert "NEG" not in ls["operadores"]


def test_slow_wrappers_lexicos_legitimos_sobreviven():
    """La línea divisoria: categoría gramatical cerrada → operador; contenido
    LÉXICO → predicado. La manera, los locativos y los temporales se quedan."""
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    ls = m.map_sentence_to_ls(
        nlp("Ayer Juan corrió tres horas en el parque.").sentences[0])
    assert "yesterday'(" in ls["ls_lexical"] and "be-in'(parque" in ls["ls_lexical"]

    ls = m.map_sentence_to_ls(nlp("Juan corrió lentamente.").sentences[0])
    assert "lentamente'(" in ls["ls_lexical"]

    ls = m.map_sentence_to_ls(nlp("Juan rezó durante la clase.").sentences[0])
    assert "during'(clase" in ls["ls_lexical"]


def test_slow_completeness_no_avisa_por_elemento_cubierto_por_operador():
    """El 'no' ya no se busca como wrapper↔rama: está cubierto por ⟨NEG⟩.
    No debe generar advertencias nuevas."""
    import stanza
    from discodop.tree import ParentedTree
    import rrg_ls_mapper as m
    from .completeness import verificar

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    ls = m.map_sentence_to_ls(nlp("Juan no corrió.").sentences[0])
    # Un árbol cualquiera basta: el elemento cubierto por operador se resuelve
    # ANTES de buscar nada en el árbol (por eso deja de haber advertencia).
    arbol = ParentedTree("CLAUSE", [ParentedTree("CORE", [ParentedTree("NUC", [2])])])
    comp = verificar(ls, arbol)
    peri = [c for c in comp["checks"] if c["tipo"] == "periferia"]
    assert any(c["estado"] == "ok" and "⟨NEG⟩" in c["detalle"] for c in peri), peri
    assert not any(c["estado"] == "falta_en_arbol" for c in peri)


# ---------------------------------------------------------------------------
# OPERATORS_2 §1 — la EL ya no lleva pseudo-predicados
# ---------------------------------------------------------------------------
def test_tokens_cubiertos_mapea_disparadores():
    from .operadores import tokens_cubiertos
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 3, ""),
        _t(2, "no", "no", "ADV", "advmod", 3, "Polarity=Neg"),
        _t(3, "corrió", "correr", "VERB", "root", 0,
           "Mood=Ind|Number=Sing|Person=3|Tense=Past|VerbForm=Fin"),
    ]
    cubiertos = tokens_cubiertos(detectar_operadores(toks, 3, None, CFG))
    assert cubiertos[2] == "NEG"     # el 'no' lo cubre el operador
    assert cubiertos[3] == "TNS"     # el verbo finito, el tiempo


def test_nunca_no_dispara_neg_y_conserva_su_wrapper():
    """'nunca' lleva Polarity=Neg pero FUSIONA negación y cuantificación de
    evento: reducirla a ⟨NEG⟩ perdería la parte cuantificacional (EVQ no
    existe todavía), así que conserva su predicado léxico `never'`."""
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 3, ""),
        _t(2, "nunca", "nunca", "ADV", "advmod", 3, "Polarity=Neg"),
        _t(3, "corrió", "correr", "VERB", "root", 0,
           "Mood=Ind|Number=Sing|Person=3|Tense=Past|VerbForm=Fin"),
    ]
    ops = detectar_operadores(toks, 3, None, CFG)
    assert "NEG" not in ops
    from .operadores import tokens_cubiertos
    assert 2 not in tokens_cubiertos(ops)   # -> wrappers_ls lo envolverá


def test_wrapper_suprimido_solo_para_el_token_del_operador():
    """El filtro es por ID de token, no por lista de lemas: un adverbio que
    NO dispara operador conserva su wrapper (no se pierde información)."""
    from .wrappers_ls import componer_wrappers
    peri = [{"id": 2, "text": "no", "lemma": "no", "deprel": "advmod",
             "tipo": "generico", "estrato": "centro", "case": None},
            {"id": 5, "text": "aparentemente", "lemma": "aparentemente",
             "deprel": "advmod", "tipo": "epistemico", "estrato": "clausula",
             "case": None}]
    f, l, ap = componer_wrappers("P", "P", peri, {}, {2: "NEG"})
    assert "no'" not in f                    # cubierto por ⟨NEG⟩
    assert "apparently'" in f or "aparentemente'" in f   # conservado
    suprimidos = [a for a in ap if a.get("razon") == "operador"]
    assert [(a["trigger"], a["operador"]) for a in suprimidos] == [("no", "NEG")]


def test_sin_cubiertos_los_wrappers_no_cambian():
    """Regresión: sin operadores (flag apagado) `componer_wrappers` se comporta
    EXACTAMENTE como antes -- si no, apagar la etapa perdería la negación."""
    from .wrappers_ls import componer_wrappers
    peri = [{"id": 2, "text": "no", "lemma": "no", "deprel": "advmod",
             "tipo": "generico", "estrato": "centro", "case": None}]
    con_none = componer_wrappers("P", "P", peri, {}, None)
    con_vacio = componer_wrappers("P", "P", peri, {}, {})
    assert con_none[0] == con_vacio[0] == "no'([P])"


# ---------------------------------------------------------------------------
# OPERATORS_2 §2 — corrección de operadores
# ---------------------------------------------------------------------------
def _res_con_ops(ops, oracion="Juan corrió.", periferia=None, verb_lemma="correr"):
    return {"oracion": oracion, "ls_lista": [{
        "ls_type": "activity", "ls_lexical": "do'(Juan, [correr'(Juan)])",
        "ls_formal": "do'(x1, [correr'(x1)])", "morph_note": "",
        "verb_lemma": verb_lemma, "core": [], "agx": [],
        "periferia": periferia or [], "operadores": ops}]}


def test_correccion_rechaza_valores_fuera_de_la_teoria():
    import tempfile
    from . import correccion as c
    r = c.corregir_operador(_res_con_ops({}), 0, "TNS", "cambiar", "PLUSCUAM",
                            lambda o: None, data_dir=tempfile.mkdtemp())
    assert r["accion"] == "error"


def test_correccion_rechaza_operador_desconocido():
    import tempfile
    from . import correccion as c
    r = c.corregir_operador(_res_con_ops({}), 0, "EVID", "cambiar", "REP",
                            lambda o: None, data_dir=tempfile.mkdtemp())
    assert r["accion"] == "error"


def test_correccion_de_parse_va_a_staging_con_la_senal():
    """IF/TNS/ASP no salen de listas de palabras sino de rasgos morfológicos:
    su corrección NUNCA puede escribirse en un léxico -> staging honesto."""
    import csv as _csv
    import os
    import tempfile
    from . import correccion as c
    tmp = tempfile.mkdtemp()
    ops = {"IF": {"valor": "DEC", "estrato": "clausular",
                  "origen": "declarativa (default)", "origen_ids": []}}
    r = c.corregir_operador(_res_con_ops(ops, "Cómete la manzana."), 0,
                            "IF", "cambiar", "IMP", lambda o: None, data_dir=tmp)
    assert r["accion"] == "staging_operador"
    filas = list(_csv.DictReader(
        open(os.path.join(tmp, "correcciones_operadores.csv"), encoding="utf-8")))
    assert filas[0]["operador"] == "IF"
    assert filas[0]["valor_predicho"] == "DEC" and filas[0]["valor_correcto"] == "IMP"
    assert filas[0]["senal_origen"] == "declarativa (default)"


def test_correccion_quitar_operador():
    import tempfile
    from . import correccion as c
    ops = {"NEG": {"valor": "NEG", "estrato": "nuclear",
                   "origen": "'no' advmod", "origen_ids": [2]}}
    r = c.corregir_operador(_res_con_ops(ops), 0, "NEG", "quitar", None,
                            lambda o: None, data_dir=tempfile.mkdtemp())
    assert r["accion"] == "staging_operador"


def test_candidato_lexico_ignora_adverbios_que_ya_disparan_operador():
    from .correccion import _candidato_lexico
    ls = {"operadores": {"STA": {"valor": "IRR", "origen": "", "origen_ids": [1]}},
          "periferia": [{"id": 1, "text": "Quizá", "lemma": "quizá", "deprel": "advmod"},
                        {"id": 4, "text": "raramente", "lemma": "raramente",
                         "deprel": "advmod"}]}
    # el candidato es el que NO está cubierto todavía
    assert _candidato_lexico(ls, "STA") == "raramente"


def test_confirmador_de_operador():
    from .correccion import _confirma_operador
    ls = {"operadores": {"TNS": {"valor": "PRES"}}}
    assert _confirma_operador(ls, "TNS", "cambiar", "PRES")
    assert not _confirma_operador(ls, "TNS", "cambiar", "PAST")
    assert _confirma_operador(ls, "NEG", "quitar", None)
    assert not _confirma_operador(ls, "TNS", "quitar", None)


def test_valores_operador_espeja_la_teoria():
    from .correccion import VALORES_OPERADOR
    assert VALORES_OPERADOR["IF"] == ["DEC", "INT", "IMP"]
    assert VALORES_OPERADOR["TNS"] == ["PAST", "PRES", "FUT"]
    assert set(VALORES_OPERADOR) <= set(ORDEN_SCOPE_TEST)


ORDEN_SCOPE_TEST = ["IF", "EVID", "TNS", "STA", "NEG", "MOD", "EVQ", "DIR", "ASP"]


def test_perifrasis_modal_como_raiz_con_xcomp_dispara_mod():
    """Sin esto, corregir un MOD escribiría en `operadores.modales` una
    entrada que la detección nunca leería (Stanza analiza 'suele correr' con
    el modal de RAÍZ, no como auxiliar)."""
    cfg = {**CFG, "modales": {**CFG["modales"], "soler": "OBLG"}}
    toks = [
        _t(1, "Juan", "Juan", "PROPN", "nsubj", 2, ""),
        _t(2, "suele", "soler", "VERB", "root", 0,
           "Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin"),
        _t(3, "correr", "correr", "VERB", "xcomp", 2, "VerbForm=Inf"),
    ]
    assert detectar_operadores(toks, 2, None, cfg)["MOD"]["valor"] == "OBLG"


def main():
    rapidos = [
        test_canonico_2_26_deteccion,
        test_canonico_2_26_envuelta_byte_a_byte,
        test_canonico_estratos_y_origen,
        test_estudie_declarativa_pasado,
        test_imperfecto_es_past_mas_impf,
        test_pluscuamperfecto_perf_impf,
        test_condicional_sin_tns_y_con_sta_irr,
        test_futuro,
        test_verbo_finito_es_el_auxiliar_cuando_la_raiz_no_lo_es,
        test_negacion,
        test_neg_no_se_duplica_en_la_etiqueta,
        test_modal_deber_oblg,
        test_modal_poder_abil,
        test_modal_deberia_es_oblg_mas_irr,
        test_tener_que_patron_propio,
        test_perifrasis_vigiladas_se_reportan_sin_cambiar_nada,
        test_perifrasis_vigilada_como_raiz_con_xcomp,
        test_verbo_vigilado_sin_infinitivo_no_se_loguea,
        test_quiza_subjuntivo_irr,
        test_tal_vez_es_multipalabra_fixed,
        test_adverbio_asertivo_hace_real_explicito,
        test_sin_adverbio_no_hay_sta,
        test_imperativo_por_forma_de_la_oracion,
        test_exclamativa_con_sujeto_no_es_imperativa,
        test_interrogativa_wh,
        test_operadores_no_especificados_se_omiten,
        test_orden_de_scope_completo,
        test_sin_operadores_la_el_no_se_toca,
        test_operadores_envuelven_por_fuera_de_los_wrappers,
        test_notacion_usa_corchetes_angulares_no_menor_mayor,
        test_dict_no_referencia_variables_numeradas,
        test_toks_vacios_no_rompe,
        # OPERATORS_2 §1
        test_tokens_cubiertos_mapea_disparadores,
        test_nunca_no_dispara_neg_y_conserva_su_wrapper,
        test_wrapper_suprimido_solo_para_el_token_del_operador,
        test_sin_cubiertos_los_wrappers_no_cambian,
        # OPERATORS_2 §2
        test_correccion_rechaza_valores_fuera_de_la_teoria,
        test_correccion_rechaza_operador_desconocido,
        test_correccion_de_parse_va_a_staging_con_la_senal,
        test_correccion_quitar_operador,
        test_candidato_lexico_ignora_adverbios_que_ya_disparan_operador,
        test_confirmador_de_operador,
        test_valores_operador_espeja_la_teoria,
        test_perifrasis_modal_como_raiz_con_xcomp_dispara_mod,
    ]
    tests = rapidos + ([test_slow_integracion_mapper,
                        test_slow_flag_maestro_apagado_no_deja_rastro_de_la_etapa,
                        test_slow_el_canonica_sin_pseudo_predicados,
                        test_slow_supresion_es_por_operador_no_por_lista_de_lemas,
                        test_slow_wrappers_lexicos_legitimos_sobreviven,
                        test_slow_completeness_no_avisa_por_elemento_cubierto_por_operador]
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
