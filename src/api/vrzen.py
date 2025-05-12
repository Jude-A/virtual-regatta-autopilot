# api/vrzen.py
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
        resp = requests.get(url, headers=headers, params=params, cookies=cookies)
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

def launch_vrzen_simulation(course_name, lat_start, lon_start, lat_target, lon_target, user_id_cookie):
    """
    Lance une simulation de route via l'API de VRZen.
    
    Args:
        course_name (str): Nom de la course (ex: "PAPREC25").
        lat_start (float): Latitude de départ.
        lon_start (float): Longitude de départ.
        lat_target (float): Latitude d'arrivée.
        lon_target (float): Longitude d'arrivée.
        user_id_cookie (str): UUID utilisateur VRZen à passer en cookie (ex: depuis navigateur).
    
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
        "parametres": "1,2,5:16:4:False:10C:-1::1:0:0:False:True:100:MIXGEFS025",
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
        resp = requests.get(url, headers=headers, params=params, cookies=cookies)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print("❌ Erreur requête VRZen :", e)
        return None
