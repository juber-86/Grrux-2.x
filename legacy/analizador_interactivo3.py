import sys
import os
import subprocess
import stanza
from stanza.utils.conll import CoNLL
from datetime import datetime


def _extraer_primer_bloque(salida_raw):
    """
    Extrae el primer bloque de árbol completo del stdout de convertir.py.

    La duplicación ocurre porque convertir.py puede iterar internamente
    sobre todas las oraciones del .conllu o porque la importación de ud2rrg
    provoca ejecuciones circulares que repiten el output N veces en el buffer.
    Esta función corta después del primer bloque, definido como el texto que
    termina justo antes de que aparezca una repetición del mismo contenido.

    Estrategia:
      1. Eliminar líneas de diagnóstico conocidas.
      2. Detectar el marcador de inicio de bloque de árbol (línea de guiones
         o la primera línea no vacía).
      3. Retornar solo hasta la segunda ocurrencia del marcador de inicio,
         o la totalidad del texto limpio si no hay duplicación.
    """
    PREFIJOS_DIAGNOSTICO = (
        "Convirtiendo:",
        "--- Oración",
        "--- Oraci",      # fallback sin tilde
        "Convertidas:",
        "ÁRBOL RRG",      # encabezado que convertir.py pudiera emitir
        "árbol rrg",      # variante en minúsculas
        "ud2rrg",         # línea de crédito del módulo
    )

    lineas_filtradas = []
    for linea in salida_raw.splitlines():
        stripped = linea.strip()
        if any(stripped.startswith(p) or stripped.lower().startswith(p.lower())
               for p in PREFIJOS_DIAGNOSTICO):
            continue
        lineas_filtradas.append(linea)

    # Detectar duplicación: buscamos la primera línea no vacía significativa
    # (el "ancla" del árbol) y cortamos cuando aparece por segunda vez.
    ancla = None
    for linea in lineas_filtradas:
        if linea.strip():
            ancla = linea
            break

    if ancla is None:
        # stdout vacío o sin contenido útil
        return ""

    # Buscar segunda ocurrencia del ancla → ahí empieza la copia duplicada
    primera = lineas_filtradas.index(ancla)
    try:
        segunda = lineas_filtradas.index(ancla, primera + 1)
        bloque = lineas_filtradas[primera:segunda]
    except ValueError:
        # No hay duplicación: usar todo el contenido filtrado
        bloque = lineas_filtradas[primera:]

    return "\n".join(bloque).strip()


