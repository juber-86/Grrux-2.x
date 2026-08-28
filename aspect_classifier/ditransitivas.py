"""Estructuras Lógicas ditransitivas (Fase LINKING, Etapa L2.5).

"Juan le dio flores a María" hoy produciría una LS de plantilla Active
Accomplishment (`do'(juan,[dar'(juan,flores)]) & INGR consumed'(flores)`) —
ERRÓNEA: los verbos con recipiente son Realizaciones/Logros CAUSATIVOS cuya
LS une actividad + estado resultante de posesión, no un "consumo" del tema.

Diseño (decisión de Julian, no re-litigar): los roles temáticos son
POSICIONES en la LS, no etiquetas que un modelo clasifique. Sin LLM/probe:
(a) se elige la PLANTILLA de LS por verbo+construcción (léxico curado en
`data/verbos_ditransitivos.xlsx` + trigger estructural + log de
candidatos — mismo patrón que `causatividad.py`), (b) los slots sintácticos
ya vienen mapeados a macrorroles por Etapa 1 (`nucleo_periferia`), (c) el
rol temático específico (Efectuador/Poseedor/Tema/...) es un lookup fijo
por posición, tomado de `data/continuum_de_relaciones_tematicas.xlsx`
(columnas "Primer arg. de do'", "argumento de estado pred'(x)", etc. —
Van Valin 2005:58). Un fallback con probe BERTIN queda para el futuro SOLO
si el log de candidatos demuestra huecos reales (no implementado aquí).

Plantillas (metalenguaje inglés en primitivos; predicados léxicos españoles
solo en la plantilla de comunicación, ver abajo):

  TRANSFERENCIA ("dio un regalo a María"):
    [do'(x, Ø)] CAUSE [BECOME have'(y, z)]
    x=efectuador, y=poseedor, z=tema. Clase: accomplishment (causativo).

  BENEFACTIVA ("compró/hizo/preparó/reparó/buscó z para y"):
    La entrada léxica selecciona uno de cinco subtipos semánticos:
    obtención `BECOME have'(x,z)`, preparación `BECOME prepared'(z)`,
    creación `BECOME exist'(z)`, cambio de estado con un predicado
    monovalente curado, o actividad `do'(x,[lema'(x,z)])`. El propósito
    curado se compone como `PURP [BECOME have'(y,z)]`, `PURP [have'(y,z)]`
    o se omite. x=efectuador, y=poseedor/beneficiario, z=tema; sólo el
    subtipo actividad es `activity`, los resultativos son `accomplishment`.

  COMUNICACIÓN ("le dijo la verdad/que viniera a Pedro") — FORMA SIMPLE:
    do'(x, [<lema>.to.(y)'(x, z)])
    x=emisor, y=receptor (embebido en el NOMBRE del predicado, no es un
    argumento numerado — esta plantilla solo tiene dos slots x,z), z=tema
    (puede ser el núcleo de un ccomp: "dijo QUE VINIERA" → z=viniera).
    Clase: activity. ESTO ES UNA SIMPLIFICACIÓN deliberada de la forma
    plena de Van Valin `do'(x, [express(α).to.(β).in.language.(γ)'(x, z)])`
    — Julian pidió dejarla simple por ahora y refinar MUCHO después.
    El bucle de corrección hace upsert atómico de la especificación
    estructurada y sólo la conserva si el reanálisis la confirma exactamente.

El clítico/AGX no altera la LS ni la clase (ya garantizado por Etapa 1,
L1a): siempre UN solo x para el recipiente/receptor, venga como clítico
solo (x = etiqueta morfológica '3sg'), sintagma pleno solo, o doblado.

Funciones puras sobre `roles` (de `nucleo_periferia.analizar_roles`) y
tokens; sin Stanza, sin modelos — testeable en frío.
"""

import csv
import re
from pathlib import Path

import pandas as pd

from . import linking

