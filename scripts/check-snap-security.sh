#!/usr/bin/env sh
# Refuser les dépendances libx11 vulnérables avant publication sur le Store.
set -eu

if [ "$#" -ne 1 ]; then
  printf '%s\n' "Usage : $0 fichier.snap" >&2
  exit 2
fi

manifest="$(mktemp)"
trap 'rm -f "$manifest"' EXIT HUP INT TERM
unsquashfs -cat "$1" snap/manifest.yaml > "$manifest"
minimum='2:1.8.7-1ubuntu0.1'
for package in libx11-6 libx11-data; do
  versions="$(sed -n "s/^[[:space:]]*-[[:space:]]*${package}=\([^[:space:]]*\)[[:space:]]*$/\1/p" "$manifest" | sort -u)"
  if [ -z "$versions" ]; then
    printf '%s\n' "Paquet absent du manifeste : $package" >&2
    exit 1
  fi
  for version in $versions; do
    if ! dpkg --compare-versions "$version" ge "$minimum"; then
      printf '%s\n' "USN-8913-1 : $package=$version est antérieur à $minimum" >&2
      exit 1
    fi
    printf '%s\n' "USN-8913-1 : $package=$version corrigé"
  done
done
