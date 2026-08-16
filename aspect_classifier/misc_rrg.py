"""Canal MISC (Fase LINKING, Etapa L2) — vuelca los veredictos del mapper a
la columna MISC del `.conllu`, token por token, PRESERVANDO lo que ya
hubiera ahí. Es el CONTRATO que la futura capa 'es' de `ud2rrg.py` (Etapa
L3, prompt posterior) leerá para no tener que re-derivar core/periferia por
su cuenta — Etapa 1 (`nucleo_periferia`) sigue siendo la ÚNICA fuente de
verdad.

Formato UD estándar: `Clave1=Valor1|Clave2=Valor2` (o `_` si no hay nada).
Vocabulario mínimo (namespace `RRG*`, para no chocar con MISC de terceros):

    RRGRole=CoreArg     | RRGMacrorole=<Actor|Undergoer|...|NMR(dativo)>
                        | RRGVar=x|y|z
        En el token del argumento nuclear (nsubj/obj/obl:agent/obl:arg...).

    RRGRole=Periphery   | RRGType=<aspectual|manera|locativo|temporal|
                          frecuencia|razon|concesion|condicion|epistemico|
                          generico>  (Etapa PERIFERIA, 2026-07-13: NUNCA
                          "otro"/"modo" -- ver nucleo_periferia._tipo_periferia)
                        | RRGStratum=<nucleo|centro|clausula>  (Etapa
                          PERIFERIA: ANCLAJE del árbol -- ud2rrg.py cuelga la
                          rama -PERI de NUC/CORE/CLAUSE según esta clave, NO
                          según RRGType. Reemplaza la regla L3
                          "temporal→CLAUSE" por scope-driven.)
                        | RRGWrap=<for|during|be-in|yesterday|...>  (solo si
                          wrappers_ls envolvió ese item; predicado SIN el
                          apóstrofe final)
                        | RRGDetached=si  (Etapa L4.5 §2, solo temporal:
                          periferia en posición dislocada izquierda -- LDP/
                          PrDP en vez de -PERI@CLAUSE; ver
                          nucleo_periferia._es_destacado_inicial)
        En el token cabeza del adjunto periférico.

    RRGRole=AGX         | RRGDoblado=<si|no>  (solo se usa con fuente=dativo)
                        | RRGArgVar=x|y|z  (solo si doblado: variable del
                          sintagma pleno que materializa el mismo argumento)
                        | RRGAgxFuente=<dativo|acusativo|reflexivo|se_pasivo|
                          se_impersonal|se_aspectual>  (L4.5 §3; L5 §1 añade
                          acusativo/reflexivo para me/te/nos/os)
        En el token del CLÍTICO (dativo le/les, o "se"/me/te/nos/os
        reflejo-pasivo/impersonal/aspectual) — nunca genera su propia
        variable, es concordancia (ver nucleo_periferia._detectar_agx).
        Una oración puede tener VARIOS tokens AGX de fuentes distintas
        (p.ej. dativo "les" + "se" pasivo en la misma cláusula) — cada uno
        con su propia entrada; `ls_data['agx']` es una LISTA desde L4.5
        (antes L4: dict único|None).

    RRGRole=Impersonal
        En el token raíz de un verbo impersonal/pleonástico (llover...).

    RRGImplicitActor=<1sg|3pl|...>
        En el token raíz cuando el sujeto es pro-drop (sin realización
        sintáctica) — la etiqueta es la misma que `actor_implicito.etiqueta`.

    RRGAnalyzed=si
        En el token raíz, SIEMPRE que gruxx analizó la oración (L5 §1).
        `ud2rrg._es_conllu_analizado` la usa para subordinar su fallback de
        clíticos al MISC (una sola fuente de verdad para AGX).

    RRGThemRel=<Efectuador|Poseedor|Tema|Emisor|Receptor|Contenido|...>
        Opcional, se fusiona con `RRGRole=CoreArg` en el MISMO token (Etapa
        L2.5, `ditransitivas.py`): el rol temático específico por posición
        en la LS (continuum de Van Valin 2005:58, ver
        `ditransitivas.cargar_continuum`), más fino que `RRGMacrorole`.
        "Poseedor" (decisión de Julian, L3): primer argumento de `have'` en
        transferencia/benefactiva, ceñido a la etiqueta del continuum
        (Van Valin 2005:58 lista POSEEDOR para el primer arg. de
        `have'(y,z)`, no "Recipiente" — ver ditransitivas.py). La
        comunicación (que no tiene `have'`) conserva "Receptor".
        Ej.: "María" en "Juan le dio un regalo a María" →
        `RRGRole=CoreArg|RRGMacrorole=NMR(dativo)|RRGVar=y|RRGThemRel=Poseedor`.

Funciones puras (salvo `escribir_misc_en_conllu`, que hace I/O de archivo
explícito — sin Stanza, sin modelos).
"""

