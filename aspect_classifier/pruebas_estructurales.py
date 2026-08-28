"""Pruebas de Van Valin ESTRUCTURALES (RRG) — detector sobre la oración real.

Completa la familia de pruebas de la GRR (texto fuente: data/reglas_RRG.txt)
en la dirección correcta: detectar el ENTORNO de prueba en la oración del
usuario (rule-based sobre roles/aux_asp ya computados), no sintetizar frames
y pedirle un juicio a un MLM. Patrón ya validado en el pipeline: el gate
`AA_sin_delimitador→Activity` de nucleo_periferia ES la Prueba 4; la cascada
de causatividad del Paso 4 (causatividad.py) ES la Prueba 7.

Cubiertas aquí: P1 (progresivo), P2 (adverbios dinámicos), P3 (adverbios de
ritmo), P4 (durativa: "durante/por X" o duración desnuda), P5 (terminativa:
"en X"). NO cubiertas aquí:
  - P6 (participio resultativo): es un juicio de aceptabilidad morfológica,
    no ancla a un token de la oración de entrada — sin entorno estructural.
  - P7 (causativa): ya la cubre la cascada de causatividad del Paso 4
    (causatividad.py); no se repite.

Funciones puras: sin Stanza, sin modelos, sin I/O — operan sobre `toks`
(formato complejo_verbal.desde_stanza), `roles` (nucleo_periferia.analizar_roles,
con periferia ya extendida con case/lemma) y `aux_asp`
(rrg_ls_mapper.detect_aux_aspect).
"""

from .nucleo_periferia import _NOMBRES_TIEMPO

DEFAULT_ADV_DINAMICOS = ["vigorosamente", "activamente", "enérgicamente",
                         "dinámicamente"]
DEFAULT_ADV_RITMO = ["lentamente", "rápidamente", "gradualmente"]
DEFAULT_PREP_DURATIVAS = ["durante", "por"]
DEFAULT_PREP_TERMINATIVA = "en"

# Cuadro 1 (reglas_RRG.txt): patrón esperado de pruebas por clase aspectual.
# Claves de prueba con el mismo formato que las evidencias detectadas.
CUADRO_PRUEBAS = {
    "state":                 {"P1": "✗", "P2": "✗(n/a)", "P3": "✗(n/a)",
                              "P4": "✓", "P5": "✗"},
    "activity":               {"P1": "✓", "P2": "✓", "P3": "✓",
                              "P4": "✓", "P5": "✗"},
    "achievement":            {"P1": "✗(suj.sing.)", "P2": "✗", "P3": "✗",
                              "P4": "✗", "P5": "✗"},
    "semelfactive":           {"P1": "iterativo", "P2": "✗", "P3": "✗",
                              "P4": "✗", "P5": "✗"},
    "accomplishment":         {"P1": "✓", "P2": "✗", "P3": "✓",
                              "P4": "✓", "P5": "✓"},
    "active_accomplishment":  {"P1": "✓", "P2": "✓", "P3": "✓",
                              "P4": "✓", "P5": "✓"},
}

_DISPLAY_CLASE = {
    "state": "State", "activity": "Activity", "achievement": "Achievement",
    "semelfactive": "Semelfactive", "accomplishment": "Accomplishment",
    "active_accomplishment": "Active_Accomplishment",
}

_PRUEBA_LABEL = {"P1": "progresivo", "P2": "dinámico", "P3": "ritmo",
                 "P4": "atélico", "P5": "télico"}


# Determinantes que sí expresan una CANTIDAD de tiempo acotada ("una hora" ~
# "un rato"). Deliberadamente NO incluye artículos definidos (el/la/los/las,
# lema "el") ni cuantificadores universales/distributivos (todo, cada,
# alguno): esos marcan frecuencia/genericidad ("todos los días", "cada
# semana", "algunas veces" = hábito), no la duración de Prueba 4. Hallado
# por el informe de checkpoint: "corre todos los días" disparaba P4 por el
# artículo "los" (det de "días"), no por "todos" (que ni siquiera es hijo
# directo de "días" en el árbol UD — cuelga de "los").
_DET_CANTIDAD = {"uno"}


