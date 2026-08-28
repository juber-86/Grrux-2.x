"""Tests de la capa española de ud2rrg.py — Fase LINKING, Etapa L3.

Ejecutar:
    python -m aspect_classifier.test_ud2rrg_es          # puros
    python -m aspect_classifier.test_ud2rrg_es --slow   # + Stanza/ud2rrg real

Compatible con pytest (los @slow requieren RUN_SLOW=1). A diferencia de las
demás suites del proyecto, esta NO es "en frío": ud2rrg.py opera sobre
`ParentedTree`/`UDNode` reales (discodop + conllu), así que las 4 fijaciones
ancladas (a-d) corren el pipeline real (Stanza + MISC + ud2rrg, "como lo
hace GRRux") y hacen aserciones ESTRUCTURALES sobre el árbol en memoria
(`.parent.label`), no sobre el ASCII-art. Las fijaciones (e) y (f) son
rápidas: (e) solo lee/limpia un `.conllu` estático, (f) construye un
fixture UD a mano.
"""

import io
import os
import sys
from pathlib import Path

RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv

REPO_ROOT = Path(__file__).resolve().parent.parent
ANCORA_DEV = (REPO_ROOT / "treebanks" / "spanish" / "UD_Spanish-AnCora"
             / "es_ancora-ud-dev.conllu")


def _find(tree, label):
    return next((t for t in tree.subtrees() if t.label == label), None)


# ---------------------------------------------------------------------------
# (e) gold AnCora crudo vs limpiado — rápido, sin Stanza (lee un .conllu
# estático del treebank ya descargado con descargar_treebanks_es.sh)
# ---------------------------------------------------------------------------
def test_gold_ancora_crudo_convierte_igual_que_limpiado():
    if not ANCORA_DEV.exists():
        import pytest
        pytest.skip(f"treebank no disponible en {ANCORA_DEV} "
                    "(correr descargar_treebanks_es.sh)")

    import copy

    import ud2rrg
    from conllu import parse_tree_incr

    bloques = ANCORA_DEV.read_text(encoding="utf-8").strip().split("\n\n")
    muestra = "\n\n".join(bloques[:20]) + "\n"

    with io.StringIO(muestra) as f:
        arboles_crudo = list(parse_tree_incr(f))

    # versión "limpiada": XPOS -> _ en cada token (mismo efecto que
    # limpiar_conllu_stanza en el pipeline real; no se usa aquí para no
    # depender de grrux_ai1/Stanza en un test rápido)
    limpio_txt = []
    for linea in muestra.split("\n"):
        if linea.startswith("#") or "\t" not in linea:
            limpio_txt.append(linea)
        else:
            cols = linea.split("\t")
            if len(cols) > 4:
                cols[4] = "_"
            limpio_txt.append("\t".join(cols))
    with io.StringIO("\n".join(limpio_txt)) as f:
        arboles_limpio = list(parse_tree_incr(f))

    assert len(arboles_crudo) == 20

    convertidas_crudo = convertidas_limpio = 0
    diffs = []
    for t_crudo, t_limpio in zip(arboles_crudo, arboles_limpio):
        try:
            r_crudo = str(ud2rrg.transform(copy.deepcopy(t_crudo), "es", layer="SENTENCE"))
            convertidas_crudo += 1
        except Exception:
            r_crudo = None
        try:
            r_limpio = str(ud2rrg.transform(copy.deepcopy(t_limpio), "es", layer="SENTENCE"))
            convertidas_limpio += 1
        except Exception:
            r_limpio = None
        if r_crudo != r_limpio:
            diffs.append((r_crudo, r_limpio))

    assert convertidas_crudo > 0, "gold crudo (XPOS intacto): 0 conversiones (bug pre-L3)"
    assert convertidas_crudo == convertidas_limpio
    assert diffs == [], "crudo y limpiado deben producir el mismo árbol por oración"


