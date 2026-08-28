#!/usr/bin/env bash
# Instalador para Bazzite: usa un contenedor Distrobox Fedora para no modificar
# la imagen atómica del host.
set -Eeuo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTENEDOR="${GRRUX_DISTROBOX_NAME:-grrux}"
IMAGEN="${GRRUX_DISTROBOX_IMAGE:-quay.io/fedora/fedora:44}"

if [ "${1:-}" = "--dentro-distrobox" ]; then
  shift
  command -v dnf >/dev/null 2>&1 || {
    echo "[GRRux] El modo interno necesita una imagen Fedora con dnf." >&2
    exit 1
  }
  echo "[GRRux] instalando dependencias dentro de Distrobox"
  sudo dnf install -y python3 python3-devel gcc gcc-c++ make git curl redhat-rpm-config
  exec bash "${REPO}/instalar_comun.sh" "$@"
fi

command -v distrobox >/dev/null 2>&1 || {
  echo "[GRRux] No encuentro Distrobox. Instálalo desde el Centro de Software de Bazzite y vuelve a ejecutar este script." >&2
  exit 1
}

if ! distrobox list --no-color | awk '{print $1}' | grep -Fxq "$CONTENEDOR"; then
  echo "[GRRux] creando Distrobox '${CONTENEDOR}' (${IMAGEN})"
  distrobox create --yes --name "$CONTENEDOR" --image "$IMAGEN"
fi

echo "[GRRux] entrando a Distrobox '${CONTENEDOR}' para instalar"
exec distrobox enter --name "$CONTENEDOR" -- bash "${REPO}/instalar_bazzite.sh" --dentro-distrobox "$@"
