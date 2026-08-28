"""
grrux_motor.py
==============
Fase GUI, Etapa G0 — el pipeline de análisis GRR como API interna
(`cargar()`/`analizar()`/`estado()`), para que una futura interfaz gráfica
(G1) lo consuma sin pasar por la terminal.

PROHIBIDO tocar el motor (`rrg_ls_mapper.py`, `nucleo_periferia.py`,
`completeness.py`, `misc_rrg.py`, `ud2rrg.py`, `convertir.py`, etc.) — este
módulo es SOLO orquestación, reutiliza `grrux_ai1.py` tal cual (mismas
funciones que ya usa la CLI, cero cambios en ese archivo) con dos
diferencias respecto al modo interactivo:

  1. Cada llamada usa su PROPIO `.conllu` temporal (`tempfile`, borrado al
     terminar) — nunca pisa `input_estudiante.conllu` (eso sigue siendo de
     la CLI).
  2. No se invoca el subprocess `convertir.py` (el ASCII no se necesita en
     pantalla): el árbol es el mismo objeto in-process
     (`grrux_ai1._arboles_inprocess`) que ya alimenta a `completeness`,
     serializado a JSON por `serializar_arbol` (ver G0.2).

Contrato de `analizar()` — ver prompt_GUI_G0_G1.md §G0.3 (checkpoint G0).

Nada de esto se importa a nivel de módulo con coste real: `cargar()` es la
única función que construye el pipeline Stanza (pesado); importar
`grrux_motor` es barato.
"""

import os
import math
import tempfile
import uuid
from collections import OrderedDict

from aspect_classifier import display_grr
from aspect_classifier.completeness import verificar
from aspect_classifier.gui_contract import inventario_enrutado

LANG = "es"

_nlp = None


# ---------------------------------------------------------------------------
# G0.1 — carga / estado
# ---------------------------------------------------------------------------
def cargar() -> None:
    """Idempotente: construye el pipeline Stanza residente. Importar
    `rrg_ls_mapper` (vía `grrux_ai1`, más abajo) ya deja cargado el
    clasificador aspect_classifier — igual que hace la CLI."""
    global _nlp
    if _nlp is not None:
        return
    import grrux_ai1  # noqa: F401 — módulo importable sin coste (no construye Stanza)
    _nlp = grrux_ai1.cargar_pipeline_stanza(LANG)


def estado() -> dict:
    return {"listo": _nlp is not None}


# ---------------------------------------------------------------------------
# G0.2 — serialización del árbol RRG a JSON
# ---------------------------------------------------------------------------
def serializar_arbol(nodo):
    """`ParentedTree` -> dict anidado JSON-able. Las hojas de
    `ud2rrg.preterminal` son ÍNDICES 0-based de posición del token
    (`token_id - 1`), NUNCA texto (ver nota en `completeness.py`) — aquí se
    conserva ese índice tal cual; el frontend lo resuelve contra `tokens`.
    Función pura (testeable en frío con árboles sintéticos).

    Fase GUI, G2 §0.1 (fix, veredicto de Julian): `ud2rrg.transform` añade
    hijos en orden de PROCESAMIENTO, no de superficie ("Juan come pizza"
    salía "come pizza Juan"; "la película" salía "película la") — el render
    ASCII no lo sufre porque `DrawTree` coloca por índice de hoja, pero el
    frontend dibuja el array tal cual. Se reordenan los `hijos` de cada
    nodo RECURSIVAMENTE por la hoja MÍNIMA de su subárbol — el árbol queda
    en el mismo orden lineal de la oración (regla de Julian: el predicado
    cae donde le toca en la oración, sin centrado artificial), sin alterar
    la estructura (mismos padres/hijos, solo el orden de dibujo)."""
    return _serializar_ordenado(nodo)[0]


def _serializar_ordenado(nodo):
    if isinstance(nodo, int):
        return {"token": nodo}, nodo
    label = nodo.label if isinstance(nodo.label, str) else str(nodo.label)
    hijos_con_min = sorted((_serializar_ordenado(hijo) for hijo in nodo),
                          key=lambda par: par[1])
    min_propio = min((m for _, m in hijos_con_min), default=0)
    return {"label": label, "hijos": [h for h, _ in hijos_con_min]}, min_propio