# ---------------------------------------------------------------------------
# (f) gating: sin MISC, o lengua != 'es', el árbol no cambia — rápido, sin
# Stanza (fixture UD a mano, MISC inyectado directamente en el .conllu)
# ---------------------------------------------------------------------------
_EN_SIN_MISC = """# sent_id = 1
# text = Peter ran in the park yesterday.
1\tPeter\tPeter\tPROPN\tNNP\tNumber=Sing\t2\tnsubj\t_\t_
2\tran\trun\tVERB\tVBD\tMood=Ind|Tense=Past|VerbForm=Fin\t0\troot\t_\t_
3\tin\tin\tADP\tIN\t_\t5\tcase\t_\t_
4\tthe\tthe\tDET\tDT\tDefinite=Def|PronType=Art\t5\tdet\t_\t_
5\tpark\tpark\tNOUN\tNN\tNumber=Sing\t2\tobl\t_\t_
6\tyesterday\tyesterday\tADV\tRB\t_\t2\tadvmod\t_\tSpaceAfter=No
7\t.\t.\tPUNCT\t.\t_\t2\tpunct\t_\t_

"""

_EN_CON_MISC = _EN_SIN_MISC.replace(
    "5\tpark\tpark\tNOUN\tNN\tNumber=Sing\t2\tobl\t_\t_",
    "5\tpark\tpark\tNOUN\tNN\tNumber=Sing\t2\tobl\t_\t"
    "RRGRole=Periphery|RRGType=locativo|RRGWrap=be-in",
).replace(
    "6\tyesterday\tyesterday\tADV\tRB\t_\t2\tadvmod\t_\tSpaceAfter=No",
    "6\tyesterday\tyesterday\tADV\tRB\t_\t2\tadvmod\t_\t"
    "SpaceAfter=No|RRGRole=Periphery|RRGType=temporal|RRGWrap=yesterday",
)


def test_gating_lengua_no_es_ignora_misc():
    """L3 solo cambia comportamiento para language=='es'. Fixture inglesa
    CON marcas MISC (RRGRole=Periphery, igual que produciría la Etapa 1
    para español) debe dar el MISMO árbol que sin ellas — evidencia del
    gating, sin necesitar Stanza ni una copia congelada de ud2rrg.py."""
    import ud2rrg
    from conllu import parse_tree_incr

    with io.StringIO(_EN_SIN_MISC) as f:
        arbol_sin = ud2rrg.transform(next(parse_tree_incr(f)), "en", layer="SENTENCE")
    with io.StringIO(_EN_CON_MISC) as f:
        arbol_con = ud2rrg.transform(next(parse_tree_incr(f)), "en", layer="SENTENCE")

    # byte-identico completo: el gating es por lengua, MISC no mueve nada
    assert str(arbol_sin) == str(arbol_con)
    # PP-PERI solo existe con es+MISC (ver test_gating_es_sin_misc_no_cambia
    # y test_slow_l3_fijaciones_ancladas/b); en ingles el 'obl' de "park"
    # nunca lleva -PERI (is_marked_as_argument es un stub que siempre da
    # True, comportamiento heredado, ajeno a L3).
    assert _find(arbol_con, "PP-PERI") is None
    # ADVP-PERI SI existe para "yesterday" (peri() ya se llamaba sin
    # condicion en el default de advmod, para cualquier lengua, desde antes
    # de L3) pero su capa no cambia: sigue bajo CORE, nunca sube a CLAUSE.
    advp = _find(arbol_con, "ADVP-PERI")
    assert advp is not None
    assert advp.parent.label == "CORE"


def test_gating_es_sin_misc_no_cambia():
    """Con language=='es' pero SIN marcas MISC, ud2rrg no debe adivinar: el
    anclaje por estrato (CLAUSE para temporal) no dispara sin RRGType, y el
    'obl' de "park" (sin marcar) no gana -PERI (comportamiento heredado,
    is_marked_as_argument sigue siendo un stub que da True)."""
    import ud2rrg
    from conllu import parse_tree_incr

    with io.StringIO(_EN_SIN_MISC) as f:
        arbol_es_sin_misc = ud2rrg.transform(next(parse_tree_incr(f)), "es", layer="SENTENCE")
    assert _find(arbol_es_sin_misc, "PP-PERI") is None
    advp = _find(arbol_es_sin_misc, "ADVP-PERI")
    assert advp is not None
    assert advp.parent.label == "CORE"


