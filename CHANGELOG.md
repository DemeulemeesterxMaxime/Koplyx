# Changelog

Toutes les versions notables de Koplyx sont documentées dans ce fichier.

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
