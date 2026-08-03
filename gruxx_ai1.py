"""
rrg_interactivo.py
==================
Pipeline integrado GRR:
  1. Stanza analiza la oración y produce CoNLL-U base
  2. rrg_ls_mapper genera la Estructura Lógica (LS) con pipeline de 3 niveles:
       Nivel 1 — léxico estático (VERB_CLASSES)
       Nivel 2 — clasificador morfosintáctico (rrg_morph_classifier)
       Nivel 3 — fallback LLM local (rrg_llm_fallback, via Ollama/gemma)
  3. Los metadatos rrg_* se inyectan como comentarios en el .conllu
  4. ud2rrg (vía convertir.py) genera el árbol sintáctico RRG
  5. La salida combina LS + árbol en pantalla
  6. Opcional: se guarda todo en un archivo .txt

Uso:
  python3 rrg_interactivo.py
  → El script pregunta el modo al iniciar:
      [1] Una oración por vez (bucle interactivo)
      [2] Varias oraciones en terminal (batch)
      [3] Cargar oraciones desde archivo .txt (batch archivo)
  → También acepta un .conllu como argumento:
      python3 rrg_interactivo.py archivo.conllu
"""

import sys
import os
import subprocess
import stanza
from stanza.utils.conll import CoNLL
from datetime import datetime
from rrg_ls_mapper import map_sentence_to_ls
from aspect_classifier.display_grr import render_bloque
from aspect_classifier import glosario
from aspect_classifier.correccion import bucle_correccion as _bucle_correccion

# ---------------------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------------------
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
CONLLU_PATH  = os.path.join(SCRIPT_DIR, "input_estudiante.conllu")
CONVERTIR_PY = os.path.join(SCRIPT_DIR, "convertir.py")
LANG         = "es"

SEP  = "=" * 56
SEP2 = "═" * 56

# Con --verbose se muestran los bloques de depuración (CoNLL-U enriquecido
# y ESTRUCTURAS LÓGICAS); por defecto la salida es solo el análisis útil.
VERBOSE = False


# ---------------------------------------------------------------------------
# UTILIDADES — ANÁLISIS
# ---------------------------------------------------------------------------
def cargar_pipeline_stanza(lang: str):
    try:
        nlp = stanza.Pipeline(lang=lang,
                              processors='tokenize,mwt,pos,lemma,depparse',
                              verbose=False)
    except Exception:
        print(f"[INFO] Descargando modelo Stanza '{lang}'...")
        stanza.download(lang)
        nlp = stanza.Pipeline(lang=lang,
                              processors='tokenize,mwt,pos,lemma,depparse',
                              verbose=False)
    return nlp


def limpiar_conllu_stanza(conllu_path: str):
    LEMA_FIXES = {'comir': 'comer'}
    MISC_STRIP = {'start_char', 'end_char'}
    with open(conllu_path, 'r', encoding='utf-8') as f:
        content = f.read()
    bloques_raw     = content.strip().split('\n\n')
    bloques_limpios = []
    sent_counter    = 0
    for bloque in bloques_raw:
        if not bloque.strip():
            continue
        lines       = bloque.split('\n')
        comentarios = [l for l in lines if l.startswith('#')]
        tokens      = [l for l in lines if not l.startswith('#') and l.strip()]
        text_line   = next((l for l in comentarios if l.startswith('# text')), None)
        sent_counter += 1
        nuevos_comentarios = [f'# sent_id = {sent_counter}']
        if text_line:
            nuevos_comentarios.append(text_line)
        for c in comentarios:
            if not c.startswith('# sent_id') and not c.startswith('# text'):
                nuevos_comentarios.append(c)
        tokens_limpios = []
        for tok in tokens:
            cols = tok.split('\t')
            if len(cols) == 10:
                cols[2] = LEMA_FIXES.get(cols[2], cols[2])
                cols[4] = '_'
                misc    = cols[9]
                if misc != '_':
                    pares   = [p for p in misc.split('|')
                               if p.split('=')[0] not in MISC_STRIP]
                    cols[9] = '|'.join(pares) if pares else '_'
                tokens_limpios.append('\t'.join(cols))
            else:
                tokens_limpios.append(tok)
        bloques_limpios.append('\n'.join(nuevos_comentarios + tokens_limpios))
    with open(conllu_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(bloques_limpios) + '\n\n')