# ---------------------------------------------------------------------------
# G0.3 — construcción del contrato por (sub)oración
# ---------------------------------------------------------------------------
def _tokens_de(sentence) -> list[dict]:
    return [{"id": int(w.id), "texto": w.text, "lema": w.lemma}
            for w in sentence.words]


def _argumentos_de(ls: dict) -> list[dict]:
    from aspect_classifier.rrg_variables import (canonical_variables,
                                                 validate_mapping_values)
    variables = ls.get("variables") or {}
    id_a_var = ls.get("id_a_var") or {}
    variables = canonical_variables(variables)
    validate_mapping_values(id_a_var, field="id_a_var")
    var_a_id = {v: k for k, v in id_a_var.items()}
    core_por_id = {c["id"]: c for c in (ls.get("core") or [])}
    roles_tematicos = ls.get("roles_tematicos") or {}
    actor_implicito = ls.get("actor_implicito")

    argumentos = []
    for var, texto in variables.items():
        tid = var_a_id.get(var)
        entry = core_por_id.get(tid) if tid is not None else None
        deprel = entry.get("deprel") if entry else None
        papel = (roles_tematicos.get(tid) if tid is not None else None) \
            or (entry.get("macropapel") if entry else None)
        if papel is None and actor_implicito and texto == actor_implicito.get("etiqueta"):
            papel = "Actor(implícito)"
        if papel is None and texto == "Ø":
            papel = "actor inespecificado (se)"
        argumentos.append({"var": var, "token_id": tid, "texto": texto,
                           "deprel": deprel, "papel": papel})
    return argumentos


def _periferia_de(ls: dict) -> list[dict]:
    wrappers = ls.get("wrappers") or []
    wrap_por_id = {w["id"]: w for w in wrappers if w.get("id") is not None}
    salida = []
    for p in (ls.get("periferia") or []):
        wrap = wrap_por_id.get(p["id"])
        aplicado = wrap is not None and wrap.get("aplicado")
        salida.append({"id": p["id"], "texto": p.get("text", ""),
                       "tipo": p.get("tipo"), "estrato": p.get("estrato"),
                       "wrap": wrap.get("pred") if aplicado else None})
    return salida


def _agx_de(ls: dict) -> list[dict]:
    return [{"clitico": e.get("clitico"), "fuente": e.get("fuente"),
             "doblado": bool(e.get("doblado")), "token_id": e.get("clitico_id")}
            for e in (ls.get("agx") or [])]


def _rasgos_de(ls: dict) -> dict | None:
    vec = ls.get("vector")
    if not vec:
        return None
    return {"estatico": vec.get("stat"), "dinamico": vec.get("dyn"),
            "telico": vec.get("tel"), "puntual": vec.get("pun"),
            "confianza": _normalizar_confianza(ls.get("confianza")),
            "metodo": ls.get("metodo")}


def _normalizar_confianza(valor) -> float | None:
    """Contrato GUI LA2.1: número finito 0..1 o ``None``.

    Acepta números y cadenas numéricas heredadas en el límite del motor,
    pero rechaza booleanos, etiquetas cualitativas, NaN e infinitos.
    """
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) and 0.0 <= numero <= 1.0 else None


def _causatividad_de(ls: dict) -> dict | None:
    if not ls.get("causativo"):
        return None
    confianza_cruda = ls.get("causativo_confianza")
    return {"tipo": ls.get("causativo_tipo"), "fuente": ls.get("causativo_source"),
            "confianza": _normalizar_confianza(confianza_cruda),
            "nivel_confianza": (confianza_cruda if isinstance(confianza_cruda, str)
                                and confianza_cruda in {"alta", "media", "baja"} else None),
            "clase_base": ls.get("ls_type"),
            "clase_derivada": ls.get("causativo_clase_derivada")}


def _actor_implicito_de(ls: dict) -> dict | None:
    actor = ls.get("actor_implicito")
    if not actor:
        return None
    return {"etiqueta": actor.get("etiqueta")}


