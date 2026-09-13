# Leçons actives

[2026-09-13] | Les scripts Python lancés depuis `tests/` ne résolvent pas automatiquement le paquet à la racine. | Ajouter explicitement la racine du dépôt à `sys.path` dans les scripts de test autonomes.
[2026-09-13] | Sous Xvfb, le démarrage complet de GTK peut être bloqué par les portails du conteneur avant d'atteindre le code applicatif. | Tester l'indicateur D-Bus de façon isolée et compléter par un contrôle sur une session de bureau réelle.
[2026-09-13] | Le lanceur Snap 0.3.0 utilisait `SNAPCRAFT_ARCH_TRIPLET`, variable présente au build mais absente au runtime, et quittait avant le démarrage de l'application. | Ne jamais exposer une variable `SNAPCRAFT_*` dans un script exécuté par Snap et vérifier le lanceur dans le smoke test sans cette variable.
[2026-09-13] | Le filtre `stage` du part Snap excluait les dépendances déclarées dans `stage-packages`, dont Python et ses modules. | Ne jamais restreindre `stage` sans vérifier que chaque dépendance runtime est incluse dans le Snap produit.
