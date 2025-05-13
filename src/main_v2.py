# main_v2.py

import json
import os
from api.auth import auth
from api.race import get_my_races
from api.vrzen import get_course_names
from utils.secure import decrypt_message

# === Fichiers / chemins
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
RACES_PATH = os.path.join(BASE_DIR, "races.json")

# === Chargement des identifiants
with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
    creds = json.load(f)

MAIL = creds["MAIL"]
MDP = decrypt_message(creds["MDP"])

# === Authentification
auth_token, player_id = auth(MAIL, MDP)
if not auth_token:
    print("❌ Authentification échouée")
    exit()
print(f"✅ Authentifié - ID: {player_id}")

# === Récupération des courses actives
races = get_my_races(auth_token, player_id)
if not races:
    print("❌ Aucune course récupérée.")
    exit()
print(f"📋 {len(races)} course(s) détectée(s)")

# === Récupération des noms de course VRZen
# Tu dois copier ton UserID VRZen manuellement ici
USER_ID_COOKIE = "0ecf9f9a-cd68-4116-a641-20958223aec1"

vrzen_names = get_course_names(USER_ID_COOKIE)
print(f"🔍 {len(vrzen_names)} noms récupérés via VRZen")

# === Mise à jour de races.json
if os.path.exists(RACES_PATH):
    with open(RACES_PATH, "r", encoding="utf-8") as f:
        races_data = json.load(f)
else:
    races_data = {}

for race in races:
    race_id = race["race_id"]
    name = vrzen_names.get(race_id, f"AUTO_{race_id}")
    if name not in races_data:
        races_data[name] = race_id
        print(f"➕ Ajout : {name} ↔ {race_id}")
    else:
        print(f"✔️ Déjà présent : {name}")

# === Sauvegarde
with open(RACES_PATH, "w", encoding="utf-8") as f:
    json.dump(races_data, f, indent=4)

print("✅ races.json mis à jour.")
