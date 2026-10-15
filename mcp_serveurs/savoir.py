"""Serveur MCP « savoir » : traduction, definitions, cryptomonnaies, jours feries. Services publics, sans cle."""
import json, re, urllib.parse, urllib.request
from base import Serveur

srv = Serveur("savoir", "Traduction (MyMemory), définitions (Wiktionnaire), prix des cryptos (CoinGecko), jours fériés.")
UA = {"User-Agent": "Deepy/1.0 (assistant local)"}


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return json.load(r)


@srv.lecture
def traduire(texte: str, vers: str = "fr", depuis: str = "auto") -> str:
    """Traduit un texte court (codes de langue : fr, en, es, de, it, pt, ar, nl…)."""
    src = "Autodetect" if depuis == "auto" else depuis
    d = get_json("https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(
        {"q": texte[:500], "langpair": f"{src}|{vers}"}))
    return d.get("responseData", {}).get("translatedText") or "Traduction indisponible."


@srv.lecture
def definition(mot: str) -> str:
    """Définition d'un mot français (Wiktionnaire)."""
    d = get_json("https://fr.wiktionary.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "format": "json", "titles": mot.strip()}))
    page = next(iter(d.get("query", {}).get("pages", {}).values()), {})
    texte = page.get("extract") or ""
    m = re.search(r"(?s)== Français ==(.*?)(\n== |\Z)", texte)
    texte = (m.group(1) if m else texte).strip()
    return texte[:2500] if texte else f"Aucune définition trouvée pour « {mot} »."


@srv.lecture
def crypto(monnaie: str = "bitcoin", devise: str = "eur") -> str:
    """Prix actuel d'une cryptomonnaie (bitcoin, ethereum, solana…) et variation sur 24 h."""
    ident = monnaie.lower().strip()
    ident = {"btc": "bitcoin", "eth": "ethereum", "sol": "solana", "doge": "dogecoin", "xrp": "ripple"}.get(ident, ident)
    dev = devise.lower()
    d = get_json("https://api.coingecko.com/api/v3/simple/price?" + urllib.parse.urlencode(
        {"ids": ident, "vs_currencies": dev, "include_24hr_change": "true"}))
    if ident not in d:
        return f"Cryptomonnaie inconnue : {monnaie} (utilise son nom complet, ex. bitcoin)."
    prix, var = d[ident].get(dev), d[ident].get(f"{dev}_24h_change") or 0
    return f"{ident} : {prix:,} {dev.upper()} ({var:+.2f} % sur 24 h)".replace(",", " ")


@srv.lecture
def jours_feries(pays: str = "FR", annee: int = 0) -> str:
    """Jours fériés d'un pays (code à 2 lettres : FR, BE, CH, CA…) pour une année (0 = cette année)."""
    import datetime
    a = int(annee) or datetime.date.today().year
    code = re.sub(r"[^A-Za-z]", "", pays).upper()[:2]
    d = get_json(f"https://date.nager.at/api/v3/PublicHolidays/{a}/{code}")
    return "\n".join(f"{j['date']} : {j['localName']}" for j in d) or "Aucun jour férié trouvé."


if __name__ == "__main__":
    srv.lancer()
