"""Tests de `gruxx_motor.py` — Fase GUI, Etapa G0.

En frío (sin Stanza, sin roBERTa): árboles `ParentedTree` construidos a
mano (mismo patrón que `aspect_classifier/test_completeness.py`) y dicts
`ls` de fixture (sin pasar por `rrg_ls_mapper`). Verifican:
  - G0.2: serialización del árbol a JSON (hojas 0-based, nunca texto).
  - G0.3: `construir_sub_oracion` produce TODAS las claves del contrato con
    los tipos correctos, y `argumentos` viene de los campos estructurados
    del mapper (variables/id_a_var/core/roles_tematicos), nunca de parsear
    `args_map`.

Ejecutar:
    python -m pytest test_gruxx_motor.py
    python test_gruxx_motor.py
"""

import sys

from discodop.tree import ParentedTree

import gruxx_motor as gm


def _arbol(spec):
    label, hijos = spec
    if isinstance(hijos, int):
        return ParentedTree(label, [hijos])
    return ParentedTree(label, [_arbol(h) for h in hijos])


# ═══════════════════════ G0.2 — serialización del árbol ═══════════════════
def test_serializar_arbol_hojas_0based():
    arbol = _arbol(("CLAUSE", [
        ("CORE", [
            ("NP", [("N", 0)]),
            ("NUC", [("V", 1)]),
        ]),
    ]))
    esperado = {"label": "CLAUSE", "hijos": [
        {"label": "CORE", "hijos": [
            {"label": "NP", "hijos": [{"label": "N", "hijos": [{"token": 0}]}]},
            {"label": "NUC", "hijos": [{"label": "V", "hijos": [{"token": 1}]}]},
        ]},
    ]}
    assert gm.serializar_arbol(arbol) == esperado


def test_serializar_arbol_agx_y_peri():
    arbol = _arbol(("CORE", [
        ("AGX", [("CL", 0)]),
        ("NP-PERI", [("N", 1)]),
    ]))
    salida = gm.serializar_arbol(arbol)
    labels = [h["label"] for h in salida["hijos"]]
    assert labels == ["AGX", "NP-PERI"]
    assert salida["hijos"][0]["hijos"][0]["hijos"][0] == {"token": 0}


# ═══════════ G2 §0.1 — orden de constituyentes (fix, veredicto Julian) ═════
def test_serializar_arbol_reordena_hijos_desordenados():
    """Regresión del bug reproducido por Julian: "Juan come pizza" salía
    "come pizza Juan" -- `ud2rrg.transform` añade los hijos en orden de
    PROCESAMIENTO (NUC/objeto antes que el sujeto), no de superficie. El
    árbol sintético reproduce ESE mismo desorden (NUC con el verbo=token 1,
    luego el objeto=token 2, luego el sujeto=token 0, como construiría el
    motor) y verifica que `serializar_arbol` lo corrige: hojas 0..2 de
    izquierda a derecha en el árbol serializado."""
    arbol = _arbol(("CLAUSE", [
        ("CORE", [
            ("NUC", [("V", 1)]),          # "come"  -- token 1, procesado primero
            ("NP", [("N", 2)]),           # "pizza" -- token 2
            ("NP", [("N", 0)]),           # "Juan"  -- token 0, procesado al final
        ]),
    ]))
    salida = gm.serializar_arbol(arbol)
    core = salida["hijos"][0]
    labels_orden = [h["label"] for h in core["hijos"]]
    assert labels_orden == ["NP", "NUC", "NP"]
    hojas = [h["hijos"][0]["hijos"][0]["token"] for h in core["hijos"]]
    assert hojas == [0, 1, 2]


def test_serializar_arbol_reordena_np_interno():
    """Mismo bug, caso NP interno: "la película" salía "película la" -- el
    determinante (token 0) queda como segundo hijo del NP en el árbol tal
    como lo arma el motor; debe reordenarse ANTES del núcleo nominal
    (token 1)."""
    arbol = _arbol(("NP", [
        ("CORE_N", [("N", 1)]),          # "película" -- token 1
        ("DEF", [("D", 0)]),              # "la"       -- token 0
    ]))
    salida = gm.serializar_arbol(arbol)
    labels_orden = [h["label"] for h in salida["hijos"]]
    assert labels_orden == ["DEF", "CORE_N"]
    hojas = [h["hijos"][0]["hijos"][0]["token"] for h in salida["hijos"]]
    assert hojas == [0, 1]


