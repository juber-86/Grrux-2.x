"""L0 — Baseline cuantificado de la fase de linking sintaxis↔semántica.

Mide, sobre un treebank gold (`.conllu` DIRECTO, sin Stanza — así se aísla
el conversor del parser):

  1. Tasa de fallos de ud2rrg (vía el mismo subprocess que usa
     `grrux_ai1.correr_ud2rrg`: `convertir.py <conllu> es`).
  2. Tasa de desacuerdo de periferia entre `analizar_roles` (Etapa 1) y el
     árbol RRG que produce ud2rrg.
  3. Contadores: doblado de clítico dativo, `obl:arg` totales, periferia por
     tipo.

No toca código de producción: solo LEE `aspect_classifier.nucleo_periferia`
y ejecuta `convertir.py`/`ud2rrg` tal cual están.

Ejecutar:
    python -m aspect_classifier.kpi_linking [--n 300] [--treebank ancora-dev]

──────────────────────────────────────────────────────────────────────────
HALLAZGO CLAVE (documentado aquí porque el propio script lo mide dos veces):
`grrux_ai1.limpiar_conllu_stanza` pone la columna XPOS en `_` para cada
token ANTES de invocar ud2rrg. Esto NO es cosmético: prácticamente todas
las funciones `is_*` de ud2rrg.py (is_verb, is_noun, is_adjective...)
consultan XPOS con listas/prefijos en MAYÚSCULA (tags estilo Penn/STTS de
en/de: "VBZ", "NNP"...) y SOLO caen al fallback por UPOS si XPOS está vacío.
AnCora/Freeling-EAGLES usa XPOS en minúscula ("vmis3s0", "ncms000"...), que
nunca matchea. Resultado: alimentar ud2rrg con un `.conllu` gold estándar
(XPOS intacto, como pide esta metodología L0 "sin Stanza") lo hace fallar
en el dispatch de nivel superior en ~100% de las oraciones — no por falta
de reglas para deprels españoles, sino por un mismatch de mayúsculas en el
tagset. El pipeline real de `grrux_ai1.py` evita el bug por el efecto
colateral (no documentado como tal) de `limpiar_conllu_stanza`. Por eso
este script mide AMBAS variantes: "xpos_intacto" (metodología L0 literal,
aísla el conversor tal cual lo vería cualquier `.conllu` externo) y
"xpos_stripped_pipeline_real" (replica el pre-procesamiento real de
grrux_ai1 — es la cifra comparable con lo que Julian usa día a día, y la
que debería trackearse en L4 tras el fix de L3).
──────────────────────────────────────────────────────────────────────────
FASE LINKING, ETAPA L4 — `kpi4_pipeline_hibrido` (más abajo) es la medición
HONESTA del acuerdo de periferia y la tasa de completeness: a diferencia de
KPI2 (que corre `ud2rrg.transform` sobre el gold SIN inyectar MISC — el
anclaje por estrato de L3 es 100% MISC-gated, así que KPI2 nunca lo
ejercita), KPI4 corre el pipeline REAL por oración: Etapa 1 + el mapper
completo (`rrg_ls_mapper.map_sentence_to_ls`, CON el clasificador aspectual
roBERTa) sobre un objeto "sentence" sintético que envuelve los tokens GOLD
(sintaxis gold real, no re-parseada con Stanza — "híbrido": gold syntax +
clasificación semántica real), inyecta el MISC resultante vía
`aspect_classifier.misc_rrg`, y SOLO ENTONCES convierte con `ud2rrg`.

⚠️  ADVERTENCIA OOM (heredada de CHECKPOINT_L3.md): `kpi4_pipeline_hibrido`
carga el clasificador aspectual roBERTa completo (aspect_classifier,
BERTIN) para cada oración de la muestra. NO correr esta función (ni
`main()`, que la incluye) con una instancia interactiva de `grrux_ai1.py`
abierta, ni con las suites `--slow` corriendo en paralelo — máquina de
12 GB; dos copias de Stanza+BERTIN + navegador la agotan.
──────────────────────────────────────────────────────────────────────────
"""

