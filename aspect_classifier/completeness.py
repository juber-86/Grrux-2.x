"""Fase LINKING, Etapa L4 — Restricción de Integridad de la RRG vuelta código.

`verificar(ls_data, arbol)` compara el dict que devuelve
`rrg_ls_mapper.map_sentence_to_ls` (el mismo `ls` que ya consume
`misc_rrg.anotaciones_misc`) contra el árbol RRG real que produce
`ud2rrg.transform` para esa misma oración, y reporta si cada argumento y
cada pieza de periferia tiene su contraparte esperada.

No es un validador estricto: varias "faltas" son en realidad
SATISFACCIONES morfológicas previstas por la teoría (Completeness
Constraint de Van Valin) y se marcan `ok`, no error:
  - actor implícito (pro-drop): la morfología verbal ya lo satisface.
  - dativo solo-clítico (agx sin doblar): el nodo AGX ya lo satisface.
  - impersonal: no se espera ningún argumento.

Módulo puro (sin Stanza, sin ud2rrg): recibe el dict del mapper y un
árbol `discodop.tree.ParentedTree` ya construido (o `None`), no importa
ud2rrg ni corre ninguna conversión — testeable en frío con árboles
sintéticos.

NOTA sobre las hojas del árbol (importante para tests sintéticos): en
`ud2rrg.py`, `preterminal()` fija cada hoja al ÍNDICE 0-based de posición
del token (`int(udnode.token['id']) - 1`), NUNCA a la forma superficial de
la palabra — el texto real solo se reintroduce en el render ASCII
(`DrawTree(tree, sent)`, ver `convertir.py`), no en el objeto
`ParentedTree`. Por eso el matching de este módulo es por ÍNDICE de
posición (`token_id - 1`), no por comparación de texto — un árbol
sintético de prueba debe usar hojas enteras (0-based), igual que produce
`ud2rrg.transform`.
"""

from . import linking

# Etapa PERIFERIA (2026-07-13): el anclaje esperado se lee del campo
# "estrato" (nucleo/centro/clausula, ver nucleo_periferia._tipo_periferia),
# NO del "tipo" fino -- reemplaza la regla L3 "temporal→CLAUSE" (doctrina
# corregida: el marco temporal ancla a CENTRO/CORE, no a CLÁUSULA). Default
# "centro" para periferia reconstruida de un MISC viejo sin RRGStratum.
_ESTRATO_A_LABEL = {"nucleo": "NUC", "centro": "CORE", "clausula": "CLAUSE"}
_ESTRATO_DEFECTO = "CORE"

# Fase L4.5 §1: deprels de origen cuyo filler es una CLÁUSULA subordinada
# (juntura CORE/CLAUSE), no un NP/PP -- el x_n mismo ES el token verbal
# incrustado (ver CORE_DEPRELS en nucleo_periferia.py).
_DEPRELS_CLAUSALES = {"ccomp", "xcomp", "csubj"}


def _tiene_agx(arbol) -> bool:
    if arbol is None:
        return False
    return any(isinstance(st.label, str) and st.label == "AGX"
               for st in arbol.subtrees())


def _contar_agx(arbol) -> int:
    if arbol is None:
        return 0
    return sum(1 for st in arbol.subtrees()
              if isinstance(st.label, str) and st.label == "AGX")


def _buscar_constituyente_argumental(arbol, token_id: int | None) -> str | None:
    """Primer nodo NP o PP (sin sufijo -PERI) cuya hoja incluya la posición
    de `token_id` (0-based, `token_id - 1`, igual que `ud2rrg.preterminal`).
    None si no se encuentra."""
    if arbol is None or token_id is None:
        return None
    pos = token_id - 1
    for st in arbol.subtrees():
        label = st.label if isinstance(st.label, str) else ""
        if label in ("NP", "PP") and pos in st.leaves():
            return label
    return None


def _es_argumento_clausal(arbol, token_id: int | None) -> bool:
    """Fase L4.5 §1: ¿el token es el NÚCLEO VERBAL (NUC) de una cláusula
    incrustada (juntura CORE/CLAUSE subordinada)? Para ccomp/xcomp/csubj el
    x_n del mapper ES el propio verbo incrustado (ver CORE_DEPRELS), así
    que basta comprobar que su posición cuelga de un nodo NUC verbal
    (transform_V etiqueta el núcleo del predicado siempre como NUC
    exactamente) -- distinto de buscar 'la' CORE que lo contiene, que
    trivialmente sería la CORE raíz para cualquier token de la oración."""
    if arbol is None or token_id is None:
        return False
    pos = token_id - 1
    return any(isinstance(st.label, str) and st.label == "NUC" and pos in st.leaves()
              for st in arbol.subtrees())


