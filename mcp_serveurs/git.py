"""Serveur MCP « git » : etat d'un depot Git, historique, differences. Lecture seule (rien n'est commite)."""
import os, shutil, subprocess
from base import Serveur

srv = Serveur("git", "Lit l'état d'un dépôt Git : fichiers modifiés, historique, différences, branches. Lecture seule.")
SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def git(dossier, *args):
    if not shutil.which("git"):
        return "Git n'est pas installé (winget install Git.Git)."
    d = os.path.expanduser(dossier or ".")
    if not os.path.isdir(d):
        return f"Dossier introuvable : {d}"
    r = subprocess.run(["git", "-C", d, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=30, creationflags=SANS_FENETRE)
    return (r.stdout if r.returncode == 0 else r.stderr).strip() or "(rien)"


@srv.lecture
def statut(dossier: str = ".") -> str:
    """Branche actuelle et fichiers modifiés / non suivis d'un dépôt."""
    return git(dossier, "status", "--short", "--branch")


@srv.lecture
def historique(dossier: str = ".", nombre: int = 10) -> str:
    """Derniers commits (date, auteur, message)."""
    return git(dossier, "log", f"-{max(1, min(int(nombre), 50))}", "--pretty=format:%h  %ad  %an  %s", "--date=short")


@srv.lecture
def differences(dossier: str = ".", fichier: str = "", max_caracteres: int = 6000) -> str:
    """Modifications non commitées (diff), pour tout le dépôt ou un fichier."""
    t = git(dossier, "diff", "--", fichier) if fichier else git(dossier, "diff")
    return t[:max(200, int(max_caracteres))]


@srv.lecture
def branches(dossier: str = ".") -> str:
    """Branches locales et distantes."""
    return git(dossier, "branch", "-a", "-vv")


if __name__ == "__main__":
    srv.lancer()