import argparse
import io
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import date, datetime
from types import SimpleNamespace

from conllu import parse_incr, parse_tree_incr

from .nucleo_periferia import analizar_roles

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONVERTIR_PY = os.path.join(REPO_ROOT, "convertir.py")
LANG = "es"

TREEBANKS = {
    "ancora-dev": "treebanks/spanish/UD_Spanish-AnCora/es_ancora-ud-dev.conllu",
    "ancora-train": "treebanks/spanish/UD_Spanish-AnCora/es_ancora-ud-train.conllu",
    "ancora-test": "treebanks/spanish/UD_Spanish-AnCora/es_ancora-ud-test.conllu",
    "gsd-dev": "treebanks/spanish/UD_Spanish-GSD/es_gsd-ud-dev.conllu",
    "pud-test": "treebanks/spanish/UD_Spanish-PUD/es_pud-ud-test.conllu",
}

# Examen final de la fase (L4 §4.2): PUD tiene convenciones de anotación
# distintas de AnCora -- números más bajos son esperables ahí. Correrlo UNA
# SOLA VEZ al final, con todo ya validado contra ancora-dev; PROHIBIDO
# iterar o ajustar nada mirando sus resultados.
DEFAULT_OUT_POR_TREEBANK = {
    "ancora-dev": "kpi_linking_post_l4.json",
    "pud-test": "kpi_pud_final.json",
}

DATIVOS_CLITICOS = {"le", "les"}


# ---------------------------------------------------------------------------
# Lectura del gold .conllu
# ---------------------------------------------------------------------------
def _feats_to_str(feats: dict | None) -> str:
    if not feats:
        return ""
    return "|".join(f"{k}={v}" for k, v in feats.items())


def leer_bloques(path: str, n: int) -> list[str]:
    """Primeros n bloques (oraciones) del .conllu, tal cual (blank-line split)."""
    contenido = open(path, encoding="utf-8").read().strip()
    bloques = [b for b in contenido.split("\n\n") if b.strip()]
    return bloques[:n]


def bloque_a_tokens(bloque: str) -> list[dict]:
    """Bloque CoNLL-U → lista de tokens en el formato de analizar_roles
    (id, text, lemma, upos, deprel, head, feats); descarta líneas de rango
    multiword (id tipo '13-14', sin deprel/head propios)."""
    toks = []
    for tl in parse_incr(io.StringIO(bloque)):
        for tok in tl:
            if not isinstance(tok["id"], int):
                continue   # rango multiword: sin deprel/head propios
            toks.append({
                "id": tok["id"], "text": tok["form"], "lemma": tok["lemma"] or "",
                "upos": tok["upos"], "deprel": tok["deprel"], "head": tok["head"],
                "feats": _feats_to_str(tok["feats"]),
            })
        break   # un solo bloque = una sola oración
    return toks


def root_id_de(tokens: list[dict]) -> int | None:
    return next((t["id"] for t in tokens if t["deprel"] == "root"), None)


# ---------------------------------------------------------------------------
# KPI 1 — tasa de fallos de ud2rrg (subprocess, mismo path que grrux_ai1)
# ---------------------------------------------------------------------------
def _xpos_stripped(bloque: str) -> str:
    """Replica el efecto de grrux_ai1.limpiar_conllu_stanza: xpos → '_'."""
    lineas = []
    for linea in bloque.split("\n"):
        if linea.startswith("#") or not linea.strip():
            lineas.append(linea)
            continue
        cols = linea.split("\t")
        if len(cols) == 10:
            cols[4] = "_"
        lineas.append("\t".join(cols))
    return "\n".join(lineas)


def correr_convertir(bloques: list[str], tmp_path: str) -> dict:
    """Escribe los bloques a tmp_path y corre convertir.py (subprocess),
    igual que grrux_ai1.correr_ud2rrg. Devuelve conteos parseados de stdout."""
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(bloques) + "\n\n")
    proc = subprocess.run([sys.executable, CONVERTIR_PY, tmp_path, LANG],
                          capture_output=True, text=True, cwd=REPO_ROOT)
    ok = len([l for l in proc.stdout.splitlines() if l.startswith("--- Oración")])
    fail = len([l for l in proc.stdout.splitlines() if l.startswith("ERROR en oración")])
    resumen = next((l for l in proc.stdout.splitlines() if l.startswith("Convertidas:")), "")
    return {"ok": ok, "fail": fail, "total": ok + fail, "resumen_linea": resumen}


