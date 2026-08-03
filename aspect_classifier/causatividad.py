"""Paso 4B — Detección de causatividad y composición del operador CAUSE.

Causatividad = parámetro ORTOGONAL a la Aktionsart (RRG): forma
[do'(x, Ø)] CAUSE [β], donde β conserva SU clase Vendler. El español
marca la derivación anticausativa con `se` (inespecificación x → Ø,
paciente asciende a PSA).

Detección HÍBRIDA en cascada, con precedencia estricta:
  1. Léxico (data/causative_lexicon.csv, curado) — confianza alta.
  2. Fallback heurístico CONSERVADOR (sesgo a no-CAUSE): dispara solo
     con `se` anticausativo estructuralmente fuerte; confianza baja,
     candidato logueado para bootstrapping del léxico.

Módulo puro sobre tokens UD (mismo formato dict que complejo_verbal);
sin torch, sin Stanza: testeable en frío.
"""

import csv
from pathlib import Path

from . import linking

PKG_DIR = Path(__file__).parent
LEXICON_CSV = PKG_DIR / "data" / "causative_lexicon.csv"
CANDIDATOS_CSV = PKG_DIR / "data" / "causative_candidates_heuristico.csv"

DEFAULT_CLITIC_DEPRELS = {"expl", "expl:pv", "expl:pass", "expl:impers"}

# Clases β en forma canónica (acepta también minúsculas del mapper)
_CANON = {
    "state": "State", "activity": "Activity", "achievement": "Achievement",
    "semelfactive": "Semelfactive", "accomplishment": "Accomplishment",
    "active_accomplishment": "Active_Accomplishment",
}


def cargar_lexicon(path: Path = LEXICON_CSV) -> dict[str, dict]:
    """Carga el léxico causativo curado, indexado por lema (sin -se)."""
    lexicon: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["causativo_lexico"] = row["causativo_lexico"].strip().lower() == "true"
            row["toma_se_anticausativo"] = (
                row["toma_se_anticausativo"].strip().lower() == "true")
            row["aktionsart_base"] = (row.get("aktionsart_base") or "").strip()
            row["predicado_base"] = (row.get("predicado_base") or "").strip()
            lexicon[row["lema"].strip().lower()] = row
    return lexicon


def detectar_causatividad(tokens: list[dict], root_id: int,
                          lexicon: dict[str, dict],
                          cfg: dict | None = None) -> dict:
    """Cascada léxico-primero → heurístico conservador.

    Returns dict con: causativo, tipo, source, confianza, causer_id,
    patient_id, se_anticausativo, se_reflexivo_no_causativo,
    candidato_lexico, lex_aktionsart.
    """
    cfg = cfg or {}
    clitics = set(cfg.get("clitic_deprels", DEFAULT_CLITIC_DEPRELS))

    res = {
        "causativo": False, "tipo": None, "source": None, "confianza": None,
        "causer_id": None, "patient_id": None, "se_anticausativo": False,
        "se_reflexivo_no_causativo": False, "candidato_lexico": False,
        "lex_aktionsart": None,
    }
    root = next(t for t in tokens if t["id"] == root_id)
    hijos = [t for t in tokens if t["head"] == root_id]
    nsubj = next((t for t in hijos if t["deprel"] == "nsubj"), None)
    obj = next((t for t in hijos if t["deprel"] == "obj"), None)
    se = next((t for t in hijos if t["deprel"] in clitics), None)

    lex = lexicon.get(root["lemma"].lower())
    if lex is not None:
        res["lex_aktionsart"] = lex.get("aktionsart_base") or None

    # ── Nivel 1: léxico ───────────────────────────────────────────────────
    if lex is not None and lex["causativo_lexico"]:
        if obj is not None:
            # marco transitivo: nsubj causante + obj paciente
            res.update(causativo=True, tipo="lexico_transitivo",
                       source="lexicon", confianza="alta",
                       causer_id=nsubj["id"] if nsubj else None,
                       patient_id=obj["id"])
            return res
        if se is not None and lex["toma_se_anticausativo"]:
            # anticausativo con se: paciente asciende a nsubj, causante Ø
            res.update(causativo=True, tipo="lexico_anticausativo_se",
                       source="lexicon", confianza="alta",
                       se_anticausativo=True,
                       patient_id=nsubj["id"] if nsubj else None)
            return res
        if se is not None:
            # causativo léxico cuyo `se` NO es anticausativo (sacudir, agitar):
            # se medio/reflexivo sin cambio de estado → alimenta el gate 4D
            res["se_reflexivo_no_causativo"] = True
        return res

    if lex is not None:
        # en el léxico pero no causativo (p. ej. morir, lado incoativo supletivo)
        if se is not None and not lex["toma_se_anticausativo"]:
            res["se_reflexivo_no_causativo"] = True
        return res

    # ── Nivel 2: fallback heurístico CONSERVADOR ─────────────────────────
    # Solo señal estructural fuerte: `se` + paciente-sujeto nominal común
    # (proxy de inanimado: cambio de estado plausible) + sin OD.
    # PROPN sujeto ("Juan se peinó") o presencia de obj → no dispara.
    if (se is not None and obj is None and nsubj is not None
            and nsubj["upos"] == "NOUN"):
        res.update(causativo=True, tipo="heuristico_anticausativo_se",
                   source="heuristic", confianza="baja",
                   se_anticausativo=True, patient_id=nsubj["id"],
                   candidato_lexico=True)
    return res


