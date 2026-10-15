"""Cerveau cloud de Deepy (repris de Bot Groq). Acces direct avec GROQ_API_KEY si elle existe sur ce PC,
sinon relais prive (adresse dans la config privee de l'utilisateur, jamais dans le code publie).
La cle n'est jamais affichee ni ecrite."""
import json, os, re, time, urllib.error, urllib.request

DIRECT = "https://api.groq.com/openai/v1"
PREFERES = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b", "llama-3.3-70b-versatile"]


def _cle():
    cle = os.environ.get("GROQ_API_KEY", "").strip()
    if not cle and os.name == "nt":  # variable utilisateur definie apres l'ouverture de la console
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                cle = str(winreg.QueryValueEx(k, "GROQ_API_KEY")[0]).strip()
        except OSError:
            pass
    return cle


class Groq:
    def __init__(self, relais=""):
        self.adresse_relais = relais.rstrip("/")
        self.compteur = None  # fonction(usage) appelee apres chaque reponse
        self.base, self.relais, self._cle = None, False, ""
        self.modeles, self.modele, self.vision = [], "", ""

    def _requete(self, methode, chemin, corps=None, delai=180):
        req = urllib.request.Request(self.base + chemin, method=methode,
                                     data=json.dumps(corps).encode() if corps is not None else None,
                                     headers={"Content-Type": "application/json", "User-Agent": "Deepy/1.0"})
        if self.relais:
            req.add_header("X-Bot-Client", "bot-groq")  # le relais ajoute la cle de son cote
        else:
            req.add_header("Authorization", "Bearer " + self._cle)
        try:
            with urllib.request.urlopen(req, timeout=delai) as r:
                return r.status, r.read().decode("utf-8"), 0
        except urllib.error.HTTPError as e:
            attente = int(float(e.headers.get("retry-after") or 0))
            return e.code, e.read().decode("utf-8", "replace"), attente

    def connecter(self):
        """Essaie la cle locale, puis le relais. Renvoie un texte decrivant l'acces."""
        self._cle = _cle()
        statut, texte = 0, ""
        if self._cle:
            self.base, self.relais = DIRECT, False
            try:
                statut, texte, _ = self._requete("GET", "/models", delai=20)
            except OSError:
                statut = 0
        if statut != 200:
            if not self.adresse_relais:
                raise RuntimeError("Pas de GROQ_API_KEY sur ce PC et aucun relais configuré "
                                   "(\"relais\" dans %APPDATA%\\Deepy\\config.json).")
            self.base, self.relais, self._cle = self.adresse_relais, True, ""
            statut, texte, _ = self._requete("GET", "/models", delai=30)
            if statut != 200:
                raise RuntimeError(f"Groq inaccessible (relais : {statut}) {erreur(texte)}")
        ids = sorted(m["id"] for m in json.loads(texte).get("data", [])
                     if not re.search(r"whisper|orpheus|guard|tts|embed", m["id"]))
        self.modeles = ids
        self.modele = next((m for m in PREFERES if m in ids), ids[0] if ids else "")
        self.vision = next((m for m in ids if re.search(r"llama-4-(scout|maverick)|vision|-vl\b", m)), "") or \
            next((m for m in ids if re.search(r"qwen3\.[5-9]", m)), "")
        return "relais privé" if self.relais else "clé GROQ_API_KEY (direct)"

    def chat(self, messages, outils=None, modele=None, max_tokens=None, json_seul=False):
        """Appel avec reprises : 429 (pause), 5xx, tool_use_failed. Renvoie le message de l'assistant."""
        corps = {"model": modele or self.modele, "messages": messages, "temperature": 0.2}
        if json_seul:
            corps["response_format"] = {"type": "json_object"}
        if outils:
            corps.update(tools=outils, tool_choice="auto")
        if max_tokens:
            corps["max_completion_tokens"] = max_tokens
        for essai in range(6):
            statut, texte, attente = self._requete("POST", "/chat/completions", corps)
            if statut == 200:
                j = json.loads(texte)
                if self.compteur:  # suivi du quota (tokens du jour, dont ceux servis par le cache de Groq)
                    self.compteur(j.get("usage") or {})
                return j["choices"][0]["message"]
            if statut == 429 and essai < 5:
                attente = attente or 10
                if attente > 90:
                    raise RuntimeError(f"Limite Groq atteinte (attente {attente} s). {erreur(texte)}")
                time.sleep(attente); continue
            if statut == 413 or "too large" in texte:
                raise OverflowError(erreur(texte))
            if (statut == 400 and "tool_use_failed" in texte and essai < 2) or (statut >= 500 and essai < 2):
                time.sleep(2); continue
            raise RuntimeError(f"Erreur Groq {statut} : {erreur(texte)}")
        raise RuntimeError("Groq ne répond pas correctement après plusieurs essais.")


def erreur(texte):
    try:
        return json.loads(texte)["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return texte[:300]
