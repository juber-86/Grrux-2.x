"""Wrappers de periferia en la LS (Fase LINKING, Etapa L1b; reescrito en la
Etapa PERIFERIA, 2026-07-13 — ver prompt_opus48_periferia.md).

En la GRR la periferia no es un adjunto "suelto": se representa como un
operador/predicado que ENVUELVE la LS del estrato al que modifica. Este
módulo compone esos wrappers sobre la LS ya construida (formal y léxica) a
partir de la periferia ya tipada por `nucleo_periferia.analizar_roles` (cada
item trae `tipo` y `estrato`; ver ese módulo para la doctrina de tipado).

DOCTRINA (Julian, 2026-07-13): NINGÚN elemento periférico queda fuera de la
EL. Los adverbios se formulan como predicados MONOVALENTES `adv'([LS])`; las
frases preposicionales, como preposiciones predicativas BIVALENTES
`prep'(x, [LS])` donde `x` es el objeto de la preposición (simplificación
documentada: la cabeza del sintagma, no el NP completo con modificadores —
eso es la categoría de fix B, fuera de esta etapa) e `y` es la LS del
estrato modificado. Cuando no hay entrada específica para una preposición o
un adverbio, la PROPIA preposición/lema es el predicado (mata "otro"):
`with'(martillo, [LS])`, `también'([LS])`.

ANIDAMIENTO (Opción A, Julian 2026-07-13): cada wrapper envuelve la LS
COMPLETA del estrato al que pertenece (no el sub-predicado exacto); el
ANCLAJE DEL ÁRBOL sí es exacto (NUC/CORE/CLAUSE, ver `ud2rrg.py`). Orden de
adentro hacia afuera (núcleo → centro → cláusula), y TODOS los items de
periferia se apilan (no solo el primero por capa) en orden estable por id de
token dentro de cada capa:

  0  nucleo   aspectual         (completamente'(...))
 10  centro   manera            (lentamente'(...))
 20  centro   locativo          (be-in'(x, ...))
 25  centro   generico          (with'(x, ...) / lema'(...))  -- mata "otro"
 30  centro   temporal (marco)  (for'/during'/at'/before'/... (x, ...))
 40  centro   temporal (adv.)   (yesterday'(...))
 45  centro   frecuencia        (always'(...) / every'(x, ...))
 50  clausula razon             (because-of'(x, ...))
 55  clausula concesion         (despite'(x, ...))
 60  clausula condicion         (in-case-of'(x, ...))
 70  clausula epistemico        (probably'(...))            -- más externa

Solo el wrapper MÁS INTERNO aplicado envuelve el LS original entre corchetes
`[...]`; los wrappers subsiguientes embeben la cadena ya formateada (sin
corchetes adicionales) — así sale en el ejemplo canónico de Julian:
"Ayer Juan corrió tres horas en el parque" →
  yesterday'(for'(horas, be-in'(parque, [do'(Juan, [correr'(Juan)])])))

LIMITACIÓN DE DISEÑO (documentada, no oculta): `componer_wrappers` recibe
`periferia` (no `toks`), por lo que NO puede verificar por sí mismo si una
duración desnuda ("tres horas" vs "todos los días") lleva numeral/determinante
de cantidad — la misma ambigüedad que `pruebas_estructurales` resolvió con
`_DET_CANTIDAD` (ver ese módulo). En vez de duplicar esa heurística, el
mapper (que sí tiene `toks` y ya corre `detectar_evidencia`) anota cada item
de periferia con `cuantificada=True` cuando P4 ya lo confirmó; sin esa
anotación (p.ej. en tests unitarios de este módulo) la duración desnuda NO
se envuelve — sesgo conservador, consistente con el resto del pipeline
("solo evidencia presente y unívoca dispara").

Función pura: sin Stanza, sin modelos, sin I/O.
"""

from .nucleo_periferia import _NOMBRES_TIEMPO

# ---------------------------------------------------------------------------
# Tablas por defecto (config.yaml → wrappers_ls las sobreescribe)
# ---------------------------------------------------------------------------
DEFAULT_LOCATIVOS = {
    "en": "be-in", "sobre": "be-on", "encima": "be-on",
    "bajo": "be-under", "debajo": "be-under", "entre": "be-between",
    "cerca": "be-near", "delante": "be-in-front-of", "ante": "be-in-front-of",
    "detrás": "be-behind", "tras": "be-behind", "junto": "be-beside",
}
DEFAULT_LOCATIVO_FALLBACK = "be-at"

