@echo off
chcp 65001 >nul
title Deepy
cd /d "%~dp0"
rem Ollama et le modele sont installes/demarres par Deepy lui-meme (competences/modele.py)
python interface.py
pause