PKG_DIR = Path(__file__).parent
LEXICON_XLSX = PKG_DIR / "data" / "verbos_ditransitivos.xlsx"
CONTINUUM_XLSX = PKG_DIR / "data" / "continuum_de_relaciones_tematicas.xlsx"
CANDIDATOS_CSV = PKG_DIR / "data" / "ditransitivos_candidatos.csv"

DEFAULT_PLANTILLA = "transferencia"
DEFAULT_CASE_PARA = "para"

PLANTILLAS = {"transferencia", "benefactiva", "comunicacion"}
SUBTIPOS_BENEFACTIVOS = {
    "obtencion", "preparacion", "creacion", "cambio_estado", "actividad",
}
PROPOSITOS = {"become_have", "have", "none"}
_PREDICADO_RESULTADO_RE = re.compile(r"^[a-z][a-z0-9_.-]*'$", re.IGNORECASE)

# Rol temático específico por posición x/y/z, y su macrorrol (Actor/
# Undergoer/NMR) — lookup DIRECTO (autorizado por Julian: "basta el mapeo
# directo" para las plantillas de este prompt). Verificado contra
# continuum_de_relaciones_tematicas.xlsx (ver cargar_continuum): EFECTUADOR
# y EMISOR están en la columna "Primer arg. de do'(x,...)"; el continuum
# lista POSEEDOR para el primer arg. de have'(y,z) — etiqueta usada aquí
# (decisión de Julian, L3; en L2.5 se usó "Recipiente", tomado de
# jerarquia_semantica_a_gramatical.xlsx en inglés, Given-to/Sent-to/
# Handed-to → Recipient — renombrado para ceñirse al continuum). Aquí el
# NMR(dativo) de Etapa 1 (L1a) ya decidió que el dativo español NO es
# macrorrol — decisión previa, no re-litigada — así que "Poseedor"/
# "Receptor" mapean a NMR, no a Actor/Undergoer, pese a que la jerarquía
# inglesa permite ambos. La comunicación (sin have') conserva "Receptor".
_ROLES_POR_PLANTILLA = {
    "transferencia": {"x": "Efectuador", "y": "Poseedor", "z": "Tema"},
    "benefactiva":   {"x": "Efectuador", "y": "Poseedor", "z": "Tema"},
    "comunicacion":  {"x": "Emisor",     "y": "Receptor",   "z": "Contenido"},
}
_MACRORROL_X = "Actor"
_MACRORROL_Z_OBJ = "Undergoer"      # z desde obj
_MACRORROL_Z_CCOMP = "Tema"         # z desde ccomp (mismo macropapel que ya usa Etapa 1)
_MACRORROL_Y = "NMR"

