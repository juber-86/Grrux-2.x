"""Fase LINKING, Etapa LA1 — el linking algorithm explícito de la RRG
(fig. 5.1, Van Valin 2005; spec de Julian, prompt_LA1.md).

Etapa ADITIVA: no cambia clases, ni EL, ni golds — lee la EL YA construida
(canónica desde OPERATORS_2: solo contenido léxico dentro de la EL,
operadores ⟨ ⟩ fuera) y añade el análisis del linking ENCIMA.

Jerarquía Actor-Padecedor (AUH), de mayor a menor rango — las 5 posiciones
de la fig. 5.1:
    arg. de DO > 1er arg. de do'(x,…) > 1er arg. de pred'(x,y) >
    2º arg. de pred'(x,y) > arg. de estado pred'(x)
Actor = el argumento de rango MÁS ALTO (no-Ø, no-NMR); Undergoer = el de
rango MÁS BAJO (default). El dativo español es NMR (decisión ya tomada en
L1a/L2.5, no se re-litiga aquí): ocupa una posición de la AUH pero queda
EXCLUIDO de la competencia de macropapel. Ø (argumento inespecificado) NUNCA
recibe macropapel — si el de mayor jerarquía es Ø, el siguiente candidato
asciende (ya es el comportamiento del se-pasivo/anticausativo; aquí se
declara formalmente).

M-transitividad = número de macropapeles asignados: transitivo=2,
intransitivo=1, ATRANSITIVO=0 (impersonales tipo "llueve" — por fin con su
nombre teórico).

El algoritmo es BIDIRECCIONAL:
  - sintaxis→semántica (COMPRENSIÓN): lo que el resto de gruxx ya hace
    (nucleo_periferia asigna macropapeles por deprel/plantilla).
  - semántica→sintaxis (PRODUCCIÓN, 5 pasos): EL → macropapeles →
    codificación PSA/caso/concordancia → plantilla sintáctica → asignación
    con AGX/PrCS/LDP.
Esta etapa NO genera oraciones: usa la dirección de producción como
RE-DERIVACIÓN VERIFICADORA (round-trip) sobre el árbol que YA existe — es
la Completeness Constraint operando en la otra dirección.

Módulo puro: sin Stanza, sin modelos, sin torch. `toks` son los dicts de
`complejo_verbal.desde_stanza` (id/text/lemma/upos/deprel/head/feats);
`arbol` (cuando se recibe) es un `discodop.tree.ParentedTree` ya construido,
igual que en completeness.py. La única I/O es `log_discrepancia` (append a
un CSV de curaduría), mismo patrón que `causatividad.log_candidato` /
`ditransitivas.log_candidato`.
"""

import csv
import re
from pathlib import Path

from .operadores import verbo_finito as _verbo_finito

PKG_DIR = Path(__file__).parent
DISCREPANCIAS_CSV = PKG_DIR / "data" / "linking_discrepancias.csv"

# ---------------------------------------------------------------------------
# §0. La Jerarquía Actor-Padecedor (AUH) — fig. 5.1, de mayor a menor rango.
# Constante documentada: estos 5 nombres son el contrato de `posicion` que
# build_ls / causatividad.componer_cause / ditransitivas.construir_el usan
# al declarar `ls_estructura` (ver esos módulos). Verificados 1:1 contra las
# 5 columnas de data/continuum_de_relaciones_tematicas.xlsx (mismo orden:
# "Argumento de DO", "Primer arg. de do'(x,…)", "Primer arg. de pred'(x,y)",
# "Segundo arg. de pred'(x,y)", "Argumento de estado pred'(x)") — ver
# test_linking.py::test_auh_coherente_con_continuum_xlsx.
# ---------------------------------------------------------------------------
AUH = ["arg_de_DO", "1_do", "1_pred_xy", "2_pred_xy", "arg_estado"]
_RANGO = {pos: i for i, pos in enumerate(AUH)}

# Etiqueta legible de cada posición — el mismo texto que usa la teoría
# (fig. 5.1 / prompt_LA1.md), para la justificación posicional de la traza:
# "Actor=Juan ← 1er arg. de do'".
JUSTIFICACION = {
    "arg_de_DO":  "arg. de DO",
    "1_do":       "1er arg. de do'",
    "1_pred_xy":  "1er arg. de pred'(x,y)",
    "2_pred_xy":  "2º arg. de pred'(x,y)",
    "arg_estado": "arg. de estado pred'(x)",
}


