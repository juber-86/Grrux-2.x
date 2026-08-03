"""
analizar_texto.py
=================
Pipeline integrado:
  1. Stanza analiza la oración y produce CoNLL-U base
  2. rrg_ls_mapper genera la Estructura Lógica GRR
  3. Los metadatos rrg_* se inyectan como comentarios en el .conllu
  4. ud2rrg (vía convertir.py) genera el árbol sintáctico
  5. La salida final combina LS + árbol en pantalla

Uso:
  python3 analizar_texto.py "Juan come pizza."
  python3 analizar_texto.py                      # usa oración de prueba
"""

import sys
import os
import subprocess
import stanza
from stanza.utils.conll import CoNLL
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
# UTILIDADES
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
      1. MISC: elimina start_char/end_char que ud2rrg no espera; si no queda
         nada útil, pone '_'.
      2. Lema: corrige lemas erróneos conocidos del modelo es de Stanza
         (ej. 'comir' → 'comer').
      3. Orden y numeración de sent_id: Stanza puede poner # text antes que
         # sent_id, o poner sent_id=0. Se reordena a sent_id → text y se
         renumeran desde 1.

    Nota: añadir entradas a LEMA_FIXES cuando aparezcan nuevos errores de
    lematización del modelo es de Stanza.
    """
    LEMA_FIXES = {
        'comir': 'comer',
    }
    MISC_STRIP = {'start_char', 'end_char'}

    with open(conllu_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Dividir en bloques de oración (separados por línea vacía)
    bloques_raw = content.strip().split('\n\n')
    bloques_limpios = []
    sent_counter = 0

    for bloque in bloques_raw:
        if not bloque.strip():
            continue

        lines = bloque.split('\n')
        comentarios = [l for l in lines if l.startswith('#')]
        tokens     = [l for l in lines if not l.startswith('#') and l.strip()]

        # Extraer text= y sent_id= existentes
        text_line   = next((l for l in comentarios if l.startswith('# text')), None)
        # Ignorar sent_id de Stanza — siempre regeneramos
        sent_counter += 1
        nuevos_comentarios = [f'# sent_id = {sent_counter}']
        if text_line:
            nuevos_comentarios.append(text_line)
        # Otros comentarios que no sean sent_id ni text (rrg_* etc.)
        for c in comentarios:
            if not c.startswith('# sent_id') and not c.startswith('# text'):
                nuevos_comentarios.append(c)

        # Limpiar tokens
        tokens_limpios = []
        for tok in tokens:
            cols = tok.split('\t')
            if len(cols) == 10:
                # Lema
                cols[2] = LEMA_FIXES.get(cols[2], cols[2])
                # XPOS — ud2rrg no maneja los códigos ANCORA de Stanza
                cols[4] = '_'
                # MISC
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
    Lee el .conllu generado por Stanza y, después de cada línea '# text = ...',
    inserta los comentarios rrg_* correspondientes.

    Maneja múltiples oraciones correctamente.
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


# ---------------------------------------------------------------------------
# SALIDA FORMATEADA
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
    oracion = sys.argv[1] if len(sys.argv) > 1 else "Juan come pizza."

    print(SEP)
    print(f"  ANÁLISIS GRR INTEGRADO")
    print(f"  Texto: «{oracion}»")
    print(SEP)

    # 1. Análisis Stanza
    print("\n[1/4] Ejecutando Stanza...")
    nlp = cargar_pipeline_stanza(LANG)
    doc = nlp(oracion)

    # 2. Generar CoNLL-U base
    print("[2/4] Generando CoNLL-U base...")
    CoNLL.write_doc2conll(doc, CONLLU_PATH)

    # 2b. Limpiar CoNLL-U de Stanza (lemas, MISC, sent_id)
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

    print(f"\n{SEP}")
    print("  ÁRBOL SINTÁCTICO RRG (ud2rrg)")
    print(SEP)
    if stdout:
        print(stdout)
    else:
        print("  (sin salida)")
    if stderr:
        print(f"\n⚠️  Advertencias ud2rrg:\n{stderr}")

    print(f"\n{SEP}")
    print("  RESUMEN FINAL")
    print(SEP)
    for i, ls in enumerate(ls_data_lista, start=1):
        print(f"  [{i}] {ls['ls_lexical']}")
    print()


if __name__ == "__main__":
    main()
