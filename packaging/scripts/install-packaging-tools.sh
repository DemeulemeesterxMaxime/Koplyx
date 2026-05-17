#!/usr/bin/env sh
set -eu

sudo snap install snapcraft --classic
if ! snap list lxd >/dev/null 2>&1; then
  sudo snap install lxd
fi

sudo usermod -aG lxd "$USER"
if ! groups | tr ' ' '\n' | grep -qx 'lxd'; then
  printf '%s\n' "Current user was added to the lxd group."
  printf '%s\n' "Log out and log back in, or run: newgrp lxd"
fi

sudo lxd init --auto >/dev/null 2>&1 || true

sudo apt-get update
sudo apt-get install -y flatpak flatpak-builder appstream desktop-file-utils

if ! flatpak remote-list | grep -q '^flathub'; then
  flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
fi

flatpak install -y flathub org.flatpak.Builder

printf '%s\n' "Packaging tools installed."
