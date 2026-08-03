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

  BENEFACTIVA/CREACIÓN-OBTENCIÓN ("compró/hizo un regalo para María"):
    [[do'(x, Ø)] CAUSE [BECOME have'(x, z)]] PURP [have'(y, z)]
    x obtiene/crea z primero, con el PROPÓSITO de que y lo posea.
    x=efectuador, y=poseedor/beneficiario, z=tema. Clase: accomplishment.

  COMUNICACIÓN ("le dijo la verdad/que viniera a Pedro") — FORMA SIMPLE:
    do'(x, [<lema>.to.(y)'(x, z)])
    x=emisor, y=receptor (embebido en el NOMBRE del predicado, no es un
    argumento numerado — esta plantilla solo tiene dos slots x,z), z=tema
    (puede ser el núcleo de un ccomp: "dijo QUE VINIERA" → z=viniera).
    Clase: activity. ESTO ES UNA SIMPLIFICACIÓN deliberada de la forma
    plena de Van Valin `do'(x, [express(α).to.(β).in.language.(γ)'(x, z)])`
    — Julian pidió dejarla simple por ahora y refinar MUCHO después.
    TODO(futuro, no implementar aquí): bucle de corrección — si el usuario
    corrige una LS ditransitiva errónea en gruxx_ai1, el lema debería
    agregarse automáticamente al léxico curado (data/verbos_ditransitivos.xlsx).

El clítico/AGX no altera la LS ni la clase (ya garantizado por Etapa 1,
L1a): siempre UN solo x para el recipiente/receptor, venga como clítico
solo (x = etiqueta morfológica '3sg'), sintagma pleno solo, o doblado.

