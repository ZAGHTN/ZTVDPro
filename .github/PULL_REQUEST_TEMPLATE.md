## Résumé

Décrivez brièvement la modification et son objectif.

## Type de changement

- [ ] Correctif de bug
- [ ] Nouvelle fonctionnalité
- [ ] Documentation
- [ ] Build / CI / distribution
- [ ] Traduction
- [ ] Refactorisation sans changement de comportement

## Vérifications

- [ ] `python -m pytest -q` passe
- [ ] `python -m compileall -q app main.py tests` passe
- [ ] `python -m flake8 .` passe
- [ ] `CHANGELOG.md` mis à jour si le comportement change
- [ ] Aucun secret, log, `.venv`, `dist`, `build`, `src/ffmpeg` ou `src/deno` ajouté

## Notes pour la revue

Précisez les points d'attention, les limitations ou les tests manuels effectués.
