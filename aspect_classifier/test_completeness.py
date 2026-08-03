"""Tests de `completeness.py` — Fase LINKING, Etapa L4.

En frío (sin Stanza, sin ud2rrg, sin roBERTa): dicts del mapper y árboles
`ParentedTree` construidos a mano. Las hojas de los árboles son ENTEROS
0-based (`token_id - 1`), igual que produce `ud2rrg.preterminal` -- ver
la nota al respecto en el docstring de `completeness.py`.

Ejecutar:
    python -m aspect_classifier.test_completeness

Compatible con pytest.
"""

import sys

from discodop.tree import ParentedTree

from .completeness import verificar


def _arbol(spec):
    """Construye un ParentedTree a partir de tuplas anidadas
    (label, [hijos]) o (label, hoja_entera)."""
    label, hijos = spec
    if isinstance(hijos, int):
        return ParentedTree(label, [hijos])
    return ParentedTree(label, [_arbol(h) for h in hijos])


# ---------------------------------------------------------------------------
# "Juan comió pizza ayer" -- x1:Juan(id1) x2:pizza(id3), periferia ayer(id4)
# temporal envuelta por yesterday'. Árbol CORRECTO en todo.
#
# Etapa PERIFERIA (2026-07-13): el marco temporal ancla a CENTRO/CORE, no a
# CLÁUSULA (corrección doctrinal de Julian que rompe la decisión L3 --
# "temporal siempre CLAUSE"). Ver prompt_opus48_periferia.md.
# ---------------------------------------------------------------------------
ARBOL_OK = _arbol(("CLAUSE", [
    ("CORE", [
        ("NP", [("N", 0)]),          # Juan, id=1 -> pos 0
        ("NUC", [("V", 1)]),         # comió,  id=2 -> pos 1
        ("NP", [("N", 2)]),          # pizza,  id=3 -> pos 2
        ("ADVP-PERI", [("ADV", 3)]), # ayer,   id=4 -> pos 3 (CENTRO/CORE)
    ]),
]))

LS_OK = {
    "variables": {"x1": "Juan", "x2": "pizza"},
    "id_a_var": {1: "x1", 3: "x2"},
    "core": [{"id": 1, "text": "Juan", "deprel": "nsubj", "macropapel": "Actor"},
            {"id": 3, "text": "pizza", "deprel": "obj", "macropapel": "Undergoer"}],
    "periferia": [{"id": 4, "text": "ayer", "deprel": "advmod", "tipo": "temporal",
                  "estrato": "centro", "case": None, "lemma": "ayer"}],
    "wrappers": [{"capa": "adverbio", "id": 4, "trigger": "ayer",
                 "pred": "yesterday'", "aplicado": True}],
    "actor_implicito": None, "agx": None, "impersonal": False,
}


def test_todo_ok():
    r = verificar(LS_OK, ARBOL_OK)
    assert r["ok"] is True
    estados = {c["estado"] for c in r["checks"]}
    assert estados == {"ok"}
    assert r["resumen"].startswith("Completeness: ✓")
    assert "x1↔NP" in r["resumen"] and "x2↔NP" in r["resumen"]
    assert "yesterday'↔PERI@CORE" in r["resumen"]


def test_sin_arbol():
    r = verificar(LS_OK, None)
    assert r["ok"] is None
    assert r["motivo"] == "sin_arbol"
    assert r["checks"] == []


# ---------------------------------------------------------------------------
# Mismatches: falta_en_arbol / falta_en_ls
# ---------------------------------------------------------------------------
def test_argumento_falta_en_arbol():
    # árbol sin el NP de "pizza" (x2) -- solo Juan y el verbo.
    arbol = _arbol(("CLAUSE", [("CORE", [("NP", [("N", 0)]), ("NUC", [("V", 1)])])]))
    ls = {**LS_OK, "periferia": [], "wrappers": []}
    r = verificar(ls, arbol)
    assert r["ok"] is False
    x2 = next(c for c in r["checks"] if c["elemento"] == "x2")
    assert x2["estado"] == "falta_en_arbol"
    assert "sin constituyente en el árbol" in x2["detalle"]


def test_periferia_wrapped_sin_rama_peri_falta_en_arbol():
    # árbol sin ninguna rama -PERI para "ayer".
    arbol = _arbol(("CLAUSE", [("CORE", [
        ("NP", [("N", 0)]), ("NUC", [("V", 1)]), ("NP", [("N", 2)]),
        ("ADV", 3),   # ayer presente pero SIN sufijo -PERI
    ])]))
    r = verificar(LS_OK, arbol)
    assert r["ok"] is False
    peri = next(c for c in r["checks"] if c["tipo"] == "periferia")
    assert peri["estado"] == "falta_en_arbol"
    assert "PERI@CORE" in peri["detalle"]


