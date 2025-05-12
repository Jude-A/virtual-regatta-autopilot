# api/race.py

import requests
from config import headers_auth
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
        if str(race_id) not in data.values():
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
