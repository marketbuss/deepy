"""Serveur MCP « presse_papier » : lire et remplir le presse-papiers Windows."""
import os, subprocess
from base import Serveur

srv = Serveur("presse_papier", "Lit ou remplace le contenu du presse-papiers Windows (texte).")


def ps(cmd, texte=None):
    # le texte passe par une variable d'environnement : jamais insere dans la commande PowerShell
    env = {**os.environ, "DEEPY_TXT": texte or ""}
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + cmd],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, env=env)
    return r.stdout.rstrip()


@srv.lecture
def lire(max_caracteres: int = 4000) -> str:
    """Texte actuellement dans le presse-papiers."""
    t = ps("Get-Clipboard -Raw")
    return t[:max(1, int(max_caracteres))] if t else "(presse-papiers vide ou pas de texte)"


@srv.outil
def ecrire(texte: str) -> str:
    """Remplace le contenu du presse-papiers par ce texte."""
    ps("Set-Clipboard -Value $env:DEEPY_TXT", texte)
    return f"Copié dans le presse-papiers ({len(texte)} caractères)."


if __name__ == "__main__":
    srv.lancer()
