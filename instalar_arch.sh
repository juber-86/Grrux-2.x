#!/usr/bin/env bash
# Instalador para Arch Linux y derivadas con pacman.
set -Eeuo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v pacman >/dev/null 2>&1 || {
  echo "[GRRux] Este instalador requiere una distribución con pacman." >&2
  exit 1
}
command -v sudo >/dev/null 2>&1 || {
  echo "[GRRux] Se necesita sudo para instalar las dependencias del sistema." >&2
  exit 1
}

echo "[GRRux] instalando dependencias del sistema con pacman"
sudo pacman -Syu --needed --noconfirm base-devel python python-pip git curl

exec bash "${REPO}/instalar_comun.sh" "$@"