from .rrg_variables import (reject_legacy_notation, validate_mapping_values,
                            validate_variable)


def fusionar_misc(existente: str, nuevas: dict) -> str:
    """Combina el MISC ya presente en la fila CoNLL-U con las claves nuevas
    (las nuevas ganan si hay colisión — solo puede pasar si esta función se
    corre dos veces sobre el mismo archivo, idempotente)."""
    pares = {}
    if existente and existente != "_":
        for par in existente.split("|"):
            if "=" in par:
                k, v = par.split("=", 1)
                pares[k] = v
    for campo in ("RRGVar", "RRGArgVar"):
        if campo in pares:
            validate_variable(pares[campo], field=campo)
        if campo in nuevas and nuevas[campo] is not None:
            validate_variable(nuevas[campo], field=campo)
    pares.update(nuevas)
    if not pares:
        return "_"
    return "|".join(f"{k}={v}" for k, v in pares.items())


def anotaciones_misc(ls: dict) -> dict[int, dict[str, str]]:
    """Deriva las anotaciones MISC por token a partir del dict que devuelve
    `rrg_ls_mapper.map_sentence_to_ls` (ya trae core/periferia/agx/
    impersonal/actor_implicito/wrappers/id_a_var/root_id).

    Returns:
        {token_id: {ClaveRRG: valor, ...}, ...} — sin tocar el archivo.
    """
    anot: dict[int, dict[str, str]] = {}

    def _add(tid, **kv):
        if tid is None:
            return
        limpio = {k: v for k, v in kv.items() if v is not None}
        if limpio:
            anot.setdefault(tid, {}).update(limpio)

    id_a_var = ls.get("id_a_var") or {}
    validate_mapping_values(id_a_var, field="id_a_var")

    for c in ls.get("core") or []:
        _add(c["id"], RRGRole="CoreArg", RRGMacrorole=c["macropapel"],
             RRGVar=id_a_var.get(c["id"]))

    wrap_por_id = {w["id"]: w["pred"].rstrip("'")
                  for w in (ls.get("wrappers") or [])
                  if w.get("aplicado") and w.get("id") is not None}
    for p in ls.get("periferia") or []:
        _add(p["id"], RRGRole="Periphery", RRGType=p["tipo"],
             RRGStratum=p.get("estrato"),
             RRGWrap=wrap_por_id.get(p["id"]),
             RRGDetached=("si" if p.get("destacado_inicial") else None))

    # Fase L4.5 §3: 'agx' es una LISTA (antes L4: dict único|None) -- una
    # oración puede tener varios AGX (p.ej. dativo + se-pasivo en la misma
    # cláusula). Cada entrada vive en SU PROPIO token (clitico_id distinto),
    # así que no hay colisión de escritura entre entradas.
    for agx in (ls.get("agx") or []):
        if agx.get("clitico_id") is None:
            continue
        arg_var = (id_a_var.get(agx["arg_id"])
                  if agx.get("arg_id") is not None else None)
        _add(agx["clitico_id"], RRGRole="AGX",
             RRGDoblado=("si" if agx.get("doblado") else "no"),
             RRGArgVar=arg_var, RRGAgxFuente=agx.get("fuente"))

    # Etapa L2.5 (ditransitivas.py): rol temático específico por posición,
    # se fusiona con el CoreArg ya anotado arriba (mismo token).
    for tid, rol in (ls.get("roles_tematicos") or {}).items():
        _add(tid, RRGThemRel=rol)

    root_id = ls.get("root_id")
    if ls.get("impersonal"):
        _add(root_id, RRGRole="Impersonal")
    elif ls.get("actor_implicito"):
        _add(root_id, RRGImplicitActor=ls["actor_implicito"]["etiqueta"])

    # Fase L5 §1 (conciliación AGX): marca en la RAÍZ de que este .conllu lo
    # analizó gruxx (canal MISC poblado). ud2rrg._es_conllu_analizado la lee
    # para SUBORDINAR su fallback de clíticos (is_clitic_pronoun) al MISC:
    # con esta marca, el MISC es la única fuente de verdad para AGX y ud2rrg
    # no inventa nodos AGX por su cuenta. Se pone siempre (aunque la raíz no
    # tenga otra anotación), para que una oración sin clíticos ni pro-drop
    # igual quede identificada como analizada.
    _add(root_id, RRGAnalyzed="si")

    return anot


