"""Competences de Deepy. Chaque module expose COMMANDES = {"/nom": (fonction, "aide")}.
Une fonction recoit (ui, arguments) ; ui donne acces a l'affichage, au compagnon et a la confirmation."""
from . import fichiers, code, outils_mcp, modele, vscode

# outils_mcp remplace l'ancien mcp.py : /mcp + /agent (@question), serveurs integres + mcp.json
COMMANDES = {**fichiers.COMMANDES, **code.COMMANDES, **outils_mcp.COMMANDES, **modele.COMMANDES, **vscode.COMMANDES}