# 'durante'/'por'/'a'/'en' tienen regla semántica propia, no van en esta tabla.
DEFAULT_TEMPORALES_SIMPLES = {
    "antes": "before", "después": "after", "hasta": "until", "desde": "since",
}

DEFAULT_ADVERBIOS_MONOVALENTES = {
    "ayer": "yesterday", "hoy": "today", "anoche": "last.night",
    "ahora": "now", "mañana": "tomorrow",   # solo alcanzable vía deprel=advmod (NOUN "la mañana" es duración, otra rama)
}
DEFAULT_SIN_WRAPPER = ["ya", "todavía"]     # aspectuales, operadores futuros — quedan listados, sin envolver

# NÚCLEO -- adverbios aspectuales de fase/grado.
DEFAULT_ASPECTUALES = {
    "completamente": "completely", "totalmente": "completely",
    "íntegramente": "completely", "parcialmente": "partially",
    "continuamente": "continuously", "ininterrumpidamente": "continuously",
    "incesantemente": "continuously", "constantemente": "constantly",
    "gradualmente": "gradually", "paulatinamente": "gradually",
    "progresivamente": "progressively",
}

# CLÁUSULA -- epistémicos/evidenciales.
DEFAULT_EPISTEMICOS = {
    "probablemente": "probably", "posiblemente": "possibly",
    "seguramente": "surely", "quizá": "maybe", "quizás": "maybe",
    "tal vez": "maybe", "evidentemente": "evidently",
    "obviamente": "obviously", "aparentemente": "apparently",
}

# CENTRO -- frecuencia (adverbio monovalente / NP distributivo bivalente).
DEFAULT_FRECUENCIA_ADVERBIOS = {
    "siempre": "always", "nunca": "never", "frecuentemente": "frequently",
    "habitualmente": "habitually", "a menudo": "often", "a veces": "sometimes",
    "algunas veces": "sometimes",
}
DEFAULT_FRECUENCIA_DISTRIBUTIVA = "every"   # NP distributivo: every'(x, [LS])

# CLÁUSULA -- razón/concesión/condición.
DEFAULT_RAZON = {
    "debido a": "because-of", "a causa de": "because-of",
    "por causa de": "because-of", "gracias a": "thanks-to", "por": "because-of",
}
DEFAULT_RAZON_FALLBACK = "because-of"
DEFAULT_CONCESION = {"a pesar de": "despite", "pese a": "despite"}
DEFAULT_CONCESION_FALLBACK = "despite"
DEFAULT_CONDICION = {"en caso de": "in-case-of"}
DEFAULT_CONDICION_FALLBACK = "in-case-of"

# GENÉRICO (mata "otro") -- preposiciones frecuentes sin capa propia;
# cualquier otra usa su propio lema como predicado (fallback documentado).
DEFAULT_PREPOSICIONES_PREDICATIVAS = {
    "con": "with", "sin": "without", "para": "for-benefit",
    "contra": "against", "según": "according-to", "mediante": "by-means-of",
}


def _tabla(cfg, clave, default):
    return {**default, **cfg.get(clave, {})} if isinstance(default, dict) \
        else list(cfg.get(clave, default))


def _embed(ls: str, primero: bool) -> str:
    return f"[{ls}]" if primero else ls


def _pred_temporal_con_case(p: dict, cfg: dict) -> str | None:
    """Regla case→predicado para periferia temporal CON preposición."""
    case = p.get("case")
    if case is None:
        return None
    simples = _tabla(cfg, "temporales_simples", DEFAULT_TEMPORALES_SIMPLES)
    if case in simples:
        return simples[case]
    if case == "durante":
        # Regla SEMÁNTICA: cantidad de tiempo → for'; evento/intervalo → during'.
        es_cantidad = p.get("lemma") in _NOMBRES_TIEMPO or p.get("cuantificada")
        return "for" if es_cantidad else "during"
    if case == "por":
        return "for"
    if case in ("a", "en"):
        return "at"
    return None


def _pred_temporal_desnuda(p: dict) -> str | None:
    """Duración desnuda (sin preposición): 'tres horas', 'toda la noche'."""
    if p.get("case") is not None or p.get("deprel") == "advmod":
        return None   # no es desnuda, o es un adverbio (otra capa)
    if p.get("lemma") in _NOMBRES_TIEMPO and p.get("cuantificada"):
        return "for"
    return None


