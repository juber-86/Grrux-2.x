"""
rrg_interactivo_unificado.py
============================
Pipeline integrado de Gramática de Rol y Referencia (GRR):
  1. Menú interactivo (Oración simple, Batch manual, Batch desde archivo).
  2. Stanza analiza la oración y produce CoNLL-U base.
  3. rrg_ls_mapper (con fallback a IA/Morfosintaxis) genera la Estructura Lógica.
  4. Los metadatos rrg_* se inyectan en el .conllu.
  5. ud2rrg genera el árbol sintáctico.
  6. Posibilidad de guardar resultados sin cierres inesperados.
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
# UTILIDADES — ANÁLISIS NLP Y METADATOS
# ---------------------------------------------------------------------------
def cargar_pipeline_stanza(lang: str):
    try:
        nlp = stanza.Pipeline(lang=lang, processors='tokenize,mwt,pos,lemma,depparse', verbose=False)
    except Exception:
        print(f"[INFO] Descargando modelo Stanza '{lang}'...")
        stanza.download(lang)
        nlp = stanza.Pipeline(lang=lang, processors='tokenize,mwt,pos,lemma,depparse', verbose=False)
    return nlp


def limpiar_conllu_stanza(conllu_path: str):
    LEMA_FIXES = {'comir': 'comer'}
    MISC_STRIP = {'start_char', 'end_char'}

    with open(conllu_path, 'r', encoding='utf-8') as f:
        content = f.read()

    bloques_raw = content.strip().split('\n\n')
    bloques_limpios = []
    sent_counter = 0

    for bloque in bloques_raw:
        if not bloque.strip():
            continue

        lines = bloque.split('\n')
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
                    pares = [p for p in misc.split('|') if p.split('=')[0] not in MISC_STRIP]
                    cols[9] = '|'.join(pares) if pares else '_'
                tokens_limpios.append('\t'.join(cols))
            else:
                tokens_limpios.append(tok)

        bloque_limpio = '\n'.join(nuevos_comentarios + tokens_limpios)
        bloques_limpios.append(bloque_limpio)

    with open(conllu_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(bloques_limpios) + '\n\n')


def inyectar_metadata_rrg(conllu_path: str, ls_data_por_oracion: list):
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
    if not os.path.exists(CONVERTIR_PY):
        return ("[ud2rrg no encontrado — omitiendo árbol sintáctico]\n", "")
    proc = subprocess.run(
        [sys.executable, CONVERTIR_PY, conllu_path, LANG],
        capture_output=True, text=True
    )
    return proc.stdout, proc.stderr


def _dividir_arboles_ud2rrg(stdout: str) -> list[str]:
    import re
    bloques = re.split(r'--- Oración \d+ ---\n?', stdout)
    return [b.strip() for b in bloques[1:] if b.strip()]


# ---------------------------------------------------------------------------
# UTILIDADES — VISUALIZACIÓN Y GUARDADO
# ---------------------------------------------------------------------------
def _extraer_arbol(stdout_ud2rrg: str) -> str:
    lineas, copiar = [], False
    for linea in stdout_ud2rrg.splitlines():
        if linea.strip().startswith(("┌", "│", "└")):
            copiar = True
        if copiar:
            lineas.append(linea)
    return "\n".join(lineas).rstrip()

def imprimir_ls(ls: dict, idx: int):
    print(f"\n{'─'*56}")
    print(f"  ORACIÓN {idx}")
    print(f"{'─'*56}")
    print(f"  Tipo aspectual : {ls['ls_type'].upper()}")
    print(f"  LS formal      : {ls['ls_formal']}")
    print(f"  LS léxica      : {ls['ls_lexical']}")
    if ls['args_map']:
        print(f"  Argumentos     : {ls['args_map']}")
    
    # Soporte para módulos IA / Morfosintaxis
    src = ls.get('cls_source', '')
    if src and src != 'lexicon':
        etiquetas = {'morph': '🔬 morfosintaxis', 'llm': '🤖 LLM local'}
        print(f"  Clasificado por: {etiquetas.get(src, src)}")
    if ls.get('morph_note'):
        print(f"  Rasgos morph   : {ls['morph_note']}")

def imprimir_conllu(path: str):
    print(f"\n{'─'*56}")
    print("  ARCHIVO CoNLL-U ENRIQUECIDO")
    print(f"{'─'*56}")
    with open(path, 'r', encoding='utf-8') as f:
        print(f.read())

def preguntar_guardar(callback_guardar):
    """
    Maneja el input de forma segura, ignorando saltos de línea residuales en el búfer
    para evitar que el script se salte la pregunta y se cierre abruptamente.
    """
    print()
    while True:
        try:
            resp = input("¿Guardar el análisis completo en un archivo .txt? (s/n): ").strip().lower()
            if resp in ("s", "si", "sí", "y", "yes"):
                callback_guardar()
                break
            elif resp in ("n", "no"):
                break
            elif resp == "":
                # Ignora los 'enters' residuales
                continue
            else:
                print("  [Por favor, responde 's' para sí, o 'n' para no]")
        except (EOFError, KeyboardInterrupt):
            print("\n  [Operación cancelada]")
            break

def _nombre_archivo(origen: str, is_batch: bool = False) -> str:
    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
    tabla = str.maketrans('áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN')
    
    if is_batch:
        if origen and origen != 'terminal':
            base = os.path.splitext(os.path.basename(origen))[0].translate(tabla)
            base = "".join(c if c.isalnum() or c == '_' else '_' for c in base)
            return f"batch_{base}_{fecha}.txt"
        return f"batch_terminal_{fecha}.txt"
    else:
        palabras = origen.strip().rstrip("?.!").split()[:5]
        nombre = "_".join(palabras).lower().translate(tabla)
        nombre = "".join(c if c.isalnum() or c == '_' else '' for c in nombre)
        return f"analisis_{nombre}.txt"

def ejecutar_guardado(origen: str, resultados: list, is_batch: bool):
    nombre_archivo = _nombre_archivo(origen, is_batch)
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    encabezado = (
        "=" * 60 + "\n"
        "  ANÁLISIS GRR — ud2rrg + rrg_ls_mapper\n"
        f"  Fuente  : {origen}\n"
        f"  Fecha   : {fecha}\n"
        f"  Total   : {len(resultados)} oración(es)\n"
        "=" * 60 + "\n\n"
        "NOTA PARA ABRIR CORRECTAMENTE:\n"
        "  • Usa un editor con fuente MONOESPACIADA (Courier New, Consolas)\n"
        "  • No pegues el árbol en un párrafo normal de Word\n"
        "\n" + "=" * 60 + "\n\n"
    )

    bloques = []
    for n, res in enumerate(resultados, start=1):
        bloque = f"{'═' * 60}\n  ORACIÓN {n}: {res.get('oracion', 'N/A')}\n{'═' * 60}\n\n"
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
                    bloque += f"  Argumentos     : {ls['args_map']}\n\n"

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

    print(f"\n[OK] Análisis guardado con éxito en: {nombre_archivo}")

# ---------------------------------------------------------------------------
# MOTORES DE PROCESAMIENTO
# ---------------------------------------------------------------------------
def procesar_oraciones(nlp, oraciones: list[str]) -> list[dict]:
    resultados = []
    total = len(oraciones)

    for n, oracion in enumerate(oraciones, start=1):
        if total > 1:
            print(f"\n{'═'*56}")
            print(f"  [{n}/{total}]  {oracion}")
            print(f"{'═'*56}")

        doc = nlp(oracion)
        
        open(CONLLU_PATH, 'w', encoding='utf-8').close()
        CoNLL.write_doc2conll(doc, CONLLU_PATH)
        limpiar_conllu_stanza(CONLLU_PATH)

        ls_lista = [map_sentence_to_ls(sent) for sent in doc.sentences]
        inyectar_metadata_rrg(CONLLU_PATH, ls_lista)

        for i, ls in enumerate(ls_lista, start=1):
            if total == 1:
                imprimir_ls(ls, i)
            else:
                sub = f" (sub-oración {i})" if len(ls_lista) > 1 else ""
                print(f"\n  LS{sub}")
                print(f"  Tipo     : {ls['ls_type'].upper()}")
                print(f"  Formal   : {ls['ls_formal']}")
                print(f"  Léxica   : {ls['ls_lexical']}")
                if ls['args_map']:
                    print(f"  Args     : {ls['args_map']}")

        if total == 1:
            imprimir_conllu(CONLLU_PATH)

        stdout, stderr = correr_ud2rrg(CONLLU_PATH)
        arboles = _dividir_arboles_ud2rrg(stdout)

        if total > 1:
            print()
        for i, arbol in enumerate(arboles, start=1):
            if total == 1:
                print(f"\n{'─'*56}\n  ÁRBOL RRG\n{'─'*56}")
            else:
                sub = f" (sub-oración {i})" if len(arboles) > 1 else ""
                print(f"  Árbol RRG{sub}:")
            print(arbol)

        if stderr:
            print(f"\n  ⚠️ Advertencias ud2rrg:\n{stderr}")

        resultados.append({
            'oracion': oracion,
            'ls_lista': ls_lista,
            'stdout': stdout
        })
    return resultados

def leer_oraciones_desde_archivo(ruta: str) -> list[str]:
    if not os.path.exists(ruta):
        print(f"[ERROR] No se encontró el archivo: {ruta}")
        return []
    with open(ruta, 'r', encoding='utf-8') as f:
        lineas = f.readlines()
    return [l.strip() for l in lineas if l.strip() and not l.strip().startswith('#')]

def leer_oraciones_desde_terminal() -> list[str]:
    print("\n  Escribe una oración por línea.")
    print("  Escribe FIN (o presiona Enter dos veces seguidas) para terminar.\n")
    oraciones = []
    vacias = 0
    while True:
        try:
            linea = input(f"  [{len(oraciones)+1}] ").strip()
        except EOFError:
            break
        if linea.lower() == 'fin':
            break
        if not linea:
            vacias += 1
            if vacias >= 2: break
            continue
        vacias = 0
        oraciones.append(linea)
    return oraciones

def leer_ls_desde_conllu(conllu_path: str) -> list[dict]:
    resultado = []
    with open(conllu_path, 'r', encoding='utf-8') as f:
        content = f.read()
    for bloque in content.strip().split('\n\n'):
        if not bloque.strip(): continue
        ls = {'ls_type': 'desconocido', 'ls_formal': '', 'ls_lexical': '', 'args_map': ''}
        for line in bloque.split('\n'):
            if line.startswith('# rrg_ls_type'): ls['ls_type'] = line.split('=', 1)[1].strip()
            elif line.startswith('# rrg_ls_lex'): ls['ls_lexical'] = line.split('=', 1)[1].strip()
            elif line.startswith('# rrg_ls '): ls['ls_formal'] = line.split('=', 1)[1].strip()
            elif line.startswith('# rrg_args'): ls['args_map'] = line.split('=', 1)[1].strip()
        if ls['ls_formal'] or ls['ls_lexical']:
            resultado.append(ls)
    return resultado

# ---------------------------------------------------------------------------
# MENÚ PRINCIPAL Y FLUJOS
# ---------------------------------------------------------------------------
def main():
    print(SEP)
    print("  PARSER GRR INTEGRADO — MENÚ INTERACTIVO")
    print(SEP)

    print("\n[INFO] Cargando modelos base (esto tomará un momento)...")
    nlp = cargar_pipeline_stanza(LANG)
    
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
    
    print("[OK] Sistema listo.\n")

    while True:
        print(f"\n{SEP}")
        print("  ¿QUÉ DESEAS HACER?")
        print(f"{SEP}")
        print("  1. Analizar una oración (Modo iterativo)")
        print("  2. Analizar varias oraciones (Modo Batch Terminal)")
        print("  3. Analizar oraciones desde un archivo (.txt o .conllu)")
        print("  4. Salir")
        
        opcion = input("\n  Elige una opción (1-4): ").strip()

        if opcion == '1':
            while True:
                oracion = input("\nEscribe una oración (o 'volver' para ir al menú): ").strip()
                if oracion.lower() in ['volver', 'salir', 'exit']:
                    break
                if not oracion:
                    continue
                
                print(f"\nAnalizando: '{oracion}'...")
                resultados = procesar_oraciones(nlp, [oracion])
                preguntar_guardar(lambda: ejecutar_guardado(oracion, resultados, is_batch=False))

        elif opcion == '2':
            print(f"\n{SEP}\n  MODO BATCH — TERMINAL\n{SEP}")
            oraciones = leer_oraciones_desde_terminal()
            if not oraciones:
                print("  [AVISO] No se ingresaron oraciones.")
                continue
            
            print(f"\n[INFO] Procesando {len(oraciones)} oración(es)...")
            resultados = procesar_oraciones(nlp, oraciones)
            preguntar_guardar(lambda: ejecutar_guardado('terminal', resultados, is_batch=True))

        elif opcion == '3':
            print(f"\n{SEP}\n  MODO ARCHIVO\n{SEP}")
            ruta = input("  Ingresa la ruta del archivo (.txt o .conllu) o 'volver': ").strip()
            if ruta.lower() == 'volver' or not ruta:
                continue
            
            if not os.path.exists(ruta):
                print(f"  [ERROR] El archivo no existe: {ruta}")
                continue

            # Flujo si es un CoNLL-U ya anotado
            if ruta.endswith('.conllu'):
                print("\n[INFO] Leyendo estructuras lógicas del archivo CoNLL-U...")
                ls_data_lista = leer_ls_desde_conllu(ruta)
                stdout, stderr = correr_ud2rrg(ruta)
                resultados = [{'oracion': f"Archivo: {os.path.basename(ruta)}", 'ls_lista': ls_data_lista, 'stdout': stdout}]
                
                for i, ls in enumerate(ls_data_lista, start=1):
                    imprimir_ls(ls, i)
                print(f"\n{'─'*56}\n  ÁRBOL RRG GLOBAL\n{'─'*56}")
                print(stdout)
                
                if stderr: print(f"\n⚠️ Advertencias:\n{stderr}")
                preguntar_guardar(lambda: ejecutar_guardado(os.path.basename(ruta), resultados, is_batch=True))

            # Flujo si es un archivo de texto plano
            else:
                oraciones = leer_oraciones_desde_archivo(ruta)
                if not oraciones:
                    continue
                print(f"\n[INFO] Procesando {len(oraciones)} oración(es) desde {os.path.basename(ruta)}...")
                resultados = procesar_oraciones(nlp, oraciones)
                preguntar_guardar(lambda: ejecutar_guardado(os.path.basename(ruta), resultados, is_batch=True))

        elif opcion == '4':
            print("\nCerrando el parser. ¡Éxito en tu investigación!")
            break
        else:
            print("  [Opción no válida. Intenta de nuevo]")

if __name__ == "__main__":
    main()