"""Sub-paso 2.3 — Entrena la cabeza CONTEXTUAL (4 LogisticRegression sobre
embeddings complex-pooled) y la evalúa con CV estratificada.

La cabeza léxica (models/logreg_*.joblib) NO se toca. La contextual se
guarda en models/contextual/.

Uso:
    python -m aspect_classifier.train_contextual
"""

import json
from pathlib import Path

import numpy as np
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import StratifiedGroupKFold

from .classifier import FEATURES, FeatureClassifiers
from .decision_tree import classify
from .extractor import load_config

PKG_DIR = Path(__file__).parent
MODELS_CTX_DIR = PKG_DIR / "models" / "contextual"


def load_ctx_embeddings(config: dict) -> tuple[np.ndarray, list[dict]]:
    emb_dir = PKG_DIR / config["data"]["embeddings_dir"]
    X = np.load(emb_dir / "embeddings_ctx.npy")
    with open(emb_dir / "index_ctx.json") as f:
        index = json.load(f)
    assert X.shape[0] == len(index), (
        f"embeddings_ctx.npy ({X.shape[0]}) no alineado con index_ctx.json ({len(index)})"
    )
    return X, index


def cross_validate(X: np.ndarray, index: list[dict], thresholds: dict,
                   n_splits: int = 5):
    y_class = np.array([r["clase"] for r in index])
    y_feats = {f: np.array([r[f] for r in index]) for f in FEATURES}
    # CRÍTICO: con varias oraciones por lema, agrupar por lema evita que
    # variantes del mismo verbo caigan a la vez en train y test (fuga).
    grupos = np.array([r["lema"] for r in index])

    skf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=42)
    feat_f1 = {f: [] for f in FEATURES}
    y_true_all, y_pred_all = [], []

    for train_idx, test_idx in skf.split(X, y_class, groups=grupos):
        assert not set(grupos[train_idx]) & set(grupos[test_idx]), "fuga por lema"
        clfs = FeatureClassifiers().fit(
            X[train_idx], {f: y_feats[f][train_idx] for f in FEATURES})
        probs = clfs.predict_proba(X[test_idx])

        for j, feat in enumerate(FEATURES):
            y_test = y_feats[feat][test_idx]
            binary = (y_test == 0) | (y_test == 1)
            if binary.sum() and len(set(y_test[binary])) > 1:
                pred = (probs[binary, j] >= 0.5).astype(int)
                feat_f1[feat].append(f1_score(y_test[binary].astype(int), pred))

        for i, row_idx in enumerate(test_idx):
            vector = dict(zip(FEATURES, probs[i]))
            y_pred_all.append(classify(vector, thresholds)["clase"])
            y_true_all.append(y_class[row_idx])

    print(f"\n=== CV estratificada cabeza CONTEXTUAL ({n_splits} folds, "
          f"{len(index)} oraciones) ===")
    print("\nF1 por rasgo (solo etiquetas binarias):")
    for feat in FEATURES:
        scores = feat_f1[feat]
        print(f"  {feat}: {np.mean(scores):.3f} ± {np.std(scores):.3f}")
    print("\nClase final (rasgos predichos + árbol de decisión):")
    print(classification_report(y_true_all, y_pred_all, zero_division=0))


def train_final(X: np.ndarray, index: list[dict]) -> None:
    y_feats = {f: np.array([r[f] for r in index]) for f in FEATURES}
    clfs = FeatureClassifiers().fit(X, y_feats)
    clfs.save(MODELS_CTX_DIR)
    meta = {
        "n_train": len(index),
        "features": FEATURES,
        "embedding_dim": int(X.shape[1]),
        "receta": "complex_pool",
    }
    with open(MODELS_CTX_DIR / "meta.json", "w") as f:
        json.dump(meta, f, indent=1)
    print(f"\nCabeza contextual guardada en {MODELS_CTX_DIR}")


def run():
    config = load_config()
    X, index = load_ctx_embeddings(config)
    cross_validate(X, index, config.get("decision_tree", {}))
    train_final(X, index)


if __name__ == "__main__":
    run()
