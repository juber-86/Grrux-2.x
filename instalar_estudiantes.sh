#!/usr/bin/env bash
# ============================================================================
# instalar_estudiantes.sh — instalador de GRRux para las laptops de los
# estudiantes (Linux Mint 21+ o Ubuntu 22.04, incluido Ubuntu en WSL).
#
# Deja lista GRRux en sus DOS formas de uso:
#   • Terminal (CLI):  ./venv/bin/python grrux_ai1.py
#   • Interfaz gráfica (GUI):  ./grrux-gui   →   http://127.0.0.1:8763/
#
# ANTES de correr esto, copiar de la USB a la máquina:
#   1. la carpeta del repo (esta) ................ ~/proyectos/ud2rrg
#   2. la carpeta disco-dop (HERMANA del repo) ... ~/proyectos/disco-dop
#   3. los modelos de Stanza ..................... ~/.cache/stanza
#   4. el modelo BERTIN .......................... ~/.cache/huggingface
# (los pasos 3 y 4 son opcionales: si faltan, se descargan de internet
#  ~2 GB la primera vez que se analice una oración)
#
# Uso:
#   bash instalar_estudiantes.sh                  # verifica e instala todo
#   bash instalar_estudiantes.sh --solo-verificar # solo revisa, no instala
#
# Qué hace: verifica archivos y Python → instala dependencias del sistema
# (gcc etc., pide sudo solo para eso) → crea el venv → instala los paquetes
# de Python (torch en variante CPU, sin CUDA) → compila disco-dop → prueba
# que todo importe (núcleo + GUI). Al final explica cómo abrir la GUI
# (con instrucciones específicas para WSL) y ofrece una prueba completa.
# ============================================================================
set -u

# ── colores / mensajes ──────────────────────────────────────────────────────
if [ -t 1 ]; then
  ROJO=$'\033[1;31m'; VERDE=$'\033[1;32m'; AMBAR=$'\033[1;33m'; AZUL=$'\033[1;34m'; FIN=$'\033[0m'
else
  ROJO=""; VERDE=""; AMBAR=""; AZUL=""; FIN=""
fi
ok()    { echo "  ${VERDE}[OK]${FIN}    $*"; }
falta() { echo "  ${ROJO}[FALTA]${FIN} $*"; }
aviso() { echo "  ${AMBAR}[AVISO]${FIN} $*"; }
paso()  { echo; echo "${AZUL}== $* ==${FIN}"; }
morir() { echo; echo "${ROJO}ERROR:${FIN} $*"; echo "Instalación detenida — nada quedó a medias peligroso; se puede volver a correr."; exit 1; }

SOLO_VERIFICAR=0
[ "${1:-}" = "--solo-verificar" ] && SOLO_VERIFICAR=1

# ── ¿estamos en WSL? (para dar instrucciones específicas al final) ───────────
ES_WSL=0
if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null || [ -n "${WSL_DISTRO_NAME:-}" ]; then
  ES_WSL=1
fi

# ── rutas ───────────────────────────────────────────────────────────────────
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DISCODOP_DIR="${DISCODOP_DIR:-$(dirname "$REPO")/disco-dop}"
STANZA_CACHE="$HOME/.cache/stanza"
HF_BERTIN="$HOME/.cache/huggingface/hub/models--bertin-project--bertin-roberta-base-spanish"
VENV="$REPO/venv"

echo "GRRux — instalador para estudiantes"
echo "  repo:      $REPO"
echo "  disco-dop: $DISCODOP_DIR"
[ "$ES_WSL" = 1 ] && echo "  entorno:   Ubuntu sobre WSL detectado"

# ══════════════════════════════════════════════════════════════════════════
paso "1/6 Verificando Python"
# ══════════════════════════════════════════════════════════════════════════
PYTHON=""
if command -v python3.10 >/dev/null 2>&1; then
  PYTHON=python3.10
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
else
  morir "no hay Python 3 instalado (sudo apt install python3 python3-venv python3-dev)"
fi
PYVER="$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
case "$PYVER" in
  3.10) ok "Python $PYVER ($PYTHON) — la misma versión del sistema de referencia" ;;
  3.11|3.12|3.13)
    aviso "Python $PYVER — GRRux está probado con 3.10 (Mint 21 / Ubuntu 22.04)."
    aviso "Puede funcionar, pero si algo falla al compilar disco-dop, usar Ubuntu 22.04."
    read -r -p "  ¿Continuar igualmente? [Enter para seguir, Ctrl+C para salir] " _ ;;
  *) morir "Python $PYVER es demasiado viejo: GRRux necesita 3.10 o más (Mint 21+ / Ubuntu 22.04+)" ;;