_CLASE_POR_PLANTILLA = {
    "transferencia": "accomplishment",
    "benefactiva":    "accomplishment",
    "comunicacion":   "activity",
}


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------
def cargar_lexicon(path: Path = LEXICON_XLSX) -> dict[str, dict]:
    """Carga y valida el léxico curado, indexado por lema.

    Las columnas benefactivas son obligatorias en el libro migrado, pero sólo
    deben llevar valor en filas de esa familia. Una inconsistencia falla con
    la fila/lema exactos: nunca degrada silenciosamente a la antigua plantilla
    rígida basada en ``have'``.
    """
    df = pd.read_excel(path)
    requeridas = {"lema", "plantilla", "subtipo_benefactivo",
                  "predicado_resultado", "proposito", "ambiguo", "notas", "fuente"}
    faltantes = requeridas - set(df.columns)
    if faltantes:
        raise ValueError(f"{Path(path).name}: faltan columnas: {', '.join(sorted(faltantes))}")
    lexicon = {}
    for indice, row in df.iterrows():
        fila = indice + 2
        lema = str(row["lema"]).strip().lower()
        plantilla = str(row["plantilla"]).strip().lower()
        if not lema or lema == "nan":
            raise ValueError(f"{Path(path).name}: fila {fila}: lema vacío")
        if lema in lexicon:
            raise ValueError(f"{Path(path).name}: fila {fila}: lema duplicado {lema!r}")
        if plantilla not in PLANTILLAS:
            raise ValueError(f"{Path(path).name}: fila {fila} ({lema}): plantilla inválida {plantilla!r}")
        subtipo = _celda(row.get("subtipo_benefactivo"))
        predicado = _celda(row.get("predicado_resultado"))
        proposito = _celda(row.get("proposito"))
        if plantilla == "benefactiva":
            if subtipo not in SUBTIPOS_BENEFACTIVOS:
                raise ValueError(f"{Path(path).name}: fila {fila} ({lema}): subtipo benefactivo inválido {subtipo!r}")
            if proposito not in PROPOSITOS:
                raise ValueError(f"{Path(path).name}: fila {fila} ({lema}): propósito inválido {proposito!r}")
            exige_predicado = subtipo in {"preparacion", "creacion", "cambio_estado"}
            if exige_predicado and not predicado:
                raise ValueError(f"{Path(path).name}: fila {fila} ({lema}): falta predicado resultativo")
            if predicado and not _PREDICADO_RESULTADO_RE.fullmatch(predicado):
                raise ValueError(f"{Path(path).name}: fila {fila} ({lema}): predicado resultativo inválido {predicado!r}")
            if subtipo in {"obtencion", "actividad"} and predicado:
                raise ValueError(f"{Path(path).name}: fila {fila} ({lema}): {subtipo} no admite predicado resultativo")
        elif subtipo or predicado or proposito:
            raise ValueError(f"{Path(path).name}: fila {fila} ({lema}): campos benefactivos en {plantilla}")
        notas = _celda(row.get("notas"))
        lexicon[lema] = {
            "plantilla": plantilla,
            "subtipo_benefactivo": subtipo or None,
            "predicado_resultado": predicado or None,
            "proposito": proposito or None,
            "ambiguo": bool(row.get("ambiguo", False)),
            "notas": notas,
            "fuente": _celda(row.get("fuente")) or "curado",
        }
    return lexicon


def _celda(valor) -> str:
    return "" if pd.isna(valor) else str(valor).strip().lower()


def cargar_continuum(path: Path = CONTINUUM_XLSX) -> dict[str, list[str]]:
    """Tabla interna posición→roles del continuum de relaciones temáticas
    (Van Valin 2005:58, xlsx de Julian). 5 columnas = 5 posiciones de LS;
    cada columna es una lista independiente (no alineada por fila) de
    roles válidos en esa posición, de más agentivo a más pacientivo.
    No se usa en el hot path de este prompt ("basta el mapeo directo"),
    mantenido como insumo/validación para la siguiente fase de posiciones."""
    # fila 0 = título, fila 1 = subtítulo, fila 2 = headers reales
    df = pd.read_excel(path, header=2)
    return {str(col).strip(): [v for v in df[col].dropna().tolist()]
            for col in df.columns}


# ---------------------------------------------------------------------------
# Trigger estructural (usa lo que Etapa 1 / L1a ya produce)
# ---------------------------------------------------------------------------
def _actor(roles: dict) -> dict | None:
    if roles.get("actor_implicito") is not None:
        return {"id": None, "text": roles["actor_implicito"]["etiqueta"],
               "deprel": "pro-drop"}
    for c in roles.get("core", []):
        if c["macropapel"] == "Actor":
            return {"id": c["id"], "text": c["text"], "deprel": c["deprel"]}
    return None


def _tema(roles: dict) -> dict | None:
    """Prefiere Undergoer (obj); si no hay, Tema (ccomp) — comunicación."""
    for c in roles.get("core", []):
        if c["macropapel"] == "Undergoer":
            return {"id": c["id"], "text": c["text"], "deprel": c["deprel"],
                    "es_ccomp": False}
    for c in roles.get("core", []):
        if c["macropapel"] == "Tema":
            return {"id": c["id"], "text": c["text"], "deprel": c["deprel"],
                    "es_ccomp": True}
    return None


def _recipiente_dativo(roles: dict) -> dict | None:
    for c in roles.get("core", []):
        if c["macropapel"] == "NMR(dativo)":
            return {"id": c["id"], "text": c["text"], "deprel": c["deprel"]}
    return None


