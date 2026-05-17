# Publication publique

Koplyx est pret pour une beta publique lorsque les tests de `docs/TEST_RELEASE.md` passent sur la matrice cible.

## Avant publication

- Verifier juridiquement le nom Koplyx sur INPI, EUIPO, USPTO et WIPO.
- Creer une cle mainteneur GPG et signer les artifacts ou le depot APT.
- Publier les checksums `SHA256SUMS` avec la release.
- Documenter explicitement les limites Wayland : raccourcis globaux et collage automatique dependent du bureau.
- Tester une installation propre depuis le `.deb`, puis suppression et reinstall.

## Commandes release

```bash
./scripts/smoke-test.sh
./scripts/build-dist.sh
cd dist
sha256sum -c SHA256SUMS
```

Tag GitHub :

```bash
git tag v0.2.0
git push origin main
git push origin v0.2.0
```

La GitHub Action publie les artifacts en release pour les tags `v*`.
