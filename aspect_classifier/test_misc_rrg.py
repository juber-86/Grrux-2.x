"""Tests de misc_rrg.py — Fase LINKING, Etapa L2 (canal MISC).

Ejecutar:
    python -m aspect_classifier.test_misc_rrg          # puros
    python -m aspect_classifier.test_misc_rrg --slow   # + Stanza/BERTIN/ud2rrg

Compatible con pytest (los @slow requieren RUN_SLOW=1).
"""

import os
import sys
import tempfile
from pathlib import Path

from .misc_rrg import anotaciones_misc, escribir_misc_en_conllu, fusionar_misc

RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv


def _ls_base(**over):
    base = {"core": [], "periferia": [], "agx": [], "impersonal": False,
           "actor_implicito": None, "wrappers": [], "id_a_var": {}, "root_id": 1}
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# fusionar_misc
# ---------------------------------------------------------------------------
def test_fusionar_preserva_existente():
    assert fusionar_misc("SpaceAfter=No", {"RRGRole": "CoreArg"}) == \
        "SpaceAfter=No|RRGRole=CoreArg"


def test_fusionar_desde_guion_bajo():
    assert fusionar_misc("_", {"RRGRole": "AGX"}) == "RRGRole=AGX"


def test_fusionar_vacio_da_guion_bajo():
    assert fusionar_misc("_", {}) == "_"
    assert fusionar_misc("", {}) == "_"


def test_fusionar_es_idempotente():
    una_vez = fusionar_misc("_", {"RRGRole": "CoreArg", "RRGVar": "x2"})
    dos_veces = fusionar_misc(una_vez, {"RRGRole": "CoreArg", "RRGVar": "x2"})
    assert una_vez == dos_veces


# ---------------------------------------------------------------------------
# anotaciones_misc
# ---------------------------------------------------------------------------
def test_core_arg_con_var():
    ls = _ls_base(core=[{"id": 4, "text": "regalo", "deprel": "obj",
                        "macropapel": "Undergoer"}],
                  id_a_var={4: "x2"})
    anot = anotaciones_misc(ls)
    assert anot == {4: {"RRGRole": "CoreArg", "RRGMacrorole": "Undergoer",
                        "RRGVar": "x2"},
                    1: {"RRGAnalyzed": "si"}}   # L5 §1: marca en la raíz


def test_periferia_sin_wrapper():
    ls = _ls_base(periferia=[{"id": 5, "text": "vigorosamente", "deprel": "advmod",
                             "tipo": "manera", "estrato": "centro"}])
    anot = anotaciones_misc(ls)
    assert anot == {5: {"RRGRole": "Periphery", "RRGType": "manera",
                        "RRGStratum": "centro"},
                    1: {"RRGAnalyzed": "si"}}


def test_periferia_con_wrapper():
    ls = _ls_base(periferia=[{"id": 8, "text": "parque", "deprel": "obl",
                             "tipo": "locativo", "estrato": "centro"}],
                  wrappers=[{"capa": "locativo", "id": 8, "trigger": "parque",
                            "pred": "be-in'", "aplicado": True}])
    anot = anotaciones_misc(ls)
    assert anot == {8: {"RRGRole": "Periphery", "RRGType": "locativo",
                        "RRGStratum": "centro", "RRGWrap": "be-in"},
                    1: {"RRGAnalyzed": "si"}}


def test_wrapper_no_aplicado_no_se_filtra_como_wrap():
    """Un wrapper detectado pero NO aplicado (ya/todavía) no debe aparecer
    como RRGWrap."""
    ls = _ls_base(periferia=[{"id": 3, "text": "ya", "deprel": "advmod",
                             "tipo": "temporal", "estrato": "centro"}],
                  wrappers=[{"capa": "temporal", "id": 3, "trigger": "ya",
                            "pred": None, "aplicado": False,
                            "razon": "sin_wrapper"}])
    anot = anotaciones_misc(ls)
    assert anot == {3: {"RRGRole": "Periphery", "RRGType": "temporal",
                        "RRGStratum": "centro"},
                    1: {"RRGAnalyzed": "si"}}


def test_agx_doblado():
    ls = _ls_base(agx=[{"clitico": "Le", "rasgos": "3sg-dat", "fuente": "dativo",
                       "doblado": True, "arg_id": 6, "clitico_id": 1}],
                  id_a_var={6: "x3"})
    anot = anotaciones_misc(ls)
    assert anot == {1: {"RRGRole": "AGX", "RRGDoblado": "si", "RRGArgVar": "x3",
                        "RRGAgxFuente": "dativo", "RRGAnalyzed": "si"}}


def test_agx_sin_doblar_sin_argvar():
    ls = _ls_base(agx=[{"clitico": "Le", "rasgos": "3sg-dat", "fuente": "dativo",
                       "doblado": False, "arg_id": None, "clitico_id": 1}])
    anot = anotaciones_misc(ls)
    assert anot == {1: {"RRGRole": "AGX", "RRGDoblado": "no",
                        "RRGAgxFuente": "dativo", "RRGAnalyzed": "si"}}


