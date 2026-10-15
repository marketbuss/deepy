"""Ouvrir une application sans laisser le modele deviner son chemin (il l'invente : « Program Files (x86)\\Roblox »...).
Source de verite : la liste des applis du menu Demarrer fournie par Windows (Get-StartApps), applis classiques et Store.
Lancement : Start-Process "shell:AppsFolder\\<AppID>" (meme mecanisme que le menu Demarrer)."""
import difflib, json, os, re, subprocess, time, unicodedata

CACHE_S = 3600
SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_cache = {"t": 0, "applis": []}
# mots francais -> nom d'appli Windows (quand le nom affiche est different)
ALIAS = {"navigateur": "microsoft edge", "edge": "microsoft edge", "parametres": "parametres", "reglages": "parametres",
         "word": "word", "excel": "excel", "powerpoint": "powerpoint", "vscode": "visual studio code",
         "vs code": "visual studio code", "explorateur": "explorateur de fichiers", "gestionnaire des taches": "gestionnaire des taches",
         "camera": "camera", "store": "microsoft store", "terminal": "terminal", "invite de commande": "invite de commandes"}
VIDES = {"le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "moi", "mon", "ma", "mes", "app", "appli", "application",
         "logiciel", "programme", "jeu"}
INTENTION = re.compile(r"^(?:peux[- ]tu |tu peux |stp |svp )?(?:ouvre|ouvrir|lance|lancer|demarre|demarrer|execute|start)\s+(.+)$")
SUITE = re.compile(r"\s+(?:et|puis|ensuite|pour|afin de)\s+|\s*[,;]\s*")


def norm(t):
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9+#.]+", " ", t).strip()


def mots(t):
    return [w for w in norm(t).split() if w not in VIDES]


def lister(forcer=False):
    """Applis du menu Demarrer [{"nom", "id"}], mises en cache 1 h."""
    if not forcer and _cache["applis"] and time.time() - _cache["t"] < CACHE_S:
        return _cache["applis"]
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, creationflags=SANS_FENETRE)
        brut = json.loads(r.stdout or "[]")
        brut = [brut] if isinstance(brut, dict) else brut
        applis = [{"nom": a["Name"], "id": a["AppID"]} for a in brut
                  if a.get("Name") and a.get("AppID") and not re.search(r'["`$\r\n]', a["AppID"])]  # id sur pour une commande
    except (OSError, ValueError, subprocess.TimeoutExpired):
        applis = []
    if applis:
        _cache.update(t=time.time(), applis=applis)
    return applis


def score(demande, nom):
    d, n = mots(demande), mots(nom)
    if not d or not n:
        return 0
    if d == n:
        return 100
    # « roblox studio » dans « Roblox Studio » ; prefixe tolere seulement s'il manque 1-2 lettres (« word » != « wordpad »)
    if all(any(w == x or (len(w) > 3 and x.startswith(w) and len(x) - len(w) <= 2) for x in n) for w in d):
        return 90 - 3 * (len(n) - len(d))
    if all(w in n for w in d[:1]) and len(d) == 1 and len(n) <= 3:  # « spotify » -> « Spotify Premium »
        return 70
    r = difflib.SequenceMatcher(None, " ".join(d), " ".join(n)).ratio()  # fautes de frappe : « robox studio »
    return int(r * 80) if r >= 0.85 else 0


def trouver(demande):
    demande = ALIAS.get(norm(demande), demande)
    meilleur = max(((score(demande, a["nom"]), a) for a in lister()), key=lambda x: x[0], default=(0, None))
    if meilleur[0] < 70:  # la liste peut dater : nouvelle appli installee depuis moins d'une heure
        meilleur = max(((score(demande, a["nom"]), a) for a in lister(forcer=True)), key=lambda x: x[0], default=(0, None))
    return meilleur[1] if meilleur[0] >= 70 else None


def intention(question):
    """« ouvre roblox studio et cree une place » -> (appli trouvee, "cree une place") ; None si ce n'est pas une appli connue."""
    m = INTENTION.match(norm(question))
    if not m:
        return None
    morceaux = SUITE.split(m.group(1), maxsplit=1)
    cible, reste = morceaux[0].strip(), (morceaux[1].strip() if len(morceaux) > 1 else "")
    if not cible or re.match(r"^(https?|www)|\.(com|fr|be|net|org|io)\b|^(le |la )?(dossier|fichier)\b", cible):
        return None  # sites et fichiers : pas des applis
    a = trouver(cible)
    return (a, reste) if a else None


def commande(appli):
    if os.path.isfile(appli["id"]):  # appli classique dont l'id est le chemin de l'exe (ex. Roblox Studio)
        return f'Start-Process "{appli["id"]}" -WorkingDirectory "{os.path.dirname(appli["id"])}"'
    return f'Start-Process "shell:AppsFolder\\{appli["id"]}"'