def _operadores_de(ls: dict) -> list[dict]:
    """Etapa OPERATORS — los operadores de la (sub)oración, ya en ORDEN DE
    SCOPE (de fuera hacia dentro, 2.25). Se devuelve una LISTA y no el dict
    crudo del mapper para que el orden viaje garantizado por el JSON: la
    proyección espejo de la GUI lo dibuja de arriba abajo tal cual.

    Cada entrada trae `op`, `valor`, `estrato` y `origen` — el origen alimenta
    los tooltips ("de 'corrió', pretérito") y es lo que consumirá la
    corrección de operadores (TODO-OPERATORS-2). Lista vacía si la etapa está
    apagada: la GUI simplemente no dibuja la proyección."""
    ops = ls.get("operadores") or {}
    return [{"op": op, "valor": spec.get("valor", ""),
             "estrato": spec.get("estrato", ""), "origen": spec.get("origen", "")}
            for op, spec in ops.items()]


def _linking_de(ls: dict, comp: dict | None) -> dict | None:
    """Fase LINKING, Etapa LA1 — línea compacta + traza de 5 pasos +
    macropapeles/PSA, para el panel "Linking" de la GUI. `None` si la
    etapa está apagada o esta rama no calculó linking (la GUI simplemente
    no dibuja el panel, igual que con `causatividad`)."""
    info = ls.get("linking")
    if not info:
        return None
    macropapeles = info.get("macropapeles") or {}
    return {
        "linea": display_grr.linea_linking(ls),
        "traza": display_grr.traza_linking(ls, comp),
        "macropapeles": {
            "actor": macropapeles.get("actor"),
            "undergoer": macropapeles.get("undergoer"),
            "nmr": macropapeles.get("nmr", []),
            "m_transitividad": macropapeles.get("m_transitividad", 0),
        },
        "psa": info.get("psa"),
        "voz": info.get("voz"),
    }


def _integridad_de(comp: dict | None) -> dict:
    if comp is None:
        return {"ok": None, "checks": [], "linea": display_grr.linea_integridad(None)}
    return {"ok": comp.get("ok"), "checks": comp.get("checks") or [],
            "linea": display_grr.linea_integridad(comp)}


def construir_sub_oracion(tokens: list[dict], arbol, ls: dict, comp: dict | None) -> dict:
    """Función pura — arma el dict de una (sub)oración del contrato G0.3 a
    partir de: tokens ya resueltos, el árbol RRG (`ParentedTree` o None), el
    `ls` de `rrg_ls_mapper.map_sentence_to_ls` y el resultado de
    `completeness.verificar` (o None)."""
    return {
        "tokens": tokens,
        "arbol": serializar_arbol(arbol) if arbol is not None else None,
        # `formal`/`lexical` siguen siendo la EL CRUDA (sin ⟨ ⟩): el panel de
        # EL muestra las envueltas (`*_ops`), pero el resaltado de variables y
        # el bucle de corrección siguen operando sobre la cruda, que no cambió.
        "el": {"tipo": ls.get("ls_type"),
               "tipo_legible": display_grr.clase_visible(ls),
               "formal": ls.get("ls_formal", ""), "lexical": ls.get("ls_lexical", ""),
               "formal_ops": display_grr.el_formal(ls),
               "lexical_ops": display_grr.el_lexica(ls)},
        "operadores": _operadores_de(ls),
        "ditransitiva": ls.get("ditransitiva"),
        "linking": _linking_de(ls, comp),
        "argumentos": _argumentos_de(ls),
        "rasgos": _rasgos_de(ls),
        # AVISOS (2026-08-19): los `diagnosticos_analisis` del mapper viajan
        # por el canal `notas` ya existente — sin clave nueva en el contrato
        # G0.3, así que la GUI los pinta en el panel de notas sin tocar el
        # frontend. Lista vacía en un análisis sano: salida sin cambios.
        "notas": (display_grr.traducir_apendices(ls.get("morph_note", ""))
                  + display_grr.avisos(ls)),
        "causatividad": _causatividad_de(ls),
        "integridad": _integridad_de(comp),
        "periferia": _periferia_de(ls),
        "agx": _agx_de(ls),
        "inventario_enrutado": inventario_enrutado(ls),
        "actor_implicito": _actor_implicito_de(ls),
        "impersonal": bool(ls.get("impersonal")),
        "crudo": {"morph_note": ls.get("morph_note", ""),
                  "resumen_completeness": (comp or {}).get("resumen", "")},
    }


