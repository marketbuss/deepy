"""Animations et reactions de Deepy (la baleine).
ANIMS : 15 animations ; chaque image = dict(haut=ligne au-dessus, yeux=, decal=decalage, cote=texte a droite, bas=ligne dessous).
PHRASES : reactions par evenement. EVENEMENTS : evenement -> (humeur, animations possibles)."""
import random, time

ANIMS = {
    "jet":        [{"haut": "   .  "}, {"haut": "  ' . "}, {"haut": "   ' ."}, {"haut": "  . ' "}],
    "nage":       [{"decal": d, "bas": "~ ~ ~ ~ ~ ~"[d % 2:] } for d in (0, 1, 2, 3, 2, 1)],
    "saut":       [{"bas": "          "}, {"haut": "    !", "bas": "  \\  /  "}, {"haut": "  ^ ^", "decal": 1, "bas": " ~\\~~/~ "},
                   {"bas": " ~~~~~~~ "}],
    "dodo":       [{"haut": "      z", "yeux": "u"}, {"haut": "     z Z", "yeux": "-"}, {"haut": "   z Z z", "yeux": "u"},
                   {"haut": "  Z     ", "yeux": "-"}],
    "coeur":      [{"haut": "    ♥", "yeux": "^"}, {"haut": "  ♥   ♥", "yeux": "^"}, {"haut": " ♥  ♥  ♥", "yeux": "^"},
                   {"haut": "   ♥ ♥", "yeux": "^"}],
    "etincelles": [{"haut": "  *  .", "yeux": "^"}, {"haut": " .  *  ", "yeux": "^"}, {"haut": "*  .  *", "yeux": "^"},
                   {"haut": " * . * ", "yeux": "^"}],
    "confus":     [{"haut": "    ?", "yeux": "O"}, {"haut": "   ? ?", "yeux": "o"}, {"haut": "  ?  ?", "yeux": "O"},
                   {"haut": "    ¿", "yeux": "o"}],
    "sueur":      [{"cote": " ;", "yeux": "x"}, {"cote": " ;'", "yeux": "-"}, {"cote": "  ;", "yeux": "x"}, {"cote": " ' ;", "yeux": "-"}],
    "fete":       [{"haut": " \\o/  * ", "yeux": "^"}, {"haut": " *  \\o/ ", "yeux": "^"}, {"haut": " ~*~*~*~", "yeux": "^"},
                   {"haut": " * ~ * ~", "yeux": "^"}],
    "tourne":     [{"yeux": "o"}, {"yeux": "O"}, {"yeux": "0"}, {"yeux": "@"}],
    "clin":       [{"yeux": "o"}, {"yeux": "-"}, {"yeux": "o"}, {"yeux": "o"}],
    "bulles":     [{"haut": "    o"}, {"haut": "   o  O"}, {"haut": "  O  o ."}, {"haut": "   .  o"}],
    "radar":      [{"haut": "   ( )"}, {"haut": "  (( ))"}, {"haut": " ((( )))"}, {"haut": "  (( ))"}],
    "code":       [{"haut": "   </>", "yeux": "-"}, {"haut": "  { ; }", "yeux": "-"}, {"haut": "   0101", "yeux": "-"},
                   {"haut": "  ( => )", "yeux": "-"}],
    "musique":    [{"haut": "    ♪", "yeux": "^"}, {"haut": "   ♪ ♫", "yeux": "^"}, {"haut": "  ♫   ♪", "yeux": "^"},
                   {"haut": "    ♫", "yeux": "^"}],
}

