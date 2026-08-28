"""Fase L5 §5 — bucle de corrección del usuario (la feature estrella).

Diseño CERRADO con Julian. El usuario (lingüista GRR competente, NO técnico de
GRRux) señala qué está mal en un análisis; GRRux VALIDA la corrección y la
enruta AUTOMÁTICAMENTE al archivo correcto — el usuario nunca elige archivo.

Reglas duras anti-contaminación:
  - Nada entra a un archivo VIVO sin pasar la validación completa Y el
    re-análisis confirmatorio (si el re-análisis no lo refleja -> staging).
  - `contextual_sentences.csv` JAMÁS se toca automáticamente (solo staging:
    Julian lo promueve a mano). Protege el terreno del clasificador.
  - Todo lo persistido lleva la marca `correccion_usuario` (auditable /
    reversible) + una fila en el log maestro `correcciones_log.csv`.
  - `Esc`/vacío cancela limpio en cualquier punto, sin efectos.

Piezas puras (validación de la EL, reconocimiento de plantilla, escritura de
staging/log) testeables en frío; el orquestador `bucle_correccion` recibe por
inyección la función de re-análisis y las de entrada/salida (para el test
@slow con `input` monkeypatcheado).
"""

import csv
import json
import os
import re
import tempfile
from datetime import datetime

from . import glosario
from .gui_contract import ROUTING_BY_KEY, inventario_enrutado
from .rrg_variables import reject_legacy_notation

_PKG = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_PKG, "data")

FUENTE = "correccion_usuario"

# ── Vocabulario de la EL reconocido por el mini-parser (nivel 1) ───────────
_OPERADORES = {"CAUSE", "BECOME", "INGR", "SEML", "PURP"}      # operadores sin apóstrofe
_VALORES_OPERADORES = {"DEC", "INT", "IMP", "PAST", "PRES", "FUT", "PERF",
                       "PROG", "IMPF", "NEG", "OBLG", "ABIL", "IRR", "REAL"}
_NOMBRES_OPERADORES_GRAMATICALES = {"IF", "TNS", "ASP", "NEG", "MOD", "STA"}
_PRIMITIVOS_PRIMADOS = {"do'", "have'"}                        # predicados fijos con apóstrofe
_WRAPPERS = {"for'", "during'", "before'", "after'", "until'", "since'", "at'",
             "be-in'", "be-on'", "be-at'", "be-under'", "be-near'", "be-behind'",
             "be-between'", "be-beside'", "be-in-front-of'",
             "yesterday'", "today'", "now'", "tomorrow'", "last.night'", "every'"}

CLASES = ["state", "activity", "accomplishment", "achievement",
          "semelfactive", "active_accomplishment"]
CLASE_ES = {"state": "Estado", "activity": "Actividad",
            "accomplishment": "Realización", "achievement": "Logro",
            "semelfactive": "Semelfactivo",
            "active_accomplishment": "Realización activa"}

PLANTILLAS_ACEPTADAS = (
    "6 clases aspectuales (state/activity/accomplishment/achievement/"
    "semelfactive/active_accomplishment), causativa ([do'(x,Ø)] CAUSE [β]), "
    "las 3 ditransitivas (transferencia/benefactiva/comunicación) y los "
    "wrappers de periferia por fuera (for'/during'/be-in'/yesterday'/…)")


# ═══════════════════════════════════════════════════════════════════════════
# Validación de la EL — 3 niveles (cada rechazo con explicación específica)
# ═══════════════════════════════════════════════════════════════════════════
def _balance(el: str) -> tuple[bool, str]:
    pares = {")": "(", "]": "["}
    pila = []
    for i, ch in enumerate(el):
        if ch in "([":
            pila.append((ch, i))
        elif ch in ")]":
            if not pila or pila[-1][0] != pares[ch]:
                return False, f"paréntesis/corchete de cierre '{ch}' sin apertura en la posición {i}"
            pila.pop()
    if pila:
        ch, i = pila[-1]
        return False, f"'{ch}' abierto en la posición {i} nunca se cierra"
    return True, ""


def nivel1_sintaxis(el: str) -> tuple[bool, str]:
    """Sintaxis del formalismo: corchetes/paréntesis balanceados, primitivos
    conocidos, al menos un predicado."""
    el = (el or "").strip()
    if not el:
        return False, "la EL está vacía"
    ok, err = _balance(el)
    if not ok:
        return False, f"sintaxis: {err}"
    # tokens primados (predicados): palabra + apóstrofe
    primados = re.findall(r"[\wÀ-ÿ.\-]+'", el)
    if not primados:
        return False, ("sintaxis: no se reconoce ningún predicado (se espera al "
                       "menos uno con apóstrofe, p.ej. run', have', broken')")
    # operadores bare mal escritos: palabras EN MAYÚSCULA que no son operadores
    for m in re.finditer(r"\b([A-Z]{3,})\b", el):
        if m.group(1) not in _OPERADORES | _VALORES_OPERADORES | _NOMBRES_OPERADORES_GRAMATICALES:
            return False, (f"sintaxis: '{m.group(1)}' no es un operador conocido "
                          f"(operadores válidos: {', '.join(sorted(_OPERADORES))})")
    return True, ""


def nivel2_consistencia(el: str, tokens_oracion: list[str], verb_lemma: str) -> tuple[bool, str]:
    """Consistencia con la oración: los argumentos deben ser tokens/lemas de
    la oración (o Ø, variables x/y/z o etiquetas morfológicas '3sg'); el predicado
    principal debe corresponder al lema del verbo.

    En plantillas ABSTRACTAS (ditransitiva/causativa) el predicado nuclear es
    de la plantilla (have'/CAUSE), no el lema del verbo — ahí no se exige que
    el lema aparezca primado."""
    el = (el or "").strip()
    try:
        reject_legacy_notation(el, context="la EL corregida")
    except ValueError as exc:
        return False, f"consistencia: {exc}"
    vocab = {t.lower() for t in tokens_oracion}
    abstracta = ("CAUSE" in el or "have'" in el or ".to." in el)
    # argumentos = identificadores dentro de paréntesis que NO son predicados
    # (no llevan apóstrofe) ni operadores. Se toleran Ø, variables x/y/z y
    # morf '3sg'/'1pl'.
    args = re.findall(r"[\(,\s]([\wÀ-ÿ]+)(?=[\)\],\s])", el)
    for a in args:
        al = a.lower()
        if a in _OPERADORES | _VALORES_OPERADORES | _NOMBRES_OPERADORES_GRAMATICALES:
            continue
        if al in vocab:
            continue
        if a in ("Ø",) or al in ("ø",):
            continue
        if al in ("x", "y", "z"):
            continue
        if re.fullmatch(r"\d(sg|pl)", al):
            continue
        # ¿es un predicado (lleva apóstrofe justo después)? entonces no es arg.
        if re.search(rf"{re.escape(a)}'", el):
            continue
        return False, (f"consistencia: '{a}' no es una palabra de la oración "
                      f"(ni Ø, ni x/y/z, ni una etiqueta morfológica tipo '3sg')")
    # predicado principal = lema del verbo debe aparecer primado (salvo
    # plantillas abstractas, cuyo núcleo es have'/CAUSE de la plantilla).
    if verb_lemma and not abstracta \
            and not re.search(rf"{re.escape(verb_lemma.lower())}'", el.lower()):
        return False, (f"consistencia: el predicado principal debería incluir el "
                      f"lema del verbo ('{verb_lemma}'') y no aparece")
    return True, ""


def _compactar(el: str) -> str:
    return re.sub(r"\s+", "", el or "")


def _quitar_exteriores(el: str) -> str:
    """Quita sólo operadores y wrappers exteriores balanceados conocidos."""
    e = _compactar(el)
    while e.startswith("⟨") and e.endswith("⟩"):
        interior = e[1:-1]
        pos = interior.find("⟨")
        if pos < 0:
            e = interior
            break
        if not interior.endswith("⟩"):
            break
        e = interior[pos:]
    wrappers = {w[:-1] for w in _WRAPPERS}
    while True:
        m = re.match(r"^([\wÀ-ÿ.\-]+)'\(", e)
        if not m or (m.group(1) not in wrappers and not m.group(1).startswith("be-")):
            break
        inicio = m.end()
        profundidad = 0
        coma = None
        for i in range(inicio, len(e) - 1):
            ch = e[i]
            if ch in "([": profundidad += 1
            elif ch in ")]": profundidad -= 1
            elif ch == "," and profundidad == 0:
                coma = i
                break
        if coma is None:
            break
        inner = e[coma + 1:-1]
        if inner.startswith("[") and inner.endswith("]"):
            inner = inner[1:-1]
        e = inner
    return e


_A = r"[\wÀ-ÿ.]+"


