#!/usr/bin/env bash
# Instalación portable de GRRux para una distribución Linux ya preparada.
# La invocan instalar_arch.sh e instalar_bazzite.sh; también admite uso directo.
set -Eeuo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${GRRUX_VENV:-${REPO}/venv}"
DEPS_DIR="${REPO}/.deps"
DISCODOP_DIR="${DISCODOP_DIR:-${DEPS_DIR}/disco-dop}"
DISCODOP_REPO="https://github.com/andreasvc/disco-dop.git"
DISCODOP_REV="dd181a6633e7373eed3f7049537d30e79c7ffa56"
BAJAR_MODELOS=0
PYTHON=""

uso() {
  cat <<'EOF'
Uso: bash instalar_comun.sh [--modelos]

Instala GRRux en ./venv sin paquetes CUDA. --modelos descarga Stanza español
y BERTIN; sin esa opción se descargarán automáticamente en el primer análisis.
EOF
}

for argumento in "$@"; do
  case "$argumento" in
    --modelos) BAJAR_MODELOS=1 ;;
    -h|--help) uso; exit 0 ;;
    *) echo "Opción no reconocida: $argumento" >&2; uso >&2; exit 2 ;;
  esac
done

falla() { echo "[GRRux] ERROR: $*" >&2; exit 1; }
ok() { echo "  [OK] $*"; }

command -v git >/dev/null 2>&1 || falla "No encuentro git."

seleccionar_python() {
  if [ -n "${PYTHON:-}" ] && command -v "$PYTHON" >/dev/null 2>&1; then
    printf '%s\n' "$PYTHON"
    return 0
  fi

  for candidato in python3.13 python3.12 python3.11 python3.10 python3; do
    if ! command -v "$candidato" >/dev/null 2>&1; then
      continue
    fi

    if "$candidato" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if (3, 10) <= sys.version_info < (3, 14) else 1)
PY
    then
      printf '%s\n' "$candidato"
      return 0
    fi
  done

  return 1
}

PYTHON="$(seleccionar_python)" || falla "No encuentro un Python compatible. Necesitas Python 3.10 a 3.13; en Cachy suele servir 'python3.10'."
echo "[GRRux] usando $PYTHON"

"$PYTHON" - <<'PY' || exit 1
import sys
if sys.version_info < (3, 10):
    raise SystemExit("GRRux requiere Python 3.10 o posterior.")
if sys.version_info >= (3, 14):
    raise SystemExit("GRRux todavía no está listo para Python 3.14; usa Python 3.10 a 3.13.")
PY

for archivo in gruxx_server.py gruxx_motor.py gruxx_ai1.py rrg_ls_mapper.py ud2rrg.py requirements.txt; do
  [ -f "${REPO}/${archivo}" ] || falla "Falta ${archivo}; ejecuta el instalador desde un clon completo."
done

if [ ! -d "$VENV" ]; then
  echo "[GRRux] creando entorno virtual en $VENV"
  "$PYTHON" -m venv "$VENV"
fi

PIP="$VENV/bin/python"
"$PIP" -m pip install --upgrade pip setuptools wheel

echo "[GRRux] instalando PyTorch para CPU (sin CUDA)"
"$PIP" -m pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.11.0"

echo "[GRRux] instalando dependencias Python"
"$PIP" -m pip install -r "${REPO}/requirements.txt"

mkdir -p "$DEPS_DIR"
if [ ! -d "${DISCODOP_DIR}/.git" ]; then
  [ ! -e "$DISCODOP_DIR" ] || falla "$DISCODOP_DIR existe pero no es un clon de disco-dop."
  echo "[GRRux] obteniendo disco-dop (${DISCODOP_REV:0:12})"
  git clone "$DISCODOP_REPO" "$DISCODOP_DIR"
fi
git -C "$DISCODOP_DIR" fetch --quiet --tags
git -C "$DISCODOP_DIR" checkout --quiet "$DISCODOP_REV"

echo "[GRRux] compilando disco-dop"
"$PIP" -m pip install --no-build-isolation "$DISCODOP_DIR"

echo "[GRRux] verificando importaciones"
(
  cd "$REPO"
  "$PIP" - <<'PY'
import conllu, openpyxl, pandas, sklearn, stanza, torch, transformers
from discodop.tree import DrawTree, ParentTree
import gruxx_motor
import rrg_ls_mapper
print("Python, dependencias, disco-dop y módulos centrales: OK")
PY
)
ok "entorno instalado en $VENV"

if [ "$BAJAR_MODELOS" -eq 1 ]; then
  echo "[GRRux] descargando modelos de Stanza y BERTIN"
  "$PIP" - <<'PY'
import stanza
from transformers import AutoTokenizer, AutoModel
stanza.download("es")
AutoTokenizer.from_pretrained("bertin-project/bertin-roberta-base-spanish")
AutoModel.from_pretrained("bertin-project/bertin-roberta-base-spanish")
print("Modelos descargados.")
PY
else
  echo "[GRRux] modelos: se descargarán al primer análisis; para anticiparlo ejecuta:"
  echo "  bash instalar_comun.sh --modelos"
fi

echo "[GRRux] GUI:      ./gruxx-gui"
echo "[GRRux] terminal: ${VENV}/bin/python gruxx_ai1.py"
