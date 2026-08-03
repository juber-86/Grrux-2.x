"""Etapa OPERATORS — operadores de la GRR en la Estructura Lógica.

Los operadores (tiempo, aspecto, modalidad, fuerza ilocutiva…) son categorías
gramaticales CERRADAS y semánticamente complejas. Van Valin NO les da
semántica sustantiva: les da un LUGAR en la representación, indicando su
ALCANCE sobre la EL. La notación son versalitas dentro de corchetes angulares
⟨ ⟩ (U+27E8/U+27E9 — NUNCA `<` `>`, que colisionan con HTML en la GUI).

Esquema general de scope (2.25), de fuera hacia dentro:

    ⟨IF … ⟨EVID … ⟨TNS … ⟨STA … ⟨NEG … ⟨MOD … ⟨EVQ … ⟨DIR … ⟨ASP … ⟨LS⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

Los operadores SIN especificación SE OMITEN. Ejemplo canónico (2.26),
"Has Kim been crying?":

    ⟨IF INT ⟨TNS PRES ⟨ASP PERF PROG ⟨do'(Kim, [cry'(Kim)])⟩⟩⟩⟩

Los operadores NO tocan la proyección de constituyentes (`ud2rrg.py`): son
una proyección APARTE, en espejo, que converge con el árbol solo en el núcleo
(la V). Este módulo la calcula; la EL envuelta y la GUI la representan.

EVID, EVQ y DIR no se implementan (el español no los gramaticaliza como los
persigue Van Valin): se omiten siempre, pero conservan su hueco en el orden
de scope para que añadirlos después no cambie el anidamiento.

NOTA DE NOTACIÓN: nada aquí referencia variables numeradas (x1/x2/x3). Esa
numeración es un gruxx-ismo con una reforma pendiente (la GRR usa x/y por
predicado); el dict de operadores y el JSON de la GUI hablan de valores,
estratos y señales de origen, nunca de variables.

Detección y notación son funciones PURAS: sin Stanza, sin modelos, sin I/O.
La única excepción es `log_perifrasis` (append a un CSV de curaduría), mismo
patrón que `ditransitivas.log_candidato`. Los `toks` son los dicts de
`complejo_verbal.desde_stanza` (id, text, lemma, upos, deprel, head, feats).
"""

import csv
from pathlib import Path

CANDIDATOS_CSV = Path(__file__).parent / "data" / "perifrasis_no_cubiertas.csv"

# Corchetes angulares matemáticos (U+27E8 / U+27E9).
ABRE = "⟨"
CIERRA = "⟩"

# Orden de scope (2.25), de FUERA hacia DENTRO. EVID/EVQ/DIR nunca se
# detectan en español pero mantienen su hueco: si algún día se añaden, el
# anidamiento del resto no cambia.
ORDEN_SCOPE = ["IF", "EVID", "TNS", "STA", "NEG", "MOD", "EVQ", "DIR", "ASP"]

# Estrato de la cláusula que modifica cada operador (fig. 5.2). Determina a
# qué nodo de la espina se engancha en la proyección espejo de la GUI y su
# cercanía morfológica a la raíz verbal.
ESTRATO = {
    "ASP": "nuclear", "DIR": "nuclear", "NEG": "nuclear",
    "MOD": "central", "EVQ": "central",
    "STA": "clausular", "TNS": "clausular", "EVID": "clausular", "IF": "clausular",
}

# TODO-OPERATORS-2: NEG se asigna a 'nuclear' sin subtipar. La teoría
# distingue NEG nuclear (alcance sobre el núcleo) de NEG interna (alcance
# sobre el core, estrato central); separarlas necesita alcance real sobre
# los argumentos, que es materia del sub-prompt de corrección.

_MOODS_IRREALIS = {"Sub": "Mood=Sub", "Cnd": "Mood=Cnd"}

# Tense (UD) -> valor de TNS. 'Imp' (imperfecto) es TNS PAST *y además*
# ASP IMPF: dos operadores de un solo feat morfológico.
_TENSE_A_TNS = {"Past": "PAST", "Imp": "PAST", "Pres": "PRES", "Fut": "FUT"}


