"""Competence MCP : Deepy se connecte a des serveurs MCP (Model Context Protocol) et laisse le modele
local utiliser leurs outils. Aucune dependance en plus de rich : client stdio JSON-RPC ecrit a la main.

/mcp                          serveurs configures, etat et nombre d'outils
/mcp outils                   detail des outils
/mcp add <nom> <commande...>  ajoute un serveur (stdio)
/mcp retirer <nom>            le supprime
/mcp reload                   relance tous les serveurs
/mcp config                   chemin du fichier mcp.json (format identique a Claude Desktop)
/mcp appeler <srv.outil> {..} appelle un outil a la main
/agent <question>             le modele utilise les outils MCP pour repondre  (raccourci : @question)
"""
import atexit, json, os, re, shlex, shutil, subprocess, sys, threading, urllib.error, urllib.request
from rich.table import Table
from rich.text import Text
from rich import box

ACCENT, GRIS = "#d97757", "grey50"
OLLAMA = "http://localhost:11434"
MAX_TOURS = 6        # allers-retours modele <-> outils au maximum par question
MAX_SORTIE = 6000    # caracteres d'un resultat d'outil renvoyes au modele
CTX = 8192           # contexte demande a Ollama (les descriptions d'outils prennent de la place)
SYSTEME = ("Tu es Deepy, un assistant qui tourne sur le PC de l'utilisateur. Tu disposes d'outils (MCP). "
           "Utilise-les quand ils aident a repondre, un a la fois si les etapes dependent les unes des autres. "
           "Ne devine jamais le contenu d'un fichier ou d'une page : lis-le. Reponds en francais, de facon concise.")
SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)
INTEGRES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_serveurs")


class ErreurMCP(RuntimeError):
    pass


