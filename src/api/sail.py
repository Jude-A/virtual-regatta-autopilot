# api/sail.py
import unicodedata
from config import url_sail, headers_sail
from api.heading import post_boat_action
from utils.logger import log

# Identifiants de voiles Virtual Regatta, clés normalisées (minuscules, sans accents ni espaces)
SAIL_IDS = {
    "jib": 1, "foc": 1,
    "spi": 2, "spinnaker": 2,
    "trinquette": 3, "staysail": 3,
    "genoisleger": 4, "lightjib": 4,
    "code0": 5,
    "spilourd": 6, "heavygennaker": 6, "heavygnk": 6,
    "spileger": 7, "lightgennaker": 7, "lightgnk": 7,
}
# Nom écrit dans les CSV pour chaque identifiant (celui des exports VRZen)
SAIL_NAMES = {1: "Jib", 2: "Spi", 3: "Staysail", 4: "LightJib", 5: "Code0", 6: "HeavyGnk", 7: "LightGnk"}

def get_sail_value(sail):
    key = unicodedata.normalize("NFKD", sail or "").encode("ascii", "ignore").decode()
    key = "".join(c for c in key.lower() if c.isalnum())
    return SAIL_IDS.get(key)

def send_sail_now(race_id, sail, label, authToken, playerId, leg_num=1, ts=None):
    s = get_sail_value(sail)
    if s is None:
        log(race_id, f"| [SAIL] {label} | Voile inconnue '{sail}', non envoyée")
        return None, None
    try:
        code, err = post_boat_action(race_id, leg_num, {"value": s, "type": "sail"},
                                     authToken, playerId, url_sail, headers_sail, ts)
        refused = f" | REFUSÉ : {err}" if err else ""
        log(race_id, f"| [SAIL] {label} | Voile {sail} activée | -> Status: {code}{refused}")
        return code, err
    except Exception as e:
        log(race_id, f" Erreur d'envoi sail: {e}")
        return None, None
