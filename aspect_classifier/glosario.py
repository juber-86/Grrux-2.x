"""Fase L5 §4 — glosario de GRRux (comando -help / -ayuda).

El glosario vive en `data/glosario_grrux.csv` (columnas
`categoria,termino,definicion`) para que Julian lo edite sin tocar código.
Este módulo lo carga y ofrece:
  - el volcado COMPLETO agrupado por categorías (estilo ayuda de Linux),
  - la búsqueda TOLERANTE de un término (sin distinguir mayúsculas ni
    acentos, por coincidencia parcial): `-help agx` → AGX; `-help telico`
    → télico (tel); `-help peri` → todas las entradas que contienen "peri".

Módulo puro salvo la lectura del CSV (I/O de archivo explícito).
"""

import csv
import os
import unicodedata

_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "data", "glosario_grrux.csv")

ANUNCIO = ('escribe "-help" para mostrar el glosario completo o '
           '"-help término" para buscar un término específico')

# Las cuatro formas admitidas del comando (sin argumento = glosario completo).
_FORMAS_HELP = {"-help", "--help", "-ayuda", "--ayuda"}


def _normalizar(s: str) -> str:
    """minúsculas + sin acentos (NFD, descarta diacríticos)."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def cargar_glosario(path: str | None = None) -> list[dict]:
    ruta = path or _CSV
    with open(ruta, encoding="utf-8", newline="") as f:
        return [dict(fila) for fila in csv.DictReader(f)]


def es_comando_help(linea: str) -> tuple[bool, str | None]:
    """¿La línea es una invocación del glosario? Devuelve (True, término|None)
    -- término None = glosario completo. (False, None) si no es -help."""
    partes = (linea or "").strip().split(None, 1)
    if not partes or partes[0].lower() not in _FORMAS_HELP:
        return False, None
    arg = partes[1].strip() if len(partes) > 1 else None
    return True, (arg or None)


def buscar(termino: str, glosario: list[dict] | None = None) -> list[dict]:
    """Coincidencia parcial tolerante (sin acentos/mayúsculas) sobre el campo
    `termino`. Vacío si no hay ninguna coincidencia."""
    glosario = glosario if glosario is not None else cargar_glosario()
    q = _normalizar(termino)
    if not q:
        return []
    return [e for e in glosario if q in _normalizar(e["termino"])]


def bloques_glosario(glosario: list[dict] | None = None) -> list[str]:
    """El glosario completo formateado en BLOQUES, uno por categoría (para el
    paginado simple: el caller imprime bloque a bloque). Preserva el orden de
    aparición de las categorías en el CSV."""
    glosario = glosario if glosario is not None else cargar_glosario()
    orden: list[str] = []
    por_cat: dict[str, list[dict]] = {}
    for e in glosario:
        cat = e["categoria"]
        if cat not in por_cat:
            por_cat[cat] = []
            orden.append(cat)
        por_cat[cat].append(e)

    bloques = []
    for cat in orden:
        lineas = [cat, "─" * len(cat)]
        ancho = max((len(e["termino"]) for e in por_cat[cat]), default=0)
        for e in por_cat[cat]:
            lineas.append(f"  {e['termino'].ljust(ancho)}  {e['definicion']}")
        bloques.append("\n".join(lineas))
    return bloques


def formatear_entradas(entradas: list[dict]) -> str:
    """Formatea una lista de entradas (resultado de `buscar`) para imprimir."""
    ancho = max((len(e["termino"]) for e in entradas), default=0)
    return "\n".join(f"  {e['termino'].ljust(ancho)}  [{e['categoria']}]  "
                     f"{e['definicion']}" for e in entradas)


def respuesta_help(termino: str | None, glosario: list[dict] | None = None) -> str:
    """Texto ya listo para imprimir: glosario completo si `termino` es None,
    la(s) definición(es) si hay match, o el mensaje de redirección si no."""
    glosario = glosario if glosario is not None else cargar_glosario()
    if termino is None:
        return "\n\n".join(bloques_glosario(glosario))
    encontrados = buscar(termino, glosario)
    if encontrados:
        return formatear_entradas(encontrados)
    return (f'término «{termino}» no encontrado — escribe "-help" para ver el '
            "glosario completo")