# ---------------------------------------------------------------------------
# L4 §3.1 — obl:arg bajo cabeza NOMINAL (nominalizaciones): mismo dispatch
# MISC-primero/fallback-es que L3 añadió a transform_V, replicado en
# transform_N. Fixture a mano, rápido (sin Stanza).
# ---------------------------------------------------------------------------
_NOMINALIZACION_OBL_ARG = """# sent_id = 1
# text = la entrega del regalo a María
1\tla\tel\tDET\t_\tDefinite=Def|Gender=Fem|Number=Sing\t2\tdet\t_\t_
2\tentrega\tentrega\tNOUN\t_\tGender=Fem|Number=Sing\t0\troot\t_\t_
3\tde\tde\tADP\t_\t_\t4\tcase\t_\t_
4\tel\tel\tDET\t_\tDefinite=Def|Gender=Masc|Number=Sing\t5\tdet\t_\t_
5\tregalo\tregalo\tNOUN\t_\tGender=Masc|Number=Sing\t2\tnmod\t_\t_
6\ta\ta\tADP\t_\t_\t7\tcase\t_\t_
7\tMaría\tMaría\tPROPN\t_\t_\t2\tobl:arg\t_\t_

"""


def test_nominalizacion_obl_arg_bajo_noun_convierte():
    """Antes de L4, 'obl:arg' no estaba en el dispatch de transform_N (solo
    transform_V lo tenía, desde L3): la oración entera fallaba con
    NotHandled en el hijo 'María'. L4 replica el mismo dispatch
    MISC-primero/fallback-es. Sin MISC inyectado, el fallback trata el
    obl:arg como CoreArg (mismo comportamiento por defecto que
    transform_V)."""
    import ud2rrg
    from conllu import parse_tree_incr

    with io.StringIO(_NOMINALIZACION_OBL_ARG) as f:
        tree = ud2rrg.transform(next(parse_tree_incr(f)), "es", layer="SENTENCE")

    # "María" debe aparecer como NP/PP argumental (no perderse, no AGX: no
    # es clítico), colgando de CORE_N (fallback CoreArg de transform_N).
    pp = _find(tree, "PP")
    assert pp is not None, "se esperaba un PP para 'a María'"
    assert _find(tree, "AGX") is None, "'María' no es clítico, no debe generar AGX"


def test_gating_no_es_obl_arg_bajo_noun_sigue_nothandled():
    """Mismo régimen que el resto de L3/L4: gated language=='es'. Para
    otra lengua, 'obl:arg' bajo NOUN sigue sin dispatch (comportamiento
    previo a L4, intacto) -> NotHandled."""
    import ud2rrg
    from conllu import parse_tree_incr

    with io.StringIO(_NOMINALIZACION_OBL_ARG) as f:
        udtree = next(parse_tree_incr(f))
    try:
        ud2rrg.transform(udtree, "en", layer="SENTENCE")
        assert False, "se esperaba NotHandled para obl:arg bajo NOUN en 'en'"
    except Exception as e:
        assert type(e).__name__ == "NotHandled"


# ---------------------------------------------------------------------------
# L4 §3.2 — "se" reflejo-pasivo/impersonal (expl:pass/expl:impers) -> AGX
# bajo NUC. Fixtures a mano (estilo gold AnCora): con Stanza real estas dos
# frases concretas no siempre reproducen estos deprels exactos (ver
# test_slow_guard_frecuencia_postverbal_anclado_clause para un hallazgo
# similar con el guard de frecuencia) -- el dispatch se valida aquí contra
# el deprel de la especificación (gold), que es lo que mide kpi_linking.py.
# ---------------------------------------------------------------------------
_SE_PASIVA_REFLEJA = """# sent_id = 1
# text = Se venden casas
1\tSe\tél\tPRON\t_\tCase=Acc|Person=3|PronType=Prs|Reflex=Yes\t2\texpl:pass\t_\t_
2\tvenden\tvender\tVERB\t_\tMood=Ind|Number=Plur|Person=3|Tense=Pres|VerbForm=Fin\t0\troot\t_\t_
3\tcasas\tcasa\tNOUN\t_\tGender=Fem|Number=Plur\t2\tnsubj:pass\t_\t_

"""

_SE_IMPERSONAL = """# sent_id = 1
# text = Se vive bien
1\tSe\tél\tPRON\t_\tCase=Acc|Person=3|PronType=Prs|Reflex=Yes\t2\texpl:impers\t_\t_
2\tvive\tvivir\tVERB\t_\tMood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin\t0\troot\t_\t_
3\tbien\tbien\tADV\t_\t_\t2\tadvmod\t_\t_

"""


