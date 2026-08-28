#!/bin/bash
# ============================================================
# setup_analizador_propio.sh
# Instala Stanza y crea el script para analizar oraciones propias.
# Requisito: Haber corrido ud2rrg_debian.sh previamente.
# ============================================================

set -e

echo "=================================================="
echo " Preparando el entorno para oraciones propias..."
echo "=================================================="

# 1. Verificar que el entorno previo existe
if [ ! -d ~/proyectos/ud2rrg/venv ]; then
    echo "ERROR: No se encontró el entorno virtual en ~/proyectos/ud2rrg/venv."
    echo "Asegúrate de haber instalado ud2rrg primero."
    exit 1
fi

# 2. Navegar al proyecto y activar el entorno
cd ~/proyectos/ud2rrg
source venv/bin/activate

# 3. Instalar Stanza
echo ""
echo "[1/2] Instalando Stanza (librería de Stanford NLP)..."
pip install stanza

# 4. Crear el script de análisis
echo ""
echo "[2/2] Creando el script analizar_texto.py..."

cat > analizar_texto.py << 'EOF'
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
EOF

echo ""
echo "=================================================="
echo " ¡Todo listo para la Fase 2!"
echo " Para analizar una oración propia, usa estos comandos:"
echo ""
echo "   cd ~/proyectos/ud2rrg"
echo "   source venv/bin/activate"
echo "   python3 analizar_texto.py \"Escribe tu oración aquí.\""
echo "=================================================="
