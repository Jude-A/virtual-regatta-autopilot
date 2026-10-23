# enhanced_gui.py
from tkinter import Frame, Entry, Label, Button, messagebox, scrolledtext, ttk, Tk, Menu
from ttkthemes import ThemedTk
from multiprocessing import Process, Queue, freeze_support
from api.auth import auth
from core.autopilot import run_autopilot
from config import MAIL, MDP, VRZEN_USER_ID
from api.race import get_my_races
from api.vrzen import get_course_names
from utils.logger import register_log_queue, unregister_log_queue
from utils.secure import encrypt_message, decrypt_message
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
CONFIG_PATH = os.path.join(BASE_DIR, "races.json")
AUTOPILOT_PROCS = {}
LOG_QUEUES = {}

AUTH_TOKEN, USER_ID = None, None
ACTIVE_RACE_IDS = set()

def save_race(name, race_id):
    data = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    data[name] = race_id
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def load_races():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def is_running(name):
    # Un autopilote arrivé au bout de sa route se termine tout seul : on l'oublie
    p = AUTOPILOT_PROCS.get(name)
    if p and not p.is_alive():
        del AUTOPILOT_PROCS[name]
        return False
    return p is not None

def sync_active_races():
    """Ajoute à races.json les courses en cours sur le compte VR, sous leur nom VRZen."""
    ACTIVE_RACE_IDS.clear()
    ACTIVE_RACE_IDS.update(r["race_id"] for r in get_my_races(AUTH_TOKEN, USER_ID))
    known = load_races().values()
    missing = [rid for rid in ACTIVE_RACE_IDS if rid not in known]
    if missing:
        vrzen_names = get_course_names(VRZEN_USER_ID)
        for rid in missing:
            if rid in vrzen_names:
                save_race(vrzen_names[rid], rid)

def get_course_state(name, race_id):
    if is_running(name):
        return "✔️"
    # ⏳ : course en cours sur le compte, prête à être routée ; 🏁 : terminée ou pas inscrit
    return "⏳" if race_id in ACTIVE_RACE_IDS else "🏁"

def create_log_tab(notebook, name, queue):
    for tab_id in notebook.tabs():
        if notebook.tab(tab_id, "text") == name:
            notebook.forget(tab_id)
            break
    tab = Frame(notebook)
    notebook.add(tab, text=name)
    notebook.select(tab)

    text_area = scrolledtext.ScrolledText(tab, state="disabled", width=100, height=30)
    text_area.pack(expand=True, fill='both')

    def update_logs():
        try:
            while True:
                msg = queue.get_nowait()
                text_area.config(state="normal")
                text_area.insert('end', msg + "\n")
                text_area.config(state="disabled")
                text_area.yview('end')
        except:
            pass
        tab.after(500, update_logs)

    update_logs()

def start_autopilot(name, race_id, notebook, refresh_callback=None):
    if is_running(name):
        messagebox.showinfo("Déjà en cours", f"L'autopilote pour {name} est déjà lancé.")
        return

    if race_id not in ACTIVE_RACE_IDS:
        sync_active_races()  # course rejointe depuis l'ouverture de l'app ?
    if race_id not in ACTIVE_RACE_IDS:
        messagebox.showwarning("Course inactive", f"{name} n'est pas en cours sur ton compte Virtual Regatta.")
        return

    log_q = Queue()
    register_log_queue(race_id, log_q)
    LOG_QUEUES[name] = log_q
    p = Process(target=run_autopilot, args=(race_id, AUTH_TOKEN, USER_ID, log_q))
    p.start()
    AUTOPILOT_PROCS[name] = p
    create_log_tab(notebook, name, log_q)

    if refresh_callback:
        refresh_callback()

def stop_autopilot(name, refresh_callback=None):
    p = AUTOPILOT_PROCS.get(name)
    if p:
        p.terminate()
        del AUTOPILOT_PROCS[name]
        race_id = load_races().get(name)
        if race_id:
            unregister_log_queue(race_id)
        messagebox.showinfo("Arrêté", f"L'autopilote pour {name} a été stoppé.")
    if refresh_callback:
        refresh_callback()

def open_credentials_editor():
    editor = Tk()
    editor.title("Modifier les identifiants")

    Label(editor, text="Mail:").grid(row=0, column=0, padx=5, pady=5)
    entry_mail = Entry(editor, width=30)
    entry_mail.grid(row=0, column=1, padx=5, pady=5)

    Label(editor, text="Mot de passe:").grid(row=1, column=0, padx=5, pady=5)
    entry_mdp = Entry(editor, show="*", width=30)
    entry_mdp.grid(row=1, column=1, padx=5, pady=5)

    if os.path.exists(CREDENTIALS_PATH):
        with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
            creds = json.load(f)
            entry_mail.insert(0, creds.get("MAIL", ""))
            try:
                entry_mdp.insert(0, decrypt_message(creds.get("MDP", "")))
            except:
                pass

    def save_new_creds():
        mail = entry_mail.get().strip()
        mdp = entry_mdp.get().strip()
        if not mail or not mdp:
            messagebox.showerror("Erreur", "Veuillez remplir les deux champs.")
            return
        with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
            json.dump({"MAIL": mail, "MDP": encrypt_message(mdp)}, f, indent=4)
        global AUTH_TOKEN, USER_ID
        token, uid = auth(mail, mdp)
        if token:
            AUTH_TOKEN, USER_ID = token, uid
            messagebox.showinfo("OK", "Identifiants mis à jour et rechargés.")
            editor.destroy()
        else:
            messagebox.showerror("Erreur", "Échec de l'authentification avec les nouveaux identifiants.")

    Button(editor, text="Sauvegarder", command=save_new_creds).grid(row=2, columnspan=2, pady=10)

