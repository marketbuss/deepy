"""Tests de validite des commandes (chemins inventes, syntaxe fausse, recherches sur tout un disque).
Usage : python test_commandes.py   (aucune commande n'est executee)"""
import os, sys, tempfile

os.environ["DEEPY_DATA"] = tempfile.mkdtemp(prefix="deepy_test_")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deepseek_local as ds

INVALIDES = [
    'Get-ChildItem "C:\\Program Files (x86)\\Roblox\\Versions" -Directory',
    'Start-Process "${studio.FullName}\\RobloxStudioBeta.exe"',
    'Start-Process "C:\\Program Files\\Invente\\app.exe"',
    'Get-Content "C:\\inexistant\\x.txt"',
    "Get-ChildItem -Path 'C:\\' -Filter 'x.txt' -Recurse -ErrorAction SilentlyContinue",
    'Get-ChildItem C:\\ -Recurse -Filter *.pdf',
    'gci -Recurse D:\\',
]
VALIDES = [
    'Get-ChildItem "$env:USERPROFILE\\Desktop"',
    'Get-ChildItem "$env:USERPROFILE\\Documents" -Recurse -Filter *.pdf',
    'New-Item -ItemType Directory "$env:USERPROFILE\\Desktop\\nouveau"',
    'Start-Process "https://www.youtube.com"',
    'Start-Process notepad',
    'Get-ChildItem C:\\',
    'cd C:\\Windows; dir',
    'Get-Process | Sort-Object CPU -Descending | Select-Object -First 5',
]

if __name__ == "__main__":
    erreurs = 0
    for c in INVALIDES:
        if ds.commande_valide(c):
            erreurs += 1
            print(f"ECHEC devrait etre invalide :: {c}")
    for c in VALIDES:
        if not ds.commande_valide(c):
            erreurs += 1
            print(f"ECHEC devrait etre valide ({ds.pourquoi_invalide(c)}) :: {c}")
    total = len(INVALIDES) + len(VALIDES)
    print(f"== COMMANDES : {total - erreurs}/{total} correct")
    sys.exit(1 if erreurs else 0)
