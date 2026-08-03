"""Tests del corroborador Van Valin (pruebas_clase_aspectual).

Ejecutar:
    python -m aspect_classifier.test_pruebas_aspectuales          # puros
    python -m aspect_classifier.test_pruebas_aspectuales --slow   # + MLM real

Los tests @slow usan CONTRASTES RELATIVOS entre verbos (robustos), no
umbrales absolutos: los absolutos dependen de la calibración pendiente.
"""

import os
import sys

from .gen_contextual_sentences import gerundio, participio
from .pruebas_clase_aspectual import construir_frames

RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv


def test_gerundio():
    casos = {"estudiar": "estudiando", "correr": "corriendo",
             "leer": "leyendo", "construir": "construyendo",
             "dormir": "durmiendo", "derretir": "derritiendo",
             "reír": "riendo", "ir": "yendo"}
    for lema, esperado in casos.items():
        assert gerundio(lema) == esperado, (lema, gerundio(lema))


def test_participio():
    casos = {"estudiar": "estudiado", "correr": "corrido",
             "leer": "leído", "caer": "caído", "romper": "roto",
             "abrir": "abierto", "escribir": "escrito",
             "morir": "muerto", "resolver": "resuelto", "hacer": "hecho"}
    for lema, esperado in casos.items():
        assert participio(lema) == esperado, (lema, participio(lema))


def test_frames_transitivo():
    # OD por lema desde el mapa OBJ curado: estudiar → "matemáticas"
    f = construir_frames("estudiar", transitivo=1)
    assert f["p1_progresivo"] == ("Juan está estudiando matemáticas.",
                                  "Juan estudia matemáticas.")
    assert f["p45_telicidad"]["plantilla"] == \
        "Juan estudió matemáticas [MASK] una hora."
    assert f["p45_telicidad"]["candidatos"] == ("en", "durante")
    # p6 usa sujeto genérico "El objeto" (evita concordancia con el OD)
    assert f["p6_participial"][0] == "El objeto está estudiado."


def test_frames_pronominal_enclitico_se():
    # infinitivos con clítico -se (detenerse, volcarse) SE CONJUGAN quitando
    # el enclítico; el rasgo pronominal ya lo marca el marco por separado.
    from .pruebas_clase_aspectual import _lema_base
    assert _lema_base("detenerse") == "detener"
    assert _lema_base("volcarse") == "volcar"
    assert _lema_base("romper") == "romper"          # sin enclítico: intacto
    f = construir_frames("detenerse", transitivo=0, pronominal=1)
    assert f["p1_progresivo"] == ("El objeto se está deteniendo.",
                                  "El objeto se detiene.")
    assert f["p45_telicidad"]["plantilla"] == "El objeto se detuvo [MASK] una hora."
    assert f["p6_participial"][0] == "El objeto está detenido."


def test_frames_transitivo_od_fallback():
    # lema transitivo (conjugable) sin entrada en OBJ → fallback "el objeto"
    from .gen_contextual_sentences import OBJ
    assert "saludar" not in OBJ
    f = construir_frames("saludar", transitivo=1)
    assert f["p1_progresivo"][0] == "Juan está saludando el objeto."


def test_frames_pronominal():
    f = construir_frames("romper", transitivo=1, pronominal=1)
    # marco anticausativo/medio: sujeto paciente + se, sin OD
    assert f["p1_progresivo"] == ("El objeto se está rompiendo.",
                                  "El objeto se rompe.")
    assert f["p6_participial"][0] == "El objeto está roto."


def test_frames_intransitivo():
    f = construir_frames("correr")
    assert f["p1_progresivo"] == ("Juan está corriendo.", "Juan corre.")
    assert f["p6_participial"] == ("Juan está corrido.", "Juan está corriendo.")


