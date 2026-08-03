#!/bin/bash
# ============================================================
# descargar_treebanks_es.sh
# Descarga los treebanks de español de Universal Dependencies
# Uso: bash descargar_treebanks_es.sh
# Corre desde: ~/proyectos/ud2rrg (con venv activo)
# ============================================================

# ------------------------------------------------------------
# Descripción de los treebanks disponibles:
#
# GSD   — ~16,000 oraciones, noticias y Wikipedia
#          Alta tasa de éxito con ud2rrg. Recomendado.
#
# PUD   — 1,000 oraciones, noticias y Wikipedia
#          Más pequeño, bueno para pruebas rápidas.
#
# AnCora — ~17,000 oraciones, noticias
#          El más grande pero requiere preprocesamiento
#          antes de usarlo con ud2rrg (ver nota abajo)
# ------------------------------------------------------------

TREEBANK_DIR=~/treebanks/spanish
mkdir -p "$TREEBANK_DIR"

echo "=================================================="
echo " Descarga de treebanks UD en español"
echo "=================================================="

# ------------------------------------------------------------
# 1. GSD (recomendado para empezar)
# ------------------------------------------------------------
echo ""
echo "[1/3] Descargando UD_Spanish-GSD..."
git clone https://github.com/UniversalDependencies/UD_Spanish-GSD.git \
    "$TREEBANK_DIR/UD_Spanish-GSD"
echo "      Listo: $TREEBANK_DIR/UD_Spanish-GSD"

# ------------------------------------------------------------
# 2. PUD (pequeño, ideal para pruebas)
# ------------------------------------------------------------
echo ""
echo "[2/3] Descargando UD_Spanish-PUD..."
git clone https://github.com/UniversalDependencies/UD_Spanish-PUD.git \
    "$TREEBANK_DIR/UD_Spanish-PUD"
echo "      Listo: $TREEBANK_DIR/UD_Spanish-PUD"

# ------------------------------------------------------------
# 3. AnCora (el más grande)
#    ADVERTENCIA: AnCora NO funciona directamente con ud2rrg.
#    Tiene anotaciones extendidas en columnas 9 y 10 que
#    causan errores de parseo. Antes de usarlo hay que
#    preprocesarlo con un script de limpieza.
#    Por ahora se descarga pero NO se usa directamente.
# ------------------------------------------------------------
echo ""
echo "[3/3] Descargando UD_Spanish-AnCora..."
git clone https://github.com/UniversalDependencies/UD_Spanish-AnCora.git \
    "$TREEBANK_DIR/UD_Spanish-AnCora"
echo "      Listo: $TREEBANK_DIR/UD_Spanish-AnCora"

# ------------------------------------------------------------
# Resumen de archivos disponibles
# ------------------------------------------------------------
echo ""
echo "=================================================="
echo " Treebanks descargados. Archivos .conllu:"
echo ""
echo " GSD (recomendado):"
ls "$TREEBANK_DIR/UD_Spanish-GSD/"*.conllu 2>/dev/null | xargs -I{} basename {}
echo ""
echo " PUD:"
ls "$TREEBANK_DIR/UD_Spanish-PUD/"*.conllu 2>/dev/null | xargs -I{} basename {}
echo ""
echo " AnCora (requiere preprocesamiento):"
ls "$TREEBANK_DIR/UD_Spanish-AnCora/"*.conllu 2>/dev/null | xargs -I{} basename {}
echo ""
echo "=================================================="
echo " Para analizar con ud2rrg, corre por ejemplo:"
echo ""
echo "   cd ~/proyectos/ud2rrg"
echo "   source venv/bin/activate"
echo "   python3 convertir.py """direccion del archivo .conllu .../es_gsd-ud-test.conllu es"""
echo "=================================================="
