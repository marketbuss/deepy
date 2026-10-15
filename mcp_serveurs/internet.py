"""Serveur MCP « internet » : recherche web (DuckDuckGo), lecture d'une page, actualites (Google News RSS). Sans cle."""
import html, re, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from base import Serveur

srv = Serveur("internet", "Recherche sur le web, lit le texte d'une page, donne les actualités. Aucune clé API.")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Deepy/1.0", "Accept-Language": "fr-FR,fr;q=0.9"}


def get(url, donnees=None):
    req = urllib.request.Request(url, data=donnees, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        brut = r.read(3_000_000)
        enc = r.headers.get_content_charset() or "utf-8"
    return brut.decode(enc, "replace")


def texte_html(h):
    h = re.sub(r"(?is)<(script|style|noscript|svg|head|nav|footer|form)\b.*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr)>", "\n", h)
    t = html.unescape(re.sub(r"<[^>]+>", " ", h))
    lignes = [re.sub(r"[ \t\xa0]+", " ", l).strip() for l in t.splitlines()]
    return "\n".join(l for l in lignes if len(l) > 1)


@srv.lecture
def rechercher(requete: str, nombre: int = 6) -> str:
    """Recherche sur le web (DuckDuckGo) : titres, liens et extraits des meilleurs résultats."""
    h = get("https://html.duckduckgo.com/html/", urllib.parse.urlencode({"q": requete, "kl": "fr-fr"}).encode())
    res = []
    for m in re.finditer(r'(?s)class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>', h):
        lien = m.group(1)
        if "uddg=" in lien:  # lien de redirection DuckDuckGo -> vraie adresse
            lien = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlparse(lien).query).get("uddg", [lien])[0])
        if "duckduckgo.com/y.js" in lien:  # publicite
            continue
        titre, extrait = (html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in (m.group(2), m.group(3)))
        res.append(f"{len(res) + 1}. {titre}\n   {lien}\n   {extrait}")
        if len(res) >= max(1, min(int(nombre), 10)):
            break
    return "\n".join(res) or "Aucun résultat (ou DuckDuckGo a limité la recherche, réessaie dans un moment)."


@srv.lecture
def lire_page(url: str, max_caracteres: int = 6000) -> str:
    """Télécharge une page web et renvoie son texte lisible (sans menus ni scripts)."""
    if not re.match(r"^https?://", url):
        url = "https://" + url
    t = texte_html(get(url))
    n = max(200, int(max_caracteres))
    return t[:n] + (f"\n[… {len(t) - n} caractères de plus]" if len(t) > n else "")


@srv.lecture
def actualites(sujet: str = "", nombre: int = 8) -> str:
    """Derniers titres de l'actualité (en français), en général ou sur un sujet."""
    langue = "hl=fr&gl=FR&ceid=FR:fr"
    url = (f"https://news.google.com/rss/search?q={urllib.parse.quote(sujet)}&{langue}" if sujet
           else f"https://news.google.com/rss?{langue}")
    racine = ET.fromstring(get(url))
    lignes = []
    for item in racine.iter("item"):
        titre, date = item.findtext("title", ""), (item.findtext("pubDate") or "")[5:22]
        lignes.append(f"- {titre}  ({date})")
        if len(lignes) >= max(1, min(int(nombre), 20)):
            break
    return "\n".join(lignes) or "Aucune actualité trouvée."


if __name__ == "__main__":
    srv.lancer()