esac

# ══════════════════════════════════════════════════════════════════════════
paso "2/6 Verificando archivos copiados de la USB"
# ══════════════════════════════════════════════════════════════════════════
FALTAN=0
requerir() {  # requerir <ruta relativa al repo o absoluta> <descripción>
  local ruta="$1"; [ "${ruta#/}" = "$ruta" ] && ruta="$REPO/$1"
  if [ -e "$ruta" ]; then ok "$2"; else falta "$2  →  $ruta"; FALTAN=1; fi
}

# núcleo de la terminal (grrux_ai1.py y todo su árbol de imports)
requerir grrux_ai1.py                 "grrux_ai1.py (la terminal)"
requerir convertir.py                 "convertir.py"
requerir ud2rrg.py                    "ud2rrg.py (conversor sintáctico)"
requerir export.py                    "export.py"
requerir linkage.py                   "linkage.py"
requerir util.py                      "util.py"
requerir verbnet.py                   "verbnet.py"
requerir add_traces_to_rrg_from_ud.py "add_traces_to_rrg_from_ud.py"
requerir rrg_ls_mapper.py             "rrg_ls_mapper.py (mapper semántico)"
requerir requirements.txt             "requirements.txt (lista de paquetes)"
requerir aspect_classifier/__init__.py  "paquete aspect_classifier/"
requerir aspect_classifier/config.yaml  "aspect_classifier/config.yaml"
requerir aspect_classifier/data/glosario_grrux.csv       "glosario (-help)"
requerir aspect_classifier/data/verbos_ditransitivos.xlsx "léxico de ditransitivas"
requerir aspect_classifier/data/causative_lexicon.csv     "léxico causativo"
requerir aspect_classifier/data/contextual_sentences.csv  "dataset contextual"
requerir aspect_classifier/data/embeddings/embeddings.npy     "embeddings léxicos"
requerir aspect_classifier/data/embeddings/embeddings_ctx.npy "embeddings contextuales"

N_JOBLIB="$(find "$REPO/aspect_classifier/models" -name '*.joblib' 2>/dev/null | wc -l)"
if [ "$N_JOBLIB" -ge 8 ]; then
  ok "clasificador entrenado ($N_JOBLIB archivos .joblib)"
else
  falta "clasificador entrenado — se esperaban 8 .joblib en aspect_classifier/models/, hay $N_JOBLIB"
  FALTAN=1
fi

if [ -f "$DISCODOP_DIR/setup.py" ] && [ -d "$DISCODOP_DIR/discodop" ]; then
  ok "disco-dop (carpeta hermana del repo)"
else
  falta "disco-dop  →  $DISCODOP_DIR (copiarla JUNTO a la carpeta del repo, o correr con DISCODOP_DIR=/ruta bash instalar_estudiantes.sh)"
  FALTAN=1
fi

# GUI — ahora OBLIGATORIA (la queremos disponible en todas las laptops)
GUI_OK=1
for f in grrux-gui grrux_motor.py grrux_server.py gui/index.html gui/app.js gui/estilo.css; do
  if [ -e "$REPO/$f" ]; then ok "GUI: $f"; else falta "GUI: $f  →  $REPO/$f"; GUI_OK=0; FALTAN=1; fi
done

# modelos (opcionales: sin ellos se descargan de internet)
MODELOS_FALTAN=0
if find "$STANZA_CACHE" -maxdepth 4 -type d -name es 2>/dev/null | grep -q .; then
  ok "modelos de Stanza en español ($STANZA_CACHE)"
else
  aviso "modelos de Stanza NO copiados — se descargarán (~1.5 GB) al primer análisis"
  MODELOS_FALTAN=1
fi
if [ -d "$HF_BERTIN/snapshots" ]; then
  ok "modelo BERTIN ($HF_BERTIN)"
else
  aviso "modelo BERTIN NO copiado — se descargará (~0.5 GB) al primer análisis"
  MODELOS_FALTAN=1
fi

[ "$FALTAN" = 1 ] && morir "faltan archivos (marcados [FALTA] arriba). Revisar el copiado de la USB y volver a correr."
ok "todos los archivos obligatorios están (núcleo + GUI)"

if [ "$SOLO_VERIFICAR" = 1 ]; then
  echo
  echo "${VERDE}Verificación completa.${FIN} Correr sin --solo-verificar para instalar."
  exit 0
fi

