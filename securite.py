"""Securite de Deepy : chaque commande PowerShell est analysee AVANT execution.

- "bloque" : jamais executee, meme si on confirme (destruction du systeme, desactivation des protections,
             code telecharge puis execute, commandes obfusquees : ce qu'un petit modele ou une page piegee
             pourrait produire, jamais ce qu'un utilisateur demande normalement a Deepy).
- "danger" : executee seulement apres un "oui" explicite (suppression, extinction, registre, services...).
- "ok"     : sans risque, executee directement (mode normal) ou apres confirmation (mode strict).

Les regles s'appliquent a toutes les sources : modele local, Groq, neurones appris, cache, et commandes tapees avec !.
"""
import re

# Toujours refuse. (motif, raison)
BLOQUE = [
    (r"\b(invoke-expression|iex)\b", "exécution de code dynamique (Invoke-Expression)"),
    (r"\[scriptblock\]|scriptblock\]::create|\badd-type\b|\[(system\.)?reflection\.assembly\]|\bnew-object\b[^;|]*\bcomobject\b",
     "construction de code à la volée"),
    (r"(^|[;|({\s])[&.]\s*[(\[$'\"]|\b(gcm|get-command|gal|get-alias)\b[^;|]*\*", "appel indirect de commande (obfuscation)"),
    (r"frombase64string|-e(nc(odedcommand)?)?\s+[a-z0-9+/=]{16,}", "commande encodée / cachée"),
    (r"`(?![ntr0])[a-z]", "commande obfusquée (accents graves dans les mots)"),  # `n `t `r `0 = retours/tabs legitimes
    (r"\b(downloadstring|downloadfile|net\.webclient|start-bitstransfer)\b.*\|\s*(&|\.)", "téléchargement puis exécution"),
    (r"(iwr|irm|invoke-webrequest|invoke-restmethod|curl|wget)\b[^|;]*\|\s*(&|\.|powershell|pwsh|cmd)", "téléchargement puis exécution"),
    (r"\bformat(-volume)?\b\s+([a-z]:|-driveletter)|\bdiskpart\b|\bclear-disk\b|\binitialize-disk\b", "formatage de disque"),
    (r"\b(bcdedit|bootrec|vssadmin|wbadmin)\b", "démarrage / sauvegardes Windows"),
    (r"\bcipher\b\s+/w|\bsdelete\b", "effacement irrécupérable"),
    (r"\b(wevtutil\s+cl|clear-eventlog)\b", "effacement des journaux Windows"),
    (r"set-mppreference\b.*-disable|add-mppreference\b.*-exclusion|\bdisable-windowsoptionalfeature\b.*defender",
     "désactivation de l'antivirus"),
    (r"netsh\s+(adv)?firewall\b.*\b(off|disable)|set-netfirewallprofile\b.*-enabled\s+(false|0)", "désactivation du pare-feu"),
    (r"\b(takeown|icacls)\b[^;|]*\\windows\b", "droits sur les fichiers système"),
    (r"\breg(\.exe)?\s+delete\s+hk(lm|ey_local_machine)|remove-item(property)?\b[^;|]*hklm:", "suppression dans le registre système"),
    (r"\b(remove-item|ri|rm|rmdir|rd|del|erase)\b[^;|]*['\"\s]([a-z]:\\?(windows|program files( \(x86\))?|programdata|users)?['\"\\]?)(\s|$|['\"])",
     "suppression d'un disque ou d'un dossier système"),
    (r"\b(remove-item|ri|rm|rmdir|rd|del|erase)\b[^;|]*(\$env:(systemroot|windir|programfiles|userprofile)['\"]?(\s|$))",
     "suppression d'un dossier système ou du dossier personnel entier"),
    (r"\bnet\s+user\b.*\s/add|\bnew-localuser\b|\bnet\s+localgroup\s+administrat|add-localgroupmember\b.*admin",
     "création de compte / ajout d'administrateur"),
    (r"set-executionpolicy\b.*\b(unrestricted|bypass)\b.*-scope\s+localmachine", "politique d'exécution de la machine"),
]

# Demande un "oui" explicite. (motif, raison)
DANGER = [
    (r"\b(remove-item|ri|rm|rmdir|rd|del|erase|clear-content|clear-recyclebin)\b", "supprime des fichiers"),
    (r"\b(stop-computer|restart-computer|shutdown(\.exe)?\s+/[srlhpg])\b|logoff\b", "éteint ou redémarre le PC"),
    (r"\b(stop-process|spps|kill|taskkill)\b", "ferme des programmes"),
    (r"\b(set-itemproperty|new-itemproperty|remove-itemproperty|reg(\.exe)?\s+(add|delete|import))\b|"
     r"\b(new-item|remove-item|set-item)\b[^;|]*\bhk(lm|cu|ey_)", "modifie le registre"),  # Get-ItemProperty (lecture) : ok
    (r"\b(stop-service|set-service|remove-service|sc(\.exe)?\s+(stop|delete|config))\b", "modifie des services"),
    (r"\b(uninstall-package|winget\s+uninstall|pip\s+uninstall|msiexec\b.*/x)\b", "désinstalle un logiciel"),
    (r"\b(winget|choco|scoop)\s+install|\bpip3?\s+install|\bnpm\s+(i|install)\s+-g", "installe un logiciel"),
    (r"(invoke-webrequest|iwr|curl|wget|start-bitstransfer)\b.*(-outfile|-o\s|>)", "télécharge un fichier"),
    (r"-verb\s+runas|\bsudo\b", "demande les droits administrateur"),
    (r"\b(schtasks|register-scheduledtask|new-scheduledtask)\b", "programme une tâche automatique"),
    (r"\bset-executionpolicy\b", "change la politique d'exécution"),
    (r"\b(move-item|mi|move)\b[^;|]*\b(windows|system32|program files)\b", "déplace des fichiers système"),
    (r"\b(set-content|out-file|add-content)\b[^;|]*\.(ps1|bat|cmd|vbs|exe|dll|reg|lnk)\b|>\s*\S+\.(ps1|bat|cmd|vbs|reg)\b",
     "écrit un script ou un exécutable"),
    (r"\b(new-item|set-content|add-content|copy-item|move-item|out-file|set-itemproperty|new-itemproperty|reg(\.exe)?\s+add)\b"
     r"[^;|]*(\\startup\b|\\currentversion\\run)", "ajoute un programme au démarrage de Windows"),
    (r"\b(disable|enable)-(netadapter|pnpdevice|computerrestore)\b|\bnetsh\b.*\bset\b", "modifie le réseau ou le matériel"),
]


def analyser(cmd):
    """Renvoie (niveau, raison) avec niveau in {"bloque", "danger", "ok"}."""
    if not cmd or not cmd.strip():
        return "bloque", "commande vide"
    t = cmd.lower().replace("\u2013", "-").replace("\u2014", "-")  # tirets longs -> tirets
    if len(t) > 2000:
        return "bloque", "commande anormalement longue"
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\u200b-\u200f\u202a-\u202e\u2066-\u2069]", cmd):
        return "bloque", "caractères invisibles ou de contrôle"
    for motif, raison in BLOQUE:
        if re.search(motif, t):
            return "bloque", raison
    for motif, raison in DANGER:
        if re.search(motif, t):
            return "danger", raison
    return "ok", ""


def apprenable(cmd):
    """Seules les commandes sans risque peuvent devenir des exemples ou des neurones."""
    return analyser(cmd)[0] == "ok"
