@echo off
chcp 65001 > nul
title BDD Pubs
cd /d "%~dp0"
where py > nul 2> nul
if %errorlevel%==0 (
  py -3 app.py %*
) else (
  python app.py %*
)
if errorlevel 1 (
  echo.
  echo Probleme au lancement. Python est-il installe ?
  echo Telechargement : https://www.python.org/downloads/  ^(cocher "Add python.exe to PATH"^)
  pause
)