def test_serializar_arbol_reordena_dos_niveles():
    """Desorden a DOS niveles simultáneamente (interno de un NP + entre los
    hijos de CORE) -- confirma que el reordenamiento es recursivo, no solo
    en el nivel más externo."""
    arbol = _arbol(("CLAUSE", [
        ("CORE", [
            ("NUC", [("V", 2)]),                                  # token 2
            ("NP", [("CORE_N", [("N", 1)]), ("DEF", [("D", 0)])]),  # "la película": 0,1
        ]),
    ]))
    salida = gm.serializar_arbol(arbol)
    core = salida["hijos"][0]
    assert [h["label"] for h in core["hijos"]] == ["NP", "NUC"]
    np = core["hijos"][0]
    assert [h["label"] for h in np["hijos"]] == ["DEF", "CORE_N"]
    todas_las_hojas = []

    def _recolectar(n):
        if "token" in n:
            todas_las_hojas.append(n["token"])
        else:
            for h in n["hijos"]:
                _recolectar(h)
    _recolectar(salida)
    assert todas_las_hojas == [0, 1, 2]


# ═══════════════════════ G0.3 — contrato de construir_sub_oracion ═════════
_TOKENS = [{"id": 1, "texto": "Juan", "lema": "Juan"},
          {"id": 2, "texto": "comió", "lema": "comer"},
          {"id": 3, "texto": "pizza", "lema": "pizza"}]

_LS_BASICO = {
    "ls_type": "accomplishment", "ls_formal": "BECOME comido'(pizza)",
    "ls_lexical": "BECOME comer'(pizza)",
    "variables": {"x1": "Juan", "x2": "pizza"},
    "id_a_var": {1: "x1", 3: "x2"},
    "core": [{"id": 1, "text": "Juan", "deprel": "nsubj", "macropapel": "Actor"},
            {"id": 3, "text": "pizza", "deprel": "obj", "macropapel": "Undergoer"}],
    "periferia": [], "agx": [], "wrappers": [],
    "actor_implicito": None, "impersonal": False,
    "vector": {"stat": 0.1, "dyn": 0.7, "tel": 0.8, "pun": 0.1},
    "confianza": 0.9, "metodo": "contextual",
    "morph_note": "stat=0.10 dyn=0.70 tel=0.80 pun=0.10 conf=0.90 (contextual)",
    "causativo": False, "causativo_tipo": None, "causativo_source": None,
    "causativo_confianza": None,
    "roles_tematicos": {},
}

_ARBOL_BASICO = _arbol(("CLAUSE", [
    ("CORE", [
        ("NP", [("N", 0)]),
        ("NUC", [("V", 1)]),
        ("NP", [("N", 2)]),
    ]),
]))


def _claves_contrato():
    return {"tokens", "arbol", "el", "argumentos", "rasgos", "notas",
            "causatividad", "integridad", "periferia", "agx",
            "actor_implicito", "impersonal", "crudo", "operadores", "linking",
            "inventario_enrutado"}


def test_contrato_tiene_todas_las_claves_con_tipos_correctos():
    from aspect_classifier.completeness import verificar
    comp = verificar(_LS_BASICO, _ARBOL_BASICO)
    sub = gm.construir_sub_oracion(_TOKENS, _ARBOL_BASICO, _LS_BASICO, comp)

    assert set(sub.keys()) == _claves_contrato()
    assert isinstance(sub["tokens"], list) and sub["tokens"] == _TOKENS
    assert isinstance(sub["arbol"], dict) and sub["arbol"]["label"] == "CLAUSE"
    # Sin etapa OPERATORS en el `ls` (flag apagado o análisis previo), las EL
    # envueltas caen a la EL cruda: la GUI muestra lo mismo que antes.
    assert sub["el"] == {"tipo": "accomplishment", "tipo_legible": "Realización",
                         "formal": _LS_BASICO["ls_formal"], "lexical": _LS_BASICO["ls_lexical"],
                         "formal_ops": _LS_BASICO["ls_formal"],
                         "lexical_ops": _LS_BASICO["ls_lexical"]}
    assert sub["operadores"] == []
    assert isinstance(sub["argumentos"], list) and len(sub["argumentos"]) == 2
    assert isinstance(sub["rasgos"], dict) and sub["rasgos"]["telico"] == 0.8
    assert isinstance(sub["notas"], list)
    assert sub["causatividad"] is None
    # Fase LINKING, LA1: sin 'linking' en el `ls` (fixture previo a la
    # etapa, o flag apagado), el panel simplemente no dibuja nada.
    assert sub["linking"] is None
    assert sub["integridad"]["ok"] is True
    assert sub["periferia"] == []
    assert sub["agx"] == []
    assert sub["actor_implicito"] is None
    assert sub["impersonal"] is False
    assert sub["crudo"]["morph_note"] == _LS_BASICO["morph_note"]