# ---------------------------------------------------------------------------
# Clasificación — cada item de periferia se convierte en una especificación
# de wrapper: {"orden", "forma": "mono"|"bi", "pred", "x", "aplicado",
# "razon"?}. `aplicado` es False para items detectados-pero-deliberadamente-
# sin-envolver (ya/todavía); en ese caso "forma"/"pred"/"x" no se usan.
# ---------------------------------------------------------------------------
def _clasificar(p: dict, cfg: dict) -> dict | None:
    tipo = p.get("tipo")
    case = p.get("case")
    deprel = p.get("deprel")
    lemma = p.get("lemma") or ""
    texto = p.get("text", lemma)

    if tipo == "aspectual":
        tabla = _tabla(cfg, "aspectuales", DEFAULT_ASPECTUALES)
        return {"orden": 0, "forma": "mono", "pred": tabla.get(lemma, lemma)}

    if tipo == "manera":
        return {"orden": 10, "forma": "mono", "pred": lemma}

    if tipo == "locativo":
        tabla = _tabla(cfg, "locativos", DEFAULT_LOCATIVOS)
        fallback = cfg.get("locativo_fallback", DEFAULT_LOCATIVO_FALLBACK)
        return {"orden": 20, "forma": "bi", "pred": tabla.get(case, fallback), "x": texto}

    if tipo == "temporal":
        pred = _pred_temporal_con_case(p, cfg) or _pred_temporal_desnuda(p)
        if pred:
            return {"orden": 30, "forma": "bi", "pred": pred, "x": texto}
        sin_wrapper = _tabla(cfg, "sin_wrapper", DEFAULT_SIN_WRAPPER)
        if case is None and deprel == "advmod":
            if lemma in sin_wrapper:
                return {"orden": 40, "aplicado": False, "razon": "sin_wrapper"}
            tabla_adv = _tabla(cfg, "adverbios_monovalentes", DEFAULT_ADVERBIOS_MONOVALENTES)
            return {"orden": 40, "forma": "mono", "pred": tabla_adv.get(lemma, lemma)}
        if case is not None:
            # preposición temporal sin entrada específica en la tabla --
            # mismo mecanismo que "generico": la preposición misma es el
            # predicado (nada queda sin envolver).
            tabla = _tabla(cfg, "preposiciones_predicativas", DEFAULT_PREPOSICIONES_PREDICATIVAS)
            return {"orden": 30, "forma": "bi", "pred": tabla.get(case, case), "x": texto}
        # bare NP de tiempo sin cuantificar (obl:tmod puro, p.ej.): fallback
        # conservador, duración por defecto.
        return {"orden": 30, "forma": "bi", "pred": "for", "x": texto}

    if tipo == "frecuencia":
        if deprel == "advmod":
            tabla = _tabla(cfg, "frecuencia_adverbios", DEFAULT_FRECUENCIA_ADVERBIOS)
            return {"orden": 45, "forma": "mono", "pred": tabla.get(lemma, lemma)}
        pred = cfg.get("frecuencia_distributiva", DEFAULT_FRECUENCIA_DISTRIBUTIVA)
        return {"orden": 45, "forma": "bi", "pred": pred, "x": texto}

    if tipo == "razon":
        tabla = _tabla(cfg, "razon", DEFAULT_RAZON)
        fallback = cfg.get("razon_fallback", DEFAULT_RAZON_FALLBACK)
        frase = p.get("frase") or case
        return {"orden": 50, "forma": "bi", "pred": tabla.get(frase, fallback), "x": texto}

    if tipo == "concesion":
        tabla = _tabla(cfg, "concesion", DEFAULT_CONCESION)
        fallback = cfg.get("concesion_fallback", DEFAULT_CONCESION_FALLBACK)
        frase = p.get("frase") or case
        return {"orden": 55, "forma": "bi", "pred": tabla.get(frase, fallback), "x": texto}

    if tipo == "condicion":
        tabla = _tabla(cfg, "condicion", DEFAULT_CONDICION)
        fallback = cfg.get("condicion_fallback", DEFAULT_CONDICION_FALLBACK)
        frase = p.get("frase") or case
        return {"orden": 60, "forma": "bi", "pred": tabla.get(frase, fallback), "x": texto}

    if tipo == "epistemico":
        tabla = _tabla(cfg, "epistemicos", DEFAULT_EPISTEMICOS)
        return {"orden": 70, "forma": "mono", "pred": tabla.get(lemma, lemma)}

    # "generico" (o cualquier tipo desconocido, por robustez): mata "otro".
    if case is not None:
        tabla = _tabla(cfg, "preposiciones_predicativas", DEFAULT_PREPOSICIONES_PREDICATIVAS)
        return {"orden": 25, "forma": "bi", "pred": tabla.get(case, case), "x": texto}
    return {"orden": 25, "forma": "mono", "pred": lemma}