def get_credentials_or_prompt():
    global AUTH_TOKEN, USER_ID
    if os.path.exists(CREDENTIALS_PATH):
        try:
            with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
                creds = json.load(f)
                mail = creds.get("MAIL", "")
                mdp = decrypt_message(creds.get("MDP", ""))
                AUTH_TOKEN, USER_ID = auth(mail, mdp)
                if AUTH_TOKEN:
                    return True
        except:
            pass

    login_root = Tk()
    login_root.title("Connexion Virtual Regatta")

    Label(login_root, text="Mail:").grid(row=0, column=0, padx=5, pady=5)
    entry_mail = Entry(login_root, width=30)
    entry_mail.grid(row=0, column=1, padx=5, pady=5)

    Label(login_root, text="Mot de passe:").grid(row=1, column=0, padx=5, pady=5)
    entry_mdp = Entry(login_root, show="*", width=30)
    entry_mdp.grid(row=1, column=1, padx=5, pady=5)

    def try_login():
        mail = entry_mail.get().strip()
        mdp = entry_mdp.get().strip()
        if not mail or not mdp:
            messagebox.showerror("Erreur", "Veuillez remplir les deux champs.")
            return
        token, uid = auth(mail, mdp)
        if token:
            with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
                json.dump({"MAIL": mail, "MDP": encrypt_message(mdp)}, f, indent=4)
            global AUTH_TOKEN, USER_ID
            AUTH_TOKEN, USER_ID = token, uid
            login_root.destroy()
        else:
            messagebox.showerror("Erreur", "Échec de l'authentification")

    Button(login_root, text="Se connecter", command=try_login).grid(row=2, columnspan=2, pady=10)
    login_root.mainloop()

    return AUTH_TOKEN is not None

def main_gui():
    root = ThemedTk(theme="black")
    root.title("🧭 Virtual Regatta - Autopilote")

    menu_bar = Menu(root)
    file_menu = Menu(menu_bar, tearoff=0)
    file_menu.add_command(label="Modifier les identifiants", command=open_credentials_editor)
    file_menu.add_separator()
    file_menu.add_command(label="Quitter", command=root.destroy)
    menu_bar.add_cascade(label="Fichier", menu=file_menu)
    root.config(menu=menu_bar)

    def on_close():
        for name in list(AUTOPILOT_PROCS.keys()):
            stop_autopilot(name)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    notebook = ttk.Notebook(root)
    notebook.grid(row=1, column=0, padx=10, pady=10)

    tab_home = Frame(notebook)
    notebook.add(tab_home, text="Accueil")

    Label(tab_home, text="Nom de course:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
    entry_name = Entry(tab_home)
    entry_name.grid(row=0, column=1, padx=5, pady=3)

    Label(tab_home, text="Race ID:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
    entry_id = Entry(tab_home)
    entry_id.grid(row=1, column=1, padx=5, pady=3)

    Button(tab_home, text="Ajouter la course", command=lambda: ajouter_course()).grid(row=2, columnspan=2, pady=5)

    frame_courses = Frame(tab_home)
    frame_courses.grid(row=3, column=0, columnspan=2, padx=10, pady=10)

    def ajouter_course():
        name = entry_name.get().strip()
        try:
            race_id = int(entry_id.get().strip())
        except ValueError:
            messagebox.showerror("Erreur", "Race ID invalide")
            return
        save_race(name, race_id)
        refresh_courses()

    def refresh_courses():
        for widget in frame_courses.winfo_children():
            widget.destroy()
        races = load_races()
        for i, (name, race_id) in enumerate(races.items()):
            state = get_course_state(name, race_id)
            Label(frame_courses, text=f"{state} {name} (ID: {race_id})").grid(row=i, column=0, sticky="w", padx=5, pady=3)
            Button(frame_courses, text="Lancer", command=lambda n=name, r=race_id: start_autopilot(n, r, notebook, refresh_courses)).grid(row=i, column=1, padx=2)
            Button(frame_courses, text="Stop", command=lambda n=name: stop_autopilot(n, refresh_courses)).grid(row=i, column=2, padx=2)

    sync_active_races()
    refresh_courses()

    for name, race_id in load_races().items():
        if get_course_state(name, race_id) == "⏳":
            start_autopilot(name, race_id, notebook)
            refresh_courses()

    root.mainloop()

if __name__ == "__main__":
    freeze_support()
    if get_credentials_or_prompt():
        main_gui()
