# État des lieux Koplyx, 25 septembre 2026

## Verdict

Le socle historique fonctionne dans le parcours instrumenté testé : copie texte, capture, stockage chiffré, recherche, épingles, restauration manuelle et persistance. Deux anomalies sont reproduites : collage automatique X11 inefficace vers la cible GTK et entrée texte supplémentaire lors de la capture d'un fichier. La validation E2E complète du Snap sur GNOME/Wayland reste à faire. Cet audit ne constitue pas une validation de release.

## Périmètre réellement exécuté

- Sources locales `0.4.7-beta.1`, commit de base `8352db4`, branche `feature/onboarding-method-choice`, incluant la modification locale préexistante de l'affichage de version.
- Snap installé : `0.4.7-beta.1`, révision 20, suivi `latest/beta`. Ses fichiers confirment l'absence du nouvel affichage de version des sources. Le Snap n'a pas été piloté graphiquement pendant cet audit.
- Bureau hôte : Wayland. L'hôte StatusNotifierWatcher répond, le service utilisateur ydotool est actif et son socket existe. Cela ne prouve ni le collage ni le menu graphique.
- Tests comportementaux sur Xvfb/X11 avec xfwm4, GTK 4.22.4, PyGObject 3.56.2 et Python 3.14.4. Profil temporaire, bus D-Bus isolé sans activation de services, GSettings en mémoire pour la sonde.
- Une application GTK distincte sert de cible : copie par Ctrl+C réel, lecture de son champ après collage. L'activation de carte est déclenchée par le signal GTK `row-activated`, pas par un clic physique. Recherche, épingles et suppression sont pilotées par les widgets et callbacks.
- Images et fichiers : publication et relecture du vrai presse-papiers GDK. Leur collage dans une application tierce n'a pas été testé. Pour leur restauration seule, la sonde configure la branche de repli `portal` sans autorisation, avec la variable de session `wayland`; cela ne simule pas un vrai bureau Wayland.
- Aucun changement du code applicatif, commit, push, installation ou publication effectué. Les données du parcours sont synthétiques et le profil final est supprimé.

## Résultats

| Parcours | Résultat observé |
| --- | --- |
| Smoke test | Réussi : 36 tests unittest, puis contrôles GTK de l'historique/assistant, contrôles de fenêtre, indicateur D-Bus simulé, stockage et démarrage |
| Copie texte depuis une autre application | Texte Unicode exact capturé dans l'historique |
| Stockage | Contenu déchiffrable, marqueur absent du fichier SQLite principal; la suite existante vérifie aussi chiffrement et permissions |
| Restauration texte | Ctrl+V classique dans la cible restitue le texte exact, sans doublon texte |
| Collage automatique | Échec décrit ci-dessous |
| Recherche | Recherche dans le contenu déchiffré et recherche sans résultat validées |
| Épingles | Épinglage par callback et présence dans l'onglet dédié validés |
| Paramètres | Le widget contient la version centralisée dans les sources locales |
| Image | Capture puis restauration GDK validées, dimensions conservées |
| Fichier | Capture et restauration de l'URI validées; entrée texte parasite également observée |
| Persistance | Réouverture de la base avec une nouvelle instance du stockage et de la clé : mêmes entrées et texte exact; pas un redémarrage complet de l'application |
| Suppression | Suppression unitaire et effacement du profil de test validés |

## Anomalies reproduites

### Priorité haute : collage automatique X11 vers GTK

Après activation de la carte, le champ cible reste vide, malgré le statut « Commande de collage envoyée à la fenêtre active. » et un retour positif de l'injecteur. Un essai direct `xdotool key --window <cible> --clearmodifiers ctrl+v`, avec la cible active, reste sans effet. `xdotool key --clearmodifiers ctrl+v` sur cette même cible colle le texte exact.

Point à examiner : `koplyx/main.py:435`, qui ajoute `--window`, et `koplyx/main.py:2951`, qui interprète le retour de commande. Le défaut est reproduit sur la cible GTK/X11 isolée. Sa portée sur GNOME/XWayland et le Snap reste à vérifier; le test ne démontre pas un échec de tous les backends.

