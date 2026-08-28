"""Tests del Paso 4 — causatividad ([do'(x,Ø)] CAUSE [β]).

Ejecutar:
    python -m aspect_classifier.test_causatividad          # puros (sin modelos)
    python -m aspect_classifier.test_causatividad --slow   # + Stanza/BERTIN

Compatible con pytest (los @slow requieren RUN_SLOW=1).
"""

import os
import sys
import tempfile
from pathlib import Path

from .causatividad import (aplicar_gate_semelfactive, cargar_lexicon,
                           componer_cause, detectar_causatividad,
                           log_candidato)

RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv
LEXICON = cargar_lexicon()


def _tok(id_, text, lemma, upos, deprel, head):
    return {"id": id_, "text": text, "lemma": lemma, "upos": upos,
            "deprel": deprel, "head": head}


# "El gato reventó el globo"
GATO_GLOBO = [
    _tok(1, "El", "el", "DET", "det", 2),
    _tok(2, "gato", "gato", "NOUN", "nsubj", 3),
    _tok(3, "reventó", "reventar", "VERB", "root", 0),
    _tok(4, "el", "el", "DET", "det", 5),
    _tok(5, "globo", "globo", "NOUN", "obj", 3),
]

# "El jarrón se rompió"
JARRON_SE = [
    _tok(1, "El", "el", "DET", "det", 2),
    _tok(2, "jarrón", "jarrón", "NOUN", "nsubj", 4),
    _tok(3, "se", "él", "PRON", "expl:pv", 4),
    _tok(4, "rompió", "romper", "VERB", "root", 0),
]

# "El perro se sacudió"
PERRO_SE = [
    _tok(1, "El", "el", "DET", "det", 2),
    _tok(2, "perro", "perro", "NOUN", "nsubj", 4),
    _tok(3, "se", "él", "PRON", "expl:pv", 4),
    _tok(4, "sacudió", "sacudir", "VERB", "root", 0),
]

# "La puerta se atascó" (atascar NO está en el léxico)
PUERTA_SE = [
    _tok(1, "La", "el", "DET", "det", 2),
    _tok(2, "puerta", "puerta", "NOUN", "nsubj", 4),
    _tok(3, "se", "él", "PRON", "expl:pv", 4),
    _tok(4, "atascó", "atascar", "VERB", "root", 0),
]

# "Juan leyó el libro" (transitivo NO causativo, fuera de léxico)
JUAN_LIBRO = [
    _tok(1, "Juan", "Juan", "PROPN", "nsubj", 2),
    _tok(2, "leyó", "leer", "VERB", "root", 0),
    _tok(3, "el", "el", "DET", "det", 4),
    _tok(4, "libro", "libro", "NOUN", "obj", 2),
]

# "El abuelo se murió" (morir: no causativo, se no anticausativo en léxico)
ABUELO_SE = [
    _tok(1, "El", "el", "DET", "det", 2),
    _tok(2, "abuelo", "abuelo", "NOUN", "nsubj", 4),
    _tok(3, "se", "él", "PRON", "expl:pv", 4),
    _tok(4, "murió", "morir", "VERB", "root", 0),
]


def test_lexico_transitivo():
    c = detectar_causatividad(GATO_GLOBO, 3, LEXICON)
    assert c["causativo"] and c["tipo"] == "lexico_transitivo"
    assert c["source"] == "lexicon" and c["confianza"] == "alta"
    assert c["causer_id"] == 2 and c["patient_id"] == 5
    ls = componer_cause("Achievement", "reventado'/popped'", "reventar",
                        "gato", "globo", False)
    assert ls["lexical"] == "[do'(gato, Ø)] CAUSE [INGR reventado'(globo)]"
    assert ls["formal"] == "[do'(x, Ø)] CAUSE [INGR reventado'(y)]"


def test_lexico_anticausativo_se():
    c = detectar_causatividad(JARRON_SE, 4, LEXICON)
    assert c["causativo"] and c["tipo"] == "lexico_anticausativo_se"
    assert c["se_anticausativo"] and c["patient_id"] == 2
    assert c["causer_id"] is None
    ls = componer_cause("Achievement", "broken'", "romper",
                        None, "jarrón", True)
    assert ls["lexical"] == "[do'(Ø, Ø)] CAUSE [INGR roto'(jarrón)]"


def test_gate_se_reflexivo_sacudir():
    c = detectar_causatividad(PERRO_SE, 4, LEXICON)
    assert not c["causativo"], "se de sacudir NO es anticausativo"
    assert c["se_reflexivo_no_causativo"]
    assert c["lex_aktionsart"] == "Semelfactive"
    # el gate corrige Achievement (telicidad espuria) → Semelfactive
    assert aplicar_gate_semelfactive("achievement", 0.9, c) == "semelfactive"
    # pero no toca clases con pun bajo ni otras clases
    assert aplicar_gate_semelfactive("achievement", 0.2, c) == "achievement"
    assert aplicar_gate_semelfactive("activity", 0.9, c) == "activity"