# ---------------------------------------------------------------------------
# §1 (parcial) — helper compartido por los constructores de EL: arman un
# frame de `ls_estructura` sin tener que repetir el dict a mano.
# ---------------------------------------------------------------------------
def frame(predicado: str, *args: dict) -> dict:
    """`{'predicado': predicado, 'args': [arg, ...]}` — azúcar para que
    build_ls/componer_cause/construir_el no repitan la forma del dict.
    Cada `arg` ya debe traer 'texto'/'posicion' (y opcionalmente 'nmr')."""
    return {"predicado": predicado, "args": list(args)}


def arg(texto: str, posicion: str, nmr: bool = False) -> dict:
    """Un argumento de `ls_estructura`. `nmr=True` excluye este argumento de
    la competencia de macropapel (dativo español — decisión de L1a/L2.5, no
    se re-litiga). El `id` de token NO se registra aquí (los constructores
    de EL no lo conocen — reciben texto plano, ver build_ls); lo añade
    `enriquecer_ids` en el mapper, que sí conoce el id de cada texto."""
    d = {"texto": texto, "posicion": posicion, "id": None}
    if nmr:
        d["nmr"] = True
    return d


def enriquecer_ids(estructura: list[dict], texto_a_id: dict[str, int]) -> list[dict]:
    """Rellena el campo 'id' de cada argumento de `estructura` a partir de
    un `{texto: id_de_token}` que el MAPPER arma con lo que YA tiene en ese
    punto del pipeline (roles['core'], o los ids propios de ditransitivas/
    causatividad) — los constructores de EL (build_ls, componer_cause,
    construir_el) no reciben ids, solo texto plano. Ø y las etiquetas
    morfológicas ('3sg') nunca tienen id (quedan en None): están satisfechas
    sin constituyente sintáctico propio, y así debe seguir viéndose.
    Modifica y devuelve la misma `estructura` (conveniencia)."""
    for fr in estructura or []:
        for a in fr.get("args", []):
            if a.get("texto") in texto_a_id:
                a["id"] = texto_a_id[a["texto"]]
    return estructura


# Posiciones cuyo predicado en la justificación es SIEMPRE el primitivo fijo
# (do'/DO) — nunca se sustituye por el lema léxico del frame (do' no es una
# plantilla que se instancia, es un primitivo de la teoría).
_POSICIONES_PRED_FIJO = {"arg_de_DO", "1_do"}


def _justificacion(posicion: str, predicado: str | None) -> str:
    """Texto legible de una posición AUH. En "1er/2º arg. de pred'(x,y)" y
    "arg. de estado pred'(x)" (plantillas GENÉRICAS de la teoría) se
    sustituye el predicado REAL del frame cuando se conoce — "2º arg. de
    have'" en vez de "2º arg. de pred'(x,y)", igual que el ejemplo canónico
    del prompt ("Undergoer=flores (2º arg. de have')"). arg_de_DO/1_do NO
    se sustituyen nunca (ver `_POSICIONES_PRED_FIJO`)."""
    generico = JUSTIFICACION.get(posicion, posicion or "?")
    if posicion in _POSICIONES_PRED_FIJO or not predicado:
        return generico
    if posicion == "1_pred_xy":
        return f"1er arg. de {predicado}"
    if posicion == "2_pred_xy":
        return f"2º arg. de {predicado}"
    if posicion == "arg_estado":
        return f"arg. de estado {predicado}"
    return generico


