"""Etapa 1 — Enrutado Núcleo/Core/Periferia consciente de mismatch (RRG).

Los niveles sintáctico (deprels UD) y semántico (argumentos de la LS) NO
son isomorfos: este módulo enruta cada dependiente del verbo a CORE
(argumento semántico) o PERIFERIA (adjunto), y registra explícitamente
los mismatches (pro-drop, impersonales, pasiva). Es un precursor
rule-based del linking algorithm — el linking completo y el nivel
pragmático NO se implementan aquí.

Módulo puro sobre tokens UD (formato de complejo_verbal.desde_stanza,
con `feats`); sin torch ni Stanza: testeable en frío.
"""

# Argumentos semánticos por deprel (sintaxis y semántica coinciden)
CORE_DEPRELS = {
    "nsubj": "Actor", "nsubj:pass": "Undergoer", "obj": "Undergoer",
    "iobj": "Receptor", "csubj": "Actor", "ccomp": "Tema", "xcomp": "Tema",
    "obl:agent": "Actor",          # agente de pasiva: periferia sintáctica,
                                   # argumento semántico (mismatch clásico)
    "obl:arg": "NMR(dativo)",      # dativo (Stanza etiqueta tanto el clítico
                                   # como el sintagma pleno doblado con este
                                   # deprel); ver _detectar_agx_dativo para el
                                   # colapso clítico+pleno → un solo argumento.
}

# Fase L5 §1 (conciliación AGX) — clíticos átonos que se enlazan al nodo AGX
# (concordancia, NUNCA argumento sintáctico propio). Se AMPLÍA de {le,les}
# (L1a) a me/te/nos/os: antes quedaban fuera "por cautela", pero eso dejaba
# que el fallback propio de ud2rrg (is_clitic_pronoun) los convirtiera en AGX
# en el ÁRBOL sin que la LS los registrara -> el patrón dominante de L4.5
# "árbol con MÁS nodos AGX que la LS". Una sola fuente de verdad: la Etapa 1
# los registra y el árbol lee el MISC. NO se incluye "se" (manejo propio:
# se-pasivo/impersonal/aspectual + anticausativo-no-AGX) ni lo/la/los/las
# (acusativos de 3ª: ya reconcilian como argumento de CORE en ambos lados,
# sin AGX -- no eran parte del desajuste).
_CLITICOS_AGX = {"me", "te", "nos", "os", "le", "les"}
# Persona/número por la FORMA del clítico (no por los feats del verbo, que
# son los del sujeto): le/les=3ª, me/te=1ª/2ª sg, nos/os=1ª/2ª pl.
_CLITICO_RASGOS = {"me": ("1", "sg"), "te": ("2", "sg"), "nos": ("1", "pl"),
                   "os": ("2", "pl"), "le": ("3", "sg"), "les": ("3", "pl")}
_FUENTE_ABREV = {"dativo": "dat", "acusativo": "acu", "reflexivo": "ref"}
# Deprels bajo los que Stanza puede etiquetar un receptor dativo (clítico o
# sintagma pleno doblado): verificado empíricamente que AMBOS miembros del
# doblado salen "obl:arg" hermanos (no hay 'expl' en producción, a
# diferencia del gold AnCora); iobj se deja por si Stanza lo produce.
_DEPRELS_RECEPTOR_DATIVO = {"obl:arg", "iobj"}

# Adjuntos (periferia). obl es periferia POR DEFECTO: solo asciende a core
# como agente de pasiva o meta/origen de verbos de movimiento.
PERIFERIA_DEPRELS = {"obl", "advmod", "obl:tmod", "nmod:tmod", "obl:mod", "advcl"}

DEFAULT_VERBOS_MOVIMIENTO = [
    "ir", "venir", "llegar", "salir", "entrar", "correr", "caminar",
    "subir", "bajar", "volver", "regresar", "viajar", "volar", "nadar",
    "conducir", "marchar",
]
DEFAULT_CASE_META = ["a", "hacia", "hasta"]
DEFAULT_CASE_ORIGEN = ["desde"]
DEFAULT_IMPERSONALES = ["llover", "nevar", "granizar", "amanecer",
                        "anochecer", "haber"]

# Clasificación de la periferia (Etapa PERIFERIA, 2026-07-13 — doctrina GRR de
# Julian, ver prompt_opus48_periferia.md): cada item se tipa Y se ancla a un
# ESTRATO (nucleo/centro/clausula) según su ALCANCE semántico. NUNCA se
# devuelve "otro": el residuo cae a "generico" (estrato centro), que
# wrappers_ls representa con la PROPIA preposición/lema como predicado.
_NOMBRES_TIEMPO = {"hora", "día", "noche", "tarde", "mañana", "rato",
                   "semana", "mes", "año", "minuto", "segundo", "madrugada",
                   "verano", "invierno", "primavera", "otoño", "vez"}