# ---------------------------------------------------------------------------
# Unit rápidos con STUB del MLM (sin cargar BERTIN)
# ---------------------------------------------------------------------------
def test_vector_sin_p2p3_y_dyn_none():
    """El vector ya no usa p2/p3 y dyn es None; p2/p3 solo con diagnostico."""
    from .pruebas_clase_aspectual import CorroboradorVanValin

    corr = CorroboradorVanValin()
    corr._contraste_pll = lambda par: (1.0, 0.2)               # s1 = s6 = 0.2
    corr._contraste_mask = lambda plantilla, candidatos: (5.0, 0.9)

    r = corr.evaluar("romper", 1, 1)                            # diagnostico=False
    assert r["vector"]["dyn"] is None
    assert set(r["pruebas"]) == {"p1_progresivo", "p45_telicidad", "p6_participial"}
    assert r["vector"]["pun"] == r["vector"]["stat"] == round(1 - 0.2, 4)
    # tel = (1−0.2)·s45 + 0.2·s6 = 0.8·0.9 + 0.2·0.2
    assert abs(r["vector"]["tel"] - (0.8 * 0.9 + 0.2 * 0.2)) < 1e-6

    r2 = corr.evaluar("romper", 1, 1, diagnostico=True)
    assert "p2_dinamico" in r2["pruebas"] and "p3_ritmo" in r2["pruebas"]


def test_centrado_bias_mask():
    """Con Δ fijo, el veredicto télico/atélico de p45 cambia según bias_mask."""
    from .pruebas_clase_aspectual import _score_p45

    d = 3.0
    telico = _score_p45(d, {"bias_mask": 0.0, "temperatura_mask": 4.0})
    atelico = _score_p45(d, {"bias_mask": 6.0, "temperatura_mask": 4.0})
    assert telico > 0.5 > atelico                              # el bias lo cruza


def test_predict_fast_path_sin_mlm():
    """λ todas 0 → el corroborador NO se instancia (el MLM ni se carga)."""
    import numpy as np
    from . import AspectClassifier

    clf = AspectClassifier().load()

    class _Ext:
        def embed_lemma(self, l, t, p):
            return np.zeros(768, dtype=np.float32)

    clf._extractor = _Ext()
    clf.config["pruebas"]["lambdas"] = {"stat": 0.0, "dyn": 0.0, "tel": 0.0, "pun": 0.0}
    r = clf.predict("romper")
    assert clf._corroborador is None                           # no se tocó el MLM
    assert r["metodo"] == "lexical"
    assert r["vector_pruebas"] is None and r["pruebas_detalle"] is None


def test_predict_blend_stub():
    """Blend per-rasgo con corroborador stub: λ alto sube pun; rasgo None se
    ignora aunque su λ > 0."""
    import numpy as np
    from . import AspectClassifier

    clf = AspectClassifier().load()

    class _Ext:
        def embed_lemma(self, l, t, p):
            return np.zeros(768, dtype=np.float32)

    clf._extractor = _Ext()
    base = clf.predict("romper")["vector"]

    clf.config["pruebas"]["lambdas"] = {"stat": 0.0, "dyn": 0.2, "tel": 0.6, "pun": 0.9}
    clf._pruebas_vec = lambda l, t, p: {
        "vector": {"stat": 0.9, "dyn": None, "tel": 0.95, "pun": 0.99},
        "pruebas": {"p1_progresivo": {"score": 0.01},
                    "p45_telicidad": {"score": 0.9},
                    "p6_participial": {"score": 0.3}},
    }
    r = clf.predict("romper")
    assert r["metodo"] == "lexical+pruebas"
    assert r["vector"]["pun"] >= base["pun"]                   # λ_pun alto sube pun
    assert r["vector"]["dyn"] == base["dyn"]                   # dyn None ignorado (λ_dyn>0)
    assert r["vector_pruebas"]["dyn"] is None
    assert r["pruebas_detalle"] is not None


