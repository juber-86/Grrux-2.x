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

# ---------------------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------------------
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
CONLLU_PATH  = os.path.join(SCRIPT_DIR, "input_estudiante.conllu")
CONVERTIR_PY = os.path.join(SCRIPT_DIR, "convertir.py")
LANG         = "es"

SEP  = "=" * 56
SEP2 = "═" * 56


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


def correr_ud2rrg(conllu_path: str) -> tuple[str, str]:
    if not os.path.exists(CONVERTIR_PY):
        return (f"[ud2rrg no encontrado]\nRuta: {CONVERTIR_PY}", "")
    proc = subprocess.run(
        [sys.executable, CONVERTIR_PY, conllu_path, LANG],
        capture_output=True, text=True)
    return proc.stdout, proc.stderr


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


def _bloque_ls_txt(ls: dict) -> str:
    bloque  = "  ESTRUCTURA LÓGICA GRR\n"
    bloque += f"  {'─' * 40}\n"
    bloque += f"  Tipo aspectual : {ls['ls_type'].upper()}\n"
    bloque += f"  LS formal      : {ls['ls_formal']}\n"
    bloque += f"  LS léxica      : {ls['ls_lexical']}\n"
    if ls.get('args_map'):
        bloque += f"  Argumentos     : {ls['args_map']}\n"
    src = ls.get('cls_source', 'lexicon')
    etiquetas = {
        'lexicon': 'léxico estático',
        'morph':   'morfosintaxis',
        'llm':     'LLM (qwen2.5)',
    }
    bloque += f"  Clasificado por: {etiquetas.get(src, src)}\n"
    if ls.get('morph_note'):
        bloque += f"  Rasgos morph   : {ls['morph_note']}\n"
    return bloque


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
        arboles   = _dividir_arboles_ud2rrg(res['stdout'])
        ls_lista  = res['ls_lista']
        total_sub = max(len(ls_lista), len(arboles))
        cuerpo    = ""
        for i in range(total_sub):
            if total_sub > 1:
                cuerpo += f"  — Sub-oración {i+1} —\n\n"
            if i < len(ls_lista):
                cuerpo += _bloque_ls_txt(ls_lista[i]) + "\n"
            cuerpo += "  ÁRBOL SINTÁCTICO RRG\n"
            cuerpo += f"  {'─' * 40}\n\n"
            cuerpo += (_extraer_arbol(arboles[i]) if i < len(arboles)
                       else "  (sin árbol — subtree not handled)") + "\n\n"
        bloques.append(enc + cuerpo)

    with open(nombre_archivo, 'w', encoding='utf-8') as f:
        f.write(_encabezado_txt(titulo, origen, fecha, extra))
        f.write("\n".join(bloques))

    print(f"[OK] Guardado en: {nombre_archivo}")


def _preguntar_guardar_batch(origen: str, resultados: list[dict]):
    """
    Pregunta si guardar y espera respuesta.
    flush() garantiza que el prompt aparezca antes de leer la respuesta.
    """
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


def guardar_analisis(origen: str, ls_data_lista: list, stdout_ud2rrg: str):
    """Guarda el análisis de una sola oración."""
    _guardar_resultados(
        _nombre_archivo(origen),
        "ANÁLISIS GRR — ud2rrg + rrg_ls_mapper",
        origen,
        [{'oracion': origen, 'ls_lista': ls_data_lista, 'stdout': stdout_ud2rrg}]
    )


# ---------------------------------------------------------------------------
# MODO ARCHIVO: leer LS de .conllu ya anotado
# ---------------------------------------------------------------------------
def leer_ls_desde_conllu(conllu_path: str) -> list[dict]:
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
    # Fuente SIEMPRE visible
    src = ls.get('cls_source', 'lexicon')
    etiquetas = {
        'lexicon': '📖 ls_mapper',
        'morph':   '🔬 moprh_classifier',
        'llm':     '🤖 LLM (qwen2.5)',
    }
    print(f"  Clasificado por: {etiquetas.get(src, src)}")
    if ls.get('morph_note'):
        print(f"  Rasgos morph   : {ls['morph_note']}")


def imprimir_conllu(path: str):
    print(f"\n{'─'*56}")
    print("  ARCHIVO CoNLL-U ENRIQUECIDO")
    print(f"{'─'*56}")
    with open(path, 'r', encoding='utf-8') as f:
        print(f.read())


def _mostrar_estado_modulos():
    try:
        from rrg_llm_fallback import ollama_status
        status = ollama_status()
        icono  = "✅" if status["available"] else "⚠️ "
        print(f"  [{icono}] {status['message']}")
    except ImportError:
        print("  [⚠️ ] rrg_llm_fallback no encontrado — fallback LLM desactivado")
    try:
        import rrg_morph_classifier  # noqa: F401
        print("  [✅] Clasificador morfosintáctico activo")
    except ImportError:
        print("  [⚠️ ] rrg_morph_classifier no encontrado — solo léxico estático")


# ---------------------------------------------------------------------------
# NÚCLEO DE PROCESAMIENTO
# ---------------------------------------------------------------------------
def procesar_oracion(nlp, oracion: str) -> dict:
    doc = nlp(oracion)
    open(CONLLU_PATH, 'w', encoding='utf-8').close()
    CoNLL.write_doc2conll(doc, CONLLU_PATH)
    limpiar_conllu_stanza(CONLLU_PATH)
    ls_lista = [map_sentence_to_ls(sent) for sent in doc.sentences]
    inyectar_metadata_rrg(CONLLU_PATH, doc, ls_lista)
    stdout, stderr = correr_ud2rrg(CONLLU_PATH)
    return {'oracion': oracion, 'ls_lista': ls_lista,
            'stdout': stdout, 'stderr': stderr}


