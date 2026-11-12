# Changelog

Toutes les modifications notables de ZTVD Pro sont documentées ici.
Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et le
versionnage respecte [Semantic Versioning](https://semver.org/lang/fr/).

## [1.0.0] - 2026-11-12

### Ajouté

- Interface PySide6 (Qt 6) avec thèmes clair/sombre et traductions EN/FR/AR.
- Analyse de l'URL avant téléchargement (titre, chaîne, durée, qualité maximale).
- Téléchargement via yt-dlp + ffmpeg, avec fusion sans ré-encodage.
- Qualités jusqu'à 8K et formats MP4, MKV, WEBM, MOV, AVI, MP3.
- Repli automatique WEBM → MKV en cas d'incompatibilité de codecs.
- Pause, reprise (fichiers `.part`), annulation et arrêt coopératif des threads.
- Ouverture du dossier de sortie et sélection du fichier téléchargé.
- Mise à jour de yt-dlp depuis l'interface :
  - `pip` en mode source ;
  - wheels PyPI vérifiées par SHA-256 dans `%LOCALAPPDATA%` en version compilée,
    avec repli automatique sur la version intégrée et menu de retour arrière.
- Journalisation rotative dans le dossier utilisateur.
- Solveur EJS (`yt-dlp-ejs`) embarqué et Deno optionnel.
- Build PyInstaller « onedir » (`ZTVDPro.spec`, `build.ps1`).
- Icône multi-résolutions et ressources embarquées.
- Suite de tests pytest (82 tests) et workflow GitHub Actions.
- Documentation de build, licence GPL-3.0 et notices des composants tiers.

### Corrigé

- Typage de `InstallWorker` : hérite désormais d'`UpdateWorker`.
- Qualités/formats grisés tant que l'URL n'est pas analysée.
- Vidage du presse-papiers à la fermeture uniquement s'il contient encore l'URL
  de la fenêtre.
- Validation des réglages `QSettings` et gestion des valeurs corrompues.
- Fuite de workers Qt après des pauses/reprises répétées.
