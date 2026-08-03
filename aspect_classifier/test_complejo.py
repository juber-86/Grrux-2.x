"""Tests del complejo verbal (Fase 2).

Ejecutar:
    python -m aspect_classifier.test_complejo          # tests rápidos (sin BERTIN)
    python -m aspect_classifier.test_complejo --slow   # además, integración con BERTIN

También es compatible con pytest (los @slow requieren RUN_SLOW=1).
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

from .complejo_verbal import DEFAULT_CLITIC_DEPRELS, extraer_complejo
from .extractor import VerbEmbeddingExtractor

FIXTURE = Path(__file__).parent / "data" / "input_estudiante.conllu"

DEFAULT_CFG = {
    "clitic_deprels": DEFAULT_CLITIC_DEPRELS,
    "incluir_od_nucleo": True,
    "incluir_od_det": False,
}

RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv


def parse_conllu(path: Path) -> list[dict]:
    """Mini-parser CoNLL-U: solo la primera oración, sin MWT ni nodos vacíos."""
    tokens = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            if tokens:
                break
            continue
        if line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) != 10 or not cols[0].isdigit():
            continue
        tokens.append({
            "id": int(cols[0]),
            "text": cols[1],
            "lemma": cols[2],
            "upos": cols[3],
            "deprel": cols[7],
            "head": int(cols[6]),
        })
    return tokens


# ---------------------------------------------------------------------------
# Tests rápidos (sin modelo)
# ---------------------------------------------------------------------------
def test_extraer_complejo_fixture():
    """'juan se comió la pizza completa' → {se, comió, pizza}, sin det ni amod."""
    tokens = parse_conllu(FIXTURE)
    assert [t["text"] for t in tokens] == ["juan", "se", "comió", "la", "pizza", "completa"]
    root_id = next(t["id"] for t in tokens if t["head"] == 0)

    comp = extraer_complejo(tokens, root_id, DEFAULT_CFG)

    assert comp["incluidos"] == [2, 3, 5], comp["incluidos"]
    assert 4 not in comp["incluidos"], "'la' (det) no debe incluirse"
    assert 6 not in comp["incluidos"], "'completa' (amod) no debe incluirse"
    assert comp["texto"] == "juan se comió la pizza completa"

    # Los spans apuntan exactamente a esos tokens dentro de "texto"
    superficies = [comp["texto"][a:b] for a, b in comp["spans"]]
    assert superficies == ["se", "comió", "pizza"], superficies


def test_spans_discontiguos():
    """Debe haber un hueco entre 'comió' y 'pizza' (donde está 'la')."""
    tokens = parse_conllu(FIXTURE)
    root_id = next(t["id"] for t in tokens if t["head"] == 0)
    spans = extraer_complejo(tokens, root_id, DEFAULT_CFG)["spans"]

    huecos = [b - a for (_, a), (b, _) in zip(spans, spans[1:])]
    # "se"→"comió" son adyacentes (hueco = 1 espacio); "comió"→"pizza" salta "la"
    assert any(h > 1 for h in huecos), f"spans no discontiguos: {spans}"


def test_flags_od():
    tokens = parse_conllu(FIXTURE)
    root_id = next(t["id"] for t in tokens if t["head"] == 0)

    con_det = extraer_complejo(tokens, root_id, {**DEFAULT_CFG, "incluir_od_det": True})
    assert con_det["incluidos"] == [2, 3, 4, 5]

    sin_od = extraer_complejo(tokens, root_id, {**DEFAULT_CFG, "incluir_od_nucleo": False})
    assert sin_od["incluidos"] == [2, 3]


class _StubTokenizer:
    """Tokeniza por espacios; añade BOS/EOS con offset (0,0) como RoBERTa."""

    def __call__(self, sentence, return_offsets_mapping=True, return_tensors="pt"):
        offsets, pos = [(0, 0)], 0
        for tok in sentence.split():
            start = sentence.index(tok, pos)
            offsets.append((start, start + len(tok)))
            pos = start + len(tok)
        offsets.append((0, 0))
        n = len(offsets)
        return {
            "input_ids": torch.arange(n).unsqueeze(0),
            "offset_mapping": torch.tensor([offsets]),
        }


class _StubModel:
    """hidden_states[capa][0][i] = vector constante con el índice i del token."""

    def __call__(self, input_ids):
        n = input_ids.shape[1]
        h = torch.arange(n, dtype=torch.float32).unsqueeze(1).expand(n, 4)
        return SimpleNamespace(hidden_states=[h.unsqueeze(0)] * 9)


def test_embed_char_spans_poolea_solo_el_complejo():
    """Con el stub, el embedding = media de los ÍNDICES de los tokens pooleados."""
    ext = VerbEmbeddingExtractor.__new__(VerbEmbeddingExtractor)
    ext.tokenizer, ext.model = _StubTokenizer(), _StubModel()
    ext.layer, ext.device = 8, "cpu"

    tokens = parse_conllu(FIXTURE)
    root_id = next(t["id"] for t in tokens if t["head"] == 0)
    comp = extraer_complejo(tokens, root_id, DEFAULT_CFG)

    emb = ext.embed_char_spans(comp["texto"], comp["spans"])

    # Tokens del stub: BOS=0 juan=1 se=2 comió=3 la=4 pizza=5 completa=6 EOS=7
    # Complejo = {se, comió, pizza} → media(2, 3, 5) = 10/3
    assert np.allclose(emb, 10 / 3), emb

    # Compatibilidad: embed_span(un solo span) sigue funcionando
    emb1 = ext.embed_span(comp["texto"], *comp["spans"][1])   # solo "comió"
    assert np.allclose(emb1, 3.0), emb1


# ---------------------------------------------------------------------------
# Tests de integración (cargan BERTIN) — solo con --slow / RUN_SLOW=1
# ---------------------------------------------------------------------------
def test_slow_fase1_intacta():
    from . import AspectClassifier
    clf = AspectClassifier().load()
    r = clf.predict("cocinar")
    assert r["metodo"] == "lexical"
    assert set(r) >= {"clase", "vector", "confianza", "metodo"}
    assert set(r["vector"]) == {"stat", "dyn", "tel", "pun"}


def test_slow_predict_con_complejo():
    from . import AspectClassifier
    clf = AspectClassifier().load()
    tokens = parse_conllu(FIXTURE)
    root_id = next(t["id"] for t in tokens if t["head"] == 0)
    comp = extraer_complejo(tokens, root_id, DEFAULT_CFG)

    r = clf.predict("comer", oracion=comp["texto"], span=comp["spans"])
    assert r["metodo"] == "contextual"
    assert r["clase"] in {"State", "Activity", "Achievement", "Semelfactive",
                          "Accomplishment", "Active_Accomplishment", "State_Activity"}


if not RUN_SLOW:
    try:
        import pytest
        test_slow_fase1_intacta = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_fase1_intacta)
        test_slow_predict_con_complejo = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_predict_con_complejo)
    except ImportError:
        pass


def main():
    rapidos = [
        test_extraer_complejo_fixture,
        test_spans_discontiguos,
        test_flags_od,
        test_embed_char_spans_poolea_solo_el_complejo,
    ]
    lentos = [test_slow_fase1_intacta, test_slow_predict_con_complejo]
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
        print("  (tests de integración omitidos; usa --slow para incluirlos)")
    if fallos:
        sys.exit(1)
    print(f"\n{len(tests)} tests pasaron.")


if __name__ == "__main__":
    main()
