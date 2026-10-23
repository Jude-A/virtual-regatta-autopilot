# api/race.py

import requests
from config import headers_auth, url_heading, headers_heading
import json
import os

RACES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "races.json")

def update_races_json(race_list):
    data = {}
    if os.path.exists(RACES_PATH):
        with open(RACES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

    for race in race_list:
        race_id = race["race_id"]
        if race_id not in data.values():
            name = f"AUTO_{race_id}"
            data[name] = race_id

    with open(RACES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_my_races(authToken, playerId):
    url = "https://prod.vro.sparks.virtualregatta.com/rs/device/Xcl3WbCUmfcu5pWCktUoC0slGT4xkbEt/AccountDetailsRequest"

    payload = {
        "@class": "AccountDetailsRequest",
        "requestId": "638827022443340000_0",
        "authToken": authToken,
        "playerId": playerId
    }

    headers = headers_auth.copy()
    headers["x-api-key"] = "WJaKt4qoQEqcrKcQczwja9KQe2LKifyoSCMB71vfgUY="

    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        legs = data.get("scriptData", {}).get("currentLegs", [])
        return [{"race_id": leg["raceId"], "leg": leg["legNum"]} for leg in legs]
    except Exception as e:
        print("❌ Erreur lors de la récupération des courses :", e)
        return []

def log_event(event_key, authToken, playerId, **params):
    """Événement de lecture sur l'API du jeu -> scriptData de la réponse."""
    payload = {
        "@class": "LogEventRequest",
        "eventKey": event_key,
        "requestId": "638827022443340000_1",
        "authToken": authToken,
        "playerId": playerId,
        **params
    }
    resp = requests.post(url_heading, headers=headers_heading, json=payload)
    resp.raise_for_status()
    return resp.json().get("scriptData", {})

def get_boat_state(authToken, playerId, race_id, leg_num):
    """État du bateau (pos, heading, sail, state...) ou None."""
    try:
        return log_event("Game_GetBoatState", authToken, playerId, raceId=race_id, legNum=leg_num).get("boatState")
    except Exception as e:
        print("❌ Erreur lors de la récupération du bateau :", e)
        return None

def get_leg_end(authToken, playerId, race_id, leg_num):
    """(lat, lon) de l'arrivée de l'étape, ou None."""
    try:
        legs = log_event("Leg_GetList", authToken, playerId).get("res", [])
    except Exception as e:
        print("❌ Erreur lors de la récupération des étapes :", e)
        return None
    for leg in legs:
        if leg["raceId"] == int(race_id) and leg["legNum"] == leg_num:
            return leg["end"]["lat"], leg["end"]["lon"]
    return None