# ---------------------------------------------------------------------------
# §2.1 — asignación de macropapeles por la AUH.
# ---------------------------------------------------------------------------
def asignar_macropapeles(estructura: list[dict], cfg: dict | None = None) -> dict:
    """Aplica la AUH sobre `estructura` (§1: lista de frames
    `{'predicado','args':[{'texto','posicion','id'?,'nmr'?}]}` que
    build_ls/componer_cause/construir_el ya devuelven).

    Actor = argumento NO-Ø, NO-NMR de rango MÁS ALTO. Undergoer = el de
    rango MÁS BAJO. Con un único candidato tras excluir Ø/NMR
    (M-transitividad 1): rango arg_de_DO/1_do/1_pred_xy ("lado Actor" —
    incluye el 1er argumento de predicados relacionales de 2 lugares, p.ej.
    el Cognizer de "saber", que RRG trata como Actor por defecto incluso
    solo) → Actor; rango 2_pred_xy/arg_estado ("lado Undergoer", el
    paciente por defecto de logros/estados intransitivos, "el jarrón se
    rompió") → Undergoer. TODO (documentado en prompt_LA1.md): la doble
    ruta psych de la jerarquía (verbos de percepción/emoción con
    Actor/Undergoer intercambiables según construcción) NO se resuelve
    aquí — este es el default no marcado de Van Valin.

    `cfg` reservado (paridad con el resto de módulos de la etapa); esta
    función no usa configuración hoy.

    Devuelve:
        {'actor': arg|None, 'undergoer': arg|None, 'nmr': [arg,...],
         'inespecificado': [arg,...], 'm_transitividad': int}
    cada `arg` es el dict original + 'predicado' (el de su frame) +
    'rango' (0-4) + 'justificacion' (texto legible de su posición).
    """
    candidatos, nmr, inespecificado = [], [], []
    for fr in estructura or []:
        pred = fr.get("predicado")
        for a in fr.get("args", []):
            posicion = a.get("posicion")
            enriquecido = {**a, "predicado": pred,
                           "rango": _RANGO.get(posicion, len(AUH)),
                           "justificacion": _justificacion(posicion, pred)}
            if a.get("texto") == "Ø":
                inespecificado.append(enriquecido)
            elif a.get("nmr"):
                nmr.append(enriquecido)
            else:
                candidatos.append(enriquecido)

    if not candidatos:
        return {"actor": None, "undergoer": None, "nmr": nmr,
                "inespecificado": inespecificado, "m_transitividad": 0}

    candidatos.sort(key=lambda c: c["rango"])
    mas_alto, mas_bajo = candidatos[0], candidatos[-1]

    if len(candidatos) == 1:
        if mas_alto["rango"] <= _RANGO["1_pred_xy"]:
            actor, undergoer = mas_alto, None
        else:
            actor, undergoer = None, mas_alto
    else:
        actor, undergoer = mas_alto, mas_bajo

    m = (1 if actor is not None else 0) + (1 if undergoer is not None else 0)
    return {"actor": actor, "undergoer": undergoer, "nmr": nmr,
            "inespecificado": inespecificado, "m_transitividad": m}


# ---------------------------------------------------------------------------
# §2.2 — voz (la conoce el mapper) y selección de PSA.
# ---------------------------------------------------------------------------
def detectar_voz(caus: dict | None, roles: dict | None,
                 agx: list[dict] | None) -> str:
    """activa | pasiva_perifrastica | pasiva_refleja | anticausativa |
    impersonal. "La voz ya la conoce el mapper (nsubj:pass/expl:pass/agx
    se_pasivo/impersonal)" (prompt_LA1.md §2.2) — esta función solo declara
    la lectura a partir de esas mismas señales, ya calculadas por
    nucleo_periferia/causatividad. anticausativa ("se venden casas": el Ø
    del causante asciende el paciente a PSA) es estructuralmente el mismo
    patrón que la pasiva refleja para efectos de PSA — TEORÍA VALIDADA por
    Julian, 2026-07-10 (análisis de C. González Vergara)."""
    caus = caus or {}
    roles = roles or {}
    agx = agx or []
    if caus.get("se_anticausativo"):
        return "anticausativa"
    if any(e.get("fuente") == "se_pasivo" for e in agx):
        return "pasiva_refleja"
    if roles.get("impersonal") or any(e.get("fuente") == "se_impersonal" for e in agx):
        return "impersonal"
    if any(c.get("deprel") == "nsubj:pass" for c in (roles.get("core") or [])):
        return "pasiva_perifrastica"
    return "activa"


