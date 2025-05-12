# gui.spec

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

BASE_DIR = Path(os.getcwd())

datas = [
    # JSON dans le dossier de l'exécutable
    ("races.json", "."),
    ("credentials.json", "."),
    # Icône dans le même dossier que l'exe
    ("../autopilot.ico", "."),
]

# Ajout des fichiers CSV manuellement
CSV_COPIER = BASE_DIR / "csv" / "csv_copier"
CSV_RDY = BASE_DIR / "csv" / "csv_rdy"

for file in CSV_COPIER.glob("*"):
    if file.is_file():
        datas.append((str(file), f"csv/csv_copier/"))

for file in CSV_RDY.glob("*"):
    if file.is_file():
        datas.append((str(file), f"csv/csv_rdy/"))

a = Analysis(
    ['gui.py'],
    pathex=[str(BASE_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules('utils') +
                   collect_submodules('api') +
                   collect_submodules('core'),
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VirtualRegattaAutopilot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=os.path.abspath("../autopilot.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='VirtualRegattaAutopilot'
)
