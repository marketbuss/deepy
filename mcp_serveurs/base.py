"""Mini-socle MCP (stdio, JSON-RPC ligne par ligne), sans dependance.
Usage :
    srv = Serveur("nom", "description")
    @srv.outil
    def ma_fonction(ville: str, jours: int = 1) -> str:
        '''Description vue par le modele.'''
    srv.lancer()
Le schema des parametres est deduit des annotations ; ceux sans valeur par defaut sont requis."""
import inspect, json, sys, traceback

TYPES = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}


class Serveur:
    def __init__(self, nom, instructions=""):
        self.nom, self.instructions, self.outils = nom, instructions, {}

    def outil(self, f):
        sig = inspect.signature(f)
        props, requis = {}, []
        for p in sig.parameters.values():
            props[p.name] = {"type": TYPES.get(p.annotation, "string")}
            if p.default is inspect.Parameter.empty:
                requis.append(p.name)
        self.outils[f.__name__] = (f, {"name": f.__name__, "description": inspect.getdoc(f) or "",
                                       "inputSchema": {"type": "object", "properties": props, "required": requis}})
        return f

    def lecture(self, f):
        """Comme @outil, mais marque l'outil en lecture seule : Deepy l'appelle sans demander confirmation."""
        self.outil(f)
        self.outils[f.__name__][1]["annotations"] = {"readOnlyHint": True}
        return f

    def _repondre(self, msg):
        m, i = msg.get("method"), msg.get("id")
        if m == "initialize":
            res = {"protocolVersion": msg.get("params", {}).get("protocolVersion", "2025-06-18"),
                   "capabilities": {"tools": {}}, "serverInfo": {"name": self.nom, "version": "1.0"},
                   "instructions": self.instructions}
        elif m == "tools/list":
            res = {"tools": [schema for _, schema in self.outils.values()]}
        elif m == "tools/call":
            p = msg.get("params", {})
            f = self.outils.get(p.get("name"), (None,))[0]
            try:
                if not f:
                    raise ValueError(f"outil inconnu : {p.get('name')}")
                r = f(**(p.get("arguments") or {}))
                texte = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False, indent=1)
                res = {"content": [{"type": "text", "text": texte}]}
            except Exception as e:
                traceback.print_exc(file=sys.stderr)
                res = {"content": [{"type": "text", "text": f"Erreur : {e}"}], "isError": True}
        elif m == "ping":
            res = {}
        elif i is None:
            return None  # notification : pas de reponse
        else:
            return {"jsonrpc": "2.0", "id": i, "error": {"code": -32601, "message": f"méthode inconnue : {m}"}}
        return {"jsonrpc": "2.0", "id": i, "result": res}

    def lancer(self):
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
        proto, sys.stdout = sys.stdout, sys.stderr  # un print() parasite ne casse pas le protocole
        for ligne in sys.stdin:
            try:
                r = self._repondre(json.loads(ligne))
            except ValueError:
                continue
            if r is not None:
                proto.write(json.dumps(r, ensure_ascii=False) + "\n")
                proto.flush()
