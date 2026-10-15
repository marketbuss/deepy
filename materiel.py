"""Detecte le materiel, choisit le meilleur modele qui tient sur le PC, l'installe et mesure sa vitesse."""
import json, os, shutil, subprocess, time, urllib.request

OLLAMA = "http://127.0.0.1:11434"

# Du meilleur au plus leger. ram/vram = Go minimum ; taille = Go a telecharger.
CATALOGUE = [
    {"nom": "qwen2.5-coder:14b", "taille": 9.0, "ram": 32, "vram": 12, "note": "excellent en code et commandes"},
    {"nom": "qwen2.5-coder:7b", "taille": 4.7, "ram": 16, "vram": 6, "note": "très bon en code et commandes"},
    {"nom": "qwen2.5-coder:3b", "taille": 1.9, "ram": 12, "vram": 4, "note": "bon compromis"},
    {"nom": "qwen2.5-coder:1.5b", "taille": 1.0, "ram": 6, "vram": 2, "note": "léger, correct en commandes"},
    {"nom": "qwen2.5:0.5b", "taille": 0.4, "ram": 0, "vram": 0, "note": "ultra léger, réponses basiques"},
]
# Proposes en choix manuel (/modele) en plus du catalogue
AUTRES = [
    {"nom": "deepseek-r1:1.5b", "taille": 1.1, "ram": 6, "vram": 2, "note": "DeepSeek R1 distillé"},
    {"nom": "deepseek-coder:1.3b", "taille": 0.8, "ram": 6, "vram": 2, "note": "DeepSeek spécialisé code"},
    {"nom": "deepseek-r1:7b", "taille": 4.7, "ram": 16, "vram": 6, "note": "DeepSeek R1 distillé, plus fort"},
    {"nom": "deepseek-coder:6.7b", "taille": 3.8, "ram": 16, "vram": 6, "note": "DeepSeek code, plus fort"},
]


def _ps(cmd):
    try:
        return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def detecter():
    """RAM, CPU, GPU NVIDIA (VRAM), disque libre. Tout en Go."""
    d = {"ram": 0.0, "ram_libre": 0.0, "cpu": "?", "coeurs": 0, "gpu": None, "vram": 0.0, "disque_libre": 0.0}
    brut = _ps("$c=Get-CimInstance Win32_ComputerSystem; $o=Get-CimInstance Win32_OperatingSystem; "
               "$p=Get-CimInstance Win32_Processor | Select-Object -First 1; "
               "@{ram=$c.TotalPhysicalMemory; libre=$o.FreePhysicalMemory*1KB; cpu=$p.Name; "
               "coeurs=$p.NumberOfLogicalProcessors} | ConvertTo-Json -Compress")
    try:
        j = json.loads(brut)
        d.update(ram=round(j["ram"] / 2**30, 1), ram_libre=round(j["libre"] / 2**30, 1),
                 cpu=(j["cpu"] or "?").strip(), coeurs=j["coeurs"] or 0)
    except (ValueError, KeyError, TypeError):
        pass
    if shutil.which("nvidia-smi"):  # seules les cartes NVIDIA sont sures avec Ollama sous Windows
        try:
            l = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=15).stdout.strip().splitlines()[0]
            nom, mo = l.rsplit(",", 1)
            d.update(gpu=nom.strip(), vram=round(int(mo) / 1024, 1))
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            pass
    dossier = os.environ.get("OLLAMA_MODELS") or os.path.expanduser("~")
    try:
        d["disque_libre"] = round(shutil.disk_usage(dossier).free / 2**30, 1)
    except OSError:
        pass
    return d


def choisir(m):
    """Meilleur modele qui tient : VRAM d'abord, sinon RAM totale ; et la place disque."""
    for e in CATALOGUE:
        if not m["gpu"] and (e["taille"] > 5 or (e["taille"] > 2 and m["coeurs"] < 8)):
            continue  # sans GPU : 14b trop lent partout, 7b trop lent sous 8 threads
        tient =(m["vram"] >= e["vram"] and e["vram"] > 0 and m["gpu"]) or m["ram"] >= e["ram"]
        if tient and m["disque_libre"] >= e["taille"] * 1.3:
            return e
    return CATALOGUE[-1]


def ollama_present():
    return bool(shutil.which("ollama")) or os.path.exists(
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"))


def ollama_repond():
    try:
        urllib.request.urlopen(OLLAMA + "/api/version", timeout=3).read()
        return True
    except OSError:
        return False


def demarrer_ollama():
    exe = shutil.which("ollama") or os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
    subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(30):
        if ollama_repond():
            return True
        time.sleep(1)
    return False


def installer_ollama():
    """Installe Ollama via winget (source officielle). Renvoie True si ok."""
    if not shutil.which("winget"):
        return False
    r = subprocess.run(["winget", "install", "-e", "--id", "Ollama.Ollama", "--accept-source-agreements",
                        "--accept-package-agreements", "--silent"], capture_output=True, text=True)
    return r.returncode == 0 or ollama_present()


def modeles_installes():
    try:
        with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=5) as r:
            return [m["name"] for m in json.load(r).get("models", [])]
    except OSError:
        return []


def telecharger(nom, progression):
    """ollama pull en streaming ; progression(fait, total, statut) appelee a chaque etape."""
    req = urllib.request.Request(OLLAMA + "/api/pull", json.dumps({"model": nom, "stream": True}).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3600) as r:
        for ligne in r:
            if not ligne.strip():
                continue
            e = json.loads(ligne)
            if "error" in e:
                raise RuntimeError(e["error"])
            progression(e.get("completed", 0), e.get("total", 0), e.get("status", ""))
            if e.get("status") == "success":
                return True
    return False


def mesurer(nom):
    """Vitesse reelle en tokens/s (charge le modele puis genere ~40 tokens)."""
    corps = {"model": nom, "prompt": "Compte de 1 a 30.", "stream": False, "keep_alive": "30m",
             "options": {"num_predict": 40, "num_ctx": 1024}}
    req = urllib.request.Request(OLLAMA + "/api/generate", json.dumps(corps).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        j = json.load(r)
    return round(j.get("eval_count", 0) / max(j.get("eval_duration", 1) / 1e9, 1e-6), 1)
