# Politique de sécurité

## Versions prises en charge

| Version | Support |
|---|---|
| 1.0.x | ✅ |
| < 1.0 | ❌ |

## Signaler une vulnérabilité

Merci de **ne pas ouvrir d'issue publique** pour une vulnérabilité de sécurité.

Utilisez de préférence l'onglet **Security → Advisories → Report a vulnerability**
du dépôt GitHub :

<https://github.com/ZAGHTN/ZTVDPro/security/advisories/new>

Si ce canal n'est pas disponible, contactez le mainteneur via GitHub en précisant :

- la version de ZTVD Pro et le système d'exploitation ;
- les étapes de reproduction ;
- l'impact estimé ;
- une preuve de concept si possible.

## Périmètre

Sont concernés notamment :

- l'exécution de commandes externes (yt-dlp, ffmpeg, Deno) ;
- le téléchargement et l'installation des wheels yt-dlp/yt-dlp-ejs ;
- la validation des URL et des chemins de fichiers ;
- les fichiers de configuration et les journaux ;
- la chaîne de build PyInstaller.

## Bonnes pratiques

- Téléchargez uniquement des contenus dont vous détenez les droits.
- Vérifiez les SHA-256 publiés avec les releases.
- Gardez yt-dlp à jour via **Outils → Mettre à jour yt-dlp…**.
- Signalez toute dépendance compromise via le canal ci-dessus.
