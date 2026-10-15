"""Serveur MCP « notes » : carnet de notes et de taches persistant (%APPDATA%\\Deepy\\notes.json)."""
import json, os, time
from base import Serveur

srv = Serveur("notes", "Carnet de notes et de tâches de l'utilisateur.")
FICHIER = os.path.join(os.environ.get("DEEPY_DATA") or os.path.join(os.environ.get("APPDATA", "."), "Deepy"), "notes.json")


def charger():
    try:
        with open(FICHIER, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def sauver(notes):
    os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
    tmp = FICHIER + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=1)
    os.replace(tmp, FICHIER)


@srv.outil
def ajouter(texte: str, tache: bool = False, etiquette: str = "") -> str:
    """Ajoute une note (ou une tâche à cocher si tache=true), avec une étiquette facultative."""
    notes = charger()
    n = {"id": max([x["id"] for x in notes], default=0) + 1, "texte": texte.strip(), "tache": tache,
         "faite": False, "etiquette": etiquette.strip().lower(), "date": time.strftime("%Y-%m-%d %H:%M")}
    notes.append(n)
    sauver(notes)
    return f"Ajouté (n°{n['id']})."


@srv.lecture
def lister(etiquette: str = "", seulement_a_faire: bool = False) -> str:
    """Liste les notes, filtrées par étiquette ou seulement les tâches non faites."""
    notes = [n for n in charger() if (not etiquette or n["etiquette"] == etiquette.lower())
             and (not seulement_a_faire or (n["tache"] and not n["faite"]))]
    if not notes:
        return "(aucune note)"
    return "\n".join(f"{n['id']}. {'[x] ' if n['faite'] else '[ ] ' if n['tache'] else ''}{n['texte']}"
                     f"{'  #' + n['etiquette'] if n['etiquette'] else ''}  ({n['date']})" for n in notes)


@srv.outil
def cocher(id: int, faite: bool = True) -> str:
    """Marque une tâche comme faite (ou non faite)."""
    notes = charger()
    for n in notes:
        if n["id"] == int(id):
            n["faite"] = faite
            sauver(notes)
            return f"Tâche {id} : {'faite' if faite else 'à faire'}."
    return f"Pas de note n°{id}."


@srv.lecture
def chercher(mot: str) -> str:
    """Cherche un mot dans les notes."""
    m = mot.lower()
    r = [f"{n['id']}. {n['texte']}" for n in charger() if m in n["texte"].lower() or m == n["etiquette"]]
    return "\n".join(r) or "(rien trouvé)"


@srv.outil
def supprimer(id: int) -> str:
    """Supprime une note."""
    notes = charger()
    reste = [n for n in notes if n["id"] != int(id)]
    if len(reste) == len(notes):
        return f"Pas de note n°{id}."
    sauver(reste)
    return f"Note {id} supprimée."


if __name__ == "__main__":
    srv.lancer()
