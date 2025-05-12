from colorama import Fore, Style
import multiprocessing

# Dictionnaire partagé pour contenir les queues par race_id
_LOG_QUEUES = {}
CURRENT_QUEUE = None

# Couleurs associées aux courses connues (ajuste selon tes préférences)
RACE_COLORS = {
    723: Fore.GREEN,
    733: Fore.CYAN,
    740: Fore.MAGENTA,
    755: Fore.YELLOW,
    712: Fore.RED,
}

def use_local_log_queue(queue):
    global CURRENT_QUEUE
    CURRENT_QUEUE = queue

def register_log_queue(race_id, queue):
    _LOG_QUEUES[race_id] = queue

def unregister_log_queue(race_id):
    _LOG_QUEUES.pop(race_id, None)

def log(race_id, msg):
    """Affiche le message en console et l’envoie aussi dans la queue GUI si disponible."""
    try:
        from config import RACES
        RACES_INVERTED = {v: k for k, v in RACES.items()}
        race_name = RACES_INVERTED.get(race_id, "Unknown Race")
    except:
        race_name = str(race_id)

    color = RACE_COLORS.get(race_id, Fore.WHITE)
    formatted_console = f"{color}[{race_name}]{Style.RESET_ALL} {msg}"
    print(formatted_console)

    if CURRENT_QUEUE:
        try:
            CURRENT_QUEUE.put(f"{msg}")
        except:
            pass