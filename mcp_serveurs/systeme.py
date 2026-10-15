"""Serveur MCP « systeme » : informations sur le PC Windows, en lecture seule."""
import json, subprocess
from base import Serveur

srv = Serveur("systeme", "Infos du PC Windows (lecture seule : rien n'est modifié).")


def ps(cmd):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + cmd],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    return r.stdout.strip()


def ps_json(cmd):
    brut = ps(cmd + " | ConvertTo-Json -Compress -Depth 3")
    return json.loads(brut) if brut else None


@srv.lecture
def resume_pc() -> dict:
    """Résumé du PC : Windows, processeur, RAM totale et libre, démarré depuis."""
    return ps_json("$o=Get-CimInstance Win32_OperatingSystem; $p=Get-CimInstance Win32_Processor | Select -First 1; "
                   "[pscustomobject]@{windows=$o.Caption; version=$o.Version; processeur=$p.Name.Trim(); "
                   "ram_go=[math]::Round($o.TotalVisibleMemorySize/1MB,1); ram_libre_go=[math]::Round($o.FreePhysicalMemory/1MB,1); "
                   "allume_depuis=((Get-Date)-$o.LastBootUpTime).ToString('d\\j\\ hh\\h\\ mm\\m\\i\\n')}")


@srv.lecture
def disques() -> list:
    """Espace utilisé et libre de chaque disque."""
    return ps_json("Get-PSDrive -PSProvider FileSystem | Where-Object Used -ne $null | ForEach-Object { "
                   "[pscustomobject]@{lecteur=$_.Name; libre_go=[math]::Round($_.Free/1GB,1); utilise_go=[math]::Round($_.Used/1GB,1)} }")


@srv.lecture
def processus(nombre: int = 10, tri: str = "ram") -> list:
    """Programmes qui consomment le plus. tri = 'ram' ou 'cpu'."""
    cle = "CPU" if tri == "cpu" else "WorkingSet64"
    return ps_json(f"Get-Process | Sort-Object {cle} -Descending | Select-Object -First {max(1, min(int(nombre), 50))} "
                   "@{n='nom';e={$_.ProcessName}}, @{n='ram_mo';e={[math]::Round($_.WorkingSet64/1MB)}}, "
                   "@{n='cpu_s';e={[math]::Round($_.CPU,1)}}")


@srv.lecture
def reseau() -> dict:
    """Adresses IP locales et réseau Wi-Fi connecté."""
    ips = ps_json("Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -ne '127.0.0.1' | "
                  "Select-Object @{n='interface';e={$_.InterfaceAlias}}, @{n='ip';e={$_.IPAddress}}")
    wifi = ps("(netsh wlan show interfaces) -match '^\\s+SSID' | Select-Object -First 1").split(":", 1)[-1].strip()
    return {"adresses": ips, "wifi": wifi or None}


@srv.lecture
def batterie() -> str:
    """Niveau de batterie (portable)."""
    r = ps_json("Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus")
    if isinstance(r, list):  # plusieurs entrees (dont parfois une vide) : la premiere qui a un niveau
        r = next((b for b in r if b.get("EstimatedChargeRemaining") is not None), None)
    if not r:
        return "Pas de batterie (PC fixe)."
    etat = {1: "sur batterie", 2: "branché"}.get(r.get("BatteryStatus"), "inconnu")
    return f"{r.get('EstimatedChargeRemaining')} % ({etat})"


if __name__ == "__main__":
    srv.lancer()