def aplicar_gate_semelfactive(verb_class: str, pun: float, caus: dict,
                              pun_min: float = 0.5) -> str:
    """Gate 4D (SOLO léxico, alta precisión): si el `se` es reflexivo/medio
    de un verbo cuya base léxica es Semelfactive y pun es alto, la clase
    es Semelfactive, no Achievement (corta la telicidad espuria de
    "el perro se sacudió"). No toca nada más."""
    if (verb_class == "achievement"
            and caus.get("se_reflexivo_no_causativo")
            and caus.get("lex_aktionsart") == "Semelfactive"
            and pun >= pun_min):
        return "semelfactive"
    return verb_class


def _beta(base: str, pred: str, y: str, resultative: bool = False) -> str:
    """β_LS con la Aktionsart de base aplicada al paciente y."""
    if resultative and base != "Achievement":
        # La lectura heurística de se-pasivo no representa la actividad de
        # vender: representa el estado resultante del paciente.
        return f"BECOME {pred}({y})"
    if base == "Achievement":
        return f"INGR {pred}({y})"
    if base == "Accomplishment":
        return f"BECOME {pred}({y})"
    if base == "Semelfactive":
        return f"SEML {pred}({y})"
    if base in ("Activity", "Active_Accomplishment"):
        return f"do'({y}, [{pred}({y})])"
    return f"{pred}({y})"                      # State


def componer_cause(aktionsart_base: str, predicado_base: str | None,
                   lema: str, causer_lex: str | None, patient_lex: str | None,
                   se_anticausativo: bool,
                   causativo_heuristico: bool = False) -> dict:
    """[do'(x, Ø)] CAUSE [β(paciente)]; anticausativo: x → Ø.

    Devuelve {"formal", "lexical", "estructura"}. `estructura` (Fase
    LINKING, LA1 §1): x (causante, o "Ø" si es anticausativo) es siempre el
    1er argumento del do' EXTERNO ("1_do"); el paciente y ocupa la posición
    que le da su Aktionsart de base — "1_do" también si β es una
    actividad/AA (embebida en SU PROPIO do': "do'(y,[pred'(y)])", ver
    `_beta`), o "arg_estado" en cualquier otro caso (logro/realización/
    semelfactivo/estado: el paciente de un cambio de estado resultante).
    """
    base = _CANON.get(aktionsart_base.lower(), aktionsart_base)
    pred = (predicado_base or "").strip() or _participio_es(lema) + "'"
    # El léxico histórico conserva algunas glosas inglesas. Para una
    # plantilla resultativa española no deben escapar al contrato visible.
    if pred.rstrip("'").lower() in {"broken", "sold"}:
        pred = _participio_es(lema) + "'"
    pred = pred.split("/")[0].strip()          # "reventado'/popped'" → primero
    if not pred.endswith("'"):
        pred += "'"

    y_lex = patient_lex or "y"
    if se_anticausativo:
        x_var = x_lex = "Ø"
    else:
        x_var, x_lex = "x1", (causer_lex or "x")

    resultative = bool(se_anticausativo and causativo_heuristico)
    formal = f"[do'({x_var}, Ø)] CAUSE [{_beta(base, pred, 'x2', resultative)}]"
    lexical = f"[do'({x_lex}, Ø)] CAUSE [{_beta(base, pred, y_lex, resultative)}]"

    posicion_y = "arg_estado" if resultative else (
        "1_do" if base in ("Activity", "Active_Accomplishment") else "arg_estado")
    estructura = [
        linking.frame("do'", linking.arg(x_lex, "1_do")),
        linking.frame(pred, linking.arg(y_lex, posicion_y)),
    ]
    return {"formal": formal, "lexical": lexical, "estructura": estructura}


def _participio_es(lema: str) -> str:
    """Participio regular mínimo para la diana heurística de LA2.

    El léxico curado sigue siendo la fuente preferida; esta función solo
    evita que una lectura resultativa heurística invente un predicado inglés
    o el infinitivo español.
    """
    lema = (lema or "").lower()
    irregulares = {"hacer": "hecho", "ver": "visto", "poner": "puesto",
                   "romper": "roto", "abrir": "abierto", "escribir": "escrito",
                   "decir": "dicho", "volver": "vuelto"}
    if lema in irregulares:
        return irregulares[lema]
    if lema.endswith("ar"):
        return lema[:-2] + "ado"
    if lema.endswith("er") or lema.endswith("ir"):
        return lema[:-2] + "ido"
    return lema


def log_candidato(lema: str, oracion: str,
                  path: Path = CANDIDATOS_CSV) -> None:
    """Registra un disparo heurístico para bootstrapping del léxico."""
    nuevo = not path.exists()
    if not nuevo:
        with open(path, newline="", encoding="utf-8") as f:
            if any(r["lema"] == lema and r["oracion"] == oracion
                   for r in csv.DictReader(f)):
                return
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["lema", "oracion"])
        w.writerow([lema, oracion])
