"""Banc difficile : questions jamais vues par le banc de base, en 2 parties.
- entrainement : on a le droit d'ajouter des exemples pour les reussir
- controle     : jamais ajoutees aux exemples -> mesure honnete de la generalisation
Part d'un dossier de donnees vierge (comme un nouvel utilisateur). Aucune commande n'est executee.
Usage : python banc_difficile.py [entrainement|controle|tout]"""
import json, os, re, sys, tempfile, time

os.environ["DEEPY_DATA"] = tempfile.mkdtemp(prefix="deepy_banc_")  # avant l'import : donnees neuves
os.environ.setdefault("DS_MODELE", "qwen2.5-coder:1.5b")  # modele choisi pour un PC 8 Go sans GPU
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deepseek_local as ds

ICI = os.path.dirname(os.path.abspath(__file__))
BANC = json.load(open(os.path.join(ICI, "banc_difficile.json"), encoding="utf-8"))


def juste(attendu, action, contenu):
    if attendu == "reponse":
        return action == "reponse"
    return action == "commande" and any(
        re.search(rf"(?<![\w-]){re.escape(e)}(?![\w-])", contenu, re.I) for e in attendu)


def evaluer(partie):
    exemples = ds.charger_exemples()
    ok, temps, ratees = 0, [], []
    for q, attendu in BANC[partie]:
        t0 = time.time()
        action, contenu, _ = ds.repondre_local(q, [], exemples)  # cerveau local (pas Groq)
        d = time.time() - t0
        bon = juste(attendu, action, contenu)
        ok += bon
        temps.append(d)
        if not bon:
            ratees.append(q)
        print(f"  {'OK ' if bon else 'NON'} {d:4.1f}s  {q[:44]:44} -> {action}: {contenu[:70]!r}")
    n = len(BANC[partie])
    print(f"== {partie.upper()} : {ok}/{n} ({100 * ok // n} %), moyenne {sum(temps) / n:.1f} s\n")
    return ok, n, ratees


if __name__ == "__main__":
    choix = sys.argv[1] if len(sys.argv) > 1 else "tout"
    ds.changer_modele = lambda nom: None  # ne touche pas a la config de l'utilisateur
    for partie in (["entrainement", "controle"] if choix == "tout" else [choix]):
        evaluer(partie)