# ---------------------------------------------------------------------------
# Contrastes reales con el MLM — solo con --slow / RUN_SLOW=1
# ---------------------------------------------------------------------------
def test_slow_contrastes_relativos():
    from .pruebas_clase_aspectual import CorroboradorVanValin

    corr = CorroboradorVanValin()
    estudiar = corr.evaluar("estudiar", transitivo=1)
    correr = corr.evaluar("correr")
    romper = corr.evaluar("romper", transitivo=1, pronominal=1)
    estornudar = corr.evaluar("estornudar")

    # p1 progresivo separa durativos de puntuales (la señal más limpia)
    s1 = {k: r["pruebas"]["p1_progresivo"]["score"]
          for k, r in [("estudiar", estudiar), ("correr", correr),
                       ("romper", romper), ("estornudar", estornudar)]}
    assert s1["estudiar"] > 0.5 and s1["correr"] > 0.5
    assert s1["romper"] < 0.5 and s1["estornudar"] < 0.5

    # pun compuesto: romper/estornudar ≫ estudiar/correr
    assert romper["vector"]["pun"] > 0.5 > estudiar["vector"]["pun"]
    assert estornudar["vector"]["pun"] > 0.5 > correr["vector"]["pun"]

    # telicidad RELATIVA: el cambio de estado supera al proceso atélico
    assert romper["vector"]["tel"] > correr["vector"]["tel"]
    assert romper["vector"]["tel"] > estudiar["vector"]["tel"]

    # participial: resultado en romper ≫ correr (Achievement vs Activity)
    assert romper["pruebas"]["p6_participial"]["score"] > \
        correr["pruebas"]["p6_participial"]["score"]


def test_slow_p45_telicidad_relativa():
    """El Δ CRUDO de p45 ordena la telicidad: el cambio de estado (romper)
    supera al proceso atélico (estudiar). El bias_mask solo desplaza el corte
    absoluto télico/atélico (por eso se calibra), no este orden relativo."""
    from .pruebas_clase_aspectual import CorroboradorVanValin

    corr = CorroboradorVanValin()
    d_rom = corr.evaluar("romper", 1, 1)["pruebas"]["p45_telicidad"]["delta"]
    d_est = corr.evaluar("estudiar", 1)["pruebas"]["p45_telicidad"]["delta"]
    assert d_rom > d_est


def test_slow_blend_sube_pun():
    """Con el corroborador activo, el blend de predict() sube pun en puntuales
    (romper/estornudar), donde el probe lo daba bajo. Requiere BERTIN."""
    from . import AspectClassifier

    clf = AspectClassifier().load()
    clf.config["pruebas"]["lambdas"] = {"stat": 0.0, "dyn": 0.0, "tel": 0.5, "pun": 0.6}
    for lema, t, p in [("romper", 1, 1), ("estornudar", 0, 0)]:
        r = clf.predict(lema)
        assert r["metodo"].endswith("+pruebas")
        assert r["vector_pruebas"]["pun"] > 0.5                 # corroborador: puntual
        assert r["vector"]["pun"] >= r["vector_probe"]["pun"] - 1e-9


_SLOW_TESTS = [test_slow_contrastes_relativos, test_slow_p45_telicidad_relativa,
               test_slow_blend_sube_pun]

if not RUN_SLOW:
    try:
        import pytest
        for _t in _SLOW_TESTS:
            globals()[_t.__name__] = pytest.mark.skipif(
                True, reason="lento: exportar RUN_SLOW=1")(_t)
    except ImportError:
        pass


def main():
    rapidos = [test_gerundio, test_participio, test_frames_transitivo,
               test_frames_pronominal_enclitico_se,
               test_frames_transitivo_od_fallback, test_frames_pronominal,
               test_frames_intransitivo, test_vector_sin_p2p3_y_dyn_none,
               test_centrado_bias_mask, test_predict_fast_path_sin_mlm,
               test_predict_blend_stub]
    tests = rapidos + (_SLOW_TESTS if RUN_SLOW else [])

    fallos = 0
    for t in tests:
        try:
            t()
            print(f"  [OK]   {t.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"  [FAIL] {t.__name__}: {e}")
    if not RUN_SLOW:
        print("  (contrastes reales omitidos; usa --slow)")
    if fallos:
        sys.exit(1)
    print(f"\n{len(tests)} tests pasaron.")


if __name__ == "__main__":
    main()
