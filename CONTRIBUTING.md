# Contribuer a Koplyx

Merci de vouloir contribuer a Koplyx. Le projet est une application Linux de bureau pour historiser le presse-papiers localement, avec une priorite sur la confidentialite, la simplicite et l'integration GNOME/X11.

## Avant de commencer

- Ouvrir une issue avant une modification importante.
- Garder les changements limites a un sujet clair.
- Ne pas ajouter de synchronisation cloud, telemetrie ou dependance lourde sans discussion prealable.
- Documenter les limites Wayland quand une fonctionnalite depend du bureau.

## Environnement local

```bash
cd Koplyx
./bin/koplyx
```

Validation minimale avant pull request :

```bash
./scripts/smoke-test.sh
/usr/bin/python3 -m py_compile scripts/build-html-docs.py koplyx/main.py koplyx/__init__.py
./scripts/build-dist.sh
cd dist
sha256sum -c SHA256SUMS
```

## Style de contribution

- Utiliser les patterns deja presents dans le code.
- Garder l'interface compacte et sobre.
- Ne pas committer les artefacts generes : `dist/`, `*.snap`, `__pycache__/`.
- Mettre a jour `README.md` ou `docs/PUBLIC_RELEASE.md` si le comportement utilisateur ou le packaging change.

## Pull requests

Une pull request doit contenir :

- le probleme traite ;
- le resume des changements ;
- les tests lances ;
- les limites connues, surtout pour Wayland, Snap ou Flatpak.

## Signalement de bug

Inclure si possible :

- distribution et version Linux ;
- session X11 ou Wayland ;
- environnement de bureau ;
- installation utilisee : source, `.deb`, Snap ou Flatpak ;
- logs ou traceback.
