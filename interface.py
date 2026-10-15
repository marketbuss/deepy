"""DeepSeek local - interface style terminal Claude + compagnon Deepy (baleine)."""
import json, os, random, re, threading, time
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
import deepseek_local as ds
import securite
import reactions as rx
import competences

con = Console(highlight=False)
ACCENT, BLEU, GRIS = "#d97757", "#4d9de0", "grey50"
FICHIER_COMPAGNON = ds.donnee("compagnon.json")

# ---------- Compagnon ----------
YEUX = {"content": "o", "reflechit": "-", "fier": "^", "triste": "x", "dort": "u", "surpris": "O"}
JETS = ["   .  ", "  ' . ", "   ' .", "  . ' "]
# Deepy grandit avec son niveau : (niveau mini, nom, couleur, dessin)
STADES = [
    (10, "baleine légendaire", "#e5b94e", ["     {jet}", "      ,/\\/\\,", "  .-''''''-.___/|",
                                           " (  {e}          _<", "  \\   ~~       /\\|", "   `-.......-'"]),
    (6, "grande baleine", "#4d9de0", ["     {jet}", "  .-''''''-.___/|", " (  {e}          _<",
                                      "  \\   ~~       /\\|", "   `-.......-'"]),
    (3, "baleine", "#4d9de0", ["   {jet}", "  .-'''-.__/|", " ( {e}      _ <", "  `-....-' \\|"]),
    (1, "bébé baleine", "#7fc8f8", ["  {jet}", "   .-''-._/|", "  ( {e}    _<", "   `-..-'\\|"]),
]
class Compagnon:
    def __init__(self):
        d = {}
        try:
            with open(FICHIER_COMPAGNON, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            pass
        self.nom, self.xp, self.humeur, self.anim = d.get("nom", "Deepy"), d.get("xp", 0), "content", None
        self.stats = d.get("stats", {"questions": 0, "commandes": 0, "echecs": 0})

    @property
    def niveau(self):
        return self.xp // 20 + 1

    def sauver(self):
        with open(FICHIER_COMPAGNON, "w", encoding="utf-8") as f:
            json.dump({"nom": self.nom, "xp": self.xp, "stats": self.stats}, f, ensure_ascii=False)

    def gagner(self, n):
        avant, stade = self.niveau, self.stade
        self.xp += n
        self.sauver()
        if self.stade != stade:  # evolution : moment a partager
            con.print(Panel(Group(Text(f"{self.nom} évolue en {self.stade[1]} !", style="bold #e5b94e"),
                                  self.dessin()), box=box.DOUBLE, border_style="#e5b94e", padding=(0, 2)))
        return self.niveau > avant

    @property
    def stade(self):
        return next(s for s in STADES if self.niveau >= s[0])

    def dessin(self, frame=0):
        _, _, couleur, art = self.stade
        images = rx.ANIMS.get(self.anim) or [{}]
        img = images[frame % len(images)]
        e = img.get("yeux") or YEUX.get(self.humeur, "o")
        jet = img.get("haut", JETS[frame % 4] if self.humeur in ("reflechit", "fier") and not self.anim else "")
        pad = " " * img.get("decal", 0)
        lignes = [pad + l.replace("{jet}", jet).replace("{e}", e) for l in art]
        if img.get("cote"):
            i = next(i for i, l in enumerate(art) if "{e}" in l)
            lignes[i] += img["cote"]
        lignes.append(pad + img.get("bas", ""))  # ligne toujours presente : le dessin ne saute pas
        return Text("\n".join(lignes), style=couleur)

    def vue(self, bulle, frame=0):
        g = Table.grid(padding=(0, 1))
        g.add_column(no_wrap=True)
        g.add_column()
        txt = Text.assemble((f"{self.nom} ", f"bold {BLEU}"), (f"niv {self.niveau} · {self.stade[1]}\n", GRIS),
                            (bulle, "italic"))
        g.add_row(self.dessin(frame), Panel(txt, box=box.ROUNDED, border_style=GRIS, padding=(0, 1)))
        return g

    def dit(self, evenement, humeur=None):
        self.humeur = humeur or rx.humeur(evenement)
        self.anim = rx.anim(evenement) if ANIMATIONS[0] else None
        return rx.phrase(evenement)


ANIMATIONS = [ds.lire_config().get("animations", True)]


def montrer(c, bulle, images=8):
    """Joue l'animation en cours (~1 s) puis laisse Deepy affiche, calme."""
    if c.anim and ANIMATIONS[0] and con.is_terminal:
        with Live(console=con, refresh_per_second=12, transient=True) as live:
            for f in range(images):
                live.update(c.vue(bulle, f))
                time.sleep(0.13)
    con.print(c.vue(bulle, images - 1))
    c.anim = None


# ---------- Affichage ----------
def accueil(c, neurones, exemples):
    info = Text.assemble(("* ", ACCENT), ("Deepy", "bold"), ("  ·  cerveau : ", GRIS), (ds.nom_cerveau(), GRIS), "\n\n",
                         ("/aide", "bold"), (" pour l'aide · ", GRIS), ("!cmd", "bold"), (" commande directe\n", GRIS),
                         (f"cwd : {os.getcwd()}\n", GRIS),
                         (f"{len(neurones)} neurones · {len(exemples)} exemples d'entraînement", GRIS))
    con.print(Panel(info, box=box.ROUNDED, border_style=ACCENT, padding=(1, 2)))
    montrer(c, c.dit(rx.salutation()))


def carte(c):
    """Carte de profil de Deepy : affichee + exportee en image SVG et texte pour la partager."""
    s, n = c.stats, int(10 * (c.xp % 20) / 20)
    infos = Text.assemble((f"{c.nom}\n", "bold"), (f"{c.stade[1]} · niveau {c.niveau}\n", GRIS),
                          ("█" * n + "░" * (10 - n), BLEU), (f" {c.xp}/{c.niveau * 20} XP\n\n", GRIS),
                          (f"{s['questions']} questions\n{s['commandes']} commandes réussies\n{s['echecs']} échecs\n\n", ""),
                          (f"cerveau : {ds.nom_cerveau()}", GRIS))
    g = Table.grid(padding=(0, 3))
    g.add_column(no_wrap=True); g.add_column()
    g.add_row(c.dessin(), infos)
    panneau = Panel(g, title=f"[bold {ACCENT}]* Deepy[/]", subtitle="[grey50]IA locale · 100 % hors ligne[/]",
                    box=box.ROUNDED, border_style=ACCENT, padding=(1, 2), width=64)
    con.print(panneau)
    dossier = os.path.join(os.path.expanduser("~"), "Documents", "Deepy")
    os.makedirs(dossier, exist_ok=True)
    rec = Console(record=True, width=64, file=open(os.devnull, "w", encoding="utf-8"))
    rec.print(panneau)
    rec.save_svg(os.path.join(dossier, "carte-deepy.svg"), title=f"{c.nom} · Deepy")
    point(Text(f"Carte enregistrée : {os.path.join(dossier, 'carte-deepy.svg')} (à partager !)", style=GRIS), GRIS)


def point(texte, style="white"):
    con.print(Text.assemble(("● ", style), texte))


def sortie_cmd(sortie, ok):
    lignes = sortie.splitlines() or ["(vide)"]
    montre = lignes[:15]
    for i, l in enumerate(montre):
        con.print(Text.assemble(("  └ " if i == 0 else "    ", GRIS), (l, "white" if ok else "red")))
    if len(lignes) > 15:
        con.print(Text(f"    … +{len(lignes) - 15} lignes", style=GRIS))


def statut(c, duree=None, source=""):
    t = f"{c.nom} niv {c.niveau} · {c.xp} XP · {ds.nom_cerveau()}"
    if duree is not None:
        t += f" · {source}{duree:.1f} s"
    con.print(Text(t, style=GRIS), justify="right")


def penser(c, q, historique, exemples):
    return attendre(c, lambda: ds.repondre(q, historique, exemples))


def attendre(c, fonction, bulle=None, evenement=None):
    """Lance fonction() dans un thread ; Deepy s'anime pendant l'attente. Ctrl+C abandonne (-> None)."""
    res = {}

    def tache():
        try:
            res["r"] = fonction()
        except Exception as e:  # remonte l'erreur au fil principal
            res["e"] = e
    fil = threading.Thread(target=tache, daemon=True)
    fil.start()
    evt = evenement or ("cloud" if ds.groq_actif() and not bulle else "reflechit")
    texte = c.dit(evt)
    bulle, t0, frame = bulle or texte, time.time(), 0
    c.humeur = "reflechit"
    try:
        with Live(console=con, refresh_per_second=6, transient=True) as live:
            while fil.is_alive():
                live.update(Group(c.vue(bulle, frame),
                                  Text(f"  {time.time() - t0:.1f} s · Ctrl+C pour annuler", style=GRIS)))
                frame += 1
                fil.join(0.25)
    except KeyboardInterrupt:
        return None
    if "e" in res:
        raise res["e"]
    return res.get("r")


class UI:
    """Ce que les competences peuvent utiliser."""
    def __init__(self, c):
        self.con, self.c, self.ds = con, c, ds

    def point(self, texte, style="white", markup=False):
        # markup seulement sur demande : un chemin ou une sortie contenant [..] casserait l'affichage
        point(texte if isinstance(texte, Text) else Text.from_markup(texte) if markup else Text(texte), style)

    def dire(self, bulle, humeur="content"):
        self.c.humeur = humeur
        con.print(self.c.vue(bulle))

    def reagir(self, evenement, humeur):
        montrer(self.c, self.c.dit(evenement, humeur))

    def attendre(self, fonction, bulle=None, evenement=None):
        return attendre(self.c, fonction, bulle, evenement)

    def confirmer(self, titre, detail, danger=False):
        """Scripts, outils MCP qui modifient quelque chose, ajout de serveurs : toujours un oui explicite."""
        con.print(Panel(Text(str(detail)), title=Text(titre, style="bold"), border_style="red" if danger else ACCENT,
                        box=box.ROUNDED, expand=False))
        return demander_oui()

    def sortie(self, texte, ok=True):
        sortie_cmd(texte, ok)

    def xp(self, n):
        if self.c.gagner(n):
            self.reagir("niveau", "fier")


def demander_oui(apprendre=False):
    choix = r"\[o]ui / \[N]on" + (r" / \[a]pprendre" if apprendre else "")  # \[ : crochets affiches tels quels
    try:
        r = con.input(f"[bold]{choix} :[/] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    if apprendre and r in ("a", "apprendre"):
        return "apprendre"
    return r in ("o", "oui", "y", "yes")


def confirmer(cmd):
    """Securite (securite.py) : bloquee = jamais ; dangereuse = oui explicite ; sinon direct (mode normal)
    ou apres confirmation (mode strict, /securite strict)."""
    niveau, raison = securite.analyser(cmd)
    if niveau == "bloque":
        point(Text(f"Bloquée par la sécurité : {raison}. Cette commande ne sera pas exécutée.", style="bold red"), "red")
        return "non"
    if niveau == "danger":
        point(Text(f"Attention : {raison}.", style="bold red"), "red")
    elif ds.lire_config().get("securite", "normal") != "strict":
        return "oui"
    r = demander_oui(apprendre=niveau == "ok")
    return "apprendre" if r == "apprendre" else "oui" if r else "non"


AIDE = Table.grid(padding=(0, 2))
for k, v in [("!<commande>", "exécute une commande PowerShell (contrôlée par la sécurité)"),
                 ("/securite [normal|strict]", "normal : confirme les commandes à risque · strict : confirme tout"),
             ("/neurones", "compétences instantanées"), ("/oublie <nom>", "supprime un neurone"),
             ("/carte", "carte de profil de Deepy (exportée en image)"), ("/anim", "animations on/off"), ("/quota", "tokens Groq du jour et cache"), ("/nom <nom>", "renomme le compagnon"),
             ("@<question>", "le modèle utilise les outils MCP (/mcp)"), ("/reset", "efface la conversation"), ("/historique [n]", "derniers échanges (deepy --reprendre pour continuer)"), ("/clear", "efface l'écran"), ("/quitter", "sortir")]:
    AIDE.add_row(Text(k, style="bold"), Text(v, style=GRIS))
AIDE.add_row(Text("— compétences —", style=ACCENT), Text(""))
for k, (_, v) in competences.COMMANDES.items():
    AIDE.add_row(Text(k, style="bold"), Text(v, style=GRIS))


# ---------- Boucle ----------
def executer_flux(c, q, cmd, neurones, exemples, depuis_modele):
    point(Text.assemble(("PowerShell", "bold"), (f"({cmd})", GRIS)), ACCENT)
    choix = confirmer(cmd)
    if choix == "non":
        montrer(c, c.dit("annule", "content"))
        return
    sortie, ok = ds.lancer(cmd)
    sortie_cmd(sortie, ok)
    if not ok:
        ds.cache_retirer(q)  # une commande qui echoue ne doit pas etre resservie depuis le cache
    c.stats["commandes" if ok else "echecs"] += 1
    if not ok:
        montrer(c, c.dit("echec", "triste"))
        c.sauver()
        return
    monte = c.gagner(3)
    if depuis_modele:
        ds.memoriser(q, cmd, exemples)
    if choix == "apprendre":
        mot = con.input("[grey50]Mot-clé déclencheur (2 mots min, Entrée = ta phrase) :[/] ").strip() or q
        if not securite.apprenable(cmd):
            con.print(Text("  Commande à risque : Deepy ne l'apprend pas en réflexe.", style="red"))
        elif ds.mot_cle_valide(mot):
            neurones.append({"nom": mot, "declencheurs": [mot], "cmd": cmd})
            ds.sauver_neurones(neurones)
            montrer(c, c.dit("apprend", "fier"))
        else:
            con.print(Text("  Mot-clé trop court : il se déclencherait partout. Pas enregistré.", style="red"))
    else:
        montrer(c, c.dit("niveau" if monte else "succes", "fier"))


# ---------- Historique des conversations ----------
SESSION = time.strftime("%Y-%m-%d %H:%M:%S")


def noter(q, action, contenu):
    """Chaque echange est garde dans historique.jsonl (dossier de donnees de Deepy, jamais envoye nulle part)."""
    with open(ds.donnee("historique.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"session": SESSION, "q": q[:2000], "action": action, "contenu": contenu[:4000]},
                           ensure_ascii=False) + "\n")


def lire_historique():
    try:
        with open(ds.donnee("historique.jsonl"), encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
    except (OSError, ValueError):
        return []


def reprendre():
    """Derniers echanges de la session precedente, pour continuer la conversation (deepy --reprendre)."""
    h = lire_historique()
    if not h:
        return []
    derniere = h[-1]["session"]
    tours = []
    for e in [e for e in h if e["session"] == derniere][-ds.HISTO_MAX // 2:]:
        tours += [{"role": "user", "content": e["q"]},
                  {"role": "assistant", "content": json.dumps({"action": e["action"], "contenu": e["contenu"]}, ensure_ascii=False)}]
    return tours


def afficher_historique(n=15):
    h = lire_historique()[-n:]
    if not h:
        return point("Aucun historique pour l'instant.", GRIS)
    t = Table(box=box.SIMPLE, header_style="bold")
    t.add_column("Quand", style=GRIS); t.add_column("Question"); t.add_column("Réponse", style=GRIS)
    for e in h:
        t.add_row(e["session"][5:16], Text(e["q"][:50]), Text(("$ " if e["action"] == "commande" else "") + e["contenu"][:60]))
    con.print(t)


def traiter(c, q, historique, neurones, exemples):
    """Une question : neurone instantane, sinon le modele (reponse ou commande controlee par la securite)."""
    c.stats["questions"] += 1
    t0 = time.time()
    # une question (« c'est quoi la ram ») ne doit pas declencher le neurone « ram »
    n = None if re.search(ds.REPONSE_RE, ds.norm(q).strip()) else ds.trouver_neurone(q, neurones)
    if n:
        point(Text.assemble(("Neurone ", ""), (n["nom"], "bold")), BLEU)
        montrer(c, c.dit("neurone", "fier"))
        noter(q, "commande", n["cmd"])
        executer_flux(c, q, n["cmd"], neurones, exemples, False)
        statut(c, time.time() - t0, "neurone · ")
        return

    r = penser(c, q, historique, exemples)
    if r is None:
        montrer(c, c.dit("annule", "surpris")); return
    action, contenu, duree = r
    historique.extend([{"role": "user", "content": q},
                       {"role": "assistant", "content": json.dumps({"action": action, "contenu": contenu}, ensure_ascii=False)}])
    noter(q, action, contenu)
    if action == "reponse":
        point(Text(contenu))
        c.humeur = "content"
        c.gagner(1)
    elif not ds.commande_valide(contenu):
        point(Text.assemble((f"Je ne lance pas cette commande : {ds.pourquoi_invalide(contenu)}.\n", "red"),
                            (contenu[:300], GRIS)), "red")
        montrer(c, c.dit("invalide", "triste"))
    else:
        executer_flux(c, q, contenu, neurones, exemples, contenu not in ds.APPLI)
    for note in ds.NOTE:  # partie de la demande qu'aucune commande ne peut faire : on le dit franchement
        point(Text(note), GRIS)
    ds.NOTE.clear()
    statut(c, duree)


def main(une_question=None, reprise=False):
    os.system("")
    c = Compagnon()
    con.print(c.vue("Je me réveille…", 0))
    ui = UI(c)
    # 1er lancement : installe Ollama si besoin, choisit et telecharge le modele adapte au PC
    if not competences.modele.configurer(ui):
        con.input("Entrée pour fermer.")
        return
    # cerveau Groq si dispo (cle ou relais) ; sinon on charge le modele local en RAM
    acces = attendre(c, ds.connecter_groq, "Je me connecte à Groq…") if ds.cerveau() != "local" else None
    if not acces and not ds.prechauffer():
        con.input("Entrée pour fermer.")
        return
    neurones, exemples = ds.charger_neurones(), ds.charger_exemples()
    historique = reprendre() if reprise else []
    if une_question:  # deepy "question" : une reponse, puis on rend la main au terminal
        traiter(c, une_question, historique, neurones, exemples)
        c.sauver()
        return
    con.clear()
    accueil(c, neurones, exemples)
    if historique:
        point(f"Conversation reprise ({len(historique) // 2} échange(s) précédents).", GRIS)
    n_vs = c.stats.get("vscode", 0) - c.stats.get("vscode_vu", 0)
    if n_vs > 0:  # appels recus depuis VS Code pendant que la console etait fermee
        c.dit("vscode")
        montrer(c, f"VS Code m'a appelé {n_vs} fois depuis la dernière fois !")
        c.stats["vscode_vu"] = c.stats.get("vscode", 0)
        c.sauver()
    while True:
        con.print()
        try:
            q = con.input(f"[bold {ACCENT}]>[/] ").strip().lstrip("﻿")  # BOM d'un texte colle/redirige.lstrip("Feff")
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q.startswith("@"):  # raccourci : @question = /agent question (outils MCP)
            q = "/agent " + q[1:].strip()
        if q in ("/quitter", "/q", "exit"):
            break
        if q == "/aide":
            con.print(AIDE); continue
        if q == "/clear":
            con.clear(); accueil(c, neurones, exemples); continue
        if q == "/reset":
            historique = []; point("Conversation effacée.", GRIS); continue
        if q in ("/quota", "/quota vider"):
            if q == "/quota vider":
                ds.oublier_cache(); point("Cache de réponses vidé.", GRIS); continue
            qt = ds.quota()
            total = qt["envoyes"] + qt["generes"]
            n = min(10, int(10 * total / ds.QUOTA_JOUR))
            t = Table(box=box.SIMPLE, show_header=False)
            t.add_column(style=GRIS); t.add_column(style="bold")
            t.add_row("Groq aujourd'hui", f"{'█' * n}{'░' * (10 - n)} {total:,} / {ds.QUOTA_JOUR:,} tokens".replace(",", " "))
            t.add_row("Requêtes Groq", str(qt["requetes"]))
            t.add_row("Tokens servis par le cache Groq", f"{qt['en_cache_groq']:,}".replace(",", " "))
            t.add_row("Réponses du cache local (0 token)", str(qt["cache_local"]))
            t.add_row("Réponses mémorisées", str(len(ds._lire_json(ds.FICHIER_CACHE, {}))))
            con.print(t)
            point(f"Au-delà de {int(ds.SEUIL_QUOTA * 100)} % : modèle local jusqu'à demain. /quota vider efface le cache.", GRIS)
            continue
        if q in ("/anim", "/anim on", "/anim off"):
            ANIMATIONS[0] = q != "/anim off" if q != "/anim" else not ANIMATIONS[0]
            ds.maj_config(animations=ANIMATIONS[0])
            point(f"Animations {'activées' if ANIMATIONS[0] else 'désactivées'} ({rx.nb_reactions()} réactions, "
                  f"{len(rx.ANIMS)} animations).", GRIS); continue
        if q.startswith("/historique"):
            n = q[len("/historique"):].strip()
            afficher_historique(int(n) if n.isdigit() else 15); continue
        if q.startswith("/securite"):
            mode = q[len("/securite"):].strip()
            if mode in ("normal", "strict"):
                ds.maj_config(securite=mode)
            actuel = ds.lire_config().get("securite", "normal")
            point(f"Sécurité : {actuel}. Commandes dangereuses bloquées dans tous les cas ; "
                  f"{'toutes les commandes' if actuel == 'strict' else 'les commandes à risque'} demandent ton accord.", GRIS)
            continue
        if q in ("/deepy", "/carte"):
            carte(c); continue
        if q.startswith("/nom "):
            c.nom = q[5:].strip()[:20] or c.nom; c.sauver()
            con.print(c.vue(f"Je m'appelle {c.nom} maintenant !")); continue
        if q == "/neurones":
            t = Table(box=box.SIMPLE, header_style="bold")
            t.add_column("Neurone"); t.add_column("Déclencheur", style=GRIS)
            for n in neurones:
                t.add_row(n["nom"], n.get("regex") or ", ".join(n["declencheurs"]))
            con.print(t); continue
        if q.startswith("/oublie "):
            nom = q[8:].strip()
            ds.oublier_neurone(nom, neurones); point(f"Neurone « {nom} » oublié.", GRIS); continue
        if q.startswith("!"):
            executer_flux(c, q, q[1:].strip(), neurones, exemples, False); continue
        nom_cmd, _, args = q.partition(" ")
        if nom_cmd in competences.COMMANDES:
            try:
                competences.COMMANDES[nom_cmd][0](ui, args.strip())
            except Exception as e:
                point(Text(f"Erreur dans {nom_cmd} : {e}", style="red"), "red")
                montrer(c, c.dit("echec", "triste"))
            continue
        if q.startswith("/"):
            point(Text(f"Commande inconnue : {nom_cmd} (/aide)", style=GRIS), GRIS); continue

        traiter(c, q, historique, neurones, exemples)
    c.humeur = "dort"
    montrer(c, c.dit("aurevoir"))


def arguments():
    """deepy [--reprendre] ["question"]   ·   type log.txt | deepy explique"""
    import sys
    args = [a for a in sys.argv[1:] if a != "--reprendre"]
    question = " ".join(args).strip()
    if not sys.stdin.isatty():  # texte envoye par un pipe : ajoute a la question
        contenu = sys.stdin.read(20000).strip()
        sys.stdin = open("CON" if os.name == "nt" else "/dev/tty", encoding="utf-8")  # pour pouvoir confirmer ensuite
        if contenu:
            question = f"{question or 'explique ce texte'} :\n{contenu[:6000]}"
    return question or None, "--reprendre" in sys.argv


if __name__ == "__main__":
    try:
        une_question, reprise = arguments()
        main(une_question, reprise)
    except Exception:  # jamais de fenetre qui se ferme sans explication
        import traceback
        journal = ds.donnee("erreurs.log")
        with open(journal, "a", encoding="utf-8") as f:
            f.write(time.strftime("\n[%Y-%m-%d %H:%M:%S]\n") + traceback.format_exc())
        con.print(Panel(Text.assemble(("Deepy a planté.\n", "bold red"), (f"Détails : {journal}", GRIS)),
                        border_style="red", box=box.ROUNDED))