# ---------------------------------------------------------------------------
# helpers de tokens
# ---------------------------------------------------------------------------
def _feats(tok: dict) -> dict:
    """"Mood=Ind|Tense=Past" -> {'Mood': 'Ind', 'Tense': 'Past'}."""
    crudo = tok.get("feats") or ""
    salida = {}
    for par in crudo.split("|"):
        if "=" in par:
            k, v = par.split("=", 1)
            salida[k] = v
    return salida


def _hijos(toks: list[dict], head_id: int) -> list[dict]:
    return [t for t in toks if t.get("head") == head_id]


def _tok(toks: list[dict], tid: int) -> dict | None:
    return next((t for t in toks if t.get("id") == tid), None)


def _lema(tok: dict) -> str:
    return (tok.get("lemma") or "").lower()


def _texto_con_fixed(toks: list[dict], tok: dict) -> str:
    """Texto de un adverbio incluyendo sus dependientes `fixed` — "tal vez"
    parsea como NOUN('tal') + fixed('vez'), no como un solo token."""
    piezas = [tok] + [h for h in _hijos(toks, tok["id"]) if h.get("deprel") == "fixed"]
    piezas.sort(key=lambda t: t["id"])
    return " ".join((t.get("text") or "").lower() for t in piezas)


def verbo_finito(toks: list[dict], root_id: int) -> dict | None:
    """El verbo que porta los rasgos FINITOS de la cláusula: la raíz si es
    finita, si no el primer auxiliar finito que dependa de ella.

    Esto NO es un detalle: en "Juan habría estudiado" la raíz ('estudiado')
    lleva `Tense=Past` por ser PARTICIPIO, no por ser pasado — leer el tiempo
    de ahí daría TNS PAST cuando el tiempo real es el condicional de 'habría'
    (que no lleva Tense y sí Mood=Cnd → STA IRR, sin TNS). Igual en
    "¿Ha estado llorando Juan?": la raíz es gerundio (sin Tense) y el tiempo
    vive en el auxiliar 'Ha' (Tense=Pres) → TNS PRES, como en 2.26.
    """
    root = _tok(toks, root_id)
    if root is None:
        return None
    if _feats(root).get("VerbForm") == "Fin":
        return root
    for aux in _hijos(toks, root_id):
        if aux.get("deprel") in ("aux", "aux:pass", "cop") and \
                _feats(aux).get("VerbForm") == "Fin":
            return aux
    return None


# ---------------------------------------------------------------------------
# detección por operador
# ---------------------------------------------------------------------------
def _spec(valor: str, op: str, origen: str, ids) -> dict:
    """Un operador detectado. `origen_ids` son los TOKENS que lo dispararon —
    no es decoración:

      · Etapa OPERATORS_2 §1: el mapper suprime el wrapper de periferia de un
        token que YA disparó un operador, para que la información no aparezca
        dos veces (⟨NEG ⟨no'(…)⟩⟩). Hacerlo por id y no por lista de lemas es
        lo que garantiza que NADA se pierda: si un adverbio no dispara
        operador (p.ej. 'aparentemente', que es evidencial y EVID no está
        implementado), conserva su wrapper léxico.
      · Etapa OPERATORS_2 §2: la corrección necesita saber a qué token culpar.
    """
    return {"valor": valor, "estrato": ESTRATO[op], "origen": origen,
            "origen_ids": sorted({i for i in (ids or []) if i is not None})}


