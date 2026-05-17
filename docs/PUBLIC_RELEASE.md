# Publication publique

Koplyx est pret pour une beta publique lorsque les tests de `docs/TEST_RELEASE.md` passent sur la matrice cible.

## Avant publication

- Verifier juridiquement le nom Koplyx sur INPI, EUIPO, USPTO et WIPO.
- Creer une cle mainteneur GPG et signer les artifacts ou le depot APT.
- Publier les checksums `SHA256SUMS` avec la release.
- Documenter explicitement les limites Wayland : raccourcis globaux et collage automatique dependent du bureau.
- Tester une installation propre depuis le `.deb`, puis suppression et reinstall.

## Commandes release

```bash
./scripts/smoke-test.sh
./scripts/build-dist.sh
cd dist
sha256sum -c SHA256SUMS
```

## Snapcraft

Installer l'outil :

```bash
./packaging/scripts/install-packaging-tools.sh
snapcraft login
```

Construire et publier :

```bash
snapcraft pack
snapcraft upload --release=edge koplyx_0.2.1_amd64.snap
```

Pour une premiere publication, reserver le nom si necessaire :

```bash
snapcraft register koplyx
```

## Flathub

Installer les outils :

```bash
./packaging/scripts/install-packaging-tools.sh
```

Construire localement :

```bash
flatpak-builder --force-clean --user --install build-dir packaging/flatpak/dev.limax.koplyx.yml
```

Verifier les metadonnees :

```bash
desktop-file-validate packaging/dev.limax.koplyx.desktop
appstreamcli validate --no-net packaging/metainfo/dev.limax.koplyx.metainfo.xml
```

Soumission Flathub :

1. Forker `flathub/flathub`.
2. Creer une branche depuis `new-pr`.
3. Copier `packaging/flatpak/dev.limax.koplyx.yml` et `packaging/flatpak/flathub.json` a la racine du fork.
4. Ouvrir une pull request vers la branche `new-pr`, pas `master`.
5. Commenter `bot, build` quand le review bot le demande.

Tag GitHub :

```bash
git tag v0.2.0
git push origin main
git push origin v0.2.0
```

La GitHub Action publie les artifacts en release pour les tags `v*`.