def test_se_pasiva_refleja_agx_y_nsubj_pass_como_np():
    """'Se venden casas': el clítico 'se' (expl:pass) -> AGX bajo NUC;
    'casas' (nsubj:pass) sigue como NP argumento del CORE -- Undergoer,
    dispatch preexistente de L3, sin tocar (decisión de Julian: los
    clíticos se enlazan a AGX, pendiente de validación teórica, ver
    CHECKPOINT_L4.md)."""
    import ud2rrg
    from conllu import parse_tree_incr

    with io.StringIO(_SE_PASIVA_REFLEJA) as f:
        tree = ud2rrg.transform(next(parse_tree_incr(f)), "es", layer="SENTENCE")

    agx = _find(tree, "AGX")
    assert agx is not None, "se esperaba AGX para el 'se' pasivo-reflejo"
    assert agx.parent.label == "NUC"
    np = _find(tree, "NP")
    assert np is not None, "se esperaba NP para 'casas' (nsubj:pass)"


def test_se_impersonal_agx():
    """'Se vive bien': el clítico 'se' (expl:impers) -> AGX bajo NUC; sin
    sujeto sintáctico (impersonal), 'bien' es periferia."""
    import ud2rrg
    from conllu import parse_tree_incr

    with io.StringIO(_SE_IMPERSONAL) as f:
        tree = ud2rrg.transform(next(parse_tree_incr(f)), "es", layer="SENTENCE")

    agx = _find(tree, "AGX")
    assert agx is not None, "se esperaba AGX para el 'se' impersonal"
    assert agx.parent.label == "NUC"


def test_gating_no_es_se_pasiva_sigue_nothandled():
    """Gating: para otra lengua, expl:pass/expl:impers siguen sin dispatch
    (comportamiento previo a L4, intacto)."""
    import ud2rrg
    from conllu import parse_tree_incr

    with io.StringIO(_SE_PASIVA_REFLEJA) as f:
        udtree = next(parse_tree_incr(f))
    try:
        ud2rrg.transform(udtree, "en", layer="SENTENCE")
        assert False, "se esperaba NotHandled para expl:pass en 'en'"
    except Exception as e:
        assert type(e).__name__ == "NotHandled"


# ---------------------------------------------------------------------------
# L4.5 §2 — LDP MISC-gated: cubre el hueco de precedes_subject() (heurística
# genérica preexistente) cuando NO hay sujeto sintáctico que comparar (p.ej.
# pro-drop). Fixture a mano: "Ayer, corrió" (sin sujeto).
# ---------------------------------------------------------------------------
_AYER_PRODROP_SIN_MISC = """# sent_id = 1
# text = Ayer, corrió
1\tAyer\tayer\tADV\t_\t_\t3\tadvmod\t_\t_
2\t,\t,\tPUNCT\t_\t_\t1\tpunct\t_\t_
3\tcorrió\tcorrer\tVERB\t_\tMood=Ind|Number=Sing|Person=3|Tense=Past\t0\troot\t_\t_

"""

_AYER_PRODROP_CON_MISC = _AYER_PRODROP_SIN_MISC.replace(
    "1\tAyer\tayer\tADV\t_\t_\t3\tadvmod\t_\t_",
    "1\tAyer\tayer\tADV\t_\t_\t3\tadvmod\t_\t"
    "RRGRole=Periphery|RRGType=temporal|RRGWrap=yesterday|RRGDetached=si",
)


def test_ldp_misc_gated_cubre_prodrop_sin_precedes_subject():
    """Sin sujeto sintáctico (pro-drop), precedes_subject() nunca dispara
    (no hay hermano nsubj que comparar) -- sin el enrutado MISC-gated de
    L4.5, 'Ayer' caería a -PERI@CLAUSE en vez de LDP/PrDP."""
    import ud2rrg
    from conllu import parse_tree_incr

    with io.StringIO(_AYER_PRODROP_CON_MISC) as f:
        tree = ud2rrg.transform(next(parse_tree_incr(f)), "es", layer="SENTENCE")
    assert _find(tree, "PrDP") is not None, "se esperaba PrDP (LDP)"
    assert _find(tree, "ADVP-PERI") is None, "no debe quedar en -PERI@CLAUSE"

    # sin MISC: comportamiento heredado (sin marca, se queda en CLAUSE-PERI,
    # el pro-drop tampoco activa la heurística sintáctica genérica).
    with io.StringIO(_AYER_PRODROP_SIN_MISC) as f:
        tree_sin = ud2rrg.transform(next(parse_tree_incr(f)), "es", layer="SENTENCE")
    assert _find(tree_sin, "PrDP") is None
    assert _find(tree_sin, "ADVP-PERI") is not None


