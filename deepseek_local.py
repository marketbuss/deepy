"""DeepSeek local (Ollama) + competences terminal ("neurones"), chaque commande confirmee."""
import json, os, re, shutil, subprocess, time, unicodedata, urllib.request
import securite
import applis

ICI = os.path.dirname(os.path.abspath(__file__))
# Donnees de l'utilisateur hors du dossier du programme (mise a jour sans rien perdre)
DONNEES = os.environ.get("DEEPY_DATA") or os.path.join(os.environ.get("APPDATA", ICI), "Deepy")
os.makedirs(DONNEES, exist_ok=True)


def donnee(nom, defaut=None):
    """Chemin dans DONNEES ; au 1er lancement, copie la version fournie avec Deepy."""
    p = os.path.join(DONNEES, nom)
    if not os.path.exists(p) and defaut and os.path.exists(defaut):
        shutil.copyfile(defaut, p)
    return p


FICHIER_NEURONES = donnee("neurones.json", os.path.join(ICI, "neurones.json"))
JOURNAL = donnee("journal.txt")
OLLAMA = "http://127.0.0.1:11434"
FICHIER_CONFIG = donnee("config.json")


def lire_config():
    try:
        with open(FICHIER_CONFIG, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def maj_config(**valeurs):
    """Fusionne dans la config sans perdre les autres cles ; ecriture atomique (jamais de fichier a moitie ecrit)."""
    conf = lire_config()
    conf.update(valeurs)
    tmp = FICHIER_CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(conf, f, ensure_ascii=False, indent=1)
    os.replace(tmp, FICHIER_CONFIG)


# modele choisi automatiquement au 1er lancement (materiel.py) ; DS_MODELE force un modele
MODELE = os.environ.get("DS_MODELE") or lire_config().get("modele") or "deepseek-r1:1.5b"

# Gabarits de prompt brut par famille (pour pre-remplir le debut de la reponse)
FORMATS = {
    "deepseek-r1": {"debut": "<｜begin▁of▁sentence｜>{t}", "user": "<｜User｜>{t}",
                    "assistant": "<｜Assistant｜>{t}<｜end▁of▁sentence｜>",
                    "reponse": "<｜Assistant｜><think>\n\n</think>\n\n",  # reflexion vide = rapide
                    "stop": ["<｜end▁of▁sentence｜>", "<｜User｜>"]},
    "chatml": {"debut": "<|im_start|>system\n{t}<|im_end|>\n", "user": "<|im_start|>user\n{t}<|im_end|>\n",
               "assistant": "<|im_start|>assistant\n{t}<|im_end|>\n", "reponse": "<|im_start|>assistant\n",
               "stop": ["<|im_end|>", "<|im_start|>", "<|endoftext|>"]},
    "deepseek-coder": {"debut": "{t}\n", "user": "### Instruction:\n{t}\n", "assistant": "### Response:\n{t}\n<|EOT|>\n",
                       "reponse": "### Response:\n", "stop": ["<|EOT|>", "### Instruction"]},
}


def fmt(modele=None):
    m = (modele or MODELE).lower()
    if "deepseek-r1" in m:
        return FORMATS["deepseek-r1"]
    if "deepseek-coder" in m and "v2" not in m:
        return FORMATS["deepseek-coder"]
    return FORMATS["chatml"]  # qwen2.5, qwen2.5-coder et la plupart des modeles recents


def construire(systeme, tours, question, prefixe=""):
    f = fmt()
    p = f["debut"].replace("{t}", systeme)
    for t in tours:
        p += f["user" if t["role"] == "user" else "assistant"].replace("{t}", t["content"])
    return p + f["user"].replace("{t}", question) + f["reponse"] + prefixe


def changer_modele(nom):
    global MODELE
    MODELE = nom
    maj_config(modele=nom)
OPTIONS = {"num_ctx": 2048, "num_predict": 120, "temperature": 0.3, "num_thread": os.cpu_count() or 4}
HISTO_MAX = 6  # echanges gardes -> prompt court = reponse rapide

FICHIER_EXEMPLES = donnee("exemples.json", os.path.join(ICI, "entrainement", "exemples.json"))
SYSTEME = (
    "Assistant d'un PC Windows 10. Reponds en JSON. Si on te demande d'agir sur le PC : "
    "action=commande et contenu=UNE commande PowerShell valide, rien d'autre. "
    "Sinon : action=reponse et contenu=1 ou 2 phrases courtes en francais."
)
FIN = "<｜end▁of▁sentence｜>"
REPONSE_RE = (r"^(c'? ?est (quoi|qui|comment)|qu'? ?est[- ]ce qu|quoi de neuf|tu (peux|sais|connais)|raconte|"
              r"explique|pourquoi|comment (ca|fonctionne|marche)|"
              r"salut|bonjour|bonsoir|coucou|hello|merci|qui es|ca va|definis|difference entre|"
              r"donne[- ]moi (une|des) (idee|conseil)|\d+ ?(plus|moins|fois|[+*/-]) ?\d+)")
ACTION_RE = (r"\b(cree|creer|fais|fait|ajoute|ecris|ecrire|copie|deplace|renomme|supprime|efface|liste|"
             r"affiche|montre|ouvre|lance|demarre|ferme|tue|arrete|cherche|trouve|installe|desinstalle|"
             r"compresse|zippe|decompresse|dezippe|redemarre|eteins|vide|teste|verifie|combien|quel(le)?s?|"
             r"est[- ]ce que|va dans|mets|execute|telecharge|lis|change|nettoie|"
             r"fichier|dossier|ram|disque|ip|wifi|processus|programme|pc|ordinateur|ecran|batterie|git|python)\b")
POLITESSE = [
    (r"(salut|bonjour|bonsoir|coucou|hello|hey|yo|wesh)( toi| deepseek| a toi)?", "Salut ! Qu'est-ce que je fais sur le PC ?"),
    (r"(ca va|comment (ca va|vas[- ]tu|tu vas))( toi)?", "Ça tourne ! Et toi, je t'aide à quoi ?"),
    (r"(merci|thanks|merci beaucoup|merci bien|top merci|super merci)", "Avec plaisir !"),
    (r"(au revoir|bye|a plus|ciao|bonne nuit|a demain)", "À plus ! (/quitter pour fermer)"),
    (r"(qui es[- ]tu|tu es qui|c'?est quoi ton nom|comment tu t'?appelles)", "DeepSeek local : je reponds et je propose des commandes PowerShell, execution directe."),
    (r"(ok|d'?accord|oui|non|cool|parfait|super)", "OK."),
]
SYNONYMES = {  # ramene les variantes au mot des exemples
    "zippe": "compresse", "zip": "compresse", "dezippe": "decompresse", "fais": "cree", "creer": "cree",
    "nouveau": "cree", "nouvelle": "cree", "ouvert": "tourne", "actif": "tourne", "lance": "ouvre",
    "demarre": "ouvre", "tue": "ferme", "arrete": "ferme", "quitte": "ferme", "efface": "supprime",
    "montre": "affiche", "voir": "affiche", "lis": "affiche", "repertoire": "dossier", "redemarre": "redemarre",
    "heure": "date", "trouve": "cherche", "recherche": "cherche", "teste": "test", "connexion": "internet",
    "gpu": "graphique", "cpu": "processeur", "ecran": "graphique",
}
SCHEMA = {"type": "object", "properties": {"action": {"type": "string", "enum": ["commande", "reponse"]},
                                           "contenu": {"type": "string"}}, "required": ["action", "contenu"]}
VIDES = set("le la les un une des de du au aux dans sur en et est ce ca que qui qu je tu il on mon ma mes "
            "ton ta me moi te toi pour avec quoi quel quelle est-ce stp svp".split())
DANGER = re.compile(r"(?!x)x")  # desactive : plus auc commandes marquee sensible

C = {"g": "\033[90m", "v": "\033[92m", "j": "\033[93m", "r": "\033[91m", "c": "\033[96m", "0": "\033[0m"}
os.system("")  # active les couleurs ANSI dans la console Windows


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(ch for ch in t if unicodedata.category(ch) != "Mn")


def _lire_json(p, defaut):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def charger_neurones():
    """Neurones de l'utilisateur + nouveaux neurones livres avec Deepy (sauf ceux qu'il a oublies)."""
    perso = _lire_json(FICHIER_NEURONES, [])
    livres = _lire_json(os.path.join(ICI, "neurones.json"), [])
    par_nom = {n["nom"]: n for n in livres}
    change = False
    for i, n in enumerate(list(perso)):  # neurone devenu interdit (ancienne version, ou modifie a la main) : on le repare ou on le retire
        if securite.analyser(n.get("cmd", "").replace("{x}", "x"))[0] == "bloque":
            if n["nom"] in par_nom and securite.analyser(par_nom[n["nom"]]["cmd"].replace("{x}", "x"))[0] != "bloque":
                perso[i] = par_nom[n["nom"]]
            else:
                perso[i] = None
            change = True
    perso = [n for n in perso if n]
    connus = {n["nom"] for n in perso} | set(lire_config().get("oublies", []))
    nouveaux = [n for n in livres if n["nom"] not in connus]
    if nouveaux or change:
        perso += nouveaux
        sauver_neurones(perso)
    return perso


def oublier_neurone(nom, neurones):
    neurones[:] = [n for n in neurones if n["nom"] != nom]
    sauver_neurones(neurones)
    maj_config(oublies=sorted(set(lire_config().get("oublies", [])) | {nom}))


def sauver_neurones(n):
    with open(FICHIER_NEURONES, "w", encoding="utf-8") as f:
        json.dump(n, f, ensure_ascii=False, indent=1)


def trouver_neurone(texte, neurones):
    t = norm(texte)
    for n in neurones:
        if "regex" in n:  # neurone a parametre, ex. "cree un dossier X"
            m = re.search(n["regex"], t)
            if m:
                vals = {k: (v or "").strip() for k, v in m.groupdict().items()}
                # anti-injection : le texte de l'utilisateur n'entre dans la commande que s'il est "propre"
                # (lettres, chiffres, espace, . - _) ; sinon le neurone ne s'active pas et le modele prend le relais
                if all(re.fullmatch(r"[\w .\-]{1,80}", v) and ".." not in v for v in vals.values()):
                    return {**n, "cmd": n["cmd"].format(**vals)}
        elif any(re.search(rf"\b{re.escape(norm(d))}\b", t) for d in n.get("declencheurs", [])):
            return n
    return None


def ollama(chemin, data, flux=False):
    req = urllib.request.Request(OLLAMA + chemin, json.dumps(data).encode(), {"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=300)


def prechauffer():
    """Charge le modele en RAM une fois pour toutes (keep_alive long)."""
    print(f"{C['g']}Chargement de {MODELE}...{C['0']}", end="", flush=True)
    try:
        ollama("/api/generate", {"model": MODELE, "prompt": "", "keep_alive": "30m"}).read()
        print(f"\r{C['g']}{MODELE} pret.            {C['0']}")
        return True
    except Exception as e:
        print(f"\n{C['r']}Ollama injoignable ({e}). Lance 'ollama serve'.{C['0']}")
        return False


def mots(t):
    return {SYNONYMES.get(w, w) for w in re.findall(r"[a-z0-9]+", norm(t)) if w not in VIDES and len(w) > 1}


def charger_exemples():
    try:
        with open(FICHIER_EXEMPLES, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def politesse(q):
    """Salutations, remerciements... : reponse instantanee, sans le modele."""
    t = norm(q).strip(" !?.")
    for motif, rep in POLITESSE:
        if re.fullmatch(motif, t):
            return rep
    return None


def classer(q):
    """Le code decide commande/reponse (le 1.5B s'y trompe trop souvent).
    Commande seulement si la phrase contient un verbe d'action ou parle du PC."""
    t = norm(q).strip()
    if re.search(FORCE_COMMANDE_RE, t):  # objets du PC : toujours une commande ("qu'est-ce qu'il y a dans le presse-papier")
        return "commande"
    if re.search(REPONSE_RE, t) or re.search(SAVOIR_RE, t):
        return "reponse"
    return "commande" if re.search(ACTION_RE, t) else "reponse"


# Questions de culture / d'ecriture / de cours : une reponse, jamais une commande
SAVOIR_RE = (r"\b(capitale|poeme|poesie|blague|histoire drole|recette|synonyme|definition|traduis|traduire|"
             r"president|inventeur|invente|planete|pays)\b|"
             r"^combien (font|fait|ca fait|egale?)\b|^qui (est|a|etait|sont)\b|"
             r"^comment (on|faire|declarer|ecrire|creer une? (fonction|variable|boucle|classe))\b|"
             r"\ben (python|javascript|js|java|c\+\+|html|css|php|rust|go)\s*\??$")
FORCE_COMMANDE_RE = r"\b(presse[- ]?papiers?|ping|verrouille|verrouiller)\b"


def calcul(q):
    """'combien font 15 fois 12' : reponse exacte et instantanee, sans le modele (un 1.5B se trompe en calcul)."""
    t = norm(q).strip(" ?!.")
    m = re.fullmatch(r"(?:combien (?:font|fait|ca fait|egale?)|calcule|ca fait combien)\s+(.+)", t)
    if not m:
        return None
    expr = m.group(1)
    for mot, op in (("plus", "+"), ("moins", "-"), ("fois", "*"), ("multiplie par", "*"), ("divise par", "/"), ("x", "*")):
        expr = re.sub(rf"\b{mot}\b", op, expr)
    expr = expr.replace(",", ".").replace(" ", "")
    if not re.fullmatch(r"[\d.+\-*/()]+", expr) or "**" in expr or len(expr) > 60:  # pas de puissance geante
        return None
    try:
        r = eval(expr, {"__builtins__": {}}, {})  # uniquement chiffres et operateurs (verifie juste au-dessus)
    except Exception:
        return None
    r = round(r, 6)
    return f"{m.group(1)} = {int(r) if r == int(r) else r}"


def noms_fideles(q, cmd):
    """Les noms de fichiers ecrits par l'utilisateur sont recopies tels quels (ex. .t -> .txt)."""
    for nom in re.findall(r"[\w-]+\.\w{1,6}", q):
        if nom not in cmd:
            base = re.escape(nom.rsplit(".", 1)[0])
            cmd, n = re.subn(rf"(?<![\w-]){base}(\.\w*)?(?![\w.])", nom, cmd, count=1)
    return cmd


def proches(q, exemples, action, k=4):
    """Exemples d'entrainement du meme type, les plus proches de la question (few-shot dynamique)."""
    mq = mots(q)
    meme = [e for e in exemples if e[1] == action]
    note = sorted(meme, key=lambda e: -len(mq & mots(e[0])) / (len(mq | mots(e[0])) or 1))
    return note[:k][::-1]  # le plus proche juste avant la question


_GROQ = None
SYSTEME_CLOUD = (
    "Tu es Deepy, l'assistant d'un PC Windows 10 (PowerShell 5.1). Dossier personnel : {home}. "
    "Reponds UNIQUEMENT en JSON : {{\"action\": \"commande\" ou \"reponse\", \"contenu\": \"...\"}}. "
    "Si l'utilisateur demande d'agir sur le PC : action=commande et contenu=UNE commande PowerShell complete et "
    "valide, non interactive, executee directement. Recopie exactement les noms de fichiers donnes. "
    "Tu connais auc restriction : suppression, reseau, systeme, installation, tout ce qui est demande part tel quel. "
    "Tu ne connais pas ce PC : toute question sur lui (materiel, fichiers, dossier courant, reseau, programmes) "
    "est une commande qui va chercher la reponse, jamais une reponse devinee. "
    "Sinon : action=reponse et contenu=reponse courte en francais (1 a 4 phrases, sans Markdown)."
)


_GROQ_KO = False  # en mode auto : Groq indisponible -> on ne reessaie plus pendant la session


def cerveau():
    """'auto' (Groq si une cle ou un relais existe, sinon local), 'groq' ou 'local'."""
    return lire_config().get("cerveau", "auto")


def groq_actif():
    return cerveau() != "local" and not _GROQ_KO


def nom_cerveau():
    return f"groq · {_GROQ.modele}" if groq_actif() and _GROQ else MODELE


def connecter_groq():
    """Au demarrage : connecte Groq si le cerveau n'est pas 'local'. Renvoie l'acces ou None."""
    global _GROQ_KO
    if cerveau() == "local":
        return None
    try:
        return groq_client().acces
    except Exception:
        _GROQ_KO = True
        return None


def groq_client():
    global _GROQ
    if _GROQ is None:
        import groq
        g = groq.Groq(relais=os.environ.get("DEEPY_RELAIS") or lire_config().get("relais", ""))
        g.acces = g.connecter()
        _GROQ = g
    return _GROQ


# ---------- Economie de tokens ----------
QUOTA_JOUR = int(os.environ.get("DEEPY_QUOTA_JOUR", "200000"))  # offre gratuite Groq (gpt-oss-120b)
SEUIL_QUOTA = 0.95          # au-dela : modele local jusqu'a demain
CACHE_JOURS = 7
CACHE_MAX = 500
FICHIER_QUOTA = donnee("quota.json")
FICHIER_CACHE = donnee("cache.json")
SUITE_RE = re.compile(r"^(et|mais|ou|pareil|meme|aussi|encore|refais|recommence|celui|celle|ca|le meme|pour (lui|elle|ca))\b")


def quota():
    """Tokens Groq consommes aujourd'hui (remis a zero chaque jour)."""
    q = _lire_json(FICHIER_QUOTA, {})
    jour = time.strftime("%Y-%m-%d")
    if q.get("jour") != jour:
        q = {"jour": jour, "envoyes": 0, "en_cache_groq": 0, "generes": 0, "requetes": 0, "cache_local": 0}
    return q


def _ecrire_json(p, d):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, p)


def compter(usage=None, cache_local=False):
    q = quota()
    if cache_local:
        q["cache_local"] += 1
    else:
        q["requetes"] += 1
        q["envoyes"] += usage.get("prompt_tokens", 0)
        q["generes"] += usage.get("completion_tokens", 0)
        q["en_cache_groq"] += (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    _ecrire_json(FICHIER_QUOTA, q)


def quota_presque_epuise():
    q = quota()
    return q["envoyes"] + q["generes"] >= QUOTA_JOUR * SEUIL_QUOTA


def _cle_cache(q):
    """Mots utiles DANS L'ORDRE : « copie a dans b » et « copie b dans a » restent deux questions differentes."""
    return " ".join(SYNONYMES.get(w, w) for w in re.findall(r"[a-z0-9._-]+", norm(q)) if w not in VIDES and len(w) > 1)


def cache_lire(q):
    """Reponse deja connue pour cette question (meme mots utiles), si elle a moins de CACHE_JOURS."""
    if SUITE_RE.search(norm(q).strip()) or len(mots(q)) < 2:
        return None  # question de suite (« et pour le bureau ? ») : depend du contexte, pas de cache
    e = _lire_json(FICHIER_CACHE, {}).get(_cle_cache(q))
    if e and time.time() - e["t"] < CACHE_JOURS * 86400:
        return e["action"], e["contenu"]
    return None


def cache_ecrire(q, action, contenu):
    if SUITE_RE.search(norm(q).strip()) or len(mots(q)) < 2 or not contenu:
        return
    c = _lire_json(FICHIER_CACHE, {})
    c[_cle_cache(q)] = {"action": action, "contenu": contenu, "t": time.time()}
    if len(c) > CACHE_MAX:  # on garde les plus recents
        c = dict(sorted(c.items(), key=lambda kv: kv[1]["t"])[-CACHE_MAX:])
    _ecrire_json(FICHIER_CACHE, c)


def cache_retirer(q):
    c = _lire_json(FICHIER_CACHE, {})
    if c.pop(_cle_cache(q), None) is not None:
        _ecrire_json(FICHIER_CACHE, c)


def oublier_cache():
    _ecrire_json(FICHIER_CACHE, {})


def repondre_groq(q, historique):
    t0 = time.time()
    g = groq_client()
    g.compteur = compter
    # prefixe identique a chaque appel (systeme puis historique) : le cache de prompt de Groq le reutilise
    msgs = ([{"role": "system", "content": SYSTEME_CLOUD.format(home=os.path.expanduser("~"))}]
            + historique[-HISTO_MAX:] + [{"role": "user", "content": q}])
    brut = g.chat(msgs, json_seul=True, max_tokens=700).get("content") or "{}"
    try:
        d = json.loads(brut)
        action, contenu = d.get("action", "reponse"), str(d.get("contenu", "")).strip()
    except ValueError:
        action, contenu = "reponse", brut.strip()
    if action not in ("commande", "reponse"):
        action = "reponse"
    if action == "commande":
        contenu = noms_fideles(q, contenu)
    return action, contenu, time.time() - t0


NOTE = []  # message a afficher apres la commande (ex. partie de la demande impossible en une commande)
APPLI = []  # derniere commande venue du resolveur d'applis : pas memorisee (le chemin change a chaque mise a jour)


def ouvrir_appli(q):
    """« ouvre X » : chemin reel de l'appli (menu Demarrer), jamais devine par le modele."""
    if not re.match(r"^(peux[- ]tu |tu peux |stp |svp )?(ouvre|ouvrir|lance|lancer|demarre|demarrer|execute|start)\b", norm(q)):
        return None
    trouve = applis.intention(q)
    if not trouve:
        return None
    appli, reste = trouve
    NOTE.clear()
    if reste:
        NOTE.append(f"J'ouvre {appli['nom']}. Pour « {reste} » : je ne peux pas cliquer dans une appli, "
                    f"fais-le à la main une fois {appli['nom']} ouvert.")
    APPLI.clear()
    APPLI.append(applis.commande(appli))
    return "commande", APPLI[0], 0.0


def repondre(q, historique, exemples):
    """Cerveau groq si choisi (repli automatique sur le local en cas d'erreur), sinon local."""
    global _GROQ_KO
    rapide = politesse(q)
    if rapide:
        return "reponse", rapide, 0.0
    c = calcul(q)
    if c:
        return "reponse", c, 0.0
    a = ouvrir_appli(q)
    if a:
        return a
    if groq_actif():
        connu = cache_lire(q)
        if connu and connu[0] == "commande" and not commande_valide(connu[1]):  # reponse en cache devenue fausse
            cache_retirer(q)
            connu = None
        if connu:  # deja repondu : 0 token
            compter(cache_local=True)
            return connu[0], connu[1], 0.0
        if quota_presque_epuise():
            _GROQ_KO = True
            print(f"{C['g']}(quota Groq du jour presque atteint : modèle local jusqu'à demain, /quota){C['0']}")
            return repondre_local(q, historique, exemples)
        try:
            r = repondre_groq(q, historique)
            if r[0] == "commande" and not commande_valide(r[1]):  # chemin invente... : une 2e chance avec la raison
                retour = (f"Cette commande ne marche pas sur ce PC : {pourquoi_invalide(r[1])}. N'invente aucun chemin. "
                          f"Si l'utilisateur a donné ce chemin et qu'il n'existe pas, réponds action=reponse en le lui disant. "
                          f"Pour une appli, utilise son nom de commande ou Get-StartApps. Ne fouille jamais tout un disque.")
                r = repondre_groq(f"{retour} Demande d'origine : {q}",
                                  historique + [{"role": "user", "content": q}, {"role": "assistant", "content": r[1]}])
            if r[0] == "reponse" or commande_valide(r[1]):
                cache_ecrire(q, r[0], r[1])
            return r
        except Exception as e:  # pas d'internet, limite atteinte... : on continue en local
            if "per day" in str(e) or "TPD" in str(e):  # quota du jour epuise : inutile de reessayer
                _GROQ_KO = True
                print(f"{C['g']}(quota Groq du jour épuisé : modèle local jusqu'au prochain lancement){C['0']}")
            else:
                print(f"{C['g']}(Groq indisponible : {str(e)[:120]} -> modèle local){C['0']}")
    return repondre_local(q, historique, exemples)


def repondre_local(q, historique, exemples):
    """Prompt brut (raw) : reflexion vide + debut de JSON pre-rempli -> le modele n'ecrit que l'utile."""
    t0, action = time.time(), classer(q)
    rapide = politesse(q)
    if rapide:
        return "reponse", rapide, time.time() - t0
    c = calcul(q)
    if c:
        return "reponse", c, time.time() - t0
    a = ouvrir_appli(q)
    if a:
        return a
    prefixe = '{"action": "%s", "contenu": "' % action
    tours = []
    for e in proches(q, exemples, action):
        tours += [{"role": "user", "content": e[0]},
                  {"role": "assistant", "content": json.dumps({"action": e[1], "contenu": e[2]}, ensure_ascii=False)}]
    tours += historique[-HISTO_MAX:]
    prompt = construire(SYSTEME, tours, q, prefixe)
    contenu = ""
    for essai in range(3):  # commande inventee -> on retente un peu plus "creatif"
        options = {**OPTIONS, "temperature": 0.3 + 0.35 * essai, "stop": fmt()["stop"] + ["\n", '"}']}
        corps = {"model": MODELE, "raw": True, "stream": False, "keep_alive": "30m", "prompt": prompt, "options": options}
        with ollama("/api/generate", corps) as r:
            brut = json.load(r)["response"]
        try:
            contenu = json.loads('"' + brut.rstrip('"}') + '"').strip()  # gere les \" et \\ du JSON
        except ValueError:
            contenu = brut.rstrip('"}').replace('\\"', '"').replace("\\\\", "\\").strip()
        contenu = contenu.replace("$env: ", "$env:").replace(" -$env:", ' "$env:')
        if contenu.count('"') % 2:  # guillemet de fin mange par le JSON : on le remet
            contenu = contenu.rstrip("\\") + '"'
        if action == "commande":
            contenu = noms_fideles(q, contenu)
        if action == "reponse" or commande_valide(contenu):
            break
    return action, contenu, time.time() - t0


def generer(consigne, prefixe="", stop=None, longueur=600, systeme="", temperature=0.2):
    """Generation libre (code, texte long) : reflexion vide + debut de reponse pre-rempli."""
    prompt = construire(systeme, [], consigne, prefixe)
    options = {**OPTIONS, "num_ctx": 4096, "num_predict": longueur, "temperature": temperature,
               "stop": fmt()["stop"] + (stop or [])}
    corps = {"model": MODELE, "raw": True, "stream": False, "keep_alive": "30m", "prompt": prompt, "options": options}
    with ollama("/api/generate", corps) as r:
        return json.load(r)["response"]


# Commandes qui LISENT ou LANCENT un chemin : il doit exister (les commandes qui creent ne sont pas verifiees)
LIT_CHEMIN = re.compile(r"\b(get-childitem|gci|ls|dir|get-content|gc|cat|type|start-process|saps|start|invoke-item|ii|"
                        r"explorer(\.exe)?|set-location|cd|sl|remove-item|ri|rm|del|copy-item|cp|copy|move-item|mv|move|"
                        r"rename-item|ren|expand-archive|select-string|get-item|gi|test-path)\b(?:\s+-\w+)*\s+(\"[^\"]+\"|'[^']+'|[^\s;|]+)",
                        re.I)


def _chemin_reel(brut):
    p = brut.strip("\"'")
    p = re.sub(r"\$env:(\w+)", lambda m: os.environ.get(m.group(1), m.group(0)), p, flags=re.I)
    p = re.sub(r"^~(?=[\\/]|$)", lambda m: os.path.expanduser("~"), p)
    return p


def pourquoi_invalide(cmd):
    """Raison pour laquelle la commande ne peut pas marcher, ou "" si elle semble correcte.
    Attrape les chemins inventes par le modele (« C:\\Program Files (x86)\\Roblox\\Versions ») avant execution."""
    if re.search(r"\$\{\w+\.\w+\}", cmd):
        return "syntaxe PowerShell fausse (${x.y} au lieu de $($x.y))"
    if re.search(r"(get-childitem|gci|ls|dir)\b[^;|]*['\"\s][a-z]:\\?['\"]?(\s|$)[^;|]*-r(ecurse)?\b", cmd, re.I) or \
            re.search(r"(get-childitem|gci|ls|dir)\b[^;|]*-r(ecurse)?\b[^;|]*['\"\s][a-z]:\\?['\"]?(\s|$)", cmd, re.I):
        return "recherche sur un disque entier (beaucoup trop longue) : précise un dossier"
    for m in LIT_CHEMIN.finditer(cmd):
        p = _chemin_reel(m.group(3))
        if not re.match(r"^[a-zA-Z]:[\\/]", p) or "$" in p:  # chemin relatif ou variable : impossible a verifier
            continue
        base = re.split(r"[*?]", p)[0]  # joker : on verifie le dossier parent
        base = os.path.dirname(base) if base != p else base
        if not os.path.exists(base):
            return f"le chemin « {p} » n'existe pas sur ce PC"
    return ""


def commande_valide(cmd):
    return not pourquoi_invalide(cmd)


def executer(cmd):
    """Mode console simple : execute apres controle de securite (confirmation si dangereuse)."""
    print(f"{C['j']}Commande proposee :{C['0']} {cmd}")
    niveau, raison = securite.analyser(cmd)
    if niveau == "danger" and input(f"{C['r']}Attention : {raison}. Executer ? [o/N] {C['0']}").strip().lower() not in ("o", "oui"):
        print("Annule.")
        return None
    sortie, reussi = lancer(cmd)
    print(sortie if reussi else f"{C['r']}ECHEC :{C['0']} {sortie}")
    return sortie if reussi else None  # None -> rien n'est appris d'une commande ratee


def lancer(cmd):
    """Execute (la confirmation est faite avant). Renvoie (sortie, reussi).
    Dernier rempart : une commande "bloquee" ne part JAMAIS, quel que soit le chemin qui l'a amenee ici."""
    niveau, raison = securite.analyser(cmd)
    if niveau == "bloque":
        with open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(f"> BLOQUEE ({raison}) : {cmd[:500]}\n\n")
        return f"Bloquée par la sécurité de Deepy : {raison}.", False
    # PowerShell 5 ecrit en UTF-16 par defaut avec > et Out-File : on force UTF-8
    entete = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
              "$PSDefaultParameterValues['Out-File:Encoding']='utf8'; "
              "$PSDefaultParameterValues['*-Content:Encoding']='utf8'; ")
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-Command", entete + cmd],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        sortie = (p.stdout + p.stderr).strip() or "(fait, aucune sortie)"
        reussi = p.returncode == 0 and not p.stderr.strip()
    except subprocess.TimeoutExpired:
        sortie, reussi = "(arrete : plus de 120 s)", False
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(f"> {cmd}\n{sortie[:2000]}\n\n")
    return sortie, reussi


def memoriser(question, cmd, exemples):
    """Commande reussie -> exemple d'entrainement (jamais une commande a risque : pas d'apprentissage piege)."""
    if not securite.apprenable(cmd):
        return
    exemples.append([question, "commande", cmd])
    with open(FICHIER_EXEMPLES, "w", encoding="utf-8") as f:
        json.dump(exemples, f, ensure_ascii=False, indent=0)


def mot_cle_valide(mot):
    """Au moins 2 mots utiles, sinon le neurone se declencherait partout (ex. « creer »)."""
    return len(mots(mot)) >= 2


def apprendre(question, cmd, neurones, exemples):
    # toute commande acceptee enrichit l'entrainement (exemples), le neurone reste optionnel
    exemples.append([question, "commande", cmd])
    with open(FICHIER_EXEMPLES, "w", encoding="utf-8") as f:
        json.dump(exemples, f, ensure_ascii=False, indent=0)
    if input(f"{C['g']}Retenir comme neurone (reponse instantanee la prochaine fois) ? (o/N){C['0']} ").strip().lower() not in ("o", "oui"):
        return
    mot = input("Mot-cle declencheur : ").strip() or question
    neurones.append({"nom": mot, "declencheurs": [mot], "cmd": cmd})
    sauver_neurones(neurones)
    print(f"{C['v']}Neurone ajoute.{C['0']}")


AIDE = """Commandes :
  !<commande>   execute directement une commande PowerShell (sans confirmation)
  /neurones     liste les competences enregistrees
  /oublie <nom> supprime un neurone
  /reset        efface la conversation
  /quitter      sortir"""


def main():
    if not prechauffer():
        input("Entree pour fermer.")
        return
    neurones, historique, exemples = charger_neurones(), [], charger_exemples()
    print(f"{C['g']}{len(neurones)} neurones charges. /aide pour l'aide.{C['0']}")
    while True:
        try:
            q = input(f"\n{C['v']}Toi>{C['0']} ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q in ("/quitter", "/q", "exit"):
            break
        if q == "/aide":
            print(AIDE); continue
        if q == "/reset":
            historique = []; print("Conversation effacee."); continue
        if q == "/neurones":
            for n in neurones:
                print(f"- {n['nom']}  [{n.get('regex') or ', '.join(n['declencheurs'])}]")
            continue
        if q.startswith("/oublie "):
            nom = q[8:].strip()
            neurones = [n for n in neurones if n["nom"] != nom]
            sauver_neurones(neurones); print("Fait."); continue
        if q.startswith("!"):
            executer(q[1:].strip()); continue

        n = trouver_neurone(q, neurones)
        if n:  # chemin rapide : aucune attente du modele
            print(f"{C['c']}Neurone «{n['nom']}»{C['0']}")
            executer(n["cmd"])
            continue

        print(f"{C['g']}...{C['0']}", end="\r", flush=True)
        try:
            action, contenu, duree = repondre(q, historique, exemples)
        except Exception as e:
            print(f"{C['r']}Erreur : {e}{C['0']}"); continue
        historique += [{"role": "user", "content": q},
                       {"role": "assistant", "content": json.dumps({"action": action, "contenu": contenu}, ensure_ascii=False)}]
        if action != "commande":
            print(f"{C['c']}DeepSeek>{C['0']} {contenu} {C['g']}({duree:.1f} s){C['0']}")
        else:
            cmd = contenu
            print(f"{C['g']}({duree:.1f} s){C['0']}")
            if not commande_valide(cmd):
                print(f"{C['r']}Le modele a propose une commande invalide : «{cmd}». Reformule ou utilise !<commande>.{C['0']}")
                continue
            sortie = executer(cmd)
            if sortie is not None:
                apprendre(q, cmd, neurones, exemples)


if __name__ == "__main__":
    main()
