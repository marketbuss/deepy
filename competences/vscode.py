"""Competence VS Code, sans extension :
- Deepy -> VS Code : la commande « code » (ouvrir un fichier a une ligne, un dossier, un diff).
- VS Code -> Deepy : serveur MCP serveur_vscode.py, preconfigure dans le mcp.json utilisateur de VS Code."""
import json, os, shutil, subprocess, sys

ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVEUR = os.path.join(ICI, "serveur_vscode.py")
MCP_VSCODE = os.path.join(os.environ.get("APPDATA", ""), "Code", "User", "mcp.json")


def exe_code():
    return shutil.which("code") or next((p for p in [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd"),
        r"C:\Program Files\Microsoft VS Code\bin\code.cmd"] if os.path.exists(p)), None)


def lancer_code(*args):
    exe = exe_code()
    if not exe:
        raise RuntimeError("VS Code introuvable (commande « code »).")
    subprocess.Popen([exe, *args], shell=exe.endswith(".cmd"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def config_mcp():
    try:
        with open(MCP_VSCODE, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def est_installe():
    c = config_mcp() or {}
    return "deepy" in c.get("servers", {})


def installer_silencieux():
    """Ajoute l'entree « deepy » au mcp.json de VS Code (sauvegarde .bak avant). Renvoie un message."""
    if not os.path.isdir(os.path.dirname(MCP_VSCODE)):
        return "VS Code n'a jamais été lancé sur ce PC (dossier de config absent)."
    if os.path.exists(MCP_VSCODE) and config_mcp() is None:
        return f"{MCP_VSCODE} contient des commentaires ou n'est pas du JSON pur : ajoute Deepy à la main (voir README)."
    c = config_mcp() or {}
    if os.path.exists(MCP_VSCODE):
        shutil.copyfile(MCP_VSCODE, MCP_VSCODE + ".bak")
    serveurs = c.setdefault("servers", {})
    serveurs["deepy"] = {"type": "stdio", "command": sys.executable, "args": [SERVEUR]}
    integres = os.path.join(ICI, "mcp_serveurs")  # les serveurs integres de Deepy, aussi dans VS Code
    for f in sorted(os.listdir(integres)) if os.path.isdir(integres) else []:
        if f.endswith(".py") and f != "base.py":
            serveurs["deepy-" + f[:-3]] = {"type": "stdio", "command": sys.executable, "args": [os.path.join(integres, f)]}
    c.setdefault("inputs", [])
    with open(MCP_VSCODE, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    return "ok"


def vscode(ui, arg):
    """/vscode | installer | retirer | ouvre <fichier[:ligne]> | dossier [chemin] | diff <a> <b>"""
    mots = arg.split(maxsplit=1)
    sous, reste = (mots[0].lower() if mots else ""), (mots[1].strip().strip('"') if len(mots) > 1 else "")
    if sous == "":
        exe = exe_code()
        ui.point(f"VS Code : {'trouvé' if exe else 'introuvable'} · pont MCP : {'installé' if est_installe() else 'non installé'}")
        ui.con.print("[grey50]  /vscode installer       Deepy apparaît dans le chat de VS Code (outils deepy_*)\n"
                     "  /vscode ouvre f.py:12   ouvre un fichier à la ligne 12\n"
                     "  /vscode dossier [chemin] ouvre un dossier (par défaut : le dossier courant)\n"
                     "  /vscode diff a b        compare deux fichiers\n"
                     "  /vscode retirer         enlève Deepy de VS Code[/]")
        return
    if sous == "installer":
        if not ui.confirmer("Connecter Deepy à VS Code ?",
                            f"J'ajoute l'entrée « deepy » dans {MCP_VSCODE} (copie .bak avant).\n"
                            "Dans le chat de VS Code (mode Agent), Deepy répondra et proposera des commandes,\n"
                            "sans jamais les exécuter. VS Code demande ton accord avant chaque appel."):
            return ui.reagir("annule", "content")
        r = installer_silencieux()
        if r != "ok":
            return ui.point(r, "red")
        ui.reagir("vscode", "fier")
        ui.point("Redémarre VS Code, ouvre le chat en mode Agent : les outils « deepy_* » sont disponibles.", "green")
        return
    if sous == "retirer":
        c = config_mcp()
        if c:
            for k in [k for k in c.get("servers", {}) if k == "deepy" or k.startswith("deepy-")]:
                del c["servers"][k]
            with open(MCP_VSCODE, "w", encoding="utf-8") as f:
                json.dump(c, f, ensure_ascii=False, indent=2)
        return ui.point("Deepy retiré de VS Code.", "grey50")
    if sous in ("ouvre", "ouvrir"):
        if not reste:
            return ui.point("Usage : /vscode ouvre <fichier[:ligne]>", "red")
        lancer_code("-r", "-g", reste)
        return ui.point(f"Ouvert dans VS Code : {reste}")
    if sous == "dossier":
        lancer_code(os.path.abspath(reste or "."))
        return ui.point(f"Dossier ouvert dans VS Code : {os.path.abspath(reste or '.')}")
    if sous == "diff":
        a = reste.split()
        if len(a) != 2:
            return ui.point("Usage : /vscode diff <fichier1> <fichier2>", "red")
        lancer_code("-d", *a)
        return ui.point("Comparaison ouverte dans VS Code.")
    ui.point("Sous-commande inconnue. Tape /vscode", "red")


COMMANDES = {"/vscode": (vscode, "VS Code sans extension : /vscode installer | ouvre f:ligne | dossier | diff")}