def _buscar_rama_peri(arbol, token_id: int | None, estrato_esperado: str | None):
    """Busca un nodo -PERI cuya hoja incluya la posición de `token_id`.

    Returns:
        (encontrado: bool, estrato_correcto: bool | None) — estrato_correcto
        es None si no se pide verificar estrato (estrato_esperado is None).
    """
    if arbol is None or token_id is None:
        return False, None
    pos = token_id - 1
    for st in arbol.subtrees():
        label = st.label if isinstance(st.label, str) else ""
        if not label.endswith("-PERI"):
            continue
        if pos not in st.leaves():
            continue
        if estrato_esperado is None:
            return True, None
        padre = st.parent
        padre_label = padre.label if padre is not None and isinstance(padre.label, str) else None
        return True, (padre_label == estrato_esperado)
    return False, None


def _es_ldp(arbol, token_id: int | None) -> bool:
    """Fase L4.5 §2: ¿el token cuelga de PrDP (posición dislocada
    izquierda), hijo de SENTENCE? La maquinaria PrDP es preexistente en
    ud2rrg.py (precedes_subject, y desde L4.5 también el enrutado
    MISC-gated de periferia temporal destacada) -- un wrapper temporal
    satisfecho por LDP en vez de -PERI@CLAUSE NUNCA es un error."""
    if arbol is None or token_id is None:
        return False
    pos = token_id - 1
    return any(isinstance(st.label, str) and st.label == "PrDP" and pos in st.leaves()
              for st in arbol.subtrees())


def _chequear_argumentos(ls_data: dict, arbol) -> list[dict]:
    checks = []
    if ls_data.get("impersonal"):
        checks.append({"tipo": "argumento", "elemento": "(impersonal)",
                       "estado": "ok",
                       "detalle": "impersonal: sin argumento esperado"})
        return checks

    variables = ls_data.get("variables") or {}
    id_a_var = ls_data.get("id_a_var") or {}
    var_a_id = {v: k for k, v in id_a_var.items()}
    core_por_id = {c["id"]: c for c in (ls_data.get("core") or [])}
    actor_implicito = ls_data.get("actor_implicito")
    # L4.5 §3: 'agx' es una lista (antes L4: dict único|None).
    # L5 §1: cualquier clítico AGX sin doblar (dativo/acusativo/reflexivo,
    # no solo dativo) satisface morfológicamente su argumento vía el nodo
    # AGX -- se_pasivo/se_impersonal/se_aspectual no generan variable, así
    # que ampliar a "no doblado" no introduce falsos ok.
    agx_clitico_solo = {e["clitico_id"] for e in (ls_data.get("agx") or [])
                        if not e.get("doblado")}

    for var, texto in variables.items():
        tid = var_a_id.get(var)

        # Pro-drop: la variable no tiene id de token (sin realización
        # sintáctica) y coincide con la etiqueta del actor implícito.
        if tid is None and actor_implicito and texto == actor_implicito.get("etiqueta"):
            checks.append({"tipo": "argumento", "elemento": var, "estado": "ok",
                           "detalle": f"{var}(morf)"})
            continue

        # Clítico solo (agx sin doblar, dativo/acusativo): satisfecho por el
        # nodo AGX, no se espera NP/PP pleno para esta variable.
        if tid is not None and tid in agx_clitico_solo:
            hay_agx = _tiene_agx(arbol)
            checks.append({
                "tipo": "argumento", "elemento": var,
                "estado": "ok" if hay_agx else "falta_en_arbol",
                "detalle": (f"{var}(clítico-AGX)" if hay_agx else
                           f"{var}: clítico sin doblar, se esperaba nodo AGX y no está"),
            })
            continue

        if tid is None:
            # No hay id de token rastreable para esta variable (p.ej.
            # causatividad/ditransitivas reasignan id_a_var sin tocar
            # variables/core — ver rrg_ls_mapper.map_sentence_to_ls):
            # mejor no_verificable que un falso positivo.
            checks.append({"tipo": "argumento", "elemento": var,
                           "estado": "no_verificable",
                           "detalle": f"{var}: sin id de token rastreable"})
            continue

        entry = core_por_id.get(tid)
        texto_buscar = (entry["text"] if entry else texto) or ""
        etiqueta = _buscar_constituyente_argumental(arbol, tid)
        if etiqueta:
            checks.append({"tipo": "argumento", "elemento": var, "estado": "ok",
                           "detalle": f"{var}↔{etiqueta}"})
            continue

        # L4.5 §1: el x_n es un complemento CLAUSAL (ccomp/xcomp/csubj) --
        # su filler es el propio verbo incrustado, no un NP/PP.
        if (entry and entry.get("deprel") in _DEPRELS_CLAUSALES
                and _es_argumento_clausal(arbol, tid)):
            checks.append({"tipo": "argumento", "elemento": var, "estado": "ok_clausal",
                           "detalle": f"{var}↔CLÁUSULA"})
            continue

        checks.append({
            "tipo": "argumento", "elemento": var, "estado": "falta_en_arbol",
            "detalle": f'{var} ("{texto_buscar}") sin constituyente en el árbol',
        })

    return checks


