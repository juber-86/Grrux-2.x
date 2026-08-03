"""Árbol de decisión sobre el vector difuso [stat, dyn, tel, pun].

Orden de nodos (por ganancia de información sobre la matriz aspectual):
  1. stat >= umbral -> State (State_Activity si dyn cae en la zona ±)
  2. pun  >= umbral -> Achievement (tel>=umbral) | Semelfactive (tel<umbral)
  3. tel  >= umbral -> Active_Accomplishment (dyn>=umbral) | Accomplishment
  4. dyn  >= umbral -> Activity
  Default          -> clase más cercana por distancia euclidiana al prototipo

La confianza es 1 - d/2, con d = distancia euclidiana del vector al
prototipo de la clase asignada (d in [0, 2] en el hipercubo [0,1]^4).
"""

import numpy as np

from .load_data import CLASS_PROTOTYPES

DEFAULT_THRESHOLDS = {"stat": 0.5, "dyn": 0.5, "tel": 0.5, "pun": 0.5}
# Semiancho de la zona "dyn ≈ 0.5" que dispara State_Activity en el nodo 1.
DEFAULT_DYN_AMBIGUOUS_BAND = 0.15


def _distance(vector: dict[str, float], prototype: list[float]) -> float:
    v = np.array([vector["stat"], vector["dyn"], vector["tel"], vector["pun"]])
    return float(np.linalg.norm(v - np.array(prototype, dtype=float)))


def nearest_prototype(vector: dict[str, float]) -> tuple[str, float]:
    """(clase, distancia) del prototipo más cercano."""
    dists = {cls: _distance(vector, proto) for cls, proto in CLASS_PROTOTYPES.items()}
    cls = min(dists, key=dists.get)
    return cls, dists[cls]


def classify(
    vector: dict[str, float],
    thresholds: dict[str, float] | None = None,
    dyn_ambiguous_band: float = DEFAULT_DYN_AMBIGUOUS_BAND,
) -> dict:
    """Clasifica un vector difuso {stat, dyn, tel, pun} con P in [0,1].

    `thresholds` admite también la clave `dyn_ambiguous_band` (tiene
    prioridad sobre el argumento homónimo), de modo que la sección
    decision_tree de config.yaml puede pasarse entera.

    Devuelve {"clase", "confianza", "regla"}.
    """
    thr = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    dyn_ambiguous_band = thr.pop("dyn_ambiguous_band", dyn_ambiguous_band)
    stat, dyn = vector["stat"], vector["dyn"]
    tel, pun = vector["tel"], vector["pun"]

    if stat >= thr["stat"]:
        if abs(dyn - 0.5) <= dyn_ambiguous_band:
            clase, regla = "State_Activity", "nodo1: stat alto, dyn en zona ±"
        else:
            clase, regla = "State", "nodo1: stat alto"
    elif pun >= thr["pun"]:
        if tel >= thr["tel"]:
            clase, regla = "Achievement", "nodo2: puntual y télico"
        else:
            clase, regla = "Semelfactive", "nodo2: puntual y atélico"
    elif tel >= thr["tel"]:
        if dyn >= thr["dyn"]:
            clase, regla = "Active_Accomplishment", "nodo3: télico y dinámico"
        else:
            clase, regla = "Accomplishment", "nodo3: télico, no dinámico"
    elif dyn >= thr["dyn"]:
        clase, regla = "Activity", "nodo4: dinámico"
    else:
        clase, dist = nearest_prototype(vector)
        return {
            "clase": clase,
            "confianza": round(1 - dist / 2, 4),
            "regla": f"default: prototipo más cercano (d={dist:.3f})",
        }

    # Confianza por cercanía al prototipo de la clase asignada.
    # State_Activity no tiene prototipo propio: se usa el punto medio.
    if clase == "State_Activity":
        proto = [1, 0.5, 0, 0]
    else:
        proto = CLASS_PROTOTYPES[clase]
    dist = _distance(vector, proto)
    return {"clase": clase, "confianza": round(1 - dist / 2, 4), "regla": regla}