def test_argumentos_no_parsean_args_map_usan_campos_estructurados():
    """Regresión explícita del contrato (§G0.3): `argumentos` NUNCA debe
    derivarse de parsear `args_map`/`morph_note` -- ni siquiera si esos
    strings legados están AUSENTES del dict debe fallar."""
    ls = dict(_LS_BASICO)
    ls.pop("morph_note", None)   # ausente a propósito
    assert "args_map" not in ls
    argumentos = gm._argumentos_de(ls)
    por_var = {a["var"]: a for a in argumentos}
    assert por_var["x1"] == {"var": "x1", "token_id": 1, "texto": "Juan",
                             "deprel": "nsubj", "papel": "Actor"}
    assert por_var["x2"] == {"var": "x2", "token_id": 3, "texto": "pizza",
                             "deprel": "obj", "papel": "Undergoer"}


def test_argumento_pro_drop_sin_token_id():
    ls = dict(_LS_BASICO)
    ls["variables"] = {"x1": "3sg"}
    ls["id_a_var"] = {}
    ls["core"] = []
    ls["actor_implicito"] = {"persona": "3", "numero": "sg", "etiqueta": "3sg"}
    argumentos = gm._argumentos_de(ls)
    assert argumentos == [{"var": "x1", "token_id": None, "texto": "3sg",
                           "deprel": None, "papel": "Actor(implícito)"}]


def test_periferia_con_wrap_aplicado_y_sin_aplicar():
    ls = dict(_LS_BASICO)
    ls["periferia"] = [{"id": 4, "text": "ayer", "tipo": "temporal", "estrato": "centro"},
                       {"id": 5, "text": "rápido", "tipo": "manera", "estrato": "nucleo"}]
    ls["wrappers"] = [{"id": 4, "pred": "yesterday'", "aplicado": True},
                      {"id": 5, "pred": "manner'", "aplicado": False}]
    salida = gm._periferia_de(ls)
    assert salida[0] == {"id": 4, "texto": "ayer", "tipo": "temporal",
                         "estrato": "centro", "wrap": "yesterday'"}
    assert salida[1]["wrap"] is None


def test_agx_expone_token_id_del_clitico():
    ls = dict(_LS_BASICO)
    ls["agx"] = [{"clitico": "le", "fuente": "dativo", "doblado": True,
                 "arg_id": 3, "clitico_id": 2}]
    salida = gm._agx_de(ls)
    assert salida == [{"clitico": "le", "fuente": "dativo", "doblado": True, "token_id": 2}]


def test_confianza_contrato_numero_cadena_null_e_invalidos():
    assert gm._normalizar_confianza(0.55) == 0.55
    assert gm._normalizar_confianza("0.55") == 0.55
    for invalido in (None, "alta", "", float("nan"), float("inf"), -0.1, 1.1,
                     {}, [], True):
        assert gm._normalizar_confianza(invalido) is None


def test_serializadores_nunca_exponen_confianza_cualitativa():
    ls = dict(_LS_BASICO)
    ls.update(causativo=True, causativo_tipo="heuristico_anticausativo_se",
              causativo_source="heuristic", causativo_confianza="baja")
    assert gm._rasgos_de({**ls, "confianza": "0.55"})["confianza"] == 0.55
    causa = gm._causatividad_de(ls)
    assert causa["confianza"] is None
    assert causa["nivel_confianza"] == "baja"


# ── Etapa OPERATORS — `operadores` y EL envueltas en el contrato ───────────
_LS_CON_OPERADORES = {
    **_LS_BASICO,
    "operadores": {
        "IF":  {"valor": "DEC", "estrato": "clausular", "origen": "declarativa (default)"},
        "TNS": {"valor": "PAST", "estrato": "clausular", "origen": "'comió' Tense=Past"},
        "ASP": {"valor": "PERF PROG", "estrato": "nuclear", "origen": "auxiliar 'ha'"},
    },
    "ls_formal_ops": "⟨IF DEC ⟨TNS PAST ⟨ASP PERF PROG ⟨BECOME comido'(pizza)⟩⟩⟩⟩",
    "ls_lexical_ops": "⟨IF DEC ⟨TNS PAST ⟨ASP PERF PROG ⟨BECOME comer'(pizza)⟩⟩⟩⟩",
}