def test_agx_doble_dos_tokens_distintos():
    """L4.5 §3: dativo + se-pasivo en la misma cláusula -> dos entradas AGX,
    cada una en su propio token."""
    ls = _ls_base(agx=[
        {"clitico": "les", "rasgos": "3pl-dat", "fuente": "dativo",
         "doblado": False, "arg_id": None, "clitico_id": 2},
        {"clitico": "se", "rasgos": "se-pasivo", "fuente": "se_pasivo",
         "doblado": False, "arg_id": None, "clitico_id": 1},
    ])
    anot = anotaciones_misc(ls)
    assert anot[1] == {"RRGRole": "AGX", "RRGDoblado": "no",
                       "RRGAgxFuente": "se_pasivo", "RRGAnalyzed": "si"}
    assert anot[2] == {"RRGRole": "AGX", "RRGDoblado": "no", "RRGAgxFuente": "dativo"}


def test_impersonal_en_root():
    ls = _ls_base(impersonal=True, root_id=1)
    anot = anotaciones_misc(ls)
    assert anot == {1: {"RRGRole": "Impersonal", "RRGAnalyzed": "si"}}


def test_actor_implicito_en_root():
    ls = _ls_base(actor_implicito={"persona": "3", "numero": "sg", "etiqueta": "3sg"},
                  root_id=2)
    anot = anotaciones_misc(ls)
    assert anot == {2: {"RRGImplicitActor": "3sg", "RRGAnalyzed": "si"}}


def test_impersonal_y_actor_implicito_son_mutuamente_excluyentes():
    """impersonal=True gana; no debería anotar ambas claves en el mismo token
    (un verbo impersonal no tiene actor implícito real)."""
    ls = _ls_base(impersonal=True, actor_implicito={"persona": "3", "numero": "sg",
                                                    "etiqueta": "3sg"}, root_id=1)
    anot = anotaciones_misc(ls)
    assert anot == {1: {"RRGRole": "Impersonal", "RRGAnalyzed": "si"}}


def test_dict_vacio_sin_ls_type_no_crashea():
    """Robustez ante el dict reducido de la rama copulativa/_empty_ls (sin
    core/periferia/agx/...): no debe lanzar, debe devolver {}."""
    assert anotaciones_misc({"ls_type": "state"}) == {}


def test_sin_evidencia_solo_marca_raiz():
    """L5 §1: sin core/periferia/agx, la raíz igual recibe RRGAnalyzed=si
    (identifica el .conllu como analizado por gruxx para subordinar el
    fallback de clíticos de ud2rrg)."""
    assert anotaciones_misc(_ls_base()) == {1: {"RRGAnalyzed": "si"}}


# ---------------------------------------------------------------------------
# escribir_misc_en_conllu — round-trip
# ---------------------------------------------------------------------------
CONLLU_FIXTURE = """# sent_id = 1
# text = Juan corrió en el parque
1\tJuan\tJuan\tPROPN\t_\t_\t2\tnsubj\t_\t_
2\tcorrió\tcorrer\tVERB\t_\t_\t0\troot\t_\t_
3\ten\ten\tADP\t_\t_\t5\tcase\t_\t_
4\tel\tel\tDET\t_\t_\t5\tdet\t_\t_
5\tparque\tparque\tNOUN\t_\t_\t2\tobl\t_\tSpaceAfter=No

"""


def test_round_trip_escribe_y_preserva_misc_existente():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "t.conllu"
        path.write_text(CONLLU_FIXTURE, encoding="utf-8")

        anot = [{5: {"RRGRole": "Periphery", "RRGType": "locativo",
                    "RRGWrap": "be-in"}}]
        escribir_misc_en_conllu(str(path), anot)

        lineas = path.read_text(encoding="utf-8").splitlines()
        fila_parque = next(l for l in lineas if l.startswith("5\t"))
        cols = fila_parque.split("\t")
        assert cols[9] == "SpaceAfter=No|RRGRole=Periphery|RRGType=locativo|RRGWrap=be-in"
        # las demás filas quedan intactas
        fila_juan = next(l for l in lineas if l.startswith("1\t"))
        assert fila_juan.split("\t")[9] == "_"


def test_round_trip_multiword_no_se_toca():
    conllu = ("# sent_id = 1\n# text = x\n"
             "1-2\tal\t_\t_\t_\t_\t_\t_\t_\t_\n"
             "1\ta\ta\tADP\t_\t_\t3\tcase\t_\t_\n"
             "2\tel\tel\tDET\t_\t_\t3\tdet\t_\t_\n"
             "3\tfoo\tfoo\tNOUN\t_\t_\t0\troot\t_\t_\n\n")
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "t.conllu"
        path.write_text(conllu, encoding="utf-8")
        escribir_misc_en_conllu(str(path), [{1: {"RRGRole": "CoreArg"}}])
        lineas = path.read_text(encoding="utf-8").splitlines()
        fila_mwt = next(l for l in lineas if l.startswith("1-2\t"))
        assert fila_mwt.split("\t")[9] == "_"   # sin tocar


