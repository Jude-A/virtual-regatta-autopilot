# utils/csv_utils.py
import csv
import os
from utils.time_utils import add_utc_offset
from utils.logger import log
from config import RACES
RACES_INVERTED = {v: k for k, v in RACES.items()}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_COPIER_PATH = os.path.join(BASE_DIR, "csv", "csv_copier")
CSV_RDY_PATH = os.path.join(BASE_DIR, "csv", "csv_rdy")
os.makedirs(CSV_COPIER_PATH, exist_ok=True)
os.makedirs(CSV_RDY_PATH, exist_ok=True)

def parsee(race_id):
    input_dir = CSV_COPIER_PATH
    output_file = os.path.join(CSV_RDY_PATH, f"caps_{race_id}.csv")
    input_file = None

    for file in os.listdir(input_dir):
        if f"{RACES_INVERTED.get(race_id)}" in file and file.endswith(".csv"):
            input_file = os.path.join(input_dir, file)
            break

    if input_file is None:
        log(race_id, f" Aucun fichier CSV trouvé pour la course {race_id}.")
        return

    with open(input_file, mode='r', encoding='utf-8') as infile, open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
        reader = csv.DictReader(infile, delimiter=';')
        fieldnames = ['Date', 'Heure', 'HDG', 'Voile']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=',')

        writer.writeheader()
        for row in reader:
            dateheure = add_utc_offset(row['DateHeure(UTC)'], 10).split(" ")
            filtered_row = {
                'Date': dateheure[0],
                'Heure': dateheure[1],
                'HDG': row['HDG'],
                'Voile': row['Voile']
            }
            writer.writerow(filtered_row)

    log(race_id, f" caps_{race_id}.csv créé dans le dossier csv_rdy")

def parse(row):
    date_str, hour_minute_str, heading_str, sail_str = row[0], row[1], row[2], row[3]
    annee_str, mois_str, jour_str = date_str.split("-")
    hour_str, minute_str = hour_minute_str.split(":")
    minute, hour, jour, mois, annee, heading = int(minute_str), int(hour_str), int(jour_str), int(mois_str), int(annee_str), int(heading_str)
    return minute, hour, jour, mois, annee, heading, sail_str

def process_csv(csv_file):
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            yield parse(row)