def test_gating_no_es_ldp_misc_ignorado():
    """Gating: en otra lengua, RRGDetached=si se ignora -- comportamiento
    heredado, sin PrDP inducido por MISC."""
    import ud2rrg
    from conllu import parse_tree_incr

    with io.StringIO(_AYER_PRODROP_CON_MISC) as f:
        tree = ud2rrg.transform(next(parse_tree_incr(f)), "en", layer="SENTENCE")
    assert _find(tree, "PrDP") is None


# ---------------------------------------------------------------------------
# L4.5 §3 — doble AGX (dativo + se-pasivo en la misma cláusula). Fixture
# mínima sugerida por el prompt: "Se les prohibió la salida".
# ---------------------------------------------------------------------------
_SE_LES_PROHIBIO = """# sent_id = 1
# text = Se les prohibió la salida
1\tSe\tél\tPRON\t_\tCase=Acc|Person=3|PronType=Prs|Reflex=Yes\t3\texpl:pass\t_\tRRGRole=AGX|RRGDoblado=no|RRGAgxFuente=se_pasivo
2\tles\tél\tPRON\t_\tCase=Dat|Number=Plur|Person=3|PronType=Prs\t3\tobl:arg\t_\tRRGRole=AGX|RRGDoblado=no|RRGAgxFuente=dativo
3\tprohibió\tprohibir\tVERB\t_\tMood=Ind|Number=Sing|Person=3|Tense=Past|VerbForm=Fin\t0\troot\t_\t_
4\tla\tel\tDET\t_\tDefinite=Def|Gender=Fem|Number=Sing\t5\tdet\t_\t_
5\tsalida\tsalida\tNOUN\t_\tGender=Fem|Number=Sing\t3\tnsubj\t_\t_

"""


def test_doble_agx_dativo_y_se_pasivo_dos_nodos():
    import ud2rrg
    from conllu import parse_tree_incr

    with io.StringIO(_SE_LES_PROHIBIO) as f:
        tree = ud2rrg.transform(next(parse_tree_incr(f)), "es", layer="SENTENCE")
    nodos_agx = [st for st in tree.subtrees() if st.label == "AGX"]
    assert len(nodos_agx) == 2, f"se esperaban 2 nodos AGX, hubo {len(nodos_agx)}"
    assert all(st.parent.label == "NUC" for st in nodos_agx)


# ---------------------------------------------------------------------------
# L4.5 §5 — "se" ASPECTUAL -> AGX vía MISC (mismo deprel expl:pv que el
# reflexivo/anticausativo genérico, que NO produce AGX).
# ---------------------------------------------------------------------------
_SE_ASPECTUAL_COME_MANZANAS = """# sent_id = 1
# text = Juan se come las manzanas
1\tJuan\tJuan\tPROPN\t_\t_\t3\tnsubj\t_\t_
2\tse\tél\tPRON\t_\tCase=Acc|Person=3|PronType=Prs|Reflex=Yes\t3\texpl:pv\t_\tRRGRole=AGX|RRGDoblado=no|RRGAgxFuente=se_aspectual
3\tcome\tcomer\tVERB\t_\tMood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin\t0\troot\t_\t_
4\tlas\tel\tDET\t_\tDefinite=Def|Gender=Fem|Number=Plur\t5\tdet\t_\t_
5\tmanzanas\tmanzana\tNOUN\t_\tGender=Fem|Number=Plur\t3\tobj\t_\t_

"""

_SE_GENERICO_SIN_MISC = _SE_ASPECTUAL_COME_MANZANAS.replace(
    "2\tse\tél\tPRON\t_\tCase=Acc|Person=3|PronType=Prs|Reflex=Yes\t3\texpl:pv\t_\t"
    "RRGRole=AGX|RRGDoblado=no|RRGAgxFuente=se_aspectual",
    "2\tse\tél\tPRON\t_\tCase=Acc|Person=3|PronType=Prs|Reflex=Yes\t3\texpl:pv\t_\t_",
)


