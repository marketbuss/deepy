"""Competence modele : choix automatique selon le PC, installation d'Ollama et du modele, mesure de vitesse."""
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn, TextColumn
from rich.table import Table
from rich import box
import materiel as mat

VITESSE_MIN = 4.0  # tokens/s en dessous desquels Deepy devient penible


def tableau_materiel(ui, m):
    t = Table(box=box.SIMPLE, show_header=False)
    t.add_column(style="grey50"); t.add_column(style="bold")
    t.add_row("Processeur", f"{m['cpu']} ({m['coeurs']} threads)")
    t.add_row("RAM", f"{m['ram']} Go (libre : {m['ram_libre']} Go)")
    t.add_row("Carte graphique", f"{m['gpu']} ({m['vram']} Go)" if m["gpu"] else "aucune NVIDIA → calcul sur le processeur")
    t.add_row("Disque libre", f"{m['disque_libre']} Go")
    ui.con.print(t)


def assurer_ollama(ui):
    if not mat.ollama_present():
        if not ui.confirmer("Ollama n'est pas installé", "Il fait tourner le modèle sur ton PC (gratuit, officiel).\n"
                                                         "L'installer maintenant avec winget ? (~1 Go)"):
            return False
        if not ui.attendre(mat.installer_ollama, "J'installe Ollama… (quelques minutes)"):
            ui.point("Installation impossible : installe Ollama depuis ollama.com puis relance.", "red")
            return False
    if not mat.ollama_repond() and not ui.attendre(mat.demarrer_ollama, "Je démarre Ollama…"):
        ui.point("Ollama ne démarre pas. Lance « ollama serve » puis relance Deepy.", "red")
        return False
    return True


def installer(ui, entree):
    """Telecharge le modele si absent (avec barre de progression). Renvoie True si dispo."""
    nom = entree["nom"]
    if any(i == nom or i == nom + ":latest" for i in mat.modeles_installes()):
        return True
    if not ui.confirmer(f"Télécharger {nom} ?", f"~{entree['taille']} Go depuis ollama.com · {entree['note']}"):
        return False
    with Progress(TextColumn("[bold #4d9de0]{task.description}"), BarColumn(), DownloadColumn(),
                  TransferSpeedColumn(), TimeRemainingColumn(), console=ui.con) as barre:
        tache = barre.add_task(nom, total=None)

        def avance(fait, total, statut):
            barre.update(tache, completed=fait, total=total or None, description=f"{nom} · {statut[:25]}")
        try:
            mat.telecharger(nom, avance)
        except (OSError, RuntimeError) as e:
            ui.point(f"Téléchargement échoué : {e}", "red")
            return False
    ui.point(f"{nom} installé.", "green")
    return True


def activer(ui, entree):
    """Installe, mesure la vitesse, et descend d'un cran si c'est trop lent."""
    liste = mat.CATALOGUE + mat.AUTRES
    while True:
        if not installer(ui, entree):
            return False
        vitesse = ui.attendre(lambda: mat.mesurer(entree["nom"]), f"Je mesure la vitesse de {entree['nom']}…")
        if vitesse is None:
            return False
        ui.point(f"{entree['nom']} : {vitesse} tokens/s")
        plus_petit = next((e for e in mat.CATALOGUE if e["taille"] < entree["taille"]), None)
        if vitesse >= VITESSE_MIN or not plus_petit or entree not in liste or \
                not ui.confirmer("C'est lent sur ce PC", f"{vitesse} tokens/s. Essayer {plus_petit['nom']} "
                                                         f"(plus léger, {plus_petit['note']}) ?"):
            break
        entree = plus_petit
    ui.ds.changer_modele(entree["nom"])
    ui.dire(f"J'utilise maintenant {entree['nom']} ({vitesse} tokens/s).", "fier")
    return True