def _chequear_periferia(ls_data: dict, arbol) -> list[dict]:
    checks = []
    periferia = ls_data.get("periferia") or []
    wrappers = ls_data.get("wrappers") or []
    wrap_por_id = {w["id"]: w for w in wrappers if w.get("id") is not None}

    for p in periferia:
        texto_buscar = p.get("lemma") or p.get("text") or ""
        wrap = wrap_por_id.get(p["id"])

        # Etapa OPERATORS_2 §1: elemento representado como OPERADOR, no como
        # wrapper. Está cubierto por definición -- su información vive en
        # ⟨NEG⟩/⟨STA IRR⟩ -- así que ni se le busca rama-wrapper ni se le
        # marca "no verificable": eso sería una advertencia nueva por un
        # cambio que precisamente ordena la representación. Dónde ponga
        # `ud2rrg` el 'no' en el árbol es asunto suyo y no se toca.
        if wrap is not None and wrap.get("razon") == "operador":
            op = wrap.get("operador", "operador")
            checks.append({"tipo": "periferia", "elemento": texto_buscar,
                           "estado": "ok",
                           "detalle": f'"{texto_buscar}"↔operador ⟨{op}⟩'})
            continue

        if wrap is not None and wrap.get("aplicado"):
            estrato_esperado = _ESTRATO_A_LABEL.get(p.get("estrato"), _ESTRATO_DEFECTO)
            encontrado, estrato_ok = _buscar_rama_peri(arbol, p.get("id"), estrato_esperado)
            pred = wrap.get("pred", "")
            if encontrado and estrato_ok:
                checks.append({"tipo": "periferia", "elemento": pred,
                               "estado": "ok",
                               "detalle": f"{pred}↔PERI@{estrato_esperado}"})
                continue
            # L4.5 §2 (ampliado en la Etapa PERIFERIA, 2026-07-13): CUALQUIER
            # periferia se satisface con LDP/PrDP (posición dislocada
            # izquierda) -- "Ahora, el Congresillo..." nunca es -PERI@CLAUSE
            # en el árbol (va a PrDP), y eso NUNCA es un error: es la
            # estructura RRG correcta para un adjunto destacado al inicio.
            # `ud2rrg.precedes_subject` (heurística preexistente, anterior a
            # L3) ya enviaba a PrDP CUALQUIER PP/adverbio que precede al
            # sujeto -- sin distinguir tipo -- así que el checker tampoco
            # debe distinguir tipo aquí (antes solo aceptaba "temporal";
            # ahora que TODA la periferia se envuelve, la restricción
            # generaba falsos "falta_en_arbol" para locativo/razón/manera/...
            # igualmente adelantados).
            if _es_ldp(arbol, p.get("id")):
                checks.append({"tipo": "periferia", "elemento": pred,
                               "estado": "ok", "detalle": f"{pred}↔LDP"})
                continue
            motivo = ("estrato incorrecto" if encontrado
                      else "sin rama -PERI en el árbol")
            checks.append({
                "tipo": "periferia", "elemento": pred,
                "estado": "falta_en_arbol",
                "detalle": f"{pred}: se esperaba PERI@{estrato_esperado} ({motivo})",
            })
            continue

        # Periferia sin wrapper aplicado (frecuencia, beneficiario no
        # disparado, tipo 'otro'...): solo se verifica presencia de rama
        # -PERI, estrato no exigido; sin evidencia -> no_verificable, nunca
        # error.
        encontrado, _ = _buscar_rama_peri(arbol, p.get("id"), None)
        if encontrado:
            checks.append({"tipo": "periferia", "elemento": texto_buscar,
                           "estado": "ok",
                           "detalle": f'"{texto_buscar}"↔PERI'})
        else:
            checks.append({"tipo": "periferia", "elemento": texto_buscar,
                           "estado": "no_verificable",
                           "detalle": f'"{texto_buscar}": periferia sin wrapper, no verificable'})

    return checks