# ══════════════════════════════════════════════════════════════════════════
paso "3/6 Dependencias del sistema (compilador para disco-dop)"
# ══════════════════════════════════════════════════════════════════════════
APT_FALTA=()
command -v gcc >/dev/null 2>&1 || APT_FALTA+=(build-essential)
"$PYTHON" -c "import ensurepip" >/dev/null 2>&1 || APT_FALTA+=(python3-venv)
[ -e "$("$PYTHON" -c 'import sysconfig; print(sysconfig.get_path("include"))')/Python.h" ] || APT_FALTA+=(python3-dev)
if [ "${#APT_FALTA[@]}" -gt 0 ]; then
  echo "  hay que instalar: ${APT_FALTA[*]}  (se pedirá la contraseña de sudo)"
  command -v sudo >/dev/null 2>&1 || morir "no hay sudo; pedir al administrador: apt install ${APT_FALTA[*]}"
  sudo apt-get update -qq || aviso "apt update falló; se intenta instalar igual"
  sudo apt-get install -y "${APT_FALTA[@]}" || morir "no se pudieron instalar: ${APT_FALTA[*]}"
  ok "instalados: ${APT_FALTA[*]}"
else
  ok "compilador y venv ya disponibles"
fi

# internet (hace falta para pip)
if "$PYTHON" - <<'EOF' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("https://pypi.org", timeout=8)
EOF
then
  ok "hay conexión a internet (pypi.org)"
else
  morir "sin internet no se pueden instalar los paquetes de Python (~1.5 GB de descarga). Conectarse y volver a correr."
fi

# ══════════════════════════════════════════════════════════════════════════
paso "4/6 Entorno virtual + paquetes de Python"
# ══════════════════════════════════════════════════════════════════════════
if [ -x "$VENV/bin/python" ]; then
  ok "el venv ya existe — se reutiliza (borrar $VENV para empezar de cero)"
else
  "$PYTHON" -m venv "$VENV" || morir "no se pudo crear el venv"
  ok "venv creado en $VENV"
fi
PIP="$VENV/bin/pip"
"$PIP" install --quiet --upgrade pip || aviso "no se pudo actualizar pip; se sigue con el que hay"

echo "  instalando torch (variante CPU, sin CUDA — es la parte más pesada, paciencia)…"
if ! "$PIP" install --quiet torch==2.11.0 --index-url https://download.pytorch.org/whl/cpu; then
  aviso "no se encontró torch 2.11.0 para CPU; se intenta la versión CPU más cercana"
  "$PIP" install --quiet torch --index-url https://download.pytorch.org/whl/cpu || morir "no se pudo instalar torch"
fi
ok "torch instalado ($("$VENV/bin/python" -c 'import torch; print(torch.__version__)'))"

echo "  instalando el resto de los paquetes (requirements.txt, incluye la GUI: fastapi + uvicorn)…"
"$PIP" install --quiet -r "$REPO/requirements.txt" || morir "falló pip install -r requirements.txt (revisar el mensaje de arriba)"
ok "paquetes de Python instalados"

# ══════════════════════════════════════════════════════════════════════════
paso "5/6 Compilando disco-dop (tarda 1-3 minutos)"
# ══════════════════════════════════════════════════════════════════════════
if "$VENV/bin/python" -c "import discodop.tree" >/dev/null 2>&1; then
  ok "disco-dop ya estaba instalado en el venv"
else
  "$PIP" install --quiet "$DISCODOP_DIR" || morir "falló la compilación de disco-dop (¿se instaló build-essential? ¿Python 3.10?)"
  ok "disco-dop compilado e instalado"
fi

# ══════════════════════════════════════════════════════════════════════════
paso "6/6 Prueba de humo (imports del núcleo Y de la GUI, sin cargar modelos)"
# ══════════════════════════════════════════════════════════════════════════
if (cd "$REPO" && "$VENV/bin/python" - <<'EOF'
import stanza, torch, transformers, conllu, pandas, sklearn, openpyxl
from discodop.tree import DrawTree, ParentedTree
import grrux_motor          # arrastra el árbol de imports de GRRux sin cargar Stanza
from aspect_classifier import correccion, glosario, display_grr
import fastapi, uvicorn      # dependencias de la GUI
import grrux_server          # el servidor de la GUI (transporte HTTP) importa sin cargar Stanza
print("imports OK (núcleo + GUI)")
EOF
); then
  ok "todos los módulos importan (terminal y GUI)"
else
  morir "algún módulo no importa (ver traza de arriba)"
fi

# ── comprobación extra de la GUI: uvicorn ejecutable en el venv ──────────────
if [ -x "$VENV/bin/uvicorn" ]; then
  ok "uvicorn presente en el venv — la GUI puede arrancar"
else
  aviso "no encuentro $VENV/bin/uvicorn; reinstalar con: $PIP install uvicorn==0.51.0 fastapi==0.139.0"
