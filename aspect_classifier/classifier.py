"""Clasificadores por rasgo aspectual: 4 LogisticRegression independientes.

Cada regresor predice P(rasgo=1) a partir del embedding verbal. Las filas
con valor 0.5 en un rasgo (casos ±, p. ej. dyn de algunos States) se
excluyen del entrenamiento de ESE rasgo únicamente: son ambiguas por
anotación, no ruido.
"""

from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["stat", "dyn", "tel", "pun"]


def _make_pipeline() -> Pipeline:
    return Pipeline([
        ("scaler", StandardScaler()),
        ("logreg", LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")),
    ])


class FeatureClassifiers:
    """Conjunto de 4 clasificadores binarios, uno por rasgo aspectual."""

    def __init__(self):
        self.models: dict[str, Pipeline] = {}

    def fit(self, X: np.ndarray, y_features: dict[str, np.ndarray]) -> "FeatureClassifiers":
        """Entrena un regresor por rasgo. y_features[rasgo] admite {0, 0.5, 1};
        los 0.5 se excluyen del entrenamiento de ese rasgo."""
        for feat in FEATURES:
            y = np.asarray(y_features[feat], dtype=float)
            binary = (y == 0) | (y == 1)
            model = _make_pipeline()
            model.fit(X[binary], y[binary].astype(int))
            self.models[feat] = model
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Devuelve matriz (N, 4) con P(rasgo=1) en el orden de FEATURES."""
        X = np.atleast_2d(X)
        cols = [self.models[f].predict_proba(X)[:, 1] for f in FEATURES]
        return np.column_stack(cols)

    def predict_vector(self, x: np.ndarray) -> dict[str, float]:
        """Vector difuso {rasgo: P} para un solo embedding."""
        probs = self.predict_proba(x.reshape(1, -1))[0]
        return {f: round(float(p), 4) for f, p in zip(FEATURES, probs)}

    def save(self, models_dir: Path) -> None:
        models_dir = Path(models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)
        for feat, model in self.models.items():
            joblib.dump(model, models_dir / f"logreg_{feat}.joblib")

    @classmethod
    def load(cls, models_dir: Path) -> "FeatureClassifiers":
        models_dir = Path(models_dir)
        obj = cls()
        for feat in FEATURES:
            path = models_dir / f"logreg_{feat}.joblib"
            if not path.exists():
                raise FileNotFoundError(
                    f"Falta el modelo del rasgo '{feat}': {path}. ¿Ejecutaste train.py?"
                )
            obj.models[feat] = joblib.load(path)
        return obj
