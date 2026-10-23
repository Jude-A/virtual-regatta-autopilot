# app.py
"""Tableau de bord de suivi : python app.py, puis http://127.0.0.1:8765 (ouvert automatiquement)."""
import os
import threading
import webbrowser
import urllib3
from flask import Flask, jsonify, request, send_from_directory
from core.tracker import Tracker

HOST, PORT = "127.0.0.1", 8765
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

# VRZen est appelé avec verify=False (api/vrzen.py) : inutile d'afficher l'avertissement à chaque requête
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__, static_folder=None)
tracker = Tracker()

@app.get("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")

@app.get("/<path:filename>")
def static_files(filename):
    return send_from_directory(WEB_DIR, filename)

@app.get("/api/state")
def state():
    return jsonify(tracker.snapshot())

@app.post("/api/races/<int:race_id>/reroute")
def reroute(race_id):
    tracker.request_reroute(race_id)
    return jsonify(ok=True)

@app.post("/api/login")
def login():
    body = request.get_json(silent=True) or {}
    mail, mdp = (body.get("mail") or "").strip(), body.get("mdp") or ""
    if not mail or not mdp:
        return jsonify(ok=False, error="Renseigne le mail et le mot de passe."), 400
    if not tracker.login(mail, mdp):
        return jsonify(ok=False, error="Identifiants refusés par Virtual Regatta."), 401
    return jsonify(ok=True)

if __name__ == "__main__":
    tracker.start()
    threading.Timer(1.0, webbrowser.open, args=[f"http://{HOST}:{PORT}"]).start()
    print(f"⛵ Suivi de course sur http://{HOST}:{PORT}  (Ctrl+C pour arrêter)")
    app.run(host=HOST, port=PORT, threaded=True)
