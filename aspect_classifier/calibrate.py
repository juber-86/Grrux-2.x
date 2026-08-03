"""Sub-paso 3E — Recalibración de peso_contextual y umbrales del árbol
contra un split HELD-OUT (estratificado por clase, agrupado por lema).

NO se calibra contra las oraciones diana. El held-out es el primer fold
de StratifiedGroupKFold(5) sobre el set contextual; la cabeza contextual
se reentrena solo con el 80% restante para puntuar sin fuga. La cabeza
léxica (conocimiento por lema, entrenada con la semilla) se usa tal cual.

Uso:
    python -m aspect_classifier.calibrate
"""

import json
from itertools import product
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold

from .classifier import FEATURES, FeatureClassifiers
from .decision_tree import classify
from .extractor import load_config
from .predict import AspectClassifier

PKG_DIR = Path(__file__).parent

PESOS = [0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8]
DYN_THRS = [0.40, 0.45, 0.50, 0.55]
# pun bajo (0.35, 0.40) añadido por el diagnóstico del Frente 1: la mitad
# de la fuga Semelfactive→Activity tiene pun entre 0.35 y el umbral.
PUN_THRS = [0.35, 0.40, 0.45, 0.50]
TEL_THRS = [0.35, 0.40, 0.45, 0.50]


def run():
    config = load_config()
    emb_dir = PKG_DIR / config["data"]["embeddings_dir"]
    X = np.load(emb_dir / "embeddings_ctx.npy")
    with open(emb_dir / "index_ctx.json") as f:
        index = json.load(f)

    y_class = np.array([r["clase"] for r in index])
    grupos = np.array([r["lema"] for r in index])

    skf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    train_idx, held_idx = next(skf.split(X, y_class, groups=grupos))
    assert not set(grupos[train_idx]) & set(grupos[held_idx])
    print(f"Held-out: {len(held_idx)} oraciones, {len(set(grupos[held_idx]))} lemas")

    # Cabeza contextual SIN los lemas del held-out
    y_feats = {f: np.array([r[f] for r in index]) for f in FEATURES}
    ctx_head = FeatureClassifiers().fit(
        X[train_idx], {f: y_feats[f][train_idx] for f in FEATURES})
    probs_ctx = ctx_head.predict_proba(X[held_idx])

    # Cabeza léxica final + embeddings léxicos por lema (cacheados)
    clf = AspectClassifier().load()
    cache: dict[str, np.ndarray] = {}
    probs_lex = np.zeros_like(probs_ctx)
    for j, i in enumerate(held_idx):
        lema = index[i]["lema"]
        if lema not in cache:
            t, p = clf._marco_sintactico(lema)
            emb = clf.extractor.embed_lemma(lema, t, p)
            cache[lema] = clf.classifiers.predict_proba(emb)[0]
        probs_lex[j] = cache[lema]

    y_gold = y_class[held_idx]

    etiquetas = sorted(set(y_gold))

    def evaluar(w: float, dyn_thr: float, pun_thr: float, tel_thr: float):
        """(macro-F1, {clase: F1}) en el held-out para una combinación."""
        thr = {**config.get("decision_tree", {}),
               "dyn": dyn_thr, "pun": pun_thr, "tel": tel_thr}
        blended = (1 - w) * probs_lex + w * probs_ctx
        pred = [classify(dict(zip(FEATURES, v)), thr)["clase"] for v in blended]
        macro = f1_score(y_gold, pred, average="macro", zero_division=0,
                         labels=etiquetas)
        por_clase = dict(zip(etiquetas, f1_score(
            y_gold, pred, average=None, zero_division=0, labels=etiquetas)))
        return macro, por_clase

    resultados = sorted(
        ((*evaluar(w, d, p, t), w, d, p, t)
         for w, d, p, t in product(PESOS, DYN_THRS, PUN_THRS, TEL_THRS)),
        key=lambda r: r[0], reverse=True)

    act_macro, act_pc = evaluar(config["fase2"]["peso_contextual"],
                                config["decision_tree"]["dyn"],
                                config["decision_tree"]["pun"],
                                config["decision_tree"]["tel"])
    print(f"\nConfig actual (w={config['fase2']['peso_contextual']}, "
          f"dyn={config['decision_tree']['dyn']}, pun={config['decision_tree']['pun']}, "
          f"tel={config['decision_tree']['tel']}): macro-F1 = {act_macro:.3f} | "
          f"Semelf={act_pc.get('Semelfactive', 0):.2f} "
          f"State={act_pc.get('State', 0):.2f} "
          f"AA={act_pc.get('Active_Accomplishment', 0):.2f}")

    # Top-N con F1 de las clases débiles a la vista: la config se elige
    # mirando (a) macro-F1, (b) que Semelfactive/State no se hundan,
    # (c) que las frases de medida sigan cruzando a AA (batería aparte).
    print("\nTop 15 (macro | Semelf State AA | w dyn pun tel):")
    for macro, pc, w, d, p, t in resultados[:15]:
        print(f"  {macro:.3f} | Sem={pc.get('Semelfactive', 0):.2f} "
              f"Sta={pc.get('State', 0):.2f} AA={pc.get('Active_Accomplishment', 0):.2f} "
              f"| w={w:.2f} dyn={d:.2f} pun={p:.2f} tel={t:.2f}")
    best = resultados[0]
    print(f"\nMEJOR macro-F1: w={best[2]}, dyn={best[3]}, pun={best[4]}, tel={best[5]} "
          f"({best[0]:.3f} vs actual {act_macro:.3f})")
    return resultados, (act_macro, act_pc)


