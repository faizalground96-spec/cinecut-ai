@echo off
REM CineCut AI — Instalasi otomatis untuk Windows (Metode B, developer)
REM Klik dua kali file ini. Tidak perlu instal Python / FFmpeg manual.
setlocal
cd /d "%~dp0\.."

where python >nul 2>nul
if errorlevel 1 (
  echo Python belum ketemu. Pasang dulu Python 3.11+ dari python.org, lalu jalankan lagi file ini.
  pause
  exit /b 1
)

if not exist venv (
  echo Membuat virtual environment...
  python -m venv venv
)
call venv\Scripts\activate.bat

echo Menginstal pustaka...
pip install -r requirements.txt

if not exist bin\ffmpeg.exe (
  echo Mengunduh FFmpeg untuk Windows...
  powershell -Command "Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile '%TEMP%\ffmpeg.zip'; Expand-Archive -Path '%TEMP%\ffmpeg.zip' -DestinationPath '%TEMP%\ffmpeg-extract' -Force; Copy-Item '%TEMP%\ffmpeg-extract\ffmpeg-*-essentials_build\bin\ffmpeg.exe' 'bin\ffmpeg.exe' -Force; Copy-Item '%TEMP%\ffmpeg-extract\ffmpeg-*-essentials_build\bin\ffprobe.exe' 'bin\ffprobe.exe' -Force"
)

echo Membuat shortcut di Desktop...
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\CineCut AI.lnk'); $Shortcut.TargetPath = '%CD%\venv\Scripts\python.exe'; $Shortcut.Arguments = '%CD%\src\main.py'; $Shortcut.WorkingDirectory = '%CD%'; $Shortcut.Save()"

echo Selesai! Klik shortcut "CineCut AI" di Desktop untuk membuka aplikasi.
pause