def _chequear_agx(ls_data: dict, arbol) -> dict | None:
    """L4.5 §3: 'agx' es una lista -- cada entrada ↔ un nodo AGX del árbol,
    y viceversa; el CONTEO debe cuadrar (antes L4: solo presencia/ausencia
    de una única entrada, lo que ocultaba p.ej. dativo+se-pasivo en la
    misma cláusula: 2 nodos AGX en el árbol contra 1 entrada en la LS)."""
    n_ls = len(ls_data.get("agx") or [])
    n_arbol = _contar_agx(arbol)
    if n_ls == 0 and n_arbol == 0:
        return None
    if n_ls == n_arbol:
        detalle = "AGX✓" if n_ls == 1 else f"AGX✓×{n_ls}"
        return {"tipo": "agx", "elemento": "AGX", "estado": "ok", "detalle": detalle}
    if n_ls > n_arbol:
        return {"tipo": "agx", "elemento": "AGX", "estado": "falta_en_arbol",
                "detalle": f"agx en la LS ({n_ls}) pero el árbol solo tiene {n_arbol} nodo(s) AGX"}
    return {"tipo": "agx", "elemento": "AGX", "estado": "falta_en_ls",
            "detalle": f"el árbol tiene {n_arbol} nodo(s) AGX pero la LS solo trae {n_ls}"}


def _chequear_linking(ls_data: dict, arbol) -> list[dict]:
    """Fase LINKING, Etapa LA1 §5 — round-trip: re-deriva desde la EL
    (macropapeles ya asignados por la AUH, PSA+concordancia, AGX esperado)
    qué DEBERÍA haber en el árbol y compara. Es la Completeness Constraint
    operando en la dirección de PRODUCCIÓN — un ángulo distinto del que ya
    cubren `_chequear_argumentos`/`_chequear_agx` (comprensión), no una
    repetición: aquí se decide desde los MACROPAPELES (Actor/Undergoer/NMR),
    no desde las variables x_n. `estado` viene prefijado `linking_`.

    Vacío si `ls_data` no trae análisis de linking (etapa apagada, o una
    rama que no lo calcula) -- ninguna clave nueva, ningún check nuevo."""
    info = ls_data.get("linking")
    if not info:
        return []
    return linking.expectativas_sintacticas(info.get("macropapeles", {}),
                                            ls_data.get("agx"), arbol,
                                            info.get("concordancia"))


def _resumen(ok: bool, checks: list[dict]) -> str:
    simbolo = "✓" if ok else "⚠"
    por_tipo = {"argumento": [], "periferia": [], "agx": [], "linking": []}
    for c in checks:
        por_tipo.setdefault(c["tipo"], []).append(c["detalle"])
    partes = [" ".join(por_tipo["argumento"])] if por_tipo["argumento"] else []
    partes += [" · ".join(por_tipo["periferia"])] if por_tipo["periferia"] else []
    partes += [" · ".join(por_tipo["agx"])] if por_tipo["agx"] else []
    partes += [" · ".join(por_tipo["linking"])] if por_tipo["linking"] else []
    cuerpo = " · ".join(p for p in partes if p)
    return f"Completeness: {simbolo}" + (f" {cuerpo}" if cuerpo else "")


def verificar(ls_data: dict, arbol) -> dict:
    """Compara `ls_data` (dict de `rrg_ls_mapper.map_sentence_to_ls`) contra
    `arbol` (ParentedTree de `ud2rrg.transform`, o None si esa oración no
    convirtió).

    Returns:
        {'ok': bool | None,
         'checks': [{'tipo', 'elemento', 'estado', 'detalle'}, ...],
         'resumen': str}
        'ok' es None (no bool) cuando no hay árbol -- no es un fallo de
        completeness, es una oración que ud2rrg no convirtió en absoluto.
        'estado' en {'ok', 'falta_en_arbol', 'falta_en_ls', 'no_verificable',
        'ok_clausal'} + los de LA1 (round-trip, tipo='linking'):
        {'linking_ok', 'linking_falta_en_arbol', 'linking_concordancia_error'}
        -- presentes solo si `ls_data['linking']` existe (etapa encendida).
    """
    if arbol is None:
        return {"ok": None, "motivo": "sin_arbol", "checks": [],
                "resumen": "Completeness: (sin árbol — la oración no convirtió)"}

    checks = _chequear_argumentos(ls_data, arbol)
    checks += _chequear_periferia(ls_data, arbol)
    agx_check = _chequear_agx(ls_data, arbol)
    if agx_check is not None:
        checks.append(agx_check)
    checks += _chequear_linking(ls_data, arbol)

    ok = not any(c["estado"] in ("falta_en_arbol", "falta_en_ls",
                                 "linking_falta_en_arbol", "linking_concordancia_error")
                for c in checks)
    return {"ok": ok, "checks": checks, "resumen": _resumen(ok, checks)}