def seleccionar_psa(macropapeles: dict, voz: str) -> dict:
    """PSA (Argumento Sintáctico Privilegiado): español, lengua acusativa —
    pasiva (perifrástica o refleja) y anticausativa → Undergoer/Padecedor
    SIEMPRE (aunque también haya Actor, p.ej. agente de pasiva: no-PSA);
    impersonal o M-transitividad 0 (atransitivo) → SIN PSA (verbo congelado
    en 3sg). Voz activa → Actor si lo hay; si NO hay Actor (predicados
    intransitivos de un solo macropapel Undergoer por defecto — logros/
    estados no agentivos: "Juan llegó", "Juan es médico" — ningún marcador
    de pasiva/se, y aun así el único macropapel presente es Undergoer) el
    PSA es ESE Undergoer: es el único candidato a sujeto/concordancia que
    existe, y de hecho lo es (Van Valin: el macropapel único de un
    intransitivo, sea Actor o Undergoer, se realiza como sujeto por
    defecto). El PSA rige la concordancia verbal.
    """
    if voz == "impersonal" or macropapeles.get("m_transitividad", 0) == 0:
        return {"macrorol": None, "arg": None, "voz": voz,
                "justificacion": "sin PSA (impersonal/atransitivo, verbo congelado en 3sg)"}
    if voz == "activa":
        if macropapeles.get("actor") is not None:
            a, etiqueta = macropapeles["actor"], "Actor"
        else:
            a, etiqueta = macropapeles.get("undergoer"), "Undergoer"
    else:   # pasiva_perifrastica | pasiva_refleja | anticausativa
        a, etiqueta = macropapeles.get("undergoer"), "Undergoer"
    if a is None:
        return {"macrorol": None, "arg": None, "voz": voz,
                "justificacion": f"voz {voz}: sin argumento disponible para PSA"}
    return {"macrorol": etiqueta, "arg": a, "voz": voz,
            "justificacion": f"voz {voz} → PSA = {etiqueta}"}


# ---------------------------------------------------------------------------
# §2.3 — concordancia PSA↔verbo finito.
# ---------------------------------------------------------------------------
def _persona_numero(feats: dict | None) -> tuple[str, str]:
    """(persona, numero) normalizados de un dict de feats UD (Person/Number).
    Sin Number -> singular (los sustantivos comunes en singular casi nunca
    llevan Number=Sing explícito en el feats de Stanza; los propios como
    "Juan" a menudo no llevan NINGÚN feats). Sin Person -> 3 (default de
    cualquier NP que no flexiona persona)."""
    feats = feats or {}
    numero = "pl" if feats.get("Number") == "Plur" else "sg"
    persona = feats.get("Person", "3")
    return persona, numero


def verificar_concordancia(psa: dict | None, feats_psa: dict | None,
                           feats_verbo_finito: dict | None) -> dict:
    """El PSA rige la concordancia verbal (persona/número). Pro-drop /
    clítico-solo (el `arg` del PSA no tiene id de token): concuerda POR
    CONSTRUCCIÓN — la propia morfología verbal ES la fuente de esa
    etiqueta, no hay nada independiente que contrastar. Con PSA léxico (NP
    pleno): se compara contra el verbo FINITO — OJO lección de la etapa
    OPERATORS: leer el finito, NO el participio/gerundio de la raíz
    ("habría estudiado": persona/tiempo viven en 'habría', no en
    'estudiado'; ver `operadores.verbo_finito`)."""
    if psa is None or psa.get("arg") is None:
        return {"aplica": False, "ok": True, "corto": "",
                "detalle": "sin PSA: no aplica concordancia"}
    a = psa["arg"]
    if a.get("id") is None:
        persona, numero = _persona_numero(feats_verbo_finito)
        return {"aplica": True, "ok": True, "por_construccion": True,
                "corto": f"{persona}{numero}",
                "detalle": f"'{a.get('texto')}' concuerda por construcción "
                          "(pro-drop/clítico: la morfología verbal ES la fuente)"}
    persona_psa, numero_psa = _persona_numero(feats_psa)
    persona_verbo, numero_verbo = _persona_numero(feats_verbo_finito)
    ok = (persona_psa, numero_psa) == (persona_verbo, numero_verbo)
    simbolo = "✓" if ok else "✗"
    detalle = (f"PSA '{a.get('texto')}' {persona_psa}{numero_psa} vs "
              f"verbo {persona_verbo}{numero_verbo} {simbolo}")
    return {"aplica": True, "ok": ok, "por_construccion": False,
           "corto": f"{persona_verbo}{numero_verbo}", "detalle": detalle}