# ---------------------------------------------------------------------------
# G2 §1 — cache de análisis crudo (insumo de correccion.corregir_*)
# ---------------------------------------------------------------------------
# Los `corregir_*` de `aspect_classifier.correccion` consumen el `res` CRUDO
# del mapper (`{"oracion": str, "ls_lista": [...]}`), que nunca viaja al
# navegador (el contrato G0.3 ya lo traduce a `sub_oraciones`). Se cachean
# los últimos `_CACHE_MAX` análisis en memoria bajo un `analisis_id` corto;
# `analizar()` deja su id en el contrato para que la GUI lo reenvíe al
# corregir. G3 §3: subido de 20 a 100 para que el modo lote (una tanda de
# oraciones analizadas en un solo lote) quepa sin expulsar entradas que el
# usuario todavía quiere abrir/corregir -- cada entrada es texto+ParentedTree
# pequeños (nunca Stanza/roBERTa), coste extra de memoria modesto.
_CACHE_MAX = 100
_cache_crudo: "OrderedDict[str, dict]" = OrderedDict()


def _cachear_crudo(crudo: dict) -> str:
    analisis_id = uuid.uuid4().hex[:8]
    _cache_crudo[analisis_id] = crudo
    while len(_cache_crudo) > _CACHE_MAX:
        _cache_crudo.popitem(last=False)   # el más viejo (FIFO)
    return analisis_id


def obtener_crudo(analisis_id: str) -> dict | None:
    """`None` si el id es desconocido o ya salió del cache (expiró) — el
    caller (servidor) lo traduce a 404 con mensaje claro, nunca traceback."""
    return _cache_crudo.get(analisis_id)


# ---------------------------------------------------------------------------
# pipeline compartido — Stanza → mapper → árboles in-process
# ---------------------------------------------------------------------------
def _pipeline_crudo(oracion: str):
    """Corre el pipeline completo (idéntico al de `grrux_ai1.procesar_oracion`,
    salvo el `.conllu` temporal por llamada y sin subprocess `convertir.py`,
    ver docstring del módulo) y devuelve `(ls_lista, arboles, doc)` SIN
    construir el contrato G0.3 — lo reutilizan tanto `analizar()` (contrato
    completo) como `analizar_crudo()` (insumo de `correccion.corregir_*`,
    que no necesita árboles ni tokens)."""
    import grrux_ai1
    from stanza.utils.conll import CoNLL
    from rrg_ls_mapper import map_sentence_to_ls

    fd, tmp_path = tempfile.mkstemp(suffix=".conllu", prefix="grrux_gui_")
    os.close(fd)
    try:
        doc = _nlp(oracion)
        open(tmp_path, "w", encoding="utf-8").close()
        CoNLL.write_doc2conll(doc, tmp_path)
        grrux_ai1.limpiar_conllu_stanza(tmp_path)
        ls_lista = [map_sentence_to_ls(sent) for sent in doc.sentences]
        grrux_ai1.inyectar_metadata_rrg(tmp_path, doc, ls_lista)

        # G3 §4.4 — se lee el .conllu YA enriquecido (MISC con los rrg_*)
        # antes de que el `finally` lo borre: es el insumo de
        # `/exportar/conllu` (nunca se re-corre Stanza para regenerarlo).
        with open(tmp_path, encoding="utf-8") as f:
            conllu_texto = f.read()

        try:
            arboles = grrux_ai1._arboles_inprocess(tmp_path, LANG)
        except Exception:
            arboles = []
        return ls_lista, arboles, doc, conllu_texto
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def analizar_crudo(oracion: str) -> dict:
    """`{"oracion": str, "ls_lista": [...]}` — la forma que esperan
    `correccion.corregir_*` (como `reanalizar_fn`, igual que la CLI usa
    `lambda o: procesar_oracion(nlp, o)`). Puede lanzar: los callers en
    `correccion.py` ya envuelven `reanalizar_fn` en try/except (una
    corrección que no confirma cae a staging, nunca rompe la petición)."""
    if _nlp is None:
        cargar()
    ls_lista, _arboles, _doc, _conllu = _pipeline_crudo(oracion)
    return {"oracion": oracion, "ls_lista": ls_lista}


