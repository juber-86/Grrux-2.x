"""Fase L5 §3 — traducción user-friendly de la salida de gruxx.

El usuario objetivo es un lingüista competente en la GRR (Role and Reference
Grammar) que NO tiene por qué aprender los tecnicismos internos de gruxx. La
INFORMACIÓN se conserva íntegra; solo cambia el DELIVERY: el vector aspectual
crudo (`stat=0.02 dyn=0.75 ...`) y la línea de Completeness con etiquetas
internas (`falta_en_arbol`, `x2↔PP`) se re-expresan en términos legibles. El
detalle crudo completo sigue disponible con `--verbose` (ver gruxx_ai1.py).

Los términos y sus definiciones viven en el glosario (§4,
`data/glosario_gruxx.csv`) — este módulo usa las MISMAS etiquetas legibles
para que `-help <término>` y la salida hablen el mismo idioma.

Módulo puro: sin Stanza, sin modelos, sin I/O.
"""

import re

from . import linking as _linking

# Nombres legibles de las clases aspectuales (coinciden con el glosario §4).
CLASE_LEGIBLE = {
    "state": "Estado", "activity": "Actividad",
    "accomplishment": "Realización", "achievement": "Logro",
    "semelfactive": "Semelfactivo", "active_accomplishment": "Realización activa",
}

CLASE_CAUSATIVA_LEGIBLE = {
    "realizacion_causativa": "Realización causativa",
    "logro_causativo": "Logro causativo",
}


def clase_legible(ls_type: str) -> str:
    return CLASE_LEGIBLE.get((ls_type or "").lower(), (ls_type or "").upper())


def clase_visible(ls: dict) -> str:
    """Clase que se presenta al usuario; conserva `ls_type` para auditoría."""
    derivada = ls.get("causativo_clase_derivada")
    if derivada:
        return CLASE_CAUSATIVA_LEGIBLE.get(derivada, derivada)
    return clase_legible(ls.get("ls_type"))


# ── Línea de Rasgos (traducción del vector aspectual) ──────────────────────
def linea_rasgos(ls: dict) -> str | None:
    """`Rasgos: estático 0.02 · dinámico 0.75 · télico 0.40 · puntual 0.05 ·
    confianza 0.84`. Devuelve None si no hay vector (p.ej. copulativas o modo
    .conllu directo, donde el clasificador no corrió)."""
    vec = ls.get("vector")
    if not vec:
        return None
    conf = ls.get("confianza")
    partes = [f"estático {vec.get('stat', 0):.2f}",
              f"dinámico {vec.get('dyn', 0):.2f}",
              f"télico {vec.get('tel', 0):.2f}",
              f"puntual {vec.get('pun', 0):.2f}"]
    if conf is not None:
        partes.append(f"confianza {conf:.2f}")
    return "Rasgos: " + " · ".join(partes)


# ── Traducción de los apéndices técnicos del morph_note ────────────────────
_GATE_LEGIBLE = {
    "obj_desnudo→Activity": 'objeto sin determinante → Actividad',
    "obj_delimitado→AA": 'objeto delimitado → Realización activa',
    "obj_medida→AA": 'objeto de medida (numeral) → Realización activa',
    "se_aspectual→AA": '"se" completivo → Realización activa',
    "impersonal_sin_delimitador→Activity": 'impersonal sin delimitador → Actividad',
    "prodrop_durativo→Activity": 'verbo durativo sin objeto → Actividad',
    "AA_sin_delimitador→Activity": 'sin delimitador nuclear → Actividad',
    "se_reflexivo→Semelfactive": '"se" medio → Semelfactivo',
}

_DITRANS_LEGIBLE = {"transferencia": "transferencia", "benefactiva": "benefactiva",
                    "comunicacion": "comunicación", "comunicación": "comunicación"}
_SOURCE_LEGIBLE = {"lexico": "léxico", "léxico": "léxico", "default": "por defecto",
                   "correccion_usuario": "corrección del usuario"}