# ---------------------------------------------------------------------------
# §2.4 — traza de producción, 5 pasos legibles.
# ---------------------------------------------------------------------------
def _fmt_arg(a: dict | None) -> str:
    if a is None:
        return "—"
    return f"{a['texto']} ({a['justificacion']})"


def _paso1_el_seleccionada(ls_type: str, plantilla_info: dict | None) -> str:
    plantilla_info = plantilla_info or {}
    nombre = plantilla_info.get("nombre", "estándar")
    fuente = plantilla_info.get("fuente", "clasificador")
    return (f"Paso 1 — EL seleccionada: plantilla {nombre} (fuente: {fuente}) "
           f"· clase aspectual: {ls_type}")


def _paso2_macropapeles(macropapeles: dict) -> str:
    partes = [f"Actor={_fmt_arg(macropapeles.get('actor'))}",
             f"Undergoer={_fmt_arg(macropapeles.get('undergoer'))}"]
    for n in macropapeles.get("nmr", []):
        partes.append(f"{n['texto']}=NMR ({n['justificacion']})")
    partes.append(f"M-transitivo={macropapeles.get('m_transitividad', 0)}")
    return "Paso 2 — Macropapeles (AUH): " + " · ".join(partes)


def _paso3_codificacion(macropapeles: dict, voz: str, psa: dict,
                        concordancia: dict) -> str:
    partes = [f"PSA={psa.get('macrorol') or '—'} (voz {voz})"]
    psa_macrorol = (psa.get("macrorol") or "").lower()
    casos = []
    actor, undergoer = macropapeles.get("actor"), macropapeles.get("undergoer")
    if actor is not None:
        caso = "nominativo (PSA)" if psa_macrorol == "actor" else "acusativo"
        casos.append(f"{actor['texto']}={caso}")
    if undergoer is not None:
        caso = "nominativo (PSA)" if psa_macrorol == "undergoer" else "acusativo"
        casos.append(f"{undergoer['texto']}={caso}")
    for n in macropapeles.get("nmr", []):
        # NMR "oblicuo" (locativo, be-X') vs NMR dativo (recipiente/receptor
        # ditransitivo, have'/lema.to.(y)'): mismo macropapel (ninguno),
        # caso distinto — "a María" es dativo, "en la biblioteca" no.
        es_locativo = (n.get("predicado") or "").startswith("be-")
        casos.append(f"{n['texto']}=" + ("oblicuo (locativo)" if es_locativo
                                         else "dativo ('a')"))
    if casos:
        partes.append("caso: " + ", ".join(casos))
    partes.append(f"concordancia esperada: {concordancia.get('detalle', '—')}")
    return "Paso 3 — Codificación: " + " · ".join(partes)


def _paso4_plantilla_sintactica(macropapeles: dict, agx: list[dict] | None,
                                periferia: list[dict] | None) -> str:
    todos = [a for a in (macropapeles.get("actor"), macropapeles.get("undergoer"))
            if a is not None] + list(macropapeles.get("nmr") or [])
    con_id = [a for a in todos if a.get("id") is not None]
    morfologicos = [a for a in todos if a.get("id") is None]
    partes = [f"{len(con_id)} posición(es) core con constituyente propio"]
    if morfologicos:
        partes.append("satisfecha(s) solo morfológicamente: " +
                      ", ".join(a["texto"] for a in morfologicos))
    especiales = []
    if agx:
        especiales.append(f"AGX×{len(agx)}")
    destacados = [p for p in (periferia or []) if p.get("destacado_inicial")]
    if destacados:
        especiales.append(f"LDP×{len(destacados)}")
    partes.append("posiciones especiales: " + (", ".join(especiales) if especiales else "ninguna"))
    return "Paso 4 — Plantilla sintáctica: " + " · ".join(partes)