_ADV_TIEMPO = {"anoche", "ayer", "hoy", "ahora", "antes", "después", "luego",
               "temprano", "tarde", "todavía", "ya", "mientras", "entonces"}
_CASE_LOCATIVO = {"en", "sobre", "bajo", "ante", "tras", "entre"}
# "durante" es inequívocamente temporal en español sea cual sea el nombre
# que introduce ("durante la clase", no solo "durante una hora"): sin este
# check, un complemento cuyo lema no está en _NOMBRES_TIEMPO caía a tipo
# "otro" y ni pruebas_estructurales (P4) ni wrappers_ls (during') lo veían.
# "antes"/"después"/"hasta"/"desde" se REACTIVAN aquí (Etapa PERIFERIA,
# 2026-07-13): ahora que el estrato es explícito (RRGStratum), ya no hace
# falta dejarlos fuera "por si acaso" — son inequívocamente temporales como
# preposición. "por" queda FUERA a propósito (ambiguo causal/temporal): se
# maneja aparte como fallback de razón (ver _tipo_periferia), la lectura de
# duración ya la cubre el chequeo de lemma (_NOMBRES_TIEMPO) arriba.
_CASE_TEMPORAL = {"durante", "antes", "después", "hasta", "desde"}

# NÚCLEO -- adverbios aspectuales de fase/grado (envuelven el primitivo más
# profundo de la LS: BECOME(complete'(...))). Modifican el desarrollo interno
# del predicado, sin referencia a los participantes.
_ADV_ASPECTUAL = {"completamente", "totalmente", "íntegramente", "parcialmente",
                  "continuamente", "ininterrumpidamente", "incesantemente",
                  "constantemente", "gradualmente", "paulatinamente",
                  "progresivamente"}

# CLÁUSULA -- epistémicos/evidenciales (envuelven la proposición COMPLETA:
# postura del hablante / probabilidad del hecho).
_ADV_EPISTEMICO = {"probablemente", "posiblemente", "seguramente", "quizá",
                   "quizás", "tal vez", "evidentemente", "obviamente",
                   "aparentemente"}

# CENTRO -- frecuencia (marco temporal-cuantificacional, NO cláusula: ver
# doctrina en prompt_opus48_periferia.md §4). Se comprueba ANTES que
# _ADV_TIEMPO (siempre/nunca vivían ahí antes de esta etapa; salen de ahí).
_ADV_FRECUENCIA = {"siempre", "nunca", "frecuentemente", "habitualmente",
                   "a menudo", "a veces", "algunas veces"}

# CLÁUSULA -- cabezas de frase preposicional COMPUESTA de razón/concesión/
# condición, comprobadas contra `_case_compuesto_de` (arma "a pesar de" /
# "debido a" / etc. uniendo la cadena `fixed` al token `case`).
_FRASE_RAZON = {"debido a", "gracias a", "a causa de", "por causa de"}
_FRASE_CONCESION = {"a pesar de", "pese a"}
_FRASE_CONDICION = {"en caso de"}


def _parse_feats(feats: str) -> dict:
    out = {}
    for par in (feats or "").split("|"):
        if "=" in par:
            k, v = par.split("=", 1)
            out[k] = v
    return out


def _case_de(tokens: list[dict], head_id: int) -> str | None:
    """Lema de la preposición (case) que introduce un dependiente."""
    return next((t["lemma"].lower() for t in tokens
                 if t["head"] == head_id and t["deprel"] == "case"), None)


def _fuente_clitico(t: dict) -> tuple[str, str | None]:
    """Fase L5 §1 — (fuente, macropapel_morfológico) de un clítico átono AGX
    (me/te/nos/os/le/les, nunca 'se') según su deprel. El macropapel es el
    del argumento que el clítico materializa cuando va SOLO (sin sintagma
    pleno doblado); es None para el reflexivo, que es pura concordancia
    correferencial sin argumento propio distinto.

      - obl:arg / iobj  -> dativo     (NMR(dativo))  "me dio el libro"
      - obj / dobj       -> acusativo  (Undergoer)    "me ve"
      - expl:pv / expl   -> reflexivo  (—)            "me lavo"
      - otras posiciones -> dativo si es le/les (leísmo/parse raro),
                            reflexivo en otro caso (conservador).
    """
    deprel = t["deprel"]
    forma = t["text"].lower()
    if deprel in _DEPRELS_RECEPTOR_DATIVO:
        return "dativo", "NMR(dativo)"
    if deprel in ("obj", "dobj"):
        return "acusativo", "Undergoer"
    if deprel in ("expl:pv", "expl"):
        return "reflexivo", None
    return ("dativo", "NMR(dativo)") if forma in ("le", "les") else ("reflexivo", None)


