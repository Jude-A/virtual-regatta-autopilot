# api/heading.py
import requests
from config import url_heading, headers_heading
from utils.time_utils import get_ts_next_minute
from utils.logger import log

def post_boat_action(race_id, leg_num, action, authToken, playerId, url, headers, ts=None):
    """Envoie une action bateau. Retourne (status, erreur authToken si 403 / erreur du jeu si refusée)."""
    payload = {
        "@class": "LogEventRequest",
        "eventKey": "Game_AddBoatAction",
        "race_id": race_id,
        "leg_num": leg_num,
        "actions": [action],
        "ts": ts or get_ts_next_minute(),
        "requestId": "638725845444410000_25",
        "authToken": authToken,
        "playerId": playerId
    }
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code == 403:
        try:
            return resp.status_code, resp.json().get("error", {}).get("authToken")
        except ValueError:
            return resp.status_code, None
    # Un refus du jeu (ex: ERR320 "Bad API key") revient quand même en HTTP 200
    try:
        script = resp.json().get("scriptData", {})
    except ValueError:
        return resp.status_code, None
    if script.get("rc", "ok") != "ok":
        return resp.status_code, f"{script.get('rc')} {script.get('msg', '')}".strip()
    return resp.status_code, None

def send_heading_now(race_id, heading, label, authToken, playerId, leg_num=1, ts=None):
    try:
        code, err = post_boat_action(race_id, leg_num, {"value": heading, "autoTwa": False, "type": "heading"},
                                     authToken, playerId, url_heading, headers_heading, ts)
        refused = f" | REFUSÉ : {err}" if err else ""
        log(race_id, f"| [Waypoint] {label} | Cap fixé sur {heading} | -> Status: {code}{refused}")
        return code, err
    except Exception as e:
        log(race_id, f" Erreur d'envoi heading: {e}")
        return None, None
