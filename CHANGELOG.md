# Changelog

Toutes les versions notables de Koplyx sont documentées dans ce fichier.

## [0.4.7-beta.2] - 2026-09-25

### Corrigé

- Le collage X11 utilise le clavier de la fenêtre active, après vérification de la cible, au lieu d'événements ciblés ignorés par GTK.
- Une copie de fichier ne crée plus une seconde entrée texte contenant son chemin.

### Ajouté

- La version centralisée est visible dans la section « À propos » des paramètres.
- Un test E2E isolé vérifie le texte réellement collé dans une autre application GTK et l'absence d'entrée parasite pour les fichiers.

## [0.4.7-beta.1] - 2026-09-24

### Modifié

- L'assistant numérote séparément l'accueil, la préparation, les méthodes de collage et le choix final.
- L'autorisation GNOME distingue clairement la demande d'accès clavier et le test de collage qui la suit.
- Une méthode confirmée n'interrompt plus le parcours : toutes les méthodes disponibles sont essayées avant le choix final.
- Les réussites confirmées sont conservées pendant la relance XWayland et proposées dans le récapitulatif final.
- La configuration Xorg est présentée comme préparée, sans être déclarée fonctionnelle avant la reconnexion.

## [0.4.6] - 2026-09-24

### Ajouté

- Filtre global des éléments épinglés : affichage en haut, en bas ou uniquement dans l'onglet `Épinglés`.
- Onglet `Épinglés` étendu aux textes, images et fichiers.
- Assistant de premier lancement pour le raccourci, le diagnostic de session et le test actif du collage direct.
- Helper privilégié limité à `ydotool` et à la sauvegarde/restauration GDM, avec règle udev dédiée à `/dev/uinput`.

### Modifié

- Les textes longs restent sur une seule ligne avec ellipse et infobulle.
- Un clic sur une entrée restaure puis colle directement le contenu dans la fenêtre précédente, sans nouvelle entrée d'historique.
- Le collage direct essaie `wtype`, `ydotool`, puis `xdotool` sur une cible XWayland avant de recourir au portail Wayland.
- La session du portail est fermée après l'autorisation ou le collage afin de ne pas laisser l'indicateur « Bureau à distance » affiché en permanence.
- Le backend de collage est persistant (`auto`, `wtype`, `xwayland`, `xorg`, `ydotool`, `portal` ou `clipboard_only`) et le portail n'est jamais ouvert automatiquement depuis un clic non configuré.
- Les profils existants sont migrés sans afficher l'assistant ; seuls les profils réellement neufs suivent le parcours de premier lancement.
- L'assistant essaie désormais les méthodes l'une après l'autre avec des libellés compréhensibles ; les Paramètres n'exposent plus de sélecteur technique de backend.
- Le mode presse-papiers restaure maintenant le contenu en première position, le garde disponible pour un Ctrl+V manuel, puis restaure le presse-papiers précédent après la réponse.
- Le bouton final « Tester le presse-papiers » lance maintenant réellement le test avant d'enregistrer ce mode.
- L'assistant ne propose plus `ydotool` si le helper système du paquet n'est pas installé et explique explicitement l'ouverture de la demande « Bureau à distance » avant le test du portail.
- Le Snap stable ne configure pas `/dev/uinput`; ydotool est réservé aux paquets non confinés équipés du helper système.

### Corrigé

- Le collage Wayland utilise une session clavier autorisée et réutilisée, au lieu de relancer `xdotool` et sa demande de connexion à distance à chaque clic.
- Après une relance XWayland, l'assistant poursuit l'essai vers ydotool; le helper vérifie les permissions de groupe appliquées à `/dev/uinput`.
- La confirmation mémorise le backend validé (`xwayland` ou `xorg`) plutôt que le nom du binaire `xdotool`.
- Les boutons natifs réduire, agrandir et fermer conservent les dimensions et le style du bureau.
- Le raccourci d'une exécution depuis les sources rouvre le même profil local, même si le Snap est installé.
- Une entrée locale impossible à déchiffrer ne bloque plus l'ouverture de l'historique.
- Le test de collage affiche une seule action après l'échec d'une méthode, puis rétablit les choix pour l'essai suivant.