PHRASES = {
    "accueil": ["Prêt à plonger !", "On fait quoi aujourd'hui ?", "Je suis réveillé, vas-y.", "Glouglou. Je t'écoute.",
                "Nouvelle session, nouvelles vagues !", "Dis-moi tout.", "Je suis chaud comme l'océan en août."],
    "matin": ["Bonjour ! Un café et on attaque ?", "Matin calme, mer d'huile. On commence ?", "Bien dormi ? Moi j'ai fait des bulles."],
    "soir": ["Bonsoir ! Session du soir, mes préférées.", "La mer est calme ce soir. On code ?", "Encore debout ? Je suis là."],
    "nuit": ["Il est tard… on fait vite et au lit ?", "Mode nocturne activé. Chut, les poissons dorment.",
             "Les vrais codent la nuit. Allez."],
    "reflechit": ["Je réfléchis…", "Je fouille mes neurones…", "Laisse-moi une seconde…", "Je plonge chercher la réponse…",
                  "Ça mouline sous l'eau…", "Hmm, voyons voir…", "Je consulte les abysses…", "Calcul en cours, glouglou…"],
    "cloud": ["Je demande à mon grand cerveau dans le cloud…", "Signal envoyé vers Groq…", "Je sors la tête de l'eau pour capter…"],
    "reponse": ["Voilà !", "J'espère que ça aide.", "C'est ce que je sais.", "Et hop.", "Simple comme une bulle.",
                "Autre chose ?"],
    "neurone": ["Ça, je connais par cœur !", "Réflexe instantané.", "Neurone activé !", "Pas besoin de réfléchir pour ça.",
                "Facile, c'est dans mes nageoires.", "Réponse éclair !"],
    "succes": ["Fait ! +3 XP", "Nickel.", "Bien joué, on avance.", "Mission accomplie !", "Propre.", "Et un de plus !",
               "Ça roule.", "Parfait, comme une vague bien prise."],
    "echec": ["Aïe, ça a raté…", "Oups. Je note pour ne pas recommencer.", "Pas mon meilleur coup.", "Ça a coulé…",
              "Erreur… on retente autrement ?", "Bon, ça arrive même aux baleines."],
    "annule": ["OK, je ne touche à rien.", "Annulé, pas de souci.", "Compris, on laisse tomber.", "Pas de problème, je range.",
               "Ok, j'attends ton prochain ordre."],
    "invalide": ["Je n'ai pas trouvé de vraie commande. Reformule ?", "Là je bloque, dis-le autrement ?",
                 "Je ne suis pas sûr de moi… précise ?", "Cette commande n'existe pas, je préfère ne pas inventer."],
    "apprend": ["Retenu ! Je serai plus rapide la prochaine fois.", "Nouveau neurone !", "C'est gravé dans ma mémoire.",
                "J'ai appris un truc !"],
    "niveau": ["NIVEAU SUPÉRIEUR !", "Je grandis !", "Level up, glouglou !", "Je sens mes nageoires pousser !"],
    "code": ["J'écris le code…", "Je tape avec mes nageoires…", "Compilation mentale en cours…", "Je code, ne me dérange pas…"],
    "code_ok": ["Le script tourne !", "Ça compile et ça marche !", "Code validé.", "Premier essai, premier succès !"],
    "code_ko": ["Ça plante… /corrige ?", "Bug détecté. On le chasse ?", "Le code a pris l'eau."],
    "vscode": ["Coucou depuis VS Code !", "Je suis aussi dans ton éditeur maintenant.", "VS Code m'a appelé !",
               "Connexion à l'éditeur réussie."],
    "mcp": ["J'interroge le serveur…", "Je passe par le tuyau MCP…", "Requête envoyée, j'attends la réponse…"],
    "web": ["La météo arrive…", "Je regarde dehors…", "Je fais un tour sur le web…"],
    "inactif": ["Tu es toujours là ?", "Je fais des bulles en attendant…", "*nage en rond*", "Pssst, j'ai envie de bosser."],
    "aurevoir": ["À plus ! Zzz…", "Bye ! Je retourne au fond.", "À bientôt, glouglou.", "Je pars faire dodo."],
    "danger": ["Part direct.", "Elle part.", "C'est du PowerShell, on y va."],
}

# evenement -> (humeur des yeux, animations jouees)
EVENEMENTS = {
    "accueil": ("content", ["nage", "jet"]), "matin": ("content", ["jet", "musique"]), "soir": ("content", ["nage"]),
    "nuit": ("dort", ["dodo"]), "reflechit": ("reflechit", ["bulles", "jet", "tourne"]), "cloud": ("reflechit", ["radar"]),
    "reponse": ("content", ["clin", "jet"]), "neurone": ("fier", ["etincelles", "saut"]),
    "succes": ("fier", ["fete", "coeur", "saut", "etincelles"]), "echec": ("triste", ["sueur", "confus"]),
    "annule": ("content", ["clin"]), "invalide": ("triste", ["confus"]), "apprend": ("fier", ["etincelles", "coeur"]),
    "niveau": ("fier", ["fete", "saut"]), "code": ("reflechit", ["code"]), "code_ok": ("fier", ["fete", "musique"]),
    "code_ko": ("triste", ["sueur"]), "vscode": ("fier", ["etincelles"]), "mcp": ("reflechit", ["radar"]),
    "web": ("reflechit", ["radar"]), "inactif": ("content", ["nage", "dodo"]), "aurevoir": ("dort", ["dodo"]),
    "danger": ("surpris", ["confus", "sueur"]),
}


def nb_reactions():
    return sum(len(v) for v in PHRASES.values())


def phrase(evenement):
    return random.choice(PHRASES.get(evenement, ["…"]))


def anim(evenement):
    return random.choice(EVENEMENTS.get(evenement, ("content", ["jet"]))[1])


def humeur(evenement):
    return EVENEMENTS.get(evenement, ("content", []))[0]


def salutation():
    h = time.localtime().tm_hour
    return "matin" if 5 <= h < 12 else "soir" if 18 <= h < 23 else "nuit" if h >= 23 or h < 5 else "accueil"
