"""Contratos canónicos compartidos por terminal, servidor y GUI.

No contiene definiciones largas: las definiciones de tooltip siguen viviendo
en ``glosario_gruxx.csv``. Este módulo solo fija las claves estables que
pueden producir el convertidor y las rutas corregibles del análisis.
"""

NODE_GLOSSARY_KEYS = {
    "N": "sustantivo", "N-PROP": "sustantivo", "V": "verbo", "P": "preposición",
    "NUC": "NUC", "PRED": "PRED", "NP": "PP / NP / ADVP",
    "PP": "PP / NP / ADVP", "ADVP": "PP / NP / ADVP",
    "PrDP": "PrDP / LDP", "LDP": "PrDP / LDP", "PrCS": "PrCS",
    "AGX": "AGX", "CORE": "SENTENCE/CLAUSE/CORE/NUC",
    "CLAUSE": "SENTENCE/CLAUSE/CORE/NUC",
    "SENTENCE": "SENTENCE/CLAUSE/CORE/NUC",
}

# Cualquier X-PERI se resuelve a la definición de su estrato/ancla, no a la
# etiqueta léxica X. Los estratos activos de nucleo_periferia están cerrados.
PERI_GLOSSARY_KEYS = {
    "NUC": "PERI@NUC", "CORE": "PERI@CORE", "CLAUSE": "PERI@CLAUSE",
}

PERIPHERY_TYPES = (
    "temporal", "locativo", "manera", "aspectual", "frecuencia",
    "razon", "concesion", "condicion", "epistemico", "generico",
)

ROUTING_INVENTORY = (
    {"clave": "argumento_core", "etiqueta": "argumento del CORE",
     "estrato": "core", "subtipo": "argumento", "automatizacion": "automatizable"},
    {"clave": "nuc_predicado", "etiqueta": "núcleo/predicado (NUC/PRED)",
     "estrato": "nucleo", "subtipo": "predicado", "automatizacion": "solo_staging"},
    {"clave": "agx", "etiqueta": "clítico/índice de concordancia (AGX)",
     "estrato": "core", "subtipo": "concordancia", "automatizacion": "solo_staging"},
    *({"clave": f"peri_{estrato}_{tipo}",
       "etiqueta": f"periferia {tipo} @ {estrato.upper()}",
       "estrato": estrato, "subtipo": tipo, "automatizacion": "solo_staging"}
      for estrato in ("nucleo", "core", "clause")
      for tipo in PERIPHERY_TYPES),
    {"clave": "prdp_ldp", "etiqueta": "posición destacada (PrDP/LDP)",
     "estrato": "clause", "subtipo": "posición destacada", "automatizacion": "solo_staging"},
    {"clave": "prcs", "etiqueta": "posición precentral (PrCS; solo staging)",
     "estrato": "clause", "subtipo": "posición precentral", "automatizacion": "solo_staging"},
)

ROUTING_BY_KEY = {item["clave"]: item for item in ROUTING_INVENTORY}


def ruta_periferia(estrato: str | None, tipo: str | None) -> str:
    tipo_norm = (tipo or "generico").lower()
    if tipo_norm not in PERIPHERY_TYPES:
        tipo_norm = "generico"
    return f"peri_{(estrato or 'core').lower()}_{tipo_norm}"


def inventario_enrutado(ls: dict) -> list[dict]:
    """Devuelve siempre el inventario completo, con instancias presentes."""
    presentes = {item["clave"]: [] for item in ROUTING_INVENTORY}
    for c in ls.get("core") or []:
        presentes["argumento_core"].append(_instancia(c))
    if ls.get("root_id") is not None:
        presentes["nuc_predicado"].append({"elemento_id": ls["root_id"],
                                            "texto": ls.get("verb_lemma", "")})
    for a in ls.get("agx") or []:
        presentes["agx"].append({"elemento_id": a.get("clitico_id"),
                                  "texto": a.get("clitico", "")})
    for p in ls.get("periferia") or []:
        key = ruta_periferia(p.get("estrato"), p.get("tipo"))
        if key in presentes:
            presentes[key].append(_instancia(p, extra={"estrato": p.get("estrato")}))
        if p.get("destacado_inicial") and key in presentes:
            presentes["prdp_ldp"].append(_instancia(p))
    salida = []
    for item in ROUTING_INVENTORY:
        salida.append({**item, "instancias": presentes[item["clave"]],
                       "ausente": not presentes[item["clave"]]})
    return salida


def _instancia(item: dict, extra: dict | None = None) -> dict:
    out = {"elemento_id": item.get("id"), "texto": item.get("text", ""),
           "ruta_origen": item.get("ruta_origen")}
    if extra:
        out.update(extra)
    return out
