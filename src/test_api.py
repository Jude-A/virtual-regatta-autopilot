# test_api.py

import json
import requests
from api.auth import auth
from config import headers_getboatinfos
from utils.secure import decrypt_message

from api.race import get_my_races, update_races_json


# === Charger les identifiants chiffrés ===
with open("src/credentials.json", "r", encoding="utf-8") as f:
    creds = json.load(f)

MAIL = creds["MAIL"]
MDP = decrypt_message(creds["MDP"])

# === Authentification ===
auth_token, player_id = auth(MAIL, MDP)
if not auth_token:
    print("❌ Authentification échouée")
    exit()

print(f"✅ Authentifié : player_id = {player_id}")


# Récupération des courses
courses = get_my_races(auth_token, player_id)

# Mise à jour races.json
update_races_json(courses)

if not courses:
    print("Aucune course trouvée.")
else:
    for c in courses:
        print(f" - Race ID: {c['race_id']} | Leg: {c['leg']}")