def reconocer_especificacion(el: str) -> dict | None:
    """Reconoce estructura, alcance, aridad y coindexación ditransitiva."""
    e = _quitar_exteriores(el)
    acq = re.fullmatch(
        rf"\[\[do'\((?P<x>{_A}),Ø\)\]CAUSE\[BECOMEhave'\((?P=x),(?P<z>{_A})\)\]\]"
        rf"PURP\[(?P<bec>BECOME)?have'\((?P<y>{_A}),(?P=z)\)\]", e)
    if acq:
        return {"familia": "benefactiva", "plantilla": "ditrans_benefactiva",
                "subtipo_benefactivo": "obtencion", "predicado_resultado": None,
                "aridad_resultado": 2,
                "proposito": "become_have" if acq.group("bec") else "have"}
    result = re.fullmatch(
        rf"\[\[do'\((?P<x>{_A}),Ø\)\]CAUSE\[BECOME(?P<pred>[a-z][a-z0-9_.-]*')"
        rf"\((?P<z>{_A})\)\]\]PURP\[(?P<bec>BECOME)?have'\((?P<y>{_A}),(?P=z)\)\]",
        e, re.IGNORECASE)
    if result:
        pred = result.group("pred").lower()
        subtipo = ("preparacion" if pred == "prepared'" else
                   "creacion" if pred == "exist'" else "cambio_estado")
        return {"familia": "benefactiva", "plantilla": "ditrans_benefactiva",
                "subtipo_benefactivo": subtipo, "predicado_resultado": pred,
                "aridad_resultado": 1,
                "proposito": "become_have" if result.group("bec") else "have"}
    actividad = re.fullmatch(
        rf"do'\((?P<x>{_A}),\[(?P<pred>[a-z][a-z0-9_.-]*')\((?P=x),(?P<z>{_A})\)\]\)"
        rf"PURP\[(?P<bec>BECOME)?have'\((?P<y>{_A}),(?P=z)\)\]", e, re.IGNORECASE)
    if actividad:
        return {"familia": "benefactiva", "plantilla": "ditrans_benefactiva",
                "subtipo_benefactivo": "actividad", "predicado_resultado": None,
                "predicado_actividad": actividad.group("pred").lower(),
                "aridad_resultado": 0,
                "proposito": "become_have" if actividad.group("bec") else "have"}

    tiene_cause = "CAUSE" in e
    tiene_have = "have'" in e
    tiene_purp = "PURP" in e
    if tiene_purp and (tiene_cause or tiene_have):
        return None  # benefactiva mal formada: no caer a una familia general
    if re.fullmatch(rf"\[do'\(({_A}),Ø\)\]CAUSE\[BECOMEhave'\(({_A}),({_A})\)\]", e):
        return {"familia": "transferencia", "plantilla": "ditrans_transferencia"}
    if re.search(r"\.to\.\(", e) or ".to." in e:
        return {"familia": "comunicacion", "plantilla": "ditrans_comunicacion"}
    return None


def reconocer_plantilla(el: str) -> str | None:
    """Nivel 3 — plantilla reconocida; las benefactivas exigen spec exacta."""
    spec = reconocer_especificacion(el)
    if spec:
        return spec["plantilla"]
    e = _quitar_exteriores(el)
    tiene_cause = "CAUSE" in e
    tiene_have = "have'" in e
    tiene_purp = "PURP" in e
    tiene_do = "do'" in e
    if tiene_purp:
        return None
    if tiene_cause and tiene_have:
        return "ditrans_transferencia"
    if re.search(r"\.to\.\(", e) or ".to." in e:
        return "ditrans_comunicacion"
    if tiene_cause:
        return "causativa"
    if "INGR" in e:
        return "achievement"
    if "SEML" in e:
        return "semelfactive"
    if "BECOME" in e:
        return "accomplishment"
    if tiene_do:
        return "activity"        # (o active_accomplishment; se afina por clase)
    if re.search(r"[\wÀ-ÿ.\-]+'\s*\(", e):
        return "state"           # pred'(x) / pred'(x,y) simple
    return None


# G3 §2.3 — sugerencia de clase aspectual a partir de la plantilla reconocida
# (para el dropdown de "Corregir todo"). Las 3 ditransitivas y la causativa
# genérica son, en la GRR, construcciones de cambio-de-estado causado con
# término (CAUSE/BECOME): se sugieren como Realización (accomplishment); el
# resto mapea 1:1 con su propio nombre de clase.
PLANTILLA_A_CLASE = {
    "state": "state",
    "activity": "activity",
    "accomplishment": "accomplishment",
    "achievement": "achievement",
    "semelfactive": "semelfactive",
    "causativa": "accomplishment",
    "ditrans_transferencia": "accomplishment",
    "ditrans_benefactiva": "accomplishment",
    "ditrans_comunicacion": "accomplishment",
}


def clase_sugerida_por_plantilla(plantilla: str | None) -> str | None:
    return PLANTILLA_A_CLASE.get(plantilla or "")


def validar_el(el: str, tokens_oracion: list[str], verb_lemma: str) -> dict:
    """Corre los 3 niveles en orden; devuelve el primer rechazo con su nivel y
    explicación, o {ok:True, plantilla:...}."""
    ok, err = nivel1_sintaxis(el)
    if not ok:
        return {"ok": False, "nivel": 1, "error": err}
    ok, err = nivel2_consistencia(el, tokens_oracion, verb_lemma)
    if not ok:
        return {"ok": False, "nivel": 2, "error": err}
    plantilla = reconocer_plantilla(el)
    if plantilla is None:
        return {"ok": False, "nivel": 3,
                "error": ("plantilla no reconocida — las plantillas aceptadas son: "
                          + PLANTILLAS_ACEPTADAS)}
    spec = reconocer_especificacion(el)
    if (spec and spec.get("subtipo_benefactivo") == "actividad" and
            spec.get("predicado_actividad") != f"{verb_lemma.lower()}'"):
        return {"ok": False, "nivel": 3,
                "error": ("el predicado de una benefactiva de actividad debe "
                          f"corresponder al lema {verb_lemma!r}")}
    clase_sugerida = ("activity" if spec and
                       spec.get("subtipo_benefactivo") == "actividad"
                       else clase_sugerida_por_plantilla(plantilla))
    return {"ok": True, "plantilla": plantilla, "especificacion": spec,
            "clase_sugerida": clase_sugerida}


# ═══════════════════════════════════════════════════════════════════════════
# Persistencia (staging, log maestro, archivos vivos) — con data_dir inyectable
# ═══════════════════════════════════════════════════════════════════════════
def _ruta(nombre, data_dir=None):
    return os.path.join(data_dir or _DATA, nombre)