def paso_5_asignacion(comp: dict | None) -> str:
    """El paso 5 (asignación real) REUTILIZA las correspondencias que
    `completeness` ya calcula (prompt_LA1.md §2.4) — necesita el ÁRBOL, que
    no existe cuando el mapper corre (map_sentence_to_ls es anterior a
    ud2rrg.transform en el pipeline). Se completa en el momento del RENDER
    (display_grr.render_bloque / gruxx_motor.construir_sub_oracion), cuando
    `comp` (resultado de `completeness.verificar`) ya está disponible."""
    if comp is None:
        return "Paso 5 — Asignación: (pendiente: se completa tras generar el árbol)"
    if comp.get("ok") is None:
        return "Paso 5 — Asignación: sin árbol (la oración no se convirtió)"
    checks = comp.get("checks") or []
    argumentales = [c for c in checks if c.get("tipo") in ("argumento", "agx")]
    if not argumentales:
        return f"Paso 5 — Asignación: {comp.get('resumen', '')}"
    detalle = " · ".join(c.get("detalle", "") for c in argumentales)
    return f"Paso 5 — Asignación: {detalle}"


def traza_linking(ls_type: str, macropapeles: dict, voz: str, psa: dict,
                  concordancia: dict, plantilla_info: dict | None = None,
                  agx: list[dict] | None = None, periferia: list[dict] | None = None,
                  comp: dict | None = None) -> list[str]:
    """Los 5 pasos de la dirección de PRODUCCIÓN (EL → sintaxis), legibles.
    Con `comp=None` (el caso normal al calcularse dentro del mapper, antes
    de que exista árbol) el paso 5 queda como placeholder — ver
    `paso_5_asignacion`. El caller vuelve a llamar a esta función con
    `comp` ya resuelto para obtener la traza completa en el momento del
    render (es una función pura y barata: recalcularla no tiene costo)."""
    return [
        _paso1_el_seleccionada(ls_type, plantilla_info),
        _paso2_macropapeles(macropapeles),
        _paso3_codificacion(macropapeles, voz, psa, concordancia),
        _paso4_plantilla_sintactica(macropapeles, agx, periferia),
        paso_5_asignacion(comp),
    ]


def linea_compacta(macropapeles: dict, psa: dict, concordancia: dict) -> str:
    """Línea compacta de terminal (§4):
    `Linking: Actor=Juan (1er arg. de do') · Undergoer=flores (2º arg. de
    have') · María=NMR · M-transitivo=2 · PSA=Actor · concordancia 3sg ✓`
    """
    partes = [f"Actor={_fmt_arg(macropapeles.get('actor'))}",
             f"Undergoer={_fmt_arg(macropapeles.get('undergoer'))}"]
    for n in macropapeles.get("nmr", []):
        partes.append(f"{n['texto']}=NMR")
    partes.append(f"M-transitivo={macropapeles.get('m_transitividad', 0)}")
    partes.append(f"PSA={psa.get('macrorol') or '—'}")
    if concordancia.get("aplica"):
        simbolo = "✓" if concordancia.get("ok") else "⚠"
        partes.append(f"concordancia {concordancia.get('corto', '')} {simbolo}".strip())
    return "Linking: " + " · ".join(partes)


# ---------------------------------------------------------------------------
# §3 — reconciliación con los macropapeles existentes (args_map).
# ---------------------------------------------------------------------------
# args_map es una cadena PLANA y CONTROLADA por el propio mapper
# ("x1:texto,deprel,macropapel; x2:texto,deprel,macropapel; …", más
# segmentos sueltos como "Periferia: …" que este patrón excluye a
# propósito) — NO es la EL (eso sí está prohibido parsear, ver §1 del
# prompt): es un formato fijo de una sola línea que el propio mapper
# genera, sin anidamiento.
_RE_ARG_MAP_ITEM = re.compile(r"^x\d+:(.+?),([^,]+),(.+)$")


def _parse_args_map(args_map: str) -> dict[str, dict]:
    salida: dict[str, dict] = {}
    for parte in (args_map or "").split(";"):
        m = _RE_ARG_MAP_ITEM.match(parte.strip())
        if not m:
            continue
        texto, deprel, macropapel = (g.strip() for g in m.groups())
        salida[texto] = {"deprel": deprel, "macropapel": macropapel}
    return salida


