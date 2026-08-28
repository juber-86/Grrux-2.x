"""Tests del Paso 2 — cabeza contextual y Active_Accomplishment.

Ejecutar:
    python -m aspect_classifier.test_fase2_contextual          # rápidos
    python -m aspect_classifier.test_fase2_contextual --slow   # + BERTIN/Stanza

Compatible con pytest (los @slow requieren RUN_SLOW=1).
"""

import json
import os
import sys
from pathlib import Path

import numpy as np

from .complejo_verbal import extraer_complejo
from .test_complejo import DEFAULT_CFG, FIXTURE, parse_conllu

PKG_DIR = Path(__file__).parent
RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv


# ---------------------------------------------------------------------------
# Tests rápidos
# ---------------------------------------------------------------------------
def test_od_like_deprels_configurable():
    """Con od_like_deprels=[obj, obl] el núcleo puede venir de un obl."""
    tokens = [
        {"id": 1, "text": "Juan", "lemma": "juan", "upos": "PROPN",
         "deprel": "nsubj", "head": 2},
        {"id": 2, "text": "corrió", "lemma": "correr", "upos": "VERB",
         "deprel": "root", "head": 0},
        {"id": 3, "text": "por", "lemma": "por", "upos": "ADP",
         "deprel": "case", "head": 4},
        {"id": 4, "text": "kilómetros", "lemma": "kilómetro", "upos": "NOUN",
         "deprel": "obl", "head": 2},
    ]
    solo_obj = extraer_complejo(tokens, 2, DEFAULT_CFG)
    assert solo_obj["incluidos"] == [2], "por defecto obl NO cuenta como OD"

    con_obl = extraer_complejo(tokens, 2, {**DEFAULT_CFG, "od_like_deprels": ["obj", "obl"]})
    assert con_obl["incluidos"] == [2, 4]


def test_embeddings_ctx_alineados():
    """embeddings_ctx.npy y index_ctx.json existen y están alineados."""
    emb_dir = PKG_DIR / "data" / "embeddings"
    X = np.load(emb_dir / "embeddings_ctx.npy")
    with open(emb_dir / "index_ctx.json") as f:
        index = json.load(f)
    assert X.shape[0] == len(index)
    assert X.shape[1] == 768
    clases = {e["clase"] for e in index}
    assert "Active_Accomplishment" in clases, "AA debe estar en el train contextual"
    # el 'texto' pooleado reconstruye la oración tokenizada (misma fuente de verdad)
    ejemplo = index[0]
    assert ejemplo["texto"].replace(" .", ".").startswith(ejemplo["oracion"][:10])


def test_cabeza_contextual_guardada():
    ctx_dir = PKG_DIR / "models" / "contextual"
    for feat in ("stat", "dyn", "tel", "pun"):
        assert (ctx_dir / f"logreg_{feat}.joblib").exists(), feat
    meta = json.loads((ctx_dir / "meta.json").read_text())
    assert meta["receta"] == "complex_pool"
    assert meta["n_train"] > 0 and meta["embedding_dim"] == 768


def test_append_only_guard():
    """run() se niega a regenerar el CSV curado a mano."""
    from . import gen_contextual_sentences as g
    assert g.OUT_CSV.exists(), "precondición: el CSV curado existe"
    try:
        g.run()
    except SystemExit as e:
        assert "CURADO A MANO" in str(e)
    else:
        raise AssertionError("run() debió negarse a sobrescribir el CSV curado")


def test_higiene_revisar_excluido_del_train():
    """Ninguna fila con revisar=True del CSV curado entra en embeddings_ctx."""
    import pandas as pd

    df = pd.read_csv(PKG_DIR / "data" / "contextual_sentences.csv")
    pendientes = set(df[df["revisar"].astype(str).str.lower().isin(("true", "1"))]["oracion"])
    with open(PKG_DIR / "data" / "embeddings" / "index_ctx.json") as f:
        index = json.load(f)
    entrenadas = {e["oracion"] for e in index}
    filtradas = pendientes & entrenadas
    assert not filtradas, f"filas revisar=True dentro del train: {filtradas}"


def test_groupkfold_sin_fuga_por_lema():
    """Ningún lema del set contextual cae a la vez en train y test."""
    from sklearn.model_selection import StratifiedGroupKFold

    with open(PKG_DIR / "data" / "embeddings" / "index_ctx.json") as f:
        index = json.load(f)
    y = np.array([r["clase"] for r in index])
    g = np.array([r["lema"] for r in index])
    X = np.zeros((len(index), 1))
    skf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    for tr, te in skf.split(X, y, groups=g):
        assert not set(g[tr]) & set(g[te]), "fuga por lema entre train y test"
    # y hay lemas con múltiples oraciones (si no, el test no probaría nada)
    import collections
    assert max(collections.Counter(g).values()) > 1


# ---------------------------------------------------------------------------
# Tests de integración (BERTIN + Stanza) — solo con --slow / RUN_SLOW=1
# ---------------------------------------------------------------------------
def test_slow_dianas_aa_y_controles():
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    casos = {
        "Juan se comió la pizza completa": "active_accomplishment",
        "Juan corrió cinco kilómetros":    "active_accomplishment",
        "Juan corrió":                     "activity",
        "Juan corre todos los días":       "activity",
        "Juan sabe la respuesta":          "state",
        "Juan llegó":                      "achievement",
    }
    for texto, esperado in casos.items():
        ls = m.map_sentence_to_ls(nlp(texto).sentences[0])
        assert ls["ls_type"] == esperado, f"{texto}: {ls['ls_type']} != {esperado}"
    # la diana AA con clítico debe reportar el complejo agrupado
    ls = m.map_sentence_to_ls(nlp("Juan se comió la pizza completa").sentences[0])
    for tok in ("se(", "comió(", "pizza("):
        assert tok in ls["morph_note"], ls["morph_note"]
    assert "(contextual)" in ls["morph_note"]


def test_slow_fallback_sin_cabeza_contextual():
    """Sin models/contextual, predict avisa y usa la léxica sobre emb_ctx."""
    import warnings
    from . import AspectClassifier

    clf = AspectClassifier().load()
    clf.classifiers_ctx = None                     # simula cabeza ausente
    clf.config["fase2"]["usar_complejo_verbal"] = True
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        r = clf.predict("comer", oracion="Juan se comió la pizza",
                        span=[(8, 13), (17, 22)])
    assert r["metodo"] == "contextual"
    assert any("contextual no cargada" in str(x.message) for x in w)


if not RUN_SLOW:
    try:
        import pytest
        test_slow_dianas_aa_y_controles = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_dianas_aa_y_controles)
        test_slow_fallback_sin_cabeza_contextual = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_fallback_sin_cabeza_contextual)
    except ImportError:
        pass


def main():
    rapidos = [test_od_like_deprels_configurable,
               test_embeddings_ctx_alineados,
               test_cabeza_contextual_guardada,
               test_append_only_guard,
               test_higiene_revisar_excluido_del_train,
               test_groupkfold_sin_fuga_por_lema]
    lentos = [test_slow_dianas_aa_y_controles,
              test_slow_fallback_sin_cabeza_contextual]
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