# Fase LINKING, Etapa L4.5 §5 — "se" ASPECTUAL (tercer tipo del inventario,
# junto a dativo y se-pasivo/impersonal del §4): clítico reflexivo
# correferencial con el sujeto ("Juan SE come las manzanas") que marca
# telicidad completiva en un verbo TRANSITIVO. Persona/número esperados
# para desambiguar de otros usos de me/te/nos/os (para "se", invariante,
# la correferencia es trivial y no se chequea aparte).
_SE_CLITICOS_REFLEXIVOS = {"me": ("1", "sg"), "te": ("2", "sg"), "se": None,
                          "nos": ("1", "pl"), "os": ("2", "pl")}


def _detectar_se_aspectual(hijos: list[dict], root: dict) -> dict | None:
    """Estructralmente mutuamente excluyente con:
    - dativo (deprel distinto: obl:arg/iobj, no expl:pv);
    - se-pasivo/impersonal del §4 (deprel distinto: expl:pass/expl:impers);
    - anticausativo del léxico causativo (`toma_se`, `causatividad.py`): esa
      construcción NUNCA tiene 'obj' (intransitiviza -- el afectado ASCIENDE
      a sujeto, "el jarrón se rompió"); exigir 'obj' presente ya excluye esa
      lectura sin necesitar consultar el léxico de causatividad aquí.
    """
    candidatos = [t for t in hijos if t["deprel"] == "expl:pv"
                 and t["upos"] == "PRON"
                 and t["text"].lower() in _SE_CLITICOS_REFLEXIVOS]
    if not candidatos:
        return None
    clitico = candidatos[0]
    if not any(h["deprel"] == "obj" for h in hijos):
        return None   # sin objeto: reflexivo/anticausativo puro, no aspectual
    esperado = _SE_CLITICOS_REFLEXIVOS[clitico["text"].lower()]
    if esperado is not None:
        feats = _parse_feats(root.get("feats", ""))
        numero = "pl" if feats.get("Number") == "Plur" else "sg"
        if (feats.get("Person"), numero) != esperado:
            return None   # persona/numero no concuerdan: no es este clitico
    return {"clitico": clitico["text"], "rasgos": "aspectual",
           "doblado": False, "arg_id": None, "clitico_id": clitico["id"]}


def _detectar_agx(tokens: list[dict], hijos: list[dict], root: dict) -> tuple[list[dict], set[int], list[dict]]:
    """Fase LINKING — unifica TODAS las fuentes de AGX en una sola lista:
    se-pasivo / se-impersonal / se-aspectual (§4/§5 L4.5) y los clíticos
    átonos dativo / acusativo / reflexivo (me/te/nos/os/le/les — L5 §1,
    conciliación AGX). `expl:pv` genérico (reflexivo/anticausativo de "se"
    SIN el patrón aspectual) NO produce AGX -- su árbol tampoco lo produce
    (coherencia con ud2rrg.py).

    Returns:
        (agx_list, ids_a_saltar, morfologicos) -- ids_a_saltar son los ids
        de CUALQUIER clítico de la lista (nunca argumento sintáctico, se
        excluyen del loop principal). `morfologicos` es la LISTA (L5 §1:
        antes un único dativo) de entradas de core para argumentos realizados
        SOLO morfológicamente (clítico dativo/acusativo sin doblar); se
        añaden al final del core, macrorroles antes que NMR (ver
        analizar_roles).
    """
    agx_list: list[dict] = []
    ids_a_saltar: set[int] = set()
    morfologicos: list[dict] = []

    # "se" reflejo-pasivo / impersonal (expl:pass / expl:impers)
    for t in hijos:
        if t["deprel"] == "expl:pass":
            agx_list.append({"clitico": t["text"], "rasgos": "se-pasivo",
                             "fuente": "se_pasivo", "doblado": False,
                             "arg_id": None, "clitico_id": t["id"]})
            ids_a_saltar.add(t["id"])
        elif t["deprel"] == "expl:impers":
            agx_list.append({"clitico": t["text"], "rasgos": "se-impersonal",
                             "fuente": "se_impersonal", "doblado": False,
                             "arg_id": None, "clitico_id": t["id"]})
            ids_a_saltar.add(t["id"])

    # "se" aspectual (correferencial + verbo transitivo con obj)
    se_asp = _detectar_se_aspectual(hijos, root)
    if se_asp is not None:
        agx_list.append({**se_asp, "fuente": "se_aspectual"})
        ids_a_saltar.add(se_asp["clitico_id"])

    # Clíticos átonos dativo/acusativo/reflexivo (me/te/nos/os/le/les). El
    # sintagma pleno doblado (solo dativos: "a María"/"a mí") deja el
    # argumento en su propia posición; el clítico solo lo satisface
    # morfológicamente (Completeness Constraint) -> entrada en `morfologicos`.
    for t in hijos:
        if t["id"] in ids_a_saltar:
            continue
        if t["upos"] != "PRON" or t["text"].lower() not in _CLITICOS_AGX:
            continue
        forma = t["text"].lower()
        fuente, macropapel = _fuente_clitico(t)
        persona, numero = _CLITICO_RASGOS.get(forma, ("3", "sg"))
        pleno = None
        if fuente == "dativo":
            pleno = next((x for x in hijos
                          if x["id"] != t["id"] and x["id"] not in ids_a_saltar
                          and x["upos"] in ("NOUN", "PROPN", "PRON")
                          and _case_de(tokens, x["id"]) == "a"), None)
        agx_list.append({
            "clitico": t["text"], "rasgos": f"{persona}{numero}-{_FUENTE_ABREV[fuente]}",
            "fuente": fuente, "doblado": pleno is not None,
            "arg_id": pleno["id"] if pleno else None, "clitico_id": t["id"]})
        ids_a_saltar.add(t["id"])
        if pleno is None and macropapel is not None:
            morfologicos.append({"id": t["id"], "text": f"{persona}{numero}",
                                 "deprel": t["deprel"], "macropapel": macropapel})

    return agx_list, ids_a_saltar, morfologicos


