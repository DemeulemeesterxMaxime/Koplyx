# État des tâches

## Épinglage, affichage et collage direct

- [x] Ajouter le filtre global persistant des éléments épinglés avec trois modes d'affichage.
- [x] Afficher tous les types dans l'onglet des éléments épinglés et tronquer les textes sur une ligne.
- [x] Coller directement l'élément sélectionné dans la fenêtre précédente.
- [x] Mettre à jour la documentation et les tests.

## README orienté distribution et contributions

- [x] Mettre les installations, releases et contributions au premier plan.
- [x] Conserver les ressources open source et synchroniser la documentation HTML.
- [x] Vérifier les liens locaux et préparer la mise à jour sur la PR existante.

## Présentation README et assets visuels

- [x] Ajouter les badges Snap Store HTML et Markdown dans le README.
- [x] Générer et intégrer une bannière, des illustrations et une capture réelle de l'interface de présentation cohérentes avec Koplyx.
- [x] Vérifier les chemins d'assets, le rendu Markdown et les contrôles du dépôt.

## Release corrective 0.4.5

- [x] Mettre à jour la version centralisée, AppStream, Flatpak et le changelog pour le correctif de restauration au clic.
- [x] Valider les tests, le build des artefacts et les métadonnées de packaging.
- [x] Créer la pull request, attendre la CI complète, merger vers `main` et vérifier l'état distant.

## Publication 0.4.5

- [ ] Mettre à jour la procédure de publication avec la version courante.
- [ ] Valider la CI de la documentation, merger vers `main`, créer le tag et vérifier la GitHub Release.
- [ ] Construire, publier et vérifier le Snap dans le canal `latest/stable`.

## Correctif clic simple dans l'historique

- [x] Reproduire le parcours d'activation d'une ligne et identifier pourquoi le clic simple ne restaure pas l'élément.
- [x] Activer explicitement la restauration au clic simple tout en préservant les actions des boutons de ligne.
- [x] Ajouter une régression automatisée et documenter la vérification manuelle.

## Audit initial du projet

- [x] État du dépôt documenté le 2026-09-13.
- [x] Smoke test local passé : GTK, stockage chiffré, aperçus mémoire, permissions, autostart et démarrage caché.
- [x] Validation locale de la métadonnée desktop passée.
- [x] Checksums des artefacts `v0.2.4` vérifiés.
- [x] CI GitHub de `v0.2.4` passée avec succès et release publiée comme Latest.

## Reste à faire avant une beta publique/stable

- [ ] Exécuter la checklist manuelle de `docs/PUBLIC_RELEASE.md` sur X11 et Wayland.
- [ ] Tester installation propre, désinstallation et réinstallation du `.deb`.
- [ ] Construire et tester localement les paquets Snap et Flatpak.
- [ ] Vérifier la persistance, l'autostart, la barre système et le collage automatique sur les environnements cibles.
- [ ] Faire la vérification juridique du nom et préparer la signature GPG des artefacts.
- [ ] Ajouter une suite de tests dédiée si le projet doit évoluer au-delà de la beta.

## Refonte visuelle et validation du mode arrière-plan

- [x] Cartographier l'interface GTK actuelle et préserver chaque comportement existant.
- [x] Reconcevoir les écrans principal, paramètres et raccourci avec une identité visuelle cohérente.
- [x] Renforcer le démarrage caché et l'indicateur de barre système, avec retours d'état exploitables.
- [x] Ajouter des tests automatisés ciblant le stockage, le cycle de vie de l'application et l'indicateur système.
- [x] Exécuter les tests, le smoke test, le build des artefacts et les validations de métadonnées.
- [x] Consigner les limites de validation manuelle X11 et Wayland dans `tasks/TESTS-MANUELS.md`.

## Ajustement de l'identité visuelle

- [x] Centrer les icônes de type dans les cartes d'historique.
- [x] Revenir à la palette de marque vert, blanc et noir.
- [x] Vérifier le rendu GTK et les tests de régression.

## Release stable 0.3.0

- [x] Mettre à jour la version centralisée, les métadonnées de packaging et le changelog.
- [x] Ouvrir la pull request de release et attendre la CI GitHub.
- [x] Merger vers `main` après validation de la CI.
- [x] Créer le tag `v0.3.0` et vérifier la publication des artefacts GitHub.