def test_se_aspectual_misc_produce_agx():
    import ud2rrg
    from conllu import parse_tree_incr

    with io.StringIO(_SE_ASPECTUAL_COME_MANZANAS) as f:
        tree = ud2rrg.transform(next(parse_tree_incr(f)), "es", layer="SENTENCE")
    agx = _find(tree, "AGX")
    assert agx is not None, "se esperaba AGX para el 'se' aspectual (vía MISC)"
    assert agx.parent.label == "NUC"


def test_se_generico_sin_misc_no_produce_agx():
    """Mismo deprel (expl:pv), SIN RRGRole=AGX en MISC: comportamiento
    heredado -- el clítico queda como PRO-CLT normal, NO AGX (evita que
    reflexivos/anticausativos genéricos, que nucleo_periferia no clasifica
    como se_aspectual, se enruten mal por accidente)."""
    import ud2rrg
    from conllu import parse_tree_incr

    with io.StringIO(_SE_GENERICO_SIN_MISC) as f:
        tree = ud2rrg.transform(next(parse_tree_incr(f)), "es", layer="SENTENCE")
    assert _find(tree, "AGX") is None


# ---------------------------------------------------------------------------
# (a)-(d): pipeline real (Stanza + MISC + ud2rrg) — solo con --slow /
# RUN_SLOW=1. Un solo test para las 4 fijaciones (carga de Stanza es cara).
# ---------------------------------------------------------------------------
def test_slow_l3_fijaciones_ancladas():
    import stanza

    import grrux_ai1 as g
    import ud2rrg
    from conllu import parse_tree_incr

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    def _procesar(frase):
        res = g.procesar_oracion(nlp, frase)
        with open(g.CONLLU_PATH, encoding="utf-8") as f:
            udtree = next(parse_tree_incr(f))
        rrgtree = ud2rrg.transform(udtree, "es", layer="SENTENCE")
        return rrgtree, res

    # (a) "Juan comió pizza ayer" -> ADVP-PERI hija de CORE, no de CLAUSE.
    # Etapa PERIFERIA (2026-07-13, Julian): CORRECCIÓN DOCTRINAL que rompe
    # la decisión L3 -- el marco temporal (adverbio o PP) es periferia del
    # CENTRO (sitúa el evento predicativo, no toda la proposición); solo
    # razón/concesión/condición/epistémico anclan a CLAUSE. Ver
    # prompt_opus48_periferia.md §2.1.
    tree, res = _procesar("Juan comió pizza ayer")
    assert "Convertidas: 1 | Fallidas: 0" in res["stdout"]
    peri = _find(tree, "ADVP-PERI")
    assert peri is not None, "se esperaba un nodo ADVP-PERI"
    assert peri.parent.label == "CORE"

    # (b) "Juan corrió en el parque" -> PP-PERI hija de CORE (locativo
    # modifica el evento predicativo, no toda la cláusula).
    tree, res = _procesar("Juan corrió en el parque")
    assert "Convertidas: 1 | Fallidas: 0" in res["stdout"]
    peri = _find(tree, "PP-PERI")
    assert peri is not None, "se esperaba un nodo PP-PERI"
    assert peri.parent.label == "CORE"

    # (c) "Le compró un regalo a María" -> el árbol POR FIN existe (antes de
    # L3, obl:arg no estaba en el dispatch y la oración entera fallaba);
    # AGX bajo NUC (hermano del NUC que contiene PRED>V); el NP de "María"
    # sigue siendo argumento del CORE (doblado: un solo argumento
    # semántico, dos materializaciones sintácticas).
    tree, res = _procesar("Le compró un regalo a María")
    assert "Convertidas: 1 | Fallidas: 0" in res["stdout"]
    agx = _find(tree, "AGX")
    assert agx is not None, "se esperaba un nodo AGX para el clítico 'Le'"
    assert agx.parent.label == "NUC"
    pp = _find(tree, "PP")
    assert pp is not None, "se esperaba un PP para 'a María' en el CORE"
    assert pp.parent.label == "CORE"

    # (d) "Le dije la verdad" -> AGX sin doblar: SOLO el clítico (sin NP/PP
    # pleno adicional para el dativo — Completeness Constraint satisfecho
    # morfológicamente).
    tree, res = _procesar("Le dije la verdad")
    assert "Convertidas: 1 | Fallidas: 0" in res["stdout"]
    agx = _find(tree, "AGX")
    assert agx is not None
    assert agx.parent.label == "NUC"
    assert _find(tree, "PP") is None, \
        "sin doblado no debe haber PP adicional para el dativo"


