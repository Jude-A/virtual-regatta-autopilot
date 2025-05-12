import os
import sys
import win32com.client

# === CONFIGURATION ===
script_path = os.path.abspath("gui.py")  # Chemin vers ton script principal

#python_path = sys.executable
python_path = sys.executable.replace("python.exe", "pythonw.exe")

desktop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
shortcut_path = os.path.join(desktop, 'VirtualRegatta.lnk')
icon_path = os.path.abspath("autopilot.ico")

# === CRÉATION DU RACCOURCI ===
shell = win32com.client.Dispatch("WScript.Shell")
shortcut = shell.CreateShortCut(shortcut_path)
shortcut.Targetpath = python_path
shortcut.Arguments = f'"{script_path}"'
shortcut.WorkingDirectory = os.path.dirname(script_path)
shortcut.IconLocation = python_path  # Utilise l'icône de Python
shortcut.save()

print(f"✅ Raccourci créé sur le bureau : {shortcut_path}")
