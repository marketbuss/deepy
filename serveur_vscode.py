"""Deepy dans VS Code, sans extension : serveur MCP (stdio) que VS Code lance lui-meme.
Preconfigure par « /vscode installer » (ecrit l'entree « deepy » dans le mcp.json utilisateur de VS Code).
Aucun outil n'execute de commande : Deepy repond et PROPOSE, l'utilisateur decide."""
import json, os, sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
PROTO = sys.stdout          # canal MCP : uniquement du JSON
sys.stdout = sys.stderr     # tout print() parasite part dans les logs de VS Code

import deepseek_local as ds  # noqa: E402
import securite  # noqa: E402

OUTILS = [
    {"name": "deepy_demander",
     "description": "Pose une question à Deepy (assistant Windows local). Il répond, ou propose une commande "
                    "PowerShell pour agir sur le PC. La commande n'est JAMAIS exécutée par Deepy : montre-la à "
                    "l'utilisateur, qui décide.",
     "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
    {"name": "deepy_expliquer",
     "description": "Deepy explique un fichier de code ou un extrait (en français, en quelques puces).",
     "inputSchema": {"type": "object", "properties": {
         "chemin": {"type": "string", "description": "Chemin d'un fichier à expliquer (facultatif)."},
         "code": {"type": "string", "description": "Extrait de code à expliquer (facultatif)."}}}},
    {"name": "deepy_neurones",
     "description": "Liste les réflexes instantanés de Deepy (commandes Windows prêtes à l'emploi).",
     "inputSchema": {"type": "object", "properties": {"filtre": {"type": "string"}}}},
    {"name": "deepy_profil",
     "description": "Niveau, stade et statistiques du compagnon Deepy (la baleine).",
     "inputSchema": {"type": "object", "properties": {}}},
]


def compagnon(gain=0):
    """Lit le compagnon et compte l'appel venu de VS Code (Deepy le fete au prochain lancement)."""
    p = ds.donnee("compagnon.json")
    d = ds._lire_json(p, {})
    d.setdefault("stats", {}).setdefault("vscode", 0)
    if gain:
        d["xp"] = d.get("xp", 0) + gain
        d["stats"]["vscode"] += 1
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    return d


def texte_libre(consigne):
    if ds.groq_actif() and ds.connecter_groq():
        try:
            return ds.groq_client().chat([{"role": "user", "content": consigne}], max_tokens=1200).get("content", "")
        except Exception:  # quota, reseau... : repli local
            ds._GROQ_KO = True
    return "- " + ds.generer(consigne, prefixe="- ", longueur=350).strip()


def appeler(nom, a):
    if nom == "deepy_demander":
        q = a.get("question", "").strip()
        n = None if __import__("re").search(ds.REPONSE_RE, ds.norm(q)) else ds.trouver_neurone(q, ds.charger_neurones())
        if n:
            action, contenu = "commande", n["cmd"]
        else:
            if ds.cerveau() != "local":
                ds.connecter_groq()
            action, contenu, _ = ds.repondre(q, [], ds.charger_exemples())
        compagnon(1)
        if action == "commande":
            niveau, raison = securite.analyser(contenu)
            if niveau == "bloque":
                return f"Deepy a refusé de proposer cette commande ({raison})."
            alerte = f" — ATTENTION : {raison}" if niveau == "danger" else ""
            return (f"Commande PowerShell proposée par Deepy{alerte} (NON exécutée, à lancer par l'utilisateur "
                    f"s'il est d'accord) :\n{contenu}")
        return contenu
    if nom == "deepy_expliquer":
        code = a.get("code") or ""
        if a.get("chemin"):
            with open(a["chemin"], encoding="utf-8", errors="replace") as f:
                code = f.read(6000)
        if not code.strip():
            raise ValueError("donne « chemin » ou « code »")
        compagnon(1)
        return texte_libre(f"Explique simplement ce que fait ce code, en 3 à 6 puces en français.\n\n{code}")
    if nom == "deepy_neurones":
        f = ds.norm(a.get("filtre", ""))
        return "\n".join(f"- {n['nom']} : {n['cmd'][:90]}" for n in ds.charger_neurones()
                         if f in ds.norm(n["nom"])) or "(aucun)"
    if nom == "deepy_profil":
        d = compagnon()
        xp = d.get("xp", 0)
        s = d.get("stats", {})
        return (f"{d.get('nom', 'Deepy')} : niveau {xp // 20 + 1}, {xp} XP. Questions : {s.get('questions', 0)}, "
                f"commandes réussies : {s.get('commandes', 0)}, appels depuis VS Code : {s.get('vscode', 0)}. "
                f"Cerveau : {ds.cerveau()}.")
    raise ValueError(f"outil inconnu : {nom}")


def repondre(msg):
    m, i = msg.get("method"), msg.get("id")
    if m == "initialize":
        res = {"protocolVersion": msg.get("params", {}).get("protocolVersion", "2025-06-18"),
               "capabilities": {"tools": {}}, "serverInfo": {"name": "deepy", "version": "1.0"},
               "instructions": "Deepy propose des commandes Windows sans jamais les exécuter."}
    elif m == "tools/list":
        res = {"tools": OUTILS}
    elif m == "tools/call":
        p = msg.get("params", {})
        try:
            res = {"content": [{"type": "text", "text": appeler(p.get("name"), p.get("arguments") or {})}]}
        except Exception as e:
            res = {"content": [{"type": "text", "text": f"Erreur : {e}"}], "isError": True}
    elif m == "ping":
        res = {}
    elif i is None:
        return None  # notification (ex. notifications/initialized) : pas de reponse
    else:
        return {"jsonrpc": "2.0", "id": i, "error": {"code": -32601, "message": f"méthode inconnue : {m}"}}
    return {"jsonrpc": "2.0", "id": i, "result": res}


for ligne in sys.stdin:
    try:
        r = repondre(json.loads(ligne))
    except ValueError:
        continue
    if r is not None:
        PROTO.write(json.dumps(r, ensure_ascii=False) + "\n")
        PROTO.flush()