def configurer(ui, force=False):
    """Au 1er lancement (ou /modele auto) : Ollama -> materiel -> choix -> installation -> vitesse."""
    if not assurer_ollama(ui):
        return False
    deja = ui.ds.lire_config().get("modele")
    if deja and not force and any(i.startswith(deja) for i in mat.modeles_installes()):
        return True
    ui.dire("Je regarde ton ordinateur pour choisir le meilleur cerveau…", "reflechit")
    m = ui.attendre(mat.detecter, "J'analyse le matériel…")
    if m is None:
        return False
    tableau_materiel(ui, m)
    choix = mat.choisir(m)
    ui.point(f"Recommandé : [bold]{choix['nom']}[/] — {choix['note']} (~{choix['taille']} Go)", "#d97757", markup=True)
    if activer(ui, choix):
        return True
    installes = mat.modeles_installes()  # refus ou echec : on garde ce qui est deja la
    if not installes:
        return False
    garde = ui.ds.MODELE if any(i.startswith(ui.ds.MODELE) for i in installes) else installes[0]
    ui.ds.changer_modele(garde)
    ui.dire(f"Je garde {garde} pour l'instant. /modele auto pour réessayer.", "content")
    return True


def commande(ui, arg):
    """/modele | /modele auto | /modele <nom>"""
    arg = arg.strip()
    if arg == "auto":
        return configurer(ui, force=True)
    liste = mat.CATALOGUE + mat.AUTRES
    if arg:
        e = next((x for x in liste if x["nom"] == arg), {"nom": arg, "taille": 0, "ram": 0, "vram": 0, "note": "manuel"})
        return activer(ui, e)
    m = ui.attendre(mat.detecter, "J'analyse le matériel…")
    tableau_materiel(ui, m)
    installes = mat.modeles_installes()
    t = Table(box=box.SIMPLE, header_style="bold")
    for col in ("", "Modèle", "Taille", "Tient sur ce PC", "Note"):
        t.add_column(col)
    for e in liste:
        tient = (m["gpu"] and m["vram"] >= e["vram"] > 0) or m["ram"] >= e["ram"]
        actif = "●" if e["nom"] == ui.ds.MODELE else ("ok" if any(i.startswith(e["nom"]) for i in installes) else "")
        t.add_row(actif, e["nom"], f"{e['taille']} Go", "oui" if tient else "[red]non[/]", e["note"])
    ui.con.print(t)
    ui.con.print("[grey50]  ● actif · ok installé — /modele auto (choix automatique) · /modele <nom>[/]")


def choisir_cerveau(ui, arg):
    """/cerveau | /cerveau groq | /cerveau local"""
    arg = arg.strip().lower()
    if arg not in ("groq", "local", "auto"):
        ui.point(f"Cerveau actuel : {ui.ds.nom_cerveau()} ({ui.ds.cerveau()})")
        ui.con.print("[grey50]  /cerveau groq  : gpt-oss-120b dans le cloud (rapide, plus juste, demande internet)\n"
                     "  /cerveau local : modèle Ollama sur ton PC (hors ligne, privé)\n"
                     "  /cerveau auto  : Groq si une clé ou un relais existe, sinon local (défaut)[/]")
        return
    if arg in ("groq", "auto"):
        if not ui.confirmer("Passer au cerveau Groq (cloud) ?",
                            "Tes messages partent chez Groq pour être traités (plus en local).\n"
                            "Les commandes restent proposées et confirmées par toi avant exécution."):
            return ui.reagir("annule", "content")
        try:
            g = ui.attendre(ui.ds.groq_client, "Je me connecte à Groq…")
        except Exception as e:
            return ui.point(f"Connexion impossible : {e}", "red")
        if g is None:
            return ui.reagir("annule", "surpris")
        ui.ds._GROQ_KO = False
    ui.ds.maj_config(cerveau=arg)
    acces = f" via {ui.ds._GROQ.acces}" if arg == "groq" else ""
    ui.dire(f"Cerveau : {ui.ds.nom_cerveau()}{acces}.", "fier")


COMMANDES = {"/modele": (commande, "cerveau de Deepy : /modele, /modele auto, /modele <nom>"),
             "/cerveau": (choisir_cerveau, "local (hors ligne) ou groq (cloud) : /cerveau groq|local")}
