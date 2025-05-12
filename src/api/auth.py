# api/auth.py
import requests
from config import url_auth, headers_auth

def auth(mail, mdp):
    try:
        payload_auth = {
            "@class": "AuthenticationRequest",
            "userName": mail,
            "password": mdp
        }
        resp = requests.post(url_auth, headers=headers_auth, json=payload_auth)
        data = resp.json()
        print("Authentifié")
        return data["authToken"], data["userId"]
    except Exception as e:
        print("Erreur lors de l'authentification:", e)
        return None, None