def test_escribir_sin_anotaciones_no_cambia_nada():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "t.conllu"
        path.write_text(CONLLU_FIXTURE, encoding="utf-8")
        original = path.read_text(encoding="utf-8")
        escribir_misc_en_conllu(str(path), [{}])
        assert path.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# Integración (Stanza + BERTIN + ud2rrg) — solo con --slow / RUN_SLOW=1
# ---------------------------------------------------------------------------
def test_slow_pipeline_completo_y_gating_misc():
    """Antes de L3, ud2rrg.py ignoraba MISC por completo (árbol con y sin
    MISC eran byte-idénticos). Desde L3 (`ud2rrg.py`, capa 'es'), el MISC
    SÍ se lee para anclar la periferia por estrato (peri() + RRGType) — ese
    es justamente el punto de L3, ver prompt_opus48_linking_L3.md §4. Este
    test ahora verifica lo contrario de antes: con MISC el PP queda
    marcado -PERI (bajo CORE, por ser locativo), sin MISC el árbol vuelve al
    comportamiento heredado (evidencia de que el gating es real, no que
    ud2rrg ignore MISC)."""
    import stanza
    from stanza.utils.conll import CoNLL

    import gruxx_ai1 as g

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    # 1) con MISC (pipeline real completo)
    res = g.procesar_oracion(nlp, "Juan corrió en el parque")
    arbol_con_misc = g._extraer_arbol(res["stdout"])
    conllu_con_misc = open(g.CONLLU_PATH, encoding="utf-8").read()
    assert "RRGRole=Periphery" in conllu_con_misc
    assert "RRGWrap=be-in" in conllu_con_misc
    assert "PP-PERI" in arbol_con_misc

    # 2) sin ninguna metadata (ni comentarios rrg_ ni MISC) — baseline
    doc = nlp("Juan corrió en el parque")
    open(g.CONLLU_PATH, "w", encoding="utf-8").close()
    CoNLL.write_doc2conll(doc, g.CONLLU_PATH)
    g.limpiar_conllu_stanza(g.CONLLU_PATH)
    stdout_sin, _ = g.correr_ud2rrg(g.CONLLU_PATH)
    arbol_sin_misc = g._extraer_arbol(stdout_sin)

    assert "PP-PERI" not in arbol_sin_misc
    assert arbol_con_misc != arbol_sin_misc, \
        "L3: con MISC (RRGRole=Periphery) el PP debe llevar -PERI; sin MISC, comportamiento heredado"

    # impersonal: RRGRole=Impersonal en la raíz
    res_llueve = g.procesar_oracion(nlp, "llueve")
    conllu_llueve = open(g.CONLLU_PATH, encoding="utf-8").read()
    assert "RRGRole=Impersonal" in conllu_llueve

    # pro-drop: RRGImplicitActor en la raíz
    res_corrio = g.procesar_oracion(nlp, "corrió")
    conllu_corrio = open(g.CONLLU_PATH, encoding="utf-8").read()
    assert "RRGImplicitActor=3sg" in conllu_corrio


if not RUN_SLOW:
    try:
        import pytest
        test_slow_pipeline_completo_y_gating_misc = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_pipeline_completo_y_gating_misc)
    except ImportError:
        pass


def main():
    rapidos = [
        test_fusionar_preserva_existente, test_fusionar_desde_guion_bajo,
        test_fusionar_vacio_da_guion_bajo, test_fusionar_es_idempotente,
        test_core_arg_con_var, test_periferia_sin_wrapper,
        test_periferia_con_wrapper, test_wrapper_no_aplicado_no_se_filtra_como_wrap,
        test_agx_doblado, test_agx_sin_doblar_sin_argvar,
        test_impersonal_en_root, test_actor_implicito_en_root,
        test_impersonal_y_actor_implicito_son_mutuamente_excluyentes,
        test_dict_vacio_sin_ls_type_no_crashea, test_sin_evidencia_solo_marca_raiz,
        test_round_trip_escribe_y_preserva_misc_existente,
        test_round_trip_multiword_no_se_toca,
        test_escribir_sin_anotaciones_no_cambia_nada,
    ]
    tests = rapidos + ([test_slow_pipeline_completo_y_gating_misc] if RUN_SLOW else [])

    fallos = 0
    for t in tests:
        try:
            t()
            print(f"  [OK]   {t.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"  [FAIL] {t.__name__}: {e}")
    if not RUN_SLOW:
        print("  (integración omitida; usa --slow)")
    if fallos:
        sys.exit(1)
    print(f"\n{len(tests)} tests pasaron.")


if __name__ == "__main__":
    main()