### Priorité moyenne : un fichier produit également une entrée texte

Une seule publication GDK du fichier synthétique produit une entrée `file` et une entrée `text` contenant `/tmp/koplyx-e2e-.../fichier-test.txt`. Le profil contient donc quatre entrées pour trois contenus copiés : texte, image, fichier et chemin texte supplémentaire.

Explication cohérente avec le code : `ClipboardWatcher.poll` lit simultanément les formats texte et fichier; `on_text` ignore seulement les chaînes commençant par `file://` (`koplyx/main.py:815`), alors que la conversion GDK fournit ici un chemin absolu. L'absence de doublon pour la restauration d'un texte ne couvre pas ce cas multi-format.

## Fiabilité des contrôles et dette de validation

- Le premier smoke standard s'est bloqué dans l'accès à `org.freedesktop.secrets` et a atteint le timeout de 120 secondes. Il réussit avec un bus sans activation de services, ce qui utilise la clé de fichier. L'intégration réelle GNOME Keyring n'est donc pas validée. Le plug Snap `password-manager-service` est déconnecté sur cette machine.
- `tests/test_session_tray.py:15` attend encore `dev.limax.koplyx.StatusNotifierItem`, tandis que le code publie `org.kde.StatusNotifierItem-<PID>-1`. Ce script manuel est obsolète, absent du smoke et ne doit pas servir de preuve de panne de l'indicateur. Il n'isole pas le runtime et peut synchroniser le raccourci du bureau.
- Les tests existants simulent l'injecteur de collage, la relance XWayland, l'hôte d'indicateur et les réponses du portail. Ils passent sans garantir le texte réellement collé sur GNOME.
- L'assistant complet, le choix final après une vraie relance XWayland, l'autorisation GNOME, la restauration du jeton après fermeture de session portail, le menu réel du Snap, le raccourci global et l'autostart après reconnexion restent non validés ici.
- Plusieurs cases historiques dans `tasks/todo.md` contredisent des notes de réalisation ultérieures. Elles ne représentent pas un inventaire fiable des bugs actuels.
- La première sonde d'audit a subi un segfault en conservant un objet GDK FileList au-delà du callback. La lecture des URI a été déplacée dans le callback; le parcours termine alors. Ce problème de sonde n'est pas présenté comme un crash applicatif confirmé.

## Preuves et reproduction

Fichiers conservés dans `tasks/preuves-e2e-2026-09-25/` : sonde `e2e.py`, configuration D-Bus, journal du smoke et journal final du parcours. La sonde est un outil de diagnostic : elle poursuit après le collage automatique défaillant, donc son code retour 0 ne signifie pas que tous les parcours passent. Consulter les lignes `PASS`, `FAIL` et `DIAGNOSTIC`.

Depuis la racine du dépôt :

```sh
timeout 90s dbus-run-session --config-file=tasks/preuves-e2e-2026-09-25/dbus.conf -- xvfb-run -a ./scripts/smoke-test.sh

timeout 40s dbus-run-session --config-file=tasks/preuves-e2e-2026-09-25/dbus.conf -- xvfb-run -a env GDK_BACKEND=x11 XDG_SESSION_TYPE=x11 GTK_A11Y=none GSK_RENDERER=cairo /usr/bin/python3 -X faulthandler tasks/preuves-e2e-2026-09-25/e2e.py
```

La suite des validations sur bureau réel est décrite dans `tasks/TESTS-MANUELS.md`. Priorité : corriger et retester les deux anomalies, puis exécuter le parcours réel du Snap et du portail Wayland avant toute conclusion de stabilité globale.

## Suivi : correction beta.2

Les deux anomalies ci-dessus ont ensuite été corrigées dans les sources de `0.4.7-beta.2`. Le nouveau test `tests/test_clipboard_e2e.py` vérifie une insertion automatique exacte et trois entrées pour trois contenus copiés; les versions réintroduisant chaque bug échouent séparément. Le rapport initial conserve les observations faites avant correction. La validation de release est suivie dans `tasks/todo.md`.