def kpi1_tasa_fallos(bloques: list[str]) -> dict:
    scratch = "/tmp/claude-1000/-home-jbj86-proyectos-ud2rrg/d2278051-b48c-491a-b2de-6a17fe91e7b2/scratchpad"
    os.makedirs(scratch, exist_ok=True)

    xpos_intacto = correr_convertir(bloques, os.path.join(scratch, "kpi_xpos_intacto.conllu"))
    xpos_stripped = correr_convertir([_xpos_stripped(b) for b in bloques],
                                     os.path.join(scratch, "kpi_xpos_stripped.conllu"))

    def pct(d):
        t = d["total"] or 1
        return {"pct_ok": round(100 * d["ok"] / t, 1),
               "pct_fail": round(100 * d["fail"] / t, 1), **d}

    return {
        "xpos_intacto_metodologia_L0": pct(xpos_intacto),
        "xpos_stripped_pipeline_real": pct(xpos_stripped),
        "nota": ("No se observó categoría 'dummy tree/plano' en el path real "
                "(convertir.py): NotHandled se propaga sin captura local hasta "
                "el except de nivel oración; la oración se pierde entera (hard "
                "fail), no se sustituye por un árbol plano. La spec técnica "
                "describe ese fallback pero no se materializa en este pipeline."),
    }


# ---------------------------------------------------------------------------
# KPI 2 — desacuerdo de periferia (Etapa 1 vs árbol ud2rrg, in-process)
# ---------------------------------------------------------------------------
def _ids_por_posicion_hoja(bloque_stripped: str) -> list:
    """Mismo filtro que usa ud2rrg.ud2rrg()/convertir.py para construir
    `sent`: replicarlo garantiza alineación con los índices de hoja del
    árbol devuelto por converter.transform (leaves() son índices 0-based
    sobre esta misma lista)."""
    ids = []
    for linea in bloque_stripped.split("\n"):
        if linea == "" or linea.startswith("#") or "\t" not in linea:
            continue
        ids.append(linea.split("\t")[0])   # str: '7' normal, '13-14' multiword
    return ids


def _nodos_periferia(tree) -> set:
    """Índices de hoja (0-based, sobre _ids_por_posicion_hoja) que cuelgan
    de algún nodo marcado por ud2rrg.peri() (label termina en '-PERI')."""
    hojas = set()
    for st in tree.subtrees():
        if isinstance(st.label, str) and st.label.endswith("-PERI"):
            hojas.update(st.leaves())
    return hojas


