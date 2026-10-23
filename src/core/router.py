# core/router.py
import datetime
from config import VRZEN_USER_ID
from api.race import get_boat_state, get_leg_end
from api.vrzen import compute_route, available_sails
from api.sail import SAIL_NAMES
from utils.csv_utils import race_name, write_route_csv
from utils.logger import log

def _utc_minute(ms):
    """timestamp ms -> '2026-10-17 19:40' (UTC)"""
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")

def reroute(race_id, auth_token, user_id, leg_num):
    """Calcule une route VRZen depuis la position actuelle du bateau jusqu'à l'arrivée
    et l'écrit comme un export CSV VRZen.
    Retourne "ok", "arrived" (course finie) ou None si le routage a échoué."""
    boat = get_boat_state(auth_token, user_id, race_id, leg_num)
    if not boat:
        log(race_id, " Bateau introuvable, routage impossible.")
        return None
    if boat.get("state") == "arrived":
        return "arrived"

    end = get_leg_end(auth_token, user_id, race_id, leg_num)
    if not end:
        log(race_id, " Arrivée de la course introuvable, routage impossible.")
        return None

    route = compute_route(race_name(race_id), boat["pos"]["lat"], boat["pos"]["lon"], *end, VRZEN_USER_ID,
                          available_sails(boat.get("options")))
    if not route:
        log(race_id, " Routage VRZen échoué.")
        return None

    # Le dernier point est l'arrivée elle-même, sans cap à suivre
    write_route_csv(race_id, [
        (_utc_minute(p["t"]), p["hdg"], SAIL_NAMES.get(p["sail"], ""))
        for p in route["points"] if not p["end"]
    ])
    arrival = datetime.datetime.fromtimestamp(route["arrival"] / 1000).strftime("%d/%m %H:%M")
    log(race_id, f" Nouvelle route VRZen ({route['gfs']}) : arrivée estimée le {arrival}")
    return "ok"
