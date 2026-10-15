"""Serveur MCP « web » : meteo, Wikipedia, taux de change. Services publics gratuits, sans cle."""
import json, re, urllib.error, urllib.parse, urllib.request
from base import Serveur

srv = Serveur("web", "Météo (wttr.in), Wikipédia, taux de change (BCE via frankfurter). Aucune clé API.")
UA = {"User-Agent": "Deepy/1.0 (assistant local)"}


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return json.load(r)


@srv.lecture
def meteo(ville: str, jours: int = 1) -> str:
    """Météo actuelle et prévisions (1 à 3 jours) pour une ville."""
    d = get_json(f"https://wttr.in/{urllib.parse.quote(ville)}?format=j1&lang=fr")
    c = d["current_condition"][0]
    desc = (c.get("lang_fr") or c["weatherDesc"])[0]["value"]
    lignes = [f"{ville} maintenant : {c['temp_C']}°C (ressenti {c['FeelsLikeC']}°C), {desc}, "
              f"humidité {c['humidity']} %, vent {c['windspeedKmph']} km/h"]
    for j in d["weather"][:max(1, min(int(jours), 3))]:
        lignes.append(f"{j['date']} : {j['mintempC']}°C à {j['maxtempC']}°C")
    return "\n".join(lignes)


@srv.lecture
def wikipedia(sujet: str, langue: str = "fr") -> str:
    """Résumé Wikipédia d'un sujet (avec le lien de l'article)."""
    lang = re.sub(r"[^a-z]", "", langue.lower())[:3] or "fr"
    base = f"https://{lang}.wikipedia.org"
    try:
        d = get_json(f"{base}/api/rest_v1/page/summary/{urllib.parse.quote(sujet.replace(' ', '_'))}")
    except urllib.error.HTTPError:  # titre inexact : on cherche le plus proche
        r = get_json(f"{base}/w/api.php?action=opensearch&limit=1&format=json&search={urllib.parse.quote(sujet)}")
        if not r[1]:
            return f"Aucun article pour « {sujet} »."
        d = get_json(f"{base}/api/rest_v1/page/summary/{urllib.parse.quote(r[1][0].replace(' ', '_'))}")
    return f"{d.get('title')} : {d.get('extract', '')}\n{d.get('content_urls', {}).get('desktop', {}).get('page', '')}"


@srv.lecture
def devises(montant: float, de: str, vers: str) -> str:
    """Convertit un montant entre devises (EUR, USD, CHF, GBP…) au taux du jour de la BCE."""
    de, vers = de.upper().strip(), vers.upper().strip()
    d = get_json(f"https://api.frankfurter.app/latest?amount={float(montant)}&from={de}&to={vers}")
    return f"{montant} {de} = {d['rates'][vers]} {vers} (taux BCE du {d['date']})"


if __name__ == "__main__":
    srv.lancer()