def kpi2_desacuerdo_periferia(bloques: list[str]) -> dict:
    """Compara, por oración, cada item de periferia de analizar_roles contra
    si su token cuelga (en el árbol de ud2rrg) bajo un nodo -PERI.

    LIMITACIÓN documentada (permitida por la spec de esta tarea): se
    reconstruye el árbol IN-PROCESS (import directo de ud2rrg) en vez de
    parsear el ASCII-art de DrawTree — el dibujo multi-línea con cajas no
    codifica un árbol de forma robusta para un parser desechable; caminar
    el objeto ParentedTree real es la variante alcanzable y confiable.
    Solo se compara sobre oraciones donde ud2rrg (con xpos stripped, el
    modo realista) SÍ produjo árbol — es un subconjunto, no la muestra
    completa (ver kpi1 para cuántas quedan fuera).
    """
    sys.path.insert(0, REPO_ROOT)
    import ud2rrg as converter

    intentadas = 0
    con_arbol = 0
    comparaciones = 0
    acuerdos = 0
    desacuerdos = []

    for bloque in bloques:
        stripped = _xpos_stripped(bloque)
        toks = bloque_a_tokens(bloque)
        root_id = root_id_de(toks)
        if root_id is None:
            continue
        roles = analizar_roles(toks, root_id, {})
        if not roles["periferia"]:
            continue   # nada que comparar en esta oración

        intentadas += 1
        try:
            udtree = next(iter(parse_tree_incr(io.StringIO(stripped))))
            rrgtree = converter.transform(udtree, LANG, layer="SENTENCE")
        except Exception:
            continue
        con_arbol += 1

        ids_hoja = _ids_por_posicion_hoja(stripped)
        pos_por_id = {tid: i for i, tid in enumerate(ids_hoja)}
        hojas_peri = _nodos_periferia(rrgtree)

        for p in roles["periferia"]:
            pos = pos_por_id.get(str(p["id"]))
            if pos is None:
                continue   # no debería pasar salvo tokens fuera de rango
            comparaciones += 1
            if pos in hojas_peri:
                acuerdos += 1
            else:
                desacuerdos.append({"texto": p["text"], "tipo": p["tipo"],
                                    "deprel": p["deprel"]})

    return {
        "oraciones_con_periferia_etapa1": intentadas,
        "de_esas_con_arbol_ud2rrg": con_arbol,
        "items_periferia_comparados": comparaciones,
        "acuerdos": acuerdos,
        "desacuerdos": len(desacuerdos),
        "pct_acuerdo": (round(100 * acuerdos / comparaciones, 1)
                        if comparaciones else None),
        "ejemplos_desacuerdo": desacuerdos[:15],
        "limitacion": ("Comparación in-process (import directo de ud2rrg), no "
                       "parseo del ASCII-art de DrawTree — ver docstring de "
                       "kpi2_desacuerdo_periferia. Solo cubre oraciones donde "
                       "ud2rrg (xpos stripped) produjo árbol Y donde Etapa 1 "
                       "detectó periferia; con la tasa de fallos medida en "
                       "KPI1, esta cobertura es parcial."),
    }


# ---------------------------------------------------------------------------
# KPI 3 — contadores (doblado, obl:arg, periferia por tipo)
# ---------------------------------------------------------------------------
def detectar_doblado(tokens: list[dict]) -> list[dict]:
    """Patrón estructural (nota de auditoría 2, NO depende de deprel expl):
    PRON átono dativo (le/les) + hermano nominal bajo el mismo head con
    case='a' → doblado. Devuelve un item por clítico dativo encontrado,
    con doblado=True/False."""
    hallados = []
    for t in tokens:
        if t["upos"] != "PRON" or t["text"].lower() not in DATIVOS_CLITICOS:
            continue
        hermanos = [h for h in tokens if h["head"] == t["head"] and h["id"] != t["id"]]
        pleno = None
        for h in hermanos:
            if h["upos"] not in ("NOUN", "PROPN"):
                continue
            case = next((c["lemma"].lower() for c in tokens
                        if c["head"] == h["id"] and c["deprel"] == "case"), None)
            if case == "a":
                pleno = h
                break
        hallados.append({"clitico": t["text"], "id": t["id"],
                         "doblado": pleno is not None,
                         "pleno_id": pleno["id"] if pleno else None,
                         "pleno_texto": pleno["text"] if pleno else None})
    return hallados


def kpi3_contadores(bloques: list[str]) -> dict:
    doblados = 0
    clitico_solo = 0
    obl_arg_total = 0
    periferia_por_tipo = Counter()

    for bloque in bloques:
        toks = bloque_a_tokens(bloque)
        root_id = root_id_de(toks)
        obl_arg_total += sum(1 for t in toks if t["deprel"] == "obl:arg")
        for d in detectar_doblado(toks):
            if d["doblado"]:
                doblados += 1
            else:
                clitico_solo += 1
        if root_id is not None:
            roles = analizar_roles(toks, root_id, {})
            for p in roles["periferia"]:
                periferia_por_tipo[p["tipo"]] += 1

    return {
        "doblado_clitico_pleno": doblados,
        "clitico_dativo_solo": clitico_solo,
        "obl_arg_total": obl_arg_total,
        "periferia_por_tipo": dict(periferia_por_tipo),
    }