def reconciliar(macropapeles: dict, args_map: str) -> dict:
    """§3 — compara la asignación AUH (`macropapeles`) contra la que YA
    calcula el resto del pipeline (deprel/plantilla, vía nucleo_periferia /
    ditransitivas / causatividad — expuesta en `args_map`). Si coinciden
    (esperado): `args_map` gana la cita del macropapel, la AUH aporta la
    justificación posicional ("Actor(Efectuador ← 1er arg. de do')"). Si NO
    coinciden: NO se toca nada (ni gold ni la asignación vieja en
    silencio) — se reporta para que Julian decida; probablemente indica un
    bug de una de las dos vías (ver CHECKPOINT_LA1.md)."""
    previos = _parse_args_map(args_map)
    filas = []
    for macrorol, a in (("Actor", macropapeles.get("actor")),
                        ("Undergoer", macropapeles.get("undergoer"))):
        if a is None:
            continue
        anterior = previos.get(a["texto"])
        macropapel_previo = (anterior or {}).get("macropapel", "")
        coincide = anterior is not None and macropapel_previo.startswith(macrorol)
        filas.append({
            "texto": a["texto"], "macrorol_auh": macrorol,
            "posicion": a["posicion"], "justificacion": a["justificacion"],
            "macropapel_previo": macropapel_previo or "(no encontrado)",
            "coincide": coincide,
        })
    return {"filas": filas, "hay_discrepancia": any(not f["coincide"] for f in filas)}


def log_discrepancia(lema: str, oracion: str, fila: dict,
                     path: Path = DISCREPANCIAS_CSV) -> None:
    """Registra una discrepancia AUH vs args_map (append-only, deduplicado
    por (lema, oración, texto) — mismo patrón que
    `causatividad.log_candidato` / `ditransitivas.log_candidato`)."""
    nuevo = not path.exists()
    clave = (lema, oracion, fila["texto"])
    if not nuevo:
        with open(path, newline="", encoding="utf-8") as f:
            if any((r["lema"], r["oracion"], r["texto"]) == clave
                   for r in csv.DictReader(f)):
                return
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["lema", "oracion", "texto", "macrorol_auh", "posicion",
                       "macropapel_previo"])
        w.writerow([lema, oracion, fila["texto"], fila["macrorol_auh"],
                   fila["posicion"], fila["macropapel_previo"]])


# ---------------------------------------------------------------------------
# §5 — round-trip: expectativas sintácticas re-derivadas de la EL, contra
# el árbol real. Helpers de árbol MÍNIMOS y DELIBERADAMENTE duplicados de
# completeness.py (evita el import circular: completeness.py importa ESTE
# módulo para integrar sus checks — ver completeness._chequear_linking).
# ---------------------------------------------------------------------------
def _tiene_agx(arbol) -> bool:
    if arbol is None:
        return False
    return any(isinstance(st.label, str) and st.label == "AGX" for st in arbol.subtrees())


def _tiene_constituyente_o_nucleo(arbol, token_id: int | None) -> bool:
    """¿Hay un NP/PP argumental, o un NUC verbal (juntura clausal,
    ccomp/xcomp/csubj — ver completeness._es_argumento_clausal), en la
    posición de `token_id`?"""
    if arbol is None or token_id is None:
        return False
    pos = token_id - 1
    for st in arbol.subtrees():
        label = st.label if isinstance(st.label, str) else ""
        if label in ("NP", "PP", "NUC") and pos in st.leaves():
            return True
    return False


