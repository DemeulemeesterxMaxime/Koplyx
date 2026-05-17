#!/usr/bin/env sh
set -eu

sudo snap install snapcraft --classic
sudo apt-get update
sudo apt-get install -y flatpak flatpak-builder appstream desktop-file-utils

if ! flatpak remote-list | grep -q '^flathub'; then
  flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
fi

flatpak install -y flathub org.flatpak.Builder

printf '%s\n' "Packaging tools installed."
