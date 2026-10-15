"""Competence fichiers : lire, ecrire, arborescence, resume."""
import os
from rich.syntax import Syntax
from rich.tree import Tree

TEXTE_MAX = 200_000  # octets lus au plus


def chemin(arg):
    return os.path.abspath(os.path.expandvars(os.path.expanduser(arg.strip().strip('"'))))


def lire(ui, arg):
    if not arg:
        return ui.point("Usage : /lire <fichier>", "red")
    p = chemin(arg)
    if not os.path.isfile(p):
        return ui.point(f"Introuvable : {p}", "red")
    with open(p, encoding="utf-8", errors="replace") as f:
        txt = f.read(TEXTE_MAX)
    ui.point(f"Lecture de {p} ({len(txt.splitlines())} lignes)")
    ui.con.print(Syntax(txt, Syntax.guess_lexer(p, txt), line_numbers=True, word_wrap=True))
    return txt


def ecrire(ui, arg):
    if not arg:
        return ui.point("Usage : /ecrire <fichier>  puis tape le texte, termine par une ligne contenant juste .", "red")
    p = chemin(arg)
    ui.point("Tape le contenu. Termine par une ligne avec juste « . »", "grey50")
    lignes = []
    while True:
        l = ui.con.input("[grey50]│[/] ")
        if l.strip() == ".":
            break
        lignes.append(l)
    existe = os.path.exists(p)
    titre = ("Écraser" if existe else "Créer") + f" {p} ?"
    if not ui.confirmer(titre, f"{len(lignes)} lignes" + (" — le contenu actuel sera PERDU" if existe else ""), danger=existe):
        return ui.reagir("annule", "content")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n")
    ui.point(f"Écrit : {p}", "green")
    ui.xp(2)


def arbo(ui, arg):
    racine = chemin(arg or ".")
    if not os.path.isdir(racine):
        return ui.point(f"Pas un dossier : {racine}", "red")
    arbre = Tree(f"[bold]{racine}")

    def remplir(noeud, dossier, prof):
        try:
            items = sorted(os.scandir(dossier), key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError:
            return
        for i, e in enumerate(items):
            if i >= 25:
                noeud.add(f"[grey50]… +{len(items) - 25}"); break
            if e.is_dir():
                sous = noeud.add(f"[bold #4d9de0]{e.name}/")
                if prof < 1 and not e.name.startswith((".", "__")):
                    remplir(sous, e.path, prof + 1)
            else:
                noeud.add(f"{e.name} [grey50]{e.stat().st_size // 1024} Ko")
    remplir(arbre, racine, 0)
    ui.con.print(arbre)


def resume(ui, arg):
    p = chemin(arg) if arg else ""
    if not os.path.isfile(p):
        return ui.point("Usage : /resume <fichier>", "red")
    with open(p, encoding="utf-8", errors="replace") as f:
        txt = f.read(6000)  # le modele n'a que 4096 tokens de contexte
    r = ui.attendre(lambda: ui.ds.generer(
        f"Resume ce fichier en 3 a 5 puces courtes, en francais.\n\nFichier {os.path.basename(p)} :\n{txt}",
        prefixe="- ", longueur=250), "Je lis le fichier…")
    if r is None:
        return ui.reagir("annule", "surpris")
    ui.point("Résumé" + (" (début du fichier seulement)" if os.path.getsize(p) > 6000 else ""))
    ui.con.print("- " + r.strip())
    ui.xp(1)


COMMANDES = {
    "/lire": (lire, "affiche un fichier avec coloration"),
    "/ecrire": (ecrire, "écrit un fichier (texte tapé ligne par ligne)"),
    "/arbo": (arbo, "arborescence d'un dossier"),
    "/resume": (resume, "résumé d'un fichier par le modèle"),
}
