"""Banc de test : compare l'ancien mode (texte libre) et le mode entraine (JSON + exemples proches).
Aucune commande n'est executee. Usage : python banc_test.py [base|entraine|tout]"""
import json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deepseek_local as ds

ICI = os.path.dirname(os.path.abspath(__file__))
BANC = json.load(open(os.path.join(ICI, "banc_test.json"), encoding="utf-8"))

ANCIEN_SYSTEME = ("Tu es un assistant sur un PC Windows 10. Reponds en francais, en 1 a 4 phrases. "
                  "Si l'utilisateur demande une action sur le PC, propose UNE commande PowerShell "
                  "entre <cmd> et </cmd>. Sinon reponds simplement.")


def base(q):
    corps = {"model": ds.MODELE, "stream": False, "think": False, "keep_alive": "30m",
             "options": {**ds.OPTIONS, "num_predict": 400},
             "messages": [{"role": "system", "content": ANCIEN_SYSTEME}, {"role": "user", "content": q}]}
    t0 = time.time()
    txt = json.load(ds.ollama("/api/chat", corps))["message"]["content"]
    m = re.search(r"<cmd>(.*?)</cmd>", txt, re.S)
    return ("commande", m.group(1).strip()) if m else ("reponse", txt), time.time() - t0


def entraine(q):
    a, c, d = ds.repondre(q, [], ds.charger_exemples())
    return (a, c), d


def juste(attendu, action, contenu):
    if attendu == "reponse":
        return action == "reponse"
    return action == "commande" and ds.commande_valide(contenu) and any(
        re.search(rf"(?<![\w-]){re.escape(e)}(?![\w-])", contenu, re.I) for e in attendu)


def evaluer(nom, f):
    ok, temps = 0, []
    for q, attendu in BANC:
        (action, contenu), d = f(q)
        bon = juste(attendu, action, contenu)
        ok += bon; temps.append(d)
        print(f"  {'OK ' if bon else 'NON'} {d:5.1f}s  {q[:38]:38} -> {action}: {contenu[:60]!r}")
    print(f"== {nom} : {ok}/{len(BANC)} justes ({100 * ok // len(BANC)} %), "
          f"temps moyen {sum(temps) / len(temps):.1f} s, max {max(temps):.1f} s\n")


if __name__ == "__main__":
    choix = sys.argv[1] if len(sys.argv) > 1 else "tout"
    ds.prechauffer()
    if choix in ("base", "tout"):
        evaluer("BASE (ancien mode)", base)
    if choix in ("entraine", "tout"):
        evaluer("ENTRAINE", entraine)