def _tiene_cuantificador(toks: list[dict], tok_id: int) -> bool:
    """¿El token tiene un numeral o determinante DE CANTIDAD dependiente?
    ("tres horas" nummod, "una hora" det/lema=uno — desnudas, sin preposición)."""
    for t in toks:
        if t["head"] != tok_id:
            continue
        if t["deprel"] == "nummod":
            return True
        if t["deprel"] == "det" and t["lemma"].lower() in _DET_CANTIDAD:
            return True
    return False


def detectar_evidencia(toks: list[dict], root_id: int, roles: dict,
                       aux_asp: str | None, cfg: dict | None = None) -> dict:
    """Detecta el entorno de las pruebas P1-P5 en la oración real.

    Returns:
        {"evidencias": [{"prueba": "P4", "trigger": "durante una hora",
                        "rasgo": "durativo", "implica": {...}}, ...]}
    """
    cfg = cfg or {}
    adv_dinamicos = {a.lower() for a in cfg.get("adv_dinamicos", DEFAULT_ADV_DINAMICOS)}
    adv_ritmo = {a.lower() for a in cfg.get("adv_ritmo", DEFAULT_ADV_RITMO)}
    prep_durativas = {p.lower() for p in cfg.get("prep_durativas", DEFAULT_PREP_DURATIVAS)}
    prep_terminativa = cfg.get("prep_terminativa", DEFAULT_PREP_TERMINATIVA).lower()

    evidencias = []

    # P1 — progresivo (estar + gerundio): el embrión ya vivía en detect_aux_aspect.
    if aux_asp == "prog":
        evidencias.append({"prueba": "P1", "trigger": "estar+gerundio",
                           "rasgo": "progresivo",
                           "implica": {"estático": False}})

    for p in roles.get("periferia", []):
        if p.get("tipo") != "temporal":
            continue
        case = p.get("case")
        lemma = p.get("lemma", "")
        if lemma not in _NOMBRES_TIEMPO:
            continue
        if case in prep_durativas:
            evidencias.append({"prueba": "P4", "trigger": f"{case} {p['text']}",
                               "rasgo": "durativo",
                               "implica": {"duración_interna": True,
                                          "télico_en_esta_lectura": False}})
        elif case == prep_terminativa:
            evidencias.append({"prueba": "P5", "trigger": f"{case} {p['text']}",
                               "rasgo": "terminativo",
                               "implica": {"télico": True, "duración": True}})
        elif case is None and _tiene_cuantificador(toks, p["id"]):
            evidencias.append({"prueba": "P4", "trigger": p["text"],
                               "rasgo": "durativo",
                               "implica": {"duración_interna": True,
                                          "télico_en_esta_lectura": False}})

    for p in roles.get("periferia", []):
        # Etapa PERIFERIA (2026-07-13): "modo" se renombró a "manera" en
        # nucleo_periferia._tipo_periferia (misma detección: advmod en
        # -mente que no es aspectual/epistémico).
        if p.get("tipo") != "manera":
            continue
        lemma = p.get("lemma", "")
        if lemma in adv_dinamicos:
            evidencias.append({"prueba": "P2", "trigger": p["text"],
                               "rasgo": "dinámico",
                               "implica": {"dinámico": True}})
        elif lemma in adv_ritmo:
            evidencias.append({"prueba": "P3", "trigger": p["text"],
                               "rasgo": "ritmo",
                               "implica": {"puntual": False, "duración": True}})

    return {"evidencias": evidencias}


def tiene_prueba(evidencia: dict, prueba: str) -> bool:
    return any(e["prueba"] == prueba for e in evidencia.get("evidencias", []))