def _recipiente_agx_doblado(roles: dict) -> tuple[dict | None, int | None]:
    """Fallback morfologico (hito DITRANS-AGX, 2026-08-19).

    Un clitico AGX de fuente `dativo` con `doblado=True` es evidencia de
    recipiente INDEPENDIENTE de como el parser haya etiquetado el sintagma
    pleno: `nucleo_periferia` ya resolvio que "le" es dativo y que el token
    `arg_id` es su doblado. Etapa 1 solo asigna `NMR(dativo)` a `obl:arg`/
    `iobj`, asi que cuando Stanza etiqueta el doblado como `obl` a secas
    ("juan le da un beso a maria") el recipiente se pierde y toda la
    construccion ditransitiva se desactiva en silencio.

    Devuelve `(y, y_periferia_id)`: el sintagma pleno se busca primero en
    core (donde puede estar con un macropapel equivocado, p. ej. `Meta`) y
    despues en periferia; en el segundo caso el id se devuelve para que
    `construir_ditransitiva` lo haga ASCENDER (misma mecanica que
    `benefactivo_para`, decision 4). `(None, None)` si no hay doblado.
    """
    agx = next((a for a in (roles.get("agx") or [])
                if a.get("fuente") == "dativo" and a.get("arg_id") is not None),
               None)
    if agx is None:
        return None, None
    for lista, en_periferia in ((roles.get("core") or [], False),
                                (roles.get("periferia") or [], True)):
        for c in lista:
            if c["id"] == agx["arg_id"]:
                y = {"id": c["id"], "text": c["text"], "deprel": c["deprel"]}
                return y, (c["id"] if en_periferia else None)
    return None, None


def _beneficiario_para(roles: dict, case_para: str) -> dict | None:
    for p in roles.get("periferia", []):
        if p.get("case") == case_para:
            return {"id": p["id"], "text": p["text"], "deprel": p["deprel"]}
    return None


def detectar_trigger(roles: dict, verb_lemma: str, lexicon: dict,
                     cfg: dict | None = None) -> dict:
    """Construcción ditransitiva detectada cuando:
      - hay NMR(dativo) en core (clítico solo o doblado) Y hay tema
        (obj o ccomp) → tipo "dativo"; o
      - el verbo está en el léxico como "benefactiva" Y hay obj Y hay
        periferia con case='para' → tipo "benefactivo_para" (decisión 4:
        el beneficiario ASCIENDE de periferia a argumento).
      - (DITRANS-AGX) hay un clitico AGX dativo DOBLADO Y hay tema, aunque
        el sintagma doblado no haya quedado como NMR(dativo) en core
        (parser lo etiqueto `obl`) → tipo "dativo_agx"; el doblado asciende
        desde periferia si hace falta. Flag `fallback_agx_dativo`.

    Sin ninguno de los tres → sin disparo (transitivas/intransitivas siguen
    igual que hoy).

    Returns:
        {"disparo": bool, "tipo": "dativo"|"benefactivo_para"|"dativo_agx"|None,
         "x": {...}|None, "y": {...}|None, "z": {...}|None}
    """
    cfg = cfg or {}
    x = _actor(roles)
    z = _tema(roles)

    y_dativo = _recipiente_dativo(roles)
    if y_dativo is not None and z is not None:
        return {"disparo": True, "tipo": "dativo", "x": x, "y": y_dativo, "z": z}

    if cfg.get("benefactiva_para", True) and z is not None and not z["es_ccomp"]:
        entry = lexicon.get(verb_lemma)
        if entry is not None and entry["plantilla"] == "benefactiva":
            y_para = _beneficiario_para(roles, cfg.get("case_para", DEFAULT_CASE_PARA))
            if y_para is not None:
                return {"disparo": True, "tipo": "benefactivo_para",
                       "x": x, "y": y_para, "z": z}

    # Fallback morfologico (DITRANS-AGX): el clitico dativo doblado como
    # ULTIMA evidencia, despues de la ruta lexica benefactiva para no
    # robarle precedencia. Flag `fallback_agx_dativo` (invariante 9.6:
    # con false la salida es byte-identica a pre-DITRANS-AGX).
    if cfg.get("fallback_agx_dativo", True) and z is not None:
        y_agx, y_periferia_id = _recipiente_agx_doblado(roles)
        if y_agx is not None:
            return {"disparo": True, "tipo": "dativo_agx",
                    "x": x, "y": y_agx, "z": z,
                    "y_periferia_id": y_periferia_id}

    return {"disparo": False, "tipo": None, "x": None, "y": None, "z": None}


