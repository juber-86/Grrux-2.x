#!/usr/bin/env bash
# Publica una instantánea LIMPIA de GRRux (núcleo + GUI + modelos + recursos
# curados) en GitHub, sin arrastrar el historial pesado, treebanks ni
# artefactos locales. Basado en publicar_github_limpio.sh, con dos mejoras:
#   1. NO requiere GitHub CLI (gh); usa las credenciales git ya configuradas.
#   2. Empaquetado seguro con nombres Unicode y espacios (NUL-delimited),
#      para no romperse con archivos como "complex sentences/…–….png".
#
# Uso:
#   bash publicar_github.sh            # push normal (remoto vacío)
#   bash publicar_github.sh --force    # reemplaza conscientemente el main remoto
#
# Como el remoto ya tiene un main publicado, usa --force.
set -Eeuo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESTINO="${GRRUX_GITHUB_REPO:-git@github.com:juber-86/Grrux-2.x.git}"
FORZAR=0

for argumento in "$@"; do
  case "$argumento" in
    --force) FORZAR=1 ;;
    -h|--help)
      echo "Uso: bash publicar_github.sh [--force]"
      echo "Publica la instantánea limpia de GRRux en $DESTINO"
      echo "Excluye treebanks, gold_data, venv, .deps y logs locales."
      echo "--force reemplaza el main remoto ya existente."
      exit 0 ;;
    *) echo "Opción no reconocida: $argumento" >&2; exit 2 ;;
  esac
done

falla() { echo "[GRRux export] ERROR: $*" >&2; exit 1; }
command -v git >/dev/null 2>&1 || falla "No encuentro git."

LISTA="$(mktemp)"
SALIDA="$(mktemp -d)"
limpiar() { rm -f "$LISTA"; rm -rf "$SALIDA"; }
trap limpiar EXIT

cd "$REPO"
# Lista NUL-delimited, sin escapado octal de rutas Unicode, filtrando lo que
# no debe distribuirse. '|| true' evita que grep aborte cuando no descarta nada.
git -c core.quotepath=false ls-files -co --exclude-standard -z \
  | { grep -z -v -E '^(treebanks/|gold_data/|grrux-gui\.log$|analisis_.*\.txt$|sesion_.*\.txt$|batch_.*\.txt$|input_estudiante\.conllu$)' || true; } \
  > "$LISTA"

test -s "$LISTA" || falla "No se encontraron archivos para exportar."
echo "[GRRux export] Empaquetando $(tr -cd '\0' < "$LISTA" | wc -c) archivos para $DESTINO"
tar --null -cf - -T "$LISTA" | tar -xf - -C "$SALIDA"

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
  git -C "$SALIDA" fetch --quiet origin || true
  git -C "$SALIDA" push --force-with-lease -u origin main
else
  git -C "$SALIDA" push -u origin main
fi

echo "[GRRux export] publicado correctamente en $DESTINO"