## [0.4.5] - 2026-09-21

### Corrigé

- Un clic simple sur une carte de l'historique restaure désormais immédiatement la copie dans le presse-papiers.
- Le smoke test vérifie ce parcours d'interaction GTK sous affichage virtuel.

## [0.4.4] - 2026-09-19

### Corrigé

- L'indicateur Snap publie maintenant son menu avec le nom et le chemin D-Bus standard attendus par GNOME, ce qui rétablit les actions Afficher Koplyx, Paramètres et Quitter Koplyx.

### Modifié

- Le bouton redondant `Réparer l'autostart` est retiré des paramètres.

## [0.4.3] - 2026-09-19

### Corrigé

- Le Snap strict embarque maintenant les schémas GNOME requis pour appliquer automatiquement le raccourci global.

## [0.4.2] - 2026-09-19

### Modifié

- Le raccourci global GNOME est maintenant synchronisé automatiquement au démarrage et après chaque modification dans Koplyx.
- La page Paramètres présente l'accès rapide dans une carte plus lisible, avec l'état du raccourci.
- L'indicateur système expose les actions Afficher Koplyx, Paramètres et Quitter Koplyx avec une validation D-Bus complète.

## [0.4.1] - 2026-09-18

### Corrigé

- Le Snap reçoit l'accès D-Bus au watcher d'indicateurs système, nécessaire pour afficher Koplyx dans la barre système GNOME.

## [0.4.0] - 2026-09-15

### Ajouté

- Canal local sécurisé entre instances pour activer la fenêtre Koplyx déjà ouverte depuis le raccourci global dans le Snap.

### Modifié

- Le démarrage caché reste accessible par raccourci global même si l'indicateur système est temporairement indisponible.
- Le Snap redéclare les interfaces D-Bus nécessaires à l'indicateur de barre système, soumises à la validation du Store.

## [0.3.5] - 2026-09-14

### Corrigé

- La croix quitte désormais proprement Koplyx lorsqu'aucun indicateur système n'est disponible, au lieu de laisser la fenêtre ouverte.

## [0.3.4] - 2026-09-13

### Corrigé

- La publication du correctif de démarrage Snap ne dépend plus d'interfaces D-Bus soumises à une revue manuelle du Store.

## [0.3.3] - 2026-09-13

### Corrigé

- Koplyx ouvre désormais sa fenêtre dans le Snap même si le nom de service D-Bus de session n'est pas encore autorisé.
- Les noms D-Bus possédés par Koplyx sont déclarés comme des slots Snap, conformément au modèle de confinement.

## [0.3.2] - 2026-09-13

### Corrigé

- Le Snap embarque désormais les dépendances Python nécessaires et déclare les permissions D-Bus de l'application et de son indicateur système.

## [0.3.1] - 2026-09-13

### Corrigé

- Le lanceur Snap ne dépend plus d'une variable disponible seulement pendant la construction, ce qui rétablit le lancement depuis le centre d'applications.

## [0.3.0] - 2026-09-13

### Ajouté

- Tests automatisés du stockage chiffré, de l'indicateur D-Bus et de son cycle de vie sur une session réelle.
- Actions directes `Afficher Koplyx`, `Paramètres` et `Quitter Koplyx` dans l'indicateur système.
- CI exécutée sur chaque pull request vers `main` avant une release.

### Modifié

- Refonte complète de l'interface avec la palette vert, blanc et noir de Koplyx.
- Cartes d'historique, paramètres, recherche et états vides plus lisibles.
- Icônes de type centrées dans leur conteneur.
- Le lancement caché garde maintenant la fenêtre accessible si aucun hôte de barre système n'est disponible.

## [0.2.4] - 2026-05-20

- Aperçus texte, image et fichier déchiffrés uniquement en mémoire.