# ---------------------------------------------------------------------------
# Selección de plantilla
# ---------------------------------------------------------------------------
def elegir_plantilla(verb_lemma: str, trigger_tipo: str, lexicon: dict,
                     cfg: dict | None = None) -> dict:
    """León léxico-primero → default + log. El benefactivo_para SIEMPRE es
    benefactiva por construcción del propio trigger (decisión 4)."""
    cfg = cfg or {}
    if trigger_tipo == "benefactivo_para":
        entry = lexicon.get(verb_lemma)
        if entry is None or entry["plantilla"] != "benefactiva":
            raise ValueError(f"{verb_lemma}: benefactivo con para sin entrada benefactiva")
        return {**entry, "source": "lexico"}

    entry = lexicon.get(verb_lemma)
    if entry is not None:
        return {**entry, "source": "lexico"}

    default = cfg.get("default_plantilla", DEFAULT_PLANTILLA)
    return {"plantilla": default, "subtipo_benefactivo": None,
            "predicado_resultado": None, "proposito": None,
            "source": "default", "ambiguo": False, "notas": "", "fuente": "default"}


# ---------------------------------------------------------------------------
# Construcción de la LS
# ---------------------------------------------------------------------------
def construir_el(plantilla: str, verb_lemma: str, x_lex: str, y_lex: str,
                 z_lex: str, especificacion: dict | None = None) -> dict:
    """LS formal (x=efectuador/emisor, y=poseedor/receptor,
    z=tema/contenido) + léxica + `estructura` (Fase
    LINKING, LA1 §1): x siempre "1_do" (1er arg. del do' externo); z (tema/
    contenido) siempre "2_pred_xy" (2º arg. de have'/del predicado de
    comunicación); y (poseedor/receptor, el dativo español) "1_pred_xy" PERO
    marcado `nmr=True` — decisión ya tomada en L1a/L2.5 (el dativo es NMR,
    no macrorrol), no se re-litiga aquí. En comunicación, y va EMBEBIDO en
    el nombre del predicado formal como ``y`` y también ocupa su posición
    estructurada como NMR.
    """
    especificacion = especificacion or {}
    if plantilla in ("transferencia", "benefactiva"):
        if plantilla == "transferencia":
            f = "[do'(x, Ø)] CAUSE [BECOME have'(y, z)]"
            l = f"[do'({x_lex}, Ø)] CAUSE [BECOME have'({y_lex}, {z_lex})]"
            estructura = [
                linking.frame("do'", linking.arg(x_lex, "1_do", variable="x")),
                linking.frame("have'", linking.arg(y_lex, "1_pred_xy", nmr=True, variable="y"),
                              linking.arg(z_lex, "2_pred_xy", variable="z")),
            ]
        else:
            subtipo = especificacion.get("subtipo_benefactivo")
            pred = especificacion.get("predicado_resultado")
            proposito = especificacion.get("proposito")
            if subtipo not in SUBTIPOS_BENEFACTIVOS or proposito not in PROPOSITOS:
                raise ValueError(f"especificación benefactiva incompleta: {especificacion}")
            estructura = [linking.frame("do'", linking.arg(x_lex, "1_do", variable="x"))]
            if subtipo == "obtencion":
                nuc_f = "[[do'(x, Ø)] CAUSE [BECOME have'(x, z)]]"
                nuc_l = f"[[do'({x_lex}, Ø)] CAUSE [BECOME have'({x_lex}, {z_lex})]]"
                estructura.append(linking.frame(
                    "have'", linking.arg(x_lex, "1_pred_xy", variable="x"),
                    linking.arg(z_lex, "2_pred_xy", variable="z")))
            elif subtipo in {"preparacion", "creacion", "cambio_estado"}:
                nuc_f = f"[[do'(x, Ø)] CAUSE [BECOME {pred}(z)]]"
                nuc_l = f"[[do'({x_lex}, Ø)] CAUSE [BECOME {pred}({z_lex})]]"
                estructura.append(linking.frame(
                    pred, linking.arg(z_lex, "arg_estado", variable="z")))
            else:  # actividad: no entraña resultado causado
                pred_actividad = f"{verb_lemma}'"
                nuc_f = f"do'(x, [{pred_actividad}(x, z)])"
                nuc_l = f"do'({x_lex}, [{pred_actividad}({x_lex}, {z_lex})])"
                estructura.append(linking.frame(
                    pred_actividad, linking.arg(z_lex, "2_pred_xy", variable="z")))
            purp_f, purp_l = _construir_proposito(proposito, y_lex, z_lex)
            if purp_f:
                f, l = f"{nuc_f} PURP [{purp_f}]", f"{nuc_l} PURP [{purp_l}]"
                estructura.append(linking.frame(
                    "have'", linking.arg(y_lex, "1_pred_xy", nmr=True, variable="y"),
                    linking.arg(z_lex, "2_pred_xy", variable="z")))
            else:
                f, l = nuc_f, nuc_l
    elif plantilla == "comunicacion":
        pred_formal = f"{verb_lemma}.to.(y)'"
        pred_lexical = f"{verb_lemma}.to.({y_lex})'"
        f = f"do'(x, [{pred_formal}(x, z)])"
        l = f"do'({x_lex}, [{pred_lexical}({x_lex}, {z_lex})])"
        estructura = [
            linking.frame("do'", linking.arg(x_lex, "1_do")),
            linking.frame(pred_formal,
                          linking.arg(y_lex, "1_pred_xy", nmr=True),
                          linking.arg(z_lex, "2_pred_xy")),
        ]
    else:
        raise ValueError(f"plantilla desconocida: {plantilla}")

    clase = ("activity" if plantilla == "benefactiva" and
             especificacion.get("subtipo_benefactivo") == "actividad"
             else _CLASE_POR_PLANTILLA[plantilla])
    return {"formal": f, "lexical": l, "clase": clase,
           "estructura": estructura}