def _detectar_if(toks: list[dict], root_id: int) -> dict:
    """Fuerza ilocutiva. DEC es el valor por defecto y SÍ se muestra (es
    informativo: dice que la oración es una aserción, no una omisión).

    LIMITACIÓN VERIFICADA CONTRA STANZA (sonda de esta etapa): el parser
    español NUNCA etiquetó `Mood=Imp` en los imperativos de prueba —
    "¡Corre!" y "¡Estudia la lección!" salen como `Mood=Ind|Person=3`
    (homófonos del presente de indicativo) y "¡Corred!" sale como INTJ. Por
    eso IMP se infiere de la FORMA de la oración (¡! + raíz verbal finita sin
    sujeto expreso) y no del modo. Es deliberadamente conservador: un
    imperativo sin signos de exclamación ("Cómete la manzana.") se lee DEC —
    no hay señal que lo distinga del indicativo, y el sesgo del pipeline es
    "solo evidencia presente y unívoca dispara".
    """
    root = _tok(toks, root_id)
    root_feats = _feats(root) if root else {}

    if root_feats.get("Mood") == "Imp":
        return _spec("IMP", "IF", f"'{root.get('text')}' Mood=Imp", [root_id])

    qest = [t for t in toks if "PunctType=Qest" in (t.get("feats") or "")
            or t.get("text") in ("¿", "?")]
    if qest:
        return _spec("INT", "IF", "signos de interrogación ¿?",
                     [t.get("id") for t in qest])

    excl = [t for t in toks if "PunctType=Excl" in (t.get("feats") or "")
            or t.get("text") in ("¡", "!")]
    tiene_sujeto = any(h.get("deprel", "").startswith("nsubj")
                       for h in _hijos(toks, root_id))
    if (excl and root is not None and root.get("upos") == "VERB"
            and root_feats.get("VerbForm") == "Fin" and not tiene_sujeto):
        return _spec("IMP", "IF", "¡! + verbo finito sin sujeto expreso",
                     [root_id] + [t.get("id") for t in excl])

    if not excl:
        wh = next((t for t in toks if "PronType=Int" in (t.get("feats") or "")), None)
        if wh is not None:
            return _spec("INT", "IF", f"interrogativo '{wh.get('text')}'",
                         [wh.get("id")])

    return _spec("DEC", "IF", "declarativa (default)", [])


def _detectar_tns(fin: dict | None) -> dict | None:
    if fin is None:
        return None
    tense = _feats(fin).get("Tense")
    valor = _TENSE_A_TNS.get(tense or "")
    if valor is None:
        return None
    return _spec(valor, "TNS", f"'{fin.get('text')}' Tense={tense}", [fin.get("id")])


def _detectar_asp(toks: list[dict], root_id: int, fin: dict | None,
                  aux_asp: str | None) -> dict | None:
    """PERF (haber), PROG (estar + gerundio) e IMPF (imperfecto). COMBINABLES:
    "ha estado llorando" → `ASP PERF PROG`, "había estudiado" → `ASP PERF IMPF`.

    Por qué no se delega en `rrg_ls_mapper.detect_aux_aspect`: esa función
    devuelve UN solo valor ('prog' | 'complet' | None) y corta en el primer
    auxiliar que matchea, así que en "ha estado llorando" ve 'haber' y
    devuelve 'complet' — pierde el progresivo. Aquí se recorren TODOS los
    auxiliares. `aux_asp` se sigue recibiendo y se usa como red de seguridad
    (si el barrido propio no vio nada pero el mapper sí, se respeta su
    veredicto) para que las dos vistas nunca se contradigan.
    """
    valores, origenes, ids = [], [], []
    root = _tok(toks, root_id)
    root_ger = _feats(root).get("VerbForm") == "Ger" if root else False

    auxiliares = [h for h in _hijos(toks, root_id)
                  if h.get("deprel") in ("aux", "aux:pass")]
    for aux in auxiliares:
        if _lema(aux) == "haber" and "PERF" not in valores:
            valores.append("PERF")
            origenes.append(f"auxiliar '{aux.get('text')}'")
            ids.append(aux.get("id"))
        elif _lema(aux) == "estar" and root_ger and "PROG" not in valores:
            valores.append("PROG")
            origenes.append(f"auxiliar '{aux.get('text')}' + gerundio")
            ids.append(aux.get("id"))

    if fin is not None and _feats(fin).get("Tense") == "Imp":
        valores.append("IMPF")
        origenes.append(f"'{fin.get('text')}' imperfecto")
        ids.append(fin.get("id"))

    if not valores and aux_asp:
        red = {"prog": "PROG", "complet": "PERF"}.get(aux_asp)
        if red:
            valores.append(red)
            origenes.append(f"detect_aux_aspect={aux_asp}")

    if not valores:
        return None
    # Orden canónico del libro (2.26): PERF antes que PROG; IMPF al final.
    orden = {"PERF": 0, "PROG": 1, "IMPF": 2}
    pares = sorted(zip(valores, origenes), key=lambda p: orden.get(p[0], 9))
    return _spec(" ".join(v for v, _ in pares), "ASP",
                 " + ".join(o for _, o in pares), ids)


