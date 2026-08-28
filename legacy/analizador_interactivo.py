import sys
import os
import subprocess
import stanza
from stanza.utils.conll import CoNLL
from datetime import datetime


def guardar_arbol(oracion, salida):
    """Guarda el árbol RRG en un archivo .txt con encabezado informativo."""

    # Generar nombre de archivo a partir de las primeras palabras de la oración
    palabras = oracion.strip().rstrip("?.!").split()[:5]
    nombre_base = "_".join(palabras).lower()
    # Normalizar caracteres acentuados y limpiar caracteres no válidos
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

    with open(nombre_archivo, 'w', encoding='utf-8') as f:
        f.write(encabezado)
        f.write(salida)
        f.write("\n")

    print(f"\n  [OK] Árbol guardado en: {nombre_archivo}")
    print(f"       Ábrelo con un editor de texto y fuente Courier New.")


def main():
    print("==================================================")
    print(" Iniciando el Analizador Sintáctico RRG...")
    print("==================================================")

    # Cargamos el modelo una sola vez al inicio
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

    # Bucle infinito para pedir oraciones continuamente
    while True:
        oracion = input("Escribe una oración en español (o 'salir' para terminar): ")

        # Condición de salida
        if oracion.strip().lower() in ['salir', 'exit', 'quit']:
            print("\nCerrando el analizador. ¡Hasta pronto!")
            break

        # Si el usuario presiona Enter sin escribir nada, volvemos a preguntar
        if not oracion.strip():
            continue

        print(f"\nAnalizando: '{oracion}'")

        # Procesar con Stanza
        doc = nlp(oracion)
        archivo_conllu_temp = "input_estudiante.conllu"
        CoNLL.write_doc2conll(doc, archivo_conllu_temp)

        # Filtro de compatibilidad para ud2rrg
        with open(archivo_conllu_temp, 'r', encoding='utf-8') as f:
            conllu_texto = f.read()
        conllu_texto = conllu_texto.replace('\tobl:arg\t', '\tobl\t')
        with open(archivo_conllu_temp, 'w', encoding='utf-8') as f:
            f.write(conllu_texto)

        print("[OK] Generando árbol RRG...\n")

        # Llamar a convertir.py capturando la salida
        resultado = subprocess.run(
            ["python3", "convertir.py", archivo_conllu_temp, "es"],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

        salida = resultado.stdout
        if resultado.stderr:
            salida += "\n[ADVERTENCIAS]:\n" + resultado.stderr

        # Mostrar el árbol en terminal
        print(salida)

        # Preguntar si desea guardar
        respuesta = input("  ¿Guardar este árbol en un archivo .txt? (s/n): ").strip().lower()
        if respuesta in ('s', 'si', 'sí', 'yes', 'y'):
            guardar_arbol(oracion, salida)

        print("--------------------------------------------------\n")


if __name__ == "__main__":
    main()
