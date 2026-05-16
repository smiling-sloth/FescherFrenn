import tkinter as tk
from tkinter import ttk, Toplevel, messagebox, filedialog
from tkcalendar import DateEntry
import json
import os
from datetime import datetime
import getpass
import logging
import re
import webbrowser

try:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, PageBreak, Image
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.units import inch
except ImportError:
    pass

TEMP_DATA_FILE = "temp_fishing_data.json"
BACKUP_DIR = os.path.expanduser("~/FescherfrennData/backups")
APP_VERSION = "1.2"

# Set up logging
logging.basicConfig(filename='fescherfrenn.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

TRANSLATIONS_FILE = "translations.json"
SESSION_KEYS = ["manche1", "manche2", "manche3", "final"]


def _resource_path(name):
    """Locate a bundled resource whether running from source or a PyInstaller bundle."""
    import sys
    if hasattr(sys, "_MEIPASS"):
        candidate = os.path.join(sys._MEIPASS, name)
        if os.path.exists(candidate):
            return candidate
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(here, name)
    if os.path.exists(candidate):
        return candidate
    return name


def load_translations():
    path = _resource_path(TRANSLATIONS_FILE)
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception as exc:
        logging.error(f"Failed to load translations from {path}: {exc}")
        messagebox.showerror(
            "Error",
            f"Cannot load '{TRANSLATIONS_FILE}'. Place it next to the application.\n\n{exc}"
        )
        raise


LANGUAGES = load_translations()


def empty_sessions():
    return {k: {"participants": [], "catches": {}} for k in SESSION_KEYS}


def migrate_data(data):
    """Bring older v1.x and v2.0 (auto-assign) data up to the v2.1 schema in place."""
    if not isinstance(data, dict):
        return {"event": {}, "participants": {}, "sessions": empty_sessions(),
                "lang": "English", "version": APP_VERSION}
    data.setdefault("event", {})
    data.setdefault("participants", {})
    for name in list(data["participants"].keys()):
        rec = data["participants"][name]
        if not isinstance(rec, dict):
            data["participants"][name] = {"id": rec, "club": "", "category": "", "remark": ""}
        else:
            rec.setdefault("id", 0)
            rec.setdefault("club", "")
            rec.setdefault("category", "")
            rec.setdefault("remark", "")

    # Detect a v1.x save: it carries a flat "catches" dict (possibly empty).
    is_v1 = "catches" in data
    flat_catches = data.pop("catches", None)

    if "sessions" not in data or not isinstance(data["sessions"], dict):
        data["sessions"] = empty_sessions()
    for key in SESSION_KEYS:
        sess = data["sessions"].get(key)
        if not isinstance(sess, dict):
            sess = {"participants": [], "catches": {}}
        sess.setdefault("participants", [])
        sess.setdefault("catches", {})
        data["sessions"][key] = sess

    if is_v1:
        # Everything from a v1.x event lived in a single session: fold it into Manche 1
        # and assume every roster member fished in it.
        m1 = data["sessions"]["manche1"]
        if isinstance(flat_catches, dict):
            for name, catches in flat_catches.items():
                if name not in m1["participants"]:
                    m1["participants"].append(name)
                m1["catches"].setdefault(name, []).extend(catches)
        for name in data["participants"]:
            if name not in m1["participants"]:
                m1["participants"].append(name)
            m1["catches"].setdefault(name, [])

    # Ensure every assigned manche participant has a catch list.
    for key in SESSION_KEYS:
        for name in data["sessions"][key]["participants"]:
            data["sessions"][key]["catches"].setdefault(name, [])

    # Normalise individual catch records.
    for key in SESSION_KEYS:
        for catches in data["sessions"][key]["catches"].values():
            for c in catches:
                c.setdefault("num_catches", 1)
                c.setdefault("length", None)
                c.setdefault("type", "")
                c.setdefault("time", "")

    data.setdefault("lang", "English")
    data["version"] = APP_VERSION
    return data


def get_event_folder(event):
    """Helper function to construct event folder path and filename."""
    if not event or not all(event.values()):
        return f"{datetime.now().strftime('%Y%m%d')}_event"
    event_name = str(event.get("name", "event")).replace(" ", "_")
    event_date = str(event.get("date", datetime.now().strftime("%d/%m/%Y")))
    try:
        date_obj = datetime.strptime(event_date, "%d/%m/%Y")
        date_str = date_obj.strftime("%Y%m%d")
    except ValueError:
        date_str = datetime.now().strftime("%Y%m%d")
    return f"{date_str}_{event_name}"

def load_data(event=None):
    """Load data from the event-specific folder if available, else the temp file."""
    try:
        if event and all(event.values()):
            folder_name = get_event_folder(event)
            data_file = os.path.join(folder_name, f"{folder_name}.json")
            if os.path.exists(data_file):
                with open(data_file, 'r', encoding='utf-8') as file:
                    return migrate_data(json.load(file))
        if os.path.exists(TEMP_DATA_FILE):
            with open(TEMP_DATA_FILE, 'r', encoding='utf-8') as file:
                return migrate_data(json.load(file))
    except Exception as e:
        logging.error(f"load_data failed: {str(e)}")
    return {"event": {}, "participants": {}, "sessions": empty_sessions(),
            "lang": "English", "version": APP_VERSION}

def save_data(data, event=None):
    """Save data to event-specific folder with dynamic filename, fallback to user directory."""
    try:
        data["version"] = APP_VERSION
        if event and all(event.values()):
            folder_name = get_event_folder(event)
            data_file = os.path.join(folder_name, f"{folder_name}.json")
            try:
                os.makedirs(folder_name, exist_ok=True)
                with open(data_file, 'w', encoding='utf-8') as file:
                    json.dump(data, file, indent=4, ensure_ascii=False)
                try:
                    os.makedirs(BACKUP_DIR, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_file = os.path.join(BACKUP_DIR, f"backup_{folder_name}_{timestamp}.json")
                    with open(backup_file, 'w', encoding='utf-8') as file:
                        json.dump(data, file, indent=4, ensure_ascii=False)
                except Exception as e:
                    logging.error(f"Backup failed: {str(e)}")
                return
            except PermissionError:
                messagebox.showerror("Error", LANGUAGES[data.get("lang", "English")]["permission_error"].replace("[folder]", folder_name))
        fallback_dir = os.path.expanduser("~/FescherfrennData")
        data_file = os.path.join(fallback_dir, TEMP_DATA_FILE)
        try:
            os.makedirs(fallback_dir, exist_ok=True)
            with open(data_file, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
            try:
                os.makedirs(BACKUP_DIR, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = os.path.join(BACKUP_DIR, f"backup_temp_{timestamp}.json")
                with open(backup_file, 'w', encoding='utf-8') as file:
                    json.dump(data, file, indent=4, ensure_ascii=False)
            except Exception as e:
                logging.error(f"Backup failed: {str(e)}")
        except Exception:
            messagebox.showerror("Error", LANGUAGES[data.get("lang", "English")]["error"])
    except Exception as e:
        logging.error(f"save_data failed: {str(e)}")
        messagebox.showerror("Error", LANGUAGES[data.get("lang", "English")]["error"])

def session_display(lang):
    return [LANGUAGES[lang]["manche_1"], LANGUAGES[lang]["manche_2"],
            LANGUAGES[lang]["manche_3"], LANGUAGES[lang]["final"]]


def key_to_display(lang, key):
    return dict(zip(SESSION_KEYS, session_display(lang))).get(key, key)


def display_to_key(lang, disp):
    return dict(zip(session_display(lang), SESSION_KEYS)).get(disp, "manche1")


class FishingApp:
    def __init__(self, root):
        self.root = root
        try:
            self.data = load_data()
            self.lang = self.data.get("lang", "English")
            self.data["lang"] = self.lang
            self.root.title(LANGUAGES[self.lang]["title"])
            try:
                self.root.iconbitmap("logo.ico")
            except tk.TclError:
                logging.warning("logo.ico not found, using default icon")
            
            self.root.state('zoomed')
            self.root.minsize(1360, 768)
            screen_width = self.root.winfo_screenwidth()
            self.font_size = 12 if screen_width <= 1366 else 16

            # Tracks the manche currently shown in the main UI.
            self.current_manche = "manche1"
            # ttk styling for Treeviews used in the manager / catch editor.
            try:
                _style = ttk.Style()
                _style.configure("Treeview", font=("Arial", max(9, self.font_size - 4)),
                                 rowheight=int(self.font_size * 1.9))
                _style.configure("Treeview.Heading",
                                 font=("Arial", max(9, self.font_size - 4), "bold"))
            except Exception as _e:
                logging.warning(f"Treeview styling failed: {_e}")

            self.rankings = None
            self.manche_participants_list = None
            self.manche_var = None
            self.manche_combo = None
            self.manche_pf = None
            self.manage_btn = None
            self.edit_catches_btn = None
            self.catch_name = None
            self.catch_name_var = None
            self.report_btn = None
            self.reset_btn = None
            self.export_btn = None
            self.import_btn = None
            self.help_btn = None
            self.catch_name_var = None  # Added for Combobox hint

            self.canvas = tk.Canvas(self.root)
            self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
            self.main_frame = ttk.Frame(self.canvas)
            self.canvas.configure(yscrollcommand=self.scrollbar.set)
            self.canvas.pack(side="left", fill="both", expand=True)
            self.scrollbar.pack(side="right", fill="y")
            self.canvas_frame = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
            self.main_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
            self.root.bind("<Configure>", self.on_resize)

            try:
                self.logo = tk.PhotoImage(file="logo.png")
                self.logo_label = ttk.Label(self.main_frame, image=self.logo)
                self.logo_label.grid(row=0, column=0, pady=5, padx=5, sticky="nw")
            except Exception:
                self.logo_label = ttk.Label(self.main_frame, text="Logo Placeholder (200x200px)", width=28, anchor="center")
                self.logo_label.grid(row=0, column=0, pady=5, padx=5, sticky="nw")

            self.lang_frame = ttk.Frame(self.main_frame)
            self.lang_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky="ew")
            ttk.Label(self.lang_frame, text=LANGUAGES[self.lang]["select_lang"], font=("Arial", self.font_size)).pack()
            ttk.Button(self.lang_frame, text="English", command=lambda: self.set_language("English")).pack(side=tk.LEFT, padx=5)
            ttk.Button(self.lang_frame, text="Français", command=lambda: self.set_language("French")).pack(side=tk.LEFT, padx=5)
            ttk.Button(self.lang_frame, text="Deutsch", command=lambda: self.set_language("German")).pack(side=tk.LEFT, padx=5)
            ttk.Button(self.lang_frame, text="Lëtzebuergesch", command=lambda: self.set_language("Luxembourgish")).pack(side=tk.LEFT, padx=5)

            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        except Exception as e:
            logging.error(f"Initialization failed: {str(e)}")
            messagebox.showerror("Error", f"Failed to start application: {str(e)}")
            self.root.destroy()

    def on_resize(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=self.canvas.winfo_width())

    def set_language(self, lang):
        self.lang = lang
        self.data["lang"] = lang
        self.root.title(LANGUAGES[self.lang]["title"])
        self.lang_frame.grid_forget()
        self.build_main_ui()

    def validate_number(self, input_str):
        if input_str == "":
            return True
        if self.lang in ["French", "German", "Luxembourgish"]:
            input_str = input_str.replace(",", ".")
        return bool(re.match(r"^\d*\.?\d*$", input_str))

    def validate_catches(self, input_str):
        if input_str == "":
            return True
        return bool(re.match(r"^\d+$", input_str))

    def validate_length(self, input_str):
        """Validate input length for club and remark (max 64 chars)."""
        return len(input_str) <= 64

    def check_event_details(self):
        if not self.event_name.get().strip() or not self.location.get().strip():
            messagebox.showerror("Error", LANGUAGES[self.lang]["event_error"])
            return False
        return True

    def build_main_ui(self):
        L = LANGUAGES[self.lang]
        for widget in self.main_frame.winfo_children():
            if widget != self.logo_label:
                widget.destroy()

        self.main_frame.columnconfigure(0, weight=1, minsize=430)
        self.main_frame.columnconfigure(1, weight=1, minsize=430)
        self.main_frame.rowconfigure(0, weight=0)
        self.main_frame.rowconfigure(1, weight=1)
        self.main_frame.rowconfigure(2, weight=0)

        left_frame = ttk.Frame(self.main_frame)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=3, pady=3)

        # -- Event details + Manche selector --
        event_frame = ttk.LabelFrame(left_frame, text=L["event_details"], padding=5)
        event_frame.pack(fill="x")
        event_frame.columnconfigure(1, weight=1)
        ttk.Label(event_frame, text=L["event_name"], font=("Arial", self.font_size)).grid(row=0, column=0, pady=3, sticky="w")
        self.event_name = ttk.Entry(event_frame, font=("Arial", self.font_size), width=22)
        self.event_name.grid(row=0, column=1, pady=3, sticky="ew")
        ttk.Label(event_frame, text=L["location"], font=("Arial", self.font_size)).grid(row=1, column=0, pady=3, sticky="w")
        self.location = ttk.Entry(event_frame, font=("Arial", self.font_size), width=22)
        self.location.grid(row=1, column=1, pady=3, sticky="ew")
        ttk.Label(event_frame, text=L["date"], font=("Arial", self.font_size)).grid(row=2, column=0, pady=3, sticky="w")
        self.date = DateEntry(event_frame, font=("Arial", self.font_size), date_pattern="dd/mm/yyyy", width=12)
        self.date.grid(row=2, column=1, pady=3, sticky="w")
        self.date.set_date(datetime.now())
        ttk.Label(event_frame, text=L["manche_label"], font=("Arial", self.font_size)).grid(row=3, column=0, pady=3, sticky="w")
        self.manche_var = tk.StringVar()
        self.manche_combo = ttk.Combobox(event_frame, textvariable=self.manche_var, state="readonly",
                                         values=session_display(self.lang),
                                         font=("Arial", self.font_size), width=18)
        self.manche_combo.grid(row=3, column=1, pady=3, sticky="w")
        self.manche_combo.set(key_to_display(self.lang, self.current_manche))
        self.manche_combo.bind("<<ComboboxSelected>>", self.on_manche_changed)
        self.manage_btn = ttk.Button(event_frame, text=L["manage_participants"], command=self.open_participants_manager)
        self.manage_btn.grid(row=4, column=0, columnspan=2, pady=(6, 2), sticky="ew")

        if self.data["event"]:
            self.event_name.insert(0, self.data["event"].get("name", ""))
            self.location.insert(0, self.data["event"].get("location", ""))
            date_str = self.data["event"].get("date", datetime.now().strftime("%d/%m/%Y"))
            try:
                self.date.set_date(date_str)
            except ValueError:
                self.date.set_date(datetime.now())
            self.event_name.config(state="disabled")
            self.location.config(state="disabled")
            self.date.config(state="disabled")

        # -- Log catch --
        catch_frame = ttk.LabelFrame(left_frame, text=L["log_catch"], padding=5)
        catch_frame.pack(fill="x", pady=6)
        catch_frame.columnconfigure(1, weight=1)
        ttk.Label(catch_frame, text=L["name"], font=("Arial", self.font_size)).grid(row=0, column=0, pady=3, sticky="w")
        self.catch_name_var = tk.StringVar()
        self.catch_name = ttk.Combobox(catch_frame, textvariable=self.catch_name_var,
                                       values=self.current_manche_participants(),
                                       font=("Arial", self.font_size), width=20)
        self.catch_name.grid(row=0, column=1, pady=3, sticky="ew")
        self.catch_name_var.set(L["select_participant"])
        self.catch_name.config(foreground='grey')
        self.catch_name.bind("<FocusIn>", self.on_combobox_focus_in)
        self.catch_name.bind("<FocusOut>", self.on_combobox_focus_out)
        self.catch_name.bind("<<ComboboxSelected>>", self.on_combobox_selected)
        ttk.Label(catch_frame, text=L["fish_weight"], font=("Arial", self.font_size)).grid(row=1, column=0, pady=3, sticky="w")
        self.fish_weight = ttk.Entry(catch_frame, font=("Arial", self.font_size), width=18, validate="key",
                                     validatecommand=(self.root.register(self.validate_number), "%P"))
        self.fish_weight.grid(row=1, column=1, pady=3, sticky="ew")
        ttk.Label(catch_frame, text=L["num_catches"], font=("Arial", self.font_size)).grid(row=2, column=0, pady=3, sticky="w")
        self.num_catches = ttk.Entry(catch_frame, font=("Arial", self.font_size), width=18, validate="key",
                                     validatecommand=(self.root.register(self.validate_catches), "%P"))
        self.num_catches.grid(row=2, column=1, pady=3, sticky="ew")
        self.num_catches.insert(0, "1")
        ttk.Label(catch_frame, text=L["fish_length"], font=("Arial", self.font_size)).grid(row=3, column=0, pady=3, sticky="w")
        self.fish_length = ttk.Entry(catch_frame, font=("Arial", self.font_size), width=18, validate="key",
                                     validatecommand=(self.root.register(self.validate_number), "%P"))
        self.fish_length.grid(row=3, column=1, pady=3, sticky="ew")
        ttk.Label(catch_frame, text=L["fish_type"], font=("Arial", self.font_size)).grid(row=4, column=0, pady=3, sticky="w")
        self.fish_type = ttk.Entry(catch_frame, font=("Arial", self.font_size), width=18)
        self.fish_type.grid(row=4, column=1, pady=3, sticky="ew")
        self.log_btn = ttk.Button(catch_frame, text=L["log_catch"], command=self.log_catch)
        self.log_btn.grid(row=5, column=1, pady=5, sticky="e")
        self.edit_catches_btn = ttk.Button(catch_frame, text=L["edit_catches"], command=self.open_catch_editor)
        self.edit_catches_btn.grid(row=5, column=0, pady=5, sticky="w")

        # -- Right column: rankings + manche participants --
        right_frame = ttk.Frame(self.main_frame)
        right_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=3, pady=3)

        rankings_frame = ttk.LabelFrame(right_frame, text=L["live_rankings"], padding=5)
        rankings_frame.pack(fill="both", expand=True)
        self.rankings = ttk.Label(rankings_frame, text=self.get_rankings(self.current_manche),
                                  font=("Arial", self.font_size - 2), justify="left", wraplength=420)
        self.rankings.pack(fill="both", expand=True)

        btn_frame = ttk.Frame(rankings_frame)
        btn_frame.pack(fill="x", pady=3)
        self.report_btn = ttk.Button(btn_frame, text=L["generate_report"], command=self.generate_report)
        self.report_btn.pack(side=tk.LEFT, padx=3)
        self.reset_btn = ttk.Button(btn_frame, text=L["reset_event"], command=self.reset_event)
        self.reset_btn.pack(side=tk.LEFT, padx=3)
        self.export_btn = ttk.Button(btn_frame, text=L["export_event"], command=self.export_event)
        self.export_btn.pack(side=tk.LEFT, padx=3)
        self.import_btn = ttk.Button(btn_frame, text=L["import_event"], command=self.import_event)
        self.import_btn.pack(side=tk.LEFT, padx=3)
        self.help_btn = ttk.Button(btn_frame, text=L["help"], command=self.show_help)
        self.help_btn.pack(side=tk.LEFT, padx=3)

        self.manche_pf = ttk.LabelFrame(
            right_frame,
            text=f'{L["participants"]} - {key_to_display(self.lang, self.current_manche)}', padding=5)
        self.manche_pf.pack(fill="x", pady=3)
        participants_canvas = tk.Canvas(self.manche_pf, height=180)
        participants_scrollbar = ttk.Scrollbar(self.manche_pf, orient="vertical", command=participants_canvas.yview)
        self.manche_participants_list = tk.Text(participants_canvas, height=8, width=30,
                                                font=("Arial", self.font_size - 2))
        participants_canvas.configure(yscrollcommand=participants_scrollbar.set)
        participants_scrollbar.pack(side="right", fill="y")
        participants_canvas.pack(side="left", fill="both", expand=True)
        participants_canvas.create_window((0, 0), window=self.manche_participants_list, anchor="nw")
        self.manche_participants_list.bind(
            "<Configure>", lambda e: participants_canvas.configure(scrollregion=participants_canvas.bbox("all")))
        self.update_manche_participants_list()

        # -- Footer --
        footer_frame = ttk.Frame(self.main_frame)
        footer_frame.grid(row=2, column=0, columnspan=2, pady=5, sticky="s")
        if "fescherfrenn@outlook.com" in L["copyright"]:
            before, after = L["copyright"].split("fescherfrenn@outlook.com", 1)
            ttk.Label(footer_frame, text=before, font=("Arial", self.font_size - 4)).pack(side=tk.LEFT)
            email_label = tk.Label(footer_frame, text="fescherfrenn@outlook.com",
                                   font=("Arial", self.font_size - 4), foreground="blue", cursor="hand2")
            email_label.pack(side=tk.LEFT)
            email_label.bind("<Button-1>", lambda e: webbrowser.open("mailto:fescherfrenn@outlook.com"))
            ttk.Label(footer_frame, text=after, font=("Arial", self.font_size - 4)).pack(side=tk.LEFT)
        else:
            ttk.Label(footer_frame, text=L["copyright"], font=("Arial", self.font_size - 4)).pack(side=tk.LEFT)

        # -- Tooltips --
        self.create_tooltip(self.manage_btn, L["tooltip_manage"])
        self.create_tooltip(self.log_btn, L["tooltip_log"])
        self.create_tooltip(self.edit_catches_btn, L["tooltip_edit_catches"])
        self.create_tooltip(self.report_btn, L["tooltip_report"])
        self.create_tooltip(self.reset_btn, L["tooltip_reset"])
        self.create_tooltip(self.export_btn, L["tooltip_export"])
        self.create_tooltip(self.import_btn, L["tooltip_import"])
        self.create_tooltip(self.help_btn, L["tooltip_help"])

    def on_combobox_focus_in(self, event):
        if self.catch_name_var.get() == LANGUAGES[self.lang]["select_participant"]:
            self.catch_name_var.set('')
            self.catch_name.config(foreground='black')

    def on_combobox_focus_out(self, event):
        if not self.catch_name_var.get():
            self.catch_name_var.set(LANGUAGES[self.lang]["select_participant"])
            self.catch_name.config(foreground='grey')

    def on_combobox_selected(self, event):
        self.catch_name.config(foreground='black')

    def create_tooltip(self, widget, text):
        tooltip = tk.Toplevel(self.root)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry("+0+0")
        label = ttk.Label(tooltip, text=text, background="lightyellow", relief="solid", borderwidth=1)
        label.pack()
        tooltip.withdraw()

        def show(event):
            x, y = event.widget.winfo_rootx() + 20, event.widget.winfo_rooty() + 20
            tooltip.wm_geometry(f"+{x}+{y}")
            tooltip.deiconify()

        def hide(event):
            tooltip.withdraw()

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    def show_help(self):
        help_window = Toplevel(self.root)
        help_window.title(LANGUAGES[self.lang]["help"])
        help_window.geometry("600x400")
        help_window.transient(self.root)
        help_window.grab_set()

        canvas = tk.Canvas(help_window)
        scrollbar = ttk.Scrollbar(help_window, orient="vertical", command=canvas.yview)
        help_frame = ttk.Frame(canvas)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.create_window((0, 0), window=help_frame, anchor="nw")
        help_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        ttk.Label(help_frame, text=LANGUAGES[self.lang]["help_manual"], font=("Arial", self.font_size-2), wraplength=550, justify="left").pack(padx=5, pady=5)
        email_label = tk.Label(help_frame, text="fescherfrenn@outlook.com", font=("Arial", self.font_size-2), foreground="blue", cursor="hand2")
        email_label.pack(anchor="w", padx=5)
        email_label.bind("<Button-1>", lambda e: webbrowser.open("mailto:fescherfrenn@outlook.com"))

        close_btn = ttk.Button(help_frame, text=LANGUAGES[self.lang]["close"], command=help_window.destroy)
        close_btn.pack(pady=5)
        help_window.bind("<Return>", lambda e: help_window.destroy())

    def update_manche_participants_list(self):
        if not self.manche_participants_list:
            return
        L = LANGUAGES[self.lang]
        self.manche_participants_list.config(state="normal")
        self.manche_participants_list.delete(1.0, tk.END)
        parts = self.current_manche_participants()
        if not parts:
            self.manche_participants_list.insert(tk.END, L["no_manche_participants"])
        else:
            for i, name in enumerate(parts, 1):
                info = self.data["participants"].get(name, {})
                cat_key = info.get("category", "")
                cat_disp = L["category_options"].get(cat_key, cat_key)
                extra = f" ({cat_disp})" if cat_disp else ""
                self.manche_participants_list.insert(tk.END, f"{i}. {name}{extra}\n")
        self.manche_participants_list.config(state="disabled")

    def log_catch(self):
        if not self.check_event_details():
            return
        L = LANGUAGES[self.lang]
        name = self.catch_name_var.get().strip()
        fish_type = self.fish_type.get().strip()
        num_catches_str = self.num_catches.get()
        try:
            weight_str = self.fish_weight.get()
            length_str = self.fish_length.get()
            if not weight_str or float(weight_str.replace(",", ".")) <= 0:
                messagebox.showerror("Error", L["invalid_number"])
                return
            if not num_catches_str or int(num_catches_str) < 1:
                messagebox.showerror("Error", L["invalid_catches"])
                return
            if name == L["select_participant"] or not name:
                messagebox.showerror("Error", L["error"])
                return
            if name not in self.data["participants"]:
                messagebox.showerror("Error", L["duplicate_name"])
                return
            if name not in self.data["sessions"][self.current_manche]["participants"]:
                messagebox.showerror("Error", L["error"])
                return
            weight = float(weight_str.replace(",", "."))
            num_catches = int(num_catches_str)
            length = (float(length_str.replace(",", "."))
                      if length_str and float(length_str.replace(",", ".")) > 0
                      else None)
            if num_catches > 1:
                fish_type = ""
                length = None
            catch = {"weight": weight, "length": length, "type": fish_type,
                     "time": datetime.now().strftime("%H:%M"), "num_catches": num_catches}
            self.data["sessions"][self.current_manche]["catches"].setdefault(name, []).append(catch)
            self.fish_type.delete(0, tk.END)
            self.fish_weight.delete(0, tk.END)
            self.fish_length.delete(0, tk.END)
            self.num_catches.delete(0, tk.END)
            self.num_catches.insert(0, "1")
            self.catch_name_var.set('')
            self.on_combobox_focus_out(None)
            self.rankings.config(text=self.get_rankings(self.current_manche))
            self.update_event()
            messagebox.showinfo("Success", L["saved"])
        except ValueError:
            messagebox.showerror("Error", L["invalid_number"])

    def update_event(self):
        self.data["event"] = {"name": self.event_name.get(), "location": self.location.get(), "date": self.date.get()}
        if all(self.data["event"].values()):
            self.event_name.config(state="disabled")
            self.location.config(state="disabled")
            self.date.config(state="disabled")
        try:
            save_data(self.data, self.data["event"])
        except Exception as e:
            logging.error(f"update_event failed: {str(e)}")
            messagebox.showerror("Error", LANGUAGES[self.lang]["error"])

    def fmt_weight(self, value):
        """Format a weight (in grams) as a whole number, localised for the UI language."""
        s = f"{value:,.0f}"
        if self.lang in ["French", "German", "Luxembourgish"]:
            s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return s

    def get_rankings(self, manche_key=None):
        L = LANGUAGES[self.lang]
        if manche_key is None:
            manche_key = self.current_manche
        sess_label = key_to_display(self.lang, manche_key)
        rankings = f'{L["live_rankings"]} - {sess_label}:\n\n'
        _catches_dict = self.data["sessions"][manche_key]["catches"]

        total_weights = {name: sum(c["weight"] for c in catches)
                         for name, catches in _catches_dict.items()}
        top_weights = sorted(total_weights.items(), key=lambda x: x[1], reverse=True)[:3]
        rankings += f"{L['total_weight']}:\n"
        for i, (name, weight) in enumerate(top_weights, 1):
            rankings += f"{i}. {name}: {self.fmt_weight(weight)} g\n"
        all_catches = [(name, catch) for name, catches in _catches_dict.items()
                       for catch in catches if catch["num_catches"] == 1]
        top_lengths = sorted(all_catches, key=lambda x: x[1]["length"] or 0, reverse=True)[:3]
        rankings += f"\n{L['longest_fish']}:\n"
        for i, (name, catch) in enumerate(top_lengths, 1):
            rankings += f"{i}. {name}: {catch['length'] or 0} cm\n"
        top_heaviest = sorted(all_catches, key=lambda x: x[1]["weight"], reverse=True)[:3]
        rankings += f"\n{L['heaviest_fish']}:\n"
        for i, (name, catch) in enumerate(top_heaviest, 1):
            rankings += f"{i}. {name}: {self.fmt_weight(catch['weight'])} g\n"
        num_catches = {name: sum(c["num_catches"] for c in catches)
                       for name, catches in _catches_dict.items()}
        top_catches = sorted(num_catches.items(), key=lambda x: x[1], reverse=True)[:3]
        rankings += f"\n{L['num_catches_label']}:\n"
        for i, (name, count) in enumerate(top_catches, 1):
            rankings += f"{i}. {name}: {count} catches\n"
        return rankings

    # -- formatting helper for editable numbers ---------------------
    def num_to_str(self, value):
        if value is None:
            return ""
        try:
            fv = float(value)
        except (TypeError, ValueError):
            return str(value)
        s = str(int(fv)) if fv.is_integer() else repr(fv)
        if self.lang in ["French", "German", "Luxembourgish"]:
            s = s.replace(".", ",")
        return s

    # -- manche helpers --------------------------------------------
    def current_manche_participants(self):
        return sorted(self.data["sessions"][self.current_manche]["participants"], key=str.lower)

    def on_manche_changed(self, event=None):
        self.current_manche = display_to_key(self.lang, self.manche_var.get())
        self.refresh_manche_view()

    def refresh_manche_view(self):
        L = LANGUAGES[self.lang]
        if self.catch_name is not None:
            self.catch_name["values"] = self.current_manche_participants()
            self.catch_name_var.set(L["select_participant"])
            self.catch_name.config(foreground='grey')
        if self.rankings is not None:
            self.rankings.config(text=self.get_rankings(self.current_manche))
        if self.manche_pf is not None:
            self.manche_pf.config(
                text=f'{L["participants"]} - {key_to_display(self.lang, self.current_manche)}')
        self.update_manche_participants_list()

    # -- participant rename across all sessions --------------------
    def rename_participant(self, old, new):
        if old == new:
            return
        self.data["participants"][new] = self.data["participants"].pop(old)
        for sk in SESSION_KEYS:
            sess = self.data["sessions"][sk]
            if old in sess["participants"]:
                sess["participants"] = [new if p == old else p for p in sess["participants"]]
            if old in sess["catches"]:
                sess["catches"][new] = sess["catches"].pop(old)

    # -- Manage Participants window --------------------------------
    def open_participants_manager(self):
        if not self.check_event_details():
            return
        self.update_event()  # lock event details once we touch the roster
        L = LANGUAGES[self.lang]

        win = Toplevel(self.root)
        win.title(L["manage_participants"])
        win.transient(self.root)
        win.grab_set()
        win.geometry("980x560")

        container = ttk.Frame(win, padding=10)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.columnconfigure(2, weight=1)
        container.rowconfigure(0, weight=1)

        # Left: full roster
        left = ttk.LabelFrame(container, text=L["competition_roster"], padding=6)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        roster_tv = ttk.Treeview(left, columns=("club", "cat"), show="tree headings",
                                 height=14, selectmode="extended")
        roster_tv.heading("#0", text=L["name"].rstrip(":"))
        roster_tv.heading("club", text=L["table_club"])
        roster_tv.heading("cat", text=L["table_category"])
        roster_tv.column("#0", width=180, anchor="w")
        roster_tv.column("club", width=120, anchor="w")
        roster_tv.column("cat", width=100, anchor="w")
        roster_sb = ttk.Scrollbar(left, orient="vertical", command=roster_tv.yview)
        roster_tv.configure(yscrollcommand=roster_sb.set)
        roster_sb.pack(side="right", fill="y")
        roster_tv.pack(side="top", fill="both", expand=True)
        roster_btns = ttk.Frame(left)
        roster_btns.pack(side="bottom", fill="x", pady=(6, 0))

        # Middle: transfer buttons
        mid = ttk.Frame(container)
        mid.grid(row=0, column=1, padx=6)

        # Right: current manche's participants
        right = ttk.LabelFrame(
            container,
            text=L["in_manche"].format(manche=key_to_display(self.lang, self.current_manche)),
            padding=6)
        right.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        manche_tv = ttk.Treeview(right, columns=("cat",), show="tree headings",
                                 height=14, selectmode="extended")
        manche_tv.heading("#0", text=L["name"].rstrip(":"))
        manche_tv.heading("cat", text=L["table_category"])
        manche_tv.column("#0", width=200, anchor="w")
        manche_tv.column("cat", width=110, anchor="w")
        manche_sb = ttk.Scrollbar(right, orient="vertical", command=manche_tv.yview)
        manche_tv.configure(yscrollcommand=manche_sb.set)
        manche_sb.pack(side="right", fill="y")
        manche_tv.pack(side="top", fill="both", expand=True)
        manche_btns = ttk.Frame(right)
        manche_btns.pack(side="bottom", fill="x", pady=(6, 0))

        def refresh_panes():
            roster_tv.delete(*roster_tv.get_children())
            for name in sorted(self.data["participants"].keys(), key=str.lower):
                info = self.data["participants"][name]
                cat_disp = L["category_options"].get(info.get("category", ""), info.get("category", ""))
                roster_tv.insert("", "end", iid=name, text=name,
                                 values=(info.get("club", ""), cat_disp))
            manche_tv.delete(*manche_tv.get_children())
            for name in self.current_manche_participants():
                info = self.data["participants"].get(name, {})
                cat_disp = L["category_options"].get(info.get("category", ""), info.get("category", ""))
                manche_tv.insert("", "end", iid=name, text=name, values=(cat_disp,))

        def need_selection(tv):
            sel = tv.selection()
            if not sel:
                messagebox.showinfo(L["manage_participants"], L["select_row"])
                return None
            return sel

        def add_new():
            self.participant_form(win, on_done=lambda: (refresh_panes(), self.refresh_manche_view()))

        def edit_selected():
            sel = need_selection(roster_tv)
            if not sel:
                return
            self.participant_form(win, edit_name=sel[0],
                                  on_done=lambda: (refresh_panes(), self.refresh_manche_view()))

        def remove_selected():
            sel = need_selection(roster_tv)
            if not sel:
                return
            name = sel[0]
            if self.custom_dialog(L["remove"], L["confirm_remove_participant"],
                                  [(L["yes"], True), (L["no"], False)]):
                self.data["participants"].pop(name, None)
                for sk in SESSION_KEYS:
                    sess = self.data["sessions"][sk]
                    if name in sess["participants"]:
                        sess["participants"].remove(name)
                    sess["catches"].pop(name, None)
                self.update_event()
                refresh_panes()
                self.refresh_manche_view()

        def add_to_manche():
            sel = need_selection(roster_tv)
            if not sel:
                return
            sess = self.data["sessions"][self.current_manche]
            added = False
            for name in sel:
                if name in sess["participants"]:
                    continue
                sess["participants"].append(name)
                sess["catches"].setdefault(name, [])
                added = True
            if added:
                self.update_event()
                refresh_panes()
                self.refresh_manche_view()
            elif len(sel) == 1:
                messagebox.showinfo(L["manage_participants"],
                                    L["already_in_manche"].format(name=sel[0]))

        def remove_from_manche():
            sel = need_selection(manche_tv)
            if not sel:
                return
            if self.custom_dialog(L["remove_from_manche"], L["confirm_remove_from_manche"],
                                  [(L["yes"], True), (L["no"], False)]):
                sess = self.data["sessions"][self.current_manche]
                for name in sel:
                    if name in sess["participants"]:
                        sess["participants"].remove(name)
                    sess["catches"].pop(name, None)
                self.update_event()
                refresh_panes()
                self.refresh_manche_view()

        ttk.Button(roster_btns, text=L["add_participant"], command=add_new).pack(side="left", padx=2)
        ttk.Button(roster_btns, text=L["edit"], command=edit_selected).pack(side="left", padx=2)
        ttk.Button(roster_btns, text=L["remove"], command=remove_selected).pack(side="left", padx=2)
        ttk.Button(mid, text=L["add_to_manche"], command=add_to_manche).pack(pady=10, fill="x")
        ttk.Button(mid, text=L["remove_from_manche"], command=remove_from_manche).pack(pady=10, fill="x")
        ttk.Button(manche_btns, text=L["remove_from_manche"], command=remove_from_manche).pack(side="left", padx=2)
        ttk.Button(win, text=L["close"], command=win.destroy).pack(pady=(0, 8))

        refresh_panes()
        win.wait_window()

    # -- Add / Edit participant dialog -----------------------------
    def participant_form(self, parent, edit_name=None, on_done=None):
        L = LANGUAGES[self.lang]
        dlg = Toplevel(parent)
        dlg.title(L["edit_participant"] if edit_name else L["add_participant"])
        dlg.transient(parent)
        dlg.grab_set()
        dlg.geometry("440x320")

        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text=L["name"], font=("Arial", self.font_size)).grid(row=0, column=0, sticky="w", pady=4)
        name_entry = ttk.Entry(frame, font=("Arial", self.font_size), width=22)
        name_entry.grid(row=0, column=1, pady=4, sticky="ew")
        name_entry.focus_set()

        ttk.Label(frame, text=L["club"], font=("Arial", self.font_size)).grid(row=1, column=0, sticky="w", pady=4)
        club_entry = ttk.Entry(frame, font=("Arial", self.font_size), width=22, validate="key",
                               validatecommand=(self.root.register(self.validate_length), "%P"))
        club_entry.grid(row=1, column=1, pady=4, sticky="ew")

        ttk.Label(frame, text=L["category"], font=("Arial", self.font_size)).grid(row=2, column=0, sticky="w", pady=4)
        category_combobox = ttk.Combobox(frame, font=("Arial", self.font_size), width=20,
                                         values=list(L["category_options"].values()),
                                         state="readonly")
        category_combobox.grid(row=2, column=1, pady=4, sticky="ew")
        category_combobox.set("")

        ttk.Label(frame, text=L["remark"], font=("Arial", self.font_size)).grid(row=3, column=0, sticky="w", pady=4)
        remark_entry = ttk.Entry(frame, font=("Arial", self.font_size), width=22, validate="key",
                                 validatecommand=(self.root.register(self.validate_length), "%P"))
        remark_entry.grid(row=3, column=1, pady=4, sticky="ew")

        if edit_name:
            info = self.data["participants"].get(edit_name, {})
            name_entry.insert(0, edit_name)
            club_entry.insert(0, info.get("club", ""))
            remark_entry.insert(0, info.get("remark", ""))
            category_combobox.set(L["category_options"].get(info.get("category", ""), ""))

        def save():
            new_name = name_entry.get().strip()
            club = club_entry.get().strip()[:64]
            remark = remark_entry.get().strip()[:64]
            category = next((k for k, v in L["category_options"].items()
                             if v == category_combobox.get()), "")
            if not new_name:
                messagebox.showerror("Error", L["error"])
                return
            if edit_name:
                if new_name != edit_name and new_name in self.data["participants"]:
                    messagebox.showerror("Error", L["duplicate_name"])
                    return
                self.data["participants"][edit_name].update(
                    {"club": club, "category": category, "remark": remark})
                if new_name != edit_name:
                    self.rename_participant(edit_name, new_name)
            else:
                if new_name in self.data["participants"]:
                    messagebox.showerror("Error", L["duplicate_name"])
                    return
                next_id = max([p.get("id", 0) for p in self.data["participants"].values()], default=0) + 1
                self.data["participants"][new_name] = {
                    "id": next_id, "club": club, "category": category, "remark": remark}
            self.update_event()
            messagebox.showinfo("Success", L["saved"])
            if on_done:
                on_done()
            dlg.destroy()

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=12)
        ttk.Button(button_frame, text=L["save"], command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=L["close"], command=dlg.destroy).pack(side=tk.LEFT, padx=5)
        dlg.bind("<Return>", lambda e: save())
        dlg.wait_window()

    # -- Catch editor window ---------------------------------------
    def open_catch_editor(self):
        if not self.check_event_details():
            return
        L = LANGUAGES[self.lang]
        win = Toplevel(self.root)
        win.title(f'{L["edit_catches"]} - {key_to_display(self.lang, self.current_manche)}')
        win.transient(self.root)
        win.grab_set()
        win.geometry("820x480")

        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)

        cols = ("participant", "time", "type", "num", "weight", "length")
        headers = [L["table_participant_name"], L["indiv_time"], L["indiv_type"],
                   L["number_of_catches"], L["indiv_weight"], L["indiv_length"]]
        widths = [170, 70, 130, 90, 110, 100]
        tv = ttk.Treeview(frame, columns=cols, show="headings", height=14)
        for c, h, w in zip(cols, headers, widths):
            tv.heading(c, text=h)
            anchor = "w" if c in ("participant", "type") else "center"
            tv.column(c, width=w, anchor=anchor)
        tv_sb = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=tv_sb.set)
        tv_sb.pack(side="right", fill="y")
        tv.pack(side="top", fill="both", expand=True)

        rowmap = {}

        def refresh():
            tv.delete(*tv.get_children())
            rowmap.clear()
            sess = self.data["sessions"][self.current_manche]
            for name in sorted(sess["catches"].keys(), key=str.lower):
                for idx, c in enumerate(sess["catches"][name]):
                    iid = tv.insert("", "end", values=(
                        name,
                        c.get("time", ""),
                        c.get("type", "") or "-",
                        c.get("num_catches", 1),
                        self.fmt_weight(c.get("weight", 0)),
                        self.num_to_str(c.get("length")) if c.get("length") is not None else "-"))
                    rowmap[iid] = (name, idx)

        def edit_selected():
            sel = tv.selection()
            if not sel:
                messagebox.showinfo(L["edit_catch"], L["select_row"])
                return
            name, idx = rowmap[sel[0]]
            self.catch_form(win, name, idx,
                            on_done=lambda: (refresh(), self.refresh_manche_view()))

        def delete_selected():
            sel = tv.selection()
            if not sel:
                messagebox.showinfo(L["delete"], L["select_row"])
                return
            name, idx = rowmap[sel[0]]
            if self.custom_dialog(L["delete"], L["confirm_delete_catch"],
                                  [(L["yes"], True), (L["no"], False)]):
                try:
                    del self.data["sessions"][self.current_manche]["catches"][name][idx]
                except (KeyError, IndexError):
                    pass
                self.update_event()
                refresh()
                self.refresh_manche_view()

        btns = ttk.Frame(frame)
        btns.pack(side="bottom", fill="x", pady=6)
        ttk.Button(btns, text=L["edit"], command=edit_selected).pack(side="left", padx=4)
        ttk.Button(btns, text=L["delete"], command=delete_selected).pack(side="left", padx=4)
        ttk.Button(btns, text=L["close"], command=win.destroy).pack(side="right", padx=4)

        refresh()
        win.wait_window()

    # -- Edit catch dialog -----------------------------------------
    def catch_form(self, parent, name, idx, on_done=None):
        L = LANGUAGES[self.lang]
        try:
            catch = self.data["sessions"][self.current_manche]["catches"][name][idx]
        except (KeyError, IndexError):
            return
        dlg = Toplevel(parent)
        dlg.title(L["edit_catch"])
        dlg.transient(parent)
        dlg.grab_set()
        dlg.geometry("420x320")

        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text=f'{L["table_participant_name"]}: {name}',
                  font=("Arial", self.font_size, "bold")).grid(row=0, column=0, columnspan=2,
                                                                sticky="w", pady=(0, 8))

        ttk.Label(frame, text=L["fish_weight"], font=("Arial", self.font_size)).grid(row=1, column=0, sticky="w", pady=4)
        weight_entry = ttk.Entry(frame, font=("Arial", self.font_size), width=16, validate="key",
                                 validatecommand=(self.root.register(self.validate_number), "%P"))
        weight_entry.grid(row=1, column=1, pady=4, sticky="ew")
        weight_entry.insert(0, self.num_to_str(catch.get("weight", 0)))

        ttk.Label(frame, text=L["num_catches"], font=("Arial", self.font_size)).grid(row=2, column=0, sticky="w", pady=4)
        num_entry = ttk.Entry(frame, font=("Arial", self.font_size), width=16, validate="key",
                              validatecommand=(self.root.register(self.validate_catches), "%P"))
        num_entry.grid(row=2, column=1, pady=4, sticky="ew")
        num_entry.insert(0, str(catch.get("num_catches", 1)))

        ttk.Label(frame, text=L["fish_length"], font=("Arial", self.font_size)).grid(row=3, column=0, sticky="w", pady=4)
        length_entry = ttk.Entry(frame, font=("Arial", self.font_size), width=16, validate="key",
                                 validatecommand=(self.root.register(self.validate_number), "%P"))
        length_entry.grid(row=3, column=1, pady=4, sticky="ew")
        length_entry.insert(0, self.num_to_str(catch.get("length")) if catch.get("length") is not None else "")

        ttk.Label(frame, text=L["fish_type"], font=("Arial", self.font_size)).grid(row=4, column=0, sticky="w", pady=4)
        type_entry = ttk.Entry(frame, font=("Arial", self.font_size), width=16)
        type_entry.grid(row=4, column=1, pady=4, sticky="ew")
        type_entry.insert(0, catch.get("type", "") or "")

        def save():
            try:
                weight = float(weight_entry.get().replace(",", "."))
                if weight <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", L["invalid_number"])
                return
            num_str = num_entry.get()
            if not num_str or int(num_str) < 1:
                messagebox.showerror("Error", L["invalid_catches"])
                return
            num = int(num_str)
            length = None
            length_str = length_entry.get().strip()
            if length_str:
                try:
                    lv = float(length_str.replace(",", "."))
                    length = lv if lv > 0 else None
                except ValueError:
                    messagebox.showerror("Error", L["invalid_number"])
                    return
            fish_type = type_entry.get().strip()
            if num > 1:
                length = None
                fish_type = ""
            catch["weight"] = weight
            catch["num_catches"] = num
            catch["length"] = length
            catch["type"] = fish_type
            self.update_event()
            if on_done:
                on_done()
            dlg.destroy()

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=12)
        ttk.Button(button_frame, text=L["save"], command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=L["close"], command=dlg.destroy).pack(side=tk.LEFT, padx=5)
        dlg.bind("<Return>", lambda e: save())
        dlg.wait_window()

    def generate_report(self):
        L = LANGUAGES[self.lang]
        if not self.data["participants"]:
            messagebox.showerror("Error", L["error"])
            return
        try:
            event = self.data["event"]
            event_name_file = str(event.get("name", "event")).replace(" ", "_")
            event_name_display = str(event.get("name", "event"))
            event_date = str(event.get("date", datetime.now().strftime("%d/%m/%Y")))
            date_obj = datetime.strptime(event_date, "%d/%m/%Y")
            date_str = date_obj.strftime("%Y%m%d")
            folder_name = f"{date_str}_{event_name_file}"
            filename = f"{folder_name}/{folder_name}.pdf"

            try:
                os.makedirs(folder_name, exist_ok=True)
            except PermissionError:
                messagebox.showerror("Error", L["permission_error"].replace("[folder]", folder_name))
                return

            page = landscape(letter)
            doc = SimpleDocTemplate(filename, pagesize=page,
                                    leftMargin=36, rightMargin=36,
                                    topMargin=42, bottomMargin=42)
            styles = getSampleStyleSheet()
            normal_style = styles["BodyText"]
            normal_style.fontSize = 10
            bold_style = styles["BodyText"].clone("bold_cell")
            bold_style.fontName = "Helvetica-Bold"
            bold_style.fontSize = 10
            center_style = styles["Heading2"].clone("center_h2")
            center_style.alignment = 1
            story = []

            logo_path = "logo.png"
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=1 * inch, height=1 * inch)
                logo.hAlign = "LEFT"
                story.append(logo)
                story.append(Spacer(1, 12))

            event_location = str(event.get("location", "Unknown Location"))
            story.append(Paragraph(L["summary_report"], styles["Title"]))
            story.append(Spacer(1, 12))
            story.append(Paragraph(f"{event_name_display} - {event_location} - {event_date}", center_style))
            story.append(Spacer(1, 12))

            # ---- One summary table per session ----
            common_style = [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (5, 1), (-1, -1), "RIGHT"),
                ("WORDWRAP", (0, 0), (-1, -1), "CJK"),
            ]
            col_widths = [32, 150, 95, 95, 110, 60, 75, 65]

            grand_participants = 0
            grand_catches = 0
            grand_weight = 0
            session_summaries = []

            for sk in SESSION_KEYS:
                sess = self.data["sessions"][sk]
                if not sess["participants"] and not any(sess["catches"].values()):
                    continue
                sess_label = key_to_display(self.lang, sk)
                story.append(Paragraph(f'{L["summary_report"]} - {sess_label}', center_style))
                story.append(Spacer(1, 6))

                table = [[
                    Paragraph("#", normal_style),
                    Paragraph(L["name"].rstrip(":"), normal_style),
                    Paragraph(L["table_club"], normal_style),
                    Paragraph(L["table_category"], normal_style),
                    Paragraph(L["table_remark"], normal_style),
                    Paragraph(L["table_participants"], normal_style),
                    Paragraph(L["table_total_weight"], normal_style),
                    Paragraph(L["table_longest_fish"], normal_style),
                ]]
                names_in_sess = sess["participants"]
                totals = {n: sum(c["weight"] for c in sess["catches"].get(n, []))
                          for n in names_in_sess}
                sorted_names = sorted(names_in_sess, key=lambda n: totals[n], reverse=True)

                sess_total_catches = 0
                sess_total_weight = 0
                for rank_i, name in enumerate(sorted_names, 1):
                    catches = sess["catches"].get(name, [])
                    total_catches = sum(c["num_catches"] for c in catches) if catches else 0
                    total_weight = sum(c["weight"] for c in catches) if catches else 0
                    longest = max((c["length"] for c in catches if c["length"] is not None), default=0) if catches else 0
                    sess_total_catches += total_catches
                    sess_total_weight += total_weight
                    info = self.data["participants"].get(name, {})
                    cat_disp = L["category_options"].get(info.get("category", ""), info.get("category", ""))
                    table.append([
                        Paragraph(str(rank_i), normal_style),
                        Paragraph(str(name), normal_style),
                        Paragraph(info.get("club", "") or "", normal_style),
                        Paragraph(cat_disp, normal_style),
                        Paragraph(info.get("remark", "") or "", normal_style),
                        Paragraph(str(total_catches), normal_style),
                        Paragraph(self.fmt_weight(total_weight), normal_style),
                        Paragraph(f"{longest}" if longest else "", normal_style),
                    ])
                story.append(Table(table, colWidths=col_widths, style=common_style))
                story.append(Spacer(1, 8))
                summary_text = (f"{L['summary']} {len(names_in_sess)} {L['summary_participants']}, "
                                f"{sess_total_catches} {L['summary_total_catches']}, "
                                f"{self.fmt_weight(sess_total_weight)} {L['summary_total_weight']}")
                story.append(Paragraph(summary_text, styles["Normal"]))
                story.append(PageBreak())

                session_summaries.append((sk, sess_label, sorted_names))
                grand_participants = max(grand_participants, len(self.data["participants"]))
                grand_catches += sess_total_catches
                grand_weight += sess_total_weight

            # ---- Per-participant pages, scoped to each session ----
            indiv_widths = [80, 130, 90, 110, 110]
            indiv_style = [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ("WORDWRAP", (0, 0), (-1, -1), "CJK"),
            ]

            for sk, sess_label, sorted_names in session_summaries:
                sess = self.data["sessions"][sk]
                for rank_i, name in enumerate(sorted_names, 1):
                    catches = sorted(sess["catches"].get(name, []), key=lambda x: x["time"])
                    if not catches:
                        continue
                    story.append(Paragraph(f"{event_name_display} - {event_location} - {event_date}", styles["Title"]))
                    story.append(Paragraph(f"{name} - {sess_label}", styles["Title"]))
                    story.append(Spacer(1, 8))
                    catch_table = [[
                        Paragraph(L["indiv_time"], normal_style),
                        Paragraph(L["indiv_type"], normal_style),
                        Paragraph(L["number_of_catches"], normal_style),
                        Paragraph(L["indiv_weight"], normal_style),
                        Paragraph(L["indiv_length"], normal_style),
                    ]]
                    max_w = max(c["weight"] for c in catches)
                    max_l = max((c["length"] or 0 for c in catches if c["length"] is not None), default=0)
                    for c in catches:
                        fish_type = c.get("type", "") or "-"
                        weight_val = c["weight"]
                        weight_par = Paragraph(self.fmt_weight(weight_val),
                                               bold_style if weight_val == max_w else normal_style)
                        length_v = c.get("length")
                        if length_v is None:
                            length_par = Paragraph("-", normal_style)
                        else:
                            length_par = Paragraph(self.num_to_str(length_v),
                                                   bold_style if length_v == max_l else normal_style)
                        catch_table.append([
                            Paragraph(str(c.get("time", "")), normal_style),
                            Paragraph(str(fish_type), normal_style),
                            Paragraph(str(c["num_catches"]), normal_style),
                            weight_par,
                            length_par,
                        ])
                    story.append(Table(catch_table, colWidths=indiv_widths, style=indiv_style))
                    story.append(Spacer(1, 12))
                    info = self.data["participants"].get(name, {})
                    if info.get("club"):
                        story.append(Paragraph(f"{L['club']} {info['club']}", styles["Normal"]))
                    if info.get("category"):
                        _cat = L["category_options"].get(info["category"], info["category"])
                        story.append(Paragraph(f"{L['category']} {_cat}", styles["Normal"]))
                    if info.get("remark"):
                        story.append(Paragraph(f"{L['remark']} {info['remark']}", styles["Normal"]))
                    total_catches = sum(c["num_catches"] for c in catches)
                    total_weight = sum(c["weight"] for c in catches)
                    story.append(Paragraph(f"{L['indiv_total_catches']}: {total_catches}", styles["Normal"]))
                    story.append(Paragraph(f"{L['indiv_total_weight']}: {self.fmt_weight(total_weight)} g", styles["Normal"]))
                    story.append(Paragraph(f"{L['indiv_final_rank']}: {rank_i}", styles["Normal"]))
                    story.append(PageBreak())

            # ---- Combined ranking across all sessions ----
            combined_rows = []
            for sk in SESSION_KEYS:
                sess = self.data["sessions"][sk]
                sess_label = key_to_display(self.lang, sk)
                for name in sess["participants"]:
                    catches = sess["catches"].get(name, [])
                    if not catches:
                        continue
                    total_catches = sum(c["num_catches"] for c in catches)
                    total_weight = sum(c["weight"] for c in catches)
                    longest = max((c["length"] for c in catches if c["length"] is not None), default=0)
                    combined_rows.append((name, sess_label, total_catches, total_weight, longest))

            if combined_rows:
                combined_rows.sort(key=lambda r: r[3], reverse=True)
                story.append(Paragraph(L["combined_report"], styles["Title"]))
                story.append(Spacer(1, 8))
                story.append(Paragraph(f"{event_name_display} - {event_location} - {event_date}", center_style))
                story.append(Spacer(1, 12))
                comb_table = [[
                    Paragraph("#", normal_style),
                    Paragraph(L["table_participant_name"], normal_style),
                    Paragraph(L["session_column"], normal_style),
                    Paragraph(L["table_participants"], normal_style),
                    Paragraph(L["table_total_weight"], normal_style),
                    Paragraph(L["table_longest_fish"], normal_style),
                ]]
                for rank_i, (name, sess_label, tc, tw, lg) in enumerate(combined_rows, 1):
                    comb_table.append([
                        Paragraph(str(rank_i), normal_style),
                        Paragraph(name, normal_style),
                        Paragraph(sess_label, normal_style),
                        Paragraph(str(tc), normal_style),
                        Paragraph(self.fmt_weight(tw), normal_style),
                        Paragraph(f"{lg}" if lg else "", normal_style),
                    ])
                comb_widths = [40, 200, 110, 90, 110, 90]
                comb_style = [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("LEADING", (0, 0), (-1, -1), 12),
                    ("ALIGN", (0, 1), (0, -1), "CENTER"),
                    ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                    ("WORDWRAP", (0, 0), (-1, -1), "CJK"),
                ]
                story.append(Table(comb_table, colWidths=comb_widths, style=comb_style))
                story.append(Spacer(1, 8))
                grand_text = (f"{L['summary']} {len(self.data['participants'])} {L['summary_participants']}, "
                              f"{grand_catches} {L['summary_total_catches']}, "
                              f"{self.fmt_weight(grand_weight)} {L['summary_total_weight']}")
                story.append(Paragraph(grand_text, styles["Normal"]))

            # ---- Footer on every page ----
            def add_footer(canvas, doc):
                canvas.saveState()
                canvas.setFont("Helvetica", 9)
                footer_text = L["copyright"].replace(
                    "fescherfrenn@outlook.com",
                    '<link href="mailto:fescherfrenn@outlook.com" color="blue">fescherfrenn@outlook.com</link>')
                p = Paragraph(footer_text, normal_style)
                w, h = p.wrap(doc.width, doc.bottomMargin)
                p.drawOn(canvas, doc.leftMargin, doc.bottomMargin - h - 6)
                canvas.restoreState()

            doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
            messagebox.showinfo(
                "Success",
                L["report_generated"].replace("[date]_[event_name]", f"{date_str}_{event_name_file}"))
        except Exception as e:
            logging.error(f"generate_report failed: {e}")
            messagebox.showerror("Error", f"Report generation failed: {type(e).__name__}: {e}")

    def custom_dialog(self, title, message, buttons):
        dialog = Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        text_length = len(message)
        width = max(300, min(600, text_length * 8))
        height = max(150, 100 + (text_length // 50) * 30)
        dialog.geometry(f"{int(width)}x{int(height)}")

        label = ttk.Label(dialog, text=message, wraplength=width-20, font=("Arial", self.font_size))
        label.pack(pady=10, padx=10)
        
        result = [None]
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=5, side=tk.BOTTOM)
        for btn_text, value in buttons:
            btn = ttk.Button(btn_frame, text=btn_text, command=lambda v=value: [result.__setitem__(0, v), dialog.destroy()])
            btn.pack(side=tk.LEFT, padx=5)
            if btn_text == LANGUAGES[self.lang]["yes"]:
                btn.focus_set()
                dialog.bind("<Return>", lambda e, v=value: [result.__setitem__(0, v), dialog.destroy()])

        dialog.wait_window()
        return result[0]

    def reset_event(self):
        if self.custom_dialog(LANGUAGES[self.lang]["reset_event"], LANGUAGES[self.lang]["confirm_reset"], [(LANGUAGES[self.lang]["yes"], True), (LANGUAGES[self.lang]["no"], False)]):
            self.data = {"event": {}, "participants": {}, "sessions": empty_sessions(), "lang": self.lang, "version": APP_VERSION}
            folder_name = get_event_folder(self.data["event"])
            data_file = os.path.join(folder_name, f"{folder_name}.json")
            if os.path.exists(data_file):
                try:
                    os.remove(data_file)
                except Exception as e:
                    logging.error(f"reset_event file removal failed: {str(e)}")
            if os.path.exists(TEMP_DATA_FILE):
                try:
                    os.remove(TEMP_DATA_FILE)
                except Exception as e:
                    logging.error(f"reset_event temp file removal failed: {str(e)}")
            self.build_main_ui()
            messagebox.showinfo(LANGUAGES[self.lang]["saved"], LANGUAGES[self.lang]["reset_success"])

    def export_event(self):
        event = self.data["event"]
        folder_name = get_event_folder(event)
        filename = os.path.join(folder_name, f"{folder_name}.json")

        try:
            os.makedirs(folder_name, exist_ok=True)
        except PermissionError:
            messagebox.showerror("Error", LANGUAGES[self.lang]["permission_error"].replace("[folder]", folder_name))
            return

        try:
            with open(filename, 'w', encoding='utf-8') as file:
                json.dump(self.data, file, indent=4, ensure_ascii=False)
            messagebox.showinfo(LANGUAGES[self.lang]["saved"], LANGUAGES[self.lang]["export_success"].format(filename=filename))
        except Exception as e:
            logging.error(f"export_event failed: {str(e)}")
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def import_event(self):
        try:
            file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
            if not file_path:
                return
            with open(file_path, 'r', encoding='utf-8') as file:
                imported_data = json.load(file)
        
            if not isinstance(imported_data, dict) or "event" not in imported_data or "participants" not in imported_data:
                raise ValueError("Invalid event data format")
            self.data = migrate_data(imported_data)
            self.root.title(LANGUAGES[self.lang]["title"])
            self.build_main_ui()
            messagebox.showinfo(LANGUAGES[self.lang]["saved"], LANGUAGES[self.lang]["import_success"])
        except Exception as e:
            logging.error(f"import_event failed: {str(e)}")
            messagebox.showerror(LANGUAGES[self.lang]["error"], f"Failed to import event: {str(e)}")

    def on_closing(self):
        if self.custom_dialog(LANGUAGES[self.lang]["close"], LANGUAGES[self.lang]["confirm_close"], [(LANGUAGES[self.lang]["yes"], True), (LANGUAGES[self.lang]["no"], False)]):
            try:
                save_data(self.data, self.data["event"])
            except Exception as e:
                logging.error(f"on_closing save failed: {str(e)}")
                messagebox.showerror("Error", LANGUAGES[self.lang]["error"])
            self.root.destroy()

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = FishingApp(root)
        root.mainloop()
    except Exception as e:
        logging.error(f"Main loop error: {str(e)}")
        messagebox.showerror("Error", f"Application failed: {str(e)}")