def test_gate_no_dispara_con_morir():
    """'se murió' tiene se no-anticausativo, pero base Achievement: sin gate."""
    c = detectar_causatividad(ABUELO_SE, 4, LEXICON)
    assert not c["causativo"]
    assert c["se_reflexivo_no_causativo"]
    assert c["lex_aktionsart"] == "Achievement"
    assert aplicar_gate_semelfactive("achievement", 0.95, c) == "achievement"


def test_heuristico_conservador():
    c = detectar_causatividad(PUERTA_SE, 4, LEXICON)
    assert c["causativo"] and c["source"] == "heuristic"
    assert c["confianza"] == "baja" and c["candidato_lexico"]
    assert c["se_anticausativo"] and c["patient_id"] == 2


def test_fallback_no_dispara_en_transitivo():
    c = detectar_causatividad(JUAN_LIBRO, 2, LEXICON)
    assert not c["causativo"], "sesgo a no-CAUSE: transitivo sin señal no dispara"
    assert not c["se_reflexivo_no_causativo"]


def test_componer_cause_seis_clases():
    casos = {
        "State":          "[do'(x, Ø)] CAUSE [asustado'(y)]",
        "Activity":       "[do'(x, Ø)] CAUSE [do'(y, [rodar'(y)])]",
        "Achievement":    "[do'(x, Ø)] CAUSE [INGR roto'(y)]",
        "Semelfactive":   "[do'(x, Ø)] CAUSE [SEML destello'(y)]",
        "Accomplishment": "[do'(x, Ø)] CAUSE [BECOME seco'(y)]",
        "Active_Accomplishment": "[do'(x, Ø)] CAUSE [do'(y, [pasear'(y)])]",
    }
    preds = {"State": "asustado'", "Activity": "rodar'", "Achievement": "roto'",
             "Semelfactive": "destello'", "Accomplishment": "seco'",
             "Active_Accomplishment": "pasear'"}
    for base, esperado in casos.items():
        ls = componer_cause(base, preds[base], "x", "Juan", "cosa", False)
        assert ls["formal"] == esperado, (base, ls["formal"])


def test_log_candidato():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "cand.csv"
        log_candidato("atascar", "La puerta se atascó", p)
        log_candidato("atascar", "La puerta se atascó", p)   # dedupe
        lineas = p.read_text(encoding="utf-8").strip().splitlines()
        assert len(lineas) == 2  # header + 1


# ---------------------------------------------------------------------------
# Integración (Stanza + BERTIN) — solo con --slow / RUN_SLOW=1
# ---------------------------------------------------------------------------
def test_slow_cause_por_clase_y_regresion():
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    # pares causativos de la teoría, uno por clase de β
    causativos = {
        "El ruido asustó al niño":      ("state", "CAUSE"),
        "El niño destrozó el juguete":  ("achievement", "CAUSE"),
        "El sol secó la ropa":          ("accomplishment", "CAUSE"),
        "El faro destelló una señal":   ("semelfactive", "CAUSE"),
        "Juan rodó la pelota":          ("activity", "CAUSE"),
        "Juan paseó al perro":          ("activity", "CAUSE"),
    }
    for texto, (clase, marca) in causativos.items():
        ls = m.map_sentence_to_ls(nlp(texto).sentences[0])
        assert ls["causativo"], texto
        assert ls["causativo_source"] == "lexicon", texto
        assert marca in ls["ls_formal"], (texto, ls["ls_formal"])
        assert ls["ls_type"] == clase, (texto, ls["ls_type"])

    # anticausativo: x → Ø, paciente a PSA
    ls = m.map_sentence_to_ls(nlp("El jarrón se rompió").sentences[0])
    assert ls["causativo"] and ls["causativo_tipo"] == "lexico_anticausativo_se"
    assert "do'(Ø, Ø)" in ls["ls_lexical"] and "jarrón" in ls["ls_lexical"]
    assert "→PSA" in ls["args_map"]

    # gate: se reflexivo/medio de base Semelfactive
    ls = m.map_sentence_to_ls(nlp("El perro se sacudió").sentences[0])
    assert not ls["causativo"]
    assert ls["ls_type"] == "semelfactive", ls["ls_type"]

    # sesgo a no-CAUSE
    ls = m.map_sentence_to_ls(nlp("Juan leyó el libro").sentences[0])
    assert not ls["causativo"] and "CAUSE" not in ls["ls_formal"]


if not RUN_SLOW:
    try:
        import pytest
        test_slow_cause_por_clase_y_regresion = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_cause_por_clase_y_regresion)
    except ImportError:
        pass


def main():
    rapidos = [test_lexico_transitivo, test_lexico_anticausativo_se,
               test_gate_se_reflexivo_sacudir, test_gate_no_dispara_con_morir,
               test_heuristico_conservador, test_fallback_no_dispara_en_transitivo,
               test_componer_cause_seis_clases, test_log_candidato]
    tests = rapidos + ([test_slow_cause_por_clase_y_regresion] if RUN_SLOW else [])

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