def test_periferia_wrapped_estrato_incorrecto():
    # rama -PERI SÍ existe para "ayer", pero cuelga directamente de CLAUSE
    # (fuera de CORE) -- estrato incorrecto (se esperaba CENTRO/CORE).
    arbol = _arbol(("CLAUSE", [
        ("CORE", [
            ("NP", [("N", 0)]), ("NUC", [("V", 1)]), ("NP", [("N", 2)]),
        ]),
        ("ADVP-PERI", [("ADV", 3)]),
    ]))
    r = verificar(LS_OK, arbol)
    assert r["ok"] is False
    peri = next(c for c in r["checks"] if c["tipo"] == "periferia")
    assert peri["estado"] == "falta_en_arbol"
    assert "estrato incorrecto" in peri["detalle"]


def test_agx_falta_en_arbol():
    ls = {**LS_OK, "periferia": [], "wrappers": [],
         "agx": [{"clitico": "le", "fuente": "dativo", "doblado": True,
                 "arg_id": 5, "clitico_id": 2}]}
    # árbol sin nodo AGX en absoluto.
    r = verificar(ls, ARBOL_OK)
    assert r["ok"] is False
    agx_check = next(c for c in r["checks"] if c["tipo"] == "agx")
    assert agx_check["estado"] == "falta_en_arbol"


def test_agx_falta_en_ls():
    # árbol CON nodo AGX pero la LS no reporta agx -- inconsistencia inversa.
    arbol = _arbol(("CLAUSE", [("CORE", [
        ("NUC", [("AGX", 4), ("NUC", [("V", 1)])]),
        ("NP", [("N", 0)]), ("NP", [("N", 2)]),
    ])]))
    ls = {**LS_OK, "periferia": [], "wrappers": []}
    r = verificar(ls, arbol)
    assert r["ok"] is False
    agx_check = next(c for c in r["checks"] if c["tipo"] == "agx")
    assert agx_check["estado"] == "falta_en_ls"


# ---------------------------------------------------------------------------
# Satisfacciones morfológicas -- NUNCA son error (Completeness Constraint)
# ---------------------------------------------------------------------------
def test_pro_drop_no_es_error():
    # "corrió" -- x1 es actor implícito (pro-drop), sin id de token.
    arbol = _arbol(("CLAUSE", [("CORE", [("NUC", [("V", 0)])])]))
    ls = {
        "variables": {"x1": "3sg"}, "id_a_var": {}, "core": [],
        "periferia": [], "wrappers": [],
        "actor_implicito": {"persona": "3", "numero": "sg", "etiqueta": "3sg"},
        "agx": None, "impersonal": False,
    }
    r = verificar(ls, arbol)
    assert r["ok"] is True
    x1 = next(c for c in r["checks"] if c["elemento"] == "x1")
    assert x1["estado"] == "ok"
    assert "morf" in x1["detalle"]


def test_clitico_solo_no_es_error():
    # "Le dije la verdad" -- dativo sin doblar, satisfecho por AGX.
    arbol = _arbol(("CLAUSE", [("CORE", [
        ("NUC", [("AGX", 0), ("NUC", [("V", 1)])]),
        ("NP", [("N", 3)]),   # "verdad"
    ])]))
    ls = {
        "variables": {"x1": "3sg", "x2": "verdad"},
        "id_a_var": {1: "x1", 4: "x2"},
        "core": [{"id": 4, "text": "verdad", "deprel": "obj", "macropapel": "Undergoer"}],
        "periferia": [], "wrappers": [],
        "actor_implicito": None,
        "agx": [{"clitico": "le", "fuente": "dativo", "doblado": False,
                "arg_id": None, "clitico_id": 1}],
        "impersonal": False,
    }
    r = verificar(ls, arbol)
    assert r["ok"] is True
    x1 = next(c for c in r["checks"] if c["elemento"] == "x1")
    assert x1["estado"] == "ok"
    assert "clítico-AGX" in x1["detalle"]
    agx_check = next(c for c in r["checks"] if c["tipo"] == "agx")
    assert agx_check["estado"] == "ok"


def test_impersonal_sin_argumento_esperado():
    arbol = _arbol(("CLAUSE", [("CORE", [("NUC", [("V", 0)])])]))
    ls = {"variables": {}, "id_a_var": {}, "core": [], "periferia": [],
         "wrappers": [], "actor_implicito": None, "agx": None, "impersonal": True}
    r = verificar(ls, arbol)
    assert r["ok"] is True
    assert len(r["checks"]) == 1
    assert r["checks"][0]["estado"] == "ok"
    assert "impersonal" in r["checks"][0]["detalle"]