def guardar_arbol(oracion, archivo_conllu):
    """Re-ejecuta convertir.py capturando stdout a un archivo .txt."""

    palabras = oracion.strip().rstrip("?.!").split()[:5]
    nombre_base = "_".join(palabras).lower()
    reemplazos = str.maketrans('áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN')
    nombre_base = nombre_base.translate(reemplazos)
    nombre_base = "".join(c if c.isalnum() or c == '_' else '' for c in nombre_base)
    nombre_archivo = f"arbol_{nombre_base}.txt"

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")

    encabezado = (
        "=" * 60 + "\n"
        "  ÁRBOL RRG — ud2rrg\n"
        f"  Oración : {oracion}\n"
        f"  Fecha   : {fecha}\n"
        "=" * 60 + "\n\n"
        "NOTA PARA ABRIR CORRECTAMENTE:\n"
        "  • Abre este archivo con un editor de texto\n"
        "    (Gedit, Notepad, VS Code, etc.).\n"
        "  • Usa una fuente MONOESPACIADA (Courier New, Consolas,\n"
        "    DejaVu Sans Mono) para que las ramas queden alineadas.\n"
        "  • Para incluir en Word/LibreOffice: inserta el texto en\n"
        "    un cuadro de texto con fuente Courier New (9-10pt).\n"
        "  • NO pegues el árbol directamente en un párrafo normal:\n"
        "    las ramas se desalinearán al cambiar de fuente.\n"
        "\n" + "=" * 60 + "\n\n"
    )

    # Preparar entorno del subproceso.
    # NO usar python3 -I: ese flag aísla sys.path y rompe 'import ud2rrg',
    # que vive en el mismo directorio que convertir.py.
    # Usamos cwd= al directorio de convertir.py para que Python lo encuentre,
    # igual que lo hace os.system() al ejecutar desde el mismo directorio.
    directorio_convertir = os.path.dirname(os.path.abspath("convertir.py"))
    archivo_conllu_abs = os.path.abspath(archivo_conllu)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("PYTHONPATH", None)   # limpiar PYTHONPATH heredado del shell

    resultado = subprocess.run(
        ["python3", "convertir.py", archivo_conllu_abs, "es"],
        cwd=directorio_convertir,   # ud2rrg es importable desde aquí
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )

    # Decodificar stdout
    salida_raw = resultado.stdout.decode('utf-8', errors='replace')

    # Registrar stderr si no está vacío (ayuda a diagnosticar import circular)
    stderr_txt = resultado.stderr.decode('utf-8', errors='replace').strip()
    if stderr_txt:
        print(f"\n  [AVISO] convertir.py emitió mensajes en stderr:")
        for ln in stderr_txt.splitlines()[:10]:   # máximo 10 líneas
            print(f"          {ln}")

    # Extraer el primer bloque de árbol, sin duplicaciones
    salida_limpia = _extraer_primer_bloque(salida_raw)

    if not salida_limpia:
        print("\n  [ERROR] No se obtuvo contenido del árbol. "
              "Revisa que convertir.py funcione correctamente.")
        return

    # Escribir el archivo: modo 'w' garantiza truncar cualquier versión previa
    with open(nombre_archivo, 'w', encoding='utf-8') as f:
        f.write(encabezado)
        f.write(salida_limpia)
        f.write("\n")

    print(f"\n  [OK] Árbol guardado en: {nombre_archivo}")
    print(f"       Ábrelo con un editor de texto y fuente Courier New.")


def main():
    print("==================================================")
    print(" Iniciando el Analizador Sintáctico RRG...")
    print("==================================================")

    try:
        nlp = stanza.Pipeline(
            lang='es', package='gsd',
            processors='tokenize,mwt,pos,lemma,depparse',
            verbose=False
        )
    except Exception:
        print("Descargando el modelo GSD de español por primera vez (~500 MB)...")
        stanza.download('es', package='gsd')
        nlp = stanza.Pipeline(
            lang='es', package='gsd',
            processors='tokenize,mwt,pos,lemma,depparse',
            verbose=False
        )

    print("\n[OK] Motor NLP cargado y listo.\n")

    archivo_conllu_temp = "input_estudiante.conllu"

    while True:
        oracion = input("Escribe una oración en español (o 'salir' para terminar): ")

        if oracion.strip().lower() in ['salir', 'exit', 'quit']:
            print("\nCerrando el analizador. ¡Hasta pronto!")
            break

        if not oracion.strip():
            continue

        print(f"\nAnalizando: '{oracion}'")

        # Procesar con Stanza
        doc = nlp(oracion)

        # Truncar el archivo antes de escribir para evitar acumulación
        with open(archivo_conllu_temp, 'w', encoding='utf-8') as f:
            f.write("")
        CoNLL.write_doc2conll(doc, archivo_conllu_temp)

        # Filtro de compatibilidad para ud2rrg
        with open(archivo_conllu_temp, 'r', encoding='utf-8') as f:
            conllu_texto = f.read()
        conllu_texto = conllu_texto.replace('\tobl:arg\t', '\tobl\t')
        with open(archivo_conllu_temp, 'w', encoding='utf-8') as f:
            f.write(conllu_texto)

        print("[OK] Generando árbol RRG...\n")

        # Mostrar el árbol en terminal con os.system (funciona bien)
        os.system(f"python3 convertir.py {archivo_conllu_temp} es")

        print()

        # Preguntar si desea guardar
        respuesta = input("  ¿Guardar este árbol en un archivo .txt? (s/n): ").strip().lower()
        if respuesta in ('s', 'si', 'sí', 'yes', 'y'):
            # Re-ejecutar capturando stdout para el archivo
            guardar_arbol(oracion, archivo_conllu_temp)

        print("--------------------------------------------------\n")


if __name__ == "__main__":
    main()
