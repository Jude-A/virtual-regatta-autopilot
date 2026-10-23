# core/tracker.py
"""Suivi des courses en tâche de fond : état du bateau chaque minute, route VRZen
recalculée chaque heure depuis la position réelle, trace enregistrée sur disque."""
import copy
import json
import os
import threading
import time
import config
from api.auth import auth
from api.race import get_my_races, get_boat_state, log_event
from api.vrzen import available_sails, compute_route, get_course_names
from utils.secure import encrypt_message

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

POLL_EVERY = 60            # s : état du bateau (VR recalcule la position chaque minute)
REROUTE_EVERY = 60 * 60    # s : nouvelle route VRZen depuis la position réelle
RETRY_EVERY = 10 * 60      # s : nouvel essai si le routage a échoué
LEGS_EVERY = 10 * 60       # s : infos des courses (nom, arrivée, nombre de concurrents)
SESSION_TTL = 30 * 60      # s : on se reconnecte avant que le token VR n'expire

# Plan de programmation : prix d'une action supplémentaire, en °·h d'écart de TWA évité.
# 8 donne ~2° d'écart moyen avec la route pour une douzaine d'actions sur 2 jours de course.
PLAN_ACTION_COST = 8

def _weighted_median(values, weights):
    items = sorted(zip(values, weights))
    half, acc = sum(weights) / 2, 0
    for v, w in items:
        acc += w
        if acc >= half:
            return v
    return items[-1][0]

def build_twa_plan(points, arrival):
    """Route -> actions à programmer dans le jeu en pilote TWA.

    Chaque action fixe une TWA et une voile, tenues jusqu'à l'action suivante : en pilote TWA
    le bateau suit seul les bascules du vent. Le découpage minimise
    (nombre d'actions × PLAN_ACTION_COST) + écart de TWA à la route × durée, sans jamais
    mélanger deux bords ou deux voiles dans une même action."""
    pts = [p for p in points if not p["end"]]
    if not pts:
        return []
    hours = [((pts[k + 1]["t"] if k + 1 < len(pts) else arrival) - pts[k]["t"]) / 3.6e6 for k in range(len(pts))]

    def segment(i, j):
        """pts[i:j] tenu à une seule TWA -> (coût, twa), ou None si bord ou voile changent."""
        seg = pts[i:j]
        if seg[-1]["twa"] * seg[0]["twa"] < 0 or seg[-1]["sail"] != seg[0]["sail"]:
            return None
        twa = _weighted_median([p["twa"] for p in seg], hours[i:j])
        return sum(abs(p["twa"] - twa) * h for p, h in zip(seg, hours[i:j])), twa

    # Programmation dynamique : best[j] = coût minimal pour couvrir pts[:j]
    n = len(pts)
    best = [0.0] + [float("inf")] * n
    cut = [None] * (n + 1)
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            seg = segment(i, j)
            if seg is None:
                break  # un segment plus long contiendrait aussi ce changement
            cost = best[i] + PLAN_ACTION_COST + seg[0]
            if cost < best[j]:
                best[j], cut[j] = cost, (i, seg[1])
    bounds, j = [], n
    while j:
        i, twa = cut[j]
        bounds.append((i, j, twa))
        j = i

    plan = []
    for i, j, twa in reversed(bounds):
        prev = plan[-1] if plan else None
        kinds = []
        if prev and prev["twa"] * twa < 0:
            kinds.append("Virement" if abs(twa) < 90 else "Empannage")
        if prev and pts[i]["sail"] != prev["sail"]:
            kinds.append("Changement de voile")
        if prev and not kinds:
            kinds.append("Changement d'angle")
        plan.append({"t": pts[i]["t"], "until": pts[j]["t"] if j < n else arrival,
                     "twa": twa, "sail": pts[i]["sail"], "hdg": pts[i]["hdg"],
                     "prev_twa": prev["twa"] if prev else None, "kinds": kinds or ["Réglage de départ"]})
    return plan

