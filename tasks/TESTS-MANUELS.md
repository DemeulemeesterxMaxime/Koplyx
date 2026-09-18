# Tests manuels à effectuer

## À valider sur X11

- Vérifier la nouvelle hiérarchie visuelle avec un historique texte, image et fichiers.
- Fermer la fenêtre, faire un clic droit sur l'indicateur, puis vérifier `Afficher Koplyx`, `Paramètres` et `Quitter Koplyx`.
- Vérifier que le menu d'indicateur Snap apparaît bien depuis l'icône, sans nécessiter l'ouverture de la fenêtre.
- Modifier le raccourci dans Koplyx, vérifier qu'il est immédiatement visible dans les raccourcis GNOME, puis l'utiliser pour afficher et masquer l'application.
- Restaurer une copie texte dans une autre application et confirmer le collage automatique.

## À valider sur Wayland

- Vérifier que Koplyx reste accessible lorsque la barre système ou le raccourci global ne sont pas exposés par le compositeur.
- Tester l'historique, la restauration, l'indicateur éventuel et les limites de collage automatique propres au bureau.

## À valider après installation

- Installer le `.deb` sur un profil propre, redémarrer la session et confirmer l'autostart caché.
- Répéter les contrôles de l'indicateur avec les paquets Snap et Flatpak.
