# État des tâches

## Parcours de l'assistant de collage

- [x] Cartographier l'état actuel des étapes, leur numérotation et la persistance des méthodes.
- [x] Représenter les sous-étapes GNOME/XWayland sans recommencer la numérotation à 1.
- [x] Continuer l'assistant après chaque réussite et permettre de choisir la méthode à conserver à la fin.
- [x] Mettre à jour la version beta, le changelog et les métadonnées pour l'assistant remanié.
- [x] Exécuter les vérifications du projet et contrôler les artefacts.
- [ ] Fusionner après CI, publier une nouvelle beta Snap, puis l'installer pour la vérification manuelle.
- [ ] Confirmer dans l'interface que les succès s'enchaînent et que le choix final est mémorisé.
- Vérifications : `xvfb-run -a ./scripts/smoke-test.sh`, build `.deb`, SHA-256, métadonnée AppStream et compilation Python réussis.

## Publication stable 0.4.6 et retrait des préversions beta

- [x] Préparer les métadonnées 0.4.6, la documentation et les changements locaux du bouton.
- [x] Exécuter les vérifications, les artefacts de distribution et contrôler leurs sommes.
- [x] Pousser la branche, créer la PR, attendre les contrôles, puis publier le tag stable.
- [x] Vérifier la publication Snap stable, fermer `latest/beta` et retirer les releases/tags GitHub beta.
- [x] Vérifier l'installation Snap stable sur cette machine.
- Résultat : PR #16 fusionnée, tag `v0.4.6` publié, workflow de release réussi. Snap `latest/stable` est en 0.4.6 révision 19; `latest/beta` est fermé et les releases/tags GitHub beta ont été supprimés. Installation locale confirmée, application démarrée depuis `/snap/koplyx/19/`.

## Bouton en double après un échec de collage

- [x] Masquer le bouton secondaire pendant l'état d'échec et le réafficher aux étapes suivantes.
- [x] Couvrir les transitions échec, nouvel essai et réussite dans la vérification de l'assistant.
- [x] Vérifier que l'interface n'affiche plus qu'une seule action après un échec.
- Vérification : `NO_AT_BRIDGE=1 timeout 30s dbus-run-session -- xvfb-run -a /usr/bin/python3 tests/test_history_interaction.py` réussit.

## Validation manuelle beta.3 sur la session active

- [x] Installer le `.deb` beta.3 et vérifier le paquet installé.
- [x] Confirmer Wayland, les droits `root:ydotool` sur `/dev/uinput` et la disponibilité d'un démon ydotool pour le test.
- [ ] Confirmer le marqueur réellement inséré dans un champ texte et distinguer ce résultat du code retour de ydotool.
- Note : le clic physique a renvoyé `True`, mais le champ ne contenait pas le marqueur. La restauration du presse-papiers a été confirmée; l'insertion du marqueur reste non validée.

## Correctif du parcours ydotool après relance XWayland

- [x] Conserver ydotool dans les étapes de l'assistant après la relance XWayland, avant le portail et le repli presse-papiers.
- [x] Ajouter une régression couvrant le plan du processus relancé et vérifier les tests ciblés.
- [x] Construire et contrôler le `.deb` beta.4, sa version Debian, son helper embarqué et son SHA-256.
- [x] Publier la préversion GitHub beta.4 avec le `.deb`, publier le Snap sur `latest/beta` et installer le `.deb` sur la session Wayland.
- [x] Confirmer dans un champ visible que le code beta.4 insère le marqueur par ydotool et restaure le presse-papiers précédent.
- [ ] Parcourir l'assistant Koplyx lui-même après sa relance XWayland et confirmer le backend ydotool.
- Empreinte construite : `0f8916423995be5ffeb213c08b42fe9376e0a79379ad0adabe0c10086a83d5b3`.
- Note : GitHub Release `v0.4.6-beta.4` créée. Le job Snap CI est refusé car son jeton limite les canaux à `edge,stable`; le Snap construit par CI a ensuite été publié avec la session locale en révision 18 de `latest/beta`.
- Vérification directe du 2026-09-24 : retour ydotool positif, marqueur observé dans le champ et contenu antérieur du presse-papiers restauré. Le test du parcours graphique complet reste à faire.

## Correctif final du test presse-papiers beta.3

- [x] Faire passer le bouton « Tester le presse-papiers » par le test actif commun avant confirmation.
- [x] Ajouter une régression UI, relancer le smoke test et reconstruire le `.deb`.
- [x] Publier `0.4.6-beta.3` sur `latest/beta`, publier le `.deb`, puis vérifier la révision Store.
- Note : `latest/beta` est maintenant sur la révision 17. La GitHub Release beta.3 est disponible; le test manuel du parcours reste à faire par l'utilisateur.

