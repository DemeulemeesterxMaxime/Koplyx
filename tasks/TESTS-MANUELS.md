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
- Vérifier que l'étape XWayland explique la relance locale de Koplyx avec `GDK_BACKEND=x11`, sans redémarrer Ubuntu, puis que l'assistant reprend le test dans le nouveau processus. Si aucun fichier `/usr/share/xsessions/*.desktop` n'existe, vérifier que l'assistant explique pourquoi l'étape Xorg avec redémarrage est indisponible.
- Dans l'assistant, préparer un champ texte cible, lancer le test actif et confirmer le texte identifiable. Vérifier qu'il n'est pas ajouté à l'historique et que l'ancien presse-papiers revient lorsque le bureau le permet.
- Déclarer un échec, vérifier que l'assistant propose la solution suivante sans exposer de jargon, puis parcourir les méthodes jusqu'à la demande « Bureau à distance » et au mode presse-papiers. Le portail doit annoncer sa demande avant de l'afficher et ne doit jamais s'ouvrir automatiquement depuis un clic non configuré.
- Relancer l'assistant depuis Paramètres et vérifier qu'aucun sélecteur de backend n'est présent : la méthode est mémorisée uniquement après « Oui, ça fonctionne ».
- Si une session Xorg est disponible, vérifier la sauvegarde GDM, le message de redémarrage, le bouton « Restaurer Wayland » et le refus de restauration après modification externe. Tester aussi `koplyx --restore-display-session`.
- Si `ydotool` et son helper de paquet sont disponibles, vérifier que le bouton demande explicitement `pkexec`, crée uniquement le groupe `ydotool`, installe la règle `/dev/uinput`, n'utilise jamais le groupe `input`, puis demande une reconnexion. Depuis les sources sans helper, l'étape ne doit pas être proposée. Sous Snap ou Flatpak, vérifier que le bouton est désactivé.

- Vérifier que le raccourci rouvre bien l'instance locale en cours de test, et non le Snap installé.
- Depuis Paramètres, autoriser le clavier dans la demande du bureau, puis revenir au champ cible et sélectionner une entrée : vérifier le texte effectivement inséré au curseur.
- Répéter avec deux entrées différentes : aucune nouvelle demande d'autorisation ne doit apparaître tant que Koplyx reste ouvert.
- Fermer puis relancer Koplyx avec le même profil : sélectionner une entrée et vérifier que le jeton persistant réactive le collage sans nouvelle demande. Si le bureau a révoqué l'autorisation, le clic doit seulement restaurer le contenu et afficher un message invitant à retourner dans Paramètres.
- Refuser une demande, puis réessayer dans les paramètres. Aucun collage ne doit partir dans la boîte d'autorisation.
- Vérifier que les boutons réduire, agrandir et fermer ont leur apparence native dans l'historique et les paramètres.
- Vérifier que Koplyx reste accessible lorsque la barre système ou le raccourci global ne sont pas exposés par le compositeur.
- Tester l'historique, la restauration, l'indicateur éventuel et les limites de collage automatique propres au bureau.
- En mode presse-papiers, cliquer une entrée et vérifier que son contenu devient le presse-papiers courant, qu'aucune nouvelle entrée d'historique n'est créée et que Koplyx tente Ctrl+V avant d'afficher une consigne manuelle si l'injection est impossible.

## À valider après installation

- Installer le `.deb` sur un profil propre, redémarrer la session et confirmer l'autostart caché.
- Répéter les contrôles de l'indicateur avec les paquets Snap et Flatpak.
## Validation beta de l'assistant de collage (0.4.6-beta.4)

- Installer le Snap avec `sudo snap install koplyx --channel=latest/beta`, ou basculer avec `sudo snap refresh koplyx --channel=latest/beta`, puis confirmer `latest/beta` avec `snap info koplyx`.
- Dans Paramètres, ouvrir l'assistant, suivre le test jusqu'au repli presse-papiers, puis vérifier que le marqueur reste copiable au clavier après le retour de l'assistant. Confirmer le mode et vérifier qu'une copie réelle suivante apparaît dans l'historique.
- Pour ydotool, installer le `.deb` `koplyx_0.4.6-beta.4_all.deb` depuis la GitHub Release préversion, lancer cette installation plutôt que le Snap, puis utiliser l'assistant pour autoriser le helper. Après la relance XWayland, l'étape ydotool doit rester proposée. Vérifier `/dev/uinput` en `root:ydotool` avec le mode `660`, se déconnecter/reconnecter, démarrer le service utilisateur avec `systemctl --user start ydotool` s'il est inactif, et vérifier le socket `$XDG_RUNTIME_DIR/.ydotool_socket` avant le test réel dans un champ Wayland.
- Pour xdotool sous Wayland, tester dans une cible XWayland et confirmer le texte réellement collé; le code retour seul ne valide pas l'essai.
- Revenir au Snap stable avec `sudo snap refresh koplyx --channel=latest/stable` après la validation beta.

### Résultat du test direct beta.4, 2026-09-24

- Sous la session Wayland, le champ de test actif a reçu le marqueur via `paste_clipboard_now` du paquet installé, en forçant `ydotool`.
- Le code retour était positif, le marqueur exact a été observé et le contenu antérieur du presse-papiers a été restauré.
- Ce contrôle valide l'injection ydotool et la restauration dans la sonde; il ne remplace pas le parcours complet de l'assistant Koplyx après relance XWayland.
