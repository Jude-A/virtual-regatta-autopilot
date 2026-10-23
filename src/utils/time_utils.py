# utils/time_utils.py
import datetime

def get_ts_next_minute():
    now = datetime.datetime.now()
    rounded = now.replace(second=0, microsecond=0)
    if now.second > 0 or now.microsecond > 0:
        rounded += datetime.timedelta(minutes=1)
    return int(rounded.timestamp() * 1000)

def get_ts_for_specific_time(hour, minute, day=None, month=None, year=None):
    now = datetime.datetime.now()
    year = year or now.year
    month = month or now.month
    day = day or now.day
    specific_dt = datetime.datetime(year, month, day, hour, minute)
    return int(specific_dt.timestamp() * 1000)

def parse_utc(date_str):
    """'2025-05-12 08:26' (heure UTC de VRZen) -> datetime UTC."""
    return datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M").replace(tzinfo=datetime.timezone.utc)

def local_hhmm(dt):
    """Heure locale du PC au format HH:MM, pour les logs."""
    return dt.astimezone().strftime("%H:%M")