## Validation beta de l'assistant de collage

- [x] Vérifier et corriger les parcours de restauration presse-papiers et de test ydotool.
- [x] Ajouter une publication de tag beta vers le canal `latest/beta` sans toucher à `stable`.
- [x] Construire et valider le `.deb`, les tests et les métadonnées, puis confirmer les limites réelles de Snap pour ydotool.
- [x] Publier la version beta et vérifier le canal ainsi que les instructions d'installation.
- Note : beta.2 était la révision 16 et a été remplacée par beta.3. Le push CI Snap échoue toujours car le jeton GitHub est limité à `edge,stable`; les révisions beta.2 et beta.3 ont été publiées avec la session Snapcraft locale sans modifier le jeton GitHub.

## Onboarding de configuration du collage direct

- [x] Migrer la configuration avec `onboarding_completed` et `paste_backend` sans interrompre les profils existants.
- [x] Ajouter l'assistant GTK relançable depuis Paramètres : raccourci, diagnostic, test actif et replis explicites.
- [x] Ajouter la détection XWayland/Xorg et la commande de restauration de session GDM sans modifier automatiquement le système.
- [x] Ajouter le helper `pkexec` dédié à `ydotool` et la règle udev restreinte à l'utilisateur courant.
- [x] Intégrer la sélection du backend au collage runtime et fermer les sessions du portail après usage.
- [x] Remplacer le sélecteur technique par un parcours guidé qui essaie les méthodes successivement et ne mémorise qu'une réussite confirmée.
- [x] Mettre à jour le packaging, le README, le changelog et les tests manuels.
- [ ] Exécuter les tests, les artefacts et le lancement manuel avant tout push.

## Correction du parcours de test du collage direct

- [x] Rendre le repli presse-papiers réellement actif : restaurer l'élément, le laisser en première position et tenter Ctrl+V, avec un message clair si aucune injection n'est possible.
- [x] Ne proposer ydotool que lorsque le helper système est réellement installé, et expliquer la disponibilité depuis un paquet installé.
- [x] Rendre la demande « Bureau à distance » visible et diagnosticable, sans session persistante ouverte après le test.
- [x] Rejouer les tests, le smoke test et le build `.deb`; le build Snap local est bloqué par le réseau de l'instance LXD.
- [ ] Tester manuellement la beta publiée sous Wayland, notamment la restauration du presse-papiers et ydotool depuis le `.deb`.

## Parcours XWayland et Xorg dans l'assistant

- [ ] Relier la relance `GDK_BACKEND=x11` à une étape réelle de l'assistant et reprendre le test au redémarrage de Koplyx.
- [ ] Afficher le diagnostic XWayland/Xorg et expliquer lorsqu'aucune session Xorg ne peut demander un redémarrage.

## Repli de collage silencieux Wayland

- [x] Détecter et essayer les outils dans l'ordre `wtype`, `xdotool` XWayland, `ydotool`, puis le portail.
- [x] Ajouter les tests de sélection, d'échec et de repli entre les outils.
- [x] Mettre à jour les dépendances et la documentation sans rendre `ydotool` obligatoire.
- [x] Rejouer les tests, le smoke test et le build, puis relancer l'instance locale pour validation manuelle.

## Épinglage, affichage et collage direct

- [x] Remplacer le collage XTEST sous Wayland par une session clavier du portail, avec autorisation explicite et réutilisable.
- [x] Restreindre le style des boutons au contenu pour préserver les contrôles natifs de fenêtre.
- [x] Tester les erreurs, refus et collages successifs simulés ; vérifier la création/sélection clavier sur le portail GNOME réel et reconstruire les artefacts.
- [ ] Valider l'insertion réelle au curseur après autorisation dans l'instance locale et obtenir le retour utilisateur avant push.

- [x] Ajouter le filtre global persistant des éléments épinglés avec trois modes d'affichage.
- [x] Afficher tous les types dans l'onglet des éléments épinglés et tronquer les textes sur une ligne.
- [ ] Valider le collage direct sur le bureau réel après autorisation GNOME.
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

## Correctif réaffichage de l'assistant pendant les tests

- [x] Maintenir l'application active lorsque l'assistant et la fenêtre principale sont masqués pendant un test.
- [x] Réafficher l'assistant après succès ou échec du backend, puis libérer proprement l'application.
- [x] Ajouter un test de régression sur le cycle masquage, injection et réaffichage.
- [ ] Valider manuellement l'étape 2 sous Wayland.

## Release corrective 0.4.4

- [x] Mettre à jour la version centralisée, les métadonnées, la documentation et le changelog.
- [ ] Créer la pull request et attendre la CI complète.
- [ ] Merger vers `main`, créer le tag `v0.4.4` et vérifier la publication Snap stable.