def aplicar_coerciones(verb_class: str, evidencia: dict,
                       delimitador_nuclear: bool,
                       cfg: dict | None = None) -> dict:
    """Coerciones/avisos licenciados por las pruebas P1-P5.

    R1/R2 cambian de clase (coerción licenciada por la propia teoría de Van
    Valin); R3/R4 solo anotan — el clasificador y los gates existentes (AA,
    causatividad) siguen gobernando la clase. Default = no hacer nada; solo
    evidencia presente y unívoca dispara.

    Returns:
        {"clase": str, "notas": [str, ...]}
    """
    cfg = cfg or {}
    coerciones_cfg = cfg.get("coerciones", {})
    avisos_on = cfg.get("avisos", True)
    r1_on = coerciones_cfg.get("semelfactive_iterativa", True)
    r2_on = coerciones_cfg.get("lectura_atelica", True)

    p1 = tiene_prueba(evidencia, "P1")
    p2 = tiene_prueba(evidencia, "P2")
    p3 = tiene_prueba(evidencia, "P3")
    p4 = tiene_prueba(evidencia, "P4")
    p5 = tiene_prueba(evidencia, "P5")

    clase = verb_class
    notas = []

    # R1 — semelfactivo + (progresivo O durativa P4) → lectura iterativa.
    # "tosió durante una hora", "está tosiendo": el propio Van Valin describe
    # esta lectura del semelfactivo bajo prueba de duración.
    if r1_on and verb_class == "semelfactive" and (p1 or p4):
        clase = "activity"
        notas.append("coercion=P1/P4 semelfactive→activity_iterativa")

    # R2 — accomplishment/AA + durativa P4 SIN terminativa P5 → atélico.
    # "leyó el libro durante una hora": el evento no culmina en esta lectura.
    elif r2_on and verb_class in ("accomplishment", "active_accomplishment") \
            and p4 and not p5:
        clase = "activity"
        notas.append("coercion=P4 lectura_atélica")

    if avisos_on:
        # R3 — activity + delimitador nuclear + P5: refuerzo télico, sin
        # cambiar clase aquí (el paso a AA ya lo gobiernan el clasificador +
        # el gate AA existente). Conservador a propósito.
        if clase == "activity" and delimitador_nuclear and p5:
            notas.append("P5 confirma télico")

        # R4 — conflictos: solo warning, sin cambio de clase.
        if verb_class == "state" and p2:
            notas.append("⚠ conflicto=P2 vs State")
        if verb_class in ("achievement", "semelfactive") and p3:
            notas.append("⚠ conflicto=P3 vs puntual")
        if verb_class == "achievement" and p1:
            notas.append("⚠ conflicto=P1 vs Achievement "
                         "(lectura prospectiva/iterativa posible)")

    return {"clase": clase, "notas": notas}


def linea_coherencia(clase_final: str, evidencia: dict) -> str:
    """Línea compacta de coherencia contra CUADRO_PRUEBAS, solo si hubo
    evidencia (sin evidencia → sin línea, no ruido)."""
    evs = evidencia.get("evidencias") if evidencia else None
    if not evs:
        return ""
    patron = CUADRO_PRUEBAS.get(clase_final, {})
    display = _DISPLAY_CLASE.get(clase_final, clase_final)
    partes = []
    for e in evs:
        prueba = e["prueba"]
        esperado = patron.get(prueba, "✗")
        if prueba == "P1" and clase_final == "semelfactive":
            coherente = True   # lectura iterativa, licenciada por la teoría
        else:
            coherente = esperado.startswith("✓")
        label = _PRUEBA_LABEL.get(prueba, e["rasgo"])
        marca = "✓coherente" if coherente else "⚠conflicto"
        partes.append(f"{prueba} '{e['trigger']}'→{label} {marca} con {display}")
    return "Pruebas: " + " · ".join(partes)
