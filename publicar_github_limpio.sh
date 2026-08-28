#!/usr/bin/env bash
# Publica una instantánea limpia de GRRux sin arrastrar el historial pesado,
# treebanks ni artefactos locales. Para un remoto ya poblado exige --force.
set -Eeuo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESTINO="${GRRUX_GITHUB_REPO:-https://github.com/juber-86/Grrux-2.x.git}"
FORZAR=0

uso() {
  cat <<'EOF'
Uso: bash publicar_github_limpio.sh [--force]

Construye un repositorio Git nuevo con los archivos actuales de GRRux y lo
publica en https://github.com/juber-86/Grrux-2.x.git (o GRRUX_GITHUB_REPO).
Excluye treebanks, gold_data, venv, .deps y logs locales.

--force solo es necesario si el remoto ya tiene una rama main que debe
reemplazarse conscientemente con esta historia limpia.
EOF
}

for argumento in "$@"; do
  case "$argumento" in
    --force) FORZAR=1 ;;
    -h|--help) uso; exit 0 ;;
    *) echo "Opción no reconocida: $argumento" >&2; uso >&2; exit 2 ;;
  esac
done

falla() { echo "[GRRux export] ERROR: $*" >&2; exit 1; }
command -v git >/dev/null 2>&1 || falla "No encuentro git."
command -v gh >/dev/null 2>&1 || falla "No encuentro GitHub CLI (gh)."
gh auth status -h github.com >/dev/null 2>&1 || falla "GitHub no está autenticado. Ejecuta: gh auth login -h github.com"

LISTA="$(mktemp)"
SALIDA="$(mktemp -d)"
limpiar() {
  rm -f "$LISTA"
  rm -rf "$SALIDA"
}
trap limpiar EXIT

cd "$REPO"
git ls-files -co --exclude-standard |
  awk '!/^treebanks\// && !/^gold_data\// && !/^grrux-gui\.log$/ && !/^analisis_.*\.txt$/ && !/^sesion_.*\.txt$/ && !/^batch_.*\.txt$/ && !/^input_estudiante\.conllu$/' > "$LISTA"

test -s "$LISTA" || falla "No se encontraron archivos para exportar."
tar -cf - -T "$LISTA" | tar -xf - -C "$SALIDA"

git -C "$SALIDA" init --initial-branch=main --quiet
NOMBRE="$(git config user.name || true)"
CORREO="$(git config user.email || true)"
[ -n "$NOMBRE" ] || falla "Configura tu nombre: git config --global user.name 'Tu nombre'"
[ -n "$CORREO" ] || falla "Configura tu correo: git config --global user.email 'tu@correo'"
git -C "$SALIDA" config user.name "$NOMBRE"
git -C "$SALIDA" config user.email "$CORREO"
git -C "$SALIDA" add -- .
git -C "$SALIDA" commit --quiet -m "Publicar GRRux 2.x para Bazzite y Arch"
git -C "$SALIDA" remote add origin "$DESTINO"

if [ "$FORZAR" -eq 1 ]; then
  # El repositorio temporal no tiene refs remotas todavía. Actualizarla primero
  # permite que --force-with-lease compare contra el estado real de main.
  git -C "$SALIDA" fetch --quiet origin
  git -C "$SALIDA" push --force-with-lease -u origin main
else
  git -C "$SALIDA" push -u origin main
fi

echo "[GRRux export] publicado correctamente en $DESTINO"