_CUANTIF_UNIVERSAL = {"todo", "cada"}

# Etapa PERIFERIA (2026-07-13): "fin" SOLO se admite aquí (frecuencia), no en
# el _NOMBRES_TIEMPO general -- "el fin" a secas significa "el final" (de una
# película, de un proceso...), no un periodo de tiempo; solo en plural con
# artículo/cuantificador ("los fines de semana") es la lectura habitual que
# motivó esta etapa (bug de campo de Julian).
_NOMBRES_TIEMPO_FRECUENCIA = _NOMBRES_TIEMPO | {"fin"}


def _es_np_tiempo_cuantificada(tokens: list[dict], t: dict) -> bool:
    """NP con nucleo en nombre de tiempo + cuantificador universal
    ('todos los días', 'cada día'): candidata al guard de frecuencia de
    analizar_roles (bug de campo: Stanza a veces la parsea como nsubj/obj
    del verbo en vez de como periferia)."""
    if t["lemma"].lower() not in _NOMBRES_TIEMPO:
        return False
    return any(h["head"] == t["id"] and h["lemma"].lower() in _CUANTIF_UNIVERSAL
               for h in tokens)


def _es_np_tiempo_frecuencia(tokens: list[dict], t: dict) -> bool:
    """NP PLURAL de nombre de tiempo con cuantificador universal O artículo
    definido, SIN numeral ('los fines de semana', 'los lunes', 'todos los
    días'): lectura HABITUAL/distributiva -- distinto de una duración
    cuantificada ("tres horas", numeral presente) o un punto temporal único
    (singular, "la mañana"). Usado dentro de `_tipo_periferia` para items de
    periferia YA correctamente enrutados como obl/advmod (a diferencia de
    `_es_np_tiempo_cuantificada`, que es el guard para el mis-parse nsubj/obj)."""
    if t["lemma"].lower() not in _NOMBRES_TIEMPO_FRECUENCIA:
        return False
    feats = _parse_feats(t.get("feats", ""))
    if feats.get("Number") != "Plur":
        return False
    hijos = [h for h in tokens if h["head"] == t["id"]]
    tiene_universal = any(h["lemma"].lower() in _CUANTIF_UNIVERSAL for h in hijos)
    tiene_articulo_def = any(h["deprel"] == "det" and h["lemma"].lower() == "el" for h in hijos)
    tiene_numeral = any(h["deprel"] in ("nummod", "nummod:gov") for h in hijos)
    return (tiene_universal or tiene_articulo_def) and not tiene_numeral


def _guard_frecuencia_dispara(hijos: list[dict], root: dict, t: dict) -> bool:
    """Evidencia independiente de que 't' (NP tiempo + cuantificador
    universal, parseada como nsubj/obj) NO es el argumento real:
    (a) hay otro nsubj entre los hermanos (el sujeto real también salió
    parseado), o (b) la persona del verbo no concuerda con un nombre común
    (siempre 3a persona implícita) pero sí con un pro-drop (p.ej. "como"
    1sg vs "días" 3a). Conservador a propósito: sin evidencia no dispara
    (ver control "Todos los días son iguales", donde concuerda 3pl y es el
    único candidato — SÍ es el sujeto)."""
    otro_nsubj = any(h["deprel"] == "nsubj" and h["id"] != t["id"] for h in hijos)
    persona_verbo = _parse_feats(root.get("feats", "")).get("Person", "3")
    mismatch_pro_drop = persona_verbo != "3"
    return otro_nsubj or mismatch_pro_drop


def _case_compuesto_de(tokens: list[dict], head_id: int) -> str | None:
    """Como el chequeo de `case` de un dependiente, pero arma la CADENA
    COMPLETA de una preposición compuesta uniendo los dependientes `fixed`
    del token `case` (convención UD para multiword prepositions: "a pesar
    de" = case:a + fixed:pesar + fixed:de, todos hermanos colgando del
    primer token). Devuelve la frase completa en minúsculas y orden de
    aparición ("a pesar de"), o None si no hay `case`. Para preposiciones
    simples devuelve lo mismo que el lema del case."""
    case_tok = next((t for t in tokens if t["head"] == head_id and t["deprel"] == "case"), None)
    if case_tok is None:
        return None
    cadena = [case_tok] + [t for t in tokens
                           if t["head"] == case_tok["id"] and t["deprel"] == "fixed"]
    cadena.sort(key=lambda t: t["id"])
    return " ".join(t["text"].lower() for t in cadena)