def _detectar_neg(toks: list[dict], root_id: int, cfg: dict) -> dict | None:
    """Negación gramatical. Dispara SOLO con el negador puro ('no'), NO con
    cualquier `Polarity=Neg`.

    Por qué (decisión de la Etapa OPERATORS_2 §1, a la vista de la sonda):
    Stanza marca `Polarity=Neg` también en 'nunca' / 'jamás' / 'tampoco', pero
    esas palabras FUSIONAN negación con cuantificación de evento ('nunca' =
    'en ninguna ocasión') o con aditividad ('tampoco'). Reducirlas a ⟨NEG⟩
    perdería esa parte del significado, porque el operador que la expresaría
    —EVQ— no está implementado. Así que conservan su wrapper LÉXICO
    (`never'(…)`) y no disparan NEG: la etapa elimina duplicaciones, nunca
    información. TODO: cuando exista EVQ, 'nunca' debería ser ⟨NEG⟨EVQ…⟩⟩.
    """
    # `str(n)`: si alguien escribe `negadores: [no]` sin comillas, YAML 1.1 lo
    # entrega como el booleano False -- se normaliza en vez de reventar.
    negadores = {str(n).lower() for n in ((cfg or {}).get("negadores") or ["no"])}
    for h in _hijos(toks, root_id):
        if h.get("deprel") == "advmod" and _lema(h) in negadores:
            return _spec("NEG", "NEG", f"'{h.get('text')}' advmod del verbo",
                         [h.get("id")])
    return None


def _detectar_mod(toks: list[dict], root_id: int, cfg: dict) -> dict | None:
    """Modalidad deóntica. Patrones VERIFICADOS contra Stanza en esta etapa:

      · deber/poder + infinitivo → AUX con `deprel=aux` colgando del
        infinitivo, que es la RAÍZ ("Juan debe estudiar": root=estudiar,
        aux=debe). Patrón limpio.
      · "tener que" + infinitivo → NO parsea como auxiliar: la raíz es
        'tiene' (VERB) y el infinitivo cuelga como `conj` con un `cc`
        ('que') propio. Se cubre con un patrón aparte y se documenta: la EL
        se construye sobre 'tener', no sobre el infinitivo (divergencia
        preexistente del pipeline, ajena a esta etapa).
    """
    modales = (cfg or {}).get("modales") or {}
    for aux in _hijos(toks, root_id):
        if aux.get("deprel") not in ("aux", "aux:pass"):
            continue
        valor = modales.get(_lema(aux))
        if valor:
            return _spec(valor, "MOD",
                         f"perífrasis '{aux.get('text')} + infinitivo'",
                         [aux.get("id")])

    # Perífrasis cuyo verbo modal es la RAÍZ y el infinitivo cuelga como
    # `xcomp` ('suele/quiere/va a + inf'). Es la forma en que Stanza analiza
    # de verdad casi todas las perífrasis españolas (ver
    # `perifrasis_no_cubiertas`), y sin este patrón añadir un lema a
    # `operadores.modales` no tendría NINGÚN efecto: la corrección de un MOD
    # no cubierto escribiría en config una entrada que nadie lee.
    root = _tok(toks, root_id)
    if root is not None:
        valor = modales.get(_lema(root))
        if valor:
            inf = next((h for h in _hijos(toks, root_id)
                        if h.get("deprel") == "xcomp"
                        and _feats(h).get("VerbForm") == "Inf"), None)
            if inf is not None:
                return _spec(valor, "MOD",
                             f"perífrasis '{root.get('text')} + {inf.get('text')}'",
                             [root_id, inf.get("id")])

    if (cfg or {}).get("perifrasis_tener_que", True):
        if root is not None and _lema(root) == "tener":
            for h in _hijos(toks, root_id):
                if h.get("deprel") != "conj" or _feats(h).get("VerbForm") != "Inf":
                    continue
                if any(_lema(n) == "que" and n.get("deprel") == "cc"
                       for n in _hijos(toks, h["id"])):
                    return _spec("OBLG", "MOD",
                                 f"perífrasis 'tener que {h.get('text')}'",
                                 [root_id, h.get("id")])
    return None


