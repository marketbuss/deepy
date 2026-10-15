@echo off
chcp 65001 >nul
title Installation de Deepy
cd /d "%~dp0"
echo.
echo   Installation de Deepy - assistant IA local
echo   ==========================================
echo.

rem 1. Python
where python >nul 2>nul
if errorlevel 1 (
  echo   Python n'est pas installe.
  choice /m "  L'installer maintenant avec winget (source officielle)"
  if errorlevel 2 goto fin
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  echo   Ferme cette fenetre et relance installer.bat pour continuer.
  goto fin
)

rem 2. Dependances Python
echo   Installation des dependances...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo   Echec de pip. Verifie ta connexion internet.
  goto fin
)

rem 3. Raccourci sur le Bureau
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Deepy.lnk'); $s.TargetPath='%~dp0Deepy.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%SystemRoot%\System32\SHELL32.dll,220'; $s.Save()"
echo   Raccourci « Deepy » cree sur le Bureau.

rem 4. Pont VS Code (sans extension) : Deepy devient un serveur MCP du chat de VS Code
where code >nul 2>nul
if not errorlevel 1 (
  python -c "import sys; sys.path.insert(0, r'%~dp0.'); from competences import vscode; r = vscode.installer_silencieux(); print('  VS Code : Deepy connecte (outils deepy_* dans le chat)' if r == 'ok' else '  VS Code : ' + r)"
)
echo.
echo   Deepy va maintenant choisir et installer le modele adapte a ton PC.
echo.
call "%~dp0Deepy.bat"
exit /b

:fin
pause
