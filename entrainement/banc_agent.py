"""Banc de l'agent MCP (@question) : le modele appelle-t-il le bon outil ?
Les outils qui modifient quelque chose (rappel, presse-papier, ouvrir...) sont simules : rien n'est execute.
Usage : python banc_agent.py"""
import os, sys, tempfile, time

os.environ["DEEPY_DATA"] = tempfile.mkdtemp(prefix="deepy_agent_")
os.environ.setdefault("DS_MODELE", "qwen2.5-coder:1.5b")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deepseek_local as ds
from competences import outils_mcp as om

BANC = [
    ("quel temps fait-il a Lyon ?", "meteo"),
    ("combien vaut le bitcoin en euros ?", "crypto"),
    ("quelles sont les actus sur la formule 1 ?", "actualites"),
    ("traduis 'see you tomorrow' en francais", "traduire"),
    ("que veut dire le mot procrastiner ?", "definition"),
    ("cherche sur internet le prix d'un raspberry pi 5", "rechercher"),
    ("rappelle-moi dans 20 minutes de sortir le linge", "rappel"),
    ("combien de batterie il me reste ?", "batterie"),
    ("convertis 10 miles en km", "convertir"),
    ("quels sont les jours feries en belgique ?", "jours_feries"),
    ("ajoute une note : acheter du pain", "ajouter"),
    ("resume la page https://example.com", "lire_page"),
]


class UI:
    def __init__(self):
        self.ds, self.con = ds, self

    def print(self, *a, **k): pass
    def print_json(self, t): pass
    def point(self, t, style="", markup=False): pass
    def attendre(self, f, *a, **k): return f()
    def confirmer(self, *a, **k): return True
    def sortie(self, t, ok=True): pass
    def reagir(self, *a): pass
    def dire(self, *a): pass
    def xp(self, n): pass


appeles = []
_vrai = om.executer


def executer(ui, serveur, outil, args):
    appeles.append(outil["name"])
    if (outil.get("annotations") or {}).get("readOnlyHint"):
        return _vrai(ui, serveur, outil, args)
    return "OK (simulé pendant le banc)."


om.executer = executer

if __name__ == "__main__":
    ui = UI()
    om.gest(ui).demarrer()
    ok, temps = 0, []
    for q, attendu in BANC:
        appeles.clear()
        t0 = time.time()
        try:
            om.agent(ui, q)
        except Exception as e:
            appeles.append(f"ERREUR {e}")
        d = time.time() - t0
        bon = attendu in appeles
        ok += bon
        temps.append(d)
        print(f"  {'OK ' if bon else 'NON'} {d:5.1f}s  {q[:46]:46} -> {appeles or '(aucun outil)'}")
    print(f"== AGENT : {ok}/{len(BANC)} ({100 * ok // len(BANC)} %), moyenne {sum(temps) / len(temps):.1f} s")
