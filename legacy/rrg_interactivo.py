"""
rrg_interactivo.py
==================
Pipeline integrado:
  1. Stanza analiza la oración y produce CoNLL-U base
  2. rrg_ls_mapper genera la Estructura Lógica GRR
  3. Los metadatos rrg_* se inyectan como comentarios en el .conllu
  4. ud2rrg (vía convertir.py) genera el árbol sintáctico
  5. La salida final combina LS + árbol en pantalla
  6. Opcional: se guarda todo en un archivo .txt

Modos de uso:
  python3 rrg_interactivo.py                        # modo interactivo (una oración)
  python3 rrg_interactivo.py --batch                # modo batch: escribir oraciones en terminal
  python3 rrg_interactivo.py --batch oraciones.txt  # modo batch: cargar desde archivo .txt
  python3 rrg_interactivo.py archivo.conllu         # modo archivo CoNLL-U ya anotado

Modo batch desde terminal:
  Escribe una oración por línea. Para terminar, escribe FIN (o deja una línea vacía + Enter dos veces).

Formato del archivo .txt para batch:
  Una oración por línea. Las líneas que empiezan con # se ignoran (comentarios).
  Líneas vacías se omiten.
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

SEP = "=" * 56


# ---------------------------------------------------------------------------
# UTILIDADES — ANÁLISIS
# ---------------------------------------------------------------------------
def cargar_pipeline_stanza(lang: str):
    """Carga el pipeline de Stanza, descargando el modelo si hace falta."""
    try:
        nlp = stanza.Pipeline(
            lang=lang,
            processors='tokenize,mwt,pos,lemma,depparse',
            verbose=False
        )
    except Exception:
        print(f"[INFO] Descargando modelo Stanza '{lang}'...")
        stanza.download(lang)
        nlp = stanza.Pipeline(
            lang=lang,
            processors='tokenize,mwt,pos,lemma,depparse',
            verbose=False
        )
    return nlp


def limpiar_conllu_stanza(conllu_path: str):
    """
    Normaliza el CoNLL-U generado por Stanza para que ud2rrg lo acepte.

    Problemas conocidos que corrige:
      1. MISC: elimina start_char/end_char; si no queda nada útil, pone '_'.
      2. Lema: corrige lemas erróneos conocidos (ej. 'comir' → 'comer').
      3. Orden y numeración de sent_id: se reordena a sent_id → text
         y se renumeran desde 1.
    """
    LEMA_FIXES = {
        'comir': 'comer',
    }
    MISC_STRIP = {'start_char', 'end_char'}

    with open(conllu_path, 'r', encoding='utf-8') as f:
        content = f.read()

    bloques_raw = content.strip().split('\n\n')
    bloques_limpios = []
    sent_counter = 0

    for bloque in bloques_raw:
        if not bloque.strip():
            continue

        lines      = bloque.split('\n')
        comentarios = [l for l in lines if l.startswith('#')]
        tokens      = [l for l in lines if not l.startswith('#') and l.strip()]

        text_line = next((l for l in comentarios if l.startswith('# text')), None)
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
                misc = cols[9]
                if misc != '_':
                    pares = [p for p in misc.split('|')
                             if p.split('=')[0] not in MISC_STRIP]
                    cols[9] = '|'.join(pares) if pares else '_'
                tokens_limpios.append('\t'.join(cols))
            else:
                tokens_limpios.append(tok)

        bloque_limpio = '\n'.join(nuevos_comentarios + tokens_limpios)
        bloques_limpios.append(bloque_limpio)

    with open(conllu_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(bloques_limpios) + '\n\n')


def inyectar_metadata_rrg(conllu_path: str, doc, ls_data_por_oracion: list):
    """
    Inserta comentarios rrg_* después de cada línea '# text = ...'
    en el .conllu.  Maneja múltiples oraciones correctamente.
    """
    with open(conllu_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    updated = []
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
    """Ejecuta convertir.py y retorna (stdout, stderr)."""
    if not os.path.exists(CONVERTIR_PY):
        return ("[ud2rrg no encontrado — omitiendo árbol sintáctico]\n"
                f"Ruta buscada: {CONVERTIR_PY}", "")
    proc = subprocess.run(
        [sys.executable, CONVERTIR_PY, conllu_path, LANG],
        capture_output=True,
        text=True
    )
    return proc.stdout, proc.stderr


def _dividir_arboles_ud2rrg(stdout: str) -> list[str]:
    """
    Divide la salida completa de ud2rrg en bloques individuales por oración.
    ud2rrg separa cada oración con una línea '--- Oración N ---'.
    Retorna lista de strings, uno por oración, sin la línea de cabecera.
    """
    import re
    bloques = re.split(r'--- Oración \d+ ---\n?', stdout)
    bloques = [b.strip() for b in bloques[1:] if b.strip()]
    return bloques


# ---------------------------------------------------------------------------
# UTILIDADES — GUARDADO EN ARCHIVO
# ---------------------------------------------------------------------------
def _nombre_archivo(texto: str) -> str:
    """
    Genera un nombre de archivo limpio a partir de las primeras 5 palabras
    del texto (sin tildes, sin caracteres especiales).
    """
    palabras = texto.strip().rstrip("?.!").split()[:5]
    nombre   = "_".join(palabras).lower()
    tabla    = str.maketrans('áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN')
    nombre   = nombre.translate(tabla)
    nombre   = "".join(c if c.isalnum() or c == '_' else '' for c in nombre)
    return f"analisis_{nombre}.txt"


def _extraer_arbol(stdout_ud2rrg: str) -> str:
    """
    Filtra la salida cruda de ud2rrg y devuelve solo las líneas
    que forman el árbol (las que comienzan con caracteres de caja Unicode).
    """
    lineas  = []
    copiar  = False
    for linea in stdout_ud2rrg.splitlines():
        t = linea.strip()
        if t.startswith("┌") or t.startswith("│") or t.startswith("└"):
            copiar = True
        if copiar:
            lineas.append(linea)
    return "\n".join(lineas).rstrip()


def guardar_analisis(origen: str, ls_data_lista: list, stdout_ud2rrg: str):
    """
    Escribe en un .txt el análisis completo: encabezado, estructuras lógicas
    y árbol(es) sintáctico(s), oración por oración.
    """
    nombre_archivo = _nombre_archivo(origen)
    fecha          = datetime.now().strftime("%Y-%m-%d %H:%M")

    encabezado = (
        "=" * 60 + "\n"
        "  ANÁLISIS GRR — ud2rrg + rrg_ls_mapper\n"
        f"  Fuente  : {origen}\n"
        f"  Fecha   : {fecha}\n"
        "=" * 60 + "\n\n"
        "NOTA PARA ABRIR CORRECTAMENTE:\n"
        "  • Abre este archivo con un editor de texto plano\n"
        "  • Usa una fuente MONOESPACIADA (Courier New, Consolas, DejaVu Sans Mono)\n"
        "  • En Word/LibreOffice usa un cuadro de texto con Courier New 9–10pt\n"
        "  • No pegues el árbol en un párrafo normal\n"
        "\n" + "=" * 60 + "\n\n"
    )

    arboles = _dividir_arboles_ud2rrg(stdout_ud2rrg)
    total   = max(len(ls_data_lista), len(arboles))

    bloques_oraciones = []
    for i in range(total):
        bloque = f"{'═' * 60}\n  ORACIÓN {i + 1}\n{'═' * 60}\n\n"

        # — Estructura Lógica —
        if i < len(ls_data_lista):
            ls = ls_data_lista[i]
            bloque += "  ESTRUCTURA LÓGICA GRR\n"
            bloque += f"  {'─' * 40}\n"
            bloque += f"  Tipo aspectual : {ls['ls_type'].upper()}\n"
            bloque += f"  LS formal      : {ls['ls_formal']}\n"
            bloque += f"  LS léxica      : {ls['ls_lexical']}\n"
            if ls['args_map']:
                bloque += f"  Argumentos     : {ls['args_map']}\n"
            bloque += "\n"

        # — Árbol sintáctico —
        bloque += "  ÁRBOL SINTÁCTICO RRG\n"
        bloque += f"  {'─' * 40}\n\n"
        if i < len(arboles):
            arbol_limpio = _extraer_arbol(arboles[i])
            bloque += arbol_limpio + "\n"
        else:
            bloque += "  (sin árbol — subtree not handled)\n"

        bloques_oraciones.append(bloque)

    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write(encabezado)
        f.write("\n\n".join(bloques_oraciones))
        f.write("\n")

    print(f"\n[OK] Análisis guardado en: {nombre_archivo}")


# ---------------------------------------------------------------------------
# MODO ARCHIVO: leer LS directamente de comentarios rrg_* en un .conllu
# ---------------------------------------------------------------------------
def leer_ls_desde_conllu(conllu_path: str) -> list[dict]:
    """
    Extrae los datos LS de los comentarios rrg_* de un .conllu ya anotado.
    Retorna una lista de dicts con el mismo formato que map_sentence_to_ls.
    """
    resultado = []
    with open(conllu_path, 'r', encoding='utf-8') as f:
        content = f.read()

    for bloque in content.strip().split('\n\n'):
        if not bloque.strip():
            continue
        ls = {
            'ls_type':    'desconocido',
            'ls_formal':  '',
            'ls_lexical': '',
            'args_map':   '',
            'variables':  {},
        }
        for line in bloque.split('\n'):
            if line.startswith('# rrg_ls_type'):
                ls['ls_type']    = line.split('=', 1)[1].strip()
            elif line.startswith('# rrg_ls_lex'):
                ls['ls_lexical'] = line.split('=', 1)[1].strip()
            elif line.startswith('# rrg_ls '):
                ls['ls_formal']  = line.split('=', 1)[1].strip()
            elif line.startswith('# rrg_args'):
                ls['args_map']   = line.split('=', 1)[1].strip()
        if ls['ls_formal'] or ls['ls_lexical']:
            resultado.append(ls)
    return resultado


# ---------------------------------------------------------------------------
# SALIDA FORMATEADA EN PANTALLA
# ---------------------------------------------------------------------------
def imprimir_ls(ls: dict, idx: int):
    print(f"\n{'─'*56}")
    print(f"  ORACIÓN {idx}")
    print(f"{'─'*56}")
    print(f"  Tipo aspectual : {ls['ls_type'].upper()}")
    print(f"  LS formal      : {ls['ls_formal']}")
    print(f"  LS léxica      : {ls['ls_lexical']}")
    if ls['args_map']:
        print(f"  Argumentos     : {ls['args_map']}")
    # Mostrar fuente de clasificación y rasgos morfológicos si están disponibles
    src = ls.get('cls_source', '')
    if src and src != 'lexicon':
        etiquetas = {'morph': '🔬 morfosintaxis', 'llm': '🤖 LLM local'}
        print(f"  Clasificado por: {etiquetas.get(src, src)}")
    if ls.get('morph_note'):
        print(f"  Rasgos morph   : {ls['morph_note']}")


def imprimir_conllu(path: str):
    """Muestra el .conllu enriquecido con los metadatos inyectados."""
    print(f"\n{'─'*56}")
    print("  ARCHIVO CoNLL-U ENRIQUECIDO")
    print(f"{'─'*56}")
    with open(path, 'r', encoding='utf-8') as f:
        print(f.read())


# ---------------------------------------------------------------------------
# BATCH — lectura de oraciones
# ---------------------------------------------------------------------------
def leer_oraciones_desde_archivo(ruta: str) -> list[str]:
    """
    Lee un archivo .txt y retorna una lista de oraciones.
    Ignora líneas vacías y líneas que empiezan con '#'.
    """
    if not os.path.exists(ruta):
        print(f"[ERROR] No se encontró el archivo: {ruta}")
        sys.exit(1)

    with open(ruta, 'r', encoding='utf-8') as f:
        lineas = f.readlines()

    oraciones = [
        l.strip()
        for l in lineas
        if l.strip() and not l.strip().startswith('#')
    ]

    if not oraciones:
        print(f"[ERROR] El archivo '{ruta}' no contiene oraciones válidas.")
        sys.exit(1)

    return oraciones


def leer_oraciones_desde_terminal() -> list[str]:
    """
    Pide al usuario que escriba oraciones en la terminal, una por línea.
    Termina cuando el usuario escribe 'FIN' o deja dos líneas vacías seguidas.
    """
    print("\n" + SEP)
    print("  MODO BATCH — Ingreso por terminal")
    print(SEP)
    print("  Escribe una oración por línea.")
    print("  Escribe FIN (o presiona Enter dos veces) para terminar.\n")

    oraciones = []
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
        print("\n[AVISO] No se ingresaron oraciones. Saliendo.")
        sys.exit(0)

    print(f"\n  → {len(oraciones)} oración(es) recibida(s).")
    return oraciones


# ---------------------------------------------------------------------------
# BATCH — procesamiento y salida consolidada
# ---------------------------------------------------------------------------
def _nombre_archivo_batch(origen: str) -> str:
    """Genera nombre de archivo para la salida del batch."""
    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
    if origen and origen != 'terminal':
        base = os.path.splitext(os.path.basename(origen))[0]
        tabla = str.maketrans('áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN')
        base = base.translate(tabla)
        base = "".join(c if c.isalnum() or c == '_' else '_' for c in base)
        return f"batch_{base}_{fecha}.txt"
    return f"batch_terminal_{fecha}.txt"


def guardar_batch(origen: str, resultados: list[dict]):
    """
    Guarda el análisis consolidado de todas las oraciones del batch en un .txt.

    Cada elemento de `resultados` es un dict con:
      oracion   : str  — texto original
      ls_lista  : list[dict]  — datos LS por sub-oración detectada
      stdout    : str  — salida cruda de ud2rrg
    """
    nombre_archivo = _nombre_archivo_batch(origen)
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_oraciones = len(resultados)

    encabezado = (
        "=" * 60 + "\n"
        "  ANÁLISIS GRR EN BATCH — ud2rrg + rrg_ls_mapper\n"
        f"  Fuente  : {origen}\n"
        f"  Fecha   : {fecha}\n"
        f"  Total   : {total_oraciones} oración(es)\n"
        "=" * 60 + "\n\n"
        "NOTA PARA ABRIR CORRECTAMENTE:\n"
        "  • Usa un editor con fuente MONOESPACIADA (Courier New, Consolas)\n"
        "  • No pegues el árbol en un párrafo normal de Word\n"
        "\n" + "=" * 60 + "\n\n"
    )

    bloques = []
    for n, res in enumerate(resultados, start=1):
        bloque = (
            f"{'═' * 60}\n"
            f"  ORACIÓN {n}: {res['oracion']}\n"
            f"{'═' * 60}\n\n"
        )

        arboles = _dividir_arboles_ud2rrg(res['stdout'])
        total_sub = max(len(res['ls_lista']), len(arboles))

        for i in range(total_sub):
            if total_sub > 1:
                bloque += f"  — Sub-oración {i+1} —\n\n"

            if i < len(res['ls_lista']):
                ls = res['ls_lista'][i]
                bloque += "  ESTRUCTURA LÓGICA GRR\n"
                bloque += f"  {'─' * 40}\n"
                bloque += f"  Tipo aspectual : {ls['ls_type'].upper()}\n"
                bloque += f"  LS formal      : {ls['ls_formal']}\n"
                bloque += f"  LS léxica      : {ls['ls_lexical']}\n"
                if ls['args_map']:
                    bloque += f"  Argumentos     : {ls['args_map']}\n"
                bloque += "\n"

            bloque += "  ÁRBOL SINTÁCTICO RRG\n"
            bloque += f"  {'─' * 40}\n\n"
            if i < len(arboles):
                bloque += _extraer_arbol(arboles[i]) + "\n"
            else:
                bloque += "  (sin árbol — subtree not handled)\n"
            bloque += "\n"

        bloques.append(bloque)

    with open(nombre_archivo, 'w', encoding='utf-8') as f:
        f.write(encabezado)
        f.write("\n".join(bloques))

    print(f"\n[OK] Análisis batch guardado en: {nombre_archivo}")


def procesar_batch(nlp, oraciones: list[str]) -> list[dict]:
    """
    Procesa una lista de oraciones y retorna los resultados consolidados.
    Imprime el progreso y el análisis de cada una en pantalla.
    """
    resultados = []
    total = len(oraciones)

    print(f"\n{SEP}")
    print(f"  PROCESANDO BATCH ({total} oración(es))")
    print(SEP)

    for n, oracion in enumerate(oraciones, start=1):
        print(f"\n{'═'*56}")
        print(f"  [{n}/{total}]  {oracion}")
        print(f"{'═'*56}")

        # 1. Stanza
        doc = nlp(oracion)

        # 2. CoNLL-U base
        open(CONLLU_PATH, 'w', encoding='utf-8').close()
        CoNLL.write_doc2conll(doc, CONLLU_PATH)
        limpiar_conllu_stanza(CONLLU_PATH)

        # 3. Estructuras Lógicas
        ls_lista = [map_sentence_to_ls(sent) for sent in doc.sentences]
        inyectar_metadata_rrg(CONLLU_PATH, doc, ls_lista)

        # Mostrar LS en pantalla
        for i, ls in enumerate(ls_lista, start=1):
            sub = f" (sub-oración {i})" if len(ls_lista) > 1 else ""
            print(f"\n  LS{sub}")
            print(f"  Tipo     : {ls['ls_type'].upper()}")
            print(f"  Formal   : {ls['ls_formal']}")
            print(f"  Léxica   : {ls['ls_lexical']}")
            if ls['args_map']:
                print(f"  Args     : {ls['args_map']}")

        # 4. Árbol sintáctico
        stdout, stderr = correr_ud2rrg(CONLLU_PATH)
        arboles = _dividir_arboles_ud2rrg(stdout)

        print()
        for i, arbol in enumerate(arboles, start=1):
            sub = f" (sub-oración {i})" if len(arboles) > 1 else ""
            print(f"  Árbol RRG{sub}:")
            print(arbol)

        if stderr:
            print(f"\n  ⚠️  Advertencias ud2rrg:\n{stderr}")

        resultados.append({
            'oracion': oracion,
            'ls_lista': ls_lista,
            'stdout': stdout,
        })

    return resultados


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    args = sys.argv[1:]

    # ════════════════════════════════════════════════════════════════════════
    # MODO ARCHIVO CoNLL-U — ya tiene anotaciones rrg_*
    # Uso: python3 rrg_interactivo.py archivo.conllu
    # ════════════════════════════════════════════════════════════════════════
    if args and args[0].endswith('.conllu') and os.path.exists(args[0]):
        conllu_path = os.path.abspath(args[0])
        nombre      = os.path.basename(args[0])

        print(SEP)
        print("  ANÁLISIS GRR INTEGRADO")
        print("  Modo  : archivo CoNLL-U")
        print(f"  Fuente: {nombre}")
        print(SEP)

        print("\n[1/2] Leyendo estructuras lógicas del archivo...")
        ls_data_lista = leer_ls_desde_conllu(conllu_path)

        print("[2/2] Generando árboles sintácticos con ud2rrg...")
        stdout, stderr = correr_ud2rrg(conllu_path)

        arboles = _dividir_arboles_ud2rrg(stdout)
        total   = max(len(ls_data_lista), len(arboles))

        for i in range(total):
            print(f"\n{'═'*56}")
            print(f"  ORACIÓN {i+1}")
            print(f"{'═'*56}")
            if i < len(ls_data_lista):
                ls = ls_data_lista[i]
                print(f"  Tipo aspectual : {ls['ls_type'].upper()}")
                print(f"  LS formal      : {ls['ls_formal']}")
                print(f"  LS léxica      : {ls['ls_lexical']}")
                if ls['args_map']:
                    print(f"  Argumentos     : {ls['args_map']}")
            print(f"\n{'─'*56}")
            print("  ÁRBOL RRG")
            print(f"{'─'*56}")
            if i < len(arboles):
                print(arboles[i])
            else:
                print("  (sin árbol)")

        if stderr:
            print(f"\n⚠️  Advertencias ud2rrg:\n{stderr}")

        print()
        respuesta = input("¿Guardar el análisis en un archivo .txt? (s/n): ").strip().lower()
        if respuesta in ("s", "si", "sí", "y", "yes"):
            guardar_analisis(nombre, ls_data_lista, stdout)

        print()
        return

    # ════════════════════════════════════════════════════════════════════════
    # MODO BATCH
    # Uso: python3 rrg_interactivo.py --batch [archivo.txt]
    # ════════════════════════════════════════════════════════════════════════
    if args and args[0] == '--batch':
        archivo_txt = args[1] if len(args) > 1 else None

        print(SEP)
        print("  ANÁLISIS GRR INTEGRADO — MODO BATCH")
        print(SEP)

        # Determinar origen y leer oraciones
        if archivo_txt:
            if not os.path.exists(archivo_txt):
                print(f"[ERROR] No se encontró el archivo: {archivo_txt}")
                sys.exit(1)
            print(f"\n  Cargando oraciones desde: {archivo_txt}")
            oraciones = leer_oraciones_desde_archivo(archivo_txt)
            origen    = archivo_txt
        else:
            oraciones = leer_oraciones_desde_terminal()
            origen    = 'terminal'

        # Cargar Stanza una sola vez para todo el batch
        print("\n[INFO] Cargando modelo Stanza...")
        nlp = cargar_pipeline_stanza(LANG)
        print(f"[OK] Modelo cargado. Procesando {len(oraciones)} oración(es)...\n")

        # Procesar todas las oraciones
        resultados = procesar_batch(nlp, oraciones)

        # Resumen final
        print(f"\n{SEP}")
        print(f"  BATCH COMPLETADO — {len(resultados)} oración(es) analizadas")
        print(SEP)

        # Guardar (siempre se ofrece al final del batch)
        print()
        respuesta = input("¿Guardar el análisis completo en un archivo .txt? (s/n): ").strip().lower()
        if respuesta in ("s", "si", "sí", "y", "yes"):
            guardar_batch(origen, resultados)

        print()
        return

    # ════════════════════════════════════════════════════════════════════════
    # MODO INTERACTIVO — una oración a la vez
    # Uso: python3 rrg_interactivo.py
    # ════════════════════════════════════════════════════════════════════════
    print(SEP)
    print("  ANÁLISIS GRR INTEGRADO (MODO INTERACTIVO)")
    print("  Tip: usa --batch para analizar varias oraciones a la vez")
    print(SEP)

    print("\n[INFO] Cargando modelo Stanza (esto tomará un momento)...")
    nlp = cargar_pipeline_stanza(LANG)
    print("[OK] Modelo NLP cargado y listo.")

    # Mostrar estado de los módulos opcionales
    try:
        from rrg_llm_fallback import ollama_status
        status = ollama_status()
        icono = "✅" if status["available"] else "⚠️ "
        print(f"[{icono}] {status['message']}")
    except ImportError:
        pass
    try:
        import rrg_morph_classifier  # noqa: F401
        print("[✅] Clasificador morfosintáctico activo (rrg_morph_classifier)")
    except ImportError:
        pass
    print()

    while True:
        oracion = input("Escribe una oración en español (o 'salir' para terminar): ")

        if oracion.strip().lower() in ['salir', 'exit', 'quit']:
            print("\nCerrando el analizador. ¡Hasta pronto!")
            break

        if not oracion.strip():
            continue

        print(f"\nAnalizando: '{oracion}'")

        # 1. Análisis Stanza
        print("\n[1/4] Ejecutando Stanza...")
        doc = nlp(oracion)

        # 2. CoNLL-U base
        print("[2/4] Generando CoNLL-U base...")
        open(CONLLU_PATH, 'w', encoding='utf-8').close()
        CoNLL.write_doc2conll(doc, CONLLU_PATH)
        limpiar_conllu_stanza(CONLLU_PATH)

        # 3. Estructuras Lógicas
        print("[3/4] Calculando Estructuras Lógicas GRR...")
        ls_data_lista = [map_sentence_to_ls(sent) for sent in doc.sentences]
        inyectar_metadata_rrg(CONLLU_PATH, doc, ls_data_lista)

        print(f"\n{SEP}")
        print("  ESTRUCTURAS LÓGICAS")
        print(SEP)
        for i, ls in enumerate(ls_data_lista, start=1):
            imprimir_ls(ls, i)

        imprimir_conllu(CONLLU_PATH)

        # 4. Árbol sintáctico
        print("[4/4] Generando árbol sintáctico con ud2rrg...")
        stdout, stderr = correr_ud2rrg(CONLLU_PATH)

        arboles = _dividir_arboles_ud2rrg(stdout)
        total   = max(len(ls_data_lista), len(arboles))

        print(f"\n{SEP}")
        print("  ANÁLISIS POR ORACIÓN")
        print(SEP)

        for i in range(total):
            print(f"\n{'═'*56}")
            print(f"  ORACIÓN {i+1}")
            print(f"{'═'*56}")
            if i < len(ls_data_lista):
                ls = ls_data_lista[i]
                print(f"  Tipo aspectual : {ls['ls_type'].upper()}")
                print(f"  LS formal      : {ls['ls_formal']}")
                print(f"  LS léxica      : {ls['ls_lexical']}")
                if ls['args_map']:
                    print(f"  Argumentos     : {ls['args_map']}")
            print(f"\n{'─'*56}")
            print("  ÁRBOL RRG")
            print(f"{'─'*56}")
            if i < len(arboles):
                print(arboles[i])
            else:
                print("  (sin árbol — subtree not handled)")

        if stderr:
            print(f"\n⚠️  Advertencias ud2rrg:\n{stderr}")

        print()
        respuesta = input("¿Guardar el análisis en un archivo .txt? (s/n): ").strip().lower()
        if respuesta in ("s", "si", "sí", "y", "yes"):
            guardar_analisis(oracion, ls_data_lista, stdout)

        print("\n" + "=" * 56 + "\n")

if __name__ == "__main__":
    main()