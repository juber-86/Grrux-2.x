import sys
import os
import stanza
from stanza.utils.conll import CoNLL

def main():
    oracion = "El gato negro duerme tranquilamente en la alfombra."
    if len(sys.argv) > 1:
        oracion = sys.argv[1]

    print("==================================================")
    print(f" Analizando: '{oracion}'")
    print("==================================================")

    try:
        # Intentar cargar el modelo localmente
        nlp = stanza.Pipeline(lang='es', processors='tokenize,mwt,pos,lemma,depparse', verbose=False)
    except Exception as e:
        # Si falla, es porque no está descargado
        print("Descargando el modelo de español por primera vez (aprox. 500 MB)...")
        print("Esto puede tardar unos minutos dependiendo de tu conexión.")
        stanza.download('es')
        nlp = stanza.Pipeline(lang='es', processors='tokenize,mwt,pos,lemma,depparse', verbose=False)

    doc = nlp(oracion)
    archivo_conllu_temp = "input_estudiante.conllu"
    CoNLL.write_doc2conll(doc, archivo_conllu_temp)
    print(f"[OK] Análisis sintáctico completado.")
    print("[OK] Generando árbol en formato RRG...\n")
    
    # Llamar a ud2rrg
    os.system(f"python3 convertir.py {archivo_conllu_temp} es")

if __name__ == "__main__":
    main()