# ---------------------------------------------------------------------------
# KPI 4 (Fase LINKING, Etapa L4) — pipeline híbrido REAL: Etapa 1 + mapper
# completo (roBERTa) sobre sintaxis gold, MISC inyectado, ENTONCES ud2rrg.
# ---------------------------------------------------------------------------
def _tokens_a_sentence_fake(toks: list[dict]):
    """Envuelve tokens gold (formato `bloque_a_tokens`) en un objeto con la
    misma interfaz mínima que `rrg_ls_mapper.map_sentence_to_ls` espera de
    un `stanza.Sentence` (`.words`, cada uno con `.id/.text/.lemma/.upos/
    .deprel/.head/.feats`) -- sin depender de Stanza: la sintaxis viene del
    gold, no de un re-parseo. Esto es lo que hace "híbrido" al pipeline:
    sintaxis gold real + clasificación semántica real (roBERTa)."""
    words = [SimpleNamespace(id=t["id"], text=t["text"],
                             lemma=t["lemma"] or t["text"], upos=t["upos"],
                             deprel=t["deprel"], head=t["head"],
                             feats=t["feats"])
             for t in toks]
    return SimpleNamespace(words=words)


def _inyectar_misc_en_bloque(bloque: str, anotaciones: dict) -> str:
    """Fusiona `anotaciones` (dict token_id -> {ClaveRRG: valor}, formato de
    `misc_rrg.anotaciones_misc`) en la columna MISC de `bloque`, en memoria
    (sin tocar disco) -- variante de `misc_rrg.escribir_misc_en_conllu` para
    un único bloque ya aislado, sin depender de marcadores `# text =`."""
    from .misc_rrg import fusionar_misc
    # L5 §1: si la oración fue analizada (RRGAnalyzed en algún token), estampar
    # RRGAnalyzed=si en TODOS los tokens -- misma lógica que
    # misc_rrg.escribir_misc_en_conllu (subordina el fallback de clíticos de
    # ud2rrg en toda la oración, cláusulas embebidas incluidas).
    analizada = any("RRGAnalyzed" in v for v in anotaciones.values())
    lineas = []
    for linea in bloque.split("\n"):
        if linea.startswith("#") or not linea.strip() or "\t" not in linea:
            lineas.append(linea)
            continue
        cols = linea.split("\t")
        if len(cols) == 10 and cols[0].isdigit():
            nuevas = dict(anotaciones.get(int(cols[0])) or {})
            if analizada:
                nuevas.setdefault("RRGAnalyzed", "si")
            if nuevas:
                cols[9] = fusionar_misc(cols[9], nuevas)
                linea = "\t".join(cols)
        lineas.append(linea)
    return "\n".join(lineas)


