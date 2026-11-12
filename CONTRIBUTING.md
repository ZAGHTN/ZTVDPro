# Contribuer à ZTVD Pro

Merci pour votre intérêt ! Les contributions (correctifs, traductions,
documentation, tests) sont bienvenues.

## Environnement de développement

Prérequis :

- Python **3.11+** ;
- ffmpeg et ffprobe dans `src/ffmpeg/bin` ou dans le `PATH` ;
- Deno **2.9.8+** (recommandé) ou Node.js pour les formats YouTube récents.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python main.py
```

Sur macOS/Linux :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python main.py
```

## Tests et qualité

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q app main.py tests
.venv\Scripts\python.exe -m flake8 .
```

La CI exécute les tests sur Ubuntu et Windows avec Python 3.11 et 3.13.
Les tests Qt utilisent `QT_QPA_PLATFORM=offscreen` (voir `tests/conftest.py`).

## Compilation Windows

```powershell
.\build.ps1
```

Le résultat est dans `dist\ZTVDPro\`. Distribuez le dossier complet, jamais
seulement l'exécutable. Pour ne pas embarquer Deno :

```powershell
.\build.ps1 -NoDeno
```

## Règles de contribution

- Ouvrez une issue avant les changements importants.
- Gardez les modifications ciblées et ajoutez des tests pour les correctifs.
- Respectez le style existant (français pour les commentaires/docstrings,
  anglais pour les identifiants).
- Ne committez jamais `.venv/`, `dist/`, `build/`, `src/ffmpeg/`, `src/deno/`,
  les logs, les secrets ou les fichiers `.part`.
- Mettez à jour `CHANGELOG.md` pour les changements visibles.
- Vérifiez que `pytest`, `compileall` et `flake8` passent avant d'ouvrir une PR.

## Licence

En contribuant, vous acceptez que votre contribution soit distribuée sous
**GPL-3.0-only**, la licence du projet (voir [`LICENSE`](LICENSE)).
