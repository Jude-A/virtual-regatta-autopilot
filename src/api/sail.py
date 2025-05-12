# api/sail.py
import requests
from config import LEG_NUM, url_sail, headers_sail
from utils.time_utils import get_ts_next_minute
from utils.logger import log

def get_sail_value(sail):
    sail_mapping = {
        "Code 0": 5,
        "Jib": 1,
        "Spi": 2,
        "Spi leger": 7,
        "Spi lourd": 6,
        "Genois leger": 4,
        "Trinquette": 3
    }
    return sail_mapping.get(sail, None)

def send_sail_now(race_id, sail, hour, minute, authToken, playerId):
    s = get_sail_value(sail)
    payload = {
        "@class": "LogEventRequest",
        "eventKey": "Game_AddBoatAction",
        "race_id": race_id,
        "leg_num": LEG_NUM,
        "actions": [{"value": s, "type": "sail"}],
        "ts": get_ts_next_minute(),
        "requestId": "638725845444410000_25",
        "authToken": authToken,
        "playerId": playerId
    }
    try:
        resp = requests.post(url_sail, headers=headers_sail, json=payload)
        log(race_id, f"| [SAIL] {hour:02}:{minute:02} | Voile {sail} activée | -> Status: {resp.status_code}")
    except Exception as e:
        log(race_id, f" Erreur d'envoi sail: {e}")