def expectativas_sintacticas(macropapeles: dict, agx: list[dict] | None,
                             arbol, concordancia: dict | None = None) -> list[dict]:
    """Round-trip (dirección de producción, §5): desde la EL YA analizada,
    re-derivar qué DEBERÍA haber en el árbol (nº de posiciones core, PSA
    con su concordancia, nodos AGX) y comparar contra el árbol real.
    Devuelve checks con el MISMO formato que completeness.py
    (`{'tipo','elemento','estado','detalle'}`), con `estado` prefijado
    `linking_` — se integran a la lista de checks de Integridad existente,
    sin repetir lo que ya cubren (p.ej. completeness._chequear_agx ya
    reconcilia el CONTEO fino de AGX; aquí solo se confirma la
    presencia/ausencia que la EL anticipa — ángulo de PRODUCCIÓN, no de
    comprensión, ver docstring del módulo).

    `arbol=None` (la oración no convirtió): sin checks — no es un fallo de
    linking, es la misma situación que ya reporta completeness.verificar.
    """
    checks: list[dict] = []
    if arbol is None:
        return checks

    candidatos = [a for a in (macropapeles.get("actor"), macropapeles.get("undergoer"))
                 if a is not None] + list(macropapeles.get("nmr") or [])
    esperan_constituyente = [a for a in candidatos if a.get("id") is not None]
    encontrados = sum(1 for a in esperan_constituyente
                      if _tiene_constituyente_o_nucleo(arbol, a["id"]))
    n_esp = len(esperan_constituyente)
    checks.append({
        "tipo": "linking", "elemento": "conteo_core",
        "estado": "linking_ok" if encontrados == n_esp else "linking_falta_en_arbol",
        "detalle": f"producción: {n_esp} posición(es) core esperada(s) por la EL, "
                  f"{encontrados} con constituyente en el árbol",
    })

    if concordancia is not None and concordancia.get("aplica"):
        estado = "linking_ok" if concordancia.get("ok") else "linking_concordancia_error"
        checks.append({"tipo": "linking", "elemento": "concordancia",
                       "estado": estado, "detalle": concordancia.get("detalle", "")})

    if agx:
        presente = _tiene_agx(arbol)
        checks.append({
            "tipo": "linking", "elemento": "agx",
            "estado": "linking_ok" if presente else "linking_falta_en_arbol",
            "detalle": ("producción: AGX esperado por la EL y presente en el árbol"
                       if presente else
                       "producción: AGX esperado por la EL pero AUSENTE en el árbol"),
        })

    return checks


# ---------------------------------------------------------------------------
# Orquestador — llamado UNA VEZ desde rrg_ls_mapper.map_sentence_to_ls,
# gated por `linking.enabled`. Pasos 1-4 de la traza (el paso 5 y el
# round-trip necesitan el árbol: se resuelven más tarde, ver arriba).
# ---------------------------------------------------------------------------
def _parse_feats(feats: str | None) -> dict:
    salida = {}
    for par in (feats or "").split("|"):
        if "=" in par:
            k, v = par.split("=", 1)
            salida[k] = v
    return salida


def _tok_por_id(toks: list[dict], tid: int | None) -> dict | None:
    if tid is None:
        return None
    return next((t for t in toks if t.get("id") == tid), None)


def analizar_linking(estructura: list[dict], roles: dict, agx: list[dict],
                     caus: dict | None, toks: list[dict], root_id: int,
                     ls_type: str, plantilla_info: dict | None = None,
                     cfg: dict | None = None) -> dict:
    """Pasos 1-4 de la dirección de producción sobre la EL ya construida
    (no genera oraciones — usa esta dirección como re-derivación
    verificadora, ver docstring del módulo). Devuelve:
        {'macropapeles', 'voz', 'psa', 'concordancia', 'traza'}
    `traza` trae el paso 5 como placeholder (sin árbol todavía) — el
    caller (display_grr) lo completa llamando otra vez a `traza_linking`
    con `comp` resuelto.
    """
    macropapeles = asignar_macropapeles(estructura, cfg)
    voz = detectar_voz(caus, roles, agx)
    psa = seleccionar_psa(macropapeles, voz)

    tok_psa = _tok_por_id(toks, (psa.get("arg") or {}).get("id"))
    feats_psa = _parse_feats(tok_psa.get("feats")) if tok_psa else None
    fin = _verbo_finito(toks, root_id)
    feats_verbo = _parse_feats(fin.get("feats")) if fin else None
    concordancia = verificar_concordancia(psa, feats_psa, feats_verbo)

    periferia = roles.get("periferia") if roles else None
    traza = traza_linking(ls_type, macropapeles, voz, psa, concordancia,
                          plantilla_info, agx, periferia, comp=None)

    return {"macropapeles": macropapeles, "voz": voz, "psa": psa,
            "concordancia": concordancia, "traza": traza}
