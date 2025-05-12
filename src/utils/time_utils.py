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

def add_utc_offset(date_str, offset_hours):
    date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    offset = datetime.timedelta(hours=offset_hours)
    new_date_obj = date_obj + offset
    return new_date_obj.strftime("%Y-%m-%d %H:%M")