def _tipo_periferia(tokens: list[dict], tok: dict,
                    case: str | None) -> tuple[str, str]:
    """Devuelve (tipo_fino, estrato) -- NUNCA "otro" (ver doctrina GRR en
    prompt_opus48_periferia.md). estrato ∈ {nucleo, centro, clausula}."""
    deprel, lemma = tok["deprel"], tok["lemma"].lower()

    # NÚCLEO -- adverbios aspectuales de fase/grado.
    if deprel == "advmod" and lemma in _ADV_ASPECTUAL:
        return "aspectual", "nucleo"

    # CLÁUSULA -- epistémicos/evidenciales.
    if deprel == "advmod" and lemma in _ADV_EPISTEMICO:
        return "epistemico", "clausula"

    # CENTRO -- frecuencia: adverbio, o NP plural distributivo/habitual
    # ("todos los días" / "cada semana" / "los fines de semana").
    if deprel == "advmod" and lemma in _ADV_FRECUENCIA:
        return "frecuencia", "centro"
    if _es_np_tiempo_frecuencia(tokens, tok):
        return "frecuencia", "centro"

    # CLÁUSULA -- razón/concesión/condición: frase preposicional COMPUESTA.
    frase = _case_compuesto_de(tokens, tok["id"])
    if frase in _FRASE_CONCESION:
        return "concesion", "clausula"
    if frase in _FRASE_CONDICION:
        return "condicion", "clausula"
    if frase in _FRASE_RAZON:
        return "razon", "clausula"

    # CENTRO -- marco temporal (obl:tmod/nmod:tmod, nombre de tiempo,
    # adverbio de tiempo no-frecuencia, o case temporal reactivado).
    if deprel in ("obl:tmod", "nmod:tmod"):
        return "temporal", "centro"
    if lemma in _NOMBRES_TIEMPO or lemma in _ADV_TIEMPO:
        return "temporal", "centro"
    if case in _CASE_TEMPORAL:
        return "temporal", "centro"

    # CLÁUSULA -- "por" causal, SOLO como fallback: ya se descartó agente de
    # pasiva (analizar_roles lo asciende a core antes de llegar aquí) y ya se
    # descartó la lectura de duración/marco arriba (nombre de tiempo). Es
    # ambiguo por naturaleza (causal/agentivo/temporal) -- documentado, ver
    # prompt_opus48_periferia.md §4. NOTA: "por + ruta" (locativo, "caminó
    # por el parque") cae también aquí, gap heredado (ya existía como "otro"
    # antes de esta etapa), sin resolver por ahora.
    if case == "por":
        return "razon", "clausula"

    # CENTRO -- manera (advmod en -mente que no es aspectual ni epistémico).
    if deprel == "advmod" and lemma.endswith("mente"):
        return "manera", "centro"

    # CENTRO -- locativo espacial.
    if case in _CASE_LOCATIVO:
        return "locativo", "centro"

    # GENÉRICO -- mata "otro": PP o adverbio sin entrada específica;
    # wrappers_ls usa la preposición/el lema mismos como predicado.
    return "generico", "centro"


def _subtree_ids(tokens: list[dict], root_id: int) -> set[int]:
    """ids (incl. root_id) de todo el subárbol UD colgando de root_id -- para
    no confundir los propios hijos de una frase periférica ('el pasado' de
    'el pasado lunes') con tokens que genuinamente la preceden."""
    todos = {root_id}
    frontera = {t["id"] for t in tokens if t["head"] == root_id}
    while frontera:
        todos |= frontera
        frontera = {t["id"] for t in tokens if t["head"] in frontera} - todos
    return todos


def _es_destacado_inicial(tokens: list[dict], t: dict) -> bool:
    """Fase LINKING, Etapa L4.5 §2: periferia en POSICIÓN DISLOCADA
    IZQUIERDA (LDP) -- inicial de la oración (o solo precedida de
    puntuación; los propios tokens de la frase periférica, p.ej. 'el
    pasado' de 'el pasado lunes', no cuentan como precedentes) Y seguida de
    coma. P.ej. 'Ahora, el Congresillo quiere...' / 'Ayer, Juan corrió'.
    Solo se usa para marcar periferia TEMPORAL (ver `analizar_roles`); se
    calcula aquí para cualquier tipo por si una fase futura extiende la
    misma ruta de posiciones destacadas a PrCS (ver TODO en `misc_rrg.py`)."""
    por_id = {tok["id"]: tok for tok in tokens}
    # PUNCT excluida del cómputo de la frase: la coma que marca el LDP a
    # menudo cuelga (como hijo UD) del propio token periférico ("Ahora,"),
    # y si se cuenta como parte de la frase, max_id la absorbe y el chequeo
    # "seguido de coma" (justo el token SIGUIENTE a la frase) nunca la ve.
    ids_frase = {i for i in _subtree_ids(tokens, t["id"])
                if por_id[i]["upos"] != "PUNCT"}
    min_id, max_id = min(ids_frase), max(ids_frase)
    precede_solo_punct = all(tok["upos"] == "PUNCT"
                             for tok in tokens if tok["id"] < min_id)
    if not precede_solo_punct:
        return False
    return any(tok["id"] == max_id + 1 and tok["text"] == ","
              for tok in tokens)


