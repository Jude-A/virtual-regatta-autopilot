# api/vrzen.py
import datetime
import math
import requests

def get_course_names(user_id_cookie: str, mode="GFS"):
    """
    Récupère les correspondances entre idCourseVR et nomCourse.
    Args:
        user_id_cookie (str): ID utilisateur transmis dans les cookies
        mode (str): "GFS" ou autre mode météo (par défaut GFS)
    Returns:
        dict[int, str]: {race_id: nomCourse}
    """
    url = "https://routage.vrzen.org/Course"
    params = {
        "userID": user_id_cookie,
        "mode": mode
    }
    headers = {
        "Accept": "*/*",
        "Referer": "https://routage.vrzen.org/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        ),
        "DNT": "1"
    }
    cookies = {
        "UserID": user_id_cookie
    }

    try:
        resp = requests.get(url, headers=headers, params=params, cookies=cookies, verify=False)
        resp.raise_for_status()
        data = resp.json()
        return {
            int(course["idCourseVR"]): course["nomCourse"]
            for course in data
            if course.get("idCourseVR") and course.get("nomCourse")
        }
    except Exception as e:
        print("❌ Erreur récupération des noms de course VRZen :", e)
        return {}

BASE_SAILS = (1, 2)  # Jib et Spi : les seules voiles sans option payante
# Voiles débloquées par chaque option du bateau (champ "options" de l'état du bateau VR)
OPTION_SAILS = {"heavy": (3, 6), "light": (4, 7), "reach": (5,)}

def available_sails(boat_options):
    """Identifiants VR des voiles dont dispose le bateau."""
    sails = set(BASE_SAILS)
    for option in boat_options or []:
        sails.update(OPTION_SAILS.get(option, ()))
    return sorted(sails)

def launch_vrzen_simulation(course_name, lat_start, lon_start, lat_target, lon_target, user_id_cookie, sails=BASE_SAILS):
    """
    Lance une simulation de route via l'API de VRZen.
    
    Args:
        course_name (str): Nom de la course (ex: "PAPREC25").
        lat_start (float): Latitude de départ.
        lon_start (float): Longitude de départ.
        lat_target (float): Latitude d'arrivée.
        lon_target (float): Longitude d'arrivée.
        user_id_cookie (str): UUID utilisateur VRZen à passer en cookie (ex: depuis navigateur).
        sails (iterable[int]): voiles utilisables (identifiants VR), voir available_sails.
    
    Returns:
        dict | None: Réponse JSON de VRZen ou None en cas d'erreur.
    """
    url = "https://routage.vrzen.org/Simulation"

    params = {
        "userID": user_id_cookie,
        "course": course_name,
        "latitude_origine": lat_start,
        "longitude_origine": lon_start,
        "latitude_cible": lat_target,
        "longitude_cible": lon_target,
        # 1er champ : voiles utilisables ; 2e : durée max de simulation (jours) ; le reste est repris tel quel de VRZen
        "parametres": f"{','.join(map(str, sails))}:16:4:False:10C:-1::1:0:0:False:True:100:MIXGEFS025",
        "preferences": "EMPTY::EMAIL:10:MN:FR:"
    }

    headers = {
        "Accept": "*/*",
        "Referer": "https://routage.vrzen.org/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        ),
        "DNT": "1"
    }

    cookies = {
        "UserID": user_id_cookie
    }

    try:
        resp = requests.get(url, headers=headers, params=params, cookies=cookies, verify=False)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print("❌ Erreur requête VRZen :", e)
        return None

KMH_PER_KNOT = 1.852  # VRZen donne les vitesses (bateau et vent) en km/h

def _vrzen_ms(date_str):
    """'2026-10-17T19:40:00.0000601Z' -> timestamp en ms (UTC)."""
    dt = datetime.datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
    return int(dt.replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)

# Une arrivée au ras du quai (ex. Colombo) est souvent à terre pour VRZen, qui ne trouve alors
# aucun itinéraire : on vise un point au large, à ces distances (degrés) de l'arrivée.
OFFSHORE_RADII = (0.05, 0.1, 0.2)
_offshore_targets = {}  # (course, lat, lon) de l'arrivée -> cible acceptée par VRZen

def _candidate_targets(lat_target, lon_target, lat_start, lon_start):
    """Arrivée exacte, puis points autour d'elle, ceux du côté du départ d'abord."""
    yield lat_target, lon_target
    toward_start = math.atan2(lat_start - lat_target, lon_start - lon_target)
    bearings = sorted((math.radians(a) for a in range(0, 360, 45)),
                      key=lambda a: abs(math.remainder(a - toward_start, 2 * math.pi)))
    for r in OFFSHORE_RADII:
        for a in bearings:
            yield lat_target + r * math.sin(a), lon_target + r * math.cos(a)

def _simulate(course_name, lat_start, lon_start, lat_target, lon_target, user_id_cookie, sails):
    """Simulation VRZen vers l'arrivée, décalée au large si VRZen la refuse. None si échec."""
    key = (course_name, lat_target, lon_target)
    targets = _candidate_targets(lat_target, lon_target, lat_start, lon_start)
    if key in _offshore_targets:
        targets = [_offshore_targets[key]]
    for target in targets:
        sim = launch_vrzen_simulation(course_name, lat_start, lon_start, *target, user_id_cookie, sails)
        if sim is None:
            return None  # erreur réseau : inutile d'essayer d'autres cibles
        if sim.get("statut") == "OK" and sim.get("listDetailSimulation"):
            if target != (lat_target, lon_target):
                _offshore_targets[key] = target
            return sim
        print(f"❌ VRZen {course_name} vers {target[0]:.3f}, {target[1]:.3f} : {sim.get('messageErreur')}")
    _offshore_targets.pop(key, None)  # la cible mémorisée ne passe plus : nouvelle recherche au prochain essai
    return None

def compute_route(course_name, lat_start, lon_start, lat_target, lon_target, user_id_cookie, sails=BASE_SAILS):
    """
    Route VRZen normalisée, ou None si le routage a échoué.
    Returns:
        {"gfs": "GFS 2026-10-17T12Z Complet", "departure": ms, "arrival": ms,
         "points": [{"t": ms, "lat", "lon", "hdg", "twa", "sail": id VR ou None,
                     "speed": nds, "tws": nds, "twd", "end": bool}, ...]}  # ordre chronologique
    """
    sim = _simulate(course_name, lat_start, lon_start, lat_target, lon_target, user_id_cookie, sails)
    if not sim:
        return None
    points = [{
        "t": _vrzen_ms(p["dateHeure"]),
        "lat": p["latitude"],
        "lon": p["longitude"],
        "hdg": p["cap"],
        "twa": p["twa"],
        "sail": p["typeVoile"],
        "speed": round(p["vitesse"] / KMH_PER_KNOT, 2),
        "tws": round(p["vitesseVent"] / KMH_PER_KNOT, 2),
        "twd": p["directionVent"],
        "end": bool(p["estFin"]),
    } for p in sim["listDetailSimulation"]]
    points.sort(key=lambda p: p["t"])
    return {
        "gfs": sim.get("statusIntegrationGFS") or "",
        "departure": _vrzen_ms(sim["dateHeureDepart"]),
        "arrival": _vrzen_ms(sim["dateHeureArrivee"]),
        "points": points,
    }