# ===========================================================================
# Modo --pruebas — CALIBRACIÓN DEL CORROBORADOR VAN VALIN
# ===========================================================================
# Mismo held-out que run() (fold 1 de StratifiedGroupKFold(5, seed 42),
# agrupado por lema). La cabeza contextual se reentrena sin los lemas del
# held-out; la léxica va tal cual; w = fase2.peso_contextual queda FIJO.
# Aquí SOLO se calibra el corroborador: λ per-rasgo y bias_mask de p45.
#
# λ_pun/λ_tel incluyen 0.0 para permitir el OPT-OUT por rasgo (regla dura:
# un rasgo que no mejora queda en 0) y para que la línea base probe-solo
# esté dentro del propio barrido (guardarraíl trivialmente satisfecho).
LAMBDA_PT = [0.0, 0.3, 0.4, 0.5, 0.6, 0.7]        # λ_pun, λ_tel
LAMBDA_STAT = [0.0, 0.1, 0.2]                     # λ_stat
# dyn NO tiene señal (vector_pruebas['dyn'] is None): λ_dyn no altera P_final,
# así que barrerlo es un no-op → se fija en 0.
BIAS_GRID = [round(0.5 * k, 1) for k in range(13)]   # 0.0 … 6.0, paso 0.5

PRUEBAS_CACHE = PKG_DIR / "data" / "pruebas_cache_heldout.json"


def _cargar_cache_pruebas(config: dict, held_lemas_marcos, forzar: bool = False) -> dict:
    """{ 'lema|t|p': {s1, s6, d45} } con el Δ CRUDO de p45 (el bias se aplica
    DESPUÉS, en el barrido). Cacheado a disco: son ~n_lemas × ~5 PLLs del MLM;
    no se recomputan en cada punto del barrido."""
    cache = {}
    if PRUEBAS_CACHE.exists() and not forzar:
        cache = json.loads(PRUEBAS_CACHE.read_text())
    faltan = [lm for lm in held_lemas_marcos
              if f"{lm[0]}|{lm[1]}|{lm[2]}" not in cache]
    if faltan:
        from .pruebas_clase_aspectual import CorroboradorVanValin
        corr = CorroboradorVanValin(cfg=config.get("pruebas", {}))
        saltados = []
        for lema, t, p in faltan:
            try:
                d = corr.evaluar(lema, t, p)["pruebas"]    # carga el MLM
            except Exception as e:
                # El corroborador ABSTIENE en lemas cuyos frames no se pueden
                # construir (p. ej. conjugación no cubierta): ese lema queda
                # sin señal y el blend usa solo el probe para sus oraciones.
                saltados.append((lema, str(e)))
                continue
            cache[f"{lema}|{t}|{p}"] = {
                "s1": d["p1_progresivo"]["score"],         # 1−s1 = stat = pun
                "s6": d["p6_participial"]["score"],        # aporte a tel
                "d45": d["p45_telicidad"]["delta"],        # Δ CRUDO (sin bias)
            }
        PRUEBAS_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
        print(f"Cache de pruebas: +{len(faltan) - len(saltados)} lemas "
              f"→ {PRUEBAS_CACHE.name}")
        if saltados:
            print(f"  corroborador ABSTIENE en {len(saltados)} lema(s) sin frames: "
                  f"{', '.join(l for l, _ in saltados)}")
    return cache