def analizar_roles(tokens: list[dict], root_id: int,
                   cfg: dict | None = None) -> dict:
    """Enruta los dependientes del root a core/periferia y detecta mismatches.

    Returns:
        {"core":      [{id, text, deprel, macropapel}],
         "periferia": [{id, text, deprel, tipo, estrato, case, lemma,
                       destacado_inicial}],
                 # Etapa PERIFERIA (2026-07-13): tipo ∈ {aspectual, manera,
                 # locativo, temporal, frecuencia, razon, concesion,
                 # condicion, epistemico, generico} -- NUNCA "otro"/"modo".
                 # estrato ∈ {nucleo, centro, clausula} (anclaje del árbol).
         "actor_implicito": {"persona", "numero", "etiqueta"} | None,
         "impersonal": bool,
         "agx": [{"clitico", "rasgos", "fuente", "doblado", "arg_id", "clitico_id"}, ...],
                 # Fase L4.5 §3: LISTA (antes L4: dict único|None). fuente ∈
                 # {dativo, se_pasivo, se_impersonal, se_aspectual}. Vacía si
                 # no hay ningún clítico AGX en la oración.
         "notas_mismatch": [str, ...]}
    """
    cfg = cfg or {}
    verbos_mov = set(cfg.get("verbos_movimiento", DEFAULT_VERBOS_MOVIMIENTO))
    case_meta = set(cfg.get("case_meta", DEFAULT_CASE_META))
    case_origen = set(cfg.get("case_origen", DEFAULT_CASE_ORIGEN))
    impersonales = set(cfg.get("impersonales", DEFAULT_IMPERSONALES))

    root = next(t for t in tokens if t["id"] == root_id)
    hijos = sorted((t for t in tokens if t["head"] == root_id),
                   key=lambda t: t["id"])

    core, periferia, notas = [], [], []
    es_pasiva = any(t["deprel"] == "nsubj:pass" for t in hijos)
    # L4.5 §4: AnCora etiqueta el sujeto de la pasiva refleja como 'nsubj'
    # PLANO, no 'nsubj:pass' (verificado empíricamente sobre el gold: 0
    # ocurrencias de nsubj:pass co-ocurriendo con expl:pass en
    # es_ancora-ud-train.conllu) -- sin este flag, "casas" en "se venden
    # casas" heredaria macropapel Actor (CORE_DEPRELS por defecto), lo cual
    # contradice la propia teoria del §4 (el actor es Ø, "casas" es
    # Undergoer/PSA).
    es_pasiva_refleja = any(t["deprel"] == "expl:pass" for t in hijos)
    es_movimiento = root["lemma"].lower() in verbos_mov

    agx_list, ids_agx, morfologicos = _detectar_agx(tokens, hijos, root)
    for entrada in agx_list:
        clit = entrada["clitico"]
        fuente = entrada["fuente"]
        if fuente == "dativo":
            doblado = "doblado, argumento en el sintagma pleno" if entrada["doblado"] else "morfológico, sin doblado"
            notas.append(f"clítico dativo '{clit}' → agx ({doblado})")
        elif fuente == "acusativo":
            notas.append(f"clítico acusativo '{clit}' → agx (concordancia; Undergoer morfológico)")
        elif fuente == "reflexivo":
            notas.append(f"clítico reflexivo '{clit}' → agx (concordancia correferencial)")
        elif fuente == "se_pasivo":
            notas.append(f"'{clit}' pasivo-reflejo → agx (se_pasivo; actor Ø, ver EL)")
        elif fuente == "se_impersonal":
            notas.append(f"'{clit}' impersonal → agx (se_impersonal; actor Ø, ver EL)")
        elif fuente == "se_aspectual":
            notas.append(f"'{clit}' aspectual (correferencial + transitivo) → agx (se_aspectual; telicidad completiva)")

    for t in hijos:
        if t["id"] in ids_agx:
            continue   # concordancia (agx), no argumento — nunca a core/periferia
        deprel = t["deprel"]
        if deprel == "nsubj" and es_pasiva_refleja:
            core.append({"id": t["id"], "text": t["text"],
                         "deprel": deprel, "macropapel": "Undergoer"})
            notas.append(f"pasiva refleja: nsubj '{t['text']}' (AnCora no usa "
                         "nsubj:pass aquí) → Undergoer, no Actor")
            continue
        # Guard "todos los días" (bug de campo de Julian): NP tiempo +
        # cuantificador universal mal-parseada como nsubj/obj degrada a
        # periferia temporal SOLO con evidencia independiente de que no es
        # el argumento real. Va antes de CORE_DEPRELS porque nsubj/obj son
        # llaves de ese diccionario.
        if deprel in ("nsubj", "obj") and _es_np_tiempo_cuantificada(tokens, t) \
                and _guard_frecuencia_dispara(hijos, root, t):
            # Etapa PERIFERIA (2026-07-13): este es el MISMO patrón (nombre
            # de tiempo + cuantificador universal) que _tipo_periferia tipa
            # como "frecuencia"/centro -- antes se degradaba a "temporal" a
            # secas; se corrige aquí para no reintroducir el bug de la EL
            # (frecuencia debe wrappearse con every'/always', no con for'/
            # during'). LDP se mantiene conservador (solo temporal, no
            # ampliado a frecuencia en esta etapa): False explícito.
            periferia.append({"id": t["id"], "text": t["text"],
                              "deprel": deprel, "tipo": "frecuencia",
                              "estrato": "centro",
                              "case": None, "lemma": t["lemma"].lower(),
                              "destacado_inicial": False})
            notas.append(f"guard frecuencia: '{t['text']}' ({deprel}) degradado a "
                         "periferia de frecuencia (NP tiempo + cuantificador universal, "
                         "evidencia independiente de que no es el argumento real)")
            continue
        if deprel in CORE_DEPRELS:
            macropapel = CORE_DEPRELS[deprel]
            core.append({"id": t["id"], "text": t["text"],
                         "deprel": deprel, "macropapel": macropapel})
            if deprel == "obl:agent":
                notas.append("pasiva: obl:agent (periferia sintáctica) → Actor semántico")
            continue

        if deprel == "obl" or deprel in PERIFERIA_DEPRELS:
            case = _case_de(tokens, t["id"])
            # Etapa PERIFERIA (2026-07-13): si el case es en realidad la
            # PRIMERA palabra de una preposición COMPUESTA de razón/
            # concesión/condición ("a pesar de", "a causa de"...), no debe
            # confundirse con el "a" de meta/destino de movimiento ("corrió
            # a Madrid") -- ambigüedad genuina del marcador simple. Se
            # calcula antes para poder EXCLUIR esos casos de la promoción a
            # CORE de más abajo.
            frase_compuesta = _case_compuesto_de(tokens, t["id"])
            es_frase_no_meta = frase_compuesta in (_FRASE_RAZON | _FRASE_CONCESION
                                                    | _FRASE_CONDICION)
            # obl con "por" bajo pasiva = agente → Actor (core)
            if deprel == "obl" and es_pasiva and case == "por":
                core.append({"id": t["id"], "text": t["text"],
                             "deprel": "obl", "macropapel": "Actor"})
                notas.append("pasiva: obl con 'por' → Actor semántico")
                continue
            # meta/origen de verbos de movimiento → argumento (delimitador)
            if deprel == "obl" and es_movimiento and case in case_meta and not es_frase_no_meta:
                core.append({"id": t["id"], "text": t["text"],
                             "deprel": "obl", "macropapel": "Meta"})
                notas.append(f"movimiento: obl '{case} {t['text']}' → Meta (core)")
                continue
            if deprel == "obl" and es_movimiento and case in case_origen and not es_frase_no_meta:
                core.append({"id": t["id"], "text": t["text"],
                             "deprel": "obl", "macropapel": "Origen"})
                notas.append(f"movimiento: obl '{case} {t['text']}' → Origen (core)")
                continue
            tipo, estrato = _tipo_periferia(tokens, t, case)
            periferia.append({"id": t["id"], "text": t["text"],
                              "deprel": deprel, "tipo": tipo, "estrato": estrato,
                              "case": case, "lemma": t["lemma"].lower(),
                              # frase preposicional COMPUESTA ("a pesar de",
                              # "debido a"...) -- insumo de wrappers_ls para
                              # razón/concesión/condición, donde el `case`
                              # simple (primera palabra) no basta para el
                              # lookup de la tabla (ver _case_compuesto_de).
                              "frase": frase_compuesta,
                              "destacado_inicial": (tipo == "temporal"
                                                    and _es_destacado_inicial(tokens, t))})

    # Dativo realizado SOLO morfológicamente (clítico sin doblar): al FINAL
    # de core, no en su posición de id — convención RRG de macrorroles
    # (Actor/Undergoer) antes que el NMR dativo, igual que en el doblado
    # ("...dio un beso a María") donde el pleno ya cae ahí por orden natural.
    # L5 §1: puede haber VARIOS clíticos solo-morfológicos (p.ej. "me lo
    # dio": me=dativo x?, lo... — aunque lo/la quedan fuera de _CLITICOS_AGX;
    # el caso real es dativo + acusativo de 1ª/2ª persona). Se ordenan
    # macrorroles (Actor/Undergoer) antes que NMR(dativo), misma convención
    # que el doblado.
    for m in sorted(morfologicos,
                    key=lambda m: 0 if m["macropapel"] in ("Actor", "Undergoer") else 1):
        core.append(m)

    # ── Mismatches sin realización sintáctica ─────────────────────────────
    impersonal = root["lemma"].lower() in impersonales
    tiene_sujeto = any(c["deprel"] in ("nsubj", "nsubj:pass", "csubj")
                       for c in core)
    # L4.5 §4 (González Vergara): con se-pasivo/impersonal el actor no es
    # "implícito por pro-drop" -- es ESTRUCTURALMENTE Ø (inespecificación
    # léxica del argumento de mayor jerarquía). El mapper (rrg_ls_mapper.py)
    # construye la EL con Ø consultando 'agx'; aquí NO se dispara pro-drop
    # para ese hueco (evita un actor_implicito espurio que el mapper tendría
    # que pisar).
    tiene_se_sin_actor = any(e["fuente"] in ("se_pasivo", "se_impersonal")
                             for e in agx_list)

    actor_implicito = None
    if impersonal:
        notas.append(f"impersonal/pleonástico: '{root['lemma']}' sin argumento semántico")
    elif tiene_se_sin_actor:
        pass
    elif not tiene_sujeto:
        feats = _parse_feats(root.get("feats", ""))
        persona = feats.get("Person", "3")
        numero = "pl" if feats.get("Number") == "Plur" else "sg"
        actor_implicito = {"persona": persona, "numero": numero,
                           "etiqueta": f"{persona}{numero}"}
        notas.append(f"pro-drop: actor implícito {persona}{numero} "
                     "(de la morfología verbal)")

    return {"core": core, "periferia": periferia,
            "actor_implicito": actor_implicito,
            "impersonal": impersonal, "agx": agx_list,
            "notas_mismatch": notas}


