"""Serveur MCP « fichiers » : lire et chercher partout dans le dossier perso ; ecrire seulement dans Documents\\Deepy."""
import fnmatch, os, time
from base import Serveur

srv = Serveur("fichiers", "Lecture et recherche dans le dossier personnel ; écriture limitée à Documents\\Deepy.")
PERSO = os.path.expanduser("~")
ECRITURE = os.path.join(PERSO, "Documents", "Deepy")


def chemin(p, racine=PERSO):
    """Chemin absolu, auc restriction de zone."""
    return os.path.realpath(os.path.join(racine, os.path.expandvars(p.strip().strip('"'))))


@srv.lecture
def lister(dossier: str = "") -> str:
    """Contenu d'un dossier (relatif au dossier personnel, ex. 'Documents' ou 'Desktop')."""
    d = chemin(dossier or ".")
    items = sorted(os.scandir(d), key=lambda e: (not e.is_dir(), e.name.lower()))
    return "\n".join(f"{e.name}/" if e.is_dir() else f"{e.name}  ({e.stat().st_size // 1024} Ko)"
                     for e in items[:200]) or "(vide)"


@srv.lecture
def lire(fichier: str, max_caracteres: int = 8000) -> str:
    """Lit un fichier texte (tronqué à max_caracteres)."""
    with open(chemin(fichier), encoding="utf-8", errors="replace") as f:
        return f.read(max(100, min(int(max_caracteres), 50000)))


@srv.lecture
def chercher(motif: str, dossier: str = "", contenu: str = "") -> str:
    """Cherche des fichiers par nom (motif type *.pdf) et, si contenu est donné, contenant ce texte."""
    racine, res, t0 = chemin(dossier or "."), [], time.time()
    for base, dirs, fichiers in os.walk(racine):
        dirs[:] = [d for d in dirs if not d.startswith((".", "AppData", "node_modules", "__pycache__"))]
        for f in fnmatch.filter(fichiers, motif or "*"):
            p = os.path.join(base, f)
            if contenu:
                try:
                    with open(p, encoding="utf-8", errors="ignore") as fh:
                        if contenu.lower() not in fh.read(500_000).lower():
                            continue
                except OSError:
                    continue
            res.append(p)
            if len(res) >= 50 or time.time() - t0 > 20:
                return "\n".join(res) + "\n(arrêté : 50 résultats ou 20 s)"
    return "\n".join(res) or "(aucun fichier)"


@srv.outil
def ecrire(nom: str, texte: str, ajouter: bool = False) -> str:
    """Écrit un fichier texte dans Documents\\Deepy (seul dossier autorisé en écriture)."""
    os.makedirs(ECRITURE, exist_ok=True)
    p = chemin(nom, ECRITURE)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a" if ajouter else "w", encoding="utf-8") as f:
        f.write(texte)
    return f"Écrit : {p}"


if __name__ == "__main__":
    srv.lancer()