def leer_ls_desde_misc(bloque: str) -> dict:
    """Fase LINKING, Etapa L4 — inverso best-effort de `anotaciones_misc`:
    reconstruye, a partir del canal MISC ya escrito en un bloque `.conllu`
    (una oración), un dict compatible con
    `aspect_classifier.completeness.verificar`. Uso: modo ".conllu directo"
    de `gruxx_ai1.py`, donde no se re-corre el mapper — el `.conllu` ya
    anotado es la única fuente de verdad disponible.

    Limitación documentada: 'wrappers' solo recupera los items YA envueltos
    (RRGWrap presente); un item de periferia detectado pero deliberadamente
    sin envolver (frecuencia, beneficiario no disparado) es indistinguible
    de uno sin wrapper en absoluto — ambos caen al chequeo "solo presencia
    de rama -PERI" de `completeness._chequear_periferia`, que es
    precisamente el comportamiento correcto para ese caso (nunca error).
    """
    for linea in bloque.split("\n"):
        if linea.startswith("#") and "rrg_ls" in linea.lower():
            reject_legacy_notation(linea, context="el comentario CoNLL-U de EL formal")

    variables: dict[str, str] = {}
    id_a_var: dict[int, str] = {}
    core: list[dict] = []
    periferia: list[dict] = []
    wrappers: list[dict] = []
    agx_list: list[dict] = []   # L4.5 §3: lista, no dict único
    actor_implicito = None
    impersonal = False

    for linea in bloque.split("\n"):
        if not linea.strip() or linea.startswith("#") or "\t" not in linea:
            continue
        cols = linea.split("\t")
        if len(cols) != 10 or not cols[0].isdigit():
            continue
        tid, form, misc = int(cols[0]), cols[1], cols[9]
        if not misc or misc == "_":
            continue
        pares = dict(p.split("=", 1) for p in misc.split("|") if "=" in p)
        for campo in ("RRGVar", "RRGArgVar"):
            if pares.get(campo):
                validate_variable(pares[campo], field=f"CoNLL-U {campo}")

        role = pares.get("RRGRole")
        if role == "CoreArg":
            var = pares.get("RRGVar")
            core.append({"id": tid, "text": form, "deprel": "",
                        "macropapel": pares.get("RRGMacrorole", "")})
            if var:
                variables[var] = form
                id_a_var[tid] = var
        elif role == "Periphery":
            tipo = pares.get("RRGType", "generico")
            estrato = pares.get("RRGStratum", "centro")
            wrap = pares.get("RRGWrap")
            periferia.append({"id": tid, "text": form, "deprel": "", "tipo": tipo,
                              "estrato": estrato, "case": None, "lemma": form.lower(),
                              "destacado_inicial": pares.get("RRGDetached") == "si"})
            if wrap:
                wrappers.append({"capa": tipo, "id": tid, "trigger": form,
                                 "pred": f"{wrap}'", "aplicado": True})
        elif role == "AGX":
            doblado = pares.get("RRGDoblado") == "si"
            fuente = pares.get("RRGAgxFuente", "dativo")
            agx_list.append({"clitico": form, "doblado": doblado, "arg_id": None,
                            "clitico_id": tid, "fuente": fuente})
            # Bleed-through documentado (Etapa L2, anotaciones_misc): sin
            # doblado, el propio clítico DATIVO también pasó por el bucle de
            # core (dativo["morfologico"]) antes de que este bloque
            # sobreescribiera RRGRole a "AGX" -- RRGVar/RRGMacrorole del
            # paso anterior quedan en el MISC final. Solo aplica a la fuente
            # dativo (las fuentes se_* nunca pasan por el bucle de core).
            # Sin esto, el chequeo de satisfacción "clítico solo -> AGX" de
            # completeness._chequear_argumentos no tendría variable que
            # verificar.
            var = pares.get("RRGVar")
            if var and not doblado and fuente == "dativo":
                variables[var] = form
                id_a_var[tid] = var

        if role == "Impersonal":
            impersonal = True
        if "RRGImplicitActor" in pares:
            etiqueta = pares["RRGImplicitActor"]
            actor_implicito = {"etiqueta": etiqueta}
            variables.setdefault("x", etiqueta)

    return {"variables": variables, "id_a_var": id_a_var, "core": core,
           "periferia": periferia, "agx": agx_list, "actor_implicito": actor_implicito,
           "impersonal": impersonal, "wrappers": wrappers}