# ---------------------------------------------------------------------------
# Periferia sin wrapper -- solo se verifica presencia, nunca error
# ---------------------------------------------------------------------------
def test_periferia_sin_wrapper_presente_es_ok():
    arbol = _arbol(("CLAUSE", [("CORE", [
        ("NP", [("N", 0)]), ("NUC", [("V", 1)]),
        ("PP-PERI", [("P", 2), ("NP", [("N", 3)])]),
    ])]))
    ls = {
        "variables": {"x1": "Juan"}, "id_a_var": {1: "x1"},
        "core": [{"id": 1, "text": "Juan", "deprel": "nsubj", "macropapel": "Actor"}],
        "periferia": [{"id": 4, "text": "parque", "deprel": "obl", "tipo": "locativo",
                      "case": "en", "lemma": "parque"}],
        "wrappers": [],   # detectada pero sin wrapper aplicado
        "actor_implicito": None, "agx": None, "impersonal": False,
    }
    r = verificar(ls, arbol)
    assert r["ok"] is True
    peri = next(c for c in r["checks"] if c["tipo"] == "periferia")
    assert peri["estado"] == "ok"


def test_periferia_sin_wrapper_ausente_no_verificable():
    # sin ninguna rama -PERI para "parque" -- no_verificable, NUNCA error.
    arbol = _arbol(("CLAUSE", [("CORE", [("NP", [("N", 0)]), ("NUC", [("V", 1)])])]))
    ls = {
        "variables": {"x1": "Juan"}, "id_a_var": {1: "x1"},
        "core": [{"id": 1, "text": "Juan", "deprel": "nsubj", "macropapel": "Actor"}],
        "periferia": [{"id": 4, "text": "parque", "deprel": "obl", "tipo": "locativo",
                      "case": "en", "lemma": "parque"}],
        "wrappers": [],
        "actor_implicito": None, "agx": None, "impersonal": False,
    }
    r = verificar(ls, arbol)
    assert r["ok"] is True   # no_verificable no cuenta como fallo
    peri = next(c for c in r["checks"] if c["tipo"] == "periferia")
    assert peri["estado"] == "no_verificable"


# ---------------------------------------------------------------------------
# Fase L4.5 §1 — argumento CLAUSAL (ccomp/xcomp/csubj): su filler es el
# propio verbo incrustado, no un NP/PP.
# ---------------------------------------------------------------------------
def test_argumento_clausal_xcomp_ok():
    # "El Congresillo quiere guardar las formas": x2 = "guardar" (xcomp,
    # id=4 -> pos 3), NUC anidado (juntura CORE/CLAUSE subordinada).
    arbol = _arbol(("CLAUSE", [("CORE", [
        ("CORE", [("NP", [("N", 0)]), ("NUC", [("V", 2)])]),                # "Congresillo quiere"
        ("CORE", [("NP", [("N", 4)]), ("NUC", [("V", 3)])]),                # "las formas guardar"
    ])]))
    ls = {
        "variables": {"x1": "Congresillo", "x2": "guardar"},
        "id_a_var": {1: "x1", 4: "x2"},
        "core": [{"id": 1, "text": "Congresillo", "deprel": "nsubj", "macropapel": "Actor"},
                {"id": 4, "text": "guardar", "deprel": "xcomp", "macropapel": "Tema"}],
        "periferia": [], "wrappers": [],
        "actor_implicito": None, "agx": None, "impersonal": False,
    }
    r = verificar(ls, arbol)
    assert r["ok"] is True, r["resumen"]
    x2 = next(c for c in r["checks"] if c["elemento"] == "x2")
    assert x2["estado"] == "ok_clausal"
    assert x2["detalle"] == "x2↔CLÁUSULA"


def test_argumento_no_clausal_no_usa_fallback_clausal():
    # deprel 'obj' (no clausal): si no hay NP/PP, sigue siendo error real,
    # el fallback clausal NO debe enmascararlo.
    arbol = _arbol(("CLAUSE", [("CORE", [("NP", [("N", 0)]), ("NUC", [("V", 1)])])]))
    ls = {
        "variables": {"x1": "Juan", "x2": "pizza"}, "id_a_var": {1: "x1", 3: "x2"},
        "core": [{"id": 1, "text": "Juan", "deprel": "nsubj", "macropapel": "Actor"},
                {"id": 3, "text": "pizza", "deprel": "obj", "macropapel": "Undergoer"}],
        "periferia": [], "wrappers": [],
        "actor_implicito": None, "agx": None, "impersonal": False,
    }
    r = verificar(ls, arbol)
    assert r["ok"] is False
    x2 = next(c for c in r["checks"] if c["elemento"] == "x2")
    assert x2["estado"] == "falta_en_arbol"


