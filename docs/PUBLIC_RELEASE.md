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
newgrp lxd
snapcraft login
```

Si `snapcraft pack` affiche `user must be manually added to 'lxd' group before using LXD`, fermer et rouvrir la session Linux, ou lancer `newgrp lxd` dans le terminal courant. Snapcraft construit le paquet dans une instance LXD, donc le groupe doit etre actif avant le build.

Construire et publier :

```bash
snapcraft pack
ls -lh koplyx_0.2.1_amd64.snap
snapcraft upload --release=edge koplyx_0.2.1_amd64.snap
```

Pour une premiere publication, reserver le nom si necessaire :

```bash
snapcraft register koplyx
```

Si Snapcraft repond `already_owned: You already own the snap name "koplyx"`, le nom est deja reserve sur le compte courant. Ne pas relancer `snapcraft register koplyx`, passer directement a `snapcraft pack`.

Si `snapcraft pack` echoue avec `A network related operation failed in a context of no network access`, le build a demarre mais le conteneur LXD Snapcraft n'a pas acces au reseau. Verifier/reinitialiser LXD puis relancer le build :

```bash
lxc network list
lxc network show lxdbr0
sudo snap restart lxd
snapcraft clean
snapcraft pack
```

Si le probleme persiste, supprimer l'instance de build Snapcraft et verifier que le bridge LXD a du NAT :

```bash
lxc --project snapcraft list
lxc --project snapcraft delete --force snapcraft-koplyx-amd64-19796907 2>/dev/null || true
lxc network set lxdbr0 ipv4.nat true
lxc network set lxdbr0 ipv6.nat true
snapcraft pack
```

Ne lancer `snapcraft upload` que lorsque le fichier `.snap` existe vraiment dans le dossier projet.

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
git push origin main
git tag v0.2.1
git push origin v0.2.1
```

La GitHub Action publie les artifacts en release pour les tags `v*`.