Funciones puras sobre `roles` (de `nucleo_periferia.analizar_roles`) y
tokens; sin Stanza, sin modelos — testeable en frío.
"""

import csv
from pathlib import Path

import pandas as pd

from . import linking

PKG_DIR = Path(__file__).parent
LEXICON_XLSX = PKG_DIR / "data" / "verbos_ditransitivos.xlsx"
CONTINUUM_XLSX = PKG_DIR / "data" / "continuum_de_relaciones_tematicas.xlsx"
CANDIDATOS_CSV = PKG_DIR / "data" / "ditransitivos_candidatos.csv"

DEFAULT_PLANTILLA = "transferencia"
DEFAULT_CASE_PARA = "para"

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
    """Léxico curado (lema → plantilla/ambiguo/notas), indexado por lema."""
    df = pd.read_excel(path)
    lexicon = {}
    for _, row in df.iterrows():
        notas = row.get("notas")
        lexicon[str(row["lema"]).strip().lower()] = {
            "plantilla": str(row["plantilla"]).strip().lower(),
            "ambiguo": bool(row.get("ambiguo", False)),
            "notas": "" if pd.isna(notas) else str(notas),
        }
    return lexicon


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
    Sin ninguno de los dos → sin disparo (transitivas/intransitivas siguen
    igual que hoy).

    Returns:
        {"disparo": bool, "tipo": "dativo"|"benefactivo_para"|None,
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
        return {"plantilla": "benefactiva", "source": "lexico", "ambiguo": False}

    entry = lexicon.get(verb_lemma)
    if entry is not None:
        return {"plantilla": entry["plantilla"], "source": "lexico",
               "ambiguo": entry["ambiguo"]}

    default = cfg.get("default_plantilla", DEFAULT_PLANTILLA)
    return {"plantilla": default, "source": "default", "ambiguo": False}


# ---------------------------------------------------------------------------
# Construcción de la LS
# ---------------------------------------------------------------------------
def construir_el(plantilla: str, verb_lemma: str, x_lex: str, y_lex: str,
                 z_lex: str) -> dict:
    """LS formal (x1/x2/x3 fijos: x=efectuador/emisor, z=tema/contenido,
    y=poseedor/receptor — mismo orden que Etapa 1 asigna naturalmente,
    ver docstring de map_sentence_to_ls) + léxica + `estructura` (Fase
    LINKING, LA1 §1): x siempre "1_do" (1er arg. del do' externo); z (tema/
    contenido) siempre "2_pred_xy" (2º arg. de have'/del predicado de
    comunicación); y (poseedor/receptor, el dativo español) "1_pred_xy" PERO
    marcado `nmr=True` — decisión ya tomada en L1a/L2.5 (el dativo es NMR,
    no macrorrol), no se re-litiga aquí. En comunicación, y va EMBEBIDO en
    el nombre del predicado (no es un argumento numerado en esta forma
    simplificada) y por tanto NO aparece en `estructura`.
    """
    if plantilla in ("transferencia", "benefactiva"):
        if plantilla == "transferencia":
            f = "[do'(x1, Ø)] CAUSE [BECOME have'(x3, x2)]"
            l = f"[do'({x_lex}, Ø)] CAUSE [BECOME have'({y_lex}, {z_lex})]"
        else:
            f = "[[do'(x1, Ø)] CAUSE [BECOME have'(x1, x2)]] PURP [have'(x3, x2)]"
            l = (f"[[do'({x_lex}, Ø)] CAUSE [BECOME have'({x_lex}, {z_lex})]]"
                 f" PURP [have'({y_lex}, {z_lex})]")
        estructura = [
            linking.frame("do'", linking.arg(x_lex, "1_do")),
            linking.frame("have'", linking.arg(y_lex, "1_pred_xy", nmr=True),
                         linking.arg(z_lex, "2_pred_xy")),
        ]
    elif plantilla == "comunicacion":
        # y se embebe en el NOMBRE del predicado (no es un argumento
        # numerado en esta forma simplificada — ver docstring del módulo).
        pred = f"{verb_lemma}.to.({y_lex})'"
        f = f"do'(x1, [{pred}(x1, x2)])"
        l = f"do'({x_lex}, [{pred}({x_lex}, {z_lex})])"
        estructura = [
            linking.frame("do'", linking.arg(x_lex, "1_do")),
            linking.frame(pred, linking.arg(z_lex, "2_pred_xy")),
        ]
    else:
        raise ValueError(f"plantilla desconocida: {plantilla}")

    return {"formal": f, "lexical": l, "clase": _CLASE_POR_PLANTILLA[plantilla],
           "estructura": estructura}


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

    el = construir_el(plantilla, verb_lemma, x_lex, y_lex, z_lex)

    id_a_var: dict[int, str] = {}
    arg_meta_parts: list[str] = []
    roles_tematicos: dict[int, str] = {}

    if x is not None and x["id"] is not None:
        id_a_var[x["id"]] = "x1"
        roles_tematicos[x["id"]] = etiquetas["x"]
        arg_meta_parts.append(f"x1:{x_lex},{x['deprel']},{_MACRORROL_X}({etiquetas['x']})")
    else:
        arg_meta_parts.append(f"x1:{x_lex},pro-drop,{_MACRORROL_X}({etiquetas['x']})")

    macropapel_z = _MACRORROL_Z_CCOMP if z["es_ccomp"] else _MACRORROL_Z_OBJ
    id_a_var[z["id"]] = "x2"
    roles_tematicos[z["id"]] = etiquetas["z"]
    arg_meta_parts.append(f"x2:{z_lex},{z['deprel']},{macropapel_z}({etiquetas['z']})")

    if y["id"] is not None:
        id_a_var[y["id"]] = "x3"
        roles_tematicos[y["id"]] = etiquetas["y"]
    arg_meta_parts.append(f"x3:{y_lex},{y['deprel']},{_MACRORROL_Y}({etiquetas['y']})")

    return {
        "plantilla": plantilla, "trigger": trigger["tipo"],
        "source": plantilla_info["source"], "ambiguo": plantilla_info["ambiguo"],
        "formal": el["formal"], "lexical": el["lexical"], "clase": el["clase"],
        "estructura": el["estructura"],
        "arg_meta_parts": arg_meta_parts, "id_a_var": id_a_var,
        "roles_tematicos": roles_tematicos,
        "y_periferia_id": y["id"] if trigger["tipo"] == "benefactivo_para" else None,
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