# ---------------------------------------------------------------------------
# Fase L4.5 §2 — LDP/PrDP satisface un wrapper temporal (posición dislocada
# izquierda), igual que -PERI@CLAUSE.
# ---------------------------------------------------------------------------
def test_periferia_temporal_ldp_es_ok():
    # "Ayer, Juan corrió": "ayer" (id=1 -> pos 0) cuelga de PrDP, NO -PERI.
    arbol = _arbol(("SENTENCE", [
        ("PrDP", [("ADVP", [("ADV", 0)])]),
        ("CLAUSE", [("CORE", [("NP", [("N", 2)]), ("NUC", [("V", 3)])])]),
    ]))
    ls = {
        "variables": {"x1": "Juan"}, "id_a_var": {3: "x1"},
        "core": [{"id": 3, "text": "Juan", "deprel": "nsubj", "macropapel": "Actor"}],
        "periferia": [{"id": 1, "text": "ayer", "deprel": "advmod", "tipo": "temporal",
                      "case": None, "lemma": "ayer", "destacado_inicial": True}],
        "wrappers": [{"capa": "adverbio", "id": 1, "trigger": "ayer",
                     "pred": "yesterday'", "aplicado": True}],
        "actor_implicito": None, "agx": None, "impersonal": False,
    }
    r = verificar(ls, arbol)
    assert r["ok"] is True, r["resumen"]
    peri = next(c for c in r["checks"] if c["tipo"] == "periferia")
    assert peri["estado"] == "ok"
    assert peri["detalle"] == "yesterday'↔LDP"


def test_periferia_temporal_no_inicial_control_sigue_en_core():
    # Control: "Juan corrió ayer" (no inicial) sigue exigiendo -PERI@CORE
    # (marco temporal, Etapa PERIFERIA); LDP no es un comodín universal.
    r = verificar(LS_OK, ARBOL_OK)
    assert r["ok"] is True
    peri = next(c for c in r["checks"] if c["tipo"] == "periferia")
    assert peri["detalle"] == "yesterday'↔PERI@CORE"


# ---------------------------------------------------------------------------
# Fase L4.5 §3 — agx como LISTA: el conteo debe cuadrar (dativo + se-pasivo
# en la misma cláusula -> 2 nodos AGX, 2 entradas).
# ---------------------------------------------------------------------------
def test_agx_doble_conteo_cuadra_ok():
    # "...a sus cinco miembros se les ha prohibido la salida..." (versión
    # mínima): "se" (id=1, pasivo) + "les" (id=2, dativo) -> 2 AGX.
    arbol = _arbol(("CLAUSE", [("CORE", [
        ("NUC", [("AGX", 0), ("AGX", 1), ("NUC", [("V", 2)])]),
        ("NP", [("N", 3)]),
    ])]))
    ls = {
        "variables": {}, "id_a_var": {},
        "core": [], "periferia": [], "wrappers": [],
        "actor_implicito": None, "impersonal": False,
        "agx": [
            {"clitico": "se", "fuente": "se_pasivo", "doblado": False,
             "arg_id": None, "clitico_id": 1},
            {"clitico": "les", "fuente": "dativo", "doblado": True,
             "arg_id": 4, "clitico_id": 2},
        ],
    }
    r = verificar(ls, arbol)
    assert r["ok"] is True, r["resumen"]
    agx_check = next(c for c in r["checks"] if c["tipo"] == "agx")
    assert agx_check["estado"] == "ok"
    assert agx_check["detalle"] == "AGX✓×2"


def test_agx_conteo_no_cuadra_falta_en_ls():
    # árbol con 2 AGX pero la LS solo trae 1 entrada -- ANTES de L4.5 esto
    # se reportaba como falso "falta_en_ls" incluso cuando SÍ había una
    # entrada (dict único no distinguía "1 de 2" de "0 de 1"); ahora el
    # detalle es explícito sobre el conteo.
    arbol = _arbol(("CLAUSE", [("CORE", [
        ("NUC", [("AGX", 0), ("AGX", 1), ("NUC", [("V", 2)])]),
    ])]))
    ls = {
        "variables": {}, "id_a_var": {}, "core": [], "periferia": [], "wrappers": [],
        "actor_implicito": None, "impersonal": False,
        "agx": [{"clitico": "se", "fuente": "se_pasivo", "doblado": False,
                "arg_id": None, "clitico_id": 1}],
    }
    r = verificar(ls, arbol)
    assert r["ok"] is False
    agx_check = next(c for c in r["checks"] if c["tipo"] == "agx")
    assert agx_check["estado"] == "falta_en_ls"
    assert "1" in agx_check["detalle"] and "2" in agx_check["detalle"]


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    fallos = 0
    for t in tests:
        try:
            t()
            print(f"  [OK]   {t.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"  [FAIL] {t.__name__}: {e}")
    if fallos:
        sys.exit(1)
    print(f"\n{len(tests)} tests pasaron.")


if __name__ == "__main__":
    main()