def _load_json(name, default):
    try:
        with open(os.path.join(DATA_DIR, name), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default

def _save_json(name, data):
    path = os.path.join(DATA_DIR, name)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(path + ".tmp", path)

class Tracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._creds = (config.MAIL, config.MDP)
        self._session = {"token": None, "user": None, "at": 0}
        self._legs, self._legs_at = {}, 0
        self._vrzen_names = {}
        self._reroute_asked = set()
        self.races = {}  # race_id -> état affiché
        self.status = {"needs_login": not config.MAIL, "error": None, "last_poll": None}

    # --- API pour le serveur web (appelée depuis d'autres threads) ---

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def snapshot(self):
        with self._lock:
            return copy.deepcopy({"status": self.status, "races": list(self.races.values()),
                                  "now": int(time.time() * 1000)})

    def request_reroute(self, race_id):
        with self._lock:
            self._reroute_asked.add(race_id)
        self._wake.set()

    def login(self, mail, mdp):
        token, user = auth(mail, mdp)
        if not token:
            return False
        with open(config.CREDENTIALS_PATH, "w", encoding="utf-8") as f:
            json.dump({"MAIL": mail, "MDP": encrypt_message(mdp)}, f, indent=4)
        with self._lock:
            self._creds = (mail, mdp)
            self._session = {"token": token, "user": user, "at": time.time()}
            self.status.update(needs_login=False, error=None)
        self._wake.set()
        return True

    # --- Boucle de suivi ---

    def _run(self):
        while True:
            try:
                self._poll()
            except Exception as e:  # le suivi ne doit jamais s'arrêter sur une erreur réseau
                self._set_status(error=f"Erreur de suivi : {e}")
            self._wake.wait(POLL_EVERY)
            self._wake.clear()

    def _set_status(self, **kw):
        with self._lock:
            self.status.update(kw)

    def _ensure_session(self):
        mail, mdp = self._creds
        if not mail:
            self._set_status(needs_login=True)
            return False
        if time.time() - self._session["at"] > SESSION_TTL:
            token, user = auth(mail, mdp)
            if not token:
                self._set_status(error="Connexion à Virtual Regatta impossible.")
                return False
            self._session = {"token": token, "user": user, "at": time.time()}
        return True

    def _refresh_legs(self):
        if time.time() - self._legs_at < LEGS_EVERY:
            return
        s = self._session
        res = log_event("Leg_GetList", s["token"], s["user"]).get("res", [])
        self._legs = {(leg["raceId"], leg["legNum"]): leg for leg in res}
        self._legs_at = time.time()

    def _vrzen_name(self, race_id):
        if race_id not in self._vrzen_names:
            self._vrzen_names.update(get_course_names(config.VRZEN_USER_ID))
        return self._vrzen_names.get(race_id)

    def _poll(self):
        if not self._ensure_session():
            return
        s = self._session
        active = get_my_races(s["token"], s["user"])
        self._refresh_legs()
        for race in active:
            self._poll_race(race["race_id"], race["leg"])
        with self._lock:
            for rid in set(self.races) - {r["race_id"] for r in active}:
                del self.races[rid]
        self._set_status(error=None, last_poll=int(time.time() * 1000))

    def _poll_race(self, race_id, leg_num):
        s = self._session
        boat = get_boat_state(s["token"], s["user"], race_id, leg_num)
        if not boat:
            self._session["at"] = 0  # token probablement expiré : reconnexion au prochain tour
            return
        leg = self._legs.get((race_id, leg_num), {})
        vrzen_name = self._vrzen_name(race_id)

        with self._lock:
            race = self.races.get(race_id) or {
                "id": race_id, "leg": leg_num,
                "route": _load_json(f"route_{race_id}.json", None),
                "track": _load_json(f"track_{race_id}.json", []),
                "route_error": None, "next_route_at": 0}
            race.update(
                name=leg.get("raceName") or vrzen_name or f"Course {race_id}",
                vrzen_name=vrzen_name,
                boat_type=(leg.get("boat") or {}).get("label"),
                end=leg.get("end"),
                skippers=leg.get("nbTotalSkippers"),
                boat={k: boat.get(k) for k in (
                    "pos", "heading", "speed", "twa", "twaAuto", "isRegulated", "tws", "twd", "sail", "stamina",
                    "rank", "distanceToEnd", "distanceFromStart", "state", "lastCalcDate")})
            track = race["track"]
            new_point = boat.get("pos") and (not track or track[-1][0] != boat["lastCalcDate"])
            if new_point:
                track.append([boat["lastCalcDate"], boat["pos"]["lat"], boat["pos"]["lon"]])
            asked = race_id in self._reroute_asked
            self._reroute_asked.discard(race_id)
            due = boat.get("state") == "racing" and (asked or time.time() >= race["next_route_at"])
            self.races[race_id] = race
            if new_point:
                _save_json(f"track_{race_id}.json", track)

        if due:
            update = self._reroute(race_id, vrzen_name, leg.get("end"), boat["pos"], available_sails(boat.get("options")))
            with self._lock:
                race.update(update)

    def _reroute(self, race_id, name, end, pos, sails):
        """Nouvelle route VRZen -> champs à mettre à jour dans l'état de la course."""
        route = None
        if name and end:
            route = compute_route(name, pos["lat"], pos["lon"], end["lat"], end["lon"], config.VRZEN_USER_ID, sails)
        if not route:
            reason = "course inconnue de VRZen" if not name else "VRZen n'a pas trouvé de route"
            return {"route_error": f"Routage impossible ({reason}), nouvel essai dans 10 min.",
                    "next_route_at": time.time() + RETRY_EVERY}
        route["computed_at"] = int(time.time() * 1000)
        route["plan"] = build_twa_plan(route["points"], route["arrival"])
        _save_json(f"route_{race_id}.json", route)
        return {"route": route, "route_error": None, "next_route_at": time.time() + REROUTE_EVERY}