def escribir_misc_en_conllu(conllu_path: str,
                            anotaciones_por_oracion: list[dict]) -> None:
    """Reescribe el `.conllu` en `conllu_path` fusionando MISC por token.

    `anotaciones_por_oracion[i]` es el dict que devuelve `anotaciones_misc`
    para la i-ésima oración del archivo (mismo orden que las líneas
    `# text = `, igual que `gruxx_ai1.inyectar_metadata_rrg`).
    """
    with open(conllu_path, encoding="utf-8") as f:
        lineas = f.readlines()

    # L5 §1: una oración está "analizada" por gruxx si su dict de anotaciones
    # trae RRGAnalyzed en algún token (la raíz siempre lo lleva, ver
    # anotaciones_misc). En ese caso se estampa RRGAnalyzed=si en TODOS sus
    # tokens (incluidos los verbos de cláusulas embebidas), para que
    # ud2rrg._es_conllu_analizado subordine su fallback de clíticos en TODA la
    # oración, no solo en la cláusula principal (única fuente de verdad AGX).
    def _analizada(anot):
        return any("RRGAnalyzed" in v for v in anot.values())

    actualizadas = []
    idx_oracion = -1
    for linea in lineas:
        if linea.startswith("# text = "):
            idx_oracion += 1
        es_token = (not linea.startswith("#") and linea.strip()
                   and "\t" in linea)
        if es_token and 0 <= idx_oracion < len(anotaciones_por_oracion):
            cols = linea.rstrip("\n").split("\t")
            if len(cols) == 10 and cols[0].isdigit():
                anot = anotaciones_por_oracion[idx_oracion]
                nuevas = dict(anot.get(int(cols[0])) or {})
                if _analizada(anot):
                    nuevas.setdefault("RRGAnalyzed", "si")
                if nuevas:
                    cols[9] = fusionar_misc(cols[9], nuevas)
                    linea = "\t".join(cols) + "\n"
        actualizadas.append(linea)

    with open(conllu_path, "w", encoding="utf-8") as f:
        f.writelines(actualizadas)