fi

echo
echo "${VERDE}════════════════════════════════════════════════════════${FIN}"
echo "${VERDE} Instalación completa.${FIN}"
echo
echo " GRRux se usa de dos formas (siempre desde la carpeta del repo):"
echo "   cd $REPO"
echo
echo " ${AZUL}1) Terminal (CLI)${FIN}"
echo "      ./venv/bin/python grrux_ai1.py"
echo
echo " ${AZUL}2) Interfaz gráfica (GUI) — recomendada${FIN}"
echo "      ./grrux-gui"
echo "    Arranca el servidor local (Stanza + BERTIN, la primera vez tarda"
echo "    varios minutos) y deja la GUI disponible en:"
echo "      ${VERDE}http://127.0.0.1:8763/${FIN}"
echo
if [ "$ES_WSL" = 1 ]; then
  echo "    ${AMBAR}IMPORTANTE — Ubuntu sobre WSL (tu caso):${FIN}"
  echo "      • ./grrux-gui arranca el servidor pero NO puede abrir el"
  echo "        navegador solo (WSL no trae navegador de Linux)."
  echo "      • Deja ./grrux-gui corriendo y ABRE TÚ MISMA, en el navegador"
  echo "        de Windows (Chrome / Edge / Firefox), esta dirección:"
  echo "          ${VERDE}http://localhost:8763/${FIN}"
  echo "      • WSL2 reenvía localhost automáticamente: no hay que configurar"
  echo "        nada de red ni IPs."
  echo "      • (Opcional) para que se abra solo:  sudo apt install wslu"
  echo "        — añade 'wslview', que abre el navegador de Windows desde Linux."
else
  echo "    ${AMBAR}Nota:${FIN} si ./grrux-gui no abre el navegador solo, abre a mano"
  echo "      ${VERDE}http://127.0.0.1:8763/${FIN} en tu navegador."
fi
echo
echo "    Para DETENER el servidor de la GUI:"
echo "      pkill -f 'uvicorn grrux_server'"
echo "    Log del servidor (si algo falla, mirar aquí):"
echo "      $REPO/grrux-gui.log"
echo
if [ "$MODELOS_FALTAN" = 1 ]; then
  echo " ${AMBAR}OJO:${FIN} faltan modelos — el PRIMER análisis (CLI o GUI) descargará ~2 GB."
  echo
fi
echo " La primera carga de modelos tarda varios minutos en laptops lentas;"
echo " después queda residente mientras el programa/servidor esté abierto."
echo " En laptops con poca RAM (4-8 GB): usar UNA sola instancia a la vez y"
echo " cerrar el navegador/pestañas pesadas antes de analizar."
echo "${VERDE}════════════════════════════════════════════════════════${FIN}"
echo

# ── prueba opcional: CLI o GUI ───────────────────────────────────────────────
read -r -p "¿Correr ahora una prueba rápida con una oración (CLI, carga modelos, puede tardar minutos)? [s/N] " R
if [ "${R,,}" = "s" ] || [ "${R,,}" = "si" ] || [ "${R,,}" = "sí" ]; then
  (cd "$REPO" && "$VENV/bin/python" - <<'EOF'
import grrux_motor
print("Cargando modelos (paciencia)…", flush=True)
grrux_motor.cargar()
print("Analizando: 'Juan le dio un regalo a María'…", flush=True)
r = grrux_motor.analizar("Juan le dio un regalo a María")
assert r["error"] is None, r["error"]
sub = r["sub_oraciones"][0]
print()
print("  EL léxica :", sub["el"]["lexical"])
print("  Clase     :", sub["el"]["tipo_legible"])
print("  Integridad:", "OK" if sub["integridad"]["ok"] else "con avisos")
print()
print("PRUEBA COMPLETA SUPERADA — GRRux funciona en esta máquina.")
EOF
  ) || morir "la prueba completa falló (ver traza de arriba)"
fi

echo
read -r -p "¿Abrir la GUI ahora (arranca el servidor en http://127.0.0.1:8763/)? [s/N] " G
if [ "${G,,}" = "s" ] || [ "${G,,}" = "si" ] || [ "${G,,}" = "sí" ]; then
  ( cd "$REPO" && ./grrux-gui )
  echo
  if [ "$ES_WSL" = 1 ]; then
    echo "${VERDE}Servidor arriba.${FIN} Abre en el navegador de Windows: ${VERDE}http://localhost:8763/${FIN}"
  else
    echo "${VERDE}Servidor arriba.${FIN} Si no se abrió el navegador: ${VERDE}http://127.0.0.1:8763/${FIN}"
  fi
fi
echo "Listo."
