# api/heading.py
import requests
from config import LEG_NUM, url_heading, headers_heading
from utils.time_utils import get_ts_next_minute
from utils.logger import log

def send_heading_now(race_id, heading, hour, minute, authToken, playerId):
    payload = {
        "@class": "LogEventRequest",
        "eventKey": "Game_AddBoatAction",
        "race_id": race_id,
        "leg_num": LEG_NUM,
        "actions": [{"value": heading, "autoTwa": False, "type": "heading"}],
        "ts": get_ts_next_minute(),
        "requestId": "638725845444410000_25",
        "authToken": authToken,
        "playerId": playerId
    }
    try:
        resp = requests.post(url_heading, headers=headers_heading, json=payload)
        log(race_id, f"| [Waypoint] {hour:02}:{minute:02} | Cap fixé sur {heading} | -> Status: {resp.status_code}")
        if resp.status_code == 403:
            return resp.status_code, resp.json().get("error", {}).get("authToken")
        return resp.status_code, None
    except Exception as e:
        log(race_id, f" Erreur d'envoi heading: {e}")
        return None, None