# ---------------------------------------------------------------------------
# L4 §5 — guard de frecuencia ("todos los días") con Stanza real
# ---------------------------------------------------------------------------
def test_slow_guard_frecuencia_postverbal_anclado_clause():
    """Guard 'todos los días' (bug de campo de Julian, ver
    `nucleo_periferia._guard_frecuencia_dispara`): con Stanza real, la
    variante PREVERBAL original ("Todos los días yo como chocolates") cae en
    el homógrafo "como" SCONJ (conjunción) y da un parse totalmente
    distinto — documentado ya en CHECKPOINT_L3.md §5, se IGNORA aquí por
    orden explícita de Julian (queda para L5). La variante POSTVERBAL ("Yo
    como chocolates todos los días") es la que pide L4 §5 -- pero con la
    versión de Stanza de este entorno el MISMO homógrafo "como" descarrila
    también esta variante (root pasa a ser "Yo", "como" cae como SCONJ/case
    de "chocolates", "días" como appos): verificado empíricamente aquí, así
    que el test comprueba primero que el parser puso "comer" como raíz
    antes de exigir nada sobre la periferia -- si no, se salta con un
    motivo explícito (mismo hallazgo que L3, ahora confirmado también en
    posición postverbal) en vez de fallar sobre cimientos rotos o simular
    un pase falso."""
    import stanza

    import grrux_ai1 as g
    import ud2rrg
    from conllu import parse_tree_incr

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)
    doc = nlp("Yo como chocolates todos los días")
    raiz = next(w for w in doc.sentences[0].words if w.head == 0)
    if raiz.lemma.lower() != "comer":
        import pytest
        pytest.skip(
            "Homógrafo 'como' (SCONJ) descarrila también la variante "
            f"postverbal con esta versión de Stanza: raíz real = "
            f"'{raiz.text}' ({raiz.upos}, lema '{raiz.lemma}'), no 'comer'. "
            "Mismo hallazgo que la variante preverbal en CHECKPOINT_L3.md "
            "§5 -- queda para L5.")

    res = g.procesar_oracion(nlp, "Yo como chocolates todos los días")
    with open(g.CONLLU_PATH, encoding="utf-8") as f:
        udtree = next(parse_tree_incr(f))
    tree = ud2rrg.transform(udtree, "es", layer="SENTENCE")

    ls = res["ls_lista"][0]
    # Etapa PERIFERIA (2026-07-13): el guard de "todos los días" ahora tipa
    # como FRECUENCIA (no "temporal" a secas, ver nucleo_periferia.py), y
    # frecuencia ancla a CENTRO/CORE (no CLAUSE) -- misma corrección
    # doctrinal que (a) arriba.
    assert any(p["tipo"] == "frecuencia" for p in ls["periferia"]), \
        ("se esperaba periferia de frecuencia ('días', degradada o detectada); "
         f"periferia real: {ls['periferia']}")

    peris_core = [st for st in tree.subtrees()
                 if isinstance(st.label, str) and st.label.endswith("-PERI")
                 and st.parent is not None and st.parent.label == "CORE"]
    assert peris_core, "se esperaba al menos una rama -PERI anclada a CORE"