def inyectar_metadata_rrg(conllu_path: str, doc, ls_data_por_oracion: list):
    with open(conllu_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    updated      = []
    sentence_idx = 0
    for line in lines:
        updated.append(line)
        if line.startswith('# text = ') and sentence_idx < len(ls_data_por_oracion):
            ls = ls_data_por_oracion[sentence_idx]
            updated.append(f"# rrg_ls_type = {ls['ls_type']}\n")
            updated.append(f"# rrg_ls = {ls['ls_formal']}\n")
            updated.append(f"# rrg_ls_lex = {ls['ls_lexical']}\n")
            if ls['args_map']:
                updated.append(f"# rrg_args = {ls['args_map']}\n")
            sentence_idx += 1
    with open(conllu_path, 'w', encoding='utf-8') as f:
        f.writelines(updated)

    # Fase LINKING, Etapa L2: canal MISC por token (contrato que leerá la
    # futura capa 'es' de ud2rrg.py). Segunda pasada porque opera sobre el
    # archivo ya reescrito arriba (mismos offsets de línea que sentence_idx).
    from aspect_classifier.misc_rrg import anotaciones_misc, escribir_misc_en_conllu
    anotaciones_por_oracion = [anotaciones_misc(ls) for ls in ls_data_por_oracion]
    escribir_misc_en_conllu(conllu_path, anotaciones_por_oracion)


def correr_ud2rrg(conllu_path: str) -> tuple[str, str]:
    if not os.path.exists(CONVERTIR_PY):
        return (f"[ud2rrg no encontrado]\nRuta: {CONVERTIR_PY}", "")
    proc = subprocess.run(
        [sys.executable, CONVERTIR_PY, conllu_path, LANG],
        capture_output=True, text=True)
    return proc.stdout, proc.stderr


def _arboles_inprocess(conllu_path: str, language: str = LANG) -> list:
    """Fase LINKING, Etapa L4 — reconstruye el árbol RRG de cada oración del
    `.conllu` IN-PROCESS (import directo de `ud2rrg`, mismos pasos que
    `convertir.py`: transform + add_traces_to_rrg), SOLO como insumo del
    checker de completeness (`aspect_classifier.completeness.verificar`
    necesita el objeto ParentedTree, no el ASCII-art).

    Elección de diseño (documentada en prompt_opus48_linking_L4.md §2): el
    render en pantalla/.txt sigue viniendo del subprocess de `convertir.py`
    vía `correr_ud2rrg`, sin tocarlo — se paga el coste de convertir dos
    veces (subprocess + in-process) a cambio de cero riesgo sobre el
    formato ASCII ya validado. Cada oración se intenta de forma
    INDIVIDUAL: una oración mala no debe tumbar las demás ni el programa.
    """
    import ud2rrg as converter
    from conllu import parse_tree_incr

    arboles = []
    with open(conllu_path, encoding='utf-8') as f:
        for udtree in parse_tree_incr(f):
            try:
                sent = []
                original_sent_list = [x for x in udtree.serialize().split('\n')
                                      if x != '' and not x.startswith('#') and '\t' in x]
                for word in original_sent_list:
                    w = word.split('\t')[1]
                    sent.append(w.replace(' ', '_'))
                rrgtree = converter.transform(udtree, language, layer='SENTENCE')
                try:
                    rrgtree = converter.add_traces_to_rrg(udtree, rrgtree, sent)
                except AssertionError:
                    pass
                arboles.append(rrgtree)
            except Exception:
                arboles.append(None)
    return arboles


def _completeness_por_oracion(conllu_path: str, ls_data_lista: list[dict],
                               language: str = LANG) -> list[dict]:
    """Corre `completeness.verificar` para cada (sub)oración, alineando
    `ls_data_lista` (orden de `doc.sentences`/bloques del .conllu) con los
    árboles in-process. Individual: si la reconstrucción del árbol falla
    para el archivo entero, cada oración cae a 'sin_arbol' (nunca lanza)."""
    from aspect_classifier.completeness import verificar
    try:
        arboles = _arboles_inprocess(conllu_path, language)
    except Exception:
        arboles = []
    resultado = []
    for i, ls in enumerate(ls_data_lista):
        arbol = arboles[i] if i < len(arboles) else None
        resultado.append(verificar(ls, arbol))
    return resultado


def _dividir_arboles_ud2rrg(stdout: str) -> list[str]:
    import re
    bloques = re.split(r'--- Oración \d+ ---\n?', stdout)
    return [b.strip() for b in bloques[1:] if b.strip()]


# ---------------------------------------------------------------------------
# UTILIDADES — GUARDADO
# ---------------------------------------------------------------------------
def _extraer_arbol(stdout_ud2rrg: str) -> str:
    lineas = []
    copiar = False
    for linea in stdout_ud2rrg.splitlines():
        t = linea.strip()
        if t.startswith("┌") or t.startswith("│") or t.startswith("└"):
            copiar = True
        if copiar:
            lineas.append(linea)
    return "\n".join(lineas).rstrip()


def _nombre_archivo(texto: str) -> str:
    palabras = texto.strip().rstrip("?.!").split()[:5]
    nombre   = "_".join(palabras).lower()
    tabla    = str.maketrans('áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN')
    nombre   = nombre.translate(tabla)
    nombre   = "".join(c if c.isalnum() or c == '_' else '' for c in nombre)
    return f"analisis_{nombre}.txt"


def _nombre_archivo_batch(origen: str) -> str:
    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
    if origen and origen not in ('terminal', 'sesion_interactiva'):
        base  = os.path.splitext(os.path.basename(origen))[0]
        tabla = str.maketrans('áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN')
        base  = base.translate(tabla)
        base  = "".join(c if c.isalnum() or c == '_' else '_' for c in base)
        return f"batch_{base}_{fecha}.txt"
    prefijo = 'sesion' if origen == 'sesion_interactiva' else 'batch_terminal'
    return f"{prefijo}_{fecha}.txt"


def _encabezado_txt(titulo: str, origen: str, fecha: str, extra: str = '') -> str:
    return (
        "=" * 60 + "\n"
        f"  {titulo}\n"
        f"  Fuente  : {origen}\n"
        f"  Fecha   : {fecha}\n"
        + (f"  {extra}\n" if extra else "")
        + "=" * 60 + "\n\n"
        "NOTA PARA ABRIR CORRECTAMENTE:\n"
        "  • Usa un editor de texto plano con fuente MONOESPACIADA\n"
        "  • Fuentes: Courier New, Consolas, DejaVu Sans Mono\n"
        "  • En Word/LibreOffice: cuadro de texto Courier New 9-10pt\n"
        "\n" + "=" * 60 + "\n\n"
    )


def _guardar_resultados(nombre_archivo: str, titulo: str, origen: str,
                        resultados: list[dict]):
    """Núcleo de guardado compartido por todos los modos."""
    fecha  = datetime.now().strftime("%Y-%m-%d %H:%M")
    extra  = f"Total   : {len(resultados)} oración(es)" if len(resultados) > 1 else ''
    bloques = []

    for n, res in enumerate(resultados, start=1):
        enc   = (f"{'═' * 60}\n"
                 f"  ORACIÓN {n}: {res['oracion']}\n"
                 f"{'═' * 60}\n\n")
        arboles       = _dividir_arboles_ud2rrg(res['stdout'])
        ls_lista      = res['ls_lista']
        completeness  = res.get('completeness') or []
        total_sub = max(len(ls_lista), len(arboles))
        cuerpo    = ""
        for i in range(total_sub):
            if total_sub > 1:
                cuerpo += f"  — Sub-oración {i+1} —\n\n"
            ls   = ls_lista[i] if i < len(ls_lista) else {}
            arb  = _extraer_arbol(arboles[i]) if i < len(arboles) else None
            comp = completeness[i] if i < len(completeness) else None
            # Mismo orden GRR que en pantalla (§2): árbol → EL léxica → resto.
            cuerpo += render_bloque(ls, arb, comp, verbose=VERBOSE) + "\n\n"
        bloques.append(enc + cuerpo)

    with open(nombre_archivo, 'w', encoding='utf-8') as f:
        f.write(_encabezado_txt(titulo, origen, fecha, extra))
        f.write("\n".join(bloques))

    print(f"[OK] Guardado en: {nombre_archivo}")


def _preguntar_guardar_batch(origen: str, resultados: list[dict], reanalizar=None):
    """
    Pregunta si guardar y espera respuesta.
    flush() garantiza que el prompt aparezca antes de leer la respuesta.
    """
    # Corrección en batch (§5): se ofrece AL FINAL, por oración elegida por
    # número (nunca interrumpe sola). Solo si hay con qué re-analizar.
    if reanalizar is not None:
        while True:
            print()
            sys.stdout.flush()
            try:
                r = input(f"¿Corregir alguna oración? (número 1-{len(resultados)} "
                          "o Enter para omitir): ").strip()
            except EOFError:
                break
            if not r or not r.isdigit() or not (1 <= int(r) <= len(resultados)):
                break
            res_sel = resultados[int(r) - 1]
            sub = _elegir_suboracion(res_sel)
            if sub is not None:
                _bucle_correccion(res_sel, reanalizar, sub_idx=sub)

    print()
    sys.stdout.flush()
    try:
        resp = input("¿Guardar el análisis completo en .txt? (s/n): ").strip().lower()
    except EOFError:
        print("[Info] Sin entrada — análisis no guardado.")
        return
    if resp in ("s", "si", "sí", "y", "yes"):
        _guardar_resultados(
            _nombre_archivo_batch(origen),
            "ANÁLISIS GRR EN BATCH — ud2rrg + rrg_ls_mapper",
            origen,
            resultados
        )
    else:
        print("[Info] Análisis no guardado.")


def guardar_analisis(origen: str, ls_data_lista: list, stdout_ud2rrg: str,
                     completeness: list | None = None):
    """Guarda el análisis de una sola oración (o de un .conllu completo,
    modo ".conllu directo")."""
    _guardar_resultados(
        _nombre_archivo(origen),
        "ANÁLISIS GRR — ud2rrg + rrg_ls_mapper",
        origen,
        [{'oracion': origen, 'ls_lista': ls_data_lista, 'stdout': stdout_ud2rrg,
          'completeness': completeness or []}]
    )


# ---------------------------------------------------------------------------
# MODO ARCHIVO: leer LS de .conllu ya anotado
# ---------------------------------------------------------------------------
def leer_ls_desde_conllu(conllu_path: str) -> list[dict]:
    from aspect_classifier.misc_rrg import leer_ls_desde_misc
    resultado = []
    with open(conllu_path, 'r', encoding='utf-8') as f:
        content = f.read()
    for bloque in content.strip().split('\n\n'):
        if not bloque.strip():
            continue
        ls = {'ls_type': 'desconocido', 'ls_formal': '',
              'ls_lexical': '', 'args_map': '', 'variables': {}}
        for line in bloque.split('\n'):
            if   line.startswith('# rrg_ls_type'): ls['ls_type']    = line.split('=',1)[1].strip()
            elif line.startswith('# rrg_ls_lex'):  ls['ls_lexical'] = line.split('=',1)[1].strip()
            elif line.startswith('# rrg_ls '):     ls['ls_formal']  = line.split('=',1)[1].strip()
            elif line.startswith('# rrg_args'):    ls['args_map']   = line.split('=',1)[1].strip()
        if ls['ls_formal'] or ls['ls_lexical']:
            # Modo ".conllu directo" (L4): el checker de completeness
            # necesita los campos estructurados (core/periferia/agx/...),
            # que solo viven en el canal MISC, no en los comentarios
            # narrativos leídos arriba — ver leer_ls_desde_misc.
            ls.update(leer_ls_desde_misc(bloque))
            resultado.append(ls)
    return resultado


# ---------------------------------------------------------------------------
# SALIDA EN PANTALLA
# ---------------------------------------------------------------------------
def imprimir_ls(ls: dict, idx: int):
    print(f"\n{'─'*56}")
    print(f"  ORACIÓN {idx}")
    print(f"{'─'*56}")
    print(f"  Tipo aspectual : {ls['ls_type'].upper()}")
    print(f"  LS formal      : {ls['ls_formal']}")
    print(f"  LS léxica      : {ls['ls_lexical']}")
    if ls.get('args_map'):
        print(f"  Argumentos     : {ls['args_map']}")
    if ls.get('morph_note'):
        print(f"  Vector aspect. : {ls['morph_note']}")
    if ls.get('causativo'):
        print(f"  Causatividad   : {ls['causativo_tipo']} "
              f"({ls['causativo_source']}, conf. {ls['causativo_confianza']})")
    src = ls.get('cls_source', '')
    if src and src != 'lexicon':
        etiquetas = {'roberta': '🧠 roBERTa (aspect_classifier)'}
        print(f"  Clasificado por: {etiquetas.get(src, src)}")


def imprimir_conllu(path: str):
    print(f"\n{'─'*56}")
    print("  ARCHIVO CoNLL-U ENRIQUECIDO")
    print(f"{'─'*56}")
    with open(path, 'r', encoding='utf-8') as f:
        print(f.read())


def _imprimir_glosario(termino: str | None = None, entrada=input, salida=print):
    """Fase L5 §4 — imprime el glosario completo (paginado simple, bloque por
    categoría) o la definición de un término (búsqueda tolerante).
    `entrada`/`salida` inyectables (default input/print) para poder testear
    en frío el flujo que los invoca (ver `_manejar_help`)."""
    if termino is not None:
        salida("\n" + glosario.respuesta_help(termino))
        return
    bloques = glosario.bloques_glosario()
    interactivo = sys.stdin.isatty() and sys.stdout.isatty()
    for j, bloque in enumerate(bloques):
        salida("\n" + bloque)
        if interactivo and j < len(bloques) - 1:
            try:
                if entrada("\n  -- Enter para continuar (q para cortar) -- ").strip().lower() == "q":
                    break
            except EOFError:
                break


def _elegir_suboracion(res: dict):
    """Devuelve el índice de sub-oración a corregir (0-based), o None si se
    cancela. Con una sola (sub)oración no pregunta."""
    n = len(res.get('ls_lista') or [])
    if n <= 1:
        return 0 if n == 1 else None
    print(f"  ({n} sub-oraciones) ¿cuál corregir? [1-{n}, Esc cancela]")
    try:
        r = input("> ").strip()
    except EOFError:
        return None
    if not r or r.lower() == 'esc' or not r.isdigit() or not (1 <= int(r) <= n):
        return None
    return int(r) - 1


def _manejar_help(linea: str, entrada=input, salida=print) -> bool:
    """Si `linea` es un comando -help/-ayuda, imprime el glosario y devuelve
    True (la línea NO debe analizarse como oración ni como respuesta del
    prompt que la pidió). Fix 2026-07-12: usado en TODOS los inputs
    interactivos de gruxx (no solo la línea "Oración") — antes, el prompt de
    guardar/corregir lo ignoraba y el input caía al prompt siguiente."""
    es_help, termino = glosario.es_comando_help(linea)
    if es_help:
        _imprimir_glosario(termino, entrada=entrada, salida=salida)
    return es_help


def _flujo_guardar_o_corregir(oracion: str, res: dict, reanalizar, sub_idx_fn=None,
                              entrada=input, salida=print) -> str:
    """Fix 2026-07-12 — prompt combinado guardar/corregir del modo
    interactivo, extraído a función inyectable (patrón `entrada`/`salida` de
    `aspect_classifier.correccion`) para poder testearse en frío.

    Bug corregido (reproducido por Julian en uso real): el input crudo de
    este prompt no aceptaba `-help`/`-ayuda` — lo ignoraba y el término caía
    al prompt siguiente ("Oración (o 'salir'):"), justo cuando el usuario
    acaba de ver el anuncio del glosario y quiere consultarlo. Ahora
    `-help [término]` responde (vía `_manejar_help`, que ya imprime con
    `salida`) y VUELVE A MOSTRAR el mismo prompt, sin perder el análisis en
    pantalla ni el estado del flujo — se puede consultar el glosario varias
    veces antes de guardar/corregir/pasar.

    Returns: 'guardado' | 'no_guardado' | 'salir'.
    """
    elegir_sub = sub_idx_fn or _elegir_suboracion
    while True:
        salida("")
        try:
            resp = entrada("¿Guardar en .txt? (s/n) — o (c) para corregir el "
                          "análisis: ")
        except EOFError:
            return "no_guardado"
        resp = (resp or "").strip().lower()
        if _manejar_help(resp, entrada=entrada, salida=salida):
            continue
        if resp in ("s", "si", "sí", "y", "yes"):
            guardar_analisis(oracion, res['ls_lista'], res['stdout'],
                             res.get('completeness'))
            return "guardado"
        if resp in ("c", "corregir"):
            sub = elegir_sub(res)
            if sub is not None:
                _bucle_correccion(res, reanalizar, sub_idx=sub, entrada=entrada,
                                  salida=salida)
            continue   # vuelve a ofrecer guardar el análisis (ya corregido)
        if resp in ("salir", "exit", "quit"):
            return "salir"
        return "no_guardado"   # (n) o cualquier otra cosa: no guardar


def _mostrar_estado_modulos():
    from rrg_ls_mapper import _ASPECT_CLF_AVAILABLE
    if _ASPECT_CLF_AVAILABLE:
        print("  [✅] Clasificador aspectual roBERTa (aspect_classifier) activo")
    else:
        print("  [❌] aspect_classifier no cargado — entrena los modelos con:")
        print("       python -m aspect_classifier.train")


# ---------------------------------------------------------------------------
# NÚCLEO DE PROCESAMIENTO
# ---------------------------------------------------------------------------
# TODO-L5 (c): archivos curados destino de cada tipo de corrección aceptada
# por el bucle de L5 (ver TODO-L5 (b) en el modo interactivo, más abajo):
#   - clase aspectual incorrecta            -> conjunto_verbos_semilla_clase_aspectual.xlsx
#     (aspect_classifier/load_data.py, XLSX_PATH) — reentrenaría el clasificador.
#   - plantilla ditransitiva incorrecta     -> aspect_classifier/data/verbos_ditransitivos.xlsx
#     (aspect_classifier/ditransitivas.py, LEXICON_XLSX); los candidatos
#     heurísticos ya se acumulan en aspect_classifier/data/ditransitivos_candidatos.csv
#     (ditransitivas.log_candidato) — L5 los promovería tras validación humana.
#   - causatividad mal detectada/tipada     -> aspect_classifier/data/causative_lexicon.csv
#     (aspect_classifier/causatividad.py).
#   - core/periferia o AGX mal enrutados (lo que valida completeness.verificar
#     directamente) -> no hay léxico curado hoy: L5 tendría que decidir si
#     esto retroalimenta aspect_classifier/nucleo_periferia.py (reglas, no
#     datos) o un nuevo CSV de excepciones por lema+deprel.
def procesar_oracion(nlp, oracion: str) -> dict:
    doc = nlp(oracion)
    open(CONLLU_PATH, 'w', encoding='utf-8').close()
    CoNLL.write_doc2conll(doc, CONLLU_PATH)
    limpiar_conllu_stanza(CONLLU_PATH)
    ls_lista = [map_sentence_to_ls(sent) for sent in doc.sentences]
    inyectar_metadata_rrg(CONLLU_PATH, doc, ls_lista)
    stdout, stderr = correr_ud2rrg(CONLLU_PATH)
    completeness_lista = _completeness_por_oracion(CONLLU_PATH, ls_lista)
    return {'oracion': oracion, 'ls_lista': ls_lista,
            'stdout': stdout, 'stderr': stderr,
            'completeness': completeness_lista}


def mostrar_resultado(res: dict, n: int = 1, total: int = 1):
    """Fase L5 §2/§3 — orden de la convención GRR (árbol → EL léxica → resto)
    con la traducción user-friendly de Rasgos e Integridad (crudo con
    --verbose). Ver aspect_classifier.display_grr.render_bloque."""
    etiqueta = (f"  [{n}/{total}]  {res['oracion']}"
                if total > 1 else f"  {res['oracion']}")
    print(f"\n{SEP2}\n{etiqueta}\n{SEP2}")
    arboles        = _dividir_arboles_ud2rrg(res['stdout'])
    ls_lista       = res['ls_lista']
    completeness   = res.get('completeness') or []
    total_sub = max(len(ls_lista), len(arboles))
    hay_alerta = False
    for i in range(total_sub):
        if total_sub > 1:
            print(f"\n  — Sub-oración {i+1} —")
        ls   = ls_lista[i] if i < len(ls_lista) else {}
        arb  = arboles[i] if i < len(arboles) else None
        comp = completeness[i] if i < len(completeness) else None
        print()
        print(render_bloque(ls, arb, comp, verbose=VERBOSE))
        if comp is not None and comp.get('ok') is False:
            hay_alerta = True
    if hay_alerta:
        # Pista del bucle de corrección (§5): la Integridad trajo ⚠.
        print("\n  ¿Análisis incorrecto? Pulsa (c) al guardar para corregirlo.")
    if res.get('stderr'):
        print(f"\n  ⚠️  Advertencias ud2rrg:\n{res['stderr']}")


# ---------------------------------------------------------------------------
# BATCH — lectura de oraciones
# ---------------------------------------------------------------------------
def leer_oraciones_desde_archivo(ruta: str) -> list[str]:
    if not os.path.exists(ruta):
        print(f"[ERROR] No se encontró: {ruta}")
        sys.exit(1)
    with open(ruta, 'r', encoding='utf-8') as f:
        lineas = f.readlines()
    oraciones = [l.strip() for l in lineas
                 if l.strip() and not l.strip().startswith('#')]
    if not oraciones:
        print(f"[ERROR] '{ruta}' no contiene oraciones válidas.")
        sys.exit(1)
    return oraciones


def leer_oraciones_desde_terminal() -> list[str]:
    print(f"\n{SEP}")
    print("  Ingreso de oraciones en terminal")
    print(SEP)
    print("  Escribe una oración por línea.")
    print("  Escribe FIN (o presiona Enter dos veces) para terminar.\n")
    oraciones           = []
    vacias_consecutivas = 0
    while True:
        try:
            linea = input(f"  [{len(oraciones)+1}] ").strip()
        except EOFError:
            break
        if linea.lower() == 'fin':
            break
        if not linea:
            vacias_consecutivas += 1
            if vacias_consecutivas >= 2:
                break
            continue
        vacias_consecutivas = 0
        oraciones.append(linea)
    if not oraciones:
        print("\n[AVISO] No se ingresaron oraciones.")
        return []
    print(f"\n  → {len(oraciones)} oración(es) recibida(s).")
    return oraciones


def procesar_batch(nlp, oraciones: list[str]) -> list[dict]:
    # Las líneas -help/-ayuda se aceptan también en el batch (§4): se
    # imprimen y NO cuentan como oración a analizar.
    reales = [o for o in oraciones if not _manejar_help(o)]
    total      = len(reales)
    resultados = []
    print(f"\n{SEP}\n  PROCESANDO {total} ORACIÓN(ES)\n{SEP}")
    for n, oracion in enumerate(reales, start=1):
        res = procesar_oracion(nlp, oracion)
        mostrar_resultado(res, n, total)
        resultados.append(res)
    return resultados


# ---------------------------------------------------------------------------
# SELECCIÓN DE MODO AL INICIO
# ---------------------------------------------------------------------------
def seleccionar_modo() -> tuple[str, str | None]:
    """
    Pregunta al usuario qué modo desea usar.
    Retorna (modo, archivo_txt_o_None).
      modo: 'interactivo' | 'batch_terminal' | 'batch_archivo'
    """
    print(f"\n{SEP}")
    print("  ¿Qué deseas hacer?")
    print(SEP)
    print("  [1] Analizar una oración por vez (modo interactivo)")
    print("  [2] Escribir varias oraciones en terminal (batch)")
    print("  [3] Cargar oraciones desde un archivo .txt (batch archivo)")
    print()

    while True:
        opcion = input("  Elige una opción [1/2/3]: ").strip()
        if opcion == '1':
            return ('interactivo', None)
        elif opcion == '2':
            return ('batch_terminal', None)
        elif opcion == '3':
            ruta = input("  Ruta del archivo .txt: ").strip()
            if not ruta:
                print("  [Error] No ingresaste una ruta. Intenta de nuevo.")
                continue
            if not os.path.exists(ruta):
                print(f"  [Error] No se encontró el archivo: {ruta}")
                continue
            return ('batch_archivo', ruta)
        else:
            print("  Opción inválida. Escribe 1, 2 o 3.")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    global VERBOSE
    args = [a for a in sys.argv[1:] if a != '--verbose']
    VERBOSE = '--verbose' in sys.argv[1:]

    # ── Modo especial: archivo .conllu como argumento ─────────────────────
    if args and args[0].endswith('.conllu') and os.path.exists(args[0]):
        conllu_path = os.path.abspath(args[0])
        nombre      = os.path.basename(args[0])

        print(f"\n{SEP}\n  ANÁLISIS GRR — Archivo CoNLL-U\n  Fuente: {nombre}\n{SEP}")

        ls_data_lista  = leer_ls_desde_conllu(conllu_path)
        stdout, stderr = correr_ud2rrg(conllu_path)
        arboles        = _dividir_arboles_ud2rrg(stdout)
        completeness   = _completeness_por_oracion(conllu_path, ls_data_lista)
        total          = max(len(ls_data_lista), len(arboles))

        for i in range(total):
            print(f"\n{SEP2}\n  ORACIÓN {i+1}\n{SEP2}\n")
            ls   = ls_data_lista[i] if i < len(ls_data_lista) else {}
            arb  = arboles[i] if i < len(arboles) else None
            comp = completeness[i] if i < len(completeness) else None
            print(render_bloque(ls, arb, comp, verbose=VERBOSE))

        if stderr:
            print(f"\n⚠️  Advertencias:\n{stderr}")
        print(f"\n  {glosario.ANUNCIO}")

        print()
        resp = input("¿Guardar en .txt? (s/n): ").strip().lower()
        if resp in ("s","si","sí","y","yes"):
            guardar_analisis(nombre, ls_data_lista, stdout, completeness)
        print()
        return

    # ── Encabezado y carga de modelos ─────────────────────────────────────
    print(f"\n{SEP}")
    print("  ANALIZADOR GRR — ud2rrg + rrg_ls_mapper")
    print(SEP)
    print("\n[INFO] Cargando modelo Stanza...")
    nlp = cargar_pipeline_stanza(LANG)
    print("[OK] Modelo NLP listo.")
    _mostrar_estado_modulos()

    # ── Selección de modo ─────────────────────────────────────────────────
    modo, archivo_txt = seleccionar_modo()

    # ════════════════════════════════════════════════════════════════════════
    # MODO BATCH ARCHIVO
    # ════════════════════════════════════════════════════════════════════════
    if modo == 'batch_archivo':
        oraciones  = leer_oraciones_desde_archivo(archivo_txt)
        origen     = archivo_txt
        print(f"\n[OK] {len(oraciones)} oración(es) cargadas desde {archivo_txt}\n")
        resultados = procesar_batch(nlp, oraciones)
        print(f"\n{SEP}\n  BATCH COMPLETADO — {len(resultados)} oración(es)\n{SEP}")
        _preguntar_guardar_batch(origen, resultados, reanalizar=lambda o: procesar_oracion(nlp, o))
        print("\n¡Hasta pronto!")
        return

    # ════════════════════════════════════════════════════════════════════════
    # MODO BATCH TERMINAL
    # ════════════════════════════════════════════════════════════════════════
    if modo == 'batch_terminal':
        oraciones = leer_oraciones_desde_terminal()
        if not oraciones:
            print("No se procesaron oraciones.")
            return
        origen     = 'terminal'
        resultados = procesar_batch(nlp, oraciones)
        print(f"\n{SEP}\n  BATCH COMPLETADO — {len(resultados)} oración(es)\n{SEP}")
        _preguntar_guardar_batch(origen, resultados, reanalizar=lambda o: procesar_oracion(nlp, o))
        print("\n¡Hasta pronto!")
        return

    # ════════════════════════════════════════════════════════════════════════
    # MODO INTERACTIVO — bucle con acumulación de sesión
    # ════════════════════════════════════════════════════════════════════════
    print(f"\n{SEP}")
    print("  MODO INTERACTIVO — escribe 'salir' para terminar")
    print(SEP)
    print(f"  {glosario.ANUNCIO}\n")

    sesion_resultados = []
    reanalizar = lambda o: procesar_oracion(nlp, o)   # noqa: E731 (§5 re-análisis)

    while True:
        try:
            oracion = input("Oración (o 'salir'): ").strip()
        except EOFError:
            break

        # -help/-ayuda como línea del modo interactivo (§4)
        if _manejar_help(oracion):
            continue

        if oracion.lower() in ['salir', 'exit', 'quit']:
            # Ofrecer guardar la sesión completa antes de salir
            if sesion_resultados:
                print(f"\n  ({len(sesion_resultados)} oración(es) en esta sesión)")
                print()
                sys.stdout.flush()
                try:
                    resp = input("¿Guardar toda la sesión en .txt? (s/n): ").strip().lower()
                    if resp in ("s", "si", "sí", "y", "yes"):
                        _guardar_resultados(
                            _nombre_archivo_batch('sesion_interactiva'),
                            "ANÁLISIS GRR — Sesión interactiva",
                            'sesion_interactiva',
                            sesion_resultados
                        )
                except EOFError:
                    pass
            print("\nCerrando el analizador. ¡Hasta pronto!")
            break

        if not oracion:
            continue

        print(f"\nAnalizando: '{oracion}'")
        res = procesar_oracion(nlp, oracion)

        if VERBOSE:
            imprimir_conllu(CONLLU_PATH)
            print(f"\n{SEP}\n  ESTRUCTURAS LÓGICAS\n{SEP}")
            for i, ls in enumerate(res['ls_lista'], start=1):
                imprimir_ls(ls, i)

        print(f"\n{SEP}\n  ANÁLISIS COMPLETO\n{SEP}")
        mostrar_resultado(res)

        sesion_resultados.append(res)
        print(f"\n  {glosario.ANUNCIO}")

        # Guardar / corregir (§5): (s) guarda, (c) abre el bucle de corrección,
        # (n)/vacío no guarda, -help/-ayuda responde el glosario y re-pregunta.
        # El bucle de corrección re-analiza y solo persiste en vivo lo que
        # confirma; luego se vuelve a ofrecer guardar.
        sys.stdout.flush()
        resultado = _flujo_guardar_o_corregir(oracion, res, reanalizar)
        if resultado == "salir":
            print("\nCerrando el analizador. ¡Hasta pronto!")
            return

        print("\n" + "=" * 56 + "\n")


if __name__ == "__main__":
    main()