def traducir_apendices(morph_note: str) -> list[str]:
    """Extrae del `morph_note` crudo los apéndices técnicos y los traduce a
    frases legibles (correcciones/coerciones/construcción/causatividad). Los
    wrappers ya son legibles (for'/during'/be-in') y se dejan tal cual. El
    vector (stat/dyn/...) NO se incluye aquí — va en `linea_rasgos`."""
    note = morph_note or ""
    frases = []

    for m in re.finditer(r"gate=([^\s]+)", note):
        clave = m.group(1)
        frases.append("corrección: " + _GATE_LEGIBLE.get(clave, clave.replace("→", " → ")))

    if "coercion=P1/P4" in note or "semelfactive→activity_iterativa" in note:
        frases.append('coerción: semelfactivo iterado (progresivo o "durante X")')
    if "coercion=P4 lectura_atélica" in note or "lectura_atélica" in note:
        frases.append('coerción: lectura atélica ("durante X" sin término)')

    m = re.search(r"ditrans=([^\s(]+)\(([^)]*)\)", note)
    if m:
        plantilla = _DITRANS_LEGIBLE.get(m.group(1), m.group(1))
        source = _SOURCE_LEGIBLE.get(m.group(2), m.group(2))
        frases.append(f"construcción: {plantilla} ({source})")

    m = re.search(r"CAUSE\[([^,\]]+),?([^\]]*)\]", note)
    if m:
        tipo = _SOURCE_LEGIBLE.get(m.group(1).strip(), m.group(1).strip())
        conf = m.group(2).strip()
        frases.append(f"causatividad: {tipo}" + (f" (conf. {conf})" if conf else ""))

    m = re.search(r"wrappers:\s*(.+?)(?:\s·|$)", note)
    if m:
        frases.append(f"periferia envuelta: {m.group(1).strip()}")

    return frases


# ── Etapa OPERATORS — EL envuelta y resumen de operadores ──────────────────
def el_lexica(ls: dict) -> str:
    """La EL léxica tal como debe MOSTRARSE: envuelta en ⟨ ⟩ por sus
    operadores cuando la etapa OPERATORS corrió (esa es la representación RRG
    completa), y sin envolver cuando no (flag apagado, o un `ls` de una etapa
    anterior). La clave cruda `ls_lexical` NUNCA se toca."""
    return ls.get("ls_lexical_ops") or ls.get("ls_lexical", "")


def el_formal(ls: dict) -> str:
    return ls.get("ls_formal_ops") or ls.get("ls_formal", "")


def linea_operadores(ls: dict) -> str | None:
    """`Operadores : IF=DEC · TNS=PAST · ASP=PERF PROG`. None si no hay
    operadores (etapa apagada) — la línea no se imprime vacía."""
    ops = ls.get("operadores")
    if not ops:
        return None
    from .operadores import linea_operadores as _linea
    resumen = _linea(ops)
    return f"Operadores : {resumen}" if resumen else None


def detalle_operadores(ls: dict) -> list[str]:
    """Detalle crudo para `--verbose`: valor, ESTRATO y SEÑAL DE ORIGEN de
    cada operador, uno por línea. Es la misma información que consumirán los
    tooltips de la GUI y la futura corrección de operadores."""
    ops = ls.get("operadores") or {}
    return [f"  {op:5} = {spec['valor']:12} [{spec['estrato']}] ← {spec['origen']}"
            for op, spec in ops.items()]


# ── Traducción de la línea de Completeness → Integridad ────────────────────
_ESTRATO_LEGIBLE = {"CORE": "el centro", "CLAUSE": "la cláusula", "NUC": "el núcleo"}


def _traducir_check(c: dict) -> str:
    tipo, estado, detalle = c["tipo"], c["estado"], c.get("detalle", "")

    if tipo == "argumento":
        var = c.get("elemento", "")
        if estado == "ok":
            if "(morf)" in detalle:
                return f"{var} en la terminación verbal"
            if "clítico-AGX" in detalle:
                return f"{var} en el clítico (AGX)"
            if "↔NP" in detalle:
                return f"{var} ↔ sintagma nominal"
            if "↔PP" in detalle:
                return f'{var} ↔ frase preposicional'
            return f"{var} ✓"
        if estado == "ok_clausal":
            return f"{var} ↔ cláusula subordinada"
        if estado == "no_verificable":
            return f"{var} (no verificable)"
        if estado == "falta_en_arbol":
            m = re.search(r'"([^"]*)"', detalle)
            quien = f' ("{m.group(1)}")' if m else ""
            return f'{var}{quien} NO aparece como constituyente en el árbol'

    if tipo == "periferia":
        elem = c.get("elemento", "")
        if estado == "ok":
            if "↔LDP" in detalle:
                return f"{elem} ↔ posición destacada (inicio)"
            m = re.search(r"PERI@(\w+)", detalle)
            if m:
                return f"{elem} ↔ periferia en {_ESTRATO_LEGIBLE.get(m.group(1), m.group(1))}"
            return f"{elem} ↔ periferia"
        if estado == "no_verificable":
            return f"{elem} (periferia no verificable)"
        if estado == "falta_en_arbol":
            return f"{elem} NO aparece como periferia en el árbol"

    if tipo == "agx":
        if estado == "ok":
            return "concordancia (AGX) ✓"
        if estado == "falta_en_arbol":
            return "concordancia (AGX): la EL la anticipa pero el árbol NO la tiene"
        if estado == "falta_en_ls":
            return "el árbol tiene concordancia (AGX) que la EL NO anticipa"

    # Fallback: no romper nunca.
    return detalle or f"{c.get('elemento','')} ({estado})"