def run_pruebas(forzar_cache: bool = False):
    config = load_config()
    emb_dir = PKG_DIR / config["data"]["embeddings_dir"]
    X = np.load(emb_dir / "embeddings_ctx.npy")
    with open(emb_dir / "index_ctx.json") as f:
        index = json.load(f)

    y_class = np.array([r["clase"] for r in index])
    grupos = np.array([r["lema"] for r in index])
    y_feats = {f: np.array([r[f] for r in index]) for f in FEATURES}

    skf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    train_idx, held_idx = next(skf.split(X, y_class, groups=grupos))
    assert not set(grupos[train_idx]) & set(grupos[held_idx])
    print(f"Held-out: {len(held_idx)} oraciones, {len(set(grupos[held_idx]))} lemas")

    # Cabeza contextual SIN los lemas del held-out (sin fuga)
    ctx_head = FeatureClassifiers().fit(
        X[train_idx], {f: y_feats[f][train_idx] for f in FEATURES})
    probs_ctx = ctx_head.predict_proba(X[held_idx])

    # Cabeza léxica final + marco sintáctico por lema (cacheados)
    clf = AspectClassifier().load()
    cache_lex: dict[str, np.ndarray] = {}
    marco: dict[str, tuple[int, int]] = {}
    probs_lex = np.zeros_like(probs_ctx)
    for j, i in enumerate(held_idx):
        lema = index[i]["lema"]
        if lema not in cache_lex:
            marco[lema] = clf._marco_sintactico(lema)
            emb = clf.extractor.embed_lemma(lema, *marco[lema])
            cache_lex[lema] = clf.classifiers.predict_proba(emb)[0]
        probs_lex[j] = cache_lex[lema]

    w = float(config["fase2"]["peso_contextual"])            # FIJO
    probs_probe = (1 - w) * probs_lex + w * probs_ctx        # (n, 4) = P_probe

    y_gold = y_class[held_idx]
    etiquetas = sorted(set(y_gold))
    thr = config.get("decision_tree", {})
    tau_mask = float(config["pruebas"].get("temperatura_mask", 4.0))
    peso_p6 = float(config["pruebas"].get("peso_p6_en_tel", 0.2))
    fi = {f: k for k, f in enumerate(FEATURES)}              # índice de columna

    # Δ crudos de las pruebas por lema del held-out (cache a disco)
    held_lm = sorted({(index[i]["lema"], *marco[index[i]["lema"]]) for i in held_idx})
    cache_p = _cargar_cache_pruebas(config, held_lm, forzar=forzar_cache)
    keys = [f"{index[i]['lema']}|{marco[index[i]['lema']][0]}|{marco[index[i]['lema']][1]}"
            for i in held_idx]

    def _get(k, campo):
        return cache_p.get(k, {}).get(campo, np.nan)          # NaN = lema sin señal
    s1 = np.array([_get(k, "s1") for k in keys])
    s6 = np.array([_get(k, "s6") for k in keys])
    d45 = np.array([_get(k, "d45") for k in keys])
    tiene = ~np.isnan(s1)                                      # oraciones con pruebas
    n_sin = int((~tiene).sum())
    if n_sin:
        print(f"  {n_sin} oración(es) del held-out sin señal del corroborador "
              f"(abstiene → solo probe en esas filas)")

    def evaluar_config(l_stat, l_tel, l_pun, bias):
        """(macro-F1, {clase:F1}, {rasgo:F1}) del árbol sobre P_final. Las
        oraciones sin señal del corroborador conservan el vector del probe."""
        d = np.where(tiene, d45, 0.0)
        s45 = 1.0 / (1.0 + np.exp(-(d - bias) / tau_mask))    # recentrado
        s6f = np.where(tiene, s6, 0.0)
        tel_p = (1 - peso_p6) * s45 + peso_p6 * s6f
        neg1 = np.where(tiene, 1 - s1, 0.0)                   # stat = pun = 1−s1
        P = probs_probe.copy()
        for f, lam, pv in (("stat", l_stat, neg1), ("tel", l_tel, tel_p),
                           ("pun", l_pun, neg1)):
            blended = (1 - lam) * P[:, fi[f]] + lam * pv
            P[:, fi[f]] = np.where(tiene, blended, P[:, fi[f]])  # abstiene si no hay pruebas
        # dyn: sin señal (None) → columna intacta (λ_dyn = 0 efectivo)
        preds = [classify(dict(zip(FEATURES, row)), thr)["clase"] for row in P]
        macro = f1_score(y_gold, preds, average="macro", zero_division=0, labels=etiquetas)
        por_clase = dict(zip(etiquetas, f1_score(
            y_gold, preds, average=None, zero_division=0, labels=etiquetas)))
        por_rasgo = {}
        for f in ("tel", "pun"):
            g = y_feats[f][held_idx]
            m = (g == 0) | (g == 1)
            pred_f = (P[m, fi[f]] >= float(thr.get(f, 0.5))).astype(int)
            por_rasgo[f] = f1_score(g[m].astype(int), pred_f, zero_division=0)
        return macro, por_clase, por_rasgo

    # Línea base: corroborador APAGADO (todas las λ = 0)
    base_macro, base_pc, base_pf = evaluar_config(0.0, 0.0, 0.0, 0.0)

    # Barrido completo
    barrido = []
    for bias in BIAS_GRID:
        for l_stat in LAMBDA_STAT:
            for l_tel in LAMBDA_PT:
                for l_pun in LAMBDA_PT:
                    macro, pc, pf = evaluar_config(l_stat, l_tel, l_pun, bias)
                    lam = {"stat": l_stat, "dyn": 0.0, "tel": l_tel, "pun": l_pun}
                    barrido.append((macro, pc, pf, lam, bias))
    # macro desc, luego PARSIMONIA (menor Σλ → más ceros), luego menor bias
    barrido.sort(key=lambda r: (-r[0], sum(r[3].values()), r[4]))
    best_macro, best_pc, best_pf, best_lam, best_bias = barrido[0]

    # GUARDARRAÍL DURO: nunca por debajo de probe-solo. λ=0 está en el barrido,
    # así que best_macro ≥ base_macro por construcción; se comprueba.
    if best_macro < base_macro - 1e-9:
        best_lam = {f: 0.0 for f in FEATURES}
        best_bias = 0.0
        best_macro, best_pc, best_pf = base_macro, base_pc, base_pf

    # Opt-out explícito por rasgo: si anular una λ no baja el macro-F1, se anula.
    cambiado = True
    while cambiado:
        cambiado = False
        for f in ("stat", "tel", "pun"):
            if best_lam[f] > 0:
                prueba = dict(best_lam)
                prueba[f] = 0.0
                m = evaluar_config(prueba["stat"], prueba["tel"], prueba["pun"], best_bias)[0]
                if m >= best_macro - 1e-9:
                    best_lam = prueba
                    best_macro, best_pc, best_pf = evaluar_config(
                        best_lam["stat"], best_lam["tel"], best_lam["pun"], best_bias)
                    cambiado = True
    if all(best_lam[f] == 0 for f in FEATURES):
        best_bias = 0.0  # sin corroborador el bias es irrelevante

    def _linea(macro, pc, pf):
        return (f"macro-F1={macro:.3f} | tel_F1={pf['tel']:.2f} pun_F1={pf['pun']:.2f} "
                f"| Semelf={pc.get('Semelfactive', 0):.2f} State={pc.get('State', 0):.2f} "
                f"AA={pc.get('Active_Accomplishment', 0):.2f}")

    print("\n── Corroborador Van Valin: antes/después (held-out) ──")
    print(f"  ANTES (probe-solo, λ=0):  {_linea(base_macro, base_pc, base_pf)}")
    print(f"  DESPUÉS (calibrado):      {_linea(best_macro, best_pc, best_pf)}")
    print(f"  Ganadores: bias_mask={best_bias}  λ={best_lam}")
    guard = "OK" if best_macro >= base_macro - 1e-9 else "¡VIOLADO!"
    print(f"  Guardarraíl (macro ≥ probe-solo): {guard}")

    print("\n── Bloque para config.yaml (sección `pruebas`) ──")
    print(f"  bias_mask: {best_bias}")
    print(f"  peso_p6_en_tel: {peso_p6}")
    print("  lambdas:")
    for f in FEATURES:
        print(f"    {f}: {best_lam[f]}")

    salida = PKG_DIR / "data" / "pruebas_calibration.json"
    salida.write_text(json.dumps({
        "antes": {"macro_f1": base_macro, "por_clase": base_pc, "por_rasgo": base_pf},
        "despues": {"macro_f1": best_macro, "por_clase": best_pc, "por_rasgo": best_pf},
        "ganadores": {"bias_mask": best_bias, "peso_p6_en_tel": peso_p6, "lambdas": best_lam},
        "guardarrail_ok": bool(best_macro >= base_macro - 1e-9),
        "w_fijo": w,
    }, ensure_ascii=False, indent=1, default=float))
    print(f"\nResultados → {salida.name}")
    return barrido, (base_macro, base_pc, base_pf), (best_lam, best_bias)


if __name__ == "__main__":
    import sys
    if "--pruebas" in sys.argv:
        run_pruebas(forzar_cache="--recompute" in sys.argv)
    else:
        run()