def _append_dict_csv(ruta, fila: dict, campos: list[str]):
    existe = os.path.exists(ruta)
    with open(ruta, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        if not existe or os.path.getsize(ruta) == 0:
            w.writeheader()
        w.writerow(fila)


def log_maestro(entrada: dict, data_dir=None):
    """Fila de auditoría en correcciones_log.csv (TODA corrección, aceptada o
    en staging)."""
    campos = ["fecha", "oracion", "lema", "tipo", "accion", "destino", "detalle", "fuente"]
    fila = {c: entrada.get(c, "") for c in campos}
    fila["fecha"] = fila["fecha"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fila["fuente"] = FUENTE
    _append_dict_csv(_ruta("correcciones_log.csv", data_dir), fila, campos)


def stage_clase(oracion, lema, clase_predicha, clase_correcta, vector, data_dir=None):
    """STAGING de una corrección de clase — NUNCA toca contextual_sentences.csv
    ni el clasificador; Julian promueve a mano."""
    campos = ["fecha", "oracion", "lema", "clase_predicha", "clase_correcta",
              "vector", "fuente"]
    fila = {"fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "oracion": oracion,
            "lema": lema, "clase_predicha": clase_predicha,
            "clase_correcta": clase_correcta, "vector": vector, "fuente": FUENTE}
    _append_dict_csv(_ruta("correcciones_clase.csv", data_dir), fila, campos)
    log_maestro({"oracion": oracion, "lema": lema, "tipo": "clase",
                 "accion": "staging", "destino": "correcciones_clase.csv",
                 "detalle": f"{clase_predicha}->{clase_correcta}"}, data_dir)


def stage_enrutado(oracion, elemento, destino_deseado, motivo, data_dir=None,
                   ruta_origen="", elemento_id=None, presencia="presente"):
    campos_nuevos = ["fecha", "oracion", "elemento", "elemento_id", "presencia",
                     "ruta_origen", "destino_deseado", "motivo", "fuente"]
    ruta = _ruta("correcciones_enrutado.csv", data_dir)
    if os.path.exists(ruta) and os.path.getsize(ruta):
        with open(ruta, encoding="utf-8", newline="") as f:
            campos = next(csv.reader(f), campos_nuevos)
    else:
        campos = campos_nuevos
    fila = {"fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "oracion": oracion,
            "elemento": elemento, "elemento_id": "" if elemento_id is None else elemento_id,
            "presencia": presencia, "ruta_origen": ruta_origen or "",
            "destino_deseado": destino_deseado, "motivo": motivo, "fuente": FUENTE}
    # Un archivo histórico LA1 conserva su cabecera; las filas nuevas de un
    # archivo LA2 sí llevan el contrato estructurado completo.
    _append_dict_csv(ruta, fila, campos)
    log_maestro({"oracion": oracion, "tipo": "enrutado", "accion": "staging",
                 "destino": "correcciones_enrutado.csv",
                 "detalle": f"{elemento}->{destino_deseado} ({motivo})"}, data_dir)


def stage_operador(oracion, operador, valor_predicho, valor_correcto,
                   senal_origen, motivo, data_dir=None):
    """Staging de una corrección de OPERADOR que no puede automatizarse
    (OPERATORS_2 §2). Se registra la SEÑAL DE ORIGEN además del valor: sin
    ella la fila no sirve para diagnosticar, porque lo que falló no es un
    lexema sino la lectura de una marca morfológica."""
    campos = ["fecha", "oracion", "operador", "valor_predicho", "valor_correcto",
              "senal_origen", "motivo", "fuente"]
    fila = {"fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "oracion": oracion,
            "operador": operador, "valor_predicho": valor_predicho or "",
            "valor_correcto": valor_correcto or "", "senal_origen": senal_origen or "",
            "motivo": motivo, "fuente": FUENTE}
    _append_dict_csv(_ruta("correcciones_operadores.csv", data_dir), fila, campos)
    log_maestro({"oracion": oracion, "tipo": "operador", "accion": "staging",
                 "destino": "correcciones_operadores.csv",
                 "detalle": f"{operador}: {valor_predicho or '—'}->{valor_correcto or '—'} ({motivo})"},
                data_dir)


def stage_el(oracion, lema, el, plantilla, data_dir=None,
             especificacion=None, motivo="", accion="staging"):
    campos = ["fecha", "oracion", "lema", "el", "plantilla",
              "especificacion", "motivo", "fuente"]
    fila = {"fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "oracion": oracion,
            "lema": lema, "el": el, "plantilla": plantilla,
            "especificacion": json.dumps(especificacion or {}, ensure_ascii=False, sort_keys=True),
            "motivo": motivo, "fuente": FUENTE}
    _append_dict_csv(_ruta("correcciones_el.csv", data_dir), fila, campos)
    log_maestro({"oracion": oracion, "lema": lema, "tipo": "EL", "accion": accion,
                 "destino": "correcciones_el.csv",
                 "detalle": json.dumps({"plantilla": plantilla,
                                         "especificacion": especificacion or {},
                                         "motivo": motivo}, ensure_ascii=False, sort_keys=True)}, data_dir)


def stage_el_lema_no_identificable(oracion, el, plantilla, data_dir=None):
    """G3 §1.3 — guardia anti-basura: la plantilla reconocida se persistiría
    en un léxico VIVO (ditransitiva/causativa) pero no hay lema fiable (ni
    `verb_lemma` explícito ni un primado no-wrapper en la EL de origen) --
    NUNCA se persiste un nombre de clase aspectual como si fuera un verbo
    (el bug del checkpoint G2: "accomplishment" colado en
    verbos_ditransitivos.xlsx). Mismo archivo/esquema que `stage_el`, con
    `lema` vacío (nunca la basura) y el motivo explícito en el log maestro."""
    campos = ["fecha", "oracion", "lema", "el", "plantilla", "fuente"]
    fila = {"fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "oracion": oracion,
            "lema": "", "el": el, "plantilla": plantilla, "fuente": FUENTE}
    _append_dict_csv(_ruta("correcciones_el.csv", data_dir), fila, campos)
    log_maestro({"oracion": oracion, "lema": "", "tipo": "EL", "accion": "staging",
                 "destino": "correcciones_el.csv",
                 "detalle": f"lema no identificable ({plantilla})"}, data_dir)


# ── Escritura DIRECTA a léxicos vivos (con marca fuente + revert) ──────────
def persistir_ditransitiva(lema, especificacion, data_dir=None) -> dict:
    """Upsert atómico y reversible de una especificación ditransitiva."""
    import pandas as pd
    ruta = _ruta("verbos_ditransitivos.xlsx", data_dir)
    df = pd.read_excel(ruta)
    columnas = ["lema", "plantilla", "subtipo_benefactivo", "predicado_resultado",
                "proposito", "ambiguo", "notas", "fuente"]
    faltantes = set(columnas) - set(df.columns)
    if faltantes:
        raise ValueError(f"léxico sin migrar; faltan: {', '.join(sorted(faltantes))}")
    lema = lema.strip().lower()
    familia = especificacion.get("familia")
    plantilla = {"transferencia": "transferencia", "benefactiva": "benefactiva",
                 "comunicacion": "comunicacion"}.get(familia)
    if plantilla is None:
        raise ValueError(f"familia ditransitiva inválida: {familia!r}")
    nueva = {
        "lema": lema, "plantilla": plantilla,
        "subtipo_benefactivo": especificacion.get("subtipo_benefactivo") or "",
        "predicado_resultado": especificacion.get("predicado_resultado") or "",
        "proposito": especificacion.get("proposito") or "",
        "ambiguo": False, "notas": "", "fuente": FUENTE,
    }
    indices = df.index[df["lema"].astype(str).str.strip().str.lower() == lema].tolist()
    if len(indices) > 1:
        return {"archivo": ruta, "tipo": "xlsx", "lema": lema,
                "accion": "staging_conflicto", "conflicto": "filas activas indistinguibles"}
    contenido_anterior = open(ruta, "rb").read()
    if indices:
        idx = indices[0]
        def _escalar_python(valor):
            if pd.isna(valor):
                return ""
            return valor.item() if hasattr(valor, "item") else valor
        anterior = {c: _escalar_python(df.at[idx, c]) for c in columnas}
        comparables = ["plantilla", "subtipo_benefactivo", "predicado_resultado", "proposito"]
        if all(str(anterior[c]).strip().lower() == str(nueva[c]).strip().lower()
               for c in comparables):
            return {"archivo": ruta, "tipo": "xlsx", "lema": lema,
                    "accion": "no-op", "no_op": True, "anterior": anterior,
                    "nueva": anterior}
        if bool(anterior["ambiguo"]):
            return {"archivo": ruta, "tipo": "xlsx", "lema": lema,
                    "accion": "staging_conflicto", "conflicto":
                    "el lema está marcado ambiguo y no hay discriminador contextual suficiente",
                    "anterior": anterior}
        nota_previa = str(anterior.get("notas") or "").strip()
        cambio = (f"{datetime.now().isoformat(timespec='seconds')} {FUENTE}: "
                  f"{anterior['subtipo_benefactivo'] or anterior['plantilla']}→"
                  f"{nueva['subtipo_benefactivo'] or nueva['plantilla']}")
        nueva["notas"] = "; ".join(x for x in (nota_previa, cambio) if x)
        for c in columnas:
            df.at[idx, c] = nueva[c]
        accion = "update"
    else:
        nueva["notas"] = f"alta por {FUENTE} {datetime.now().isoformat(timespec='seconds')}"
        df = pd.concat([df, pd.DataFrame([nueva], columns=columnas)], ignore_index=True)
        accion = "insert"

    fd, temporal = tempfile.mkstemp(suffix=".xlsx", prefix="ditrans_upsert_",
                                    dir=os.path.dirname(ruta))
    os.close(fd)
    try:
        df.to_excel(temporal, index=False)
        # Validación con el mismo cargador que consumirá el mapper.
        from .ditransitivas import cargar_lexicon
        cargar_lexicon(temporal)
        os.replace(temporal, ruta)
    finally:
        if os.path.exists(temporal):
            os.remove(temporal)
    return {"archivo": ruta, "tipo": "xlsx", "lema": lema, "accion": accion,
            "contenido_anterior": contenido_anterior,
            "anterior": anterior if indices else None, "nueva": nueva}


def persistir_causativo(lema, aktionsart_base, predicado_base, data_dir=None) -> dict:
    """Añade el lema a causative_lexicon.csv con fuente en 'notas'."""
    ruta = _ruta("causative_lexicon.csv", data_dir)
    campos = ["lema", "causativo_lexico", "tipo_alternancia", "pareja_supletiva",
              "aktionsart_base", "predicado_base", "toma_se_anticausativo", "notas"]
    fila = {"lema": lema, "causativo_lexico": "True",
            "tipo_alternancia": "correccion_usuario", "pareja_supletiva": "",
            "aktionsart_base": aktionsart_base or "", "predicado_base": predicado_base or "",
            "toma_se_anticausativo": "False", "notas": f"fuente={FUENTE}"}
    _append_dict_csv(ruta, fila, campos)
    return {"archivo": ruta, "tipo": "csv", "lema": lema}


def anadir_a_lista_config(clave_seccion, clave_lista, valor, config_path=None) -> dict | None:
    """Añade `valor` a una lista de flujo YAML (`clave: [a, b, c]`) de
    config.yaml, con comentario `# correccion_usuario`. Robusto y conservador:
    si no encuentra la lista en la forma esperada, NO toca el archivo y
    devuelve None (el caller cae a staging). Devuelve token de revert."""
    ruta = config_path or os.path.join(_PKG, "config.yaml")
    with open(ruta, encoding="utf-8") as f:
        texto = f.read()
    # localizar 'clave_lista: [' y su ']' de cierre (puede abarcar varias líneas)
    m = re.search(rf"(?m)^(\s*){re.escape(clave_lista)}:\s*\[", texto)
    if not m:
        return None
    ini = m.end()
    cierre = texto.find("]", ini)
    if cierre == -1:
        return None
    contenido = texto[ini:cierre]
    if re.search(rf"(?<![\wÀ-ÿ]){re.escape(valor)}(?![\wÀ-ÿ])", contenido):
        return {"archivo": ruta, "no_op": True}   # ya estaba
    nuevo = texto[:cierre].rstrip() + f", {valor}]  # correccion_usuario" + texto[cierre + 1:]
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(nuevo)
    return {"archivo": ruta, "tipo": "yaml", "clave": clave_lista, "valor": valor}


def anadir_a_mapa_config(clave_mapa, clave, valor, config_path=None) -> dict | None:
    """Añade `clave: valor` a un MAPA en bloque de config.yaml
    (`modales:\\n  deber: OBLG`), con comentario `# correccion_usuario`.

    Hermano de `anadir_a_lista_config` para las secciones que no son listas de
    flujo: `operadores.modales` es un mapa lema->valor, y la corrección de un
    MOD no cubierto ('suele', 'quiere') necesita escribir justamente ahí.
    Mismo contrato conservador: si el bloque no tiene la forma esperada NO se
    toca el archivo y se devuelve None (el caller cae a staging).
    """
    ruta = config_path or os.path.join(_PKG, "config.yaml")
    with open(ruta, encoding="utf-8") as f:
        lineas = f.readlines()

    inicio = next((i for i, ln in enumerate(lineas)
                   if re.match(rf"(?m)^(\s*){re.escape(clave_mapa)}:\s*$", ln)), None)
    if inicio is None:
        return None
    sangria_mapa = len(lineas[inicio]) - len(lineas[inicio].lstrip())

    # última línea del bloque: entradas más indentadas que la cabecera
    fin, sangria_hijo = inicio, None
    for i in range(inicio + 1, len(lineas)):
        ln = lineas[i]
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        s = len(ln) - len(ln.lstrip())
        if s <= sangria_mapa:
            break
        if sangria_hijo is None:
            sangria_hijo = s
        if re.match(rf"^\s*{re.escape(str(clave))}:\s", ln):
            return {"archivo": ruta, "no_op": True}   # ya estaba
        fin = i
    if sangria_hijo is None:
        return None

    nueva = f"{' ' * sangria_hijo}{clave}: {valor}  # correccion_usuario\n"
    lineas.insert(fin + 1, nueva)
    with open(ruta, "w", encoding="utf-8") as f:
        f.writelines(lineas)
    return {"archivo": ruta, "tipo": "yaml_mapa", "clave": clave, "valor": valor}


def revert(token: dict):
    """Deshace un persistir_* si el re-análisis no confirmó la corrección
    (regla dura: nunca dejar en vivo algo no confirmado)."""
    if not token or token.get("no_op"):
        return
    tipo = token.get("tipo")
    ruta = token["archivo"]
    if tipo == "xlsx":
        contenido = token.get("contenido_anterior")
        if contenido is not None:
            fd, temporal = tempfile.mkstemp(suffix=".xlsx", prefix="ditrans_revert_",
                                            dir=os.path.dirname(ruta))
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(contenido)
                os.replace(temporal, ruta)
            finally:
                if os.path.exists(temporal):
                    os.remove(temporal)
    elif tipo == "csv":
        with open(ruta, encoding="utf-8") as f:
            lineas = f.readlines()
        for i in range(len(lineas) - 1, -1, -1):
            if lineas[i].startswith(token["lema"] + ",") and FUENTE in lineas[i]:
                del lineas[i]
                break
        with open(ruta, "w", encoding="utf-8") as f:
            f.writelines(lineas)
    elif tipo == "yaml":
        with open(ruta, encoding="utf-8") as f:
            texto = f.read()
        texto = texto.replace(f", {token['valor']}]  # correccion_usuario", "]")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(texto)
    elif tipo == "yaml_mapa":
        with open(ruta, encoding="utf-8") as f:
            lineas = f.readlines()
        marca = f"{token['clave']}: {token['valor']}  # correccion_usuario"
        for i in range(len(lineas) - 1, -1, -1):
            if lineas[i].strip() == marca:
                del lineas[i]
                break
        with open(ruta, "w", encoding="utf-8") as f:
            f.writelines(lineas)


# ═══════════════════════════════════════════════════════════════════════════
# Orquestador del bucle (entrada/salida y re-análisis inyectables)
# ═══════════════════════════════════════════════════════════════════════════
_CANCEL = object()


def _pedir(prompt, entrada, salida):
    """Lee una línea; '' o 'esc' (sin distinguir mayúsc.) = cancelar -> _CANCEL.

    Fix 2026-07-12: `-help`/`--help`/`-ayuda`/`--ayuda` (con o sin término)
    responde el glosario y VUELVE A MOSTRAR el mismo prompt -- en ningún
    input interactivo del bucle de corrección (menú principal ni sub-menús)
    debe -help tragarse la respuesta ni abortar el flujo (mismo bug que el
    prompt de guardar/corregir de grrux_ai1, arreglado en el mismo commit)."""
    while True:
        salida(prompt)
        try:
            val = entrada("> ")
        except EOFError:
            return _CANCEL
        val = (val or "").strip()
        es_help, termino = glosario.es_comando_help(val)
        if es_help:
            salida("")
            salida(glosario.respuesta_help(termino))
            salida("")
            continue
        if val == "" or val.lower() == "esc":
            return _CANCEL
        return val


def _aplicar_en_memoria_ditrans(lema, especificacion):
    """Inyecta la entrada en el léxico VIVO del mapper (en memoria) para que el
    re-análisis la vea sin recargar el .xlsx."""
    try:
        import rrg_ls_mapper as m
        if m._DITRANS_LEXICON is not None:
            m._DITRANS_LEXICON[lema.lower()] = {
                "plantilla": especificacion["familia"],
                "subtipo_benefactivo": especificacion.get("subtipo_benefactivo"),
                "predicado_resultado": especificacion.get("predicado_resultado"),
                "proposito": especificacion.get("proposito"),
                "ambiguo": False, "notas": f"fuente={FUENTE}", "fuente": FUENTE}
    except Exception:
        pass


def _recargar_en_memoria_ditrans(ruta):
    try:
        import rrg_ls_mapper as m
        from .ditransitivas import cargar_lexicon
        nuevo = cargar_lexicon(ruta)
        if m._DITRANS_LEXICON is not None:
            m._DITRANS_LEXICON.clear()
            m._DITRANS_LEXICON.update(nuevo)
    except Exception:
        pass


def _aplicar_en_memoria_caus(lema, aktionsart, predicado):
    try:
        import rrg_ls_mapper as m
        if m._CAUS_LEXICON is not None:
            m._CAUS_LEXICON[lema.lower()] = {
                "lema": lema, "causativo_lexico": True, "tipo_alternancia": FUENTE,
                "pareja_supletiva": "", "aktionsart_base": aktionsart or "",
                "predicado_base": predicado or "", "toma_se_anticausativo": False,
                "notas": FUENTE}
    except Exception:
        pass


def _aplicar_en_memoria_config(clave_lista, valor, seccion="nucleo_periferia"):
    """Refleja en el config YA CARGADO lo que se acaba de escribir en el
    archivo, para que el re-análisis confirmatorio de la misma sesión lo vea
    (el mapper no relee config.yaml).

    OPERATORS_2 §2: además de listas admite MAPAS (`operadores.modales`),
    donde `valor` llega como la tupla (clave, valor)."""
    try:
        import rrg_ls_mapper as m
        cfg = m._aspect_clf.config.get(seccion, {})
        if isinstance(valor, tuple):
            clave, v = valor
            cfg.setdefault(clave_lista, {})[clave] = v
            return
        lista = cfg.setdefault(clave_lista, [])
        if valor not in lista:
            lista.append(valor)
    except Exception:
        pass


def _ls_de(res, sub_idx):
    lst = res.get("ls_lista") or []
    return lst[sub_idx] if 0 <= sub_idx < len(lst) else {}


def bucle_correccion(res, reanalizar_fn, sub_idx=0, entrada=input, salida=print,
                     data_dir=None, config_path=None):
    """Menú de corrección para la (sub)oración `sub_idx` de `res`.

    `reanalizar_fn(oracion) -> res_nuevo` re-corre el pipeline (inyectable
    para el test @slow). Devuelve un dict-resumen de lo actuado (para tests).
    """
    ls = _ls_de(res, sub_idx)
    oracion = res.get("oracion", "")
    lema = _lema_de(ls)
    tokens_oracion = _tokens_de_oracion(oracion)

    salida("\n  ¿Qué está mal en el análisis?")
    salida("    1) La clase aspectual (State/Activity/…)")
    salida("    2) La Estructura Lógica completa")
    salida("    3) El enrutado de un elemento (periferia↔argumento, tipo, posición, clítico/AGX)")
    salida("    4) Un operador (tiempo, aspecto, negación, modalidad, fuerza ilocutiva)")
    salida("    Esc) Cancelar")
    opcion = _pedir("  Elige [1/2/3/4]:", entrada, salida)
    if opcion is _CANCEL:
        salida("  (corrección cancelada, sin efectos)")
        return {"accion": "cancelado"}

    if opcion == "1":
        return _flujo_clase(oracion, lema, ls, reanalizar_fn, entrada, salida, data_dir)
    if opcion == "2":
        return _flujo_el(oracion, lema, ls, tokens_oracion, sub_idx, reanalizar_fn,
                         entrada, salida, data_dir)
    if opcion == "3":
        return _flujo_enrutado(oracion, ls, sub_idx, reanalizar_fn, entrada, salida,
                               data_dir, config_path)
    if opcion == "4":
        return _flujo_operador(oracion, ls, sub_idx, reanalizar_fn, entrada, salida,
                               data_dir, config_path)
    salida("  opción no reconocida — cancelado")
    return {"accion": "cancelado"}


# ── Flujo (1) Clase ────────────────────────────────────────────────────────
def _corregir_clase_core(oracion, lema, ls, clase_correcta, data_dir=None) -> dict:
    """G0.4 — lógica de staging compartida por `_flujo_clase` (interactivo)
    y `corregir_clase` (API no-interactiva, GUI)."""
    stage_clase(oracion, lema, ls.get("ls_type", ""), clase_correcta,
                ls.get("morph_note", ""), data_dir)
    return {"accion": "staging_clase", "clase": clase_correcta}


def corregir_clase(res, sub_idx, clase_correcta, data_dir=None, verb_lemma=None) -> dict:
    """G0.4 — como `_flujo_clase` sin menú: solo el staging (el follow-up
    interactivo de sugerir una plantilla ditransitiva/causativa ausente
    queda fuera, es exclusivo del menú de terminal). `verb_lemma` (G3 §1):
    lema explícito que manda sobre el fallback `_lema_de` (ver ese docstring
    para el bug que resuelve)."""
    ls = _ls_de(res, sub_idx)
    oracion = res.get("oracion", "")
    lema = verb_lemma or _lema_de(ls)
    return _corregir_clase_core(oracion, lema, ls, clase_correcta, data_dir)


def _flujo_clase(oracion, lema, ls, reanalizar_fn, entrada, salida, data_dir):
    salida("\n  Clase aspectual correcta:")
    for i, c in enumerate(CLASES, 1):
        salida(f"    {i}) {CLASE_ES[c]} ({c})")
    sel = _pedir("  Elige [1-6]:", entrada, salida)
    if sel is _CANCEL or not sel.isdigit() or not (1 <= int(sel) <= 6):
        salida("  (cancelado, sin efectos)")
        return {"accion": "cancelado"}
    clase_correcta = CLASES[int(sel) - 1]
    _corregir_clase_core(oracion, lema, ls, clase_correcta, data_dir)
    salida("  ✓ Corrección de clase registrada en STAGING "
           "(correcciones_clase.csv). El clasificador NO se toca: Julian la "
           "promueve a mano a contextual_sentences.csv.")
    # ¿la clase corregida sugiere una plantilla ditransitiva/causativa ausente?
    if clase_correcta in ("accomplishment", "active_accomplishment"):
        try:
            import rrg_ls_mapper as m
            en_ditrans = m._DITRANS_LEXICON is not None and lema.lower() in m._DITRANS_LEXICON
            en_caus = m._CAUS_LEXICON is not None and lema.lower() in m._CAUS_LEXICON
        except Exception:
            en_ditrans = en_caus = True
        if not en_ditrans and not en_caus:
            r = _pedir("  ¿La clase implica una plantilla ditransitiva/causativa que "
                       "el léxico no tiene? Escribe la EL correcta para registrar el "
                       "lema (o Esc para omitir):", entrada, salida)
            if r is not _CANCEL:
                return _procesar_el_texto(r, oracion, lema, _tokens_de_oracion(oracion),
                                          0, reanalizar_fn, entrada, salida, data_dir)
    return {"accion": "staging_clase", "clase": clase_correcta}


# ── Flujo (2) EL completa ──────────────────────────────────────────────────
def validar_el_en_vivo(res, sub_idx, el_texto) -> dict:
    """G2 §2 — validación EN VIVO del editor de la GUI (sin persistir, sin
    re-análisis): resuelve `tokens_oracion`/`lema` con el mismo criterio que
    `corregir_el`/`_procesar_el_texto` y corre `validar_el` (3 niveles),
    standalone para el debounce del editor."""
    ls = _ls_de(res, sub_idx)
    lema = _lema_de(ls)
    tokens_oracion = _tokens_de_oracion(res.get("oracion", ""))
    return validar_el(el_texto, tokens_oracion, lema)


def corregir_el(res, sub_idx, el_texto, reanalizar_fn, data_dir=None, verb_lemma=None) -> dict:
    """G0.4 — API no-interactiva: valida `el_texto` (3 niveles) y persiste/
    confirma/revierte igual que el flujo de terminal, reusando
    `_procesar_el_texto` (ninguna lógica duplicada). `verb_lemma` (G3 §1):
    lema explícito que manda sobre el fallback `_lema_de`."""
    ls = _ls_de(res, sub_idx)
    oracion = res.get("oracion", "")
    lema = verb_lemma or _lema_de(ls)
    tokens_oracion = _tokens_de_oracion(oracion)
    return _procesar_el_texto(el_texto, oracion, lema, tokens_oracion, sub_idx,
                              reanalizar_fn, entrada=None, salida=lambda *_: None,
                              data_dir=data_dir)


def _flujo_el(oracion, lema, ls, tokens_oracion, sub_idx, reanalizar_fn,
              entrada, salida, data_dir):
    salida("\n  Escribe la Estructura Lógica correcta (con los formalismos).")
    salida(f"  EL actual: {ls.get('ls_lexical', '')}")
    el = _pedir("  EL correcta:", entrada, salida)
    if el is _CANCEL:
        salida("  (cancelado, sin efectos)")
        return {"accion": "cancelado"}
    return _procesar_el_texto(el, oracion, lema, tokens_oracion, sub_idx,
                              reanalizar_fn, entrada, salida, data_dir)


def _procesar_el_texto(el, oracion, lema, tokens_oracion, sub_idx, reanalizar_fn,
                       entrada, salida, data_dir):
    v = validar_el(el, tokens_oracion, lema)
    if not v["ok"]:
        salida(f"  ✗ Rechazada (nivel {v['nivel']}): {v['error']}")
        return {"accion": "rechazado", "nivel": v["nivel"], "error": v["error"]}
    plantilla = v["plantilla"]
    especificacion = v.get("especificacion")
    salida(f"  ✓ EL válida — plantilla reconocida: {plantilla}")

    # G3 §1.3 — guardia anti-basura: ANTES de tocar un léxico vivo, si el
    # lema resuelto (explícito o por el fallback `_lema_de`) es en realidad
    # un nombre de clase aspectual (el bug del checkpoint: `_lema_de` cayó a
    # `ls_type` porque la EL léxica original no exponía el verbo primado),
    # se protege el léxico y se manda a staging -- jamás una fila espuria.
    if plantilla.startswith("ditrans_") or plantilla == "causativa":
        if _lema_no_identificable(lema):
            stage_el_lema_no_identificable(oracion, el, plantilla, data_dir)
            salida("  ⚠ lema no identificable — se protege el léxico vivo: la "
                   "corrección queda en STAGING (correcciones_el.csv) para revisión "
                   "manual, no se persiste un nombre de clase como si fuera un verbo.")
            return {"accion": "staging_lema_no_identificable", "plantilla": plantilla}

    # Derivación automática del destino (el usuario NO elige archivo).
    if plantilla.startswith("ditrans_"):
        if especificacion is None:
            # Transferencia/comunicación reconocidas por compatibilidad:
            # completar la spec mínima que usa el léxico estructurado.
            familia = plantilla.replace("ditrans_", "")
            especificacion = {"familia": familia, "plantilla": plantilla,
                               "subtipo_benefactivo": None,
                               "predicado_resultado": None, "proposito": None}
        token = persistir_ditransitiva(lema, especificacion, data_dir)
        if token.get("accion") == "staging_conflicto":
            motivo = token.get("conflicto", "lectura conflictiva")
            stage_el(oracion, lema, el, plantilla, data_dir, especificacion, motivo,
                     accion="staging_conflicto")
            return {"accion": "staging_conflicto", "plantilla": plantilla,
                    "especificacion": especificacion, "motivo": motivo}
        _aplicar_en_memoria_ditrans(lema, especificacion)
        return _confirmar_persistencia(
            token, oracion, lema, el, plantilla, reanalizar_fn, sub_idx, entrada, salida,
            data_dir, confirma=lambda r: _confirmar_ditransitiva(
                _ls_de(r, sub_idx), el, especificacion),
            especificacion=especificacion)
    if plantilla == "causativa":
        pred = f"{lema}'"
        token = persistir_causativo(lema, "", pred, data_dir)
        _aplicar_en_memoria_caus(lema, "", pred)
        return _confirmar_persistencia(
            token, oracion, lema, el, plantilla, reanalizar_fn, sub_idx, entrada, salida,
            data_dir, confirma=lambda r: bool(_ls_de(r, sub_idx).get("causativo")))
    # clase aspectual distinta implícita -> STAGING (opción 1), no toca vivo.
    stage_el(oracion, lema, el, plantilla, data_dir)
    salida("  ✓ EL registrada en STAGING (correcciones_el.csv): implica una clase "
           "aspectual, que no se persiste en vivo (protege al clasificador).")
    return {"accion": "staging_el", "plantilla": plantilla}


def _confirmar_persistencia(token, oracion, lema, el, plantilla, reanalizar_fn,
                            sub_idx, entrada, salida, data_dir, confirma,
                            especificacion=None):
    """Cierre del ciclo: re-analiza y CONFIRMA. Si no confirma, revierte el
    archivo vivo y cae a staging (nunca deja en vivo algo no confirmado).

    Los operadores usan el MISMO ciclo pero con su propio confirmador
    (`_confirma_operador`, que mira `ls["operadores"]` en vez de la EL) y su
    propio enrutado — ver `corregir_operador`.
    """
    salida("  Re-analizando para confirmar…")
    try:
        res_nuevo = reanalizar_fn(oracion)
        ok = confirma(res_nuevo)
    except Exception as e:
        ok = False
        salida(f"  (el re-análisis falló: {e})")
    if ok:
        accion = token.get("accion", "persistido")
        detalle = {"plantilla": plantilla, "especificacion": especificacion or {},
                   "el_propuesta": el, "antes": token.get("anterior"),
                   "despues": token.get("nueva"), "accion_upsert": accion}
        log_maestro({"oracion": oracion, "lema": lema, "tipo": "EL", "accion": accion,
                     "destino": os.path.basename(token["archivo"]),
                     "detalle": json.dumps(detalle, ensure_ascii=False, sort_keys=True)},
                    data_dir)
        salida(f"  ✓ Corrección aplicada y verificada → {os.path.basename(token['archivo'])} "
               f"(fuente={FUENTE}).")
        return {"accion": accion, "plantilla": plantilla,
                "especificacion": especificacion, "archivo": token["archivo"]}
    # no confirmó: revertir vivo + staging
    revert(token)
    if token.get("tipo") == "xlsx":
        _recargar_en_memoria_ditrans(token["archivo"])
    motivo_revert = "el reanálisis no reprodujo exactamente la semántica corregida"
    log_maestro({"oracion": oracion, "lema": lema, "tipo": "EL", "accion": "revert",
                 "destino": os.path.basename(token["archivo"]),
                 "detalle": json.dumps({"plantilla": plantilla,
                                          "especificacion": especificacion or {},
                                          "el_propuesta": el,
                                          "antes": token.get("anterior"),
                                          "intento": token.get("nueva"),
                                          "motivo": motivo_revert},
                                         ensure_ascii=False, sort_keys=True)}, data_dir)
    stage_el(oracion, lema, el, plantilla, data_dir, especificacion,
             motivo_revert, accion="staging_no_confirmado")
    salida("  ⚠ La corrección se registró pero el análisis aún no la refleja — "
           "quedará para revisión (staging), no se dejó en el archivo vivo.")
    return {"accion": "staging_no_confirmado", "plantilla": plantilla}


def _confirmar_ditransitiva(ls: dict, el_propuesta: str, especificacion: dict) -> bool:
    """Confirmación exacta: spec, EL léxica, formal, estructura y argumentos."""
    meta = ls.get("ditransitiva") or {}
    familia = especificacion.get("familia")
    if meta.get("plantilla") != familia:
        return False
    for campo in ("subtipo_benefactivo", "predicado_resultado", "proposito"):
        if (meta.get(campo) or None) != (especificacion.get(campo) or None):
            return False
    propuestas = _compactar(el_propuesta)
    regeneradas = {_compactar(ls.get("ls_lexical", "")),
                   _compactar(ls.get("ls_lexical_ops", ""))}
    if propuestas not in regeneradas:
        return False
    try:
        reject_legacy_notation(ls.get("ls_formal", ""), context="EL formal regenerada")
    except ValueError:
        return False
    variables = ls.get("variables") or {}
    if not set(variables).issubset({"x", "y", "z"}):
        return False
    if not isinstance(ls.get("ls_estructura"), list) or not ls.get("ls_estructura"):
        return False
    ids = list((ls.get("id_a_var") or {}).values())
    return all(v in {"x", "y", "z"} for v in ids) and len(ids) == len(set(ids))


# ── "Corregir todo" (G3 §2) — EL + clase en un solo paso ───────────────────
def corregir_todo(res, sub_idx, el_texto, clase_correcta, reanalizar_fn, data_dir=None,
                  verb_lemma=None) -> dict:
    """G3 §2 — cuando la EL no corresponde con la clase aspectual, la clase
    también está mal: corregir las dos por separado obliga a dos
    correcciones (y dos re-análisis) sobre la MISMA oración. Compone las
    piezas EXISTENTES -- staging de clase (`_corregir_clase_core`, igual que
    `corregir_clase`) + el flujo de EL (`_procesar_el_texto`, igual que
    `corregir_el`) -- sin duplicar lógica de persistencia/validación. Reglas
    intactas: la clase SIEMPRE va a staging; la EL sigue exactamente la
    lógica de `corregir_el` (léxico vivo, staging, o rechazo), así que el
    único re-análisis posible es el que YA dispara `_procesar_el_texto`
    (cero si la EL se rechaza o solo se stagea; a lo sumo uno si persiste
    en un léxico vivo) -- nunca dos. Cada componente deja su propia fila en
    el log maestro (auditoría completa); `accion` del retorno concatena
    ambos resultados como "<accion_clase>+<accion_el>"."""
    ls = _ls_de(res, sub_idx)
    oracion = res.get("oracion", "")
    lema = verb_lemma or _lema_de(ls)
    tokens_oracion = _tokens_de_oracion(oracion)

    resultado_clase = _corregir_clase_core(oracion, lema, ls, clase_correcta, data_dir)
    resultado_el = _procesar_el_texto(el_texto, oracion, lema, tokens_oracion, sub_idx,
                                      reanalizar_fn, entrada=None, salida=lambda *_: None,
                                      data_dir=data_dir)
    return {"accion": f"{resultado_clase['accion']}+{resultado_el['accion']}",
           "clase_resultado": resultado_clase, "el_resultado": resultado_el}


# ── Flujo (3) Enrutado ─────────────────────────────────────────────────────
# Los operadores NO son un destino de enrutado (no son constituyentes: no
# viven en el árbol), así que NO están en esta tabla: tienen su propio flujo
# (4) con destinos propios — ver `VALORES_OPERADOR` / `corregir_operador`.
_DESTINOS_ENRUTADO = {
    "1": ("argumento_core", "argumento del core"),
    "2": ("periferia_temporal", "periferia temporal"),
    "3": ("periferia_locativo", "periferia locativa"),
    "4": ("periferia_modo", "periferia de modo"),
    "5": ("ldp", "posición destacada (LDP)"),
    "6": ("agx", "clítico de concordancia (AGX)"),
}

_DESTINOS_ENRUTADO_COMPLETO = {
    item["clave"]: (item["clave"], item["etiqueta"])
    for item in ROUTING_BY_KEY.values()
}
_DESTINOS_ENRUTADO_COMPLETO.update(_DESTINOS_ENRUTADO)


def _constituyentes(ls):
    items = []
    for c in ls.get("core") or []:
        items.append(("core", c.get("text", ""), c))
    for p in ls.get("periferia") or []:
        items.append(("periferia", p.get("text", ""), p))
    return items


_DESTINOS_ENRUTADO_VALORES = {
    clave: etiqueta for clave, (_, etiqueta) in _DESTINOS_ENRUTADO_COMPLETO.items()
}


def _es_recipiente_dativo(ls: dict | None, texto: str) -> bool:
    """ENRUTADO-DATIVO (2026-08-19) — ¿el elemento es el sintagma pleno que
    dobla a un clítico dativo? (`roles['agx']` ya lo resolvió: fuente
    'dativo' + `arg_id` apuntando a ese token). Es la señal de que el
    usuario está corrigiendo un RECIPIENTE, no una meta de movimiento."""
    if not ls:
        return False
    ids = {c.get("id") for c in (ls.get("core") or []) if c.get("text") == texto}
    ids |= {p.get("id") for p in (ls.get("periferia") or []) if p.get("text") == texto}
    return any(a.get("fuente") == "dativo" and a.get("arg_id") in ids
               for a in (ls.get("agx") or []))


def _enrutar_core(oracion, sub_idx, texto, lema_item, destino_clave, destino_etiqueta,
                  verbo_lema, reanalizar_fn, salida, data_dir, config_path,
                  ls=None) -> dict:
    """G0.4 — lógica de persistencia/confirmación compartida por
    `_flujo_enrutado` (interactivo, tras las 2 selecciones por menú) y
    `corregir_enrutado` (API no-interactiva, GUI)."""
    # Mapear destino -> lista de config donde persiste (si existe una)
    if destino_clave == "periferia_modo":
        token = anadir_a_lista_config("pruebas_estructurales", "adv_dinamicos",
                                      lema_item, config_path)
        _aplicar_en_memoria_config("adv_dinamicos", lema_item)
        lista_nombre = "adv_dinamicos"
    elif destino_clave == "argumento_core":
        # ENRUTADO-DATIVO (2026-08-19). Esta rama automatizaba UNA sola
        # lectura de "argumento del core" —meta/origen de un verbo de
        # movimiento— y la aplicaba a TODAS. El 2026-07-14, una corrección
        # sobre "juan le da un regalo a maria" (un RECIPIENTE dativo, no una
        # meta) acabó metiendo `dar` en `verbos_movimiento`; desde entonces
        # todo oblicuo en a/hacia/hasta bajo `dar` ascendía al core como Meta
        # ("dio un discurso a las tres" -> tres/Meta). Ver
        # CHECKPOINT_DITRANS_AGX.md §2.
        if _es_recipiente_dativo(ls, texto):
            stage_enrutado(oracion, texto, destino_etiqueta,
                           "es un recipiente dativo, no una meta de movimiento: "
                           "su ruta es la plantilla ditransitiva "
                           "(data/verbos_ditransitivos.xlsx), no verbos_movimiento",
                           data_dir)
            salida("  ⚠ Ese elemento es el recipiente de un clítico dativo, no la "
                   "meta de un verbo de movimiento. NO se toca `verbos_movimiento` "
                   "(hacerlo corrompe el enrutado de todas las oraciones con este "
                   "verbo). Registrado para revisión.")
            return {"accion": "staging_enrutado", "destino": destino_clave}
        # meta/origen de un verbo de movimiento -> case_meta / verbos_movimiento
        token = anadir_a_lista_config("nucleo_periferia", "verbos_movimiento",
                                      verbo_lema, config_path)
        _aplicar_en_memoria_config("verbos_movimiento", verbo_lema)
        lista_nombre = "verbos_movimiento"
    else:
        token = None
        lista_nombre = None

    if token is None:
        stage_enrutado(oracion, texto, destino_etiqueta,
                       "no hay lista de config donde quepa esta corrección", data_dir)
        salida("  ⚠ Registrado para revisión (correcciones_enrutado.csv); esta "
               "corrección aún no puede automatizarse.")
        return {"accion": "staging_enrutado", "destino": destino_clave}

    # confirmar por re-análisis
    salida(f"  Añadido a config ({lista_nombre}); re-analizando para confirmar…")
    try:
        res_nuevo = reanalizar_fn(oracion)
        ls_nuevo = _ls_de(res_nuevo, sub_idx)
        ok = _confirma_enrutado(ls_nuevo, texto, destino_clave)
    except Exception as e:
        ok = False
        salida(f"  (el re-análisis falló: {e})")
    if ok:
        log_maestro({"oracion": oracion, "lema": verbo_lema, "tipo": "enrutado",
                     "accion": "persistido", "destino": f"config:{lista_nombre}",
                     "detalle": f"{texto}->{destino_etiqueta}"}, data_dir)
        salida(f"  ✓ Corrección aplicada y verificada → config.yaml ({lista_nombre}, "
               "# correccion_usuario).")
        return {"accion": "persistido_enrutado", "destino": destino_clave}
    revert(token)
    stage_enrutado(oracion, texto, destino_etiqueta,
                   "el re-análisis no reflejó la corrección", data_dir)
    salida("  ⚠ La corrección se registró pero el análisis aún no la refleja — "
           "quedará para revisión (staging).")
    return {"accion": "staging_no_confirmado_enrutado", "destino": destino_clave}


def corregir_enrutado(res, sub_idx, elemento_id, destino, reanalizar_fn,
                      data_dir=None, config_path=None, verb_lemma=None,
                      ruta_origen=None) -> dict:
    """G0.4 — API no-interactiva: `elemento_id` es el `id` de token del
    constituyente (core o periferia, ver `_constituyentes`/el `id` que ya
    trae `periferia`/`core` en el contrato G0.3); `destino` es una de las
    claves de `_DESTINOS_ENRUTADO` (p.ej. 'argumento_core', 'agx', 'ldp'…).
    Sin menú: el frontend ya resolvió ambas selecciones antes de llamar.
    `verb_lemma` (G3 §1): lema explícito que manda sobre el fallback
    `_lema_de`."""
    ls = _ls_de(res, sub_idx)
    oracion = res.get("oracion", "")
    items = _constituyentes(ls)
    if destino not in _DESTINOS_ENRUTADO_VALORES:
        return {"accion": "cancelado", "error": "destino desconocido"}
    if ruta_origen and ruta_origen not in ROUTING_BY_KEY:
        return {"accion": "cancelado", "error": "ruta de origen desconocida"}
    if elemento_id is None:
        destino_etiqueta = _DESTINOS_ENRUTADO_VALORES[destino]
        stage_enrutado(oracion, "", destino_etiqueta,
                       "posición ausente o ruta aún no automatizable", data_dir,
                       ruta_origen=ruta_origen, elemento_id=None,
                       presencia="ausente")
        return {"accion": "staging_enrutado", "destino": destino,
                "ruta_origen": ruta_origen, "elemento_id": None}
    match = next((item for _, _, item in items if item.get("id") == elemento_id), None)
    if match is None:
        return {"accion": "cancelado", "error": "elemento no encontrado"}
    texto = match.get("text", "")
    lema_item = (match.get("lemma") or texto).lower()
    destino_etiqueta = _DESTINOS_ENRUTADO_VALORES[destino]
    verbo_lema = verb_lemma or _lema_de(ls)
    return _enrutar_core(oracion, sub_idx, texto, lema_item, destino, destino_etiqueta,
                         verbo_lema, reanalizar_fn, lambda *_: None, data_dir,
                         config_path, ls=ls)


def _flujo_enrutado(oracion, ls, sub_idx, reanalizar_fn, entrada, salida,
                    data_dir, config_path):
    inventario = inventario_enrutado(ls)
    # Mantener la ergonomía histórica del terminal: las categorías presentes
    # primero; las ausentes siguen siempre visibles a continuación.
    inventario = sorted(inventario, key=lambda r: r["ausente"])
    salida("\n  ¿Qué elemento está mal enrutado?")
    for i, ruta in enumerate(inventario, 1):
        estado = ", ".join(f"'{x['texto']}'" for x in ruta["instancias"]) or "(ausente)"
        salida(f"    {i}) {ruta['etiqueta']}: {estado}")
    sel = _pedir("  Elige la categoría:", entrada, salida)
    if sel is _CANCEL or not sel.isdigit() or not (1 <= int(sel) <= len(inventario)):
        salida("  (cancelado, sin efectos)")
        return {"accion": "cancelado"}
    ruta = inventario[int(sel) - 1]
    instancias = ruta["instancias"]
    if len(instancias) > 1:
        salida(f"  Instancias de {ruta['etiqueta']}:")
        for i, item in enumerate(instancias, 1):
            salida(f"    {i}) '{item['texto']}'")
        si = _pedir("  Elige la instancia:", entrada, salida)
        if si is _CANCEL or not si.isdigit() or not (1 <= int(si) <= len(instancias)):
            salida("  (cancelado, sin efectos)")
            return {"accion": "cancelado"}
        instancia = instancias[int(si) - 1]
    else:
        instancia = instancias[0] if instancias else {"elemento_id": None, "texto": ""}
    texto = instancia.get("texto", "")
    elemento_id = instancia.get("elemento_id")
    lema_item = texto.lower()

    salida("\n  ¿Qué debería ser?")
    destinos = list(_DESTINOS_ENRUTADO_COMPLETO.values())
    for k, (_, etiqueta) in enumerate(destinos, 1):
        salida(f"    {k}) {etiqueta}")
    d = _pedir("  Elige el destino:", entrada, salida)
    if d is _CANCEL or not d.isdigit() or not (1 <= int(d) <= len(destinos)):
        salida("  (cancelado, sin efectos)")
        return {"accion": "cancelado"}
    destino_clave, destino_etiqueta = destinos[int(d) - 1]
    if elemento_id is None:
        stage_enrutado(oracion, texto, destino_etiqueta,
                       "posición ausente o ruta aún no automatizable", data_dir,
                       ruta_origen=ruta["clave"], presencia="ausente")
        salida("  ⚠ Registrado para revisión (posición ausente; sin mutar el árbol).")
        return {"accion": "staging_enrutado", "destino": destino_clave,
                "ruta_origen": ruta["clave"]}
    verbo_lema = _lema_de(ls)
    return _enrutar_core(oracion, sub_idx, texto, lema_item, destino_clave,
                         destino_etiqueta, verbo_lema, reanalizar_fn, salida,
                         data_dir, config_path, ls=ls)


# ── Flujo (4) Operadores (OPERATORS_2 §2) ─────────────────────────────────
# Valores VÁLIDOS por operador: la corrección no acepta texto libre, solo lo
# que la teoría admite (Van Valin 2.25). Espejo de `operadores.py`.
VALORES_OPERADOR = {
    "IF":  ["DEC", "INT", "IMP"],
    "TNS": ["PAST", "PRES", "FUT"],
    "ASP": ["PERF", "PROG", "IMPF", "PERF PROG", "PERF IMPF", "PROG IMPF"],
    "NEG": ["NEG"],
    "MOD": ["OBLG", "ABIL"],
    "STA": ["IRR", "REAL"],
}

# Qué lista/mapa de config gobierna cada operador cuando el fallo es un HUECO
# LÉXICO. IF/TNS/ASP no aparecen: no se derivan de listas de palabras sino de
# rasgos morfológicos y puntuación, así que un fallo suyo NUNCA es léxico —
# es de parse, y va a staging.
_CONFIG_OPERADOR = {
    ("STA", "IRR"):  ("lista", "adv_epistemicos_irreal"),
    ("STA", "REAL"): ("lista", "adv_epistemicos_real"),
    ("NEG", "NEG"):  ("lista", "negadores"),
    ("MOD", "OBLG"): ("mapa", "modales"),
    ("MOD", "ABIL"): ("mapa", "modales"),
}


def _candidato_lexico(ls, operador):
    """Palabra de la oración que PODRÍA ser el disparador léxico ausente.

    STA/NEG se disparan con adverbios: el candidato es un `advmod` de la
    periferia que no disparó ningún operador. MOD se dispara con el verbo de
    la perífrasis, que en 'suele/quiere/va a + infinitivo' es la propia RAÍZ
    (ver `operadores.perifrasis_no_cubiertas`), así que el candidato es el
    lema del verbo. Devuelve None si no hay ninguno: entonces no es un hueco
    léxico y la corrección va a staging.
    """
    if operador == "MOD":
        return (ls.get("verb_lemma") or _lema_de(ls)) or None
    cubiertos = set()
    for spec in (ls.get("operadores") or {}).values():
        cubiertos.update(spec.get("origen_ids") or [])
    for p in ls.get("periferia") or []:
        if p.get("deprel") == "advmod" and p.get("id") not in cubiertos:
            return (p.get("lemma") or p.get("text") or "").lower() or None
    return None


def _confirma_operador(ls_nuevo, operador, accion, valor_correcto):
    ops = ls_nuevo.get("operadores") or {}
    if accion == "quitar":
        return operador not in ops
    spec = ops.get(operador)
    return spec is not None and spec.get("valor") == valor_correcto


def corregir_operador(res, sub_idx, operador, accion, valor_correcto,
                      reanalizar_fn, data_dir=None, config_path=None,
                      salida=lambda *_a: None) -> dict:
    """API no-interactiva (la usa la GUI) de la corrección de un operador.

    `accion` ∈ {'cambiar', 'quitar', 'anadir'}. GRRux decide SOLO la ruta —el
    usuario nunca elige archivo (regla de L5)—:

      · HUECO LÉXICO (falta un adverbio epistémico en la lista de STA, un
        negador, una perífrasis modal): se escribe EN VIVO en la lista/mapa
        de config con `# correccion_usuario` y se confirma por re-análisis;
        si el re-análisis no lo refleja, se revierte y cae a staging.
      · ERROR DE PARSE (el `Mood=Imp` que Stanza no da, un tiempo mal leído):
        no hay nada que escribir en un léxico —lo que falló es la lectura de
        una marca morfológica—, así que va a STAGING con la señal de origen y
        un mensaje honesto.

    TODO-OPERATORS-3: un override POR ORACIÓN en vivo (que arreglaría los
    casos de parse sin tocar ningún léxico) queda pendiente de diseño; hoy esa
    corrección se registra pero no se automatiza.
    """
    ls = _ls_de(res, sub_idx)
    oracion = res.get("oracion", "")
    ops = ls.get("operadores") or {}
    spec = ops.get(operador) or {}
    valor_predicho = spec.get("valor")
    senal = spec.get("origen", "")

    if operador not in VALORES_OPERADOR:
        return {"accion": "error", "detalle": f"operador desconocido: {operador}"}
    if accion != "quitar" and valor_correcto not in VALORES_OPERADOR[operador]:
        return {"accion": "error",
                "detalle": f"valor no válido para {operador}: {valor_correcto}"}

    destino = _CONFIG_OPERADOR.get((operador, valor_correcto)) if accion != "quitar" else None
    candidato = _candidato_lexico(ls, operador) if destino else None

    if destino and candidato:
        clase, nombre = destino
        if clase == "lista":
            token = anadir_a_lista_config("operadores", nombre, candidato, config_path)
        else:
            token = anadir_a_mapa_config(nombre, candidato, valor_correcto, config_path)
        if token is not None:
            _aplicar_en_memoria_config(
                nombre, candidato if clase == "lista" else (candidato, valor_correcto),
                seccion="operadores")
            salida(f"  Añadido a config ({nombre}); re-analizando para confirmar…")
            try:
                res_nuevo = reanalizar_fn(oracion)
                ok = _confirma_operador(_ls_de(res_nuevo, sub_idx), operador,
                                        accion, valor_correcto)
            except Exception as e:
                ok = False
                salida(f"  (el re-análisis falló: {e})")
            if ok:
                log_maestro({"oracion": oracion, "lema": candidato, "tipo": "operador",
                             "accion": "persistido", "destino": f"config:{nombre}",
                             "detalle": f"{operador}={valor_correcto} ({candidato})"},
                            data_dir)
                salida(f"  ✓ Corrección aplicada y verificada → config.yaml "
                       f"({nombre}, # correccion_usuario).")
                return {"accion": "persistido_operador", "operador": operador,
                        "valor": valor_correcto, "destino": f"config:{nombre}",
                        "lema": candidato}
            revert(token)
            stage_operador(oracion, operador, valor_predicho, valor_correcto, senal,
                           "el re-análisis no reflejó la corrección", data_dir)
            salida("  ⚠ La corrección se registró pero el análisis aún no la refleja — "
                   "quedará para revisión (staging), no se dejó en el archivo vivo.")
            return {"accion": "staging_no_confirmado_operador", "operador": operador}

    motivo = ("no hay lista de config donde quepa esta corrección"
              if accion == "quitar" or not destino
              else "no se identificó la palabra disparadora en la oración")
    stage_operador(oracion, operador, valor_predicho, valor_correcto, senal, motivo, data_dir)
    salida("  ⚠ Registrado para revisión (correcciones_operadores.csv); esta "
           "corrección no puede automatizarse aún (viene del análisis "
           "morfológico, no de un léxico).")
    return {"accion": "staging_operador", "operador": operador,
            "valor": valor_correcto, "motivo": motivo}


def _flujo_operador(oracion, ls, sub_idx, reanalizar_fn, entrada, salida,
                    data_dir, config_path):
    ops = ls.get("operadores") or {}
    salida("\n  Operadores detectados:")
    if not ops:
        salida("    (ninguno)")
    listado = list(ops.items())
    for i, (op, spec) in enumerate(listado, 1):
        salida(f"    {i}) {op} = {spec.get('valor')}   ← {spec.get('origen')}")
    ausentes = [op for op in VALORES_OPERADOR if op not in ops]
    base = len(listado)
    for j, op in enumerate(ausentes, base + 1):
        salida(f"    {j}) {op} (ausente — añadir)")
    salida("    Esc) Cancelar")

    sel = _pedir(f"  ¿Cuál está mal? [1-{base + len(ausentes)}]:", entrada, salida)
    if sel is _CANCEL:
        salida("  (corrección cancelada, sin efectos)")
        return {"accion": "cancelado"}
    if not sel.isdigit() or not (1 <= int(sel) <= base + len(ausentes)):
        salida("  opción no reconocida — cancelado")
        return {"accion": "cancelado"}

    idx = int(sel)
    if idx <= base:
        operador = listado[idx - 1][0]
        salida(f"\n  {operador} = {listado[idx - 1][1].get('valor')}. ¿Qué hacemos?")
        salida("    1) Cambiar su valor")
        salida("    2) Quitarlo (no debería estar)")
        salida("    Esc) Cancelar")
        que = _pedir("  Elige [1/2]:", entrada, salida)
        if que is _CANCEL or que not in ("1", "2"):
            salida("  (corrección cancelada, sin efectos)")
            return {"accion": "cancelado"}
        if que == "2":
            return corregir_operador(
                {"oracion": oracion, "ls_lista": [ls]}, 0, operador, "quitar", None,
                reanalizar_fn, data_dir, config_path, salida)
        accion = "cambiar"
    else:
        operador = ausentes[idx - base - 1]
        accion = "anadir"

    valores = VALORES_OPERADOR[operador]
    salida(f"\n  Valor correcto de {operador}:")
    for i, v in enumerate(valores, 1):
        salida(f"    {i}) {v}")
    salida("    Esc) Cancelar")
    sv = _pedir(f"  Elige [1-{len(valores)}]:", entrada, salida)
    if sv is _CANCEL or not sv.isdigit() or not (1 <= int(sv) <= len(valores)):
        salida("  (corrección cancelada, sin efectos)")
        return {"accion": "cancelado"}

    return corregir_operador({"oracion": oracion, "ls_lista": [ls]}, 0, operador,
                             accion, valores[int(sv) - 1], reanalizar_fn,
                             data_dir, config_path, salida)


def _confirma_enrutado(ls_nuevo, texto, destino_clave):
    if destino_clave.startswith("periferia"):
        return any(p.get("text") == texto for p in (ls_nuevo.get("periferia") or []))
    if destino_clave == "argumento_core":
        # ENRUTADO-DATIVO (2026-08-19): estar en el core NO basta. El
        # 2026-07-14 "maria" entró al core como Meta y aun así quedó FUERA de
        # la EL ("argumento 'maria' sin posición licenciada"), y esta
        # confirmación dio la corrección por buena y la persistió. Un
        # argumento del core que no ocupa una posición en la EL no es un
        # argumento: se exige que el re-análisis le haya asignado variable.
        ids = [c.get("id") for c in (ls_nuevo.get("core") or [])
               if c.get("text") == texto]
        if not ids:
            return False
        id_a_var = ls_nuevo.get("id_a_var") or {}
        return any(i in id_a_var for i in ids)
    if destino_clave == "agx":
        return any(a.get("clitico") == texto for a in (ls_nuevo.get("agx") or []))
    return False


# ── util ───────────────────────────────────────────────────────────────────
def _wrappers_fijos_periferia() -> set[str]:
    """G3 §1.2 — nombres de predicado (sin apóstrofe) de los wrappers FIJOS
    de la Etapa PERIFERIA, LEÍDOS de las tablas reales de `wrappers_ls.py`
    (nunca copiados a mano, para no desincronizarse si Julian las edita).
    Quedan FUERA a propósito los wrappers 'genérico' (preposición/lema
    arbitrario cuando no hay entrada en tabla) y 'manera' (SIEMPRE usa el
    lema crudo, sin tabla) -- no son cubribles por lista estática; de ahí
    que el lema explícito (capa 1, parámetro `verb_lemma` de los
    `corregir_*`) sea la vía primaria, y esta lista sea solo la red de
    fallback."""
    from . import wrappers_ls as w
    nombres = {w.DEFAULT_LOCATIVO_FALLBACK, w.DEFAULT_FRECUENCIA_DISTRIBUTIVA,
              w.DEFAULT_RAZON_FALLBACK, w.DEFAULT_CONCESION_FALLBACK,
              w.DEFAULT_CONDICION_FALLBACK, "for", "during", "at"}
    for tabla in (w.DEFAULT_LOCATIVOS, w.DEFAULT_TEMPORALES_SIMPLES,
                 w.DEFAULT_ADVERBIOS_MONOVALENTES, w.DEFAULT_ASPECTUALES,
                 w.DEFAULT_EPISTEMICOS, w.DEFAULT_FRECUENCIA_ADVERBIOS,
                 w.DEFAULT_RAZON, w.DEFAULT_CONCESION, w.DEFAULT_CONDICION):
        nombres.update(tabla.values())
    return nombres


_PRED_NO_LEMA = {"do", "have", "be-in", "be-at", "be-on", "be-under", "be-near",
                 "be-behind", "be-between", "be-beside", "be-in-front-of",
                 "for", "during", "before", "after", "until", "since", "at",
                 "yesterday", "today", "now", "tomorrow", "last.night",
                 "pred"} | _wrappers_fijos_periferia()


def _lema_de(ls):
    """Lema del verbo principal.

    PRIMERO el dato directo: `verb_lemma`, que `rrg_ls_mapper` expone desde
    OPERATORS_2 §3 -- el mapper conoce el verbo raíz, no hay por qué
    deducirlo de la representación.

    Si falta (un `ls` viejo, reconstruido de un .conllu o un stub de test) se
    conserva la heurística histórica: el primer predicado primado que NO sea
    un primitivo/wrapper (do'/have'/be-in'/for'/…) -- en
    do'(Juan,[correr'(Juan)]) el lema es 'correr', no 'do'. Esa heurística es
    la que fallaba con las ditransitivas ([do'…] CAUSE [BECOME have'…]): no
    contienen NINGÚN predicado léxico, así que caía al último recurso,
    `ls_type`, que es un nombre de CLASE y no un verbo. Ese último recurso
    sigue ahí, y sigue vigilado por `_lema_no_identificable`, que impide que
    llegue nunca a un léxico vivo."""
    directo = (ls.get("verb_lemma") or "").strip()
    if directo:
        return directo
    for m in re.finditer(r"([\wÀ-ÿ.\-]+)'", ls.get("ls_lexical", "") or ""):
        if m.group(1).lower() not in _PRED_NO_LEMA:
            return m.group(1)
    return (ls.get("ls_type", "") or "").lower()


def _lema_no_identificable(lema: str) -> bool:
    """G3 §1.3 — guardia anti-basura: ¿`lema` es en realidad un nombre de
    clase aspectual colado por el fallback de `_lema_de` (`ls_type`) en vez
    de un verbo real? Compara contra `CLASES` (claves internas) y
    `CLASE_ES` (etiquetas legibles), sin distinguir mayúsculas."""
    l = (lema or "").strip().lower()
    if not l:
        return True
    return l in CLASES or l in {v.lower() for v in CLASE_ES.values()}


def _tokens_de_oracion(oracion):
    return re.findall(r"[\wÀ-ÿ]+", oracion or "")