def linea_integridad(comp: dict | None) -> str | None:
    """`Integridad: ✓ x1 en la terminación verbal · x2 ↔ sintagma nominal ·
    concordancia (AGX) ✓` / `Integridad: ⚠ x2 ("participar") no aparece...`.
    Devuelve None si no hay árbol (nada que verificar)."""
    if not comp:
        return None
    if comp.get("ok") is None:
        return "Integridad: (sin árbol — la oración no se convirtió)"
    checks = comp.get("checks") or []
    if not checks:
        simbolo = "✓" if comp.get("ok") else "⚠"
        return f"Integridad: {simbolo}"
    simbolo = "✓" if comp.get("ok") else "⚠"
    cuerpo = " · ".join(_traducir_check(c) for c in checks)
    return f"Integridad: {simbolo} {cuerpo}"


# ── Fase LINKING, Etapa LA1 — línea compacta + traza de 5 pasos ────────────
def linea_linking(ls: dict) -> str | None:
    """`Linking: Actor=Juan (1er arg. de do') · Undergoer=flores (2º arg. de
    have') · María=NMR · M-transitivo=2 · PSA=Actor · concordancia 3sg ✓`.
    None si la etapa está apagada o esta rama no calculó linking (p.ej. sin
    root) — no se imprime una línea vacía."""
    info = ls.get("linking")
    if not info:
        return None
    return _linking.linea_compacta(info["macropapeles"], info["psa"], info["concordancia"])


def traza_linking(ls: dict, comp: dict | None) -> list[str] | None:
    """Los 5 pasos completos (--verbose): los 4 primeros ya los calculó el
    mapper (`ls['linking']['traza']`, pura, sin árbol); el 5º (asignación
    real) se resuelve aquí porque necesita `comp` (completeness.verificar),
    que en el momento del mapper todavía no existe — ver
    `linking.paso_5_asignacion`. None si la etapa está apagada."""
    info = ls.get("linking")
    if not info:
        return None
    pasos = list(info.get("traza") or [])
    if pasos:
        pasos[-1] = _linking.paso_5_asignacion(comp)
    return pasos


# ── Render en el orden de la convención GRR (§2) ───────────────────────────
def render_bloque(ls: dict, arbol_texto: str | None, comp: dict | None = None,
                  verbose: bool = False, indent: str = "  ") -> str:
    """Fase L5 §2 — un (sub)bloque en el ORDEN de la GRR: PRIMERO el árbol
    sintáctico, INMEDIATAMENTE DEBAJO la EL léxica (comparables de un
    vistazo), y debajo el resto (Tipo, EL formal, Argumentos, Rasgos,
    Integridad, CAUSE/método). Con `verbose` se muestra el detalle crudo
    (morph_note completo y resumen de completeness) en vez de la traducción
    user-friendly (§3)."""
    L: list[str] = []

    def add(s: str = ""):
        L.append(indent + s if s else "")

    # 1) Árbol sintáctico
    add("ÁRBOL SINTÁCTICO RRG")
    add("─" * 40)
    L.append(arbol_texto if arbol_texto else indent + "(sin árbol — la oración no se convirtió)")
    add()

    # 2) EL léxica, justo debajo del árbol (comparación visual directa).
    #    Etapa OPERATORS: se muestra ENVUELTA en ⟨ ⟩ — los operadores son
    #    parte de la representación RRG, no un añadido opcional.
    add(f"EL léxica  : {el_lexica(ls)}")
    add()

    # 3) Resto
    add(f"Tipo       : {clase_visible(ls)}")
    add(f"EL formal  : {el_formal(ls)}")
    if ls.get("args_map"):
        add(f"Argumentos : {ls['args_map']}")

    ops_linea = linea_operadores(ls)
    if ops_linea:
        add(ops_linea)

    linking_linea = linea_linking(ls)
    if linking_linea:
        add(linking_linea)
    if verbose:
        traza = traza_linking(ls, comp)
        if traza:
            for paso in traza:
                add(f"  {paso}")

    if verbose:
        for detalle in detalle_operadores(ls):
            add(detalle)
        if ls.get("morph_note"):
            add(f"Vector     : {ls['morph_note']}")
    else:
        rasgos = linea_rasgos(ls)
        if rasgos:
            add(rasgos)
        for frase in traducir_apendices(ls.get("morph_note", "")):
            add(frase)

    if comp is not None:
        if verbose:
            add(comp.get("resumen", ""))
        else:
            integridad = linea_integridad(comp)
            if integridad:
                add(integridad)

    if ls.get("causativo"):
        add(f"CAUSE      : {ls['causativo_tipo']} "
            f"({ls['causativo_source']}, conf. {ls['causativo_confianza']})")
    src = ls.get("cls_source", "")
    if src and src != "lexicon":
        metodo = ls.get("metodo")
        add(f"Método     : {metodo} (roBERTa)" if metodo else f"Método     : {src}")

    return "\n".join(L)