def mostrar_resultado(res: dict, n: int = 1, total: int = 1):
    etiqueta = (f"  [{n}/{total}]  {res['oracion']}"
                if total > 1 else f"  {res['oracion']}")
    print(f"\n{SEP2}\n{etiqueta}\n{SEP2}")
    arboles   = _dividir_arboles_ud2rrg(res['stdout'])
    ls_lista  = res['ls_lista']
    total_sub = max(len(ls_lista), len(arboles))
    for i in range(total_sub):
        if total_sub > 1:
            print(f"\n  — Sub-oración {i+1} —")
        if i < len(ls_lista):
            ls  = ls_lista[i]
            sub = f" (sub-oración {i+1})" if total_sub > 1 else ""
            print(f"\n  LS{sub}")
            print(f"  Tipo     : {ls['ls_type'].upper()}")
            print(f"  Formal   : {ls['ls_formal']}")
            print(f"  Léxica   : {ls['ls_lexical']}")
            if ls.get('args_map'):
                print(f"  Args     : {ls['args_map']}")
            src = ls.get('cls_source', 'lexicon')
            etiquetas = {
                'lexicon': '📖 léxico estático',
                'morph':   '🔬 morfosintaxis',
                'llm':     '🤖 LLM (qwen2.5)',
            }
            print(f"  Fuente   : {etiquetas.get(src, src)}")
        print(f"\n  {'─'*40}\n  ÁRBOL RRG\n  {'─'*40}")
        if i < len(arboles):
            print(arboles[i])
        else:
            print("  (sin árbol — subtree not handled)")
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
    total      = len(oraciones)
    resultados = []
    print(f"\n{SEP}\n  PROCESANDO {total} ORACIÓN(ES)\n{SEP}")
    for n, oracion in enumerate(oraciones, start=1):
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
    args = sys.argv[1:]

    # ── Modo especial: archivo .conllu como argumento ─────────────────────
    if args and args[0].endswith('.conllu') and os.path.exists(args[0]):
        conllu_path = os.path.abspath(args[0])
        nombre      = os.path.basename(args[0])

        print(f"\n{SEP}\n  ANÁLISIS GRR — Archivo CoNLL-U\n  Fuente: {nombre}\n{SEP}")

        ls_data_lista  = leer_ls_desde_conllu(conllu_path)
        stdout, stderr = correr_ud2rrg(conllu_path)
        arboles        = _dividir_arboles_ud2rrg(stdout)
        total          = max(len(ls_data_lista), len(arboles))

        for i in range(total):
            print(f"\n{SEP2}\n  ORACIÓN {i+1}\n{SEP2}")
            if i < len(ls_data_lista):
                ls = ls_data_lista[i]
                print(f"  Tipo aspectual : {ls['ls_type'].upper()}")
                print(f"  LS formal      : {ls['ls_formal']}")
                print(f"  LS léxica      : {ls['ls_lexical']}")
                if ls.get('args_map'):
                    print(f"  Argumentos     : {ls['args_map']}")
            print(f"\n{'─'*56}\n  ÁRBOL RRG\n{'─'*56}")
            print(arboles[i] if i < len(arboles) else "  (sin árbol)")

        if stderr:
            print(f"\n⚠️  Advertencias:\n{stderr}")

        print()
        resp = input("¿Guardar en .txt? (s/n): ").strip().lower()
        if resp in ("s","si","sí","y","yes"):
            guardar_analisis(nombre, ls_data_lista, stdout)
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
        _preguntar_guardar_batch(origen, resultados)
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
        _preguntar_guardar_batch(origen, resultados)
        print("\n¡Hasta pronto!")
        return

    # ════════════════════════════════════════════════════════════════════════
    # MODO INTERACTIVO — bucle con acumulación de sesión
    # ════════════════════════════════════════════════════════════════════════
    print(f"\n{SEP}")
    print("  MODO INTERACTIVO — escribe 'salir' para terminar")
    print(SEP + "\n")

    sesion_resultados = []

    while True:
        try:
            oracion = input("Oración (o 'salir'): ").strip()
        except EOFError:
            break

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

        imprimir_conllu(CONLLU_PATH)

        print(f"\n{SEP}\n  ESTRUCTURAS LÓGICAS\n{SEP}")
        for i, ls in enumerate(res['ls_lista'], start=1):
            imprimir_ls(ls, i)

        print(f"\n{SEP}\n  ANÁLISIS COMPLETO\n{SEP}")
        mostrar_resultado(res)

        sesion_resultados.append(res)

        # Guardar esta oración individualmente (opcional)
        print()
        sys.stdout.flush()
        try:
            resp = input("¿Guardar este análisis en .txt? (s/n): ").strip().lower()
            if resp in ("s", "si", "sí", "y", "yes"):
                guardar_analisis(oracion, res['ls_lista'], res['stdout'])
            elif resp in ("salir", "exit", "quit"):
                # Permite salir también desde esta pregunta
                print("\nCerrando el analizador. ¡Hasta pronto!")
                break
        except EOFError:
            pass

        print("\n" + "=" * 56 + "\n")


if __name__ == "__main__":
    main()