def _detectar_sta(toks: list[dict], root_id: int, fin: dict | None,
                  cfg: dict) -> dict | None:
    """Estatus (modalidad epistémica): real vs irreal. REAL se omite por
    defecto; solo se muestra si un adverbio ASERTIVO lo hace explícito."""
    origenes, ids = [], []

    if fin is not None:
        mood = _feats(fin).get("Mood")
        if mood in _MOODS_IRREALIS:
            origenes.append(f"'{fin.get('text')}' {_MOODS_IRREALIS[mood]}")
            ids.append(fin.get("id"))

    irreales = {a.lower() for a in ((cfg or {}).get("adv_epistemicos_irreal") or [])}
    reales = {a.lower() for a in ((cfg or {}).get("adv_epistemicos_real") or [])}
    adv_real = None
    for h in _hijos(toks, root_id):
        if h.get("deprel") != "advmod":
            continue
        frase = _texto_con_fixed(toks, h)
        if frase in irreales or _lema(h) in irreales:
            origenes.append(f"adverbio '{frase}'")
            ids.append(h.get("id"))
        elif frase in reales or _lema(h) in reales:
            adv_real = (frase, h.get("id"))

    if origenes:
        return _spec("IRR", "STA", " · ".join(origenes), ids)
    if adv_real:
        return _spec("REAL", "STA", f"adverbio asertivo '{adv_real[0]}'",
                     [adv_real[1]])
    return None


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def detectar_operadores(toks: list[dict], root_id: int, aux_asp: str | None,
                        cfg: dict | None = None) -> dict:
    """Operadores de la cláusula, cada uno con VALOR, ESTRATO y SEÑAL DE
    ORIGEN (qué lo disparó, en texto legible).

    La señal de origen no es decoración: alimenta los tooltips de la GUI y es
    la interfaz que consumirá la corrección de operadores (TODO-OPERATORS-2)
    para saber qué evidencia hay que contradecir al corregir.

    Devuelve p. ej.:
        {'IF':  {'valor': 'DEC', 'estrato': 'clausular',
                 'origen': 'declarativa (default)', 'origen_ids': []},
         'TNS': {'valor': 'PAST', 'estrato': 'clausular',
                 'origen': "'corrió' Tense=Past", 'origen_ids': [2]}}
    """
    cfg = cfg or {}
    if not toks or root_id is None:
        return {}

    fin = verbo_finito(toks, root_id)
    candidatos = {
        "IF":  _detectar_if(toks, root_id),
        "TNS": _detectar_tns(fin),
        "STA": _detectar_sta(toks, root_id, fin, cfg),
        "NEG": _detectar_neg(toks, root_id, cfg),
        "MOD": _detectar_mod(toks, root_id, cfg),
        "ASP": _detectar_asp(toks, root_id, fin, aux_asp),
    }
    # Orden de scope en el propio dict (Python conserva el orden de
    # inserción): quien lo recorra ya lo ve de fuera hacia dentro.
    return {op: candidatos[op] for op in ORDEN_SCOPE
            if candidatos.get(op) is not None}


def tokens_cubiertos(ops: dict) -> dict[int, str]:
    """`{token_id: 'NEG'}` — qué operador cubre cada token disparador.

    Lo consume el mapper (OPERATORS_2 §1) para NO envolver como predicado de
    la EL un elemento que ya está representado como operador: en Van Valin
    los operadores no son predicados, y tenerlos en los dos sitios a la vez
    (⟨NEG ⟨no'(…)⟩⟩) es la duplicación que esta etapa elimina.
    """
    cubiertos = {}
    for op, spec in (ops or {}).items():
        for tid in spec.get("origen_ids") or []:
            cubiertos.setdefault(tid, op)
    return cubiertos