## Correctif critique Snap 0.3.4

- [x] Identifier l'échec de démarrage depuis le centre d'applications : `SNAPCRAFT_ARCH_TRIPLET` indisponible à l'exécution.
- [x] Retirer la dépendance de runtime à cette variable de build.
- [x] Identifier les dépendances Python exclues par le filtre de staging et les permissions D-Bus manquantes.
- [x] Découpler l'ouverture de la fenêtre de l'autorisation D-Bus dans Snap.
- [x] Retirer les slots D-Bus qui imposent une revue manuelle du Store à la publication.
- [x] Valider les tests, l'artefact Snap et le lancement sur une installation Snap propre.
- [x] Ouvrir la pull request, attendre la CI puis publier `v0.3.4` sur le canal stable.

## Correctif de fermeture sans indicateur 0.3.5

- [x] Identifier que la croix consommait toute fermeture, même sans indicateur système disponible.
- [x] Quitter proprement l'application dans ce cas tout en conservant la réduction dans la barre système quand elle est disponible.
- [x] Valider la fermeture réelle et les artefacts de distribution.
- [ ] Ouvrir la pull request, attendre la CI puis publier `v0.3.5` sur le canal stable.

## Mode arrière-plan et raccourci global 0.4.0

- [x] Identifier que le Snap sans identifiant D-Bus lançait une nouvelle instance pour `--toggle`.
- [x] Ajouter un canal local entre instances afin que le raccourci active l'instance existante.
- [x] Rétablir l'indicateur système dans le Snap avec les permissions D-Bus requises par le Store.
- [x] Tester le démarrage caché, le raccourci et la réduction sur une session graphique isolée.
- [ ] Ouvrir la pull request, attendre la CI et soumettre la publication stable à la revue Snap si nécessaire.

## Correctif watcher Snap 0.4.1

- [x] Diagnostiquer le refus AppArmor vers `org.kde.StatusNotifierWatcher` sur la révision 10 installée.
- [x] Déclarer le plug D-Bus du watcher dans le manifeste Snap.
- [ ] Tester l'enregistrement réel de l'indicateur, la réduction et le raccourci après publication.
- [ ] Ouvrir la pull request, attendre la CI et soumettre la release au Store.

## Ergonomie de l'indicateur et du raccourci

- [ ] Vérifier manuellement le menu clic droit de l'indicateur et ses actions Paramètres et Quitter sur le bureau cible.
- [x] Installer ou synchroniser automatiquement le raccourci GNOME à chaque modification valide.
- [x] Supprimer le bouton d'installation devenu inutile et rendre la page Paramètres plus lisible.
- [x] Ajouter les tests ciblés, exécuter la validation complète et documenter le test manuel du raccourci GNOME.

## Release corrective 0.4.2

- [x] Mettre à jour la version centralisée, les métadonnées, la documentation et le changelog.
- [ ] Créer la pull request et attendre la CI complète.
- [ ] Merger vers `main`, créer le tag `v0.4.2` et vérifier la publication Snap stable.

## Correctif Snap du raccourci automatique 0.4.3

- [x] Identifier l'absence des schémas GNOME dans le Snap strict publié.
- [ ] Embarquer le paquet de schémas requis et empêcher sa régression avec le smoke test.
- [ ] Valider le Snap publié avec la modification réelle du raccourci GNOME.
- [ ] Ouvrir la pull request, attendre la CI, merger et publier sur `latest/stable`.

## Correctif du menu d'indicateur Snap

- [x] Identifier que l'hôte AppIndicators GNOME exige le chemin D-Bus standard `/StatusNotifierItem/menu`.
- [x] Passer au nom et au chemin StatusNotifierItem standard, puis retirer le bouton autostart redondant.
- [x] Ajouter les tests de régression et valider les contrôles automatisés du menu.
- [ ] Valider le menu réel sur le Snap publié.

## Release corrective 0.4.4

- [x] Mettre à jour la version centralisée, les métadonnées, la documentation et le changelog.
- [ ] Créer la pull request et attendre la CI complète.
- [ ] Merger vers `main`, créer le tag `v0.4.4` et vérifier la publication Snap stable.