# ---------------------------------------------------------------------------
# analizar() — pipeline completo, motor como API
# ---------------------------------------------------------------------------
def analizar(oracion: str) -> dict:
    """Contrato G0.3 + `analisis_id` (G2 §1). Nunca lanza: cualquier fallo
    del pipeline se reporta en `error` (nunca 500/traceback en la
    respuesta)."""
    if _nlp is None:
        cargar()

    try:
        ls_lista, arboles, doc, conllu_texto = _pipeline_crudo(oracion)
    except Exception as e:
        return {"oracion": oracion, "sub_oraciones": [], "error": str(e),
                "analisis_id": None}

    sub_oraciones = []
    tokens_por_sub = []
    for i, ls in enumerate(ls_lista):
        tokens = _tokens_de(doc.sentences[i])
        tokens_por_sub.append(tokens)
        arbol = arboles[i] if i < len(arboles) else None
        comp = verificar(ls, arbol)
        sub_oraciones.append(construir_sub_oracion(tokens, arbol, ls, comp))

    # G3 §1/§4 — además de `ls_lista` (lo único que necesitaban los
    # `corregir_*`), se cachea lo necesario para derivar `verb_lemma` sin
    # re-analizar (`lema_raiz`) y para las exportaciones .txt/.conllu
    # (`render_txt_grr`, `conllu_texto`): nada de esto re-corre Stanza.
    analisis_id = _cachear_crudo({"oracion": oracion, "ls_lista": ls_lista,
                                  "tokens_por_sub": tokens_por_sub, "arboles": arboles,
                                  "conllu_texto": conllu_texto})
    return {"oracion": oracion, "sub_oraciones": sub_oraciones, "error": None,
            "analisis_id": analisis_id}


# ---------------------------------------------------------------------------
# G3 §1 — lema del token raíz (insumo de `verb_lemma` en `correccion.corregir_*`)
# ---------------------------------------------------------------------------
def lema_raiz(crudo: dict, sub_idx: int) -> str | None:
    """`root_id` de la ls cruda (ya lo expone `rrg_ls_mapper.map_sentence_to_ls`)
    + el token de ESE id en `tokens_por_sub` (cacheado en `analizar()`) → su
    lema. Función PURA sobre el dict cacheado: nunca re-corre Stanza. `None`
    si `crudo` no trae `root_id`/`tokens_por_sub` (p.ej. un motor stub de
    test) — el caller (server) cae entonces al fallback `_lema_de` de
    `correccion.py`, exactamente como antes de G3."""
    ls_lista = crudo.get("ls_lista") or []
    ls = ls_lista[sub_idx] if 0 <= sub_idx < len(ls_lista) else {}
    root_id = ls.get("root_id")
    if root_id is None:
        return None
    tokens_por_sub = crudo.get("tokens_por_sub") or []
    tokens = tokens_por_sub[sub_idx] if 0 <= sub_idx < len(tokens_por_sub) else []
    tok = next((t for t in tokens if t.get("id") == root_id), None)
    return tok.get("lema") if tok else None


# ---------------------------------------------------------------------------
# G3 §4.3 — export .txt con el MISMO formato GRR que la terminal
# ---------------------------------------------------------------------------
def render_txt_grr(crudo: dict) -> str:
    """Reusa `display_grr.render_bloque` (mismo orden que `grrux_ai1`: árbol
    → EL léxica → resto) y, para el ASCII del árbol, `DrawTree` de discodop
    IN-PROCESS — como hace `convertir.py`, sin subprocess. `crudo` es el dict
    cacheado por `analizar()`; si `arboles`/`tokens_por_sub` faltan (p.ej.
    un motor stub de test) cada bloque cae a "sin árbol" en vez de lanzar."""
    from discodop.tree import DrawTree

    ls_lista = crudo.get("ls_lista") or []
    arboles = crudo.get("arboles") or []
    tokens_por_sub = crudo.get("tokens_por_sub") or []
    multi = len(ls_lista) > 1
    bloques = []
    for i, ls in enumerate(ls_lista):
        arbol = arboles[i] if i < len(arboles) else None
        tokens = tokens_por_sub[i] if i < len(tokens_por_sub) else []
        comp = verificar(ls, arbol) if arbol is not None else None
        arbol_texto = None
        if arbol is not None and tokens:
            try:
                sent = [t["texto"].replace(" ", "_") for t in tokens]
                arbol_texto = str(DrawTree(arbol, sent))
            except Exception:
                arbol_texto = None
        prefijo = f"  — Sub-oración {i + 1} —\n\n" if multi else ""
        bloques.append(prefijo + display_grr.render_bloque(ls, arbol_texto, comp))

    encabezado = f"ORACIÓN: {crudo.get('oracion', '')}\n{'=' * 60}\n\n"
    return encabezado + "\n\n".join(bloques) + "\n"