def kpi4_pipeline_hibrido(bloques: list[str]) -> dict:
    """Medición honesta (L4): para cada oración gold, corre el pipeline
    REAL -- Etapa 1 (`analizar_roles`, vía `map_sentence_to_ls`) + mapper
    completo CON el clasificador aspectual roBERTa, inyecta el MISC
    resultante (`aspect_classifier.misc_rrg`) y SOLO ENTONCES convierte con
    `ud2rrg.transform`. A diferencia de KPI2 (§ arriba), esto SÍ ejercita el
    anclaje por estrato de L3 (100% MISC-gated).

    ⚠️  Carga el clasificador roBERTa completo -- ver advertencia OOM en el
    docstring del módulo. No paralelizar con otra instancia pesada.

    Métricas:
      (a) conversión: % de oraciones que ud2rrg convierte CON el MISC real
          inyectado (vs. kpi1, que mide sin MISC).
      (b) acuerdo de periferia POR ESTRATO: de cada item de periferia
          (`ls['periferia']`), ¿existe una rama -PERI Y cuelga del estrato
          correcto (nucleo->NUC, centro->CORE, clausula->CLAUSE, campo
          "estrato" de cada item -- Etapa PERIFERIA, 2026-07-13)? Regla de
          anclaje replicada de `ud2rrg.py` directamente (no depende de si
          `wrappers_ls` envolvió ese item o no -- el anclaje por estrato se
          dispara por `RRGStratum`, no por wrapper).
      (c) tasa de completeness: % de oraciones (de las que sí convirtieron)
          con `completeness.verificar(...)['ok'] is True`.
    """
    from .completeness import _ESTRATO_A_LABEL, _ESTRATO_DEFECTO, _buscar_rama_peri, _es_ldp, verificar
    from .misc_rrg import anotaciones_misc

    sys.path.insert(0, REPO_ROOT)
    import ud2rrg as converter
    from rrg_ls_mapper import map_sentence_to_ls

    intentos = 0
    fallos_mapper = []
    conversion_ok = 0
    fallos_conversion = []
    peri_items = 0
    peri_ok_estrato = 0
    completeness_con_arbol = 0
    completeness_ok = 0
    ejemplos_completeness_warn = []
    # L5 §1 (conciliación AGX): desglose de las advertencias por tipo, para
    # verificar que agx_arbol_gt_ls (el patrón dominante de L4.5) desaparece.
    desglose_warn = {"agx_arbol_gt_ls": 0, "agx_ls_gt_arbol": 0,
                     "arg_falta_en_arbol": 0, "peri_falta_en_arbol": 0}

    for bloque in bloques:
        toks = bloque_a_tokens(bloque)
        root_id = root_id_de(toks)
        if root_id is None:
            continue
        intentos += 1

        try:
            ls = map_sentence_to_ls(_tokens_a_sentence_fake(toks))
        except Exception as e:
            fallos_mapper.append(str(e))
            continue

        anot = anotaciones_misc(ls)
        bloque_con_misc = _inyectar_misc_en_bloque(_xpos_stripped(bloque), anot)

        tree = None
        try:
            udtree = next(iter(parse_tree_incr(io.StringIO(bloque_con_misc))))
            tree = converter.transform(udtree, LANG, layer="SENTENCE")
            conversion_ok += 1
        except Exception as e:
            fallos_conversion.append(str(e))

        for p in (ls.get("periferia") or []):
            # Etapa PERIFERIA (2026-07-13): anclaje esperado por "estrato"
            # (nucleo/centro/clausula), no por "tipo" -- reemplaza la regla
            # L3 "temporal→CLAUSE" (doctrina corregida, ver completeness.py).
            estrato_esperado = _ESTRATO_A_LABEL.get(p.get("estrato"), _ESTRATO_DEFECTO)
            peri_items += 1
            encontrado, estrato_ok = _buscar_rama_peri(tree, p.get("id"), estrato_esperado)
            if encontrado and estrato_ok:
                peri_ok_estrato += 1
            elif _es_ldp(tree, p.get("id")):
                # L4.5 S2 (ampliado en la Etapa PERIFERIA): CUALQUIER
                # periferia destacada al inicio -> LDP/PrDP en vez de -PERI
                # es la estructura RRG CORRECTA (misma excepcion que el
                # checker de completeness, ver comentario ahí), no un fallo
                # de anclaje por estrato.
                peri_ok_estrato += 1

        resultado = verificar(ls, tree)
        if resultado["ok"] is not None:
            completeness_con_arbol += 1
            if resultado["ok"]:
                completeness_ok += 1
            else:
                for c in resultado["checks"]:
                    if c["tipo"] == "agx" and c["estado"] == "falta_en_ls":
                        desglose_warn["agx_arbol_gt_ls"] += 1
                    elif c["tipo"] == "agx" and c["estado"] == "falta_en_arbol":
                        desglose_warn["agx_ls_gt_arbol"] += 1
                    elif c["tipo"] == "argumento" and c["estado"] == "falta_en_arbol":
                        desglose_warn["arg_falta_en_arbol"] += 1
                    elif c["tipo"] == "periferia" and c["estado"] == "falta_en_arbol":
                        desglose_warn["peri_falta_en_arbol"] += 1
                if len(ejemplos_completeness_warn) < 15:
                    ejemplos_completeness_warn.append({
                        "texto": " ".join(t["text"] for t in toks),
                        "resumen": resultado["resumen"],
                    })

    def pct(num, den):
        return round(100 * num / den, 1) if den else None

    return {
        "muestra_n": intentos,
        "fallos_mapper": len(fallos_mapper),
        "conversion": {
            "ok": conversion_ok, "total": intentos,
            "pct_ok": pct(conversion_ok, intentos),
        },
        "acuerdo_periferia_por_estrato": {
            "items_periferia": peri_items, "ok_estrato": peri_ok_estrato,
            "pct_acuerdo": pct(peri_ok_estrato, peri_items),
        },
        "tasa_completeness": {
            "con_arbol": completeness_con_arbol, "ok": completeness_ok,
            "pct_ok": pct(completeness_ok, completeness_con_arbol),
        },
        "desglose_advertencias": desglose_warn,
        "ejemplos_completeness_advertencia": ejemplos_completeness_warn,
    }