def perifrasis_no_cubiertas(toks: list[dict], root_id: int,
                            cfg: dict | None = None) -> list[dict]:
    """Perífrasis potencialmente modales/aspectuales que este módulo NO cubre
    todavía (soler, querer, ir a, acabar de, volver a…). No cambian la
    representación: se devuelven para que el mapper las loguee y Julian decida
    cuáles ascender a operador. Función pura; el logueo es del caller.

    DOS PATRONES, ambos verificados contra Stanza (sonda de esta etapa), y el
    segundo es el que de verdad ocurre:

      · `aux` + raíz infinitiva — la forma de 'deber'/'poder'. Se vigila por
        si el parser clasifica así alguna perífrasis nueva.
      · raíz VERBAL + `xcomp` infinitivo — CÓMO PARSEAN REALMENTE 'soler',
        'querer', 'ir a', 'acabar de', 'volver a': el verbo de la perífrasis
        es la RAÍZ y el infinitivo cuelga de él como xcomp (con `mark` 'a'/'de'
        cuando la perífrasis lo lleva). Sin este segundo patrón la lista de
        vigiladas quedaba INERTE: no se logueaba nunca nada.
    """
    cfg = cfg or {}
    vigiladas = {v.lower() for v in (cfg.get("perifrasis_vigiladas") or [])}
    cubiertas = set((cfg.get("modales") or {}).keys())
    salida = []

    for aux in _hijos(toks, root_id):
        if aux.get("deprel") not in ("aux", "aux:pass"):
            continue
        lema = _lema(aux)
        if lema in vigiladas and lema not in cubiertas:
            salida.append({"lema": lema, "texto": aux.get("text"),
                           "deprel": aux.get("deprel")})

    root = _tok(toks, root_id)
    if root is not None and _lema(root) in vigiladas and _lema(root) not in cubiertas:
        inf = next((h for h in _hijos(toks, root_id)
                    if h.get("deprel") == "xcomp"
                    and _feats(h).get("VerbForm") == "Inf"), None)
        if inf is not None:
            salida.append({"lema": _lema(root), "texto": root.get("text"),
                           "deprel": "root+xcomp"})
    return salida


def log_perifrasis(lema: str, oracion: str, path: Path = CANDIDATOS_CSV) -> None:
    """Registra una perífrasis vigilada que NO se tradujo a operador, para
    curaduría (mismo patrón que `ditransitivas.log_candidato`: deduplicado por
    (lema, oración), append-only, nunca rompe el análisis)."""
    nuevo = not path.exists()
    if not nuevo:
        with open(path, newline="", encoding="utf-8") as f:
            if any(r.get("lema") == lema and r.get("oracion") == oracion
                   for r in csv.DictReader(f)):
                return
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["lema", "oracion"])
        w.writerow([lema, oracion])


def etiqueta(op: str, spec: dict) -> str:
    """`TNS PAST`, y solo `NEG` cuando el valor repite el nombre del operador
    (Van Valin escribe ⟨NEG …⟩, nunca ⟨NEG NEG …⟩)."""
    valor = (spec or {}).get("valor", "")
    return op if valor == op or not valor else f"{op} {valor}"


def envolver_ls(ls: str, ops: dict) -> str:
    """Aplica el anidamiento de 2.25 con ⟨ ⟩ sobre una EL ya construida.

        envolver_ls("do'(Kim, [cry'(Kim)])",
                    {'IF': …INT, 'TNS': …PRES, 'ASP': …'PERF PROG'})
        -> "⟨IF INT ⟨TNS PRES ⟨ASP PERF PROG ⟨do'(Kim, [cry'(Kim)])⟩⟩⟩⟩"

    Los operadores no especificados se omiten (no dejan hueco). Sin ningún
    operador la EL se devuelve TAL CUAL, sin envolver: la representación no
    gana un par de corchetes vacío de contenido.
    """
    capas = [op for op in ORDEN_SCOPE if op in (ops or {})]
    if not capas:
        return ls
    salida = f"{ABRE}{ls}{CIERRA}"
    for op in reversed(capas):
        salida = f"{ABRE}{etiqueta(op, ops[op])} {salida}{CIERRA}"
    return salida


def linea_operadores(ops: dict) -> str:
    """`IF=DEC · TNS=PAST · ASP=PERF PROG` — resumen legible de una línea."""
    if not ops:
        return ""
    return " · ".join(f"{op}={ops[op]['valor']}" for op in ORDEN_SCOPE if op in ops)
