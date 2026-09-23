# Koplyx

Un historique du presse-papiers pour Linux, local et chiffré. Retrouvez vos textes, images et fichiers copiés, recherchez une entrée et restaurez-la depuis une fenêtre compacte.

[Télécharger](https://github.com/DemeulemeesterxMaxime/Koplyx/releases/latest) · [Notes de version](CHANGELOG.md) · [Contribuer](CONTRIBUTING.md) · [Signaler un bug](https://github.com/DemeulemeesterxMaxime/Koplyx/issues)

<p align="center">
  <a href="https://snapcraft.io/koplyx">
    <img alt="Disponible sur le Snap Store" src="https://snapcraft.io/koplyx/badge.svg" />
  </a>
</p>

## Distributions et installation

### Snap Store

Installez Koplyx depuis sa [page Snap Store](https://snapcraft.io/koplyx) ou sur une distribution équipée de Snap :

```bash
sudo snap install koplyx
```

Pour demander une mise à jour du canal stable :

```bash
sudo snap refresh koplyx --channel=latest/stable
```

Pour tester la préversion, installez le Snap beta avec `sudo snap install koplyx --channel=latest/beta`, ou passez une installation existante sur ce canal avec `sudo snap refresh koplyx --channel=latest/beta`. Vérifiez le canal avec `snap info koplyx`. Le Snap strict ne peut pas configurer `/dev/uinput`; pour tester ydotool, téléchargez le `.deb` de la préversion depuis les [GitHub Releases](https://github.com/DemeulemeesterxMaxime/Koplyx/releases) et installez-le avec `sudo apt install ./koplyx_0.4.6-beta.1_all.deb`. Après avoir activé ydotool dans l'assistant, une reconnexion est nécessaire pour appliquer le groupe système dédié.

### Debian et Ubuntu (.deb)

Téléchargez `koplyx_<version>_all.deb` dans les [GitHub Releases](https://github.com/DemeulemeesterxMaxime/Koplyx/releases/latest). Depuis le dossier de téléchargement, installez le fichier de la version choisie. Exemple pour la release stable `0.4.5` :

```bash
sudo apt install ./koplyx_0.4.5_all.deb
```

Pour mettre à jour, téléchargez et installez le paquet de la nouvelle release.

### Depuis les sources

Sur Debian ou Ubuntu, installez les dépendances puis lancez le projet :

```bash
sudo apt install python3 python3-gi gir1.2-gtk-4.0 gir1.2-gdkpixbuf-2.0 python3-cryptography python3-pil python3-dbus python3-secretstorage dbus-user-session xdotool wtype ydotool
git clone https://github.com/DemeulemeesterxMaxime/Koplyx.git
cd Koplyx
./bin/koplyx
```

Vous pouvez aussi extraire l'archive source d'une release. Pour ajouter un lanceur à votre session, exécutez `./packaging/install-user.sh` depuis le dossier du projet. Le lanceur utilise ce dossier : conservez-le à son emplacement après l'installation.

### Flatpak

Le dépôt fournit un [manifeste Flatpak](packaging/flatpak/dev.limax.koplyx.yml) pour la construction locale et la préparation d'une soumission à Flathub. Les commandes et prérequis sont dans le [guide de packaging et publication](docs/PUBLIC_RELEASE.md).

## Releases

Les [GitHub Releases](https://github.com/DemeulemeesterxMaxime/Koplyx/releases) regroupent les versions publiées et leurs fichiers :

- `koplyx_<version>_all.deb` : paquet Debian et Ubuntu.
- `koplyx-<version>-linux-source.tar.gz` : archive source.
- `SHA256SUMS` : sommes de contrôle des deux artefacts.

Téléchargez les deux artefacts et `SHA256SUMS` dans le même dossier, puis vérifiez leur intégrité :

```bash
sha256sum -c SHA256SUMS
```

Le projet suit Semantic Versioning (`MAJOR.MINOR.PATCH`), avec [VERSION](VERSION) comme source de vérité. Le [changelog](CHANGELOG.md) détaille les évolutions et correctifs.

Le [workflow de release](.github/workflows/release.yml) vérifie les pull requests vers `main` et construit les artefacts Linux et Snap. Les tags `v*` déclenchent la publication GitHub ; la publication Snap stable dépend des identifiants du Store configurés dans la CI. Attendez la réussite complète de la CI avant une fusion ou une publication. Consultez le [guide de publication](docs/PUBLIC_RELEASE.md) pour la procédure complète.

## Utiliser Koplyx

<p align="center">
  <img src="assets/presentation/koplyx-history.png" alt="Capture réelle de la fenêtre d'historique de Koplyx" width="400" />
</p>

- Recherchez parmi les textes, images et fichiers copiés.
- Épinglez les textes, images et fichiers à conserver. Le filtre global choisit si les épingles apparaissent en haut, en bas ou uniquement dans l'onglet `Épinglés`.
- Cliquez sur une ligne pour restaurer puis coller immédiatement l'élément dans la fenêtre précédente, sans créer une nouvelle entrée d'historique.
- Ouvrez la fenêtre avec `Ctrl+Alt+V`, configurable dans les paramètres et installé automatiquement sous GNOME.
- Le menu de la barre système propose `Afficher Koplyx`, `Paramètres` et `Quitter Koplyx`. L'historique se consulte dans la fenêtre principale.

Koplyx peut démarrer en arrière-plan à l'ouverture de session. L'assistant essaie automatiquement les solutions de collage dans l'ordre adapté à votre session, puis s'arrête dès que vous confirmez qu'une méthode fonctionne. Le portail du bureau Wayland n'est utilisé qu'après votre accord explicite et affiche une demande « Bureau à distance » limitée au clavier. `wtype` dépend du support du compositeur ; `ydotool` nécessite son daemon, l'accès à `uinput` et le helper système fourni par le paquet installé. Koplyx ne demande ni partage d'écran ni contrôle de souris. Le bureau peut révoquer une autorisation dans ses paramètres de confidentialité. Le mode presse-papiers restaure chaque élément en première position, tente Ctrl+V, puis vous indique clairement d'utiliser Ctrl+V manuellement si aucun outil d'injection n'est disponible. L'indicateur système nécessite un hôte AppIndicator/KStatusNotifierItem.

Au premier lancement, l'assistant de collage configure le raccourci GNOME, prépare le test actif dans le champ que vous choisissez puis essaie chaque solution l'une après l'autre. Le test est exclu de l'historique et le presse-papiers précédent est restauré lorsque le bureau le permet. L'assistant reste relançable depuis Paramètres. Les Paramètres affichent seulement l'état de la configuration : le choix d'une méthode est mémorisé uniquement après votre confirmation dans l'assistant. Aucun privilège n'est demandé sans clic de votre part.

Le test XWayland relance uniquement Koplyx avec `GDK_BACKEND=x11` : il ne transforme pas toute la session Wayland. Une session Xorg n'est proposée que si un fichier `/usr/share/xsessions/*.desktop` est présent. Sa configuration sauvegarde `/etc/gdm3/custom.conf`, prend effet au prochain redémarrage et peut être annulée par le bouton « Restaurer Wayland » ou par `koplyx --restore-display-session`. La restauration refuse de remplacer un fichier GDM modifié depuis la sauvegarde.

L'option `ydotool` utilise uniquement un groupe système dédié et une règle udev pour `/dev/uinput`. Koplyx envoie des événements virtuels de collage et ne lit pas les périphériques clavier. Une reconnexion ou un redémarrage est nécessaire après l'autorisation. Le test est masqué dans une exécution depuis les sources tant que le helper root-owned n'est pas installé par le paquet. Snap et Flatpak ne peuvent pas modifier l'uinput de l'hôte depuis leur sandbox : l'assistant masque cette étape et propose le portail ou le mode presse-papiers.

Les contenus sont chiffrés avant leur stockage local dans SQLite et les aperçus sont déchiffrés en mémoire. La clé utilise Secret Service/libsecret si disponible, avec un fichier local en solution de repli. Consultez la [politique de sécurité](SECURITY.md) pour les précautions concernant les anciens historiques.

## Contributions

Koplyx est un projet open source sous [licence MIT](LICENSE). Les contributions sont bienvenues : corrections de bugs, documentation, accessibilité, packaging et tests sur différentes distributions Linux.

1. Consultez les [issues](https://github.com/DemeulemeesterxMaxime/Koplyx/issues) et ouvrez une discussion avant une modification importante.
2. Lisez le [guide de contribution](CONTRIBUTING.md) et le [code de conduite](CODE_OF_CONDUCT.md).
3. Créez une branche dédiée et effectuez les vérifications locales.
4. Ouvrez une pull request vers `main` avec une description du changement, les tests effectués et les limites connues sur X11, Wayland, Snap ou Flatpak.

Pour un bug, indiquez la version, la distribution, le bureau, le type de session et la méthode d'installation, avec les étapes de reproduction. Pour une vulnérabilité, suivez la [procédure de signalement privé](SECURITY.md).

### Vérifier et construire

Depuis la racine du dépôt, avec les dépendances de développement et de packaging installées :

```bash
./scripts/smoke-test.sh
/usr/bin/python3 -m py_compile scripts/build-html-docs.py koplyx/main.py koplyx/__init__.py
./scripts/build-dist.sh
(cd dist && sha256sum -c SHA256SUMS)
```

Le build génère les paquets dans `dist/` et régénère les [pages HTML de documentation](docs/html/index.html) avec [le script dédié](scripts/build-html-docs.py). Ne versionnez pas les paquets générés ni les données personnelles de l'application.

Les ressources de packaging comprennent le [manifeste Snap](snap/snapcraft.yaml), le [manifeste Flatpak](packaging/flatpak/dev.limax.koplyx.yml), les [métadonnées AppStream](packaging/metainfo/dev.limax.koplyx.metainfo.xml) et les [outils de packaging](packaging/scripts/install-packaging-tools.sh). La [checklist manuelle](tasks/TESTS-MANUELS.md) complète les contrôles automatisés.