def test_operadores_de_devuelve_lista_en_orden_de_scope():
    """Lista (no dict) para que el ORDEN de scope viaje garantizado por el
    JSON: la proyección espejo lo dibuja de arriba abajo tal cual."""
    salida = gm._operadores_de(_LS_CON_OPERADORES)
    assert [o["op"] for o in salida] == ["IF", "TNS", "ASP"]
    assert salida[1] == {"op": "TNS", "valor": "PAST", "estrato": "clausular",
                         "origen": "'comió' Tense=Past"}


def test_operadores_de_sin_etapa_es_lista_vacia():
    assert gm._operadores_de(_LS_BASICO) == []
    assert gm._operadores_de({}) == []


def test_contrato_expone_el_envuelta_sin_tocar_la_cruda():
    from aspect_classifier.completeness import verificar
    comp = verificar(_LS_CON_OPERADORES, _ARBOL_BASICO)
    sub = gm.construir_sub_oracion(_TOKENS, _ARBOL_BASICO, _LS_CON_OPERADORES, comp)
    # la envuelta lleva ⟨ ⟩; la cruda queda intacta (la usa la corrección)
    assert sub["el"]["lexical_ops"].startswith("⟨IF DEC ")
    assert sub["el"]["lexical"] == _LS_BASICO["ls_lexical"]
    assert "⟨" not in sub["el"]["formal"]
    assert len(sub["operadores"]) == 3


def test_estratos_de_operadores_son_los_tres_de_la_teoria():
    """El frontend engancha por estrato (nuclear→NUC, central→CORE,
    clausular→CLAUSE): un estrato desconocido dejaría el operador sin dibujar."""
    for o in gm._operadores_de(_LS_CON_OPERADORES):
        assert o["estrato"] in {"nuclear", "central", "clausular"}


def test_arbol_none_sin_arbol_produce_integridad_none():
    from aspect_classifier.completeness import verificar
    comp = verificar(_LS_BASICO, None)
    sub = gm.construir_sub_oracion(_TOKENS, None, _LS_BASICO, comp)
    assert sub["arbol"] is None
    assert sub["integridad"]["ok"] is None
    assert sub["integridad"]["linea"] is not None


def test_estado_antes_de_cargar():
    # Este módulo nunca llama a gm.cargar() -- Stanza no debe construirse
    # solo por importar/testear gruxx_motor.
    #
    # OPERATORS_2 §3: `_nlp` es estado GLOBAL del módulo, así que este test
    # dependía del ORDEN de ejecución -- pasaba aislado y fallaba después de
    # la suite de servidor, que sí carga el pipeline. Se aísla explícitamente
    # (guardar/restaurar) en vez de asumir que nadie lo tocó antes.
    previo = gm._nlp
    gm._nlp = None
    try:
        assert gm.estado() == {"listo": False}
    finally:
        gm._nlp = previo


# ═══════════════════════ G2 §1 — cache de análisis crudo ══════════════════
def test_cache_crudo_guarda_y_recupera():
    aid = gm._cachear_crudo({"oracion": "x", "ls_lista": [{"ls_type": "state"}]})
    assert isinstance(aid, str) and len(aid) > 0
    recuperado = gm.obtener_crudo(aid)
    assert recuperado == {"oracion": "x", "ls_lista": [{"ls_type": "state"}]}


def test_cache_crudo_id_desconocido_da_none():
    assert gm.obtener_crudo("no-existe-jamas") is None


def test_cache_crudo_expulsa_el_mas_viejo_tras_max():
    gm._cache_crudo.clear()
    ids = [gm._cachear_crudo({"oracion": str(i), "ls_lista": []})
           for i in range(gm._CACHE_MAX + 3)]
    assert len(gm._cache_crudo) == gm._CACHE_MAX
    for expulsado in ids[:3]:
        assert gm.obtener_crudo(expulsado) is None
    for vigente in ids[3:]:
        assert gm.obtener_crudo(vigente) is not None


