# core/autopilot.py
import os
import time
import datetime
from config import MAIL, MDP
from utils.time_utils import local_hhmm
from utils.csv_utils import parsee, process_csv
from core.router import reroute
from api.auth import auth
from api.race import get_my_races
from api.heading import send_heading_now
from api.sail import send_sail_now
from utils.logger import log, use_local_log_queue

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_RDY_PATH = os.path.join(BASE_DIR, "csv", "csv_rdy")
os.makedirs(CSV_RDY_PATH, exist_ok=True)

REROUTE_EVERY = 60 * 60  # s : nouvelle route VRZen depuis la position réelle du bateau
RETRY_EVERY = 10 * 60    # s : nouvel essai si le routage a échoué

def get_leg_num(race_id, auth_token, user_id):
    for race in get_my_races(auth_token, user_id):
        if str(race["race_id"]) == str(race_id):
            return race["leg"]
    log(race_id, " Course introuvable parmi tes courses en cours (inscrit ?), étape 1 par défaut.")
    return 1

def follow_route(csv_file, send, until):
    """Suit la route jusqu'au timestamp `until`, après avoir remis le bateau
    sur le cap/la voile du dernier waypoint passé."""
    previous_heading = None
    previous_sail = None
    started = False
    for when, heading, sail in (process_csv(csv_file) if os.path.exists(csv_file) else []):
        sail = sail or previous_sail  # cellule Voile vide dans le CSV : on garde la précédente
        # Envoi 1 min avant, l'action étant programmée côté VR à l'heure exacte du waypoint
        target = when.timestamp() - 60

        if target < time.time():
            previous_heading, previous_sail = heading, sail
            continue

        if not started:
            started = True
            now_label = datetime.datetime.now().strftime("%H:%M")
            if previous_heading is not None:
                send(send_heading_now, previous_heading, now_label)
            if previous_sail:
                send(send_sail_now, previous_sail, now_label)

        if target > until:
            break
        time.sleep(max(0, target - time.time()))

        label = local_hhmm(when)
        when_ts = int(when.timestamp() * 1000)
        if heading != previous_heading:
            send(send_heading_now, heading, label, when_ts)
        if sail and sail != previous_sail:
            send(send_sail_now, sail, label, when_ts)

        previous_heading, previous_sail = heading, sail

    time.sleep(max(0, until - time.time()))

def run_autopilot(race_id, auth_token, user_id, log_queue=None):

    if log_queue:
        use_local_log_queue(log_queue)

    csv_file = os.path.join(CSV_RDY_PATH, f"caps_{race_id}.csv")
    session = {"token": auth_token, "user": user_id}

    def refresh_session():
        # Le token de la GUI date de la connexion, qui peut remonter à plusieurs heures
        token, user = auth(MAIL, MDP) if MAIL else (None, None)
        if token:
            session.update(token=token, user=user)

    refresh_session()
    leg_num = get_leg_num(race_id, session["token"], session["user"])

    def send(send_fn, value, label, ts=None):
        code, err = send_fn(race_id, value, label, session["token"], session["user"], leg_num, ts)
        if code == 403 and err == "INVALID":
            log(race_id, " Session expirée, reconnexion...")
            refresh_session()
            send_fn(race_id, value, label, session["token"], session["user"], leg_num, ts)

    while True:
        status = reroute(race_id, session["token"], session["user"], leg_num)
        if status == "arrived":
            log(race_id, " Bateau arrivé, autopilote terminé.")
            return
        if status is None:
            log(race_id, f" On garde la route précédente, nouvel essai dans {RETRY_EVERY // 60} min.")
        parsee(race_id)
        follow_route(csv_file, send, time.time() + (REROUTE_EVERY if status else RETRY_EVERY))
        refresh_session()
