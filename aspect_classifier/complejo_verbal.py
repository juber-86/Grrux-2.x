"""Extracción del complejo verbal desde el árbol de dependencias UD.

Complejo verbal = verbo raíz + clíticos pronominales dependientes
(expl, expl:pv, …) + núcleo del objeto directo (y opcionalmente su
determinante). La Fase 2 lo usa para poolear el embedding sobre el
predicado completo ("se comió … pizza") y no solo sobre el token del
verbo. El complejo puede ser DISCONTIGUO: los spans devueltos saltan
los tokens intermedios no incluidos (p. ej. el determinante).

Función pura: no depende de torch, transformers ni Stanza, para que sea
testeable en frío y reutilizable tal cual al reentrenar con contexto.
"""

DEFAULT_CLITIC_DEPRELS = ["expl", "expl:pv", "expl:pass", "expl:impers"]
# Deprels que cuentan como "objeto directo" para el núcleo del complejo.
# Verificado con Stanza/AnCora: las frases de medida ("cinco kilómetros")
# parsean como obj, así que obl NO se incluye por defecto (arrastraría
# adjuntos como "con la cabeza" o "de todo").
DEFAULT_OD_LIKE_DEPRELS = ["obj"]


def desde_stanza(words) -> list[dict]:
    """Convierte una lista de stanza.Word al formato de tokens de este módulo.

    `feats` (rasgos morfológicos UD, p. ej. "Number=Sing|Person=1") lo usa
    nucleo_periferia para recuperar el actor implícito en pro-drop; los
    consumidores que no lo necesitan lo ignoran.
    """
    return [
        {
            "id": w.id,
            "text": w.text,
            "lemma": w.lemma,
            "upos": w.upos,
            "deprel": w.deprel,
            "head": w.head,
            "feats": w.feats or "",
        }
        for w in words
    ]


def extraer_complejo(tokens: list[dict], root_id: int, cfg: dict) -> dict:
    """Selecciona los tokens del complejo verbal y sus char-spans.

    Args:
        tokens: lista de dicts con claves id, text, lemma, upos, deprel, head
                (ids 1-based como en CoNLL-U; head=0 para la raíz).
        root_id: id del verbo raíz.
        cfg: sección `fase2` de config.yaml; se leen `clitic_deprels`,
             `incluir_od_nucleo` e `incluir_od_det`.

    Returns:
        {"texto":     oración completa (' '.join de todos los tokens),
         "spans":     [(ini, fin), ...] offsets de carácter sobre "texto",
                      uno por token incluido, en orden lineal,
         "incluidos": [ids ordenados de los tokens del complejo]}

    "texto" es la única fuente de verdad para los offsets: pásese ese mismo
    string como `oracion` a AspectClassifier.predict para que no haya deriva.
    """
    clitic_deprels = set(cfg.get("clitic_deprels", DEFAULT_CLITIC_DEPRELS))
    od_like_deprels = set(cfg.get("od_like_deprels", DEFAULT_OD_LIKE_DEPRELS))
    incluir_od_nucleo = cfg.get("incluir_od_nucleo", True)
    incluir_od_det = cfg.get("incluir_od_det", False)

    incluidos = {root_id}

    od_id = None
    for t in tokens:
        if t["head"] == root_id and t["deprel"] in clitic_deprels:
            incluidos.add(t["id"])
        if (incluir_od_nucleo and od_id is None
                and t["head"] == root_id and t["deprel"] in od_like_deprels):
            od_id = t["id"]
            incluidos.add(od_id)

    if incluir_od_det and od_id is not None:
        for t in tokens:
            if t["head"] == od_id and t["deprel"] == "det":
                incluidos.add(t["id"])

    # Offsets sobre el texto reconstruido (tokens separados por un espacio)
    texto = " ".join(t["text"] for t in tokens)
    spans = []
    pos = 0
    for t in tokens:
        if t["id"] in incluidos:
            spans.append((pos, pos + len(t["text"])))
        pos += len(t["text"]) + 1

    return {"texto": texto, "spans": spans, "incluidos": sorted(incluidos)}
