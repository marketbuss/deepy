"""Serveur MCP « outils » : calcul sur, conversions d'unites, mots de passe, dates."""
import ast, datetime, math, operator, secrets, string
from base import Serveur

srv = Serveur("outils", "Calculatrice sûre, conversions d'unités, mots de passe, calculs de dates.")

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
       ast.Pow: operator.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv, ast.USub: operator.neg}
FONCTIONS = {n: getattr(math, n) for n in ("sqrt", "sin", "cos", "tan", "log", "log10", "exp", "floor", "ceil")}
FONCTIONS.update(abs=abs, round=round, pi=math.pi, e=math.e)


def evaluer(n):
    """Evalue seulement des nombres, operateurs et fonctions math : jamais de code arbitraire."""
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
        return n.value
    if isinstance(n, ast.BinOp) and type(n.op) in OPS:
        if isinstance(n.op, ast.Pow) and abs(evaluer(n.right)) > 1000:
            raise ValueError("puissance trop grande")
        return OPS[type(n.op)](evaluer(n.left), evaluer(n.right))
    if isinstance(n, ast.UnaryOp) and type(n.op) in OPS:
        return OPS[type(n.op)](evaluer(n.operand))
    if isinstance(n, ast.Name) and n.id in FONCTIONS and not callable(FONCTIONS[n.id]):
        return FONCTIONS[n.id]
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and callable(FONCTIONS.get(n.func.id)):
        return FONCTIONS[n.func.id](*[evaluer(a) for a in n.args])
    raise ValueError("expression non autorisée")


@srv.lecture
def calculer(expression: str) -> str:
    """Calcule une expression (+ - * / ** %, sqrt, sin, log, pi…). Ex : '(12*7+3)/2' ou 'sqrt(2)*pi'."""
    r = evaluer(ast.parse(expression.replace(",", ".").replace("^", "**"), mode="eval").body)
    return f"{expression} = {round(r, 10)}"


UNITES = {  # vers l'unite de base de chaque famille
    "longueur": {"mm": .001, "cm": .01, "m": 1, "km": 1000, "in": .0254, "pouce": .0254, "ft": .3048, "pied": .3048,
                 "mi": 1609.344, "mile": 1609.344},
    "masse": {"mg": 1e-6, "g": .001, "kg": 1, "t": 1000, "lb": .45359237, "livre": .45359237, "oz": .028349523125},
    "volume": {"ml": .001, "cl": .01, "l": 1, "m3": 1000, "gal": 3.785411784},
    "vitesse": {"m/s": 1, "km/h": 1 / 3.6, "mph": .44704, "noeud": .514444},
    "donnees": {"o": 1, "ko": 1e3, "mo": 1e6, "go": 1e9, "to": 1e12, "kio": 1024, "mio": 1024**2, "gio": 1024**3},
}


@srv.lecture
def convertir(valeur: float, de: str, vers: str) -> str:
    """Convertit des unités : longueur, masse, volume, vitesse, données, et températures (c, f, k)."""
    de, vers, v = de.lower().strip(), vers.lower().strip(), float(valeur)
    temp = {"c": (lambda x: x, lambda x: x), "f": (lambda x: (x - 32) * 5 / 9, lambda x: x * 9 / 5 + 32),
            "k": (lambda x: x - 273.15, lambda x: x + 273.15)}
    if de in temp and vers in temp:
        return f"{v} °{de.upper()} = {round(temp[vers][1](temp[de][0](v)), 4)} °{vers.upper()}"
    for famille, u in UNITES.items():
        if de in u and vers in u:
            return f"{v} {de} = {round(v * u[de] / u[vers], 6)} {vers} ({famille})"
    raise ValueError(f"conversion inconnue {de} -> {vers}")


@srv.lecture
def mot_de_passe(longueur: int = 16, symboles: bool = True) -> str:
    """Génère un mot de passe aléatoire solide (générateur cryptographique, rien n'est enregistré)."""
    alphabet = string.ascii_letters + string.digits + ("!@#$%&*-_=+?" if symboles else "")
    return "".join(secrets.choice(alphabet) for _ in range(max(8, min(int(longueur), 128))))


@srv.lecture
def dates(depuis: str, jusqua: str = "", ajouter_jours: int = 0) -> str:
    """Jours entre deux dates (AAAA-MM-JJ ; jusqua vide = aujourd'hui), ou date + N jours."""
    d1 = datetime.date.fromisoformat(depuis)
    if ajouter_jours:
        r = d1 + datetime.timedelta(days=int(ajouter_jours))
        return f"{depuis} + {ajouter_jours} jours = {r.isoformat()} ({['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'][r.weekday()]})"
    d2 = datetime.date.fromisoformat(jusqua) if jusqua else datetime.date.today()
    return f"{(d2 - d1).days} jours entre {d1} et {d2}"


if __name__ == "__main__":
    srv.lancer()
