"""Frente 1 (Pre-Paso 4) — Diagnóstico de confusiones. SOLO LECTURA:
usa los embeddings cacheados, no reentrena ni toca modelos guardados.

- Predicciones out-of-fold (CV StratifiedGroupKFold por lema, seed 42,
  la misma de train*.py) de AMBAS cabezas → classification_report +
  confusion_matrix, persistidos en models/cv_report.json y
  models/contextual/cv_report.json.
- Análisis de fuga de Semelfactive en la cabeza contextual: a qué clase
  se va cada error y por qué nodo del árbol.

Uso:
    python -m aspect_classifier.diagnose
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import StratifiedGroupKFold

from .classifier import FEATURES, FeatureClassifiers
from .decision_tree import classify
from .extractor import load_config

PKG_DIR = Path(__file__).parent


def oof_predictions(X, index, thresholds):
    """Predicciones out-of-fold con la misma CV agrupada por lema del train."""
    y = np.array([r["clase"] for r in index])
    grupos = np.array([r["lema"] for r in index])
    y_feats = {f: np.array([r[f] for r in index]) for f in FEATURES}
    preds = [None] * len(index)
    detalles = [None] * len(index)

    skf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    for tr, te in skf.split(X, y, groups=grupos):
        head = FeatureClassifiers().fit(X[tr], {f: y_feats[f][tr] for f in FEATURES})
        probs = head.predict_proba(X[te])
        for j, i in enumerate(te):
            vec = dict(zip(FEATURES, (float(p) for p in probs[j])))
            d = classify(vec, thresholds)
            preds[i] = d["clase"]
            detalles[i] = {"vector": {k: round(v, 3) for k, v in vec.items()},
                           "regla": d["regla"]}
    return y, np.array(preds), detalles


def report_head(nombre, X, index, thresholds, out_path: Path):
    y, pred, detalles = oof_predictions(X, index, thresholds)
    labels = sorted(set(y) | set(pred))
    rep = classification_report(y, pred, labels=labels, zero_division=0,
                                output_dict=True)
    cm = confusion_matrix(y, pred, labels=labels)

    print(f"\n{'=' * 64}\nCABEZA {nombre.upper()} — CV out-of-fold "
          f"(GroupKFold por lema, n={len(index)})\n{'=' * 64}")
    print(classification_report(y, pred, labels=labels, zero_division=0))
    ancho = max(len(l) for l in labels)
    print("Matriz de confusión (filas=real, columnas=pred):")
    print(" " * (ancho + 2) + "  ".join(f"{l[:6]:>6}" for l in labels))
    for i, l in enumerate(labels):
        print(f"  {l:<{ancho}} " + "  ".join(f"{v:>6}" for v in cm[i]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"n": len(index), "cv": "StratifiedGroupKFold(5, seed=42) por lema",
                   "thresholds": thresholds, "labels": labels,
                   "confusion_matrix": cm.tolist(),
                   "classification_report": rep}, f, indent=1, ensure_ascii=False)
    print(f"[guardado] {out_path}")
    return y, pred, detalles


def analizar_fuga_semelfactive(index, y, pred, detalles, thresholds):
    print(f"\n{'=' * 64}\nFUGA DE SEMELFACTIVE (cabeza contextual)\n{'=' * 64}")
    errores = [i for i in range(len(y))
               if y[i] == "Semelfactive" and pred[i] != "Semelfactive"]
    total_semel = int((y == "Semelfactive").sum())
    print(f"Semelfactive: {total_semel - len(errores)}/{total_semel} correctas; "
          f"{len(errores)} fugas:\n")

    grupos = defaultdict(list)
    for i in errores:
        grupos[(pred[i], detalles[i]["regla"])].append(i)

    for (a_clase, regla), idxs in sorted(grupos.items(), key=lambda kv: -len(kv[1])):
        print(f"→ {a_clase} vía [{regla}]  ({len(idxs)} casos)")
        for i in idxs:
            v = detalles[i]["vector"]
            print(f"    {index[i]['oracion']:<44} "
                  f"[stat={v['stat']:.2f} dyn={v['dyn']:.2f} "
                  f"tel={v['tel']:.2f} pun={v['pun']:.2f}]")

    pun_thr = thresholds.get("pun", 0.5)
    pun_bajo = [i for i in errores if detalles[i]["vector"]["pun"] < pun_thr]
    a_activity = [i for i in errores if pred[i] == "Activity"]
    a_achievement = [i for i in errores if pred[i] == "Achievement"]

    print(f"\nRESUMEN: {len(pun_bajo)}/{len(errores)} fugas tienen pun < umbral "
          f"({pun_thr}); destinos: Activity={len(a_activity)}, "
          f"Achievement={len(a_achievement)}, "
          f"otros={len(errores) - len(a_activity) - len(a_achievement)}")

    print("\nRECOMENDACIÓN:")
    if len(pun_bajo) >= len(errores) * 0.6 and len(a_activity) >= len(a_achievement):
        print("  Fuga dominante por pun-bajo hacia el nodo dyn (→ Activity):")
        print("  probar umbral pun MÁS BAJO en el barrido del Frente 3 "
              "(añadir pun ∈ {0.35, 0.40} a calibrate.py) y mostrar el trade-off.")
    elif len(a_achievement) > len(a_activity):
        print("  Fuga dominante hacia Achievement (pun alto y tel dudoso): "
              "confusión genuina puntual-con-resultado vs puntual-sin-cambio;")
        print("  necesita MÁS CONTRASTE DE DATOS (pares semelfactivo/achievement), "
              "no un ajuste de umbral.")
    else:
        print("  Patrón mixto: parte se arregla con umbral pun (probar en el "
              "barrido), parte necesita más datos de contraste.")


def run():
    config = load_config()
    thresholds = dict(config.get("decision_tree", {}))
    emb_dir = PKG_DIR / config["data"]["embeddings_dir"]

    # Cabeza léxica
    X_lex = np.load(emb_dir / "embeddings.npy")
    with open(emb_dir / "index.json") as f:
        idx_lex = json.load(f)
    report_head("léxica", X_lex, idx_lex, thresholds,
                PKG_DIR / "models" / "cv_report.json")

    # Cabeza contextual
    X_ctx = np.load(emb_dir / "embeddings_ctx.npy")
    with open(emb_dir / "index_ctx.json") as f:
        idx_ctx = json.load(f)
    y, pred, detalles = report_head("contextual", X_ctx, idx_ctx, thresholds,
                                    PKG_DIR / "models" / "contextual" / "cv_report.json")

    analizar_fuga_semelfactive(idx_ctx, y, pred, detalles, thresholds)


if __name__ == "__main__":
    run()
