"""
analizador_interactivo1.py
==========================

Pipeline:
  1. Stanza analiza la oración y genera CoNLL-U temporal
  2. convertir.py genera el árbol RRG
  3. Se muestra en pantalla
  4. Opcional: se guarda limpio en .txt
"""

import stanza
import subprocess
import tempfile
from datetime import datetime
import os
import sys

# ──────────────────────────────────────────────────────────────
# Inicializar Stanza una sola vez
# ──────────────────────────────────────────────────────────────
print("\n[Inicializando Stanza...]")
nlp = stanza.Pipeline("es", processors="tokenize,pos,lemma,depparse", verbose=False)


# ──────────────────────────────────────────────────────────────
# Función: generar CoNLL-U temporal
# ──────────────────────────────────────────────────────────────
def generar_conllu(oracion):
    doc = nlp(oracion)

    conllu = []
    for sent in doc.sentences:
        for word in sent.words:
            conllu.append(
                f"{word.id}\t{word.text}\t{word.lemma}\t{word.upos}\t_\t_\t{word.head}\t{word.deprel}\t_\t_"
            )
        conllu.append("")

    contenido = "\n".join(conllu)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".conllu", mode="w", encoding="utf-8")
    tmp.write(contenido)
    tmp.close()

    return tmp.name


# ──────────────────────────────────────────────────────────────
# Función: limpiar salida y guardar árbol
# ──────────────────────────────────────────────────────────────
def guardar_arbol(oracion, salida_raw):
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
        "  • Usa una fuente MONOESPACIADA (Courier New, Consolas, DejaVu Sans Mono)\n"
        "  • En Word/LibreOffice usa un cuadro de texto con Courier New 9–10pt\n"
        "  • No pegues el árbol en un párrafo normal\n"
        "\n" + "=" * 60 + "\n\n"
    )

    # 🔥 FILTRO REAL: dejar solo el árbol ASCII
    lineas = []
    copiar = False
    for l in salida_raw.splitlines():
        t = l.strip()
        if t.startswith("┌") or t.startswith("│") or t.startswith("└"):
            copiar = True
        if copiar:
            lineas.append(l)

    salida_limpia = "\n".join(lineas).rstrip()

    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write(encabezado)
        f.write(salida_limpia)
        f.write("\n")

    print(f"\n[OK] Árbol guardado en: {nombre_archivo}")


# ──────────────────────────────────────────────────────────────
# Loop interactivo principal
# ──────────────────────────────────────────────────────────────
def main():
    print("\nAnalizador RRG interactivo (Stanza + ud2rrg)")
    print("Escribe una oración o 'salir'\n")

    while True:
        oracion = input("Oración: ").strip()

        if oracion.lower() in ("salir", "exit", "quit"):
            print("Saliendo.")
            break

        if not oracion:
            continue

        # 1) Generar CoNLL-U
        archivo_conllu = generar_conllu(oracion)

        # 2) Ejecutar convertir.py UNA SOLA VEZ
        resultado = subprocess.run(
            ["python3", "convertir.py", archivo_conllu, "es"],
            capture_output=True,
            text=True
        )

        salida_raw = resultado.stdout

        # Mostrar árbol en pantalla
        print("\n" + salida_raw)

        # 3) Preguntar si guardar
        respuesta = input("\n¿Guardar este árbol en un archivo .txt? (s/n): ").strip().lower()
        if respuesta in ("s", "si", "sí", "y", "yes"):
            guardar_arbol(oracion, salida_raw)

        # Limpiar archivo temporal
        os.remove(archivo_conllu)


if __name__ == "__main__":
    main()
