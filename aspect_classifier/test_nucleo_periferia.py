"""Tests de la Etapa 1 — enrutado núcleo/core/periferia.

Ejecutar:
    python -m aspect_classifier.test_nucleo_periferia          # puros
    python -m aspect_classifier.test_nucleo_periferia --slow   # + Stanza/BERTIN

Compatible con pytest (los @slow requieren RUN_SLOW=1).
"""

import os
import sys

from .nucleo_periferia import analizar_roles, tiene_delimitador_nuclear

RUN_SLOW = os.environ.get("RUN_SLOW") == "1" or "--slow" in sys.argv


def _tok(id_, text, lemma, upos, deprel, head, feats=""):
    return {"id": id_, "text": text, "lemma": lemma, "upos": upos,
            "deprel": deprel, "head": head, "feats": feats}


# "estudié tres horas anoche" (pro-drop 1sg; duración y adv temporales)
ESTUDIE = [
    _tok(1, "estudié", "estudiar", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=1|Tense=Past"),
    _tok(2, "tres", "tres", "NUM", "nummod", 3),
    _tok(3, "horas", "hora", "NOUN", "obl", 1),
    _tok(4, "anoche", "anoche", "ADV", "advmod", 1),
]

# "corrió" (pro-drop 3sg)
CORRIO = [_tok(1, "corrió", "correr", "VERB", "root", 0,
               "Mood=Ind|Number=Sing|Person=3|Tense=Past")]

# "Juan corrió cinco kilómetros"
CORRIO_KM = [
    _tok(1, "Juan", "Juan", "PROPN", "nsubj", 2),
    _tok(2, "corrió", "correr", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=3|Tense=Past"),
    _tok(3, "cinco", "cinco", "NUM", "nummod", 4),
    _tok(4, "kilómetros", "kilómetro", "NOUN", "obj", 2),
]

# "Juan corrió hasta la cima" (meta de movimiento → core)
CORRIO_CIMA = [
    _tok(1, "Juan", "Juan", "PROPN", "nsubj", 2),
    _tok(2, "corrió", "correr", "VERB", "root", 0),
    _tok(3, "hasta", "hasta", "ADP", "case", 5),
    _tok(4, "la", "el", "DET", "det", 5),
    _tok(5, "cima", "cima", "NOUN", "obl", 2),
]

# "el pastel fue comido por Juan"
PASTEL = [
    _tok(1, "el", "el", "DET", "det", 2),
    _tok(2, "pastel", "pastel", "NOUN", "nsubj:pass", 4),
    _tok(3, "fue", "ser", "AUX", "aux:pass", 4),
    _tok(4, "comido", "comer", "VERB", "root", 0),
    _tok(5, "por", "por", "ADP", "case", 6),
    _tok(6, "Juan", "Juan", "PROPN", "obl:agent", 4),
]

# variante: agente como obl plano con case "por"
PASTEL_OBL = [t if t["deprel"] != "obl:agent" else {**t, "deprel": "obl"}
              for t in PASTEL]

# "llueve"
LLUEVE = [_tok(1, "llueve", "llover", "VERB", "root", 0,
               "Mood=Ind|Number=Sing|Person=3|Tense=Pres")]

# "Le compró un regalo a María" (doblado: clítico + pleno, ambos obl:arg
# hermanos — así etiqueta Stanza en producción, sin 'expl')
REGALO_MARIA = [
    _tok(1, "Le", "él", "PRON", "obl:arg", 2, "Case=Dat|Number=Sing|Person=3"),
    _tok(2, "compró", "comprar", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=3|Tense=Past"),
    _tok(3, "un", "uno", "DET", "det", 4),
    _tok(4, "regalo", "regalo", "NOUN", "obj", 2),
    _tok(5, "a", "a", "ADP", "case", 6),
    _tok(6, "María", "María", "PROPN", "obl:arg", 2),
]

# "Le dije la verdad" (clítico solo, sin doblar)
DIJE_VERDAD = [
    _tok(1, "Le", "él", "PRON", "obl:arg", 2, "Case=Dat|Number=Sing|Person=3"),
    _tok(2, "dije", "decir", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=1|Tense=Past"),
    _tok(3, "la", "el", "DET", "det", 4),
    _tok(4, "verdad", "verdad", "NOUN", "obj", 2),
]

# Fase L5 §1 — clítico dativo de 1ª persona "Me dio el libro" (me=dativo
# obl:arg, sin doblar -> agx dativo 1sg + un solo x3 morfológico)
ME_DIO_LIBRO = [
    _tok(1, "Me", "yo", "PRON", "obl:arg", 2, "Case=Dat|Number=Sing|Person=1"),
    _tok(2, "dio", "dar", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=3|Tense=Past"),
    _tok(3, "el", "el", "DET", "det", 4),
    _tok(4, "libro", "libro", "NOUN", "obj", 2),
]

# Fase L5 §1 — clítico acusativo de 1ª persona "Me ve" (me=obj -> agx
# acusativo, Undergoer morfológico)
ME_VE = [
    _tok(1, "Me", "yo", "PRON", "obj", 2, "Case=Acc|Number=Sing|Person=1"),
    _tok(2, "ve", "ver", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=3|Tense=Pres"),
]

# Fase L5 §1 — clítico reflexivo "Me lavo" (me=expl:pv -> agx reflexivo,
# concordancia correferencial, sin argumento propio)
ME_LAVO = [
    _tok(1, "Me", "yo", "PRON", "expl:pv", 2, "Number=Sing|Person=1"),
    _tok(2, "lavo", "lavar", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=1|Tense=Pres"),
]

# Guard "todos los días" (bug de campo de Julian, ver L3):
# "Todos los días yo como chocolates" — mis-parse con "días" Y "yo" ambos
# nsubj de "como" (caso a: evidencia = otro nsubj).
DIAS_CASO_A = [
    _tok(1, "Todos", "todo", "DET", "det", 3),
    _tok(2, "los", "el", "DET", "det", 3),
    _tok(3, "días", "día", "NOUN", "nsubj", 5),
    _tok(4, "yo", "yo", "PRON", "nsubj", 5, "Case=Nom|Number=Sing|Person=1"),
    _tok(5, "como", "comer", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=1|Tense=Pres"),
    _tok(6, "chocolates", "chocolate", "NOUN", "obj", 5),
]

# "Todos los días como chocolates" — pro-drop puro, "días" es el único
# candidato a nsubj (caso b: evidencia = persona del verbo no concuerda).
DIAS_CASO_B = [
    _tok(1, "Todos", "todo", "DET", "det", 3),
    _tok(2, "los", "el", "DET", "det", 3),
    _tok(3, "días", "día", "NOUN", "nsubj", 4),
    _tok(4, "como", "comer", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=1|Tense=Pres"),
    _tok(5, "chocolates", "chocolate", "NOUN", "obj", 4),
]

# "Todos los días son iguales" — control: "días" ES el sujeto real
# (concordancia 3pl, único candidato) — el guard NO debe disparar.
DIAS_CONTROL = [
    _tok(1, "Todos", "todo", "DET", "det", 3),
    _tok(2, "los", "el", "DET", "det", 3),
    _tok(3, "días", "día", "NOUN", "nsubj", 5),
    _tok(4, "son", "ser", "AUX", "cop", 5,
         "Mood=Ind|Number=Plur|Person=3|Tense=Pres"),
    _tok(5, "iguales", "igual", "ADJ", "root", 0),
]

# ── Fase L4.5 §2: LDP para periferia temporal inicial destacada ───────────
# "Ahora, Juan corrió" — "Ahora" inicial + coma -> destacado_inicial.
AHORA_JUAN_CORRIO = [
    _tok(1, "Ahora", "ahora", "ADV", "advmod", 4),
    _tok(2, ",", ",", "PUNCT", "punct", 1),
    _tok(3, "Juan", "Juan", "PROPN", "nsubj", 4),
    _tok(4, "corrió", "correr", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=3|Tense=Past"),
]

# ── Fase L4.5 §3/§4: se-pasivo, se-impersonal, se-aspectual, anticausativo
# genérico (sin obj -- NO es aspectual) ────────────────────────────────────
# "Se venden casas"
SE_VENDEN_CASAS = [
    _tok(1, "Se", "él", "PRON", "expl:pass", 2,
         "Case=Acc|Person=3|PronType=Prs|Reflex=Yes"),
    _tok(2, "venden", "vender", "VERB", "root", 0,
         "Mood=Ind|Number=Plur|Person=3|Tense=Pres"),
    _tok(3, "casas", "casa", "NOUN", "nsubj", 2, "Gender=Fem|Number=Plur"),
]

# "Se vive bien"
SE_VIVE_BIEN = [
    _tok(1, "Se", "él", "PRON", "expl:impers", 2,
         "Case=Acc|Person=3|PronType=Prs|Reflex=Yes"),
    _tok(2, "vive", "vivir", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=3|Tense=Pres"),
    _tok(3, "bien", "bien", "ADV", "advmod", 2),
]

# "Juan se come las manzanas" (se aspectual: correferencial + transitivo)
JUAN_SE_COME_MANZANAS = [
    _tok(1, "Juan", "Juan", "PROPN", "nsubj", 3),
    _tok(2, "se", "él", "PRON", "expl:pv", 3,
         "Case=Acc|Person=3|PronType=Prs|Reflex=Yes"),
    _tok(3, "come", "comer", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=3|Tense=Pres"),
    _tok(4, "las", "el", "DET", "det", 5),
    _tok(5, "manzanas", "manzana", "NOUN", "obj", 3, "Gender=Fem|Number=Plur"),
]

# "El jarrón se rompió" (anticausativo genérico, SIN obj -- no es aspectual)
JARRON_SE_ROMPIO = [
    _tok(1, "El", "el", "DET", "det", 2),
    _tok(2, "jarrón", "jarrón", "NOUN", "nsubj", 4),
    _tok(3, "se", "él", "PRON", "expl:pv", 4,
         "Case=Acc|Person=3|PronType=Prs|Reflex=Yes"),
    _tok(4, "rompió", "romper", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=3|Tense=Past"),
]

# ── Fase L4.5 §5: objeto desnudo vs delimitado ─────────────────────────────
# "Juan come manzanas" (desnudo: plural, sin det ni nummod)
COME_MANZANAS_DESNUDO = [
    _tok(1, "Juan", "Juan", "PROPN", "nsubj", 2),
    _tok(2, "come", "comer", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=3|Tense=Pres"),
    _tok(3, "manzanas", "manzana", "NOUN", "obj", 2, "Gender=Fem|Number=Plur"),
]

# "Juan come la manzana" (delimitado: det definido)
COME_LA_MANZANA = [
    _tok(1, "Juan", "Juan", "PROPN", "nsubj", 2),
    _tok(2, "come", "comer", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=3|Tense=Pres"),
    _tok(3, "la", "el", "DET", "det", 4),
    _tok(4, "manzana", "manzana", "NOUN", "obj", 2, "Gender=Fem|Number=Sing"),
]

# "Juan come unas manzanas" (indefinido: TAMBIÉN delimita)
COME_UNAS_MANZANAS = [
    _tok(1, "Juan", "Juan", "PROPN", "nsubj", 2),
    _tok(2, "come", "comer", "VERB", "root", 0,
         "Mood=Ind|Number=Sing|Person=3|Tense=Pres"),
    _tok(3, "unas", "uno", "DET", "det", 4),
    _tok(4, "manzanas", "manzana", "NOUN", "obj", 2, "Gender=Fem|Number=Plur"),
]


def test_prodrop_y_periferia_temporal():
    r = analizar_roles(ESTUDIE, 1, {})
    assert r["core"] == []
    assert r["actor_implicito"] == {"persona": "1", "numero": "sg",
                                    "etiqueta": "1sg"}
    tipos = {(p["text"], p["tipo"]) for p in r["periferia"]}
    assert tipos == {("horas", "temporal"), ("anoche", "temporal")}
    assert not tiene_delimitador_nuclear(r), \
        "una duración periférica nunca delimita (Prueba 4 de Van Valin)"


def test_prodrop_3sg():
    r = analizar_roles(CORRIO, 1, {})
    assert r["actor_implicito"]["etiqueta"] == "3sg"
    assert r["core"] == [] and r["periferia"] == []


def test_obj_es_delimitador():
    r = analizar_roles(CORRIO_KM, 2, {})
    assert [(c["text"], c["macropapel"]) for c in r["core"]] == \
        [("Juan", "Actor"), ("kilómetros", "Undergoer")]
    assert r["actor_implicito"] is None
    assert tiene_delimitador_nuclear(r)


def test_meta_de_movimiento_es_core():
    r = analizar_roles(CORRIO_CIMA, 2, {})
    metas = [c for c in r["core"] if c["macropapel"] == "Meta"]
    assert len(metas) == 1 and metas[0]["text"] == "cima"
    assert tiene_delimitador_nuclear(r)
    assert r["periferia"] == []


def test_pasiva_obl_agent():
    for tokens in (PASTEL, PASTEL_OBL):
        r = analizar_roles(tokens, 4, {})
        pares = {(c["text"], c["macropapel"]) for c in r["core"]}
        assert ("pastel", "Undergoer") in pares
        assert ("Juan", "Actor") in pares
        assert r["actor_implicito"] is None      # hay nsubj:pass


def test_impersonal_llover():
    r = analizar_roles(LLUEVE, 1, {})
    assert r["impersonal"]
    assert r["core"] == [] and r["actor_implicito"] is None
    assert any("pleonástico" in n or "impersonal" in n
               for n in r["notas_mismatch"])


def test_dativo_doblado_clitico_mas_pleno():
    """'Le compró un regalo a María': x1 implícito, x2 regalo, x3 María;
    el clítico va a agx (concordancia), NUNCA genera su propia variable."""
    r = analizar_roles(REGALO_MARIA, 2, {})
    assert r["actor_implicito"] == {"persona": "3", "numero": "sg", "etiqueta": "3sg"}
    assert [(c["text"], c["macropapel"]) for c in r["core"]] == \
        [("regalo", "Undergoer"), ("María", "NMR(dativo)")]
    assert r["agx"] == [{"clitico": "Le", "rasgos": "3sg-dat", "fuente": "dativo",
                        "doblado": True, "arg_id": 6, "clitico_id": 1}]
    assert all(c["text"] != "Le" for c in r["core"])
    assert all(p["text"] != "Le" for p in r["periferia"])


def test_dativo_clitico_solo_morfologico():
    """'Le dije la verdad': sin doblado, el clítico SOLO satisface el
    argumento morfológicamente (Completeness Constraint) — entra a core
    con etiqueta de rasgos, al final (macrorroles antes que NMR)."""
    r = analizar_roles(DIJE_VERDAD, 2, {})
    assert r["actor_implicito"] == {"persona": "1", "numero": "sg", "etiqueta": "1sg"}
    assert [(c["text"], c["macropapel"]) for c in r["core"]] == \
        [("verdad", "Undergoer"), ("3sg", "NMR(dativo)")]
    assert r["agx"] == [{"clitico": "Le", "rasgos": "3sg-dat", "fuente": "dativo",
                        "doblado": False, "arg_id": None, "clitico_id": 1}]


def test_sin_clitico_dativo_sin_agx():
    r = analizar_roles(CORRIO_KM, 2, {})
    assert r["agx"] == []


# Fase L5 §1 — conciliación AGX: me/te/nos/os (dativo/acusativo/reflexivo)
def test_dativo_me_clitico_solo_morfologico():
    """'Me dio el libro': me=dativo 1sg (obl:arg, sin doblar) -> agx dativo +
    UN SOLO x3 morfológico (fixture del prompt §1)."""
    r = analizar_roles(ME_DIO_LIBRO, 2, {})
    assert r["agx"] == [{"clitico": "Me", "rasgos": "1sg-dat", "fuente": "dativo",
                        "doblado": False, "arg_id": None, "clitico_id": 1}]
    assert [(c["text"], c["macropapel"]) for c in r["core"]] == \
        [("libro", "Undergoer"), ("1sg", "NMR(dativo)")]
    assert r["actor_implicito"] == {"persona": "3", "numero": "sg", "etiqueta": "3sg"}
    assert all(c["text"] != "Me" for c in r["core"])


def test_acusativo_me_agx_undergoer_morfologico():
    """'Me ve': me=acusativo (obj) -> agx acusativo + Undergoer morfológico."""
    r = analizar_roles(ME_VE, 2, {})
    assert r["agx"] == [{"clitico": "Me", "rasgos": "1sg-acu", "fuente": "acusativo",
                        "doblado": False, "arg_id": None, "clitico_id": 1}]
    assert [(c["text"], c["macropapel"]) for c in r["core"]] == [("1sg", "Undergoer")]


def test_reflexivo_me_agx_sin_argumento_propio():
    """'Me lavo': me=reflexivo (expl:pv) -> agx reflexivo (concordancia
    correferencial), SIN entrada de core propia."""
    r = analizar_roles(ME_LAVO, 2, {})
    assert r["agx"] == [{"clitico": "Me", "rasgos": "1sg-ref", "fuente": "reflexivo",
                        "doblado": False, "arg_id": None, "clitico_id": 1}]
    assert all(c["text"] != "Me" for c in r["core"])
    # 1ª persona: pro-drop del sujeto (no hay nsubj), no confundir con el 'me'
    assert r["actor_implicito"] == {"persona": "1", "numero": "sg", "etiqueta": "1sg"}


def test_guard_frecuencia_caso_a_otro_nsubj():
    """'Todos los días yo como chocolates': 'días' se degrada a periferia
    de FRECUENCIA (Etapa PERIFERIA, 2026-07-13 -- antes "temporal" a secas)
    porque hay OTRO nsubj ('yo') — evidencia (a)."""
    r = analizar_roles(DIAS_CASO_A, 5, {})
    assert [(c["text"], c["macropapel"]) for c in r["core"]] == \
        [("yo", "Actor"), ("chocolates", "Undergoer")]
    assert [(p["text"], p["tipo"]) for p in r["periferia"]] == [("días", "frecuencia")]
    assert r["actor_implicito"] is None
    assert any("guard frecuencia" in n for n in r["notas_mismatch"])


def test_guard_frecuencia_caso_b_mismatch_pro_drop():
    """'Todos los días como chocolates': sin otro nsubj, pero la persona
    del verbo (1sg) no concuerda con 'días' (nombre, 3a persona implícita)
    — evidencia (b). Tras degradar a FRECUENCIA, dispara pro-drop 1sg."""
    r = analizar_roles(DIAS_CASO_B, 4, {})
    assert [(c["text"], c["macropapel"]) for c in r["core"]] == [("chocolates", "Undergoer")]
    assert [(p["text"], p["tipo"]) for p in r["periferia"]] == [("días", "frecuencia")]
    assert r["actor_implicito"] == {"persona": "1", "numero": "sg", "etiqueta": "1sg"}
    assert any("guard frecuencia" in n for n in r["notas_mismatch"])


def test_guard_frecuencia_control_no_degrada():
    """'Todos los días son iguales': 'días' concuerda (3pl) y es el único
    candidato — ES el sujeto real, el guard NO debe disparar."""
    r = analizar_roles(DIAS_CONTROL, 5, {})
    assert [(c["text"], c["macropapel"]) for c in r["core"]] == [("días", "Actor")]
    assert r["periferia"] == []
    assert not any("guard frecuencia" in n for n in r["notas_mismatch"])


# ---------------------------------------------------------------------------
# Fase L4.5 §2 — LDP: periferia temporal inicial destacada
# ---------------------------------------------------------------------------
def test_periferia_temporal_destacada_inicial():
    r = analizar_roles(AHORA_JUAN_CORRIO, 4, {})
    peri = next(p for p in r["periferia"] if p["text"] == "Ahora")
    assert peri["tipo"] == "temporal"
    assert peri["destacado_inicial"] is True


def test_periferia_temporal_no_inicial_no_destacada():
    """Control: 'anoche' en 'estudié tres horas anoche' NO es inicial —
    destacado_inicial debe ser False (LDP no es un comodín universal)."""
    r = analizar_roles(ESTUDIE, 1, {})
    peri_anoche = next(p for p in r["periferia"] if p["text"] == "anoche")
    assert peri_anoche["destacado_inicial"] is False


# ---------------------------------------------------------------------------
# Fase L4.5 §3/§4 — agx como lista: dativo, se-pasivo, se-impersonal,
# se-aspectual; nsubj→Undergoer en pasiva refleja; sin pro-drop espurio.
# ---------------------------------------------------------------------------
def test_se_pasivo_agx_y_nsubj_undergoer():
    r = analizar_roles(SE_VENDEN_CASAS, 2, {})
    assert [e["fuente"] for e in r["agx"]] == ["se_pasivo"]
    assert r["agx"][0]["clitico_id"] == 1
    assert [(c["text"], c["macropapel"]) for c in r["core"]] == [("casas", "Undergoer")]
    assert r["actor_implicito"] is None   # Ø estructural, NO pro-drop
    assert all(c["id"] != 1 for c in r["core"])   # "Se" nunca en core


def test_se_impersonal_agx_sin_prodrop_espurio():
    """Antes de L4.5, la ausencia de nsubj disparaba pro-drop actor
    implícito (3sg) para 'Se vive bien' -- incorrecto per González Vergara
    (el actor es Ø, no una persona/número implícita real)."""
    r = analizar_roles(SE_VIVE_BIEN, 2, {})
    assert [e["fuente"] for e in r["agx"]] == ["se_impersonal"]
    assert r["core"] == []
    assert r["actor_implicito"] is None
    assert [(p["text"], p["tipo"]) for p in r["periferia"]] == [("bien", "generico")]


def test_se_aspectual_correferencial_y_transitivo():
    r = analizar_roles(JUAN_SE_COME_MANZANAS, 3, {})
    assert [e["fuente"] for e in r["agx"]] == ["se_aspectual"]
    assert [(c["text"], c["macropapel"]) for c in r["core"]] == \
        [("Juan", "Actor"), ("manzanas", "Undergoer")]


def test_se_generico_sin_obj_no_es_aspectual():
    """Anticausativo puro ('el jarrón se rompió', SIN obj): estructuralmente
    excluido de se_aspectual (que exige obj presente) -- ver
    _detectar_se_aspectual. Terreno de causatividad.py, no de aquí."""
    r = analizar_roles(JARRON_SE_ROMPIO, 4, {})
    assert r["agx"] == []


# ---------------------------------------------------------------------------
# Fase L4.5 §5 — telicidad composicional: objeto desnudo vs delimitado
# ---------------------------------------------------------------------------
def test_objeto_desnudo_no_delimita():
    r = analizar_roles(COME_MANZANAS_DESNUDO, 2, {})
    assert not tiene_delimitador_nuclear(r, COME_MANZANAS_DESNUDO)
    # retro-compatibilidad: sin tokens, cualquier 'obj' sigue delimitando
    assert tiene_delimitador_nuclear(r)


def test_objeto_con_determinante_definido_delimita():
    r = analizar_roles(COME_LA_MANZANA, 2, {})
    assert tiene_delimitador_nuclear(r, COME_LA_MANZANA)


def test_objeto_con_determinante_indefinido_delimita():
    """'unas manzanas': indefinido, pero SIGUE delimitando -- todos los
    determinantes delimitan por igual (solo el desnudo no)."""
    r = analizar_roles(COME_UNAS_MANZANAS, 2, {})
    assert tiene_delimitador_nuclear(r, COME_UNAS_MANZANAS)


def test_objeto_con_numeral_delimita():
    r = analizar_roles(CORRIO_KM, 2, {})
    assert tiene_delimitador_nuclear(r, CORRIO_KM)   # "cinco kilómetros"


# ---------------------------------------------------------------------------
# Integración (Stanza + BERTIN) — solo con --slow / RUN_SLOW=1
# ---------------------------------------------------------------------------
def test_slow_ls_integradas():
    import stanza
    import rrg_ls_mapper as m

    nlp = stanza.Pipeline("es", processors="tokenize,mwt,pos,lemma,depparse",
                          verbose=False)

    # caso central del bug
    ls = m.map_sentence_to_ls(nlp("estudié tres horas anoche").sentences[0])
    assert ls["ls_type"] == "activity", ls["ls_type"]
    assert "consumed'" not in ls["ls_formal"]
    assert "None" not in ls["ls_formal"] and "None" not in ls["ls_lexical"]
    assert "1sg" in ls["args_map"] and "Periferia:" in ls["args_map"]
    assert ls["actor_implicito"]["etiqueta"] == "1sg"
    assert len(ls["periferia"]) >= 1

    # el delimitador nuclear sí licencia AA
    ls = m.map_sentence_to_ls(nlp("Juan corrió cinco kilómetros").sentences[0])
    assert ls["ls_type"] == "active_accomplishment"

    ls = m.map_sentence_to_ls(nlp("Juan corrió").sentences[0])
    assert ls["ls_type"] == "activity" and "Juan" in ls["ls_lexical"]

    ls = m.map_sentence_to_ls(nlp("corrió").sentences[0])
    assert ls["ls_type"] == "activity" and "3sg" in ls["ls_lexical"]

    # pasiva: Undergoer nsubj:pass + Actor agente
    ls = m.map_sentence_to_ls(nlp("el pastel fue comido por Juan").sentences[0])
    assert "pastel" in ls["args_map"] and "Undergoer" in ls["args_map"]
    assert "Juan" in ls["args_map"] and "Actor" in ls["args_map"]

    # impersonal: solo predicado
    ls = m.map_sentence_to_ls(nlp("llueve").sentences[0])
    assert ls["ls_lexical"] == "llover'", ls["ls_lexical"]

    # regresión: causativa anticausativa intacta
    ls = m.map_sentence_to_ls(nlp("el jarrón se rompió").sentences[0])
    assert ls["causativo"] and "CAUSE" in ls["ls_lexical"]
    assert ls["ls_type"] == "achievement"

    # L1a: doblado — el pleno es el argumento, el clítico va a agx.
    # Chequeo "NMR(" genérico (no literal "NMR(dativo)"): desde L2.5 estas
    # dos frases disparan ditransitivas.construir_ditransitiva (comprar/decir
    # + dativo → benefactiva/comunicación), que enriquece la etiqueta a
    # NMR(Poseedor)/NMR(Receptor) — la garantía de L1a (NMR-family, nunca
    # el clítico con su propia entrada) se mantiene, ver test_ditransitivas.py
    # para la cobertura específica de L2.5.
    ls = m.map_sentence_to_ls(nlp("Le compró un regalo a María").sentences[0])
    assert "María" in ls["args_map"] and "NMR(" in ls["args_map"]
    assert "Le," not in ls["args_map"] and "Le:" not in ls["args_map"]

    # L1a: clítico solo — satisface el argumento morfológicamente ('3sg')
    ls = m.map_sentence_to_ls(nlp("Le dije la verdad").sentences[0])
    assert "3sg" in ls["args_map"] and "NMR(" in ls["args_map"]


if not RUN_SLOW:
    try:
        import pytest
        test_slow_ls_integradas = pytest.mark.skipif(
            True, reason="lento: exportar RUN_SLOW=1")(test_slow_ls_integradas)
    except ImportError:
        pass


def main():
    rapidos = [test_prodrop_y_periferia_temporal, test_prodrop_3sg,
               test_obj_es_delimitador, test_meta_de_movimiento_es_core,
               test_pasiva_obl_agent, test_impersonal_llover,
               test_dativo_doblado_clitico_mas_pleno,
               test_dativo_clitico_solo_morfologico,
               test_sin_clitico_dativo_sin_agx,
               test_dativo_me_clitico_solo_morfologico,
               test_acusativo_me_agx_undergoer_morfologico,
               test_reflexivo_me_agx_sin_argumento_propio,
               test_guard_frecuencia_caso_a_otro_nsubj,
               test_guard_frecuencia_caso_b_mismatch_pro_drop,
               test_guard_frecuencia_control_no_degrada,
               test_periferia_temporal_destacada_inicial,
               test_periferia_temporal_no_inicial_no_destacada,
               test_se_pasivo_agx_y_nsubj_undergoer,
               test_se_impersonal_agx_sin_prodrop_espurio,
               test_se_aspectual_correferencial_y_transitivo,
               test_se_generico_sin_obj_no_es_aspectual,
               test_objeto_desnudo_no_delimita,
               test_objeto_con_determinante_definido_delimita,
               test_objeto_con_determinante_indefinido_delimita,
               test_objeto_con_numeral_delimita]
    tests = rapidos + ([test_slow_ls_integradas] if RUN_SLOW else [])

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
