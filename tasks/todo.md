# État des tâches

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