def clase_derivada_de_el(formal: str) -> str | None:
    """DITRANS-CLASE (2026-08-19) — clase VISIBLE a partir de la EL.

    La EL es la fuente de verdad: si lleva CAUSE, el operador del estado
    resultante decide si es realización o logro causativo. Devuelve None
    cuando la EL no lleva CAUSE (comunicación, benefactiva de subtipo
    actividad), que es justo cuando no hay nada causativo que anunciar.

    Misma regla que aplica la rama causativa de `rrg_ls_mapper`
    (`caus["clase_derivada"]`); vive aquí para ser testeable en frío.
    """
    formal = formal or ""
    if "CAUSE" not in formal:
        return None
    if "INGR " in formal:
        return "logro_causativo"
    if "BECOME " in formal:
        return "realizacion_causativa"
    return None


def _construir_proposito(modo: str, y_lex: str, z_lex: str) -> tuple[str, str]:
    if modo == "become_have":
        return "BECOME have'(y, z)", f"BECOME have'({y_lex}, {z_lex})"
    if modo == "have":
        return "have'(y, z)", f"have'({y_lex}, {z_lex})"
    if modo == "none":
        return "", ""
    raise ValueError(f"modalidad de propósito desconocida: {modo}")


def construir_ditransitiva(roles: dict, verb_lemma: str, lexicon: dict,
                           cfg: dict | None = None) -> dict | None:
    """Orquesta trigger → plantilla → LS → roles por posición → args_map.

    Returns None si no hay construcción ditransitiva (nada cambia). Si
    dispara, devuelve TODO lo que el mapper necesita para reemplazar la
    rama normal de build_ls/componer_cause (mismo patrón self-contained
    que la rama de causatividad en rrg_ls_mapper):

        {"plantilla", "trigger", "source", "ambiguo",
         "formal", "lexical", "clase",
         "arg_meta_parts": [...], "id_a_var": {...},
         "roles_tematicos": {id: rol, ...},   # insumo de MISC RRGThemRel
         "y_periferia_id": int|None}          # id a remover de periferia (asciende)
    """
    cfg = cfg or {}
    trigger = detectar_trigger(roles, verb_lemma, lexicon, cfg)
    if not trigger["disparo"]:
        return None

    plantilla_info = elegir_plantilla(verb_lemma, trigger["tipo"], lexicon, cfg)
    plantilla = plantilla_info["plantilla"]
    etiquetas = _ROLES_POR_PLANTILLA[plantilla]

    x, y, z = trigger["x"], trigger["y"], trigger["z"]
    x_lex = x["text"] if x else "x"
    y_lex = y["text"]
    z_lex = z["text"]

    el = construir_el(plantilla, verb_lemma, x_lex, y_lex, z_lex, plantilla_info)

    id_a_var: dict[int, str] = {}
    arg_meta_parts: list[str] = []
    roles_tematicos: dict[int, str] = {}

    if x is not None and x["id"] is not None:
        id_a_var[x["id"]] = "x"
        roles_tematicos[x["id"]] = etiquetas["x"]
        arg_meta_parts.append(f"x:{x_lex},{x['deprel']},{_MACRORROL_X}({etiquetas['x']})")
    else:
        arg_meta_parts.append(f"x:{x_lex},pro-drop,{_MACRORROL_X}({etiquetas['x']})")

    macropapel_z = _MACRORROL_Z_CCOMP if z["es_ccomp"] else _MACRORROL_Z_OBJ
    id_a_var[z["id"]] = "z"
    roles_tematicos[z["id"]] = etiquetas["z"]
    arg_meta_parts.append(f"z:{z_lex},{z['deprel']},{macropapel_z}({etiquetas['z']})")

    if y["id"] is not None:
        id_a_var[y["id"]] = "y"
        roles_tematicos[y["id"]] = etiquetas["y"]
    arg_meta_parts.append(f"y:{y_lex},{y['deprel']},{_MACRORROL_Y}({etiquetas['y']})")

    return {
        "plantilla": plantilla, "trigger": trigger["tipo"],
        "source": plantilla_info["source"], "ambiguo": plantilla_info["ambiguo"],
        "subtipo_benefactivo": plantilla_info.get("subtipo_benefactivo"),
        "predicado_resultado": plantilla_info.get("predicado_resultado"),
        "proposito": plantilla_info.get("proposito"),
        "formal": el["formal"], "lexical": el["lexical"], "clase": el["clase"],
        "estructura": el["estructura"],
        "arg_meta_parts": arg_meta_parts, "id_a_var": id_a_var,
        "variables": {"x": x_lex, "y": y_lex, "z": z_lex},
        "roles_tematicos": roles_tematicos,
        "y_periferia_id": (y["id"] if trigger["tipo"] == "benefactivo_para"
                           else trigger.get("y_periferia_id")),
    }


# ---------------------------------------------------------------------------
# Log de candidatos (mismo patrón que causatividad.log_candidato)
# ---------------------------------------------------------------------------
def log_candidato(lema: str, oracion: str, plantilla: str,
                  path: Path = CANDIDATOS_CSV) -> None:
    """Registra un disparo con plantilla por defecto o verbo ambiguo, para
    bootstrapping/curaduría del léxico (data/verbos_ditransitivos.xlsx)."""
    nuevo = not path.exists()
    if not nuevo:
        with open(path, newline="", encoding="utf-8") as f:
            if any(r["lema"] == lema and r["oracion"] == oracion
                   for r in csv.DictReader(f)):
                return
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["lema", "oracion", "plantilla"])
        w.writerow([lema, oracion, plantilla])
