# Composants tiers et licences

ZTVD Pro est distribué sous **GNU General Public License v3.0** (voir [`LICENSE`](LICENSE)).
Le projet utilise ou embarque les composants suivants. Les textes intégraux des
licences principales sont dans le dossier [`licenses/`](licenses/).

## Composants embarqués dans la version compilée

| Composant | Version de référence | Licence | Texte / source |
|---|---|---|---|
| **FFmpeg / ffprobe** | `2026-10-25-git-46f23be8b1-full_build-www.gyan.dev` (`--enable-gpl --enable-version3`) | **GPL-3.0** | [`licenses/GPL-3.0.txt`](licenses/GPL-3.0.txt) — source : <https://www.gyan.dev/ffmpeg/builds/> et <https://ffmpeg.org/download.html> |
| **Qt / PySide6** (Essentials, Addons, Pdf, WebEngine) | 6.12.0 | **LGPL-3.0-only** (ou GPL-2.0/GPL-3.0) | [`licenses/LGPL-3.0.txt`](licenses/LGPL-3.0.txt) — source : <https://code.qt.io/> |
| **Shiboken6** | 6.12.0 | LGPL-3.0-only | [`licenses/LGPL-3.0.txt`](licenses/LGPL-3.0.txt) |
| **Deno** | 2.9.8 | **MIT** | [`licenses/Deno-MIT.txt`](licenses/Deno-MIT.txt) — <https://github.com/denoland/deno> |
| **yt-dlp** | 2026.10.26 | **Unlicense** | [`licenses/Unlicense.txt`](licenses/Unlicense.txt) — <https://github.com/yt-dlp/yt-dlp> |
| **yt-dlp-ejs** | 0.8.0 | **Unlicense** (composants MIT/ISC) | [`licenses/yt-dlp-ejs.txt`](licenses/yt-dlp-ejs.txt) — <https://github.com/yt-dlp/ejs> |
| **Python** | 3.14.x au moment du build | PSF-2.0 | <https://docs.python.org/3/license.html> |
| **PyInstaller** (bootloader) | 6.22.3 | GPL-2.0-or-later avec exception bootloader | [`licenses/PyInstaller.txt`](licenses/PyInstaller.txt) — <https://pyinstaller.org/> |

## Dépendances Python

La liste complète des paquets Python installés, avec leurs versions, licences et
URL, est générée dans [`licenses/PYTHON_PACKAGES.md`](licenses/PYTHON_PACKAGES.md).
Elle inclut notamment `curl_cffi`, `certifi`, `requests`, `urllib3`, `websockets`,
`cffi`, `charset-normalizer`, `idna`, `h11`, `trio`, `wsproto`, `PySocks`,
`packaging`, `pefile`, `altgraph` et `setuptools`.

## Conformité GPL / LGPL

- **FFmpeg** est distribué comme **exécutable séparé**, invoqué par l'application
  via un sous-processus. La source correspondant au binaire distribué est
  disponible aux URL ci-dessus ; une offre écrite de source peut être obtenue en
  ouvrant une issue sur le dépôt du projet.
- **Qt/PySide6** est utilisé sous l'option **LGPL-3.0**. Les bibliothèques Qt sont
  fournies sous forme de DLL séparées dans le dossier `dist\ZTVDPro\` (build
  « onedir »), ce qui permet à l'utilisateur de les remplacer par une version
  compatible. Le texte LGPL-3.0 est fourni dans `licenses/LGPL-3.0.txt`.
- Les autres composants conservent leurs licences respectives ; leurs textes sont
  inclus dans `licenses/` ou accessibles via les liens ci-dessus.

## Signaler une erreur

Si un composant ou une licence a été omis, merci d'ouvrir une issue :
<https://github.com/ZAGHTN/ZTVDPro/issues>.
