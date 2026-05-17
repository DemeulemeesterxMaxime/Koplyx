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
- Recherche instantanee.
- Onglet dedie aux textes epingles.
- Restauration dans le presse-papiers.
- Collage automatique apres clic si `xdotool` ou `wtype` est installe.
- Indicateur de barre systeme si le bureau expose AppIndicator/KStatusNotifierItem.
- Stockage SQLite local chiffre avec `cryptography.Fernet`.
- Purge par nombre d'entrees, age et taille totale.
- Parametres integres.
- Installation optionnelle du raccourci GNOME.
- Autostart utilisateur optionnel.

## Donnees locales

- Configuration : `~/.config/koplyx/config.json`
- Cle locale : `~/.config/koplyx/key.bin`
- Base historique : `~/.local/share/koplyx/history.db`

La base ne stocke pas les contenus en clair. La cle reste locale sur la machine ; pour une publication commerciale, il faudra remplacer ce mecanisme par une integration Secret Service/libsecret plus stricte.

## Raccourci global

Le raccourci par defaut est `<Ctrl><Alt>V`. Dans les parametres, le bouton `Installer raccourci GNOME` configure un custom keybinding GNOME qui lance :

```bash
/usr/bin/python3 Koplyx/koplyx/main.py --toggle
```

Sous Wayland, le support des raccourcis globaux depend du bureau. GNOME peut accepter ce raccourci via ses parametres, mais les comportements clipboard globaux restent plus restrictifs que sous X11.

## Installation utilisateur

```bash
cd Koplyx
./packaging/install-user.sh
```

Cela installe un lanceur dans `~/.local/bin/koplyx` et une entree desktop dans `~/.local/share/applications/dev.limax.koplyx.desktop`.
Sur X11, le script tente aussi d'installer `xdotool` via `apt` pour activer le collage automatique.

## Tester avant release

```bash
cd Koplyx
./scripts/smoke-test.sh
```

Le guide complet est dans `docs/TEST_RELEASE.md`.

## Dependances optionnelles

- `xdotool` sur X11 pour coller automatiquement dans le champ actif apres un clic.
- `wtype` sur Wayland si le bureau autorise l'injection clavier.
- Support AppIndicator/KStatusNotifierItem pour afficher Koplyx dans la zone systeme pres du Wi-Fi.

## Build release

```bash
cd Koplyx
./scripts/build-dist.sh
```

Le build produit `dist/koplyx-<version>-linux-source.tar.gz`, `dist/koplyx_<version>_all.deb` et `dist/SHA256SUMS`.
La GitHub Action `.github/workflows/release.yml` genere les memes fichiers en artefacts telechargeables, et les publie dans une GitHub Release quand un tag `v*` est pousse.

## Note juridique naming

Le nom Koplyx a ete choisi apres recherche preliminaire. Ce n'est pas une garantie juridique. Avant publication publique, verifier formellement WIPO, USPTO, EUIPO et INPI.
