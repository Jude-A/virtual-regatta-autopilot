# utils/csv_utils.py
import csv
import json
import os
from utils.time_utils import parse_utc
from utils.logger import log

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_COPIER_PATH = os.path.join(BASE_DIR, "csv", "csv_copier")
CSV_RDY_PATH = os.path.join(BASE_DIR, "csv", "csv_rdy")
RACES_PATH = os.path.join(BASE_DIR, "races.json")
os.makedirs(CSV_COPIER_PATH, exist_ok=True)
os.makedirs(CSV_RDY_PATH, exist_ok=True)

def race_name(race_id):
    # Relu à chaque appel : une course ajoutée depuis la GUI doit être trouvée sans redémarrer
    try:
        with open(RACES_PATH, "r", encoding="utf-8") as f:
            races = json.load(f)
    except (OSError, ValueError):
        return None
    return next((name for name, rid in races.items() if rid == race_id), None)

def find_source_csv(race_id):
    name = race_name(race_id)
    if not name:
        return None
    files = [f for f in os.listdir(CSV_COPIER_PATH) if f.endswith(".csv")]
    # Fichier copié par "Importer CSV" en priorité, sinon un export VRZen déposé à la main
    exact = f"{name}_{race_id}.csv"
    if exact in files:
        return os.path.join(CSV_COPIER_PATH, exact)
    match = next((f for f in files if name in f), None)
    return os.path.join(CSV_COPIER_PATH, match) if match else None

def parsee(race_id):
    output_file = os.path.join(CSV_RDY_PATH, f"caps_{race_id}.csv")
    input_file = find_source_csv(race_id)

    if input_file is None:
        log(race_id, f" Aucun fichier CSV trouvé pour la course {race_id}.")
        return

    # Les heures restent en UTC : la conversion en heure locale se fait à l'affichage,
    # ce qui évite les décalages selon le fuseau du PC et les changements d'heure.
    with open(input_file, mode='r', encoding='utf-8-sig') as infile, open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
        reader = csv.DictReader(infile, delimiter=';')
        fieldnames = ['DateHeure(UTC)', 'HDG', 'Voile']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=',')

        writer.writeheader()
        for row in reader:
            if not row.get('DateHeure(UTC)') or not row.get('HDG'):
                continue
            writer.writerow({
                'DateHeure(UTC)': row['DateHeure(UTC)'],
                'HDG': row['HDG'],
                'Voile': (row.get('Voile') or "").strip()
            })

    log(race_id, f" caps_{race_id}.csv créé dans le dossier csv_rdy")

def parse(row):
    """-> (datetime UTC, cap en degrés, voile ou '' si non précisée)"""
    return parse_utc(row[0]), int(float(row[1].replace(",", "."))), row[2]

def process_csv(csv_file):
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            yield parse(row)

def write_route_csv(race_id, rows):
    """Écrit une route [(DateHeure UTC, cap, voile)] au format d'export VRZen,
    comme si elle avait été importée à la main."""
    path = os.path.join(CSV_COPIER_PATH, f"{race_name(race_id)}_{race_id}.csv")
    with open(path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['DateHeure(UTC)', 'HDG', 'Voile'])
        writer.writerows(rows)