# ---------------------------------------------------------------------------
# Composición
# ---------------------------------------------------------------------------
def componer_wrappers(ls_formal: str, ls_lexical: str, periferia: list[dict],
                      cfg: dict | None = None,
                      cubiertos_por_operador: dict | None = None
                      ) -> tuple[str, str, list[dict]]:
    """Envuelve ls_formal/ls_lexical con TODOS los wrappers de periferia
    aplicables (Opción A: cada wrapper envuelve la LS completa del estrato,
    ver docstring del módulo). Apila TODOS los items (no solo el primero por
    capa), en orden estable por id de token dentro de cada capa.

    `cubiertos_por_operador` es `{token_id: 'NEG'}` (Etapa OPERATORS_2 §1): un
    elemento que YA se representa como operador NO se envuelve además como
    predicado de la EL. En Van Valin los operadores no son predicados; tener
    'no' a la vez en ⟨NEG⟩ y en `no'(…)` es duplicar la misma información. Se
    filtra por ID DE TOKEN, no por lista de lemas, para que el criterio sea
    exactamente "¿disparó un operador?": un adverbio que no dispara ninguno
    (p.ej. 'aparentemente', evidencial, y EVID no está implementado) conserva
    su wrapper léxico intacto. La etapa quita duplicación, no información.

    Returns:
        (formal, lexical, aplicados) — aplicados: lista de
        {"capa", "id", "trigger", "pred", "aplicado": bool, "estrato"}
        (aplicado=False para casos detectados pero deliberadamente sin
        envolver, p.ej. ya/todavía, o ya cubiertos por un operador —
        `razon="operador"` con el operador en `operador`; "id" es el id del
        item de periferia — insumo del canal MISC, Etapa L2).
    """
    cfg = cfg or {}
    cubiertos = cubiertos_por_operador or {}
    aplicados_operador = []
    especificaciones = []
    for p in periferia:
        if p.get("tipo") is None:
            continue
        op = cubiertos.get(p["id"])
        if op is not None:
            aplicados_operador.append({
                "capa": p["tipo"], "id": p["id"], "trigger": p["text"],
                "pred": None, "aplicado": False, "razon": "operador",
                "operador": op, "estrato": p.get("estrato")})
            continue
        # advcl = adjunto CLAUSAL (cabeza verbal, "hace un par de días",
        # "mientras marcará la pauta..."): terreno de juntura/compuestas
        # (xcomp encadenado), explícitamente POSPUESTO por Julian -- envolver
        # con el lema del verbo como si fuera un adverbio simple produce una
        # EL incorrecta y una rama -PERI que el árbol nunca tiene marcada
        # para cláusulas subordinadas. Se deja SIN envolver (mismo
        # comportamiento conservador que el viejo "otro": solo se verifica
        # presencia, nunca error) hasta que exista esa maquinaria.
        if p.get("deprel") == "advcl":
            continue
        spec = _clasificar(p, cfg)
        if spec is None:
            continue
        especificaciones.append({**spec, "id": p["id"], "trigger": p["text"],
                                 "capa": p["tipo"], "estrato": p.get("estrato")})

    especificaciones.sort(key=lambda e: (e["orden"], e["id"]))

    formal, lexical = ls_formal, ls_lexical
    primero = True
    aplicados = list(aplicados_operador)
    for e in especificaciones:
        if not e.get("aplicado", True):
            aplicados.append({"capa": e["capa"], "id": e["id"], "trigger": e["trigger"],
                              "pred": None, "aplicado": False, "razon": e.get("razon"),
                              "estrato": e.get("estrato")})
            continue
        pred = e["pred"]
        if e["forma"] == "mono":
            formal = f"{pred}'({_embed(formal, primero)})"
            lexical = f"{pred}'({_embed(lexical, primero)})"
        else:
            x = e["x"]
            formal = f"{pred}'({x}, {_embed(formal, primero)})"
            lexical = f"{pred}'({x}, {_embed(lexical, primero)})"
        primero = False
        aplicados.append({"capa": e["capa"], "id": e["id"], "trigger": e["trigger"],
                          "pred": f"{pred}'", "aplicado": True, "estrato": e.get("estrato")})

    return formal, lexical, aplicados
