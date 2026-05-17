# Koplyx

Koplyx est une micro-app Linux d'historique du presse-papiers. Elle surveille les copies texte et image, stocke l'historique localement avec chiffrement applicatif, puis permet de retrouver et restaurer une ancienne copie via une fenetre compacte.

## Lancer en developpement

```bash
cd Koplyx
./bin/koplyx
```

## Fonctionnalites v1

- Historique texte et image.
- Deduplication par hash.
- Recherche instantanee sur les metadonnees non sensibles.
- Onglet dedie aux textes epingles.
- Restauration dans le presse-papiers.
- Collage automatique apres clic via `xdotool` sur X11.
- Indicateur de barre systeme si le bureau expose AppIndicator/KStatusNotifierItem.
- Menu de barre systeme avec acces aux parametres et action quitter.
- Icone Koplyx dediee dans le lanceur et la barre systeme.
- Stockage SQLite local chiffre avec `cryptography.Fernet`.
- Cle de chiffrement stockee via Secret Service/libsecret quand disponible, avec fallback fichier local.
- Purge par nombre d'entrees, age et taille totale.
- Parametres integres.
- Dialogue de capture du raccourci clavier avec Entree pour demarrer/valider.
- Installation optionnelle du raccourci GNOME.
- Autostart utilisateur optionnel.

## Donnees locales

- Configuration : `~/.config/koplyx/config.json`
- Cle locale : Secret Service/libsecret si disponible, sinon `~/.config/koplyx/key.bin`
- Base historique : `~/.local/share/koplyx/history.db`

Les contenus complets sont stockes dans `encrypted_blob`. Depuis `0.2.2`, les nouveaux apercus d'historique ne reprennent plus le texte copie en clair et indiquent seulement le type, la taille ou la longueur. Les historiques crees avant `0.2.2` peuvent encore contenir d'anciens apercus en clair ; purger l'historique avant une publication stable si de vraies donnees ont ete utilisees pendant les tests.

Les dossiers locaux `~/.config/koplyx` et `~/.local/share/koplyx` sont durcis en `0700`, et les fichiers config, cle et base en `0600` quand le systeme de fichiers le permet. La cle reste locale sur la machine et utilise Secret Service/libsecret quand le bureau le fournit.

## Raccourci global

Le raccourci par defaut est `<Ctrl><Alt>V`. Dans les parametres, le bouton `Installer raccourci GNOME` configure un custom keybinding GNOME qui lance :

```bash
koplyx --toggle
```

Sous Wayland, le support des raccourcis globaux depend du bureau. GNOME peut accepter ce raccourci via ses parametres, mais les comportements clipboard globaux restent plus restrictifs que sous X11.

Pour modifier la combinaison dans Koplyx : ouvrir les parametres, cliquer `Modifier`, cliquer `Demarrer` pour vider l'ancienne combinaison, choisir si besoin `Ctrl`, `Alt` ou `Super`, appuyer sur la touche principale, puis cliquer `Valider`. Le bouton `Fn` est affiche comme aide, mais GNOME ne peut generalement pas enregistrer `Fn` comme modificateur.

Si le raccourci ne repond pas, il peut deja etre reserve par l'OS. Ouvrir `Parametres > Clavier > Raccourcis clavier` pour changer ou liberer le raccourci systeme.

## Installation utilisateur

```bash
cd Koplyx
./packaging/install-user.sh
```

Cela installe un lanceur dans `~/.local/bin/koplyx` et une entree desktop dans `~/.local/share/applications/dev.limax.koplyx.desktop`.
Sur X11, le script tente aussi d'installer `xdotool` via `apt` pour activer le collage automatique.

## Validation locale

```bash
cd Koplyx
./scripts/smoke-test.sh
./scripts/build-dist.sh
cd dist
sha256sum -c SHA256SUMS
```

La checklist de publication est dans `docs/PUBLIC_RELEASE.md`.
Les versions HTML statiques de la documentation sont dans `docs/html/`.

## Contribuer

Les contributions sont bienvenues pour les corrections de bugs, la documentation, le packaging Linux et les ameliorations ciblees de l'experience utilisateur. Lire `CONTRIBUTING.md` avant d'ouvrir une issue ou une pull request.

## Dependances optionnelles

- `xdotool` sur X11 pour coller automatiquement dans le champ actif apres un clic.
- `wtype` peut etre teste sur Wayland, mais il n'est pas une dependance du paquet `.deb`.
- Support AppIndicator/KStatusNotifierItem pour afficher Koplyx dans la zone systeme pres du Wi-Fi.

Le collage automatique envoie volontairement `Ctrl+V` a la fenetre active apres restauration. Cette fonction doit etre testee sur l'environnement cible avant publication stable.

## Build release

```bash
cd Koplyx
./scripts/build-dist.sh
```

Le build produit `dist/koplyx-<version>-linux-source.tar.gz`, `dist/koplyx_<version>_all.deb` et `dist/SHA256SUMS`.
La GitHub Action `.github/workflows/release.yml` genere les memes fichiers en artefacts telechargeables, et les publie dans une GitHub Release quand un tag `v*` est pousse.

## Snapcraft et Flathub

- Snapcraft: `snap/snapcraft.yaml`
- Flathub/Flatpak: `packaging/flatpak/dev.limax.koplyx.yml`
- AppStream: `packaging/metainfo/dev.limax.koplyx.metainfo.xml`
- Outils packaging: `packaging/scripts/install-packaging-tools.sh`

Snapcraft et Flatpak Builder doivent etre installes localement pour construire ces paquets. Les commandes de publication sont documentees dans `docs/PUBLIC_RELEASE.md`.

## Note juridique naming

Le nom Koplyx a ete choisi apres recherche preliminaire. Ce n'est pas une garantie juridique. Avant publication publique, verifier formellement WIPO, USPTO, EUIPO et INPI.