# ---------------------------------------------------------------------------
# Verificación pendiente (nota de auditoría 3): routing de obl:arg HOY
# ---------------------------------------------------------------------------
def verificacion_obl_arg() -> dict:
    toks = [
        {"id": 1, "text": "Le", "lemma": "él", "upos": "PRON", "deprel": "obl:arg",
         "head": 2, "feats": "Case=Dat|Number=Sing|Person=3"},
        {"id": 2, "text": "compró", "lemma": "comprar", "upos": "VERB", "deprel": "root",
         "head": 0, "feats": "Number=Sing|Person=3|Tense=Past"},
        {"id": 3, "text": "un", "lemma": "uno", "upos": "DET", "deprel": "det",
         "head": 4, "feats": ""},
        {"id": 4, "text": "regalo", "lemma": "regalo", "upos": "NOUN", "deprel": "obj",
         "head": 2, "feats": ""},
        {"id": 5, "text": "a", "lemma": "a", "upos": "ADP", "deprel": "case",
         "head": 6, "feats": ""},
        {"id": 6, "text": "María", "lemma": "María", "upos": "PROPN", "deprel": "obl:arg",
         "head": 2, "feats": ""},
    ]
    r = analizar_roles(toks, 2, {})
    return {
        "entrada": "Le compró un regalo a María",
        "core": [(c["text"], c["deprel"], c.get("macropapel")) for c in r["core"]],
        "periferia": [(p["text"], p["deprel"], p["tipo"]) for p in r["periferia"]],
        "actor_implicito": r["actor_implicito"],
        "notas_mismatch": r["notas_mismatch"],
        "conclusion": ("obl:arg NO está en CORE_DEPRELS ni en PERIFERIA_DEPRELS "
                      "(que solo reconoce el string exacto 'obl' o el set fijo "
                      "{obl, advmod, obl:tmod, nmod:tmod, obl:mod, advcl}): "
                      "'Le' y 'María' NO aparecen ni en core ni en periferia — "
                      "se pierden por completo. Efecto secundario: al no "
                      "detectar sujeto, dispara pro-drop (actor_implicito=3sg), "
                      "que en este caso es casualmente correcto pero por la "
                      "razón equivocada."),
    }


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--treebank", default="ancora-dev", choices=list(TREEBANKS))
    ap.add_argument("--out", default=None,
                    help="Nombre de archivo en aspect_classifier/data/ "
                         "(default según --treebank, ver DEFAULT_OUT_POR_TREEBANK)")
    ap.add_argument("--skip-hibrido", action="store_true",
                    help="Omite KPI4 (carga roBERTa) -- solo baseline L0-style "
                         "(KPI1-3), para correr rápido/liviano sin el clasificador.")
    args = ap.parse_args()

    path = os.path.join(REPO_ROOT, TREEBANKS[args.treebank])
    bloques = leer_bloques(path, args.n)
    print(f"Treebank: {args.treebank} ({path})")
    print(f"Muestra: {len(bloques)} oraciones\n")

    print("[0/4] Verificación obl:arg (pre-existente)...")
    verif = verificacion_obl_arg()

    print("[1/4] KPI1 — tasa de fallos de ud2rrg (2 subprocess: xpos intacto / stripped)...")
    kpi1 = kpi1_tasa_fallos(bloques)

    print("[2/4] KPI2 — desacuerdo de periferia (in-process, SIN MISC -- ver docstring)...")
    kpi2 = kpi2_desacuerdo_periferia(bloques)

    print("[3/4] KPI3 — contadores (doblado / obl:arg / periferia por tipo)...")
    kpi3 = kpi3_contadores(bloques)

    kpi4 = None
    if not args.skip_hibrido:
        print("[4/4] KPI4 (L4) — pipeline híbrido real (Etapa 1 + roBERTa + MISC + "
             "ud2rrg)... ⚠️  carga el clasificador aspectual, puede tardar.")
        kpi4 = kpi4_pipeline_hibrido(bloques)

    resultado = {
        "fecha": date.today().isoformat(),
        "generado": datetime.now().isoformat(timespec="seconds"),
        "treebank": args.treebank,
        "muestra_n": len(bloques),
        "verificacion_obl_arg_pre_fix": verif,
        "kpi1_tasa_fallos_ud2rrg": kpi1,
        "kpi2_desacuerdo_periferia_sin_misc": kpi2,
        "kpi3_contadores": kpi3,
        "kpi4_pipeline_hibrido_l4": kpi4,
    }

    nombre_out = args.out or DEFAULT_OUT_POR_TREEBANK.get(
        args.treebank, f"kpi_{args.treebank.replace('-', '_')}.json")
    out_path = os.path.join(REPO_ROOT, "aspect_classifier", "data", nombre_out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"\nGuardado: {out_path}\n")
    print("=" * 72)
    print(f"RESUMEN — {args.treebank} (n={len(bloques)})")
    print("=" * 72)
    print(f"\nVerificación obl:arg (pre-fix, referencia L0): {verif['periferia']} periferia, "
         f"{verif['core']} core  → {'SE PIERDE' if not verif['core'] and not verif['periferia'] else 'ver detalle'}")
    xi = kpi1["xpos_intacto_metodologia_L0"]
    xs = kpi1["xpos_stripped_pipeline_real"]
    print(f"\nKPI1 — Tasa de fallos ud2rrg (n={xi['total']}, SIN MISC):")
    print(f"  xpos intacto (metodología L0 literal): {xi['pct_ok']}% OK / {xi['pct_fail']}% fail")
    print(f"  xpos stripped (pipeline real grrux_ai1): {xs['pct_ok']}% OK / {xs['pct_fail']}% fail")
    print(f"\nKPI2 — Desacuerdo de periferia (SIN MISC -- no ejercita el anclaje por estrato de L3):")
    print(f"  comparaciones: {kpi2['items_periferia_comparados']}, "
         f"acuerdo: {kpi2['pct_acuerdo']}%")
    print(f"\nKPI3 — Contadores:")
    print(f"  doblado clítico+pleno: {kpi3['doblado_clitico_pleno']}")
    print(f"  clítico dativo solo: {kpi3['clitico_dativo_solo']}")
    print(f"  obl:arg total: {kpi3['obl_arg_total']}")
    print(f"  periferia por tipo: {kpi3['periferia_por_tipo']}")
    if kpi4:
        print(f"\nKPI4 (L4) — pipeline híbrido real (n={kpi4['muestra_n']}):")
        print(f"  conversión (CON MISC real): {kpi4['conversion']['pct_ok']}% "
             f"({kpi4['conversion']['ok']}/{kpi4['conversion']['total']})")
        ape = kpi4["acuerdo_periferia_por_estrato"]
        print(f"  acuerdo de periferia POR ESTRATO: {ape['pct_acuerdo']}% "
             f"({ape['ok_estrato']}/{ape['items_periferia']})")
        tc = kpi4["tasa_completeness"]
        print(f"  tasa de completeness: {tc['pct_ok']}% ({tc['ok']}/{tc['con_arbol']})")


if __name__ == "__main__":
    main()
