# Guide de build et de release

Ce document décrit l'environnement utilisé pour produire les releases Windows de
ZTVD Pro et les vérifications à effectuer avant publication.

## Versions de référence

Environnement validé le **2026-11-12** :

| Composant | Version |
|---|---|
| Windows | 11 x64 |
| Python | 3.14.7 |
| PySide6 | 6.12.0 |
| yt-dlp | 2026.10.26 |
| yt-dlp-ejs | 0.8.0 |
| PyInstaller | 6.22.3 |
| Deno | 2.9.8 |
| FFmpeg | `2026-10-25-git-46f23be8b1-full_build-www.gyan.dev` |

Les dépendances Python sont épinglées dans `requirements.txt` et
`requirements-dev.txt`. Pour un build reproductible, conservez ces versions ou
mettez-les à jour de façon explicite dans le `CHANGELOG.md`.

## FFmpeg / ffprobe

Le build utilisé est un build **GPLv3** de gyan.dev, avec `--enable-gpl` et
`--enable-version3`. Placez les deux binaires ici :

```text
src\ffmpeg\bin\ffmpeg.exe
src\ffmpeg\bin\ffprobe.exe
```

Empreintes SHA-256 de référence :

```text
ffmpeg.exe  54B3FB947722175FFA9D9A3D6B43DE1A11D053366500BDEED75C3A4E1F343B00
ffprobe.exe 83F4654A31EA8F2A3B01AC9313A45FEF7DBE25DC715D0F00A50B310C28C801C7
```

Vérification PowerShell :

```powershell
Get-FileHash .\src\ffmpeg\bin\ffmpeg.exe -Algorithm SHA256
Get-FileHash .\src\ffmpeg\bin\ffprobe.exe -Algorithm SHA256
```

`ffplay.exe` n'est pas embarqué : inutile pour l'application et volumineux.

## Deno

Deno est optionnel mais recommandé pour les formats YouTube récents. Le build
l'embarque s'il est trouvé :

1. dans le `PATH` ;
2. dans `src\deno\deno.exe` ;
3. dans `src\deno\bin\deno.exe`.

Pour un build reproductible, préférez un binaire épinglé dans `src\deno\` plutôt
que le Deno du `PATH`. `build.ps1` avertit si la version détectée est inférieure
à **2.9.8**.

Sans Deno embarqué, l'utilisateur devra installer Deno ou Node.js.

## Compilation

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
.\build.ps1
```

Résultat :

```text
dist\ZTVDPro\ZTVDPro.exe
dist\ZTVDPro\
```

**Distribuez toujours le dossier complet `dist\ZTVDPro\`**, jamais seulement
l'exécutable : ffmpeg, ffprobe, le solveur EJS et éventuellement Deno sont à côté.

Pour ne pas embarquer Deno :

```powershell
.\build.ps1 -NoDeno
```

Équivalent manuel :

```powershell
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean ZTVDPro.spec
```

## Vérifications avant release

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q app main.py tests
.venv\Scripts\python.exe -m flake8 .
```

Puis lancez l'exécutable et vérifiez :

- l'icône de la fenêtre et de l'exécutable ;
- l'analyse d'une URL ;
- un téléchargement court avec fusion ffmpeg ;
- **Aide → À propos** (versions) ;
- la présence de ffmpeg, du solveur EJS et de Deno dans `dist\ZTVDPro\`.

## Archive de release

```powershell
Compress-Archive -Path .\dist\ZTVDPro\* -DestinationPath .\ZTVDPro-1.0.0-win64.zip
Get-FileHash .\ZTVDPro-1.0.0-win64.zip -Algorithm SHA256
```

Créez ensuite une release GitHub `v1.0.0`, joignez le zip et publiez le SHA-256
dans les notes. Une archive compressée d'environ 275 Mo (663 Mo extraits) reste
sous la limite GitHub de **2 Go par asset** ; la limite de **100 Mo par fichier**
concerne le dépôt Git, pas les releases.

### Release 1.0.0

- Page : <https://github.com/ZAGHTN/ZTVDPro/releases/tag/v1.0.0>
- Asset : `ZTVDPro-1.0.0-win64.zip` (272,6 Mo)
- SHA-256 : `D7E6CD95576BEF85C47912C094AF33B8DAE5B332FED7BADA9EF8952108528CF7`

## CI GitHub Actions

Le workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) exécute le lint
et les tests sur Ubuntu et Windows avec Python 3.11 et 3.13. Il se déclenche sur
les push et pull requests vers `master`, et peut être lancé manuellement depuis
l'onglet **Actions**.

Si l'onglet Actions affiche **« Actions has been disabled for this user »**,
le blocage est au niveau du compte GitHub, pas du dépôt : le réglage
**Settings → Actions → General** ne suffit pas. Il faut contacter le support
GitHub pour faire réactiver Actions, puis relancer le workflow.

## Captures d'écran du README

```powershell
.venv\Scripts\python.exe tools\make_screenshot.py
```

Le script régénère `docs/screenshots/main.png` (thème clair) et
`main-dark.png` (thème sombre). Il s'appuie sur la plateforme Qt **native** avec
une fenêtre non affichée (`WA_DontShowOnScreen`). N'utilisez pas
`QT_QPA_PLATFORM=offscreen` sous Windows : cette plateforme ne charge aucune
police, `QFontDatabase.families()` renvoie 0 et tous les glyphes sont rendus en
carrés. Le script s'arrête avec un message explicite si aucune police n'est
disponible.

## Signature Windows (optionnel)

L'exécutable n'est pas signé. Windows SmartScreen peut afficher un avertissement
au premier lancement. Pour une distribution grand public, envisagez une
signature Authenticode (Azure Trusted Signing, SignPath, etc.).

## macOS / Linux

Le fichier `ZTVDPro.spec` et `build.ps1` ciblent Windows. Pour macOS/Linux,
adaptez les noms d'exécutables ffmpeg/ffprobe (sans `.exe`) et utilisez
directement PyInstaller. La CI teste le code source sur Ubuntu et Windows, mais
aucune release macOS/Linux n'est produite automatiquement à ce jour.