def _objeto_desnudo(tokens: list[dict], obj_id: int) -> bool:
    """Fase L4.5 §5: objeto SIN determinante (definido/demostrativo/
    posesivo/indefinido -- todos delimitan por igual) ni numeral --
    'manzanas' (desnudo, plural/masa) vs 'la manzana'/'esas manzanas'/
    'sus manzanas'/'unas manzanas'/'cinco manzanas' (todos delimitan)."""
    hijos_obj = [t for t in tokens if t["head"] == obj_id]
    tiene_det_o_num = any(t["deprel"] in ("det", "det:poss", "nummod", "nummod:gov")
                          for t in hijos_obj)
    return not tiene_det_o_num


def tiene_delimitador_nuclear(roles: dict, tokens: list[dict] | None = None) -> bool:
    """¿Hay argumento delimitador en el core (obj DELIMITADO o Meta de
    movimiento)? Una duración periférica ("tres horas") NUNCA delimita
    (Prueba 4 de Van Valin): sin esto, Active_Accomplishment no está
    licenciada.

    Fase L4.5 §5 (bug de campo de Julian, delimitación composicional): un
    obj DESNUDO (plural/masa, sin determinante ni numeral -- "come
    manzanas") NO delimita, aunque el deprel sea 'obj' -- solo un obj
    DELIMITADO ("come la manzana"/"come cinco manzanas") lo hace. Requiere
    `tokens` (la oración completa, para mirar los hijos del obj); sin
    `tokens` (retro-compatibilidad) cualquier 'obj' delimita, como antes de
    L4.5."""
    for c in roles["core"]:
        if c["macropapel"] == "Meta":
            return True
        if c["deprel"] == "obj":
            if tokens is None or not _objeto_desnudo(tokens, c["id"]):
                return True
    return False


def objeto_con_numeral_medida(roles: dict, tokens: list[dict]) -> bool:
    """¿El obj del core lleva un NUMERAL (nummod) que lo mide? -- 'cinco
    kilómetros', 'tres manzanas', 'dos piscinas'.

    Guarda del gate G-AA-medida (Fase L5 §0.1): la delimitación por
    CANTIDAD MEDIDA de un verbo durativo (correr cinco kilómetros) licencia
    Active_Accomplishment composicional aunque el clasificador falle en la
    telicidad. A diferencia de `tiene_delimitador_nuclear`, un determinante
    simple ('el carro') NO cuenta -- solo un numeral: "empuja el carro" (det,
    sin nummod) NO debe disparar el gate; "empuja tres carros" sí mediría."""
    for c in roles["core"]:
        if c["deprel"] == "obj":
            if any(t["head"] == c["id"] and t["deprel"] in ("nummod", "nummod:gov")
                   for t in tokens):
                return True
    return False
