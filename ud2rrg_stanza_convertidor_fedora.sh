#!/bin/bash
# ============================================================
# Setup_UD2RRG_Zorin.sh
# Setup de ud2rrg en Zorin OS / Linux Mint / Ubuntu-based
# Uso: bash Setup_UD2RRG_Zorin.sh
# ============================================================

set -e

echo "=================================================="
echo " Setup de ud2rrg en Zorin OS / Linux Mint"
echo "=================================================="

echo ""
echo "[1/7] Instalando prerequisitos del sistema..."
sudo dnf update
sudo dnf install -y git wget build-essential python3-dev

# IMPORTANTE: disco-dop NO es compatible con Python 3.12+
# Se instala 3.10 desde el PPA deadsnakes
echo ""
echo "[2/7] Instalando Python 3.10..."
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo dnf update
sudo dnf install -y python3.10 python3.10-venv python3.10-dev
python3.10 --version

echo ""
echo "[3/7] Clonando ud2rrg..."
mkdir -p ~/proyectos
cd ~/proyectos
git clone https://gitlab.com/treegrasp/ud2rrg.git
cd ud2rrg

# IMPORTANTE: todo debe instalarse con el venv activo
# Si se instala fuera del venv, Cython no estará disponible
# al compilar disco-dop
echo ""
echo "[4/7] Creando entorno virtual con Python 3.10..."
python3.10 -m venv venv
source venv/bin/activate
python --version

# NOTA sobre disco-dop:
# No se puede instalar con pip directamente — su código C++
# es incompatible con GCC moderno (error: "no class template named 'rebind'")
# Solución: compilar manualmente con -fpermissive y --no-build-isolation
echo ""
echo "[5/7] Instalando dependencias Python (puede tardar varios minutos)..."
pip install --upgrade pip setuptools wheel
pip install cython
pip show cython

echo ""
echo "     Compilando disco-dop (puede tardar 5-10 minutos)..."
cd ~/proyectos
git clone https://github.com/andreasvc/disco-dop.git
cd disco-dop
git submodule update --init --recursive
CXXFLAGS="-std=c++14 -fpermissive" python setup.py build_ext --inplace
pip install -e . --no-build-isolation

cd ~/proyectos/ud2rrg
pip install conllu grapheme stanza

# ADVERTENCIA VerbNet: en algunos sistemas tar falla silenciosamente
# Si no aparece carpeta verbnet-3.2, intenta: tar -xvzf verbnet-3.2.tar.gz
# La conversión básica funciona sin VerbNet
echo ""
echo "[6/7] Descargando VerbNet..."
wget http://verbs.colorado.edu/verb-index/vn/verbnet-3.2.tar.gz || echo "AVISO: descarga fallo"
tar -xzf verbnet-3.2.tar.gz || echo "AVISO: extraccion fallo, verifica manualmente"

echo ""
echo "[7/7] Creando carpetas y archivos..."
mkdir -p gold_data conllu ud2rrg_output
touch gold_data/en_treebankGoldDev.export

cat > evalparam.prm << 'EOF'
CUTOFF_LEN 40
DISC_ONLY 0
LA 0
TED 0
DEP 0
DEBUG 0
EOF

# IMPORTANTE: printf garantiza tabs reales
# cat <<EOF puede convertir tabs a espacios causando error en conllu
printf '# sent_id = 1\n# text = The cat sleeps.\n1\tThe\tthe\tDET\tDT\tDefinite=Def|PronType=Art\t2\tdet\t_\t_\n2\tcat\tcat\tNOUN\tNN\tNumber=Sing\t3\tnsubj\t_\t_\n3\tsleeps\tsleep\tVERB\tVBZ\tNumber=Sing|Person=3|Tense=Pres\t0\troot\t_\tSpaceAfter=No\n4\t.\t.\tPUNCT\t.\t_\t3\tpunct\t_\t_\n\n' > prueba.conllu

cat > convertir.py << 'EOF'
import sys
import traceback
from conllu import parse_tree_incr
import ud2rrg as converter
from discodop.tree import DrawTree

input_file = sys.argv[1] if len(sys.argv) > 1 else 'prueba.conllu'
language = sys.argv[2] if len(sys.argv) > 2 else 'en'

print(f"Convirtiendo: {input_file} (idioma: {language})\n")

converted = 0
failed = 0

with open(input_file) as f:
    for udtree in parse_tree_incr(f):
        try:
            sent = []
            original_sent_list = [x for x in udtree.serialize().split('\n')
                                  if x != '' and not x.startswith('#') and '\t' in x]
            for word in original_sent_list:
                w = word.split('\t')[1]
                sent.append(w.replace(' ', '_'))

            rrgtree = converter.transform(udtree, language, layer='SENTENCE')
            try:
                rrgtree_final = converter.add_traces_to_rrg(udtree, rrgtree, sent)
            except AssertionError:
                rrgtree_final = rrgtree

            print(f"--- Oracion {converted+1} ---")
            print(' '.join(sent))
            print(DrawTree(rrgtree_final, sent))
            print()
            converted += 1
        except Exception as e:
            print(f"ERROR en oracion {converted+failed+1}: {e}")
            traceback.print_exc()
            failed += 1

print(f"Convertidas: {converted} | Fallidas: {failed}")
EOF

# --- Crea el chunk "analizar_texto.py" para convertir oraciones en español plano a formato conll-u -----------
echo ""
echo "     Creando script analizador con Stanza..."
cat > analizar_texto1.py << 'EOF'
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
        nlp = stanza.Pipeline(lang='es', processors='tokenize,mwt,pos,lemma,depparse', verbose=False)
    except Exception as e:
        print("Descargando el modelo de español por primera vez (esto puede tardar unos minutos)...")
        stanza.download('es')
        nlp = stanza.Pipeline(lang='es', processors='tokenize,mwt,pos,lemma,depparse', verbose=False)

    doc = nlp(oracion)
    archivo_conllu_temp = "input_estudiante.conllu"
    CoNLL.write_doc2conll(doc, archivo_conllu_temp)
    print(f"[OK] Archivo CoNLL-U generado.")
    print("[OK] Generando árbol RRG...\n")
    
    os.system(f"python3 convertir.py {archivo_conllu_temp} es")

if __name__ == "__main__":
    main()
EOF
# ---Aquí termina el chunk de analizar_texto.py-----

echo ""
echo "=================================================="
echo " Instalacion completa. Corriendo prueba..."
echo "=================================================="
python3 convertir.py prueba.conllu en

echo ""
echo "=================================================="
echo " Todo listo!"
echo " Para usar en el futuro:"
echo "   cd ~/proyectos/ud2rrg"
echo "   source venv/bin/activate"
echo "   python3 convertir.py tu_archivo.conllu en"
echo "=================================================="
