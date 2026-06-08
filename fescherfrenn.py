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
    from reportlab.lib.pagesizes import letter, landscape, A4
    from reportlab.pdfgen import canvas as _rlcanvas
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, PageBreak, Image
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.units import inch
except ImportError:
    pass

TEMP_DATA_FILE = "temp_fishing_data.json"
BACKUP_DIR = os.path.expanduser("~/FescherfrennData/backups")
APP_VERSION = "3.4.1"

# Set up logging
logging.basicConfig(filename='fescherfrenn.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

TRANSLATIONS_FILE = "translations.json"
CONFIG_FILE = "config.json"
HELP_FILE = "help.json"
SESSION_KEYS = ["manche1", "manche2", "manche3", "final"]

DEFAULT_CONFIG = {
    "invoice_prefix": "FFS2010",
    "issuer_name": "Fëscherfrënn Stengefort 2010",
    "issuer_legal_name": "Fëscherfrënn Stengefort 2010 a.s.b.l.",
    "issuer_house_number": "44",
    "issuer_street": "rue de Sterpenich",
    "issuer_postcode_country": "L",
    "issuer_postcode_digits": "8379",
    "issuer_city": "Kleinbettingen",
    "issuer_country": "Luxembourg",
    "issuer_phone": "+352 621 22 40 56",
    "issuer_email": "fescherfrenn@outlook.com",
    "bank_account_holder": "Fescherfrenn Stengefort 2010",
    "bank_name": "Banque Raiffeisen",
    "iban_groups": ["CCRA", "LU85", "0090", "0000", "0597", "1635"],
    "payment_terms_days": 30
}


def load_config():
    """Load config.json next to the script (or fall back to defaults).

    Writes the config back so users always have a starting file to edit.
    """
    path = _resource_path(CONFIG_FILE)
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                for k in DEFAULT_CONFIG:
                    if k in loaded:
                        cfg[k] = loaded[k]
        except Exception as exc:
            logging.error(f"Failed to load {CONFIG_FILE}: {exc}")
    else:
        try:
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(cfg, fh, indent=2, ensure_ascii=False)
        except Exception as exc:
            logging.error(f"Could not create default {CONFIG_FILE}: {exc}")
    return cfg


def save_config(cfg):
    """Persist config.json (best-effort) and refresh the in-memory CONFIG dict."""
    try:
        path = _resource_path(CONFIG_FILE)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(cfg, fh, indent=2, ensure_ascii=False)
    except Exception as exc:
        logging.error(f"Failed to save {CONFIG_FILE}: {exc}")
        return False
    CONFIG.clear()
    CONFIG.update(cfg)
    return True


def load_help():
    """Load help.json next to the script. Returns a dict: lang -> [{title, body}, ...].

    Falls back to an empty per-language list if the file is missing or invalid.
    """
    path = _resource_path(HELP_FILE)
    default = {lang: [] for lang in ("English", "French", "German", "Luxembourgish")}
    if not os.path.exists(path):
        logging.warning(f"{HELP_FILE} not found; help dialog will be empty.")
        return default
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            loaded = json.load(fh)
        if not isinstance(loaded, dict):
            return default
        out = dict(default)
        for lang, sections in loaded.items():
            if isinstance(sections, list):
                out[lang] = sections
        return out
    except Exception as exc:
        logging.error(f"Failed to load {HELP_FILE}: {exc}")
        return default


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
CONFIG = load_config()
HELP = load_help()


def empty_sessions():
    return {k: {"participants": [], "catches": {}} for k in SESSION_KEYS}


def new_event_data(lang="English"):
    """A fresh, fully-formed event dict.

    Single source of truth for a blank event so the invoice keys can never
    go missing again (a missing "invoices" key caused silent save failures
    and a runaway invoice counter in v3.3).
    """
    return {
        "event": {}, "participants": {}, "sessions": empty_sessions(),
        "invoices": [], "invoice_seq_start": None, "invoice_next": None,
        "invoice_unit_price": None,
        "track_details": False, "lang": lang, "version": APP_VERSION,
    }


def migrate_data(data):
    """Bring older v1.x and v2.0 (auto-assign) data up to the v2.1 schema in place."""
    if not isinstance(data, dict):
        return new_event_data()
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

    data.setdefault("track_details", False)
    # v3.0: per-event invoice store. Numbers live ONLY inside an event.
    if not isinstance(data.get("invoices"), list):
        data["invoices"] = []
    data.setdefault("invoice_seq_start", None)
    data.setdefault("invoice_next", None)
    data.setdefault("invoice_unit_price", None)
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
    return new_event_data()

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
            # Report settings: which sections to include in the generated PDF.
            self.include_individual_var = tk.BooleanVar(value=False)
            self.include_combined_var = tk.BooleanVar(value=False)
            self.combined_chk = None
            self.reset_btn = None
            self.export_btn = None
            self.import_btn = None
            self.help_btn = None
            self.catch_name_var = None  # Added for Combobox hint
            self.track_details_var = None   # event-level: record length & type
            self.overall_rankings = None    # right-hand pooled rankings widget

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
        self.main_frame.columnconfigure(1, weight=2, minsize=560)
        self.main_frame.rowconfigure(0, weight=0)
        self.main_frame.rowconfigure(1, weight=1)
        self.main_frame.rowconfigure(2, weight=0)

        left_frame = ttk.Frame(self.main_frame)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=3, pady=3)

        # -- Event details + round selector --
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

        # Event-level toggle: record fish length & type.
        self.track_details_var = tk.BooleanVar(value=self.data.get("track_details", False))
        self.track_chk = ttk.Checkbutton(
            event_frame, text=L["enable_details"], variable=self.track_details_var,
            command=self.on_track_details_toggled)
        self.track_chk.grid(row=4, column=0, columnspan=2, pady=(4, 2), sticky="w")

        self.manage_btn = ttk.Button(event_frame, text=L["manage_participants"], command=self.open_participants_manager)
        self.manage_btn.grid(row=5, column=0, columnspan=2, pady=(6, 2), sticky="ew")

        event_locked = bool(self.data["event"])
        if event_locked:
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
            # Length/type policy is fixed once the event is locked.
            self.track_chk.config(state="disabled")

        # -- Log catch --
        catch_frame = ttk.LabelFrame(left_frame, text=L["log_catch"], padding=5)
        catch_frame.pack(fill="x", pady=6)
        catch_frame.columnconfigure(1, weight=1)
        ttk.Label(catch_frame, text=L["name"], font=("Arial", self.font_size)).grid(row=0, column=0, pady=3, sticky="w")
        self.catch_name_var = tk.StringVar()
        self.catch_name = ttk.Combobox(catch_frame, textvariable=self.catch_name_var,
                                       values=self.catch_dropdown_values(),
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
        # When the event tracks length/type, every catch is a single fish, so the
        # number of catches is forced to 1 and the field is locked.
        if self.data.get("track_details", False):
            self.num_catches.config(state="disabled")
        self.length_label = ttk.Label(catch_frame, text=L["fish_length"], font=("Arial", self.font_size))
        self.length_label.grid(row=3, column=0, pady=3, sticky="w")
        self.fish_length = ttk.Entry(catch_frame, font=("Arial", self.font_size), width=18, validate="key",
                                     validatecommand=(self.root.register(self.validate_number), "%P"))
        self.fish_length.grid(row=3, column=1, pady=3, sticky="ew")
        self.type_label = ttk.Label(catch_frame, text=L["fish_type"], font=("Arial", self.font_size))
        self.type_label.grid(row=4, column=0, pady=3, sticky="w")
        self.fish_type = ttk.Entry(catch_frame, font=("Arial", self.font_size), width=18)
        self.fish_type.grid(row=4, column=1, pady=3, sticky="ew")

        # Swapped per request: Log Catch on the left, Edit Catches on the right.
        self.log_btn = ttk.Button(catch_frame, text=L["log_catch"], command=self.log_catch)
        self.log_btn.grid(row=5, column=0, pady=5, sticky="w")
        self.edit_catches_btn = ttk.Button(catch_frame, text=L["edit_catches"], command=self.open_catch_editor)
        self.edit_catches_btn.grid(row=5, column=1, pady=5, sticky="e")

        self._apply_details_enabled_state()

        # -- Right column: two-panel rankings + actions + participants --
        right_frame = ttk.Frame(self.main_frame)
        right_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=3, pady=3)

        rankings_outer = ttk.Frame(right_frame)
        rankings_outer.pack(fill="both", expand=True)
        rankings_outer.columnconfigure(0, weight=1, uniform="rk")
        rankings_outer.columnconfigure(1, weight=1, uniform="rk")
        rankings_outer.rowconfigure(0, weight=1)

        bg = self.root.cget("background")
        round_lf = ttk.LabelFrame(rankings_outer, text=L["live_rankings"], padding=5)
        round_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
        self.rankings = tk.Text(round_lf, width=30, height=20, relief="flat",
                                wrap="word", state="disabled", background=bg,
                                borderwidth=0, highlightthickness=0)
        self.rankings.pack(fill="both", expand=True)
        self._style_ranking_text(self.rankings)

        overall_lf = ttk.LabelFrame(rankings_outer, text=L["overall_rankings"], padding=5)
        overall_lf.grid(row=0, column=1, sticky="nsew", padx=(3, 0))
        self.overall_rankings = tk.Text(overall_lf, width=30, height=20, relief="flat",
                                        wrap="word", state="disabled", background=bg,
                                        borderwidth=0, highlightthickness=0)
        self.overall_rankings.pack(fill="both", expand=True)
        self._style_ranking_text(self.overall_rankings)

        self.refresh_rankings()

        btn_frame = ttk.Frame(right_frame)
        btn_frame.pack(fill="x", pady=3)
        self.report_btn = ttk.Button(btn_frame, text=L["generate_report"], command=self.generate_report)
        self.report_btn.pack(side=tk.LEFT, padx=3)
        self.reset_btn = ttk.Button(btn_frame, text=L["reset_event"], command=self.reset_event)
        self.reset_btn.pack(side=tk.LEFT, padx=3)
        self.export_btn = ttk.Button(btn_frame, text=L["export_event"], command=self.export_event)
        self.export_btn.pack(side=tk.LEFT, padx=3)
        self.import_btn = ttk.Button(btn_frame, text=L["import_event"], command=self.import_event)
        self.import_btn.pack(side=tk.LEFT, padx=3)
        self.invoices_btn = ttk.Button(btn_frame, text=L["invoices_btn"], command=self.open_invoices_manager)
        self.invoices_btn.pack(side=tk.LEFT, padx=3)
        self.settings_btn = ttk.Button(btn_frame, text=L["settings_btn"], command=self.open_settings_dialog)
        self.settings_btn.pack(side=tk.LEFT, padx=3)
        self.help_btn = ttk.Button(btn_frame, text=L["help"], command=self.show_help)
        self.help_btn.pack(side=tk.LEFT, padx=3)

        self.manche_pf = ttk.LabelFrame(
            right_frame,
            text=f'{L["participants"]} - {key_to_display(self.lang, self.current_manche)}', padding=5)
        self.manche_pf.pack(fill="x", pady=3)
        participants_canvas = tk.Canvas(self.manche_pf, height=160)
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

        # -- Report settings --
        settings_frame = ttk.LabelFrame(right_frame, text=L["report_settings_label"], padding=5)
        settings_frame.pack(fill="x", pady=3)
        ttk.Label(settings_frame, text=f'\u2713 {L["chk_event_summary"]}',
                  font=("Arial", self.font_size - 2, "italic"), foreground="gray").pack(anchor="w", pady=2)
        ttk.Checkbutton(settings_frame, text=L["chk_individual"],
                        variable=self.include_individual_var).pack(anchor="w", pady=2)
        self.combined_chk = ttk.Checkbutton(
            settings_frame, text=L["chk_combined"], variable=self.include_combined_var)
        self.combined_chk.pack(anchor="w", pady=2)
        self._update_combined_state()

        # -- Footer: version bottom-left, copyright centred --
        footer_frame = ttk.Frame(self.main_frame)
        footer_frame.grid(row=2, column=0, columnspan=2, pady=5, sticky="ew")
        footer_frame.columnconfigure(0, weight=1)
        footer_frame.columnconfigure(1, weight=0)
        footer_frame.columnconfigure(2, weight=1)
        ttk.Label(footer_frame, text=f"v{APP_VERSION}",
                  font=("Arial", self.font_size - 4), foreground="gray").grid(row=0, column=0, sticky="w", padx=6)
        cr_holder = ttk.Frame(footer_frame)
        cr_holder.grid(row=0, column=1)
        cr = self.copyright_text()
        if "fescherfrenn@outlook.com" in cr:
            before, after = cr.split("fescherfrenn@outlook.com", 1)
            ttk.Label(cr_holder, text=before, font=("Arial", self.font_size - 4)).pack(side=tk.LEFT)
            email_label = tk.Label(cr_holder, text="fescherfrenn@outlook.com",
                                   font=("Arial", self.font_size - 4), foreground="blue", cursor="hand2")
            email_label.pack(side=tk.LEFT)
            email_label.bind("<Button-1>", lambda e: webbrowser.open("mailto:fescherfrenn@outlook.com"))
            ttk.Label(cr_holder, text=after, font=("Arial", self.font_size - 4)).pack(side=tk.LEFT)
        else:
            ttk.Label(cr_holder, text=cr, font=("Arial", self.font_size - 4)).pack(side=tk.LEFT)

        # -- Tooltips --
        self.create_tooltip(self.manage_btn, L["tooltip_manage"])
        self.create_tooltip(self.log_btn, L["tooltip_log"])
        self.create_tooltip(self.edit_catches_btn, L["tooltip_edit_catches"])
        self.create_tooltip(self.report_btn, L["tooltip_report"])
        self.create_tooltip(self.reset_btn, L["tooltip_reset"])
        self.create_tooltip(self.export_btn, L["tooltip_export"])
        self.create_tooltip(self.import_btn, L["tooltip_import"])
        self.create_tooltip(self.invoices_btn, L["tooltip_invoices"])
        self.create_tooltip(self.settings_btn, L["tooltip_settings"])
        self.create_tooltip(self.help_btn, L["tooltip_help"])

    def _apply_details_enabled_state(self):
        """Grey out / lock the length & type inputs when the event doesn't track them.

        Also locks the num-catches field to 1 when length/type is enabled, since a
        length and a fish type can only meaningfully apply to a single catch.
        """
        track = self.data.get("track_details", False)
        state = "normal" if track else "disabled"
        for w in (self.fish_length, self.fish_type):
            if w is not None:
                try:
                    w.config(state=state)
                except tk.TclError:
                    pass
        fg = "black" if track else "#999999"
        for lbl in (getattr(self, "length_label", None), getattr(self, "type_label", None)):
            if lbl is not None:
                lbl.config(foreground=fg)
        # num_catches: locked at 1 whenever length/type is enabled.
        if getattr(self, "num_catches", None) is not None:
            try:
                if track:
                    self.num_catches.config(state="normal")
                    self.num_catches.delete(0, tk.END)
                    self.num_catches.insert(0, "1")
                    self.num_catches.config(state="disabled")
                else:
                    self.num_catches.config(state="normal")
            except tk.TclError:
                pass

    def on_track_details_toggled(self):
        """User flipped the length/type checkbox before the event is locked."""
        self.data["track_details"] = bool(self.track_details_var.get())
        self._apply_details_enabled_state()
        self.refresh_rankings()


    def on_combobox_focus_in(self, event):
        if self.catch_name_var.get() == LANGUAGES[self.lang]["select_participant"]:
            self.catch_name_var.set('')
            self.catch_name.config(foreground='black')

    def on_combobox_focus_out(self, event):
        if not self.catch_name_var.get():
            self.catch_name_var.set(LANGUAGES[self.lang]["select_participant"])
            self.catch_name.config(foreground='grey')

    def on_combobox_selected(self, event):
        if self._is_catch_separator(self.catch_name_var.get()):
            self.catch_name_var.set('')
            return
        self.catch_name.config(foreground='black')

    def create_tooltip(self, widget, text):
        """Hover tooltip that is safe on macOS.

        The previous implementation kept a persistent borderless (overrideredirect)
        window per widget and positioned it over the widget; on macOS, clicking a
        borderless window sitting on top of the intended target froze the app.
        This version creates the tooltip on hover, places it *below* the widget so
        it never covers the click target, and destroys it on leave or on any click.
        """
        if not text:
            return
        state = {"win": None, "after": None}

        def _build():
            state["after"] = None
            if state["win"] is not None:
                return
            try:
                x = widget.winfo_rootx() + 12
                y = widget.winfo_rooty() + widget.winfo_height() + 4
                win = tk.Toplevel(widget)
                win.wm_overrideredirect(True)
                try:
                    win.wm_attributes("-topmost", True)
                except tk.TclError:
                    pass
                ttk.Label(win, text=text, background="lightyellow",
                          relief="solid", borderwidth=1, padding=3).pack()
                win.wm_geometry(f"+{x}+{y}")
                state["win"] = win
            except tk.TclError:
                state["win"] = None

        def hide(_event=None):
            if state["after"] is not None:
                try:
                    widget.after_cancel(state["after"])
                except Exception:
                    pass
                state["after"] = None
            if state["win"] is not None:
                try:
                    state["win"].destroy()
                except tk.TclError:
                    pass
                state["win"] = None

        def schedule(_event=None):
            hide()
            state["after"] = widget.after(500, _build)

        widget.bind("<Enter>", schedule, add="+")
        widget.bind("<Leave>", hide, add="+")
        widget.bind("<Button>", hide, add="+")
        widget.bind("<Destroy>", hide, add="+")

    def show_help(self):
        """Help dialog with a left-side section list and a right-side reader pane.

        Sections come from help.json (one list per language). If the current
        language has no sections (e.g. translation pending), falls back to the
        English sections with a small notice.
        """
        L = LANGUAGES[self.lang]
        sections = HELP.get(self.lang) or []
        fallback_used = False
        if not sections:
            sections = HELP.get("English") or []
            fallback_used = True

        win = Toplevel(self.root)
        win.title(L["help"])
        win.transient(self.root)
        win.geometry("900x560")

        outer = ttk.Frame(win, padding=8)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=0, minsize=210)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(0, weight=1)

        # Left: section list
        nav_frame = ttk.LabelFrame(outer, text=L["help"], padding=4)
        nav_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        nav = tk.Listbox(nav_frame, font=("Arial", self.font_size - 2),
                         activestyle="dotbox", exportselection=False, width=26)
        nav_sb = ttk.Scrollbar(nav_frame, orient="vertical", command=nav.yview)
        nav.configure(yscrollcommand=nav_sb.set)
        nav_sb.pack(side="right", fill="y")
        nav.pack(side="left", fill="both", expand=True)
        for sec in sections:
            nav.insert(tk.END, sec.get("title", ""))

        # Right: reader
        reader_frame = ttk.Frame(outer)
        reader_frame.grid(row=0, column=1, sticky="nsew")
        body = tk.Text(reader_frame, wrap="word", relief="flat",
                       font=("Arial", self.font_size - 2), padx=10, pady=8,
                       borderwidth=0, highlightthickness=0)
        body_sb = ttk.Scrollbar(reader_frame, orient="vertical", command=body.yview)
        body.configure(yscrollcommand=body_sb.set, state="disabled")
        body_sb.pack(side="right", fill="y")
        body.pack(side="left", fill="both", expand=True)
        body.tag_configure("title", font=("Arial", self.font_size, "bold"),
                           spacing3=8)
        body.tag_configure("notice", foreground="#888888",
                           font=("Arial", self.font_size - 3, "italic"),
                           spacing3=10)

        def show_section(idx):
            if not sections:
                return
            sec = sections[idx]
            body.config(state="normal")
            body.delete("1.0", tk.END)
            if fallback_used:
                body.insert(tk.END,
                            "(Detailed manual not yet available in this language; "
                            "showing English.)\n\n", "notice")
            body.insert(tk.END, sec.get("title", "") + "\n", "title")
            body.insert(tk.END, sec.get("body", ""))
            body.config(state="disabled")

        def on_select(_evt=None):
            sel = nav.curselection()
            if sel:
                show_section(sel[0])

        nav.bind("<<ListboxSelect>>", on_select)
        if sections:
            nav.selection_set(0)
            nav.activate(0)
            show_section(0)

        # Bottom row: contact + close
        bottom = ttk.Frame(win)
        bottom.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        contact = tk.Label(bottom, text="fescherfrenn@outlook.com",
                           font=("Arial", self.font_size - 3), foreground="blue", cursor="hand2")
        contact.pack(side="left")
        contact.bind("<Button-1>", lambda e: webbrowser.open("mailto:fescherfrenn@outlook.com"))
        ttk.Button(bottom, text=L["close"], command=win.destroy).pack(side="right")
        win.bind("<Return>", lambda e: win.destroy())

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
            if name == L["select_participant"] or not name or self._is_catch_separator(name):
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
            track = self.data.get("track_details", False)
            if not track:
                length = None
                fish_type = ""
            else:
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
            self.refresh_rankings()
            if self.catch_name is not None:
                self.catch_name["values"] = self.catch_dropdown_values()
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

    def copyright_text(self):
        """Copyright line with the runtime-computed year span substituted in."""
        L = LANGUAGES[self.lang]
        yr = datetime.now().year
        span = "2025" if yr <= 2025 else f"2025 - {yr}"
        return L["copyright"].replace("{year_span}", span)

    def compute_rankings(self, catches_dict, title):
        """Return a list of (text, tag) segments for a rankings block.

        Order: Total Weight -> Most Catches -> Longest Fish -> Heaviest Fish.
        When the event does not track length/type, the last two blocks are
        rendered with the 'dim' tag and not computed.
        """
        L = LANGUAGES[self.lang]
        track = self.data.get("track_details", False)
        out = [(f"{title}\n\n", "head")]

        total_weights = {n: sum(c["weight"] for c in cs)
                         for n, cs in catches_dict.items()}
        top_w = sorted(total_weights.items(), key=lambda x: x[1], reverse=True)[:3]
        out.append((f"{L['rank_weight']}:\n", "sub"))
        for idx, (n, w) in enumerate(top_w, 1):
            out.append((f"{idx}. {n}: {self.fmt_weight(w)} g\n", "normal"))

        num_catches = {n: sum(c["num_catches"] for c in cs)
                       for n, cs in catches_dict.items()}
        top_c = sorted(num_catches.items(), key=lambda x: x[1], reverse=True)[:3]
        out.append((f"\n{L['rank_catches']}:\n", "sub"))
        for idx, (n, c) in enumerate(top_c, 1):
            out.append((f"{idx}. {n}: {c}\n", "normal"))

        single = [(n, c) for n, cs in catches_dict.items()
                  for c in cs if c["num_catches"] == 1]

        tag = "sub" if track else "dim"
        out.append((f"\n{L['rank_longest']}:", tag))
        if track:
            out.append(("\n", "normal"))
            top_l = sorted(single, key=lambda x: x[1]["length"] or 0, reverse=True)[:3]
            for idx, (n, c) in enumerate(top_l, 1):
                out.append((f"{idx}. {n}: {c['length'] or 0} cm\n", "normal"))
        else:
            out.append((f" {L['details_disabled_note']}\n", "dim"))

        out.append((f"\n{L['rank_heaviest']}:", tag))
        if track:
            out.append(("\n", "normal"))
            top_h = sorted(single, key=lambda x: x[1]["weight"], reverse=True)[:3]
            for idx, (n, c) in enumerate(top_h, 1):
                out.append((f"{idx}. {n}: {self.fmt_weight(c['weight'])} g\n", "normal"))
        else:
            out.append((f" {L['details_disabled_note']}\n", "dim"))
        return out

    def round_rankings_segments(self):
        L = LANGUAGES[self.lang]
        mk = self.current_manche
        cd = self.data["sessions"][mk]["catches"]
        return self.compute_rankings(cd, f'{L["live_rankings"]} - {key_to_display(self.lang, mk)}')

    def overall_rankings_segments(self):
        L = LANGUAGES[self.lang]
        pooled = {}
        for sk in SESSION_KEYS:
            for n, cs in self.data["sessions"][sk]["catches"].items():
                pooled.setdefault(n, []).extend(cs)
        return self.compute_rankings(pooled, L["overall_rankings"])

    def _style_ranking_text(self, widget):
        widget.tag_configure("head", font=("Arial", max(9, self.font_size - 2), "bold"))
        widget.tag_configure("sub", font=("Arial", max(8, self.font_size - 3), "bold"))
        widget.tag_configure("normal", font=("Arial", max(8, self.font_size - 3)))
        widget.tag_configure("dim", foreground="#999999",
                             font=("Arial", max(8, self.font_size - 3), "italic"))

    def render_rankings(self, widget, segments):
        if widget is None:
            return
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        for txt, tag in segments:
            widget.insert(tk.END, txt, tag)
        widget.config(state="disabled")

    def refresh_rankings(self):
        self.render_rankings(self.rankings, self.round_rankings_segments())
        self.render_rankings(self.overall_rankings, self.overall_rankings_segments())


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

    def catch_dropdown_values(self):
        """Names for the catch combobox, partitioned into those without a catch
        recorded in the current round (top) and those who already have at least
        one (below a non-selectable separator). Both groups alphabetical; all
        names remain selectable."""
        L = LANGUAGES[self.lang]
        sess = self.data["sessions"][self.current_manche]
        parts = sorted(sess["participants"], key=str.lower)
        no_catch, has_catch = [], []
        for n in parts:
            (has_catch if sess["catches"].get(n) else no_catch).append(n)
        out = list(no_catch)
        if has_catch:
            if out:
                out.append(L["catch_recorded_group"])
            out.extend(has_catch)
        return out

    def _is_catch_separator(self, s):
        return s == LANGUAGES[self.lang]["catch_recorded_group"]

    def on_manche_changed(self, event=None):
        self.current_manche = display_to_key(self.lang, self.manche_var.get())
        self.refresh_manche_view()
        self._update_combined_state()

    def _update_combined_state(self):
        """Combined ranking is only meaningful on the Final."""
        if self.combined_chk is None:
            return
        if self.current_manche == "final":
            self.combined_chk.config(state="normal")
        else:
            self.combined_chk.config(state="disabled")
            self.include_combined_var.set(False)

    def refresh_manche_view(self):
        L = LANGUAGES[self.lang]
        if self.catch_name is not None:
            self.catch_name["values"] = self.catch_dropdown_values()
            self.catch_name_var.set(L["select_participant"])
            self.catch_name.config(foreground='grey')
        self.refresh_rankings()
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
        win.update_idletasks()  # macOS: ensure window is mapped before grabbing
        win.grab_set()
        win.geometry("980x560")

        close_bar = ttk.Frame(win)
        close_bar.pack(side="bottom", fill="x")
        container = ttk.Frame(win, padding=10)
        container.pack(side="top", fill="both", expand=True)
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
        roster_btns = ttk.Frame(left)
        roster_btns.pack(side="bottom", fill="x", pady=(6, 0))
        roster_sb.pack(side="right", fill="y")
        roster_tv.pack(side="top", fill="both", expand=True)

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

        def refresh_panes():
            roster_tv.delete(*roster_tv.get_children())
            in_round = set(self.data["sessions"][self.current_manche]["participants"])
            for name in sorted(self.data["participants"].keys(), key=str.lower):
                if name in in_round:
                    continue  # already assigned to this round -> hide from roster list
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
        close_bar.columnconfigure(0, weight=1)
        ttk.Button(close_bar, text=L["close"], command=win.destroy).grid(row=0, column=0, pady=6)

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
        # Combobox (not readonly): suggestions come from the existing roster
        # so existing club names get reused; typing a new one is still allowed.
        club_entry = ttk.Combobox(frame, font=("Arial", self.font_size), width=20,
                                  values=self.known_clubs(), validate="key",
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
        win.update_idletasks()  # macOS: ensure window is mapped before grabbing
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
        # Button bar must be packed before the expanding tree, otherwise the
        # tree consumes its space and the buttons become invisible.
        btns = ttk.Frame(frame)
        btns.pack(side="bottom", fill="x", pady=6)
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
        if self.data.get("track_details", False):
            num_entry.delete(0, tk.END)
            num_entry.insert(0, "1")
            num_entry.config(state="disabled")

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

    # --- v3.0 invoicing -------------------------------------------
    FRENCH_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin",
                     "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

    def format_french_date(self, dt):
        return f"{dt.day} {self.FRENCH_MONTHS[dt.month - 1]} {dt.year}"

    def event_year(self):
        try:
            return datetime.strptime(self.data["event"].get("date", ""), "%d/%m/%Y").year
        except (ValueError, KeyError):
            return datetime.now().year

    @staticmethod
    def _canonical_clubs(club_names):
        """Group club names case-insensitively and pick a canonical display form.

        For each case-folded key, the canonical form is the most-used variant;
        ties are broken alphabetically (so 'FF Stengefort' wins over 'ff
        stengefort' when both occur the same number of times).
        Returns a list of canonical club names sorted case-insensitively.
        """
        from collections import Counter
        groups = {}  # key = casefold(name), value = Counter of original spellings
        for raw in club_names:
            name = (raw or "").strip()
            if not name:
                continue
            key = name.casefold()
            groups.setdefault(key, Counter())[name] += 1
        canonical = []
        for key, counter in groups.items():
            # Sort by (-count, name) so highest count wins; alphabetical tiebreak.
            best = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            canonical.append(best)
        return sorted(canonical, key=str.casefold)

    def invoice_clubs(self, except_invoice_index=None):
        """Distinct non-empty club names of participants assigned to any round,
        grouped case-insensitively.

        v3.3: clubs that have already been invoiced (as clubs) are still listed,
        but moved to a final "Already Invoiced" section under a non-selectable
        separator. ``except_invoice_index`` lets the form exclude the invoice
        currently being edited from the already-invoiced set.
        """
        L = LANGUAGES[self.lang]
        assigned = set()
        for sk in SESSION_KEYS:
            assigned.update(self.data["sessions"][sk]["participants"])
        names = []
        for n in assigned:
            info = self.data["participants"].get(n, {})
            names.append(info.get("club") or "")
        all_clubs = self._canonical_clubs(names)
        invoiced_cf = self._invoiced_clubs_cf(except_invoice_index)
        fresh, used = [], []
        for c in all_clubs:
            (used if c.strip().casefold() in invoiced_cf else fresh).append(c)
        out = list(fresh)
        if used:
            if out:
                out.append(L["inv_separator"])
            out.append(L["inv_already_invoiced_group"])
            out.extend(used)
        return out

    def known_clubs(self):
        """Roster-wide list of distinct club names, case-insensitively grouped.

        Used by the participant form so a club already entered for one person
        is suggested when adding/editing another - prevents accidental
        spelling/case drift that would split a club's invoice into two."""
        return self._canonical_clubs(
            (info.get("club") or "") for info in self.data["participants"].values())

    def invoice_individuals_dropdown(self, except_invoice_index=None):
        """List shown when 'Individual' is selected.

        Group 1: assigned participants whose club is blank/null, alphabetical.
        Group 2: all *other* assigned participants, alphabetical.
        Group 3 (v3.3): anyone who has already been invoiced *as an individual*
            in this event (drawn from groups 1+2). They are still pickable -
            corrective invoices are sometimes legitimate - but visually demoted.

        Each group is preceded by a non-selectable header and separated from
        the previous by a non-selectable separator string.
        """
        L = LANGUAGES[self.lang]
        assigned = set()
        for sk in SESSION_KEYS:
            assigned.update(self.data["sessions"][sk]["participants"])
        invoiced = self._invoiced_individual_names(except_invoice_index)

        true_indiv, others, already = [], [], []
        for n in sorted(assigned, key=str.lower):
            if n in invoiced:
                already.append(n)
                continue
            info = self.data["participants"].get(n, {})
            if (info.get("club") or "").strip() == "":
                true_indiv.append(n)
            else:
                others.append(n)

        items = []
        if true_indiv:
            items.append(L["inv_individuals_group"])
            items.extend(true_indiv)
        if others:
            if items:
                items.append(L["inv_separator"])
            items.append(L["inv_others_group"])
            items.extend(others)
        if already:
            if items:
                items.append(L["inv_separator"])
            items.append(L["inv_already_invoiced_group"])
            items.extend(already)
        return items

    def invoice_quantity_for_club(self, club_name):
        """Sum of round-assignments across all participants whose club matches.

        Counts assignments to rounds (Manche 1/2/3/Final) regardless of catches.
        """
        target = (club_name or "").strip().casefold()
        qty = 0
        for sk in SESSION_KEYS:
            for n in self.data["sessions"][sk]["participants"]:
                info = self.data["participants"].get(n, {})
                if (info.get("club") or "").strip().casefold() == target:
                    qty += 1
        return qty

    def invoice_quantity_for_individual(self, name):
        qty = 0
        for sk in SESSION_KEYS:
            if name in self.data["sessions"][sk]["participants"]:
                qty += 1
        return qty

    def _is_separator_label(self, s):
        L = LANGUAGES[self.lang]
        return s in (L["inv_individuals_group"], L["inv_others_group"],
                     L["inv_separator"], L["inv_already_invoiced_group"])

    def open_invoices_manager(self):
        if not self.check_event_details():
            return
        self.update_event()
        L = LANGUAGES[self.lang]

        win = Toplevel(self.root)
        win.title(L["manage_invoices"])
        win.transient(self.root)
        win.update_idletasks()  # macOS: ensure window is mapped before grabbing
        win.grab_set()
        win.geometry("840x440")

        outer = ttk.Frame(win, padding=10)
        outer.pack(fill="both", expand=True)
        # Pack the button bar FIRST so it survives the expanding tree.
        btns = ttk.Frame(outer)
        btns.pack(side="bottom", fill="x", pady=(8, 0))

        cols = ("number", "date", "client", "amount")
        headers = [L["inv_number"], L["inv_date"], L["inv_col_client"], L["inv_col_amount"]]
        widths = [160, 110, 340, 100]
        tv = ttk.Treeview(outer, columns=cols, show="headings", height=14)
        for c, h, w in zip(cols, headers, widths):
            tv.heading(c, text=h)
            tv.column(c, width=w, anchor="w" if c in ("number", "client") else "center")
        sb = ttk.Scrollbar(outer, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="top", fill="both", expand=True)

        def refresh():
            tv.delete(*tv.get_children())
            invs = self.data.get("invoices", [])
            if not invs:
                tv.insert("", "end", values=("", "", L["no_invoices"], ""))
                return
            for idx, inv in enumerate(invs):
                tv.insert("", "end", iid=str(idx), values=(
                    inv.get("number", ""),
                    inv.get("date", ""),
                    inv.get("recipient_name", ""),
                    self.fmt_money(inv.get("amount", 0))))

        def selected_index():
            sel = tv.selection()
            if not sel:
                messagebox.showinfo(L["manage_invoices"], L["select_row"])
                return None
            try:
                return int(sel[0])
            except ValueError:
                return None

        def do_new():
            # On macOS, two stacked grabs (manager + form) breaks click routing
            # if the form has no grab of its own. Release the manager's grab
            # while the form is open, then reclaim it on return so the manager
            # stays modal once the form closes.
            win.grab_release()
            try:
                self.open_invoice_form(on_done=refresh)
            finally:
                if win.winfo_exists():
                    win.grab_set()

        def do_edit():
            idx = selected_index()
            if idx is None:
                return
            win.grab_release()
            try:
                self.open_invoice_form(edit_index=idx, on_done=refresh)
            finally:
                if win.winfo_exists():
                    win.grab_set()

        def do_reprint():
            idx = selected_index()
            if idx is None:
                return
            inv = self.data["invoices"][idx]
            try:
                self.write_invoice_pdf(inv)
                messagebox.showinfo("", L["inv_saved"])
            except Exception as e:
                logging.error(f"Reprint failed: {e}")
                messagebox.showerror("Error", str(e))

        def do_delete():
            idx = selected_index()
            if idx is None:
                return
            if self.custom_dialog(L["manage_invoices"], L["confirm_delete_invoice"],
                                  [(L["yes"], True), (L["no"], False)]):
                inv = self.data["invoices"].pop(idx)
                # Best-effort: remove the on-disk PDF; the number stays burned.
                try:
                    pdf_path = self._invoice_pdf_path(inv)
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
                except Exception as e:
                    logging.warning(f"Could not delete invoice PDF: {e}")
                self.update_event()
                refresh()

        ttk.Button(btns, text=L["new_invoice"], command=do_new).pack(side="left", padx=3)
        ttk.Button(btns, text=L["edit"], command=do_edit).pack(side="left", padx=3)
        ttk.Button(btns, text=L["reprint_invoice"], command=do_reprint).pack(side="left", padx=3)
        ttk.Button(btns, text=L["delete"], command=do_delete).pack(side="left", padx=3)
        ttk.Button(btns, text=L["close"], command=win.destroy).pack(side="right", padx=3)
        refresh()
        win.wait_window()

    def fmt_money(self, value):
        """Localised price: '30' if integer, otherwise '30,50' (FR/DE/LB) or '30.50' (EN)."""
        try:
            v = float(value)
        except (TypeError, ValueError):
            return str(value)
        if abs(v - round(v)) < 0.005:
            s = f"{int(round(v))}"
        else:
            s = f"{v:.2f}"
        if self.lang in ["French", "German", "Luxembourgish"]:
            s = s.replace(".", ",")
        return s + "€"

    def _next_invoice_number(self, recompute_from=None):
        """Return next sequence integer and increment the in-memory counter."""
        if self.data.get("invoice_next") is None:
            start = recompute_from
            if start is None:
                start = self.data.get("invoice_seq_start")
            if start is None:
                start = 1
            self.data["invoice_next"] = int(start)
        n = int(self.data["invoice_next"])
        self.data["invoice_next"] = n + 1
        return n

    def _invoice_pdf_path(self, inv):
        event = self.data["event"]
        event_name_file = str(event.get("name", "event")).replace(" ", "_")
        event_date = str(event.get("date", datetime.now().strftime("%d/%m/%Y")))
        try:
            date_obj = datetime.strptime(event_date, "%d/%m/%Y")
            date_str = date_obj.strftime("%Y%m%d")
        except ValueError:
            date_str = datetime.now().strftime("%Y%m%d")
        folder = f"{date_str}_{event_name_file}"
        os.makedirs(os.path.join(folder, "invoices"), exist_ok=True)
        return os.path.join(folder, "invoices", f"{inv.get('number', 'invoice')}.pdf")

    # ---- v3.2 cross-invoice helpers ------------------------------
    def _invoiced_individual_names(self, except_index=None):
        """Names of participants already invoiced individually in this event.

        ``except_index`` skips one invoice (used when editing - the invoice
        under edit shouldn't see itself as 'already issued')."""
        out = set()
        for i, inv in enumerate(self.data.get("invoices", [])):
            if except_index is not None and i == except_index:
                continue
            if inv.get("recipient_type") == "individual":
                out.add(inv.get("recipient_name", ""))
        return out

    def _invoiced_clubs_cf(self, except_index=None):
        """Case-folded names of clubs already invoiced as clubs."""
        out = set()
        for i, inv in enumerate(self.data.get("invoices", [])):
            if except_index is not None and i == except_index:
                continue
            if inv.get("recipient_type") == "club":
                out.add((inv.get("recipient_name") or "").strip().casefold())
        return out

    def open_invoice_form(self, edit_index=None, on_done=None):
        if not self.check_event_details():
            return
        L = LANGUAGES[self.lang]
        editing = edit_index is not None
        existing = self.data["invoices"][edit_index] if editing else None

        dlg = Toplevel(self.root)
        dlg.title(L["edit_invoice"] if editing else L["new_invoice"])
        dlg.transient(self.root)
        # NOTE: do NOT call dlg.grab_set() here. tkcalendar's DateEntry popup
        # opens as a separate Toplevel and is hidden behind a modal grab on
        # this dialog. transient() is enough to keep the form on top of the
        # main window without breaking the date picker.
        dlg.geometry("540x620")

        frame = ttk.Frame(dlg, padding=14)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        row = 0
        # Starting sequence (only for the *first* invoice of the event).
        if self.data.get("invoice_next") is None and self.data.get("invoice_seq_start") is None and not editing:
            ttk.Label(frame, text=L["inv_starting_seq"], font=("Arial", self.font_size)).grid(row=row, column=0, sticky="w", pady=4)
            seq_entry = ttk.Entry(frame, font=("Arial", self.font_size), width=10)
            seq_entry.grid(row=row, column=1, pady=4, sticky="w")
            seq_entry.insert(0, "1")
            row += 1
        else:
            seq_entry = None

        # Invoice number preview (read-only).
        next_num_int = self.data.get("invoice_next")
        if editing:
            number_preview = existing.get("number", "")
        else:
            year = self.event_year()
            prev = next_num_int if next_num_int is not None else (self.data.get("invoice_seq_start") or 1)
            number_preview = f'{CONFIG.get("invoice_prefix", "INV")}-{int(prev):02d}-{year}'
        ttk.Label(frame, text=L["inv_number"], font=("Arial", self.font_size)).grid(row=row, column=0, sticky="w", pady=4)
        number_var = tk.StringVar(value=number_preview)
        ttk.Entry(frame, textvariable=number_var, font=("Arial", self.font_size),
                  state="readonly", width=22).grid(row=row, column=1, pady=4, sticky="w")
        row += 1

        # Date (defaults to event date, editable).
        ttk.Label(frame, text=L["inv_date"], font=("Arial", self.font_size)).grid(row=row, column=0, sticky="w", pady=4)
        date_entry = DateEntry(frame, font=("Arial", self.font_size), date_pattern="dd/mm/yyyy", width=14)
        date_entry.grid(row=row, column=1, pady=4, sticky="w")
        try:
            init_date = existing["date"] if editing else self.data["event"].get("date")
            date_entry.set_date(init_date)
        except Exception:
            date_entry.set_date(datetime.now())
        row += 1

        # Recipient type radios.
        ttk.Label(frame, text=L["inv_recipient_type"], font=("Arial", self.font_size)).grid(row=row, column=0, sticky="w", pady=4)
        type_var = tk.StringVar(value=(existing.get("recipient_type", "club") if editing else "club"))
        rt_frame = ttk.Frame(frame)
        rt_frame.grid(row=row, column=1, pady=4, sticky="w")
        ttk.Radiobutton(rt_frame, text=L["inv_recipient_club"], variable=type_var, value="club",
                        command=lambda: rebuild_recipient()).pack(side="left", padx=(0, 14))
        ttk.Radiobutton(rt_frame, text=L["inv_recipient_individual"], variable=type_var, value="individual",
                        command=lambda: rebuild_recipient()).pack(side="left")
        row += 1

        # Recipient dropdown (rebuilt when type changes).
        rec_label = ttk.Label(frame, text=L["inv_select_club"], font=("Arial", self.font_size))
        rec_label.grid(row=row, column=0, sticky="w", pady=4)
        recipient_var = tk.StringVar(value=existing.get("recipient_name", "") if editing else "")
        recipient_combo = ttk.Combobox(frame, textvariable=recipient_var, font=("Arial", self.font_size),
                                       width=28, state="readonly")
        recipient_combo.grid(row=row, column=1, pady=4, sticky="ew")
        row += 1

        # Description.
        ttk.Label(frame, text=L["inv_description"], font=("Arial", self.font_size)).grid(row=row, column=0, sticky="w", pady=4)
        desc_entry = ttk.Entry(frame, font=("Arial", self.font_size), width=32, validate="key",
                               validatecommand=(self.root.register(self.validate_length), "%P"))
        desc_entry.grid(row=row, column=1, pady=4, sticky="ew")
        if editing:
            desc_entry.insert(0, existing.get("description", ""))
        else:
            try:
                ev_date = self.format_french_date(datetime.strptime(self.data["event"].get("date", ""), "%d/%m/%Y"))
            except ValueError:
                ev_date = ""
            ev_name = self.data["event"].get("name", "")
            desc_entry.insert(0, f"Manche Concours {ev_name} {ev_date}".strip())
        row += 1

        # Unit price.
        ttk.Label(frame, text=L["inv_unit_price"], font=("Arial", self.font_size)).grid(row=row, column=0, sticky="w", pady=4)
        price_entry = ttk.Entry(frame, font=("Arial", self.font_size), width=12, validate="key",
                                validatecommand=(self.root.register(self.validate_number), "%P"))
        price_entry.grid(row=row, column=1, pady=4, sticky="w")
        if editing:
            price_entry.insert(0, self.num_to_str(existing.get("unit_price", 0)))
        elif self.data.get("invoice_unit_price") is not None:
            # First invoice's price is suggested for all following ones (editable).
            price_entry.insert(0, self.num_to_str(self.data.get("invoice_unit_price")))
        row += 1

        # Quantity (suggested + editable).
        ttk.Label(frame, text=L["inv_quantity"], font=("Arial", self.font_size)).grid(row=row, column=0, sticky="w", pady=4)
        qty_entry = ttk.Entry(frame, font=("Arial", self.font_size), width=12, validate="key",
                              validatecommand=(self.root.register(self.validate_catches), "%P"))
        qty_entry.grid(row=row, column=1, pady=4, sticky="w")
        if editing:
            qty_entry.insert(0, str(existing.get("quantity", 1)))
        row += 1

        # Warning area: empty by default, filled by on_recipient_picked.
        warn_label = tk.Label(frame, text="", justify="left", anchor="w",
                              wraplength=480, foreground="#A04500",
                              font=("Arial", self.font_size - 2, "italic"))
        warn_label.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(6, 4))
        row += 1

        def rebuild_recipient():
            rt = type_var.get()
            except_idx = edit_index if editing else None
            if rt == "club":
                rec_label.config(text=L["inv_select_club"])
                recipient_combo["values"] = self.invoice_clubs(except_idx)
            else:
                rec_label.config(text=L["inv_select_individual"])
                recipient_combo["values"] = self.invoice_individuals_dropdown(except_idx)
            if not editing:
                recipient_var.set("")
                qty_entry.delete(0, tk.END)

        def on_recipient_picked(_evt=None):
            chosen = recipient_var.get()
            if self._is_separator_label(chosen):
                recipient_var.set("")
                warn_label.config(text="")
                return
            if not chosen:
                warn_label.config(text="")
                return
            # Edit mode: ignore the invoice currently being edited so it does
            # not count itself as already issued.
            except_idx = edit_index if editing else None
            invoiced_individuals = self._invoiced_individual_names(except_idx)
            invoiced_clubs_cf = self._invoiced_clubs_cf(except_idx)
            warnings = []

            if type_var.get() == "club":
                q = self.invoice_quantity_for_club(chosen)
                club_cf = chosen.strip().casefold()
                # v3.3: warn if the club itself has already been invoiced.
                if club_cf in invoiced_clubs_cf:
                    warnings.append(L["inv_warn_this_club_already_invoiced"])
                # Reduce by rounds of members already invoiced individually.
                deducted = 0
                already_n = 0
                for n, info in self.data["participants"].items():
                    if (info.get("club") or "").strip().casefold() != club_cf:
                        continue
                    if n in invoiced_individuals:
                        rounds = self.invoice_quantity_for_individual(n)
                        deducted += rounds
                        already_n += 1
                if already_n:
                    q = max(q - deducted, 0)
                    warnings.append(L["inv_warn_members_already_invoiced"]
                                    .format(n=already_n, m=deducted))
            else:
                q = self.invoice_quantity_for_individual(chosen)
                # Warn if this individual was already invoiced individually.
                if chosen in invoiced_individuals:
                    warnings.append(L["inv_warn_already_individual"])
                # Warn if this participant's club has already been invoiced.
                info = self.data["participants"].get(chosen, {})
                club = (info.get("club") or "").strip()
                if club and club.casefold() in invoiced_clubs_cf:
                    warnings.append(
                        L["inv_warn_club_already_invoiced"].format(club=club))

            qty_entry.delete(0, tk.END)
            qty_entry.insert(0, str(q))
            warn_label.config(text="\n".join(warnings))

        recipient_combo.bind("<<ComboboxSelected>>", on_recipient_picked)
        rebuild_recipient()
        if editing:
            recipient_var.set(existing.get("recipient_name", ""))
            on_recipient_picked()  # populate warnings on the edited invoice

        def do_save():
            # Validate the chunk.
            rt = type_var.get()
            recipient = recipient_var.get().strip()
            if not recipient or self._is_separator_label(recipient):
                messagebox.showerror("Error", L["inv_missing_recipient"])
                return
            desc = desc_entry.get().strip()
            if not desc:
                messagebox.showerror("Error", L["inv_missing_description"])
                return
            try:
                price = float(price_entry.get().replace(",", "."))
                if price <= 0:
                    raise ValueError
                if round(price * 100) != price * 100:  # more than 2 decimals
                    raise ValueError
            except (ValueError, AttributeError):
                messagebox.showerror("Error", L["inv_invalid_price"])
                return
            try:
                qty = int(qty_entry.get())
                if qty < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", L["inv_invalid_qty"])
                return
            if rt == "individual" and qty > 4:
                # Allowed (e.g. a caretaker paying for a minor); just inform.
                messagebox.showwarning("", L["inv_qty_indiv_high"])

            # Determine the sequence number but DO NOT advance the counter yet -
            # a later failure must not bump it (the v3.3 runaway-counter bug).
            start_val = None
            if editing:
                seq = existing["seq"]
                full_number = existing["number"]
            else:
                if seq_entry is not None:
                    try:
                        start_val = int(seq_entry.get())
                        if start_val < 1:
                            raise ValueError
                    except ValueError:
                        messagebox.showerror("Error", L["inv_invalid_qty"])
                        return
                    seq = start_val
                else:
                    seq = self.data.get("invoice_next")
                    if seq is None:
                        seq = self.data.get("invoice_seq_start") or 1
                full_number = f'{CONFIG.get("invoice_prefix", "INV")}-{int(seq):02d}-{self.event_year()}'

            date_str = date_entry.get_date().strftime("%d/%m/%Y")
            amount = round(qty * price, 2)

            invoice = {
                "seq": seq,
                "number": full_number,
                "date": date_str,
                "recipient_type": rt,
                "recipient_name": recipient,
                "description": desc,
                "unit_price": price,
                "quantity": qty,
                "amount": amount,
            }

            # Guarantee the list exists even for events created before this fix.
            self.data.setdefault("invoices", [])

            # Generate the PDF FIRST. If it fails, nothing is committed: no list
            # change, no counter advance, no half-saved state.
            try:
                self.write_invoice_pdf(invoice)
            except Exception as e:
                logging.error(f"Invoice PDF failed: {e}")
                messagebox.showerror("Error", f"PDF: {e}")
                return

            # PDF succeeded -> commit the record, and (new invoices only) the
            # counter and the suggested unit price.
            if editing:
                self.data["invoices"][edit_index] = invoice
            else:
                self.data["invoices"].append(invoice)
                if start_val is not None:
                    self.data["invoice_seq_start"] = start_val
                self.data["invoice_next"] = int(seq) + 1
                if self.data.get("invoice_unit_price") is None:
                    self.data["invoice_unit_price"] = price

            self.update_event()
            messagebox.showinfo("", L["inv_saved"])
            if on_done:
                on_done()
            dlg.destroy()

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=14)
        ttk.Button(button_frame, text=L["inv_save_generate"], command=do_save).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_frame, text=L["close"], command=dlg.destroy).pack(side=tk.LEFT, padx=4)
        dlg.wait_window()

    # --- invoice PDF writer (French, A4, fixed-layout) ------------
    # Toner-friendly blues (lighter than v3.0): readable white-on-blue but
    # noticeably less ink-heavy than the saturated reference.
    INV_BLUE_TOP = (95 / 255, 120 / 255, 200 / 255)
    INV_BLUE_BOTTOM = (75 / 255, 95 / 255, 170 / 255)
    INV_TEXT_DARK = (35 / 255, 35 / 255, 40 / 255)

    LEGAL_SUFFIXES = (" a.s.b.l.", " a.s.b.l", " A.S.B.L.", " A.S.B.L",
                      " ASBL", " S.A.", " S.A", " S.\u00e0 r.l.", " S.\u00e0r.l.",
                      " s.\u00e0 r.l.", " s.\u00e0r.l.", " GmbH", " AG")

    def _split_legal_name(self, name):
        """Return (line1, line2) for the right-column issuer block.

        Tries to detect a legal-form suffix (a.s.b.l., S.A., GmbH, ...) and put
        it on line 2. If no suffix is found, line 2 is empty - but layout
        always reserves space for it so the footer alignment stays symmetric.
        """
        name = (name or "").strip()
        for sfx in self.LEGAL_SUFFIXES:
            idx = name.lower().rfind(sfx.lower())
            if idx > 0:
                return name[:idx].strip(), name[idx:].strip()
        return name, ""


    def _fmt_invoice_amount(self, value):
        """Invoice amount: '30€' when whole, '30,50€' otherwise (French)."""
        try:
            v = float(value)
        except (TypeError, ValueError):
            return f"{value}€"
        if abs(v - round(v)) < 0.005:
            return f"{int(round(v))}€"
        return f"{v:.2f}".replace(".", ",") + "€"

    def write_invoice_pdf(self, invoice):
        """Render the French invoice PDF to its event folder."""
        path = self._invoice_pdf_path(invoice)
        c = _rlcanvas.Canvas(path, pagesize=A4)
        W, H = A4

        # --- watermark (drawn first, behind everything else) ---
        wm = "watermark.png"
        if os.path.exists(wm):
            try:
                c.saveState()
                c.setFillAlpha(0.12)
                size = 480
                c.drawImage(wm, (W - size) / 2, (H - size) / 2, width=size, height=size,
                            mask="auto", preserveAspectRatio=True)
                c.restoreState()
            except Exception as exc:
                logging.warning(f"Watermark draw failed: {exc}")

        # --- top blue banner -----------------------------------------
        banner_h = 180
        c.setFillColorRGB(*self.INV_BLUE_TOP)
        c.rect(0, H - banner_h, W, banner_h, stroke=0, fill=1)

        # FACTURE - big white
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 70)
        c.drawString(40, H - banner_h + 60, "FACTURE")

        # Right block: date + invoice number
        c.setFont("Helvetica", 12)
        try:
            inv_dt = datetime.strptime(invoice["date"], "%d/%m/%Y")
            date_str = self.format_french_date(inv_dt)
        except (ValueError, KeyError):
            date_str = invoice.get("date", "")
        # Date sits at the top; "Num\u00e9ro de facture" label and the full
        # invoice number stack underneath on two separate lines.
        c.drawRightString(W - 40, H - banner_h + 110, date_str)
        c.setFont("Helvetica-Bold", 13)
        c.drawRightString(W - 40, H - banner_h + 88, "Num\u00e9ro de facture")
        c.setFont("Helvetica", 12)
        full_number = invoice.get("number", "")
        if not full_number:
            seq = invoice.get("seq", "")
            try:
                full_number = f"{int(seq):02d}"
            except (TypeError, ValueError):
                full_number = str(seq)
        c.drawRightString(W - 40, H - banner_h + 70, full_number)

        # --- white body ---------------------------------------------
        body_top = H - banner_h - 30
        c.setFillColorRGB(*self.INV_TEXT_DARK)

        # CLIENT block
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, body_top, "CLIENT")
        c.setFont("Helvetica", 12)
        c.drawString(40, body_top - 22, invoice.get("recipient_name", ""))

        # Long horizontal separator
        sep_y = body_top - 56
        c.setStrokeColorRGB(0.6, 0.6, 0.6)
        c.setLineWidth(0.6)
        c.line(40, sep_y, W - 40, sep_y)

        # Table header
        col_desc_x = 40
        col_qty_x = 360
        col_tva_x = 440
        col_amt_x = W - 40   # right-aligned
        header_y = sep_y - 90
        c.setFont("Helvetica-Bold", 11)
        c.drawString(col_desc_x, header_y, "Description")
        c.drawString(col_qty_x, header_y, "Quantité")
        c.drawString(col_tva_x, header_y, "TVA")
        c.drawRightString(col_amt_x, header_y, "Amount")
        c.setLineWidth(0.4)
        c.line(40, header_y - 6, W - 40, header_y - 6)

        # One line item
        c.setFont("Helvetica", 11)
        line_y = header_y - 30
        c.drawString(col_desc_x, line_y, invoice.get("description", ""))
        c.drawString(col_qty_x, line_y, str(invoice.get("quantity", "")))
        c.drawString(col_tva_x, line_y, "0%")
        amount_str = self._fmt_invoice_amount(invoice.get("amount", 0))
        c.drawRightString(col_amt_x, line_y, amount_str)
        c.line(40, line_y - 14, W - 40, line_y - 14)

        # Totals stack on the right
        totals = [
            ("Sous-total", amount_str, False),
            ("TVA", "0€", False),
            ("Total", amount_str, True),
        ]
        tot_y = line_y - 38
        for label, value, bold in totals:
            c.setFont("Helvetica-Bold" if bold else "Helvetica", 11 if not bold else 12)
            c.drawRightString(col_tva_x + 28, tot_y, label)
            c.drawRightString(col_amt_x, tot_y, value)
            tot_y -= 22
        c.setLineWidth(0.4)
        c.line(40, line_y - 28, W - 40, line_y - 28)

        # Payment terms text
        days = CONFIG.get("payment_terms_days", 30)
        legal = CONFIG.get("issuer_legal_name", "")
        terms = (f"À transférer sur le compte courant de {legal} dans un "
                 f"délai de {days} jours calendaires à compter de la date d'émission")
        c.setFont("Helvetica", 10)
        terms_y = tot_y - 30
        # naive word wrap to fit within body width
        words = terms.split()
        max_w = W - 80
        line = ""
        for w in words:
            test = (line + " " + w).strip()
            if c.stringWidth(test, "Helvetica", 10) <= max_w:
                line = test
            else:
                c.drawString(40, terms_y, line)
                terms_y -= 14
                line = w
        if line:
            c.drawString(40, terms_y, line)

        # --- bottom navy banner --------------------------------
        # Symmetric 2-line header on both sides + 4 content lines = 6 lines.
        # Banner height reduced from 200pt to 160pt with the new layout.
        foot_h = 160
        c.setFillColorRGB(*self.INV_BLUE_BOTTOM)
        c.rect(0, 0, W, foot_h, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)

        header_y = foot_h - 28
        line_step = 16
        content_y = header_y - 30  # 30pt gap below the header pair

        # ----- LEFT column: payment info ---------------------------
        lx = 40
        c.setFont("Helvetica-Bold", 13)
        c.drawString(lx, header_y, "INFORMATIONS DE PAIEMENT")
        # Second header line intentionally blank for layout parity with right.
        ly = content_y
        c.setFont("Helvetica", 10)
        c.drawString(lx, ly, f"Nom: {CONFIG.get('bank_account_holder', '')}")
        ly -= line_step
        c.drawString(lx, ly, f"Banque : {CONFIG.get('bank_name', '')}")
        ly -= line_step
        c.drawString(lx, ly, "Numéro de compte :")
        ly -= line_step
        c.drawString(lx, ly, " ".join(CONFIG.get("iban_groups", [])))

        # ----- RIGHT column: issuer (legal name in 2 lines) --------
        rx = W / 2 - 10
        line1, line2 = self._split_legal_name(CONFIG.get("issuer_legal_name", ""))
        c.setFont("Helvetica-Bold", 13)
        c.drawString(rx, header_y, line1.upper())
        # Always advance even if line 2 is blank - keeps the row count even
        # with the left side and keeps the layout predictable.
        if line2:
            c.drawString(rx, header_y - 18, line2.upper())
        ry = content_y
        c.setFont("Helvetica", 10)
        addr1 = (f"{CONFIG.get('issuer_house_number', '')}, "
                 f"{CONFIG.get('issuer_street', '')}, "
                 f"{CONFIG.get('issuer_postcode_country', '')}-"
                 f"{CONFIG.get('issuer_postcode_digits', '')},")
        c.drawString(rx, ry, addr1)
        ry -= line_step
        addr2 = f"{CONFIG.get('issuer_city', '')}, {CONFIG.get('issuer_country', '')}"
        c.drawString(rx, ry, addr2)
        ry -= line_step
        c.drawString(rx, ry, CONFIG.get("issuer_phone", ""))
        ry -= line_step
        c.drawString(rx, ry, CONFIG.get("issuer_email", ""))

        c.showPage()
        c.save()
        return path

    # --- Settings dialog -----------------------------------------
    def _validate_iban_groups(self, groups):
        if len(groups) != 6:
            return False
        g0 = groups[0]
        if not (len(g0) == 4 and g0.isalpha()):
            return False
        g1 = groups[1]
        if not (len(g1) == 4 and g1[:2].isalpha() and g1[2:].isdigit()):
            return False
        for g in groups[2:]:
            if not (len(g) == 4 and g.isdigit()):
                return False
        return True

    def open_settings_dialog(self):
        L = LANGUAGES[self.lang]
        dlg = Toplevel(self.root)
        dlg.title(L["settings_title"])
        dlg.transient(self.root)
        dlg.update_idletasks()  # macOS: ensure window is mapped before grabbing
        dlg.grab_set()
        dlg.geometry("640x680")

        outer = ttk.Frame(dlg, padding=12)
        outer.pack(fill="both", expand=True)
        # Stable button bar at the bottom (pack first to survive scroll).
        btn_bar = ttk.Frame(outer)
        btn_bar.pack(side="bottom", fill="x", pady=(8, 0))

        canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas)
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        entries = {}

        def add_row(parent, key, label, width=32):
            r = parent.grid_size()[1]
            ttk.Label(parent, text=label, font=("Arial", self.font_size)).grid(
                row=r, column=0, sticky="w", pady=3, padx=(0, 8))
            e = ttk.Entry(parent, font=("Arial", self.font_size), width=width)
            e.grid(row=r, column=1, sticky="ew", pady=3)
            val = CONFIG.get(key, "")
            if isinstance(val, list):
                val = " ".join(val)
            e.insert(0, str(val))
            entries[key] = e

        sec1 = ttk.LabelFrame(body, text=L["settings_invoice_section"], padding=8)
        sec1.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        sec1.columnconfigure(1, weight=1)
        for k, lk in [
            ("invoice_prefix", "settings_field_invoice_prefix"),
            ("issuer_name", "settings_field_issuer_name"),
            ("issuer_legal_name", "settings_field_issuer_legal_name"),
            ("issuer_house_number", "settings_field_house_number"),
            ("issuer_street", "settings_field_street"),
            ("issuer_postcode_country", "settings_field_postcode_country"),
            ("issuer_postcode_digits", "settings_field_postcode_digits"),
            ("issuer_city", "settings_field_city"),
            ("issuer_country", "settings_field_country"),
            ("issuer_phone", "settings_field_phone"),
            ("issuer_email", "settings_field_email"),
        ]:
            add_row(sec1, k, L[lk])

        sec2 = ttk.LabelFrame(body, text=L["settings_bank_section"], padding=8)
        sec2.grid(row=1, column=0, columnspan=2, sticky="ew")
        sec2.columnconfigure(1, weight=1)
        for k, lk in [
            ("bank_account_holder", "settings_field_bank_account_holder"),
            ("bank_name", "settings_field_bank_name"),
            ("iban_groups", "settings_field_iban"),
            ("payment_terms_days", "settings_field_payment_terms"),
        ]:
            add_row(sec2, k, L[lk])

        def do_save():
            new_cfg = dict(CONFIG)
            for k, e in entries.items():
                new_cfg[k] = e.get().strip()
            # Special parses / validations
            # IBAN
            raw = new_cfg.get("iban_groups", "")
            raw_norm = "".join(raw.split()).upper()
            groups = [raw_norm[i:i + 4] for i in range(0, len(raw_norm), 4)]
            if not self._validate_iban_groups(groups):
                messagebox.showerror("Error", L["settings_invalid_iban"])
                return
            new_cfg["iban_groups"] = groups
            # postcode
            pc_country = new_cfg.get("issuer_postcode_country", "").upper()
            pc_digits = new_cfg.get("issuer_postcode_digits", "")
            if not (1 <= len(pc_country) <= 2 and pc_country.isalpha() and pc_digits.isdigit() and len(pc_digits) == 4):
                messagebox.showerror("Error", L["settings_invalid_postcode"])
                return
            new_cfg["issuer_postcode_country"] = pc_country
            # phone
            phone = new_cfg.get("issuer_phone", "")
            if phone and not all(ch.isdigit() or ch in "+ " for ch in phone):
                messagebox.showerror("Error", L["settings_invalid_phone"])
                return
            # email
            import re as _re
            if not _re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", new_cfg.get("issuer_email", "")):
                messagebox.showerror("Error", L["settings_invalid_email"])
                return
            # payment terms days -> int
            try:
                new_cfg["payment_terms_days"] = int(new_cfg.get("payment_terms_days", 30))
            except ValueError:
                new_cfg["payment_terms_days"] = 30
            if save_config(new_cfg):
                messagebox.showinfo("", L["settings_saved"])
                dlg.destroy()

        ttk.Button(btn_bar, text=L["settings_save"], command=do_save).pack(side="left", padx=4)
        ttk.Button(btn_bar, text=L["close"], command=dlg.destroy).pack(side="right", padx=4)
        dlg.wait_window()

    def generate_report(self):
        L = LANGUAGES[self.lang]
        if not self.data["participants"]:
            messagebox.showerror("Error", L["error"])
            return
        sk = self.current_manche
        sess = self.data["sessions"][sk]
        if not sess["participants"]:
            messagebox.showinfo("", L["no_manche_participants"])
            return

        try:
            track = self.data.get("track_details", False)
            event = self.data["event"]
            event_name_file = str(event.get("name", "event")).replace(" ", "_")
            event_name_display = str(event.get("name", "event"))
            event_location = str(event.get("location", "Unknown Location"))
            event_date = str(event.get("date", datetime.now().strftime("%d/%m/%Y")))
            date_obj = datetime.strptime(event_date, "%d/%m/%Y")
            date_str = date_obj.strftime("%Y%m%d")
            folder_name = f"{date_str}_{event_name_file}"
            filename = f"{folder_name}/{folder_name}_{sk}.pdf"

            try:
                os.makedirs(folder_name, exist_ok=True)
            except PermissionError:
                messagebox.showerror("Error", L["permission_error"].replace("[folder]", folder_name))
                return

            # Portrait when length/type are not tracked, landscape when they are.
            page = landscape(letter) if track else letter
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

            sess_label = key_to_display(self.lang, sk)
            logo_path = "logo.png"
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=1 * inch, height=1 * inch)
                logo.hAlign = "LEFT"
                story.append(logo)
                story.append(Spacer(1, 12))
            story.append(Paragraph(L["summary_report"], styles["Title"]))
            story.append(Spacer(1, 12))
            story.append(Paragraph(f"{event_name_display} - {event_location} - {event_date}", center_style))
            story.append(Spacer(1, 12))

            # === Event Summary - current round only ===
            # Column set depends on whether length/type are tracked.
            if track:
                sum_headers = [L["name"].rstrip(":"), L["table_club"], L["table_category"],
                               L["table_remark"], L["table_participants"],
                               L["table_total_weight"], L["table_longest_fish"]]
                sum_widths = [32, 150, 95, 95, 110, 60, 75, 65]
            else:
                sum_headers = [L["name"].rstrip(":"), L["table_club"], L["table_category"],
                               L["table_remark"], L["table_participants"],
                               L["table_total_weight"]]
                sum_widths = [28, 132, 85, 80, 110, 50, 55]

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

            story.append(Paragraph(f'{L["summary_report"]} - {sess_label}', center_style))
            story.append(Spacer(1, 6))
            header_row = [Paragraph("#", normal_style)] + [Paragraph(h, normal_style) for h in sum_headers]
            table = [header_row]
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
                row = [
                    Paragraph(str(rank_i), normal_style),
                    Paragraph(str(name), normal_style),
                    Paragraph(info.get("club", "") or "", normal_style),
                    Paragraph(cat_disp, normal_style),
                    Paragraph(info.get("remark", "") or "", normal_style),
                    Paragraph(str(total_catches), normal_style),
                    Paragraph(self.fmt_weight(total_weight), normal_style),
                ]
                if track:
                    row.append(Paragraph(f"{longest}" if longest else "", normal_style))
                table.append(row)
            story.append(Table(table, colWidths=sum_widths, style=common_style, repeatRows=1))
            story.append(Spacer(1, 8))
            summary_text = (f"{L['summary']} {len(names_in_sess)} {L['summary_participants']}, "
                            f"{sess_total_catches} {L['summary_total_catches']}, "
                            f"{self.fmt_weight(sess_total_weight)} {L['summary_total_weight']}")
            story.append(Paragraph(summary_text, styles["Normal"]))

            include_combined = (sk == "final" and self.include_combined_var.get())
            include_individual = self.include_individual_var.get()

            # === Combined Ranking - All Rounds (Final + checkbox only) ===
            if include_combined:
                combined_rows = []
                grand_catches = 0
                grand_weight = 0
                for ssk in SESSION_KEYS:
                    ssess = self.data["sessions"][ssk]
                    ssess_label = key_to_display(self.lang, ssk)
                    for n in ssess["participants"]:
                        cc = ssess["catches"].get(n, [])
                        if not cc:
                            continue
                        tc = sum(c["num_catches"] for c in cc)
                        tw = sum(c["weight"] for c in cc)
                        lg = max((c["length"] for c in cc if c["length"] is not None), default=0)
                        combined_rows.append((n, ssess_label, tc, tw, lg))
                        grand_catches += tc
                        grand_weight += tw
                if combined_rows:
                    combined_rows.sort(key=lambda r: r[3], reverse=True)
                    story.append(PageBreak())
                    story.append(Paragraph(L["combined_report"], styles["Title"]))
                    story.append(Spacer(1, 8))
                    story.append(Paragraph(f"{event_name_display} - {event_location} - {event_date}", center_style))
                    story.append(Spacer(1, 12))
                    comb_headers = [L["table_participant_name"], L["session_column"],
                                    L["table_participants"], L["table_total_weight"]]
                    if track:
                        comb_headers.append(L["table_longest_fish"])
                        comb_widths = [40, 200, 110, 90, 110, 90]
                    else:
                        comb_widths = [34, 170, 95, 80, 90]
                    comb_table = [[Paragraph("#", normal_style)] +
                                  [Paragraph(h, normal_style) for h in comb_headers]]
                    for rank_i, (n, slabel, tc, tw, lg) in enumerate(combined_rows, 1):
                        crow = [
                            Paragraph(str(rank_i), normal_style),
                            Paragraph(n, normal_style),
                            Paragraph(slabel, normal_style),
                            Paragraph(str(tc), normal_style),
                            Paragraph(self.fmt_weight(tw), normal_style),
                        ]
                        if track:
                            crow.append(Paragraph(f"{lg}" if lg else "", normal_style))
                        comb_table.append(crow)
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
                    story.append(Table(comb_table, colWidths=comb_widths, style=comb_style, repeatRows=1))
                    story.append(Spacer(1, 8))
                    grand_text = (f"{L['summary']} {len(self.data['participants'])} {L['summary_participants']}, "
                                  f"{grand_catches} {L['summary_total_catches']}, "
                                  f"{self.fmt_weight(grand_weight)} {L['summary_total_weight']}")
                    story.append(Paragraph(grand_text, styles["Normal"]))

            # === Individual Reports for the current round ===
            if include_individual:
                if track:
                    ind_headers = [L["indiv_time"], L["indiv_type"], L["number_of_catches"],
                                   L["indiv_weight"], L["indiv_length"]]
                    indiv_widths = [80, 130, 90, 110, 110]
                else:
                    ind_headers = [L["indiv_time"], L["number_of_catches"], L["indiv_weight"]]
                    indiv_widths = [130, 130, 130]
                indiv_style = [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("LEADING", (0, 0), (-1, -1), 12),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, 1), (0, -1), "CENTER"),
                    ("WORDWRAP", (0, 0), (-1, -1), "CJK"),
                ]
                for rank_i, name in enumerate(sorted_names, 1):
                    catches = sorted(sess["catches"].get(name, []), key=lambda x: x["time"])
                    if not catches:
                        continue
                    story.append(PageBreak())
                    story.append(Paragraph(f"{event_name_display} - {event_location} - {event_date}", styles["Title"]))
                    story.append(Paragraph(f"{name} - {sess_label}", styles["Title"]))
                    story.append(Spacer(1, 8))
                    catch_table = [[Paragraph(h, normal_style) for h in ind_headers]]
                    max_w = max(c["weight"] for c in catches)
                    max_l = max((c["length"] or 0 for c in catches if c["length"] is not None), default=0)
                    for c in catches:
                        weight_val = c["weight"]
                        weight_par = Paragraph(self.fmt_weight(weight_val),
                                               bold_style if weight_val == max_w else normal_style)
                        if track:
                            fish_type = c.get("type", "") or "-"
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
                        else:
                            catch_table.append([
                                Paragraph(str(c.get("time", "")), normal_style),
                                Paragraph(str(c["num_catches"]), normal_style),
                                weight_par,
                            ])
                    story.append(Table(catch_table, colWidths=indiv_widths, style=indiv_style, repeatRows=1))
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

            # === Footer on every page (copyright with computed year span) ===
            footer_src = self.copyright_text()

            def add_footer(canvas, doc):
                canvas.saveState()
                canvas.setFont("Helvetica", 9)
                footer_text = footer_src.replace(
                    "fescherfrenn@outlook.com",
                    '<link href="mailto:fescherfrenn@outlook.com" color="blue">fescherfrenn@outlook.com</link>')
                p = Paragraph(footer_text, normal_style)
                w, h = p.wrap(doc.width, doc.bottomMargin)
                p.drawOn(canvas, doc.leftMargin, doc.bottomMargin - h - 6)
                canvas.restoreState()

            doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
            messagebox.showinfo(
                "Success",
                L["report_generated"].replace("[date]_[event_name]", f"{date_str}_{event_name_file}_{sk}"))
        except Exception as e:
            logging.error(f"generate_report failed: {e}")
            messagebox.showerror("Error", f"Report generation failed: {type(e).__name__}: {e}")

    def custom_dialog(self, title, message, buttons):
        dialog = Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.update_idletasks()  # macOS: ensure window is mapped before grabbing
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
            self.data = new_event_data(self.lang)
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