# ---------- Client MCP (stdio, JSON-RPC 2.0, un message JSON par ligne) ----------
class ServeurMCP:
    def __init__(self, nom, cfg, journal):
        self.nom, self.cfg, self.journal = nom, cfg, journal
        self.proc, self.outils, self._err = None, [], None
        self._id, self._attente, self._verrou = 0, {}, threading.Lock()

    @property
    def actif(self):
        return self.proc is not None and self.proc.poll() is None

    def demarrer(self, delai=90):
        if self.actif:
            return
        exe = shutil.which(self.cfg["command"]) or self.cfg["command"]  # npx -> npx.cmd sous Windows
        env = {**os.environ, **{k: str(v) for k, v in (self.cfg.get("env") or {}).items()}}
        try:
            self._err = open(self.journal, "a", encoding="utf-8")
            self.proc = subprocess.Popen([exe, *map(str, self.cfg.get("args") or [])], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=self._err, text=True, encoding="utf-8",
                                         errors="replace", env=env, cwd=self.cfg.get("cwd") or None,
                                         creationflags=SANS_FENETRE)
        except OSError as e:
            raise ErreurMCP(f"lancement impossible ({e})")
        threading.Thread(target=self._lire, args=(self.proc,), daemon=True).start()
        self._requete("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                     "clientInfo": {"name": "Deepy", "version": "1.0"}}, delai)
        self._envoyer({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.outils = self._lister()

    def _lire(self, proc):
        for ligne in proc.stdout:
            try:
                m = json.loads(ligne)
            except ValueError:
                continue  # le serveur a ecrit autre chose que du JSON : on ignore
            if not isinstance(m, dict):
                continue
            if "method" in m and "id" in m:  # le serveur nous interroge (ping...)
                rep = {"jsonrpc": "2.0", "id": m["id"]}
                if m["method"] == "ping":
                    rep["result"] = {}
                else:
                    rep["error"] = {"code": -32601, "message": "non supporte par Deepy"}
                try:
                    self._envoyer(rep)
                except ErreurMCP:
                    pass
            elif "id" in m:
                with self._verrou:
                    slot = self._attente.get(m["id"])
                if slot:
                    slot["m"] = m
                    slot["e"].set()
        with self._verrou:  # processus termine : on reveille tous ceux qui attendent
            for slot in self._attente.values():
                slot["e"].set()

    def _envoyer(self, message):
        try:
            self.proc.stdin.write(json.dumps(message) + "\n")  # ensure_ascii : jamais de retour a la ligne
            self.proc.stdin.flush()
        except (OSError, ValueError, AttributeError):
            raise ErreurMCP("le serveur ne répond plus")

    def _requete(self, methode, params, delai):
        with self._verrou:
            self._id += 1
            i = self._id
            slot = self._attente[i] = {"e": threading.Event(), "m": None}
        try:
            self._envoyer({"jsonrpc": "2.0", "id": i, "method": methode, "params": params})
            if not slot["e"].wait(delai):
                raise ErreurMCP(f"{methode} : délai dépassé ({delai} s)")
        finally:
            with self._verrou:
                self._attente.pop(i, None)
        m = slot["m"]
        if m is None:
            raise ErreurMCP("le serveur s'est arrêté (voir mcp.log)")
        if "error" in m:
            raise ErreurMCP(m["error"].get("message", str(m["error"])))
        return m.get("result") or {}

    def _lister(self):
        outils, curseur = [], None
        while True:
            r = self._requete("tools/list", {"cursor": curseur} if curseur else {}, 30)
            outils += r.get("tools", [])
            curseur = r.get("nextCursor")
            if not curseur:
                return outils

    def appeler(self, outil, arguments, delai=120):
        """Renvoie (texte, ok)."""
        r = self._requete("tools/call", {"name": outil, "arguments": arguments or {}}, delai)
        morceaux = []
        for b in r.get("content") or []:
            if b.get("type") == "text":
                morceaux.append(b.get("text", ""))
            elif b.get("type") == "resource":
                res = b.get("resource") or {}
                morceaux.append(res.get("text") or f"[ressource {res.get('uri', '')}]")
            else:
                morceaux.append(f"[{b.get('type', 'contenu')} non affichable]")
        if not morceaux and r.get("structuredContent"):
            morceaux.append(json.dumps(r["structuredContent"], ensure_ascii=False))
        return "\n".join(morceaux) or "(vide)", not r.get("isError", False)

    def arreter(self):
        p, self.proc = self.proc, None
        if p is not None:
            try:
                p.stdin.close()
            except OSError:
                pass
            if p.poll() is None:
                if os.name == "nt":  # npx lance node en sous-processus : on tue l'arbre entier
                    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True,
                                   creationflags=SANS_FENETRE)
                else:
                    p.terminate()
        if self._err:
            self._err.close()
            self._err = None


# ---------- Gestion des serveurs (mcp.json) ----------
class Gestionnaire:
    def __init__(self, ds):
        self.fichier, self.journal = ds.donnee("mcp.json"), ds.donnee("mcp.log")
        self.serveurs = {}

    def perso(self):
        """Serveurs ajoutes par l'utilisateur (mcp.json, format Claude Desktop)."""
        try:
            with open(self.fichier, encoding="utf-8") as f:
                return json.load(f).get("mcpServers", {})
        except (OSError, ValueError, AttributeError):
            return {}

    def config(self):
        """Serveurs integres (mcp_serveurs/*.py, sans dependance) + ceux de mcp.json, qui gagnent en cas de conflit
        (ex. {"meteo": {"disabled": true}} coupe un serveur integre)."""
        cfg = {os.path.splitext(f)[0]: {"command": sys.executable, "args": [os.path.join(INTEGRES, f)], "integre": True}
               for f in sorted(os.listdir(INTEGRES)) if f.endswith(".py") and f != "base.py"} \
            if os.path.isdir(INTEGRES) else {}
        for nom, c in self.perso().items():
            cfg[nom] = {**cfg.get(nom, {}), **c}
        return cfg

    def sauver(self, cfg):
        perso = {n: {k: v for k, v in c.items() if k != "integre"} for n, c in cfg.items()
                 if not c.get("integre") or c.get("disabled")}
        with open(self.fichier, "w", encoding="utf-8") as f:
            json.dump({"mcpServers": perso}, f, ensure_ascii=False, indent=2)

    def demarrer(self):
        """Lance (en parallele) les serveurs configures pas encore actifs. Renvoie {nom: erreur}."""
        cfg, erreurs, fils = self.config(), {}, []

        def lancer(s):
            try:
                s.demarrer()
            except Exception as e:
                erreurs[s.nom] = str(e)
                s.arreter()
        for nom in list(self.serveurs):
            if nom not in cfg or self.serveurs[nom].cfg != cfg[nom]:  # supprime ou modifie
                self.serveurs.pop(nom).arreter()
        for nom, c in cfg.items():
            if c.get("disabled") or not c.get("command"):
                continue
            s = self.serveurs.setdefault(nom, ServeurMCP(nom, c, self.journal))
            if not s.actif:
                f = threading.Thread(target=lancer, args=(s,))
                f.start()
                fils.append(f)
        for f in fils:
            f.join()
        return erreurs

    def tout_arreter(self):
        for s in self.serveurs.values():
            s.arreter()
        self.serveurs.clear()

    def outils_modele(self):
        """Outils au format Ollama + table nom_expose -> (serveur, outil)."""
        defs, carte = [], {}
        for s in self.serveurs.values():
            if not s.actif:
                continue
            for o in s.outils:
                nom = re.sub(r"[^A-Za-z0-9_-]", "_", f"{s.nom}__{o['name']}")[:64]
                carte[nom] = (s, o)
                defs.append({"type": "function", "function": {
                    "name": nom, "description": (o.get("description") or o["name"])[:600],
                    "parameters": o.get("inputSchema") or {"type": "object", "properties": {}}}})
        return defs, carte


_G = []


def gest(ui):
    if not _G:
        _G.append(Gestionnaire(ui.ds))
        atexit.register(_G[0].tout_arreter)
    return _G[0]


def _decouper(texte):
    """Decoupe une ligne de commande (chemins Windows avec \\ : pas de mode posix)."""
    return [t[1:-1] if len(t) > 1 and t[0] == t[-1] and t[0] in "\"'" else t
            for t in shlex.split(texte, posix=False)]


# ---------- Execution d'un outil (avec permission) ----------
def executer(ui, serveur, outil, args):
    """Demande la permission si l'outil n'est pas en lecture seule, l'appelle, affiche. Renvoie le texte."""
    ann = outil.get("annotations") or {}
    apercu = json.dumps(args, ensure_ascii=False)
    ui.point(Text.assemble(("MCP ", "bold"), (f"{serveur.nom}.{outil['name']}", "bold"),
                           (f"({apercu[:200]})", GRIS)), ACCENT)
    if ann.get("readOnlyHint") is not True:
        detail = f"{(outil.get('description') or '')[:200]}\n\nArguments : {apercu[:500]}\n\nExécuter cet outil ?"
        if not ui.confirmer(f"Outil MCP : {serveur.nom}.{outil['name']}", detail, danger=ann.get("destructiveHint") is True):
            return "Refusé par l'utilisateur."
    try:
        r = ui.attendre(lambda: serveur.appeler(outil["name"], args), f"{serveur.nom}.{outil['name']}…")
    except ErreurMCP as e:
        ui.sortie(str(e), False)
        return f"Erreur : {e}"
    if r is None:
        return "Annulé par l'utilisateur."
    texte, ok = r
    ui.sortie(texte, ok)
    return texte[:MAX_SORTIE] + (f"\n[… tronqué, {len(texte)} caractères au total]" if len(texte) > MAX_SORTIE else "")


# ---------- Agent : le modele local appelle les outils ----------
def _ollama(modele, messages, outils):
    corps = json.dumps({"model": modele, "messages": messages, "tools": outils, "stream": False,
                        "options": {"num_ctx": CTX}}).encode("utf-8")
    req = urllib.request.Request(OLLAMA + "/api/chat", corps, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        if "support tools" in detail:
            raise ErreurMCP(f"{modele} ne gère pas les outils. Choisis un modèle qui les gère "
                            f"(qwen2.5, qwen3, llama3.1, mistral…) avec /modele <nom>.")
        raise ErreurMCP(f"Ollama : {detail}")
    except OSError as e:
        raise ErreurMCP(f"Ollama injoignable : {e}")


def _preparer(ui):
    g = gest(ui)
    erreurs = ui.attendre(g.demarrer, "Je démarre les serveurs MCP…")
    if erreurs is None:
        return None
    for nom, e in erreurs.items():
        ui.point(f"MCP {nom} : {e}", "red")
    return g


INDICES = {  # mots de la question -> mots des outils (un petit modele ne fait pas le lien tout seul)
    "temps": "meteo", "pleut": "meteo", "pluie": "meteo", "temperature": "meteo", "chaud": "meteo", "froid": "meteo",
    "bitcoin": "crypto", "ethereum": "crypto", "btc": "crypto", "eth": "crypto", "solana": "crypto",
    "euro": "devises", "dollar": "devises", "change": "devises", "actu": "actualites", "news": "actualites",
    "info": "actualites", "infos": "actualites", "google": "rechercher", "cherche": "rechercher",
    "recherche": "rechercher", "site": "lire_page", "page": "lire_page", "url": "lire_page",
    "veut": "definition", "signifie": "definition", "sens": "definition", "anglais": "traduire",
    "espagnol": "traduire", "traduis": "traduire", "ferie": "jours_feries", "feries": "jours_feries",
    "copie": "presse_papier", "colle": "presse_papier", "rappelle": "rappel", "rappel": "rappel",
    "minutes": "rappel", "ouvre": "ouvrir", "lance": "lancer_app", "note": "notes", "tache": "notes",
    "commit": "git", "depot": "git", "branche": "git", "ram": "resume_pc", "batterie": "batterie",
    "disque": "disques", "processus": "processus", "calcule": "calculer", "convertis": "convertir",
}


def _mots(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z0-9_]+", t) if len(w) > 2}


def choisir_outils(question, defs, k=6):
    """Garde les k outils les plus proches de la question : plus rapide et beaucoup plus juste pour un petit modele."""
    q = _mots(question)
    q |= {INDICES[w] for w in q if w in INDICES}
    notes = []
    for d in defs:
        f = d["function"]
        nom = set(f["name"].lower().replace("__", "_").split("_")) | {f["name"].split("__")[-1]}
        score = 3 * len(q & nom) + len(q & _mots(f.get("description", "")))
        if score:
            notes.append((score, d))
    notes.sort(key=lambda x: -x[0])
    return [d for _, d in notes[:k]]


def appels_texte(contenu, carte):
    """Rattrapage : le modele a ecrit l'appel en JSON dans le texte au lieu d'un vrai tool_call."""
    m = re.search(r"\{.*\}", contenu or "", re.S)
    if not m:
        return []
    try:
        j = json.loads(m.group(0))
    except ValueError:
        return []
    nom = j.get("name") or j.get("function") or j.get("tool") or ""
    if isinstance(nom, dict):
        nom = nom.get("name", "")
    args = j.get("arguments") or j.get("parameters") or j.get("args") or {}
    if nom not in carte:  # nom approximatif (« internet__meteo ») -> outil reel du meme nom (« web__meteo »)
        court = str(nom).split("__")[-1].split(".")[-1]
        nom = next((n for n in carte if n.split("__")[-1] == court), "")
    return [{"function": {"name": nom, "arguments": args}}] if nom else []


def agent(ui, question):
    """/agent <question> : le modele local utilise les outils MCP pour repondre."""
    if not question:
        return ui.point("Usage : /agent <question>   (ou @<question>)   · /mcp pour voir les outils", GRIS)
    g = _preparer(ui)
    if g is None:
        return ui.reagir("annule", "surpris")
    defs, carte = g.outils_modele()
    if not defs:
        return ui.point("Aucun outil MCP disponible. /mcp pour configurer un serveur.", "red")
    defs = choisir_outils(question, defs)
    if not defs:
        return ui.point("Aucun outil ne correspond à cette question : pose-la sans @ pour une réponse directe.", GRIS)
    messages = [{"role": "system", "content": SYSTEME}, {"role": "user", "content": question}]
    deja = set()
    for _ in range(MAX_TOURS):
        historique = list(messages)
        r = ui.attendre(lambda: _ollama(ui.ds.MODELE, historique, defs), f"Je réfléchis ({len(defs)} outils)…")
        if r is None:
            return ui.reagir("annule", "surpris")
        msg = r.get("message") or {}
        messages.append(msg)
        appels = msg.get("tool_calls") or appels_texte(msg.get("content"), carte)
        if appels and not msg.get("tool_calls"):  # appel ecrit en texte : on le remet au bon format
            msg["content"], msg["tool_calls"] = "", appels
        if not appels:
            ui.point(Text((msg.get("content") or "").strip() or "(pas de réponse)"))
            return ui.xp(2)
        for a in appels:
            f = a.get("function") or {}
            nom, args = f.get("name", ""), f.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            if not isinstance(args, dict):
                args = {}
            cle = (nom, json.dumps(args, sort_keys=True))
            if cle in deja:  # un petit modele repete souvent le meme appel : le resultat est deja affiche
                return ui.xp(2)
            deja.add(cle)
            if nom in carte:
                res = executer(ui, *carte[nom], args)
            else:
                res = f"Outil inconnu : {nom}"
                ui.point(res, "red")
            messages.append({"role": "tool", "tool_name": nom, "content": res})
    ui.point(f"Trop d'étapes ({MAX_TOURS}) : j'arrête. Reformule ou découpe la question.", "red")


# ---------- Catalogue : serveurs MCP connus, installables en une commande ----------
# {MAISON} est remplace par le dossier personnel. "outil" = programme requis (npx vient avec Node.js, uvx avec uv).
CATALOGUE = {
    "memoire": ("npx", ["-y", "@modelcontextprotocol/server-memory"], "mémoire à long terme (graphe de connaissances)"),
    "reflexion": ("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"], "réflexion étape par étape"),
    "disque": ("npx", ["-y", "@modelcontextprotocol/server-filesystem", "{MAISON}"], "lire/écrire tes fichiers (dossier perso)"),
    "navigateur": ("npx", ["-y", "@playwright/mcp@latest"], "pilote un vrai navigateur (Playwright)"),
    "heure": ("uvx", ["mcp-server-time"], "heure et conversion de fuseaux horaires"),
    "fetch": ("uvx", ["mcp-server-fetch"], "télécharge une page web en Markdown"),
}


def catalogue(ui, g):
    t = Table(box=box.SIMPLE, header_style="bold")
    for col in ("Nom", "Rôle", "Requis", "État"):
        t.add_column(col)
    cfg = g.config()
    for nom, (outil, _, role) in CATALOGUE.items():
        dispo = "[green]installé[/]" if nom in cfg else \
            ("[grey50]prêt[/]" if shutil.which(outil) else f"[red]{outil} manquant[/]")
        t.add_row(nom, role, outil, dispo)
    ui.con.print(t)
    ui.con.print(f"[{GRIS}]  Installer : /mcp installer <nom>   (npx : Node.js · uvx : pip install uv)[/]")


def installer(ui, g, nom):
    if nom not in CATALOGUE:
        return ui.point(f"Inconnu dans le catalogue : {nom} (/mcp catalogue)", "red")
    outil, args, role = CATALOGUE[nom]
    if not shutil.which(outil):
        return ui.point(f"{outil} est introuvable : installe {'Node.js' if outil == 'npx' else 'uv (pip install uv)'} d'abord.", "red")
    args = [a.replace("{MAISON}", os.path.expanduser("~")) for a in args]
    return commande(ui, "add " + nom + " " + " ".join([outil, *[f'"{a}"' if " " in a else a for a in args]]))


# ---------- /mcp ----------
AIDE_MCP = ("[grey50]  /mcp add <nom> <commande...>   ex : /mcp add fichiers npx -y @modelcontextprotocol/server-filesystem "
            "C:\\Users\\toi\\Documents\n"
            "                                   ex : /mcp add web uvx mcp-server-fetch\n"
            "  /mcp outils · /mcp retirer <nom> · /mcp reload · /mcp config · /mcp appeler <srv.outil> {json}\n"
            "  /mcp catalogue · /mcp installer <nom>   (memoire, reflexion, disque, navigateur, heure, fetch)\n"
            "  Puis : /agent <question>  ou  @<question>[/]")


def afficher(ui, g, detail=False):
    if not g.config():
        ui.point("Aucun serveur MCP configuré.", GRIS)
        ui.con.print(AIDE_MCP)
        return
    erreurs = ui.attendre(g.demarrer, "Je démarre les serveurs MCP…")
    if erreurs is None:
        return ui.reagir("annule", "surpris")
    t = Table(box=box.SIMPLE, header_style="bold")
    for col in ("Serveur", "État", "Outils", "Commande"):
        t.add_column(col)
    for nom, c in g.config().items():
        s = g.serveurs.get(nom)
        etat = "[grey50]désactivé[/]" if c.get("disabled") else "[green]actif[/]" if s and s.actif else \
            f"[red]erreur : {erreurs.get(nom, 'arrêté')}[/]"
        t.add_row(nom, etat, str(len(s.outils)) if s and s.actif else "-",
                  Text(" ".join([c.get("command", ""), *map(str, c.get("args") or [])])[:60], style=GRIS))
    ui.con.print(t)
    if detail:
        for s in g.serveurs.values():
            for o in s.outils:
                lecture = " (lecture seule)" if (o.get("annotations") or {}).get("readOnlyHint") else ""
                ui.con.print(Text.assemble(("  ", ""), (f"{s.nom}.{o['name']}", "bold"), (lecture, GRIS),
                                           (" — " + (o.get("description") or "").split("\n")[0][:80], GRIS)))


def commande(ui, arg):
    """/mcp [outils|add|retirer|reload|config|appeler]"""
    g = gest(ui)
    sous, _, reste = arg.strip().partition(" ")
    reste = reste.strip()
    if sous in ("", "liste"):
        return afficher(ui, g)
    if sous == "outils":
        return afficher(ui, g, detail=True)
    if sous == "config":
        return ui.point(f"Fichier : {g.fichier}  (format « mcpServers » identique à Claude Desktop ; "
                        f"clés : command, args, env, cwd, disabled)", GRIS)
    if sous == "reload":
        g.tout_arreter()
        return afficher(ui, g)
    if sous in ("retirer", "rm"):
        cfg = g.config()
        if reste not in cfg:
            return ui.point(f"Serveur inconnu : {reste}", "red")
        if cfg[reste].get("integre"):  # serveur fourni avec Deepy : on le desactive (sinon il revient)
            cfg[reste]["disabled"] = True
        else:
            del cfg[reste]
        g.sauver(cfg)
        if reste in g.serveurs:
            g.serveurs.pop(reste).arreter()
        return ui.point(f"Serveur « {reste} » retiré.", GRIS)
    if sous == "add":
        try:
            mots = _decouper(reste)
        except ValueError as e:
            return ui.point(f"Guillemets mal fermés : {e}", "red")
        if len(mots) < 2:
            return ui.con.print(AIDE_MCP)
        nom, cmd = mots[0], mots[1:]
        if not ui.confirmer(f"Ajouter le serveur MCP « {nom} » ?",
                            f"Deepy va lancer : {' '.join(cmd)}\nUn serveur MCP s'exécute sur ton PC avec tes droits : "
                            f"n'ajoute que des serveurs de confiance.", danger=False):
            return ui.reagir("annule", "content")
        cfg = g.config()
        cfg[nom] = {"command": cmd[0], "args": cmd[1:]}
        g.sauver(cfg)
        erreurs = ui.attendre(g.demarrer, f"Je démarre {nom}… (le 1er lancement peut télécharger le serveur)")
        if erreurs is None or nom in erreurs:
            return ui.point(f"Ajouté mais ne démarre pas : {(erreurs or {}).get(nom, 'annulé')} (détails : mcp.log)", "red")
        ui.dire(f"{nom} connecté : {len(g.serveurs[nom].outils)} outils. Essaie /mcp outils puis @ta question.", "fier")
        return ui.xp(3)
    if sous == "appeler":
        cible, _, brut = reste.partition(" ")
        srv, _, outil = cible.partition(".")
        if not _preparer(ui):
            return
        s = g.serveurs.get(srv)
        o = next((x for x in (s.outils if s else []) if x["name"] == outil), None)
        if not o:
            return ui.point(f"Outil introuvable : {cible} (/mcp outils)", "red")
        try:
            args = json.loads(brut) if brut.strip() else {}
        except ValueError as e:
            return ui.point(f"JSON invalide : {e}", "red")
        executer(ui, s, o, args)
        return
    if sous == "catalogue":
        return catalogue(ui, g)
    if sous == "installer":
        return installer(ui, g, reste)
    ui.con.print(AIDE_MCP)


COMMANDES = {"/mcp": (commande, "serveurs MCP : /mcp, /mcp add <nom> <cmd>, /mcp outils, /mcp appeler"),
             "/agent": (agent, "Deepy utilise les outils MCP : /agent <question> (ou @<question>)")}
