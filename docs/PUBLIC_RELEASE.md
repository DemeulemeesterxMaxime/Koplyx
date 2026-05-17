# Publication publique

Koplyx est pret pour une beta publique lorsque la validation locale passe sur la matrice cible.

## Avant publication

- Verifier juridiquement le nom Koplyx sur INPI, EUIPO, USPTO et WIPO.
- Creer une cle mainteneur GPG et signer les artifacts ou le depot APT.
- Publier les checksums `SHA256SUMS` avec la release.
- Documenter explicitement les limites Wayland : raccourcis globaux et collage automatique dependent du bureau.
- Purger l'historique local si des donnees reelles ont ete copiees avec une version anterieure a `0.2.2`, car les anciens apercus pouvaient contenir du texte en clair.
- Tester une installation propre depuis le `.deb`, puis suppression et reinstall.

## Commandes release

```bash
./scripts/smoke-test.sh
./scripts/build-dist.sh
cd dist
sha256sum -c SHA256SUMS
```

## Verification manuelle

- Installer le `.deb`, lancer Koplyx, verifier l'icone du lanceur et de la zone systeme.
- Copier/coller un texte et verifier son apparition dans l'historique.
- Verifier dans SQLite que les nouvelles lignes ne stockent plus le texte copie en clair dans `preview`.
- Cliquer une entree texte depuis un editeur actif et verifier le collage automatique sur X11.
- Epingler un texte et verifier sa presence dans l'onglet dedie.
- Ouvrir les parametres, tester l'autostart et l'installation du raccourci GNOME.
- Redemarrer la session et verifier la persistance de l'historique.
- Installer le snap depuis `edge` et refaire le lancement, l'icone, la zone systeme et l'historique.

## Snapcraft

Installer l'outil :

```bash
./packaging/scripts/install-packaging-tools.sh
newgrp lxd
snapcraft login
```

Ne pas lancer `snapcraft` avec `sudo`. Snapcraft doit tourner avec l'utilisateur courant, sinon il utilise l'etat `/root/.local/state/snapcraft`, un autre trousseau de connexion, et une configuration LXD differente. `cd` ne s'utilise pas non plus avec `sudo` :

```bash
cd Koplyx
snapcraft pack
```

Si `snapcraft pack` affiche `user must be manually added to 'lxd' group before using LXD`, fermer et rouvrir la session Linux, ou lancer `newgrp lxd` dans le terminal courant. Snapcraft construit le paquet dans une instance LXD, donc le groupe doit etre actif avant le build.

Verifier que le groupe est actif avant de relancer Snapcraft :

```bash
groups
```

La sortie doit contenir `lxd`. Si ce n'est pas le cas :

```bash
sudo usermod -aG lxd "$USER"
newgrp lxd
groups
```

Si `groups` ne contient toujours pas `lxd`, fermer completement la session Linux puis se reconnecter.

Construire et publier :

```bash
snapcraft pack
ls -lh koplyx_0.2.2_amd64.snap
snapcraft upload --release=edge koplyx_0.2.2_amd64.snap
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

Si une tentative a ete lancee avec `sudo snapcraft`, ignorer le log dans `/root/.local/state/snapcraft` et relancer sans `sudo` depuis le dossier projet.

Si `snapcraft clean` ou `snapcraft pack` echoue avec `PermissionError(13, 'Permission denied')` sur LXD, le shell courant n'a pas encore le groupe `lxd`. Refaire la verification `groups`, puis rouvrir la session si necessaire.

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
git tag v0.2.2
git push origin v0.2.2
```

La GitHub Action publie les artifacts en release pour les tags `v*`.

## Nettoyage historique Git

Avant de rendre le depot public sans traces personnelles, garder un backup puis reecrire l'historique local pour remplacer l'email auteur par l'email GitHub noreply et supprimer les anciens chemins locaux. Apres verification, publier avec `git push --force-with-lease origin main` seulement si aucun contributeur externe n'a base de travail sur l'ancien historique.
