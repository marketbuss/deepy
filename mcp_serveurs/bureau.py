"""Serveur MCP « bureau » : ouvrir un site, un dossier ou une appli, notifications et rappels Windows."""
import os, re, shutil, subprocess
from base import Serveur

srv = Serveur("bureau", "Ouvre des sites, dossiers et applications ; affiche des notifications et des rappels minutés.")
APPS = {"bloc-notes": "notepad", "notepad": "notepad", "calculatrice": "calc", "calc": "calc", "paint": "mspaint",
        "explorateur": "explorer", "gestionnaire des taches": "taskmgr", "parametres": "ms-settings:",
        "chrome": "chrome", "edge": "msedge", "firefox": "firefox", "vscode": "code", "code": "code", "spotify": "spotify:",
        "discord": "discord", "terminal": "wt"}
SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DETACHE = SANS_FENETRE | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

# Bulle de notification Windows ; titre et texte passent par l'environnement (pas d'injection PowerShell)
BULLE = ("Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
         "$n = New-Object System.Windows.Forms.NotifyIcon; $n.Icon = [System.Drawing.SystemIcons]::Information; "
         "$n.Visible = $true; $n.ShowBalloonTip(10000, $env:DEEPY_TITRE, $env:DEEPY_TEXTE, 'Info'); "
         "Start-Sleep -Seconds 11; $n.Dispose()")


def bulle(titre, texte, attente=0):
    env = {**os.environ, "DEEPY_TITRE": titre[:60] or "Deepy", "DEEPY_TEXTE": texte[:250] or " "}
    cmd = (f"Start-Sleep -Seconds {int(attente)}; " if attente else "") + BULLE
    subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", cmd], env=env,
                     creationflags=DETACHE, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@srv.outil
def ouvrir_site(url: str) -> str:
    """Ouvre une adresse web (http/https) dans le navigateur par défaut."""
    if not re.match(r"^https?://", url):
        url = "https://" + url.lstrip("/")
    if not re.match(r"^https?://[\w.-]+(:\d+)?(/\S*)?$", url):
        return "Adresse invalide."
    os.startfile(url)
    return f"Ouvert : {url}"


@srv.outil
def ouvrir_dossier(chemin: str) -> str:
    """Ouvre un dossier dans l'explorateur (ex : Documents, Bureau, Téléchargements ou un chemin complet)."""
    alias = {"bureau": "Desktop", "documents": "Documents", "telechargements": "Downloads", "téléchargements": "Downloads",
             "images": "Pictures", "musique": "Music", "videos": "Videos", "vidéos": "Videos"}
    p = os.path.join(os.path.expanduser("~"), alias[chemin.lower()]) if chemin.lower() in alias else os.path.expanduser(chemin)
    if not os.path.isdir(p):
        return f"Dossier introuvable : {p}"
    os.startfile(p)
    return f"Ouvert : {p}"


@srv.outil
def lancer_app(nom: str) -> str:
    """Lance une application par son nom (bloc-notes, calculatrice, paint, chrome, vscode, spotify, discord…)."""
    cible = APPS.get(nom.lower().strip(), nom.strip())
    if not re.fullmatch(r"[\w.-]+:?", cible):
        return "Nom d'application invalide."
    if cible.endswith(":"):  # protocole (ms-settings:, spotify:)
        os.startfile(cible)
    elif shutil.which(cible):
        subprocess.Popen([shutil.which(cible)], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    else:
        try:
            os.startfile(cible)  # applis enregistrees (App Paths)
        except OSError:
            return f"Application introuvable : {nom}"
    return f"Lancé : {nom}"


@srv.outil
def notifier(titre: str, texte: str) -> str:
    """Affiche une notification Windows."""
    bulle(titre, texte)
    return "Notification affichée."


@srv.outil
def rappel(minutes: float, texte: str) -> str:
    """Programme un rappel : une notification apparaîtra dans N minutes (max 24 h). Fonctionne même si Deepy est fermé."""
    secondes = int(float(minutes) * 60)
    if not 1 <= secondes <= 86400:
        return "Durée entre 1 seconde et 24 heures."
    bulle("Rappel Deepy", texte, secondes)
    return f"Rappel programmé dans {minutes:g} min : {texte}"


if __name__ == "__main__":
    srv.lancer()
