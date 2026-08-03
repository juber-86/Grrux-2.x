"""Script maestro de la Fase 1.

Flujo: dataset limpio -> embeddings RoBERTa-BNE -> 4 LogisticRegression
-> evaluación con cross-validation estratificada (rasgos + clase final
vía árbol de decisión) -> modelos finales en models/.

Uso:
    python -m aspect_classifier.train
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import StratifiedGroupKFold

from .classifier import FEATURES, FeatureClassifiers
from .decision_tree import classify
from .extractor import load_config, run as extract_embeddings

PKG_DIR = Path(__file__).parent
MODELS_DIR = PKG_DIR / "models"


def load_embeddings(config: dict) -> tuple[np.ndarray, list[dict]]:
    emb_dir = PKG_DIR / config["data"]["embeddings_dir"]
    emb_path = emb_dir / "embeddings.npy"
    if not emb_path.exists():
        print("No hay embeddings cacheados; extrayendo con RoBERTa-BNE...")
        return extract_embeddings(config)
    X = np.load(emb_path)
    with open(emb_dir / "index.json") as f:
        index = json.load(f)
    print(f"Embeddings cacheados: {X.shape}")
    return X, index


def cross_validate(X: np.ndarray, index: list[dict], thresholds: dict, n_splits: int = 5):
    """CV estratificada por clase: métricas por rasgo y de clase final."""
    y_class = np.array([r["clase"] for r in index])
    y_feats = {f: np.array([r[f] for r in index]) for f in FEATURES}
    # Agrupar por lema: los duplicados legítimos (p. ej. 'escribir' Activity
    # y Accomplishment) no deben repartirse entre train y test.
    grupos = np.array([r["lema"] for r in index])

    skf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=42)
    feat_f1 = {f: [] for f in FEATURES}
    y_true_all, y_pred_all = [], []

    for train_idx, test_idx in skf.split(X, y_class, groups=grupos):
        clfs = FeatureClassifiers().fit(X[train_idx], {f: y_feats[f][train_idx] for f in FEATURES})
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

    print(f"\n=== Cross-validation estratificada ({n_splits} folds) ===")
    print("\nF1 por rasgo (solo filas con etiqueta binaria):")
    for feat in FEATURES:
        scores = feat_f1[feat]
        print(f"  {feat}: {np.mean(scores):.3f} ± {np.std(scores):.3f}")

    print("\nClase final (rasgos predichos + árbol de decisión):")
    print(classification_report(y_true_all, y_pred_all, zero_division=0))
    return y_true_all, y_pred_all


def train_final(X: np.ndarray, index: list[dict]) -> FeatureClassifiers:
    y_feats = {f: np.array([r[f] for r in index]) for f in FEATURES}
    clfs = FeatureClassifiers().fit(X, y_feats)
    clfs.save(MODELS_DIR)
    meta = {
        "n_train": len(index),
        "features": FEATURES,
        "embedding_dim": int(X.shape[1]),
    }
    with open(MODELS_DIR / "meta.json", "w") as f:
        json.dump(meta, f, indent=1)
    print(f"\nModelos finales guardados en {MODELS_DIR}")
    return clfs


def run():
    config = load_config()
    thresholds = config.get("decision_tree", {})
    X, index = load_embeddings(config)
    cross_validate(X, index, thresholds)
    train_final(X, index)


if __name__ == "__main__":
    run()
