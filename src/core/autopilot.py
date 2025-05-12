# core/autopilot.py
import os
import time
import datetime
from config import MAIL, MDP
from utils.time_utils import get_ts_for_specific_time
from utils.csv_utils import parsee, parse
from api.auth import auth
from api.heading import send_heading_now
from api.sail import send_sail_now
from utils.logger import log, use_local_log_queue

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_RDY_PATH = os.path.join(BASE_DIR, "csv", "csv_rdy")
os.makedirs(CSV_RDY_PATH, exist_ok=True)

def run_autopilot(race_id, auth_token, user_id, log_queue=None):

    if log_queue:
        use_local_log_queue(log_queue)
        
    csv_file = os.path.join(CSV_RDY_PATH, f"caps_{race_id}.csv")

    parsee(race_id)

    with open(csv_file, "r", encoding="utf-8") as f:
        import csv
        reader = csv.reader(f)
        next(reader)
        flag = 0
        previous_heading = None
        previous_sail = None
        for row in reader:
            minute, hour, day, month, year, heading, sail = parse(row)

            target_ts = get_ts_for_specific_time(hour, minute, day, month, year) - 60000
            now_ts = int(time.time()*1000)

            if target_ts < now_ts:
                log(race_id, f"| [Waypoint] {hour:02}:{minute:02} déjà passé.")
                previous_heading = heading
                previous_sail = sail
                continue

            if flag == 0:
                code, err = send_heading_now(race_id, previous_heading, datetime.datetime.now().hour, datetime.datetime.now().minute, auth_token, user_id)
                send_sail_now(race_id, previous_sail, datetime.datetime.now().hour, datetime.datetime.now().minute, auth_token, user_id)
                if code == 403 and err == "INVALID":
                    auth_token, user_id = auth(MAIL, MDP)
                    send_heading_now(race_id, previous_heading, datetime.datetime.now().hour, datetime.datetime.now().minute, auth_token, user_id)
                    send_sail_now(race_id, previous_sail, datetime.datetime.now().hour, datetime.datetime.now().minute, auth_token, user_id)
                flag = 1

            if now_ts < target_ts:
                time.sleep(max(0, (target_ts - now_ts) / 1000.0))

            if heading != previous_heading:
                code, err = send_heading_now(race_id, heading, hour, minute, auth_token, user_id)
            if sail != previous_sail:
                send_sail_now(race_id, sail, hour, minute, auth_token, user_id)
            if code == 403 and err == "INVALID":
                auth_token, user_id = auth(MAIL, MDP)
                if heading != previous_heading:
                    send_heading_now(race_id, heading, hour, minute, auth_token, user_id)
                if sail != previous_sail:
                    send_sail_now(race_id, sail, hour, minute, auth_token, user_id)

            previous_heading = heading
            previous_sail = sail
