# Tests manuels à effectuer

## À valider sur X11

- Vérifier la nouvelle hiérarchie visuelle avec un historique texte, image et fichiers.
- Épingler un texte, une image et un fichier, puis vérifier leur présence dans l'onglet `Épinglés`.
- Utiliser le bouton de filtre global et tester les trois choix `Épingles en haut`, `Épingles en bas` et `Épingles uniquement dans Épinglés`.
- Vérifier l'ordre des éléments en haut, normaux et en bas dans l'historique principal.
- Copier un texte long, vérifier que sa carte reste sur une ligne avec ellipse et que l'infobulle donne le contenu normalisé.
- Cliquer une seule fois sur une carte de l'historique et vérifier que le contenu est collé dans la fenêtre précédente, sans nouvelle entrée ni déplacement dans l'historique.
- Fermer la fenêtre, faire un clic droit sur l'indicateur, puis vérifier `Afficher Koplyx`, `Paramètres` et `Quitter Koplyx`.
- Vérifier que le menu d'indicateur Snap apparaît bien depuis l'icône, sans nécessiter l'ouverture de la fenêtre.
- Modifier le raccourci dans Koplyx, vérifier qu'il est immédiatement visible dans les raccourcis GNOME, puis l'utiliser pour afficher et masquer l'application.
- Restaurer une copie texte, image et fichier dans une autre application et confirmer le collage direct.

## À valider sur Wayland

- Sur un profil réellement neuf, vérifier que l'assistant s'ouvre au premier lancement, synchronise le raccourci GNOME et affiche le diagnostic de session.
- Dans l'assistant, cliquer dans un champ texte cible, lancer le test actif et confirmer le texte identifiable. Vérifier qu'il n'est pas ajouté à l'historique et que l'ancien presse-papiers revient lorsque le bureau le permet.
- Tester un échec, puis les options `wtype`, XWayland local, Xorg, `ydotool`, portail et presse-papiers uniquement. Le portail ne doit jamais s'ouvrir automatiquement depuis un clic non configuré.
- Relancer l'assistant depuis Paramètres et vérifier la persistance de `paste_backend` et `onboarding_completed`.
- Si une session Xorg est disponible, vérifier la sauvegarde GDM, le message de redémarrage, le bouton « Restaurer Wayland » et le refus de restauration après modification externe. Tester aussi `koplyx --restore-display-session`.
- Si `ydotool` est disponible, vérifier que le bouton demande explicitement `pkexec`, crée uniquement le groupe `ydotool`, installe la règle `/dev/uinput`, n'utilise jamais le groupe `input`, puis demande une reconnexion. Sous Snap ou Flatpak, vérifier que le bouton est désactivé.

- Vérifier que le raccourci rouvre bien l'instance locale en cours de test, et non le Snap installé.
- Depuis Paramètres, autoriser le clavier dans la demande du bureau, puis revenir au champ cible et sélectionner une entrée : vérifier le texte effectivement inséré au curseur.
- Répéter avec deux entrées différentes : aucune nouvelle demande d'autorisation ne doit apparaître tant que Koplyx reste ouvert.
- Fermer puis relancer Koplyx avec le même profil : sélectionner une entrée et vérifier que le jeton persistant réactive le collage sans nouvelle demande. Si le bureau a révoqué l'autorisation, le clic doit seulement restaurer le contenu et afficher un message invitant à retourner dans Paramètres.
- Refuser une demande, puis réessayer dans les paramètres. Aucun collage ne doit partir dans la boîte d'autorisation.
- Vérifier que les boutons réduire, agrandir et fermer ont leur apparence native dans l'historique et les paramètres.
- Vérifier que Koplyx reste accessible lorsque la barre système ou le raccourci global ne sont pas exposés par le compositeur.
- Tester l'historique, la restauration, l'indicateur éventuel et les limites de collage automatique propres au bureau.

## À valider après installation

- Installer le `.deb` sur un profil propre, redémarrer la session et confirmer l'autostart caché.
- Répéter les contrôles de l'indicateur avec les paquets Snap et Flatpak.
