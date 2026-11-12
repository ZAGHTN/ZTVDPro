# Compile ZTVD Pro avec PyInstaller (build « onedir »).
#
#   .\build.ps1            embarque Deno s'il est présent dans le PATH
#   .\build.ps1 -NoDeno    ne l'embarque pas (runtime à installer côté utilisateur)
#
# Résultat : dist\ZTVDPro\ZTVDPro.exe (distribuer le dossier complet).
[CmdletBinding()]
param(
    [switch]$NoDeno
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Environnement virtuel introuvable : $python`nCréez-le avec 'python -m venv .venv' puis installez requirements-dev.txt."
}

$pyVersion = (& $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ([version]$pyVersion -lt [version]"3.11") {
    throw "Python $pyVersion détecté : ZTVD Pro nécessite Python 3.11 ou plus récent."
}
Write-Host "Python $pyVersion détecté."

$ffmpegDir = Join-Path $PSScriptRoot "src\ffmpeg\bin"
foreach ($exe in @("ffmpeg.exe", "ffprobe.exe")) {
    $path = Join-Path $ffmpegDir $exe
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Fichier manquant : $path`nPlacez ffmpeg.exe et ffprobe.exe dans src\ffmpeg\bin."
    }
}

& $python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller n'est pas installé. Lancez : `"$python`" -m pip install -r requirements-dev.txt"
}

$env:ZTVD_EMBED_DENO = if ($NoDeno) { "0" } else { "1" }
if ($NoDeno) {
    Write-Host "Deno ne sera pas embarqué."
} else {
    $pathDeno = Get-Command deno -ErrorAction SilentlyContinue
    $localDeno = Join-Path $PSScriptRoot "src\deno\deno.exe"
    $localDenoBin = Join-Path $PSScriptRoot "src\deno\bin\deno.exe"
    $denoBinary = $null
    if ($pathDeno) {
        $denoBinary = $pathDeno.Source
        Write-Host "Deno sera embarqué depuis le PATH : $denoBinary"
    } elseif (Test-Path -LiteralPath $localDeno) {
        $denoBinary = $localDeno
        Write-Host "Deno sera embarqué depuis : $denoBinary"
    } elseif (Test-Path -LiteralPath $localDenoBin) {
        $denoBinary = $localDenoBin
        Write-Host "Deno sera embarqué depuis : $denoBinary"
    } else {
        Write-Warning "Deno introuvable (PATH, src\deno\deno.exe, src\deno\bin\deno.exe) : l'exécutable ne l'embarquera pas."
    }
    if ($denoBinary) {
        $denoLine = (& $denoBinary --version 2>$null | Select-Object -First 1)
        if ($denoLine -match 'deno\s+(\d+)\.(\d+)\.(\d+)') {
            $denoVersion = [version]"$($Matches[1]).$($Matches[2]).$($Matches[3])"
            if ($denoVersion -lt [version]"2.9.8") {
                Write-Warning "Deno $denoVersion détecté : yt-dlp recommande Deno 2.9.8 ou plus récent."
            } else {
                Write-Host "Deno $denoVersion détecté."
            }
        }
    }
}

& $python -m PyInstaller --noconfirm --clean "ZTVDPro.spec"
if ($LASTEXITCODE -ne 0) {
    throw "La compilation PyInstaller a échoué."
}

$exe = Join-Path $PSScriptRoot "dist\ZTVDPro\ZTVDPro.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    throw "Build terminé mais l'exécutable est introuvable : $exe"
}

Write-Host ""
Write-Host "Build terminé : $exe"
Write-Host "Dossier à distribuer : $(Split-Path -Parent $exe)"
