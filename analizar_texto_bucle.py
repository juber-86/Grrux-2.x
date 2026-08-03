import sys
import os
import stanza
from stanza.utils.conll import CoNLL

def main():
    print("==================================================")
    print(" Iniciando el Analizador Sintáctico RRG...")
    print("==================================================")

    # Cargamos el modelo una sola vez al inicio
    try:
        nlp = stanza.Pipeline(lang='es', package='gsd', processors='tokenize,mwt,pos,lemma,depparse', verbose=False)
    except Exception as e:
        print("Descargando el modelo GSD de español por primera vez (aprox. 500 MB)...")
        stanza.download('es', package='gsd')
        nlp = stanza.Pipeline(lang='es', package='gsd', processors='tokenize,mwt,pos,lemma,depparse', verbose=False)

    print("\n[OK] Motor NLP cargado y listo.\n")

    # Bucle infinito para pedir oraciones continuamente
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
        
        # Procesamos la oración con Stanza
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
        
        # Llamar a ud2rrg
        os.system(f"python3 convertir.py {archivo_conllu_temp} es")
        
        print("--------------------------------------------------")

if __name__ == "__main__":
    main()