# ═══════════════════════ G3 §1 — lema_raiz ═════════════════════════════════
def test_lema_raiz_resuelve_por_root_id_y_tokens_cacheados():
    crudo = {"ls_lista": [{"root_id": 2}],
            "tokens_por_sub": [[{"id": 1, "texto": "Juan", "lema": "Juan"},
                               {"id": 2, "texto": "corrió", "lema": "correr"}]]}
    assert gm.lema_raiz(crudo, 0) == "correr"


def test_lema_raiz_none_si_falta_root_id_o_tokens_por_sub():
    assert gm.lema_raiz({"ls_lista": [{}]}, 0) is None                      # sin root_id
    assert gm.lema_raiz({"ls_lista": [{"root_id": 9}]}, 0) is None          # sin tokens_por_sub
    assert gm.lema_raiz({"ls_lista": [{"root_id": 9}], "tokens_por_sub": [[]]}, 0) is None


# ═══════════════════════ G3 §4.3 — render_txt_grr ══════════════════════════
def test_render_txt_grr_con_arbol_respeta_el_orden_grr():
    """Mismo orden que `display_grr.render_bloque` (árbol -> EL léxica ->
    resto) con el ASCII vía DrawTree in-process, como pide el checkpoint."""
    arbol = _arbol(("CLAUSE", [("CORE", [("NP", [("N", 0)]), ("NUC", [("V", 1)])])]))
    tokens = [{"id": 1, "texto": "Juan", "lema": "Juan"},
             {"id": 2, "texto": "corrió", "lema": "correr"}]
    ls = {"ls_type": "activity", "ls_formal": "do'(x1,[correr'(x1)])",
         "ls_lexical": "do'(Juan,[correr'(Juan)])"}
    crudo = {"oracion": "Juan corrió", "ls_lista": [ls], "arboles": [arbol],
            "tokens_por_sub": [tokens]}
    texto = gm.render_txt_grr(crudo)
    assert "Juan corrió" in texto
    i_arbol = texto.index("ÁRBOL SINTÁCTICO RRG")
    i_lex = texto.index("EL léxica")
    assert i_arbol < i_lex
    assert "corri" in texto.lower() or "juan" in texto.lower()


def test_render_txt_grr_sin_arboles_cae_a_sin_arbol_nunca_lanza():
    crudo = {"oracion": "x", "ls_lista": [{"ls_type": "state", "ls_lexical": "estar'(x)"}]}
    texto = gm.render_txt_grr(crudo)
    assert "sin árbol" in texto


_PUROS = [
    test_serializar_arbol_hojas_0based,
    test_serializar_arbol_agx_y_peri,
    test_serializar_arbol_reordena_hijos_desordenados,
    test_serializar_arbol_reordena_np_interno,
    test_serializar_arbol_reordena_dos_niveles,
    test_contrato_tiene_todas_las_claves_con_tipos_correctos,
    test_argumentos_no_parsean_args_map_usan_campos_estructurados,
    test_argumento_pro_drop_sin_token_id,
    test_periferia_con_wrap_aplicado_y_sin_aplicar,
    test_agx_expone_token_id_del_clitico,
    test_arbol_none_sin_arbol_produce_integridad_none,
    test_estado_antes_de_cargar,
    test_cache_crudo_guarda_y_recupera,
    test_cache_crudo_id_desconocido_da_none,
    test_cache_crudo_expulsa_el_mas_viejo_tras_max,
    test_lema_raiz_resuelve_por_root_id_y_tokens_cacheados,
    test_lema_raiz_none_si_falta_root_id_o_tokens_por_sub,
    test_render_txt_grr_con_arbol_respeta_el_orden_grr,
    test_render_txt_grr_sin_arboles_cae_a_sin_arbol_nunca_lanza,
    test_operadores_de_devuelve_lista_en_orden_de_scope,
    test_operadores_de_sin_etapa_es_lista_vacia,
    test_contrato_expone_el_envuelta_sin_tocar_la_cruda,
    test_estratos_de_operadores_son_los_tres_de_la_teoria,
]


def main():
    fallos = 0
    for t in _PUROS:
        try:
            t()
            print(f"  [OK]   {t.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"  [FAIL] {t.__name__}: {e}")
        except Exception as e:
            fallos += 1
            print(f"  [ERR]  {t.__name__}: {type(e).__name__}: {e}")
    if fallos:
        sys.exit(1)
    print(f"\n{len(_PUROS)} tests pasaron.")


if __name__ == "__main__":
    main()
