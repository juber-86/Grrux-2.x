import sys
import os
import subprocess
import stanza
from stanza.utils.conll import CoNLL
from datetime import datetime


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

    # Re-ejecutar convertir.py y capturar su salida con el shell
    # Usamos PYTHONIOENCODING para asegurar UTF-8
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    resultado = subprocess.run(
        ["python3", "convertir.py", archivo_conllu, "es"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )

    # Decodificar bytes manualmente para evitar problemas de encoding
    salida_raw = resultado.stdout.decode('utf-8', errors='replace')

    # Filtrar líneas diagnósticas, conservar solo el árbol
    lineas_limpias = []
    for linea in salida_raw.splitlines():
        if linea.startswith("Convirtiendo:"):
            continue
        if linea.startswith("--- Oración") or linea.startswith("--- Oraci"):
            continue
        if linea.startswith("Convertidas:"):
            continue
        lineas_limpias.append(linea)
    salida_limpia = "\n".join(lineas_limpias).strip()

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