# ---------------------------------------------------------------------------
# L4 — checker de completeness end-to-end (grrux_ai1 + completeness), solo
# con --slow / RUN_SLOW=1.
# ---------------------------------------------------------------------------
def test_slow_l4_completeness_end_to_end():
    import stanza

    import grrux_ai1 as g

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    # (1) "Le compró un regalo a María" -> Completeness: ✓ con AGX e y↔PP.
    res = g.procesar_oracion(nlp, "Le compró un regalo a María")
    assert "Convertidas: 1 | Fallidas: 0" in res["stdout"]
    assert len(res["completeness"]) == 1
    c = res["completeness"][0]
    assert c["ok"] is True, c["resumen"]
    assert c["resumen"].startswith("Completeness: ✓")
    assert "AGX✓" in c["resumen"]
    assert "y↔PP" in c["resumen"]

    # (2) periferia temporal Y locativa -> wrappers ↔ ramas en el estrato
    # correcto. Etapa PERIFERIA (2026-07-13): AMBAS anclan a CENTRO/CORE
    # (marco espacial y temporal modifican el evento predicativo, no la
    # proposición entera) -- corrige la doctrina L3 ("temporal->CLAUSE").
    res2 = g.procesar_oracion(nlp, "Juan corrió en el parque ayer")
    assert "Convertidas: 1 | Fallidas: 0" in res2["stdout"]
    c2 = res2["completeness"][0]
    peri_checks = [chk for chk in c2["checks"] if chk["tipo"] == "periferia"]
    assert len(peri_checks) == 2, peri_checks
    assert all("PERI@CORE" in chk["detalle"] for chk in peri_checks), peri_checks
    assert all(chk["estado"] == "ok" for chk in peri_checks), peri_checks

    # (3) el .txt de guardado conserva la línea de integridad (todos los
    # modos comparten `_guardar_resultados`/`guardar_analisis`). L5 §2/§3: la
    # línea sale traducida ("Integridad: ✓") y en el orden GRR (árbol →
    # EL léxica → resto), no la etiqueta interna "Completeness:".
    nombre = g._nombre_archivo("Le compró un regalo a María")
    try:
        g.guardar_analisis("Le compró un regalo a María", res["ls_lista"],
                           res["stdout"], res["completeness"])
        with open(nombre, encoding="utf-8") as f:
            contenido = f.read()
        assert "Integridad: ✓" in contenido
        # orden GRR: el árbol va antes que la EL léxica
        assert contenido.index("ÁRBOL SINTÁCTICO RRG") < contenido.index("EL léxica")
    finally:
        if os.path.exists(nombre):
            os.remove(nombre)

    # (4) modo ".conllu directo": el MISMO .conllu ya anotado (CONLLU_PATH
    # tras el último procesar_oracion) se re-lee vía leer_ls_desde_conllu +
    # _completeness_por_oracion (canal MISC, sin re-correr el mapper) y debe
    # llegar a la misma conclusión de completeness que el modo interactivo.
    ls_desde_archivo = g.leer_ls_desde_conllu(g.CONLLU_PATH)
    completeness_desde_archivo = g._completeness_por_oracion(g.CONLLU_PATH, ls_desde_archivo)
    assert len(completeness_desde_archivo) == 1
    assert completeness_desde_archivo[0]["ok"] is True, completeness_desde_archivo[0]["resumen"]


if not RUN_SLOW:
    try:
        import pytest
        test_slow_l3_fijaciones_ancladas = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_l3_fijaciones_ancladas)
        test_slow_guard_frecuencia_postverbal_anclado_clause = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_guard_frecuencia_postverbal_anclado_clause)
        test_slow_l4_completeness_end_to_end = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_l4_completeness_end_to_end)
    except ImportError:
        pass


def main():
    rapidos = [test_gold_ancora_crudo_convierte_igual_que_limpiado,
              test_gating_lengua_no_es_ignora_misc,
              test_gating_es_sin_misc_no_cambia,
              test_nominalizacion_obl_arg_bajo_noun_convierte,
              test_gating_no_es_obl_arg_bajo_noun_sigue_nothandled,
              test_se_pasiva_refleja_agx_y_nsubj_pass_como_np,
              test_se_impersonal_agx,
              test_gating_no_es_se_pasiva_sigue_nothandled,
              test_ldp_misc_gated_cubre_prodrop_sin_precedes_subject,
              test_gating_no_es_ldp_misc_ignorado,
              test_doble_agx_dativo_y_se_pasivo_dos_nodos,
              test_se_aspectual_misc_produce_agx,
              test_se_generico_sin_misc_no_produce_agx]
    lentos = [test_slow_l3_fijaciones_ancladas,
             test_slow_guard_frecuencia_postverbal_anclado_clause,
             test_slow_l4_completeness_end_to_end]
    tests = rapidos + (lentos if RUN_SLOW else [])

    fallos = 0
    for t in tests:
        try:
            t()
            print(f"  [OK]   {t.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"  [FAIL] {t.__name__}: {e}")
        except BaseException as e:   # pytest.skip (Skipped) u otros: no aborta la corrida
            if type(e).__name__ == "Skipped":
                print(f"  [SKIP] {t.__name__}: {e}")
            else:
                raise
    if not RUN_SLOW:
        print("  (integración omitida; usa --slow)")
    if fallos:
        sys.exit(1)
    print(f"\n{len(tests)} tests pasaron.")


if __name__ == "__main__":
    main()
