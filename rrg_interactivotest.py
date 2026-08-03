"""
analizar_texto_ls.py
====================
Pipeline integrado:
  1. Stanza analiza la oración y produce CoNLL-U base
  2. rrg_ls_mapper genera la Estructura Lógica GRR
  3. Los metadatos rrg_* se inyectan como comentarios en el .conllu
  4. ud2rrg (vía convertir.py) genera el árbol sintáctico
  5. La salida final combina LS + árbol en pantalla
  6. Opcional: se guarda todo en un archivo .txt

Uso:
  python3 analizar_texto_ls.py                      # modo bucle interactivo
  python3 analizar_texto_ls.py archivo.conllu        # modo archivo anotado
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


def imprimir_conllu(path: str):
    """Muestra el .conllu enriquecido con los metadatos inyectados."""
    print(f"\n{'─'*56}")
    print("  ARCHIVO CoNLL-U ENRIQUECIDO")
    print(f"{'─'*56}")
    with open(path, 'r', encoding='utf-8') as f:
        print(f.read())


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None

    # ════════════════════════════════════════════════════════════════════════
    # MODO ARCHIVO — el .conllu ya tiene anotaciones rrg_*
    # ════════════════════════════════════════════════════════════════════════
    if arg and arg.endswith('.conllu') and os.path.exists(arg):
        conllu_path  = os.path.abspath(arg)
        nombre       = os.path.basename(arg)
        
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

        # ── Pregunta de guardado ──────────────────────────────────────────
        print()
        respuesta = input("¿Guardar el análisis en un archivo .txt? (s/n): ").strip().lower()
        if respuesta in ("s", "si", "sí", "y", "yes"):
            guardar_analisis(nombre, ls_data_lista, stdout)

        print()
        return  # Salir si se procesó un archivo

    # ════════════════════════════════════════════════════════════════════════
    # MODO BUCLE INTERACTIVO — pipeline completo con Stanza
    # ════════════════════════════════════════════════════════════════════════
    print(SEP)
    print("  ANÁLISIS GRR INTEGRADO (MODO INTERACTIVO)")
    print(SEP)
    
    print("\n[INFO] Cargando modelo Stanza (esto tomará un momento)...")
    nlp = cargar_pipeline_stanza(LANG)
    print("[OK] Modelo NLP cargado y listo.\n")

    while True:
        # Pedimos el input del usuario
        oracion = input("Escribe una oración en español (o 'salir' para terminar): ")
        
        # Condición de salida
        if oracion.strip().lower() in ['salir', 'exit', 'quit']:
            print("\nCerrando el analizador. ¡Hasta pronto!")
            break
            
        # Si el usuario presiona Enter sin escribir nada, volvemos a preguntar
        if not oracion.strip():
            continue

        print(f"\nAnalizando: '{oracion}'")

        # 1. Análisis Stanza
        print("\n[1/4] Ejecutando Stanza...")
        doc = nlp(oracion)

        # 2. Generar CoNLL-U base (truncar antes de escribir para evitar acumulación)
        print("[2/4] Generando CoNLL-U base...")
        open(CONLLU_PATH, 'w', encoding='utf-8').close()   # truncar
        CoNLL.write_doc2conll(doc, CONLLU_PATH)

        # 2b. Limpiar CoNLL-U de Stanza
        limpiar_conllu_stanza(CONLLU_PATH)

        # 3. Calcular LS para cada oración
        print("[3/4] Calculando Estructuras Lógicas GRR...")
        ls_data_lista = [map_sentence_to_ls(sent) for sent in doc.sentences]

        # Inyectar comentarios rrg_* en el .conllu
        inyectar_metadata_rrg(CONLLU_PATH, doc, ls_data_lista)

        # Mostrar LS
        print(f"\n{SEP}")
        print("  ESTRUCTURAS LÓGICAS")
        print(SEP)
        for i, ls in enumerate(ls_data_lista, start=1):
            imprimir_ls(ls, i)

        # Mostrar CoNLL-U enriquecido
        imprimir_conllu(CONLLU_PATH)

        # 4. Árbol sintáctico ud2rrg
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

        # ── Pregunta de guardado ──────────────────────────────────────────────
        print()
        respuesta = input("¿Guardar el análisis en un archivo .txt? (s/n): ").strip().lower()
        if respuesta in ("s", "si", "sí", "y", "yes"):
            guardar_analisis(oracion, ls_data_lista, stdout)

        print("\n" + "=" * 56 + "\n")

if __name__ == "__main__":
    main()
