import tkinter as tk
from tkinter import ttk, Toplevel, messagebox, filedialog
from tkcalendar import DateEntry, Calendar
import json
import os
from datetime import datetime
import getpass
import logging
import re
import webbrowser
import subprocess
import sys

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
APP_VERSION = "4.6"

# Set up logging
logging.basicConfig(filename='fescherfrenn.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

TRANSLATIONS_FILE = "translations.json"
CONFIG_FILE = "config.json"
HELP_FILE = "help.json"
SESSION_KEYS = ["manche1", "manche2", "manche3", "final"]
DEFAULT_MAX_ROUNDS = 12      # default app-wide ceiling for an event's rounds
ROUND_CEILING_HARD_MAX = 99  # absolute safety cap (guards against typos)
DEFAULT_MAX_PARTICIPANTS = 100   # default app-wide ceiling for per-round roster
PARTICIPANTS_CEILING_HARD_MAX = 999


def round_ceiling():
    """The current app-wide maximum number of rounds (from Settings/config),
    clamped to a sane 1..99 so a stray value can never explode the UI."""
    try:
        val = int(CONFIG.get("max_round_count", DEFAULT_MAX_ROUNDS))
    except (TypeError, ValueError):
        val = DEFAULT_MAX_ROUNDS
    return max(1, min(val, ROUND_CEILING_HARD_MAX))


def participants_ceiling():
    """App-wide maximum for max-participants-per-round (Settings/config),
    clamped to 1..999."""
    try:
        val = int(CONFIG.get("max_participants_count", DEFAULT_MAX_PARTICIPANTS))
    except (TypeError, ValueError):
        val = DEFAULT_MAX_PARTICIPANTS
    return max(1, min(val, PARTICIPANTS_CEILING_HARD_MAX))


def make_session_keys(num_rounds):
    """Round keys (manche1..mancheN) followed by the final."""
    n = max(1, int(num_rounds))
    return [f"manche{i}" for i in range(1, n + 1)] + ["final"]


def set_session_keys(num_rounds):
    """Point the module-level SESSION_KEYS at the current event's shape.

    The app only ever holds one event at a time, so a single global that
    tracks the active event's round count keeps every existing SESSION_KEYS
    reference correct without threading num_rounds through everything.
    """
    global SESSION_KEYS
    SESSION_KEYS = make_session_keys(num_rounds)
    return SESSION_KEYS


def highest_manche_index(sessions):
    """Largest N among 'mancheN' keys present in a sessions dict (0 if none)."""
    hi = 0
    if isinstance(sessions, dict):
        for k in sessions:
            if isinstance(k, str) and k.startswith("manche") and k[6:].isdigit():
                hi = max(hi, int(k[6:]))
    return hi

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
    "payment_terms_days": 30,
    "max_round_count": 12,        # app-wide ceiling for an event's configurable rounds
    "max_participants_count": 100,  # app-wide ceiling for max participants/round
    "invoice_banner_colour": "blue",  # header/footer tint (palette + "none")
    # Per-event defaults for new events (seeded to current behaviour):
    "default_track_details": False,
    "default_report_highlight": True,
    "default_report_highlight_colour": "green",
    "default_individual_reports": False,
    "default_combined_ranking": False,
    # App-level UI preferences (persist across launches via config.json).
    "theme_mode": "system",   # system | light | dark
    "lang": "English",        # English | French | German | Luxembourgish | Portuguese | Portuguese
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


def empty_sessions(num_rounds=None):
    keys = make_session_keys(num_rounds) if num_rounds else SESSION_KEYS
    return {k: {"participants": [], "catches": {}} for k in keys}


def new_event_data(lang="English", num_rounds=3):
    """A fresh, fully-formed event dict.

    Single source of truth for a blank event so the invoice keys can never
    go missing again (a missing "invoices" key caused silent save failures
    and a runaway invoice counter in v3.3).
    """
    set_session_keys(num_rounds)
    return {
        "event": {}, "participants": {}, "sessions": empty_sessions(num_rounds),
        "invoices": [], "invoice_seq_start": None, "invoice_next": None,
        "invoice_unit_price": None,
        "track_details": bool(CONFIG.get("default_track_details", False)),
        "config": {"num_rounds": num_rounds, "max_per_round": 30, "xproc": 10},
        "config_locked": False,
        "report_highlight": bool(CONFIG.get("default_report_highlight", True)),
        "report_highlight_colour": CONFIG.get("default_report_highlight_colour", "green"),
        "lang": lang, "version": APP_VERSION,
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

    # Determine the round count BEFORE touching sessions. Source of truth is
    # config.num_rounds, but never below the highest mancheN that already holds
    # data (so an event is never silently truncated). Then point SESSION_KEYS
    # at this event's shape for all the loops below.
    cfg_existing = data.get("config", {}) if isinstance(data.get("config"), dict) else {}
    declared = int(cfg_existing.get("num_rounds", 3) or 3)
    present_hi = highest_manche_index(data.get("sessions", {}))
    num_rounds = max(1, declared, present_hi)
    set_session_keys(num_rounds)

    if "sessions" not in data or not isinstance(data["sessions"], dict):
        data["sessions"] = empty_sessions()
    for key in SESSION_KEYS:
        sess = data["sessions"].get(key)
        if not isinstance(sess, dict):
            sess = {"participants": [], "catches": {}}
        sess.setdefault("participants", [])
        sess.setdefault("catches", {})
        data["sessions"][key] = sess
    # Drop any stray manche keys beyond the resolved count (they are guaranteed
    # empty because present_hi already folded non-empty ones into num_rounds).
    for key in list(data["sessions"].keys()):
        if key not in SESSION_KEYS:
            del data["sessions"][key]
    # Keep the sessions dict in canonical round order (tidy JSON).
    data["sessions"] = {k: data["sessions"][k] for k in SESSION_KEYS}

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
    cfg = data.setdefault("config", {})
    cfg["num_rounds"] = num_rounds   # resolved above (config vs. data present)
    cfg.setdefault("max_per_round", 30)
    cfg.setdefault("xproc", 10)
    data.setdefault("config_locked", False)
    data.setdefault("report_highlight", True)
    data.setdefault("report_highlight_colour", "green")
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
    return [key_to_display(lang, k) for k in SESSION_KEYS]


def key_to_display(lang, key):
    L = LANGUAGES[lang]
    if key == "final":
        return L["final"]
    if isinstance(key, str) and key.startswith("manche") and key[6:].isdigit():
        return L["round_label"].format(n=key[6:])
    return key


def display_to_key(lang, disp):
    if disp == LANGUAGES[lang]["final"]:
        return "final"
    digits = "".join(ch for ch in str(disp) if ch.isdigit())
    return f"manche{digits}" if digits else "manche1"


class FishingApp:
    # ---- Visual theme -----------------------------------------------------
    # Flat palette: panels share the window background and are delimited by
    # their border + label; tree/entry surfaces are slightly raised for
    # contrast. Badge colours are saturated "pill" chips, readable on both.
    THEMES = {
        "light": {
            "bg": "#f3f4f6", "surface": "#ffffff", "fg": "#1a1c1e", "fg_muted": "#5f6368",
            "accent": "#1a73e8", "accent_fg": "#ffffff", "border": "#d3d7dd",
            "tree_bg": "#ffffff", "tree_heading_bg": "#e8eaed", "sel_bg": "#1a73e8", "sel_fg": "#ffffff",
            "weight_fg": "#5f6368",
            "btn_bg": "#ffffff", "btn_light": "#ffffff", "btn_dark": "#c4c9d0", "btn_hover": "#eef3fd",
            "nav_bg": "#e4e7eb", "nav_fg": "#1a1c1e", "nav_active_bg": "#1a73e8", "nav_active_fg": "#ffffff",
            "badges": {"Q": ("#1e8e3e", "#ffffff"), "A": ("#1a73e8", "#ffffff"),
                       "?": ("#f9ab00", "#1a1c1e"), "D": ("#d93025", "#ffffff")},
        },
        "dark": {
            "bg": "#1e1f22", "surface": "#2b2d31", "fg": "#e3e5e8", "fg_muted": "#9aa0a6",
            "accent": "#5b9bff", "accent_fg": "#0b1320", "border": "#3a3d42",
            "tree_bg": "#26282c", "tree_heading_bg": "#34373c", "sel_bg": "#3b6fb6", "sel_fg": "#ffffff",
            "weight_fg": "#9aa0a6",
            "btn_bg": "#2b2d31", "btn_light": "#3a3d42", "btn_dark": "#161719", "btn_hover": "#33373d",
            "nav_bg": "#26282c", "nav_fg": "#e3e5e8", "nav_active_bg": "#5b9bff", "nav_active_fg": "#0b1320",
            "badges": {"Q": ("#2faa52", "#06210f"), "A": ("#5b9bff", "#06122b"),
                       "?": ("#e0a106", "#241900"), "D": ("#e2574d", "#2a0908")},
        },
    }

    def _detect_system_dark(self):
        """Best-effort OS dark-mode probe (macOS / Windows). Falls back to light."""
        import subprocess
        try:
            if sys.platform == "darwin":
                r = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                                   capture_output=True, text=True, timeout=1)
                return "dark" in (r.stdout or "").strip().lower()
            if sys.platform.startswith("win"):
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
                val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return val == 0
        except Exception as e:
            logging.info(f"system theme detection unavailable: {e}")
        return False

    def _resolve_theme_mode(self):
        mode = CONFIG.get("theme_mode", "system")
        if mode in ("light", "dark"):
            return mode
        return "dark" if self._detect_system_dark() else "light"

    def apply_theme(self):
        """Resolve the active theme and push it into ttk styles + the root /
        canvas backgrounds. Switches to the 'clam' base theme because the
        native macOS/Windows ttk themes ignore most colour options (so dark
        mode would otherwise be impossible)."""
        t = self.THEMES[self._resolve_theme_mode()]
        self.theme = t
        self.WEIGHT_FG = t["weight_fg"]
        fs = self.font_size
        try:
            style = ttk.Style()
            try:
                style.theme_use("clam")
            except Exception:
                pass
            style.configure(".", background=t["bg"], foreground=t["fg"],
                            fieldbackground=t["surface"], bordercolor=t["border"],
                            lightcolor=t["bg"], darkcolor=t["bg"], troughcolor=t["bg"])
            style.configure("TFrame", background=t["bg"])
            style.configure("TLabel", background=t["bg"], foreground=t["fg"])
            style.configure("TLabelframe", background=t["bg"], bordercolor=t["border"])
            style.configure("TLabelframe.Label", background=t["bg"], foreground=t["accent"],
                            font=("Arial", max(9, fs - 2), "bold"))
            style.configure("TButton", background=t["btn_bg"], foreground=t["fg"],
                            bordercolor=t["border"], lightcolor=t["btn_light"], darkcolor=t["btn_dark"],
                            relief="raised", borderwidth=2, padding=(14, 9),
                            font=("Arial", max(9, fs - 3)))
            style.map("TButton",
                      background=[("pressed", t["accent"]), ("active", t["btn_hover"])],
                      foreground=[("pressed", t["accent_fg"])],
                      relief=[("pressed", "sunken")])
            style.configure("Accent.TButton", background=t["accent"], foreground=t["accent_fg"],
                            lightcolor=t["accent"], darkcolor=t["accent"], relief="raised",
                            borderwidth=2, padding=(16, 10), font=("Arial", max(9, fs - 2), "bold"))
            style.map("Accent.TButton",
                      background=[("pressed", t["accent"]), ("active", t["accent"])],
                      foreground=[("pressed", t["accent_fg"]), ("active", t["accent_fg"])],
                      relief=[("pressed", "sunken")])
            style.configure("TCheckbutton", background=t["bg"], foreground=t["fg"])
            style.map("TCheckbutton", background=[("active", t["bg"])],
                      foreground=[("disabled", t["fg_muted"])])
            style.configure("TRadiobutton", background=t["bg"], foreground=t["fg"])
            style.map("TRadiobutton", background=[("active", t["bg"])])
            style.configure("TEntry", fieldbackground=t["surface"], foreground=t["fg"],
                            bordercolor=t["border"], insertcolor=t["fg"], padding=(6, 5))
            style.map("TEntry", fieldbackground=[("disabled", t["bg"])],
                      foreground=[("disabled", t["fg_muted"])])
            style.configure("TCombobox", fieldbackground=t["surface"], background=t["surface"],
                            foreground=t["fg"], bordercolor=t["border"], arrowcolor=t["fg"], padding=(6, 5))
            style.map("TCombobox", fieldbackground=[("readonly", t["surface"])],
                      foreground=[("readonly", t["fg"]), ("disabled", t["fg_muted"])])
            style.configure("Treeview", background=t["tree_bg"], fieldbackground=t["tree_bg"],
                            foreground=t["fg"], rowheight=int(fs * 2.15),
                            font=("Arial", max(9, fs - 4)), bordercolor=t["border"])
            style.configure("Treeview.Heading", background=t["tree_heading_bg"], foreground=t["fg"],
                            font=("Arial", max(9, fs - 4), "bold"), relief="flat")
            style.map("Treeview", background=[("selected", t["sel_bg"])],
                      foreground=[("selected", t["sel_fg"])])
            style.map("Treeview.Heading", background=[("active", t["tree_heading_bg"])])
            style.configure("Vertical.TScrollbar", background=t["surface"], troughcolor=t["bg"],
                            bordercolor=t["border"], arrowcolor=t["fg"])
            style.configure("Horizontal.TScrollbar", background=t["surface"], troughcolor=t["bg"],
                            bordercolor=t["border"], arrowcolor=t["fg"])
            # Header strip text styles.
            style.configure("HeaderTitle.TLabel", background=t["bg"], foreground=t["accent"],
                            font=("Arial", fs + 2, "bold"))
            style.configure("HeaderSub.TLabel", background=t["bg"], foreground=t["fg_muted"],
                            font=("Arial", max(9, fs - 3)))
            style.configure("PageName.TLabel", background=t["bg"], foreground=t["fg"],
                            font=("Arial", fs, "bold"))
            style.configure("HeaderLink.TLabel", background=t["bg"], foreground=t["accent"],
                            font=("Arial", max(9, fs - 3), "bold"))
        except Exception as e:
            logging.warning(f"apply_theme failed: {e}")
        try:
            self.root.configure(bg=t["bg"])
            self.canvas.configure(bg=t["bg"], highlightthickness=0)
            self.nav_bar.configure(style="TFrame")
        except Exception:
            pass

    def _on_theme_change(self, mode):
        """Persist the chosen theme mode and repaint the whole UI."""
        new_cfg = dict(CONFIG)
        new_cfg["theme_mode"] = mode
        try:
            save_config(new_cfg)
        except Exception as e:
            logging.warning(f"saving theme_mode failed: {e}")
        CONFIG.clear()
        CONFIG.update(new_cfg)
        self.apply_theme()
        self.build_main_ui()   # rebuild so tk widgets (nav, badges) repaint

    def _badge_colours(self, letter):
        return self.theme["badges"].get(letter, self.theme["badges"]["D"])

    def _make_pill(self, parent, text, bg, fg, fs):
        """A small rounded 'pill' badge drawn on a Canvas (true rounded
        corners, unlike a flat Label chip). Background matches the parent so
        the rounded edges blend into the theme."""
        pad_x, pad_y = 8, 3
        h = fs + 2 * pad_y + 2
        w = max(h, int(len(str(text)) * fs * 0.72) + 2 * pad_x)
        try:
            parent_bg = parent.cget("background")
        except Exception:
            parent_bg = self.theme["bg"]
        c = tk.Canvas(parent, width=w, height=h, highlightthickness=0, bd=0,
                      background=parent_bg)
        r = h / 2.0
        # Stadium / rounded-rect via a smoothed polygon.
        pts = [r, 0, w - r, 0, w, 0, w, r, w, h - r, w, h,
               w - r, h, r, h, 0, h, 0, h - r, 0, r, 0, 0]
        c.create_polygon(pts, smooth=True, fill=bg, outline=bg)
        c.create_text(w / 2.0, h / 2.0 + 1, text=str(text), fill=fg,
                      font=("Arial", fs, "bold"))
        return c

    def _event_subtitle(self):
        """One-line 'name · place · date' for the header, or a muted hint."""
        ev = self.data.get("event", {}) if hasattr(self, "data") else {}
        parts = [p for p in (str(ev.get("name", "")).strip(),
                             str(ev.get("location", "")).strip(),
                             str(ev.get("date", "")).strip()) if p]
        return " \u00b7 ".join(parts) if parts else LANGUAGES[self.lang].get("header_no_event", "")

    def _page_display_name(self, name):
        L = LANGUAGES[self.lang]
        return {"event": L["nav_event"], "participants": L["nav_participants"],
                "catch": L["nav_catch"], "rankings": L["nav_rankings"],
                "settings": L["nav_settings"]}.get(name, "")

    def __init__(self, root):
        self.root = root
        try:
            self.data = load_data()
            # Language is an app-level preference stored in config.json so it
            # always reopens as set. Migrate a previously-used event-file
            # language once (when config still holds the default).
            self.lang = CONFIG.get("lang", "English")
            if self.lang == "English" and self.data.get("lang") in LANGUAGES:
                self.lang = self.data["lang"]
            if self.lang not in LANGUAGES:
                self.lang = "English"
            CONFIG["lang"] = self.lang
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
            # Visual theme (light / dark / system) is applied once the canvas
            # exists, just below; ttk styles are global so a single apply()
            # covers every widget built afterwards.
            self.theme = self.THEMES["light"]

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
            # Initial state comes from the app-wide defaults (Settings).
            self.include_individual_var = tk.BooleanVar(value=bool(CONFIG.get("default_individual_reports", False)))
            self.include_combined_var = tk.BooleanVar(value=bool(CONFIG.get("default_combined_ranking", False)))
            self.combined_chk = None
            self.highlight_chk = None
            self.highlight_colour_combo = None
            self.reset_btn = None
            self.export_btn = None
            self.manage_events_btn = None
            self._open_panels = []
            self._close_confirm_open = False
            self.help_btn = None
            self.catch_name_var = None  # Added for Combobox hint
            self.track_details_var = None   # event-level: record length & type
            self.overall_rankings = None    # right-hand pooled rankings widget

            self.canvas = tk.Canvas(self.root)
            self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
            self.main_frame = ttk.Frame(self.canvas)
            self.canvas.configure(yscrollcommand=self.scrollbar.set)
            # Fixed bottom navigation bar (outside the scroll area so it never
            # scrolls away). Populated per-language in build_main_ui.
            self.nav_bar = ttk.Frame(self.root, padding=(4, 4))
            self.nav_bar.pack(side="bottom", fill="x")
            self.canvas.pack(side="left", fill="both", expand=True)
            self.scrollbar.pack(side="right", fill="y")
            self.canvas_frame = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
            self.main_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
            self.root.bind("<Configure>", self.on_resize)

            # Apply the visual theme now that the root, canvas and nav bar exist.
            self.apply_theme()

            # Paged UI: page frames live in a container; the bottom nav raises
            # one at a time. Populated in build_main_ui.
            self.pages = {}
            self.nav_buttons = {}
            self.current_page = "event"

            try:
                _raw_logo = tk.PhotoImage(file="logo.png")
                _factor = max(1, round(_raw_logo.height() / 100))
                self.logo = _raw_logo.subsample(_factor) if _factor > 1 else _raw_logo
                self.logo_label = ttk.Label(self.main_frame, image=self.logo)
                self.logo_label.grid(row=0, column=0, pady=5, padx=5, sticky="nw")
            except Exception:
                self.logo_label = ttk.Label(self.main_frame, text="Logo Placeholder (200x200px)", width=28, anchor="center")
                self.logo_label.grid(row=0, column=0, pady=5, padx=5, sticky="nw")

            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        except Exception as e:
            logging.error(f"Initialization failed: {str(e)}")
            messagebox.showerror("Error", f"Failed to start application: {str(e)}")
            self.root.destroy()

    def on_resize(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=self.canvas.winfo_width())

    def set_language(self, lang):
        if lang not in LANGUAGES:
            return
        self.lang = lang
        self.data["lang"] = lang
        self.root.title(LANGUAGES[self.lang]["title"])
        # Persist app-level language so it always reopens as set.
        new_cfg = dict(CONFIG)
        new_cfg["lang"] = lang
        try:
            save_config(new_cfg)
        except Exception as e:
            logging.warning(f"saving language failed: {e}")
        CONFIG.clear()
        CONFIG.update(new_cfg)
        self.build_main_ui()

    def _reject_input(self):
        """Give an audible cue and reject a keystroke (used by validators)."""
        try:
            self.root.bell()
        except Exception:
            pass
        return False

    def _center(self, win, w, h, parent=None):
        """Place a Toplevel at an explicit, stable position centred over its
        parent (falling back to the screen). Without an explicit +x+y, window
        managers position dialogs unpredictably - e.g. shifting as the window
        behind them grows - which is the cause of pop-ups 'wandering'."""
        x = y = None
        try:
            win.update_idletasks()
            ref = parent or self.root
            pw, ph = ref.winfo_width(), ref.winfo_height()
            if pw > 1 and ph > 1:
                x = ref.winfo_rootx() + (pw - w) // 2
                y = ref.winfo_rooty() + max(0, (ph - h) // 3)
        except Exception:
            x = None
        if x is None:
            try:
                sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            except Exception:
                sw, sh = 1280, 800
            x, y = (sw - w) // 2, (sh - h) // 3
        try:
            win.geometry(f"{w}x{h}+{max(0, int(x))}+{max(0, int(y))}")
        except Exception:
            win.geometry(f"{w}x{h}")

    def validate_number(self, input_str):
        if input_str == "":
            return True
        if self.lang in ["French", "German", "Luxembourgish", "Portuguese"]:
            input_str = input_str.replace(",", ".")
        if not re.match(r"^\d*\.?\d*$", input_str):
            return self._reject_input()
        return True

    def validate_catches(self, input_str):
        if input_str == "":
            return True
        if not re.match(r"^\d+$", input_str):
            return self._reject_input()
        return True

    def validate_round_count(self, input_str):
        """Round count typing: digits only, and never above the app-wide
        ceiling (Settings). So if the ceiling is 5 you cannot type 6 or 55;
        if it is 12 you can type up to 12. Range 1..ceiling is re-checked on
        configure. Length is implicitly bounded since the ceiling is <= 99."""
        if input_str == "":
            return True
        if not input_str.isdigit() or int(input_str) > round_ceiling():
            return self._reject_input()
        return True

    def validate_round_ceiling(self, input_str):
        """Settings field for the round ceiling: digits only, 0..99 while
        typing (>=1 enforced on save)."""
        if input_str == "":
            return True
        if not (input_str.isdigit() and int(input_str) <= ROUND_CEILING_HARD_MAX):
            return self._reject_input()
        return True

    def validate_participants_count(self, input_str):
        """Max-participants-per-round typing: digits only, never above the
        app-wide participants ceiling (Settings)."""
        if input_str == "":
            return True
        if not input_str.isdigit() or int(input_str) > participants_ceiling():
            return self._reject_input()
        return True

    def validate_participants_ceiling(self, input_str):
        """Settings field for the participants ceiling: digits only, 0..999."""
        if input_str == "":
            return True
        if not (input_str.isdigit() and int(input_str) <= PARTICIPANTS_CEILING_HARD_MAX):
            return self._reject_input()
        return True

    def validate_length(self, input_str):
        """Validate input length for club and remark (max 64 chars)."""
        if len(input_str) > 64:
            return self._reject_input()
        return True

    def check_event_details(self):
        if not self.event_name.get().strip() or not self.location.get().strip():
            messagebox.showerror("Error", LANGUAGES[self.lang]["event_error"])
            return False
        return True

    def _read_config_fields(self):
        """Validate and return the event config from the entry widgets.

        Returns a dict {num_rounds, max_per_round, xproc} or None if a field
        is invalid (an error is shown). When fields are locked/absent, falls
        back to the stored config.
        """
        L = LANGUAGES[self.lang]
        stored = self.data.get("config", {"num_rounds": 3, "max_per_round": 30, "xproc": 10})

        def read(widget, key, label, minimum, maximum=None):
            if widget is None:
                return stored.get(key)
            raw = widget.get().strip()
            try:
                val = int(raw)
                if val < minimum or (maximum is not None and val > maximum):
                    raise ValueError
                # Normalize the display: "0004" -> "4".
                if str(val) != raw:
                    try:
                        widget.delete(0, tk.END)
                        widget.insert(0, str(val))
                    except tk.TclError:
                        pass
                return val
            except ValueError:
                hint = label if maximum is None else f"{label} (1-{maximum})"
                messagebox.showerror("Error", L["cfg_invalid_int"].format(field=hint, min=minimum))
                return None

        num_rounds = read(getattr(self, "cfg_num_rounds", None), "num_rounds", L["cfg_num_rounds"], 1, round_ceiling())
        if num_rounds is None:
            return None
        max_per_round = read(getattr(self, "cfg_max_per_round", None), "max_per_round", L["cfg_max_per_round"], 1, participants_ceiling())
        if max_per_round is None:
            return None
        xproc = read(getattr(self, "cfg_xproc", None), "xproc", L["cfg_xproc"], 1)
        if xproc is None:
            return None
        return {"num_rounds": num_rounds, "max_per_round": max_per_round, "xproc": xproc}

    def _rebuild_sessions_for_config(self):
        """Reshape self.data['sessions'] to the current SESSION_KEYS, preserving
        any existing per-round data and dropping rounds beyond the new count
        (only safe while the event has no catches yet, i.e. at configure time)."""
        old = self.data.get("sessions", {})
        new = {}
        for k in SESSION_KEYS:
            sess = old.get(k, {"participants": [], "catches": {}})
            sess.setdefault("participants", [])
            sess.setdefault("catches", {})
            new[k] = sess
        self.data["sessions"] = new
        if self.current_manche not in SESSION_KEYS:
            self.current_manche = "manche1"

    def build_main_ui(self):
        """Build the paged main screen: a header (logo), a page container whose
        pages are switched by the fixed bottom nav bar, and a footer."""
        L = LANGUAGES[self.lang]
        for widget in self.main_frame.winfo_children():
            if widget != self.logo_label:
                widget.destroy()

        self.main_frame.columnconfigure(0, weight=0)   # logo
        self.main_frame.columnconfigure(1, weight=1)   # header context (app/event/page)
        self.main_frame.columnconfigure(2, weight=0)   # help/close cluster
        self.main_frame.rowconfigure(0, weight=0)   # header
        self.main_frame.rowconfigure(1, weight=1)   # page container
        self.main_frame.rowconfigure(2, weight=0)   # footer
        self.logo_label.grid(row=0, column=0, pady=5, padx=5, sticky="nw")

        # Persistent context strip next to the logo: app name, the active
        # competition (name · place · date), and the current page so you always
        # know where you are in the bottom-nav.
        header_center = ttk.Frame(self.main_frame)
        header_center.grid(row=0, column=1, sticky="w", padx=10, pady=6)
        ttk.Label(header_center, text=L["title"], style="HeaderTitle.TLabel").pack(anchor="w")
        ev_row = ttk.Frame(header_center)
        ev_row.pack(anchor="w", fill="x")
        self.header_event_label = ttk.Label(ev_row, text=self._event_subtitle(),
                                            style="HeaderSub.TLabel", cursor="hand2")
        self.header_event_label.pack(side="left")
        self.header_manage_hint = ttk.Label(ev_row, text="  \u270e " + L["header_manage_event"],
                                            style="HeaderLink.TLabel", cursor="hand2")
        self.header_manage_hint.pack(side="left")
        for _w in (self.header_event_label, self.header_manage_hint):
            _w.bind("<Button-1>", lambda e: self.open_event_manager())
        self.header_page_label = ttk.Label(header_center, text="", style="PageName.TLabel")
        self.header_page_label.pack(anchor="w", pady=(2, 0))

        # Persistent top-right controls (same place on every page).
        header_right = ttk.Frame(self.main_frame)
        header_right.grid(row=0, column=2, sticky="ne", padx=6, pady=6)
        self.help_btn = ttk.Button(header_right, text=L["help"], command=self.show_help, width=8)
        self.help_btn.pack(side=tk.LEFT, padx=3)
        self.close_btn = ttk.Button(header_right, text=L["close"], command=self.on_closing, width=8)
        self.close_btn.pack(side=tk.LEFT, padx=3)

        # -- page container: all pages share one cell; nav raises one --------
        self.page_container = ttk.Frame(self.main_frame)
        self.page_container.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=3, pady=3)
        self.page_container.rowconfigure(0, weight=1)
        self.page_container.columnconfigure(0, weight=1)
        self.pages = {}
        for name in ("event", "catch", "participants", "rankings", "settings"):
            f = ttk.Frame(self.page_container)
            f.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = f

        # Round selectors on multiple pages stay in lockstep via this registry;
        # the participants-page refresh hook is set when that workspace builds.
        self._round_selectors = []
        self._participants_refresh = None

        self._build_page_event(self.pages["event"])
        self._build_page_catch(self.pages["catch"])
        self._build_page_participants(self.pages["participants"])
        self._build_page_rankings(self.pages["rankings"])
        self._build_page_settings(self.pages["settings"])

        # -- footer: version bottom-left, copyright centred ------------------
        footer_frame = ttk.Frame(self.main_frame)
        footer_frame.grid(row=2, column=0, columnspan=3, pady=5, sticky="ew")
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

        # -- bottom navigation + initial page -------------------------------
        self._build_nav_bar()

        # -- Tooltips --
        self.create_tooltip(self.manage_btn, L["tooltip_manage"])
        self.create_tooltip(self.log_btn, L["tooltip_log"])
        self.create_tooltip(self.edit_catches_btn, L["tooltip_edit_catches"])
        self.create_tooltip(self.report_btn, L["tooltip_report"])
        self.create_tooltip(self.reset_btn, L["tooltip_reset"])
        self.create_tooltip(self.manage_events_btn, L["tooltip_manage_events"])
        self.create_tooltip(self.invoices_btn, L["tooltip_invoices"])
        self.create_tooltip(self.settings_btn, L["tooltip_settings"])
        self.create_tooltip(self.help_btn, L["tooltip_help"])

        self.show_page(self.current_page if self.current_page in self.pages else "event")

    # ---- bottom navigation -------------------------------------------------
    def _build_nav_bar(self):
        for w in self.nav_bar.winfo_children():
            w.destroy()
        L = LANGUAGES[self.lang]
        items = [("event", L["nav_event"]), ("participants", L["nav_participants"]),
                 ("catch", L["nav_catch"]), ("rankings", L["nav_rankings"]),
                 ("settings", L["nav_settings"])]
        self.nav_buttons = {}
        t = self.theme
        for i, (name, label) in enumerate(items):
            self.nav_bar.columnconfigure(i, weight=1)
            b = tk.Button(self.nav_bar, text=label, font=("Arial", self.font_size, "bold"),
                          relief="flat", bd=0, padx=8, pady=15,
                          bg=t["nav_bg"], fg=t["nav_fg"],
                          activebackground=t["nav_active_bg"], activeforeground=t["nav_active_fg"],
                          highlightthickness=0, cursor="hand2",
                          command=lambda n=name: self.show_page(n))
            b.grid(row=0, column=i, sticky="ew", padx=2)
            self.nav_buttons[name] = b

    def show_page(self, name):
        """Raise the named page and reflect the active tab in the nav bar."""
        if name not in self.pages:
            name = "event"
        self.current_page = name
        self.pages[name].tkraise()
        if getattr(self, "header_page_label", None) is not None:
            try:
                self.header_page_label.config(text=self._page_display_name(name))
            except tk.TclError:
                pass
        t = self.theme
        for n, b in self.nav_buttons.items():
            try:
                if n == name:
                    b.config(bg=t["nav_active_bg"], fg=t["nav_active_fg"],
                             font=("Arial", self.font_size, "bold"))
                else:
                    b.config(bg=t["nav_bg"], fg=t["nav_fg"],
                             font=("Arial", self.font_size))
            except tk.TclError:
                pass
        try:
            self.canvas.yview_moveto(0)
        except Exception:
            pass

    # ---- page: Event -------------------------------------------------------
    def _build_page_event(self, page):
        # Thin wrapper: the Event tab hosts the same workspace that the
        # tappable-header Event Manager dialog reuses (prototype). Keeping it a
        # single builder means both entry points stay perfectly in sync.
        self._build_event_workspace(page)

    def _build_event_workspace(self, page):
        L = LANGUAGES[self.lang]
        page.rowconfigure(1, weight=1)
        page.columnconfigure(0, weight=1)

        top = ttk.Frame(page)
        top.grid(row=0, column=0, sticky="ew")

        event_frame = ttk.LabelFrame(top, text=L["event_details"], padding=5)
        event_frame.pack(fill="x", padx=4, pady=4)
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

        cfg = self.data.get("config", {})
        vrounds = (self.root.register(self.validate_round_count), "%P")
        vparts = (self.root.register(self.validate_participants_count), "%P")
        vint = (self.root.register(self.validate_catches), "%P")  # digits only
        ttk.Label(event_frame, text=L["cfg_num_rounds"], font=("Arial", self.font_size)).grid(row=3, column=0, pady=3, sticky="w")
        nr_frame = ttk.Frame(event_frame)
        nr_frame.grid(row=3, column=1, pady=3, sticky="w")
        self.cfg_num_rounds = ttk.Entry(nr_frame, font=("Arial", self.font_size), width=6,
                                        validate="key", validatecommand=vrounds)
        self.cfg_num_rounds.pack(side="left")
        self.cfg_rounds_remark = ttk.Label(nr_frame, text=L["cfg_max_remark"].format(n=round_ceiling()),
                                           font=("Arial", max(8, self.font_size - 2)), foreground="#666")
        self.cfg_rounds_remark.pack(side="left", padx=(6, 0))
        self.cfg_num_rounds.insert(0, str(cfg.get("num_rounds", 3)))
        ttk.Label(event_frame, text=L["cfg_max_per_round"], font=("Arial", self.font_size)).grid(row=4, column=0, pady=3, sticky="w")
        mp_frame = ttk.Frame(event_frame)
        mp_frame.grid(row=4, column=1, pady=3, sticky="w")
        self.cfg_max_per_round = ttk.Entry(mp_frame, font=("Arial", self.font_size), width=6,
                                           validate="key", validatecommand=vparts)
        self.cfg_max_per_round.pack(side="left")
        self.cfg_parts_remark = ttk.Label(mp_frame, text=L["cfg_max_remark"].format(n=participants_ceiling()),
                                          font=("Arial", max(8, self.font_size - 2)), foreground="#666")
        self.cfg_parts_remark.pack(side="left", padx=(6, 0))
        self.cfg_max_per_round.insert(0, str(cfg.get("max_per_round", 30)))
        ttk.Label(event_frame, text=L["cfg_xproc"], font=("Arial", self.font_size)).grid(row=5, column=0, pady=3, sticky="w")
        self.cfg_xproc = ttk.Entry(event_frame, font=("Arial", self.font_size), width=6,
                                   validate="key", validatecommand=vint)
        self.cfg_xproc.grid(row=5, column=1, pady=3, sticky="w")
        self.cfg_xproc.insert(0, str(cfg.get("xproc", 10)))
        if self.data.get("config_locked", False):
            self.cfg_num_rounds.config(state="disabled")

        self.track_details_var = tk.BooleanVar(value=self.data.get("track_details", False))
        self.track_chk = ttk.Checkbutton(
            event_frame, text=L["enable_details"], variable=self.track_details_var,
            command=self.on_track_details_toggled)
        self.track_chk.grid(row=6, column=0, columnspan=2, pady=(4, 2), sticky="w")

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
            self.track_chk.config(state="disabled")
            self.cfg_max_per_round.config(state="disabled")
            self.cfg_xproc.config(state="disabled")

        # Event-level actions (the events list lives below, so no "Events" button).
        actions = ttk.LabelFrame(top, text=L["nav_event"], padding=5)
        actions.pack(fill="x", padx=4, pady=4)
        self.reset_btn = ttk.Button(actions, text=L["reset_event"], command=self.reset_event)
        self.reset_btn.pack(side=tk.LEFT, padx=3, pady=2)
        self.export_btn = ttk.Button(actions, text=L["export_event"], command=self.export_event)
        self.export_btn.pack(side=tk.LEFT, padx=3, pady=2)

        # -- bottom: existing events to open / import (in-page, scrollable) --
        ev_lf = ttk.LabelFrame(page, text=L["manage_events_title"], padding=6)
        ev_lf.grid(row=1, column=0, sticky="nsew", padx=4, pady=(2, 4))
        ev_btns = ttk.Frame(ev_lf)
        ev_btns.pack(side="bottom", fill="x", pady=(6, 0))
        list_holder = ttk.Frame(ev_lf)
        list_holder.pack(side="top", fill="both", expand=True)
        ecols = ("date", "title", "invoices", "size")
        ev_tv = ttk.Treeview(list_holder, columns=ecols, show="headings", height=8)
        ev_tv.heading("date", text=L["events_col_date"])
        ev_tv.heading("title", text=L["events_col_title"])
        ev_tv.heading("invoices", text=L["events_col_invoices"])
        ev_tv.heading("size", text=L["events_col_size"])
        ev_tv.column("date", width=90, anchor="center", stretch=False)
        ev_tv.column("title", width=360, anchor="w")
        ev_tv.column("invoices", width=80, anchor="center", stretch=False)
        ev_tv.column("size", width=90, anchor="e", stretch=False)
        ev_update = self._attach_treeview_scroll(ev_tv, list_holder, horizontal=True)
        ev_state = {"events": []}

        def reload_list():
            # Flush the current event to its folder first so it appears in the
            # list (quiet; only when it has the mandatory fields).
            try:
                ev = self.data.get("event", {})
                if ev.get("name") and ev.get("location"):
                    folder = get_event_folder(ev)
                    os.makedirs(folder, exist_ok=True)
                    with open(os.path.join(folder, f"{folder}.json"), "w", encoding="utf-8") as fh:
                        json.dump(self.data, fh, indent=4, ensure_ascii=False)
            except Exception as e:
                logging.error(f"flush current event before list failed: {e}")
            ev_state["events"] = self._scan_local_events()
            ev_tv.delete(*ev_tv.get_children())
            if ev_state["events"]:
                for idx, ev in enumerate(ev_state["events"]):
                    ev_tv.insert("", "end", iid=str(idx),
                                 values=(ev["date"], ev["name"], ev["invoices"],
                                         self._human_size(ev["bytes"])))
            else:
                ev_tv.insert("", "end", values=("", L["events_no_events"], "", ""))
            ev_update()

        def ev_selected():
            sel = ev_tv.selection()
            if not sel:
                messagebox.showinfo(L["manage_events_title"], L["events_select_row"])
                return None
            try:
                return ev_state["events"][int(sel[0])]
            except (ValueError, IndexError):
                return None

        def open_selected(_evt=None):
            ev = ev_selected()
            if not ev:
                return
            try:
                self._load_event_file(ev["path"])  # rebuilds the UI (and this list)
            except Exception as e:
                logging.error(f"events open failed: {e}")
                messagebox.showerror(L["error"], str(e))

        def browse():
            self._browse_import()

        def delete_selected():
            ev = ev_selected()
            if not ev:
                return
            cur = self.data.get("event", {})
            if cur.get("name"):
                if os.path.basename(ev["folder"]) == get_event_folder(cur):
                    messagebox.showwarning(L["manage_events_title"], L["events_del_current_blocked"])
                    return
            if not messagebox.askyesno("", L["events_del_confirm1"].format(
                    name=ev["name"], date=ev["date"], files=ev["files"], inv=ev["invoices"])):
                return
            if ev["invoices"] > 0:
                typed = self._prompt_text(self.root, L["events_delete"],
                                          L["events_del_confirm2_invoices"].format(inv=ev["invoices"]))
                if typed is None:
                    return
                if typed.strip() != ev["name"]:
                    messagebox.showinfo(L["events_delete"], L["events_del_name_mismatch"])
                    return
            try:
                import shutil
                shutil.rmtree(ev["folder"])
                messagebox.showinfo(L["manage_events_title"], L["events_del_done"].format(name=ev["name"]))
                reload_list()
            except Exception as e:
                logging.error(f"delete event failed: {e}")
                messagebox.showerror(L["error"], str(e))

        ev_tv.bind("<Double-1>", open_selected)
        self.manage_events_btn = ttk.Button(ev_btns, text=L["events_open"], command=open_selected)
        self.manage_events_btn.pack(side="left", padx=3)
        ttk.Button(ev_btns, text=L["events_browse"], command=browse).pack(side="left", padx=3)
        ttk.Button(ev_btns, text=L["events_delete"], command=delete_selected).pack(side="right", padx=3)
        reload_list()

    def open_event_manager(self):
        """Prototype: open the full Event workspace (details + saved-events
        list) as a dialog, reached by tapping the event line in the header.
        The Event tab still exists, so this is purely an additional shortcut.
        On close we rebuild the main UI so the shared event-detail widgets are
        re-bound to the tab and the header reflects any change."""
        if self._raise_open_panel():
            return
        L = LANGUAGES[self.lang]
        win = Toplevel(self.root)
        win.title(L["nav_event"])
        win.transient(self.root)
        win.update_idletasks()   # macOS: map before grabbing
        win.grab_set()
        self._center(win, 900, 660)
        self._register_panel(win)

        container = ttk.Frame(win, padding=8)
        container.pack(fill="both", expand=True)
        # Build the same workspace here; this rebinds self.event_name etc. to
        # these dialog widgets for as long as the dialog is open.
        self._build_event_workspace(container)

        btnbar = ttk.Frame(win, padding=(8, 0, 8, 8))
        btnbar.pack(fill="x")

        def _close():
            try:
                win.destroy()
            finally:
                # Restore the tab's widgets + header (and re-bind shared attrs).
                self.build_main_ui()
        ttk.Button(btnbar, text=L["close"], command=_close).pack(side="right")
        win.protocol("WM_DELETE_WINDOW", _close)

    # ---- page: Log Catch & Rankings (operating screen) -------------------
    def _build_page_catch(self, page):
        L = LANGUAGES[self.lang]
        cols = ttk.Frame(page)
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=0, minsize=300)   # catch entry (natural)
        cols.columnconfigure(1, weight=5)                # live board (more columns)
        cols.columnconfigure(2, weight=3)                # overall / categories
        cols.rowconfigure(0, weight=1)

        # -- left column: round selector + catch entry --
        left = ttk.Frame(cols)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        round_row = ttk.Frame(left)
        round_row.pack(fill="x", pady=(0, 4))
        ttk.Label(round_row, text=L["manche_label"], font=("Arial", self.font_size)).pack(side="left")
        self.manche_var = tk.StringVar()
        self.manche_combo = ttk.Combobox(round_row, textvariable=self.manche_var, state="readonly",
                                         values=session_display(self.lang),
                                         font=("Arial", self.font_size), width=18)
        self.manche_combo.pack(side="left", padx=6)
        self.manche_combo.set(key_to_display(self.lang, self.current_manche))
        self.manche_combo.bind("<<ComboboxSelected>>", self.on_manche_changed)
        self._round_selectors.append(self.manche_combo)

        catch_frame = ttk.LabelFrame(left, text=L["log_catch"], padding=5)
        catch_frame.pack(fill="x")
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
        self.log_btn = ttk.Button(catch_frame, text=L["log_catch"], command=self.log_catch)
        self.log_btn.grid(row=5, column=0, pady=5, sticky="w")
        self.edit_catches_btn = ttk.Button(catch_frame, text=L["edit_catches"], command=self.open_catch_editor)
        self.edit_catches_btn.grid(row=5, column=1, pady=5, sticky="e")
        self._apply_details_enabled_state()

        # -- middle column: live qualification board (aligned table) --
        live_lf = ttk.LabelFrame(cols, text=L["live_rankings"], padding=5)
        live_lf.grid(row=0, column=1, sticky="nsew", padx=4)
        self.live_legend = ttk.Frame(live_lf)
        self.live_legend.pack(side="bottom", fill="x", pady=(6, 0))
        _live_outer, self.live_table = self._scroll_area(live_lf)
        _live_outer.pack(side="top", fill="both", expand=True)

        # -- right column: overall standings / category trophies (aligned table) --
        overall_lf = ttk.LabelFrame(cols, text=L["overall_rankings"], padding=5)
        overall_lf.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        _overall_outer, self.overall_table = self._scroll_area(overall_lf)
        _overall_outer.pack(fill="both", expand=True)

        # The "in this round" list is intentionally dropped here: the live board
        # already shows who is fishing, and the space is better used.
        self.manche_pf = None
        self.manche_participants_list = None
        self.rankings = None
        self.overall_rankings = None
        self.refresh_rankings()

    # ---- page: Participants ------------------------------------------------
    def _build_page_participants(self, page):
        L = LANGUAGES[self.lang]
        self._participants_refresh = None
        # Until the configuration is locked, the roster shape isn't fixed, so
        # show the freeze gate instead of the workspace.
        if not self.data.get("config_locked", False):
            box = ttk.LabelFrame(page, text=L["nav_participants"], padding=12)
            box.pack(fill="x", padx=4, pady=4)
            ttk.Label(box, text=L["participants_locked_hint"], font=("Arial", self.font_size),
                      wraplength=620, justify="left").pack(anchor="w", pady=(0, 10))
            self.manage_btn = ttk.Button(box, text=L["lock_and_manage"],
                                         command=self._freeze_then_manage)
            self.manage_btn.pack(anchor="w")
            return
        self._build_participants_workspace(page)

    def _freeze_then_manage(self):
        """Run the config freeze gate (same as the old manager entry), then
        rebuild so the Participants page shows the workspace."""
        L = LANGUAGES[self.lang]
        if not self.check_event_details():
            return
        cfg = self._read_config_fields()
        if cfg is None:
            return
        total = cfg["num_rounds"] * cfg["xproc"]
        if total > cfg["max_per_round"]:
            if not messagebox.askyesno("", L["cfg_xproc_exceeds"].format(
                    total=total, maxp=cfg["max_per_round"])):
                return
        if not messagebox.askokcancel("", L["cfg_freeze_q"]):
            return
        self.data["config"] = cfg
        self.data["config_locked"] = True
        set_session_keys(cfg["num_rounds"])
        self._rebuild_sessions_for_config()
        self.update_event()
        self.build_main_ui()
        self.show_page("participants")

    def _build_participants_workspace(self, page):
        L = LANGUAGES[self.lang]
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)   # transfer row stretches
        page.rowconfigure(2, weight=1)   # matrix stretches

        # Round selector (synced with the operating screen).
        sel_row = ttk.Frame(page)
        sel_row.grid(row=0, column=0, sticky="w", padx=4, pady=(2, 6))
        ttk.Label(sel_row, text=L["manche_label"], font=("Arial", self.font_size)).pack(side="left")
        self.part_manche_var = tk.StringVar()
        part_combo = ttk.Combobox(sel_row, textvariable=self.part_manche_var, state="readonly",
                                  values=session_display(self.lang),
                                  font=("Arial", self.font_size), width=18)
        part_combo.set(key_to_display(self.lang, self.current_manche))
        part_combo.bind("<<ComboboxSelected>>", self.on_manche_changed)
        part_combo.pack(side="left", padx=6)
        self._round_selectors.append(part_combo)

        # Transfer area: roster | buttons | current round.
        transfer = ttk.Frame(page)
        transfer.grid(row=1, column=0, sticky="nsew", padx=4)
        transfer.columnconfigure(0, weight=1)
        transfer.columnconfigure(2, weight=1)
        transfer.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(transfer, text=L["competition_roster"], padding=6)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        roster_tv = ttk.Treeview(left, columns=("club", "cat"), show="tree headings",
                                 height=10, selectmode="extended")
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

        mid = ttk.Frame(transfer)
        mid.grid(row=0, column=1, padx=6)

        self._part_manche_lf = ttk.LabelFrame(
            transfer, text=L["in_manche"].format(manche=key_to_display(self.lang, self.current_manche)),
            padding=6)
        self._part_manche_lf.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        manche_tv = ttk.Treeview(self._part_manche_lf, columns=("club", "cat"), show="tree headings",
                                 height=10, selectmode="extended")
        manche_tv.heading("#0", text=L["name"].rstrip(":"))
        manche_tv.heading("club", text=L["table_club"])
        manche_tv.heading("cat", text=L["table_category"])
        manche_tv.column("#0", width=170, anchor="w")
        manche_tv.column("club", width=110, anchor="w")
        manche_tv.column("cat", width=100, anchor="w")
        manche_sb = ttk.Scrollbar(self._part_manche_lf, orient="vertical", command=manche_tv.yview)
        manche_tv.configure(yscrollcommand=manche_sb.set)
        manche_sb.pack(side="right", fill="y")
        manche_tv.pack(side="top", fill="both", expand=True)

        # All-rounds matrix: participant x round membership.
        matrix_lf = ttk.LabelFrame(page, text=L["allrounds_title"], padding=6)
        matrix_lf.grid(row=2, column=0, sticky="nsew", padx=4, pady=(8, 2))
        round_keys = list(SESSION_KEYS)
        matrix_cols = ("club", "cat") + tuple(round_keys)
        matrix_tv = ttk.Treeview(matrix_lf, columns=matrix_cols, show="tree headings",
                                 height=6, selectmode="none")
        matrix_tv.heading("#0", text=L["name"].rstrip(":"))
        # Fixed, readable widths (no stretch) so that with many rounds the table
        # overflows horizontally and scrolls/swipes rather than squashing columns
        # below a legible minimum.
        matrix_tv.column("#0", width=180, minwidth=130, anchor="w", stretch=False)
        matrix_tv.heading("club", text=L["table_club"])
        matrix_tv.column("club", width=120, minwidth=80, anchor="w", stretch=False)
        matrix_tv.heading("cat", text=L["table_category"])
        matrix_tv.column("cat", width=100, minwidth=70, anchor="w", stretch=False)
        for rk in round_keys:
            matrix_tv.heading(rk, text=key_to_display(self.lang, rk))
            matrix_tv.column(rk, width=84, minwidth=64, anchor="center", stretch=False)
        self._matrix_scroll_update = self._attach_treeview_scroll(matrix_tv, matrix_lf, horizontal=True)

        def need_selection(tv):
            sel = tv.selection()
            if not sel:
                messagebox.showinfo(L["manage_participants"], L["select_row"])
                return None
            return sel

        def refresh_all():
            in_round = set(self.data["sessions"][self.current_manche]["participants"])
            roster_tv.delete(*roster_tv.get_children())
            for name in sorted(self.data["participants"].keys(), key=str.lower):
                if name in in_round:
                    continue
                info = self.data["participants"][name]
                cat_disp = L["category_options"].get(info.get("category", ""), info.get("category", ""))
                roster_tv.insert("", "end", iid=name, text=name,
                                 values=(info.get("club", ""), cat_disp))
            manche_tv.delete(*manche_tv.get_children())
            for name in self.current_manche_participants():
                info = self.data["participants"].get(name, {})
                cat_disp = L["category_options"].get(info.get("category", ""), info.get("category", ""))
                manche_tv.insert("", "end", iid=name, text=name, values=(info.get("club", ""), cat_disp))
            self._part_manche_lf.config(
                text=L["in_manche"].format(manche=key_to_display(self.lang, self.current_manche)))
            matrix_tv.delete(*matrix_tv.get_children())
            membership = {rk: set(self.data["sessions"][rk]["participants"]) for rk in round_keys}
            for name in sorted(self.data["participants"].keys(), key=str.lower):
                info = self.data["participants"].get(name, {})
                cat_disp = L["category_options"].get(info.get("category", ""), info.get("category", ""))
                marks = tuple("\u2713" if name in membership[rk] else "\u2014" for rk in round_keys)
                matrix_tv.insert("", "end", iid=name, text=name,
                                 values=(info.get("club", ""), cat_disp) + marks)
            self._matrix_scroll_update()

        self._participants_refresh = refresh_all

        def add_new():
            self.participant_form(self.root, on_done=lambda: (refresh_all(), self.refresh_manche_view()))

        def edit_selected():
            sel = need_selection(roster_tv)
            if not sel:
                return
            self.participant_form(self.root, edit_name=sel[0],
                                  on_done=lambda: (refresh_all(), self.refresh_manche_view()))

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
                refresh_all()
                self.refresh_manche_view()

        def add_to_manche():
            sel = need_selection(roster_tv)
            if not sel:
                return
            sess = self.data["sessions"][self.current_manche]
            max_per = self.data.get("config", {}).get("max_per_round", 30)
            current = len(sess["participants"])
            to_add = [n for n in sel if n not in sess["participants"]]
            if current + len(to_add) > max_per:
                room = max(max_per - current, 0)
                messagebox.showwarning("", L["cfg_round_full"].format(
                    rnd=key_to_display(self.lang, self.current_manche), maxp=max_per, room=room))
                if room == 0:
                    return
                to_add = to_add[:room]
            added = False
            for name in to_add:
                sess["participants"].append(name)
                sess["catches"].setdefault(name, [])
                added = True
            if added:
                self.update_event()
                refresh_all()
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
                refresh_all()
                self.refresh_manche_view()

        def suggest_finalists():
            if self.current_manche != "final":
                messagebox.showinfo(L["manage_participants"], L["qual_only_final"])
                return

            def tie_resolver(round_key, names, slots):
                return self._ask_tie_choice(self.root, round_key, names, slots)

            result = self.compute_qualifiers(tie_resolver=tie_resolver)
            qualified = result["qualified"]
            if not qualified:
                messagebox.showinfo(L["manage_participants"], L["qual_none"])
                return
            sess = self.data["sessions"]["final"]
            added = 0
            for name in sorted(qualified, key=str.lower):
                if name not in sess["participants"]:
                    sess["participants"].append(name)
                    sess["catches"].setdefault(name, [])
                    added += 1
            self.update_event()
            refresh_all()
            self.refresh_manche_view()
            messagebox.showinfo(L["manage_participants"], L["qual_done"].format(n=added))

        self.manage_btn = ttk.Button(roster_btns, text=L["add_participant"], command=add_new)
        self.manage_btn.pack(side="left", padx=2)
        ttk.Button(roster_btns, text=L["edit"], command=edit_selected).pack(side="left", padx=2)
        ttk.Button(roster_btns, text=L["remove"], command=remove_selected).pack(side="left", padx=2)
        ttk.Button(mid, text=L["add_to_manche"], command=add_to_manche).pack(pady=10, fill="x")
        ttk.Button(mid, text=L["remove_from_manche"], command=remove_from_manche).pack(pady=10, fill="x")
        ttk.Button(mid, text=L["suggest_finalists"], command=suggest_finalists).pack(pady=(20, 4), fill="x")

        refresh_all()

    # ---- page: Rankings ----------------------------------------------------
    def _build_page_rankings(self, page):
        L = LANGUAGES[self.lang]
        page.columnconfigure(0, weight=1, uniform="ri")   # Reports panel
        page.columnconfigure(1, weight=1, uniform="ri")   # Invoices panel
        page.rowconfigure(1, weight=1)                    # the two panels stretch

        # --- report options strip (full width, above the two panels) ---
        settings_frame = ttk.LabelFrame(page, text=L["report_settings_label"], padding=5)
        settings_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=3)
        ttk.Label(settings_frame, text=f'\u2713 {L["chk_event_summary"]}',
                  font=("Arial", self.font_size - 2, "italic"), foreground="gray").pack(anchor="w", pady=2)
        ttk.Checkbutton(settings_frame, text=L["chk_individual"],
                        variable=self.include_individual_var).pack(anchor="w", pady=2)
        self.combined_chk = ttk.Checkbutton(
            settings_frame, text=L["chk_combined"], variable=self.include_combined_var)
        self.combined_chk.pack(anchor="w", pady=2)
        self._update_combined_state()
        self.highlight_var = tk.BooleanVar(value=self.data.get("report_highlight", True))
        def _on_highlight_toggle():
            self.data["report_highlight"] = self.highlight_var.get()
        self.highlight_chk = ttk.Checkbutton(settings_frame, text=L["report_highlight_label"],
                        variable=self.highlight_var, command=_on_highlight_toggle)
        self.highlight_chk.pack(anchor="w", pady=2)
        colour_row = ttk.Frame(settings_frame)
        colour_row.pack(anchor="w", pady=2, fill="x")
        ttk.Label(colour_row, text=f'{L["report_highlight_colour"]}:',
                  font=("Arial", self.font_size - 2)).pack(side="left")
        self.highlight_colour_var = tk.StringVar(value=self.data.get("report_highlight_colour", "green"))
        colour_labels = {"green": L["col_green"], "yellow": L["col_yellow"],
                         "blue": L["col_blue"], "grey": L["col_grey"], "red": L["col_red"]}
        self._highlight_colour_label_to_key = {v: k for k, v in colour_labels.items()}
        self.highlight_colour_combo = ttk.Combobox(colour_row, state="readonly", width=10,
                                    values=list(colour_labels.values()),
                                    font=("Arial", self.font_size - 2))
        self.highlight_colour_combo.set(colour_labels.get(self.highlight_colour_var.get(), L["col_green"]))
        def _on_colour_pick(_e=None):
            key = self._highlight_colour_label_to_key.get(self.highlight_colour_combo.get(), "green")
            self.data["report_highlight_colour"] = key
        self.highlight_colour_combo.bind("<<ComboboxSelected>>", _on_colour_pick)
        self.highlight_colour_combo.pack(side="left", padx=6)
        self._update_highlight_state()

        # --- Reports panel (left) ---
        rep_lf = ttk.LabelFrame(page, text=L["reports_block_title"], padding=6)
        rep_lf.grid(row=1, column=0, sticky="nsew", padx=(4, 2), pady=3)
        rep_btns = ttk.Frame(rep_lf)
        rep_btns.pack(side="bottom", fill="x", pady=(6, 0))
        rep_holder = ttk.Frame(rep_lf)
        rep_holder.pack(side="top", fill="both", expand=True)
        rep_tv = ttk.Treeview(rep_holder, columns=("round", "file"), show="headings", height=8)
        rep_tv.heading("round", text=L["reports_col_round"])
        rep_tv.heading("file", text=L["reports_col_file"])
        rep_tv.column("round", width=120, anchor="w", stretch=False)
        rep_tv.column("file", width=220, anchor="w")
        rep_update = self._attach_treeview_scroll(rep_tv, rep_holder, horizontal=True)
        rep_state = {"files": []}

        def reload_reports():
            rep_state["files"] = self._event_report_files()
            rep_tv.delete(*rep_tv.get_children())
            if rep_state["files"]:
                for idx, (label, path) in enumerate(rep_state["files"]):
                    rep_tv.insert("", "end", iid=str(idx), values=(label, os.path.basename(path)))
            else:
                rep_tv.insert("", "end", values=("", L["reports_no_files"]))
            rep_update()
        self._reports_reload = reload_reports

        def open_report(_evt=None):
            sel = rep_tv.selection()
            if not sel:
                return
            try:
                idx = int(sel[0])
            except ValueError:
                return
            self.open_file_external(rep_state["files"][idx][1])
        rep_tv.bind("<Double-1>", open_report)
        # Generate sits ahead of Open in the Reports panel.
        self.report_btn = ttk.Button(rep_btns, text=L["generate_report"], command=self.generate_report, style="Accent.TButton")
        self.report_btn.pack(side="left", padx=3)
        ttk.Button(rep_btns, text=L["reports_open"], command=open_report).pack(side="left", padx=3)

        # --- Invoices panel (right) ---
        inv_lf = ttk.LabelFrame(page, text=L["invoices_btn"], padding=6)
        inv_lf.grid(row=1, column=1, sticky="nsew", padx=(2, 4), pady=3)
        inv_btns = ttk.Frame(inv_lf)
        inv_btns.pack(side="bottom", fill="x", pady=(6, 0))
        inv_holder = ttk.Frame(inv_lf)
        inv_holder.pack(side="top", fill="both", expand=True)
        icols = ("number", "date", "client", "amount")
        inv_tv = ttk.Treeview(inv_holder, columns=icols, show="headings", height=8)
        for c, h, w in zip(icols, [L["inv_number"], L["inv_date"], L["inv_col_client"], L["inv_col_amount"]],
                           [130, 90, 200, 90]):
            inv_tv.heading(c, text=h)
            inv_tv.column(c, width=w, anchor="w" if c in ("number", "client") else "center",
                          stretch=(c == "client"))
        inv_update = self._attach_treeview_scroll(inv_tv, inv_holder, horizontal=True)

        def reload_invoices():
            inv_tv.delete(*inv_tv.get_children())
            invs = self.data.get("invoices", [])
            if invs:
                for idx, inv in enumerate(invs):
                    inv_tv.insert("", "end", iid=str(idx), values=(
                        inv.get("number", ""), inv.get("date", ""),
                        inv.get("recipient_name", ""), self.fmt_money(inv.get("amount", 0))))
            else:
                inv_tv.insert("", "end", values=("", "", L["no_invoices"], ""))
            inv_update()
        self._invoices_reload = reload_invoices

        def _inv_selected_index():
            sel = inv_tv.selection()
            if not sel:
                messagebox.showinfo(L["invoices_btn"], L["select_row"])
                return None
            try:
                return int(sel[0])
            except ValueError:
                return None   # the "no invoices" placeholder row

        def inv_new():
            if not self.check_event_details():
                return
            self.open_invoice_form(on_done=reload_invoices)

        def inv_open(_evt=None):
            sel = inv_tv.selection()
            if not sel:
                return
            try:
                inv = self.data.get("invoices", [])[int(sel[0])]
            except (ValueError, IndexError):
                return
            path = self._invoice_pdf_path(inv)
            try:
                if not os.path.exists(path):
                    self.write_invoice_pdf(inv)   # regenerate if missing (e.g. imported event)
                self.open_file_external(path)
            except Exception as e:
                logging.error(f"Open invoice failed: {e}")
                messagebox.showerror("Error", str(e))

        def inv_edit():
            idx = _inv_selected_index()
            if idx is None:
                return
            self.open_invoice_form(edit_index=idx, on_done=reload_invoices)

        def inv_delete():
            idx = _inv_selected_index()
            if idx is None:
                return
            if self.custom_dialog(L["invoices_btn"], L["confirm_delete_invoice"],
                                  [(L["yes"], True), (L["no"], False)]):
                inv = self.data["invoices"].pop(idx)
                try:
                    pdf_path = self._invoice_pdf_path(inv)
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
                except Exception as e:
                    logging.warning(f"Could not delete invoice PDF: {e}")
                self.update_event()
                reload_invoices()

        inv_tv.bind("<Double-1>", inv_open)
        # Order: New, Open, Edit, Delete
        self.invoices_btn = ttk.Button(inv_btns, text=L["new_invoice"], command=inv_new, style="Accent.TButton")
        self.invoices_btn.pack(side="left", padx=3)
        ttk.Button(inv_btns, text=L["reports_open"], command=inv_open).pack(side="left", padx=3)
        ttk.Button(inv_btns, text=L["edit"], command=inv_edit).pack(side="left", padx=3)
        ttk.Button(inv_btns, text=L["delete"], command=inv_delete).pack(side="left", padx=3)

        reload_reports()
        reload_invoices()

    # ---- page: Settings & Tools -------------------------------------------
    def _build_page_settings(self, page):
        L = LANGUAGES[self.lang]
        self._st_entries = {}
        self._st_banner_map = {}
        # Settings groups are laid out as side-by-side "islands": the small
        # groups share a 2-column grid at the top, the long Invoices group
        # spans full width below, then the Save bar.
        page.columnconfigure(0, weight=1, uniform="set")
        page.columnconfigure(1, weight=1, uniform="set")

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
            self._st_entries[key] = e

        # ---- Appearance (theme + language) ----
        g_appear = ttk.LabelFrame(page, text=L["settings_group_appearance"], padding=8)
        g_appear.grid(row=0, column=0, sticky="new", padx=4, pady=4)
        row = ttk.Frame(g_appear)
        row.pack(anchor="w", fill="x")
        ttk.Label(row, text=f'{L["settings_theme_label"]}:', font=("Arial", self.font_size)).pack(side="left", padx=(0, 10))
        self._theme_mode_var = tk.StringVar(value=CONFIG.get("theme_mode", "system"))
        for mode, key in (("system", "theme_system"), ("light", "theme_light"), ("dark", "theme_dark")):
            ttk.Radiobutton(row, text=L[key], value=mode, variable=self._theme_mode_var,
                            command=lambda m=mode: self._on_theme_change(m)).pack(side="left", padx=4)
        lang_row = ttk.Frame(g_appear)
        lang_row.pack(anchor="w", fill="x", pady=(8, 0))
        ttk.Label(lang_row, text=f'{L["settings_lang_label"]}:', font=("Arial", self.font_size)).pack(side="left", padx=(0, 10))
        self._lang_display = {"English": "English", "French": "Français",
                              "German": "Deutsch", "Luxembourgish": "Lëtzebuergesch",
                              "Portuguese": "Português"}
        self._lang_label_to_key = {v: k for k, v in self._lang_display.items()}
        self._lang_combo = ttk.Combobox(lang_row, state="readonly", width=16,
                                        values=list(self._lang_display.values()),
                                        font=("Arial", self.font_size))
        self._lang_combo.set(self._lang_display.get(self.lang, "English"))
        self._lang_combo.bind("<<ComboboxSelected>>",
                              lambda e: self.set_language(self._lang_label_to_key.get(self._lang_combo.get(), "English")))
        self._lang_combo.pack(side="left")
        ttk.Label(g_appear, text=L["settings_theme_note"],
                  font=("Arial", max(8, self.font_size - 3)), foreground=self.theme["fg_muted"],
                  wraplength=300, justify="left").pack(anchor="w", pady=(6, 0))

        # ---- Branding ----
        g_brand = ttk.LabelFrame(page, text=L["settings_group_branding"], padding=8)
        g_brand.grid(row=1, column=1, sticky="new", padx=4, pady=4)
        g_brand.columnconfigure(1, weight=1)
        ttk.Label(g_brand, text=L["asset_note"].format(max=self._human_size(self.ASSET_MAX_BYTES)),
                  font=("Arial", self.font_size - 3), foreground="#555").grid(
                      row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        status_labels = {}

        def refresh_status(which):
            present = self._asset_present(which)
            status_labels[which].config(text=L["asset_present"] if present else L["asset_absent"],
                                        foreground="#2e7d32" if present else "#999")

        def make_asset_row(r, which, label_key):
            ttk.Label(g_brand, text=L[label_key], font=("Arial", self.font_size)).grid(
                row=r, column=0, sticky="w", pady=3, padx=(0, 8))
            st = ttk.Label(g_brand, font=("Arial", self.font_size - 2))
            st.grid(row=r, column=1, sticky="w")
            status_labels[which] = st
            bf = ttk.Frame(g_brand)
            bf.grid(row=r, column=2, sticky="e")

            def upload():
                src = filedialog.askopenfilename(
                    title=L["asset_upload"],
                    filetypes=[("Images", "*.png *.jpg *.jpeg"), ("PNG", "*.png"), ("JPEG", "*.jpg *.jpeg")])
                if not src:
                    return
                if self._import_asset(which, src):
                    refresh_status(which)
                    messagebox.showinfo("", L["asset_saved"].format(which=L[label_key]))

            def remove():
                if not self._asset_present(which):
                    return
                if messagebox.askyesno("", L["asset_remove_q"].format(which=L[label_key])):
                    if self._remove_asset(which):
                        refresh_status(which)
                        messagebox.showinfo("", L["asset_removed"].format(which=L[label_key]))
            ttk.Button(bf, text=L["asset_upload"], command=upload).pack(side="left", padx=2)
            ttk.Button(bf, text=L["asset_remove"], command=remove).pack(side="left", padx=2)
            refresh_status(which)

        make_asset_row(1, "logo", "asset_logo")
        make_asset_row(2, "watermark", "asset_watermark")
        make_asset_row(3, "icon", "asset_icon")
        ttk.Label(g_brand, text=L["settings_branding_restart_note"],
                  font=("Arial", max(8, self.font_size - 3)), foreground="#888",
                  wraplength=300, justify="left").grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

        # ---- Events ----
        g_events = ttk.LabelFrame(page, text=L["settings_group_events"], padding=8)
        g_events.grid(row=0, column=1, sticky="new", padx=4, pady=4)
        g_events.columnconfigure(1, weight=1)
        ttk.Label(g_events, text=L["settings_field_max_rounds"], font=("Arial", self.font_size)).grid(
            row=0, column=0, sticky="w", pady=3, padx=(0, 8))
        self._st_max_rounds = ttk.Entry(g_events, font=("Arial", self.font_size), width=6, validate="key",
                                        validatecommand=(self.root.register(self.validate_round_ceiling), "%P"))
        self._st_max_rounds.grid(row=0, column=1, sticky="w")
        self._st_max_rounds.insert(0, str(CONFIG.get("max_round_count", DEFAULT_MAX_ROUNDS)))
        ttk.Label(g_events, text=L["settings_field_max_participants"], font=("Arial", self.font_size)).grid(
            row=1, column=0, sticky="w", pady=3, padx=(0, 8))
        self._st_max_parts = ttk.Entry(g_events, font=("Arial", self.font_size), width=6, validate="key",
                                       validatecommand=(self.root.register(self.validate_participants_ceiling), "%P"))
        self._st_max_parts.grid(row=1, column=1, sticky="w")
        self._st_max_parts.insert(0, str(CONFIG.get("max_participants_count", DEFAULT_MAX_PARTICIPANTS)))
        self._st_def_track = tk.BooleanVar(value=bool(CONFIG.get("default_track_details", False)))
        ttk.Checkbutton(g_events, text=L["settings_default_track"], variable=self._st_def_track).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 1))

        # ---- Reports ----
        g_reports = ttk.LabelFrame(page, text=L["settings_group_reports"], padding=8)
        g_reports.grid(row=1, column=0, sticky="new", padx=4, pady=4)
        self._st_def_highlight = tk.BooleanVar(value=bool(CONFIG.get("default_report_highlight", True)))
        self._st_def_individual = tk.BooleanVar(value=bool(CONFIG.get("default_individual_reports", False)))
        self._st_def_combined = tk.BooleanVar(value=bool(CONFIG.get("default_combined_ranking", False)))
        _restart = f'  ({L["settings_restart_note"]})'
        ttk.Checkbutton(g_reports, text=L["settings_default_highlight"], variable=self._st_def_highlight).grid(
            row=0, column=0, sticky="w", pady=1)
        indiv_row = ttk.Frame(g_reports)
        indiv_row.grid(row=1, column=0, sticky="w", pady=1)
        ttk.Checkbutton(indiv_row, text=L["settings_default_individual"], variable=self._st_def_individual).pack(side="left")
        ttk.Label(indiv_row, text=_restart, font=("Arial", max(8, self.font_size - 2)), foreground="#888").pack(side="left")
        comb_row = ttk.Frame(g_reports)
        comb_row.grid(row=2, column=0, sticky="w", pady=1)
        self._st_combined_chk = ttk.Checkbutton(comb_row, text=L["settings_default_combined"], variable=self._st_def_combined)
        self._st_combined_chk.pack(side="left")
        ttk.Label(comb_row, text=_restart, font=("Arial", max(8, self.font_size - 2)), foreground="#888").pack(side="left")

        def _sync_combined(*_a):
            if self._st_def_individual.get():
                self._st_combined_chk.state(["!disabled"])
            else:
                self._st_def_combined.set(False)
                self._st_combined_chk.state(["disabled"])
        self._st_def_individual.trace_add("write", _sync_combined)
        _sync_combined()

        # ---- Invoices ----
        g_inv = ttk.LabelFrame(page, text=L["settings_group_invoices"], padding=8)
        g_inv.grid(row=2, column=0, columnspan=2, sticky="new", padx=4, pady=4)
        g_inv.columnconfigure(1, weight=1)
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
            add_row(g_inv, k, L[lk])
        _bc_row = g_inv.grid_size()[1]
        ttk.Label(g_inv, text=L["settings_field_banner_colour"], font=("Arial", self.font_size)).grid(
            row=_bc_row, column=0, sticky="w", pady=3, padx=(0, 8))
        banner_labels = [(L["colour_none"], "none"), (L["col_green"], "green"),
                         (L["col_yellow"], "yellow"), (L["col_blue"], "blue"),
                         (L["col_grey"], "grey"), (L["col_red"], "red")]
        self._st_banner_map = {lbl: key for lbl, key in banner_labels}
        _banner_key_to_label = {key: lbl for lbl, key in banner_labels}
        self._st_banner_combo = ttk.Combobox(g_inv, state="readonly", width=12,
                                             values=[lbl for lbl, _ in banner_labels],
                                             font=("Arial", self.font_size))
        self._st_banner_combo.grid(row=_bc_row, column=1, sticky="w", pady=3)
        self._st_banner_combo.set(_banner_key_to_label.get(CONFIG.get("invoice_banner_colour", "blue"),
                                                          _banner_key_to_label["blue"]))
        _bk_row = g_inv.grid_size()[1]
        ttk.Label(g_inv, text=L["settings_bank_section"], font=("Arial", self.font_size, "bold")).grid(
            row=_bk_row, column=0, columnspan=2, sticky="w", pady=(12, 2))
        for k, lk in [
            ("bank_account_holder", "settings_field_bank_account_holder"),
            ("bank_name", "settings_field_bank_name"),
            ("iban_groups", "settings_field_iban"),
            ("payment_terms_days", "settings_field_payment_terms"),
        ]:
            add_row(g_inv, k, L[lk])

        save_bar = ttk.Frame(page)
        save_bar.grid(row=3, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 8))
        self.settings_btn = ttk.Button(save_bar, text=L["settings_save"], command=self._settings_do_save, style="Accent.TButton")
        self.settings_btn.pack(side="left")

    def _settings_do_save(self):
        L = LANGUAGES[self.lang]
        new_cfg = dict(CONFIG)
        for k, e in self._st_entries.items():
            new_cfg[k] = e.get().strip()
        raw_norm = "".join(new_cfg.get("iban_groups", "").split()).upper()
        groups = [raw_norm[i:i + 4] for i in range(0, len(raw_norm), 4)]
        if not self._validate_iban_groups(groups):
            messagebox.showerror("Error", L["settings_invalid_iban"])
            return
        new_cfg["iban_groups"] = groups
        pc_country = new_cfg.get("issuer_postcode_country", "").upper()
        pc_digits = new_cfg.get("issuer_postcode_digits", "")
        if not (1 <= len(pc_country) <= 2 and pc_country.isalpha() and pc_digits.isdigit() and len(pc_digits) == 4):
            messagebox.showerror("Error", L["settings_invalid_postcode"])
            return
        new_cfg["issuer_postcode_country"] = pc_country
        phone = new_cfg.get("issuer_phone", "")
        if phone and not all(ch.isdigit() or ch in "+ " for ch in phone):
            messagebox.showerror("Error", L["settings_invalid_phone"])
            return
        import re as _re
        if not _re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", new_cfg.get("issuer_email", "")):
            messagebox.showerror("Error", L["settings_invalid_email"])
            return
        try:
            new_cfg["payment_terms_days"] = int(new_cfg.get("payment_terms_days", 30))
        except ValueError:
            new_cfg["payment_terms_days"] = 30
        try:
            mrc = int(self._st_max_rounds.get().strip())
        except ValueError:
            mrc = DEFAULT_MAX_ROUNDS
        new_cfg["max_round_count"] = max(1, min(mrc, ROUND_CEILING_HARD_MAX))
        try:
            mpc = int(self._st_max_parts.get().strip())
        except ValueError:
            mpc = DEFAULT_MAX_PARTICIPANTS
        new_cfg["max_participants_count"] = max(1, min(mpc, PARTICIPANTS_CEILING_HARD_MAX))
        new_cfg["invoice_banner_colour"] = self._st_banner_map.get(self._st_banner_combo.get(), "blue")
        new_cfg["default_track_details"] = bool(self._st_def_track.get())
        new_cfg["default_report_highlight"] = bool(self._st_def_highlight.get())
        new_cfg["default_individual_reports"] = bool(self._st_def_individual.get())
        new_cfg["default_combined_ranking"] = bool(self._st_def_combined.get() and self._st_def_individual.get())
        if save_config(new_cfg):
            CONFIG.clear()
            CONFIG.update(new_cfg)   # reflect saved values in memory for this session
            messagebox.showinfo("", L["settings_saved"])

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
        self._center(win, 900, 560)
        self._register_panel(win)

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
                messagebox.showerror("Error", L["catch_unknown_participant"])
                return
            if name not in self.data["sessions"][self.current_manche]["participants"]:
                messagebox.showerror("Error", L["catch_not_in_round"].format(
                    rnd=key_to_display(self.lang, self.current_manche)))
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
            for w in (getattr(self, "cfg_num_rounds", None),
                      getattr(self, "cfg_max_per_round", None),
                      getattr(self, "cfg_xproc", None),
                      getattr(self, "track_chk", None)):
                if w is not None:
                    try:
                        w.config(state="disabled")
                    except tk.TclError:
                        pass
        try:
            save_data(self.data, self.data["event"])
        except Exception as e:
            logging.error(f"update_event failed: {str(e)}")
            messagebox.showerror("Error", LANGUAGES[self.lang]["error"])

    def fmt_weight(self, value):
        """Format a weight (in grams) as a whole number, localised for the UI language."""
        s = f"{value:,.0f}"
        if self.lang in ["French", "German", "Luxembourgish", "Portuguese"]:
            s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return s

    def copyright_text(self):
        """Copyright line with the runtime-computed year span substituted in."""
        L = LANGUAGES[self.lang]
        yr = datetime.now().year
        span = "2025" if yr <= 2025 else f"2025 - {yr}"
        return L["copyright"].replace("{year_span}", span)

    @staticmethod
    def _competition_places(ranked):
        """1224-style ranking. ``ranked`` is [(name, value), ...] sorted by
        value descending. Returns [(name, value, place), ...] where equal
        values share a place and the next place jumps by the group size
        (three tied at 5th -> next is 8th)."""
        out = []
        for i, (name, value) in enumerate(ranked):
            if i == 0 or value != ranked[i - 1][1]:
                place = i + 1
            out.append((name, value, place))
        return out

    def round_weight_ranking(self, round_key):
        """(name, total_weight, place) for participants in a round who caught
        at least one fish, ranked by total weight (tie ranking applied).

        Weight totals are rounded before comparison so that anglers meant to
        be tied are detected as tied: summing decimal weights can otherwise
        leave floating-point noise (e.g. 333.33 + 666.67 -> 1000.0000000001),
        which would split a real tie and skip the tie prompt at the boundary.
        """
        sess = self.data["sessions"][round_key]
        weights = {}
        for n in sess["participants"]:
            cs = sess["catches"].get(n, [])
            if sum(c.get("num_catches", 1) for c in cs) >= 1:  # >= 1 fish
                weights[n] = round(sum(c["weight"] for c in cs), 3)
        ranked = sorted(weights.items(), key=lambda x: (-x[1], x[0]))
        return self._competition_places(ranked)

    def _qualifiers_for_round(self, round_key, already, xproc, tie_resolver=None):
        """Qualifiers for one round. Eligible = caught >=1 fish and not already
        qualified in an earlier round. Fill up to ``xproc`` slots best-first.
        A tie group larger than the remaining slots is resolved by
        ``tie_resolver(round_key, names, slots)`` (returns the chosen names);
        if no resolver is given, those slots are left unfilled and the tie is
        reported in ``pending_tie``.
        """
        placed = [(n, w, p) for (n, w, p) in self.round_weight_ranking(round_key)
                  if n not in already]
        qualified, pending_tie = [], []
        slots = xproc
        i = 0
        while i < len(placed) and slots > 0:
            place = placed[i][2]
            group = [n for (n, w, p) in placed if p == place]
            if len(group) <= slots:
                qualified.extend(group)
                slots -= len(group)
                i += len(group)
            else:
                if tie_resolver is not None:
                    chosen = (tie_resolver(round_key, group, slots) or [])[:slots]
                    qualified.extend(chosen)
                    slots -= len(chosen)
                else:
                    pending_tie = group
                break
        return {"qualified": qualified, "pending_tie": pending_tie, "slots_left": slots}

    def compute_qualifiers(self, tie_resolver=None):
        """Walk the rounds (all SESSION_KEYS except 'final') in order, carrying
        a running already-qualified set. Returns
        {'qualified': set, 'per_round': {round_key: result}}.

        Key rule: a slot is only ever filled by someone who caught >=1 fish, so
        a round may contribute fewer than xproc qualifiers (the rest stay open).
        """
        cfg = self.data.get("config", {})
        xproc = cfg.get("xproc", 10)
        rounds = [k for k in SESSION_KEYS if k != "final"]
        already, per_round = set(), {}
        for rk in rounds:
            res = self._qualifiers_for_round(rk, already, xproc, tie_resolver)
            per_round[rk] = res
            already.update(res["qualified"])
        return {"qualified": already, "per_round": per_round}

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
        bf = ("Arial", max(8, self.font_size - 3), "bold")
        widget.tag_configure("q_badge", background="#bfe0a0", foreground="#173404", font=bf)
        widget.tag_configure("a_badge", background="#aecdf2", foreground="#0C447C", font=bf)
        widget.tag_configure("tie_badge", background="#f3cd86", foreground="#854F0B", font=bf)
        widget.tag_configure("d_badge", background="#eda9a9", foreground="#791F1F", font=bf)

    def render_rankings(self, widget, segments):
        if widget is None:
            return
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        for txt, tag in segments:
            widget.insert(tk.END, txt, tag)
        widget.config(state="disabled")

    def _round_badges(self, round_key):
        """Map participant -> qualification badge for the live board of a round:
        'A' already qualified in an earlier round, 'Q' qualifies on this round,
        '?' tied for the last slot (undecided), 'D' not qualified. Empty in the
        final (no qualification there)."""
        rounds = [k for k in SESSION_KEYS if k != "final"]
        if round_key not in rounds:
            return {}
        res = self.compute_qualifiers()  # no resolver -> ties surface as pending
        per = res["per_round"]
        idx = rounds.index(round_key)
        already_before = set()
        for r in rounds[:idx]:
            already_before |= set(per.get(r, {}).get("qualified", []))
        this = per.get(round_key, {"qualified": [], "pending_tie": []})
        qset, tset = set(this["qualified"]), set(this["pending_tie"])
        badges = {}
        for (name, w, place) in self.round_weight_ranking(round_key):
            if name in already_before:
                badges[name] = "A"
            elif name in qset:
                badges[name] = "Q"
            elif name in tset:
                badges[name] = "?"
            else:
                badges[name] = "D"
        return badges

    # Single muted colour for weight values, used in BOTH panels so they match.
    WEIGHT_FG = "#9aa0a6"
    def live_board_data(self):
        """Structured rows for the live board:
        (badge|None, place, name, club, category_display, weight_str), is_final.
        Full field (the panel scrolls when it overflows)."""
        L = LANGUAGES[self.lang]
        mk = self.current_manche
        ranked = self.round_weight_ranking(mk)
        is_final = (mk == "final")
        badges = {} if is_final else self._round_badges(mk)
        rows = []
        for (name, w, place) in ranked:
            b = None if is_final else badges.get(name, "D")
            info = self.data["participants"].get(name, {})
            cat = L["category_options"].get(info.get("category", ""), info.get("category", ""))
            rows.append((b, place, name, info.get("club", ""), cat, f"{self.fmt_weight(w)} g"))
        return rows, is_final

    def overall_podium_data(self):
        """Structured items for the overall panel: ('section', title),
        ('row', place_or_'', name, weight_str) or ('empty', text). Overall top 3
        (all participants, pooled weight) then Ladies/U20/U15/U10 best one each;
        empty categories omitted. Awards only; no effect on the final."""
        L = LANGUAGES[self.lang]
        parts = self.data.get("participants", {})

        def _club(n):
            return parts.get(n, {}).get("club", "")
        pooled, fish = {}, {}
        for sk in SESSION_KEYS:
            for n, cs in self.data["sessions"][sk]["catches"].items():
                if not cs:
                    continue
                pooled[n] = pooled.get(n, 0) + sum(c["weight"] for c in cs)
                fish[n] = fish.get(n, 0) + sum(c.get("num_catches", 1) for c in cs)
        eligible = {n: round(pooled[n], 3) for n in pooled if fish.get(n, 0) >= 1}
        items = [("section", L["overall_top3"])]
        ranked = self._competition_places(sorted(eligible.items(), key=lambda x: (-x[1], x[0])))
        if not ranked:
            items.append(("empty", L["no_results"]))
            return items
        for (n, w, p) in [r for r in ranked if r[2] <= 3]:
            items.append(("row", f"{p}.", n, _club(n), f"{self.fmt_weight(w)} g"))
        for catkey in ["Lady", "U20", "U15", "U10"]:
            in_cat = {n: w for n, w in eligible.items()
                      if parts.get(n, {}).get("category") == catkey}
            if not in_cat:
                continue
            cranked = self._competition_places(sorted(in_cat.items(), key=lambda x: (-x[1], x[0])))
            items.append(("section", L["category_options"].get(catkey, catkey)))
            for (n, w, p) in [r for r in cranked if r[2] == 1]:
                items.append(("row", "", n, _club(n), f"{self.fmt_weight(w)} g"))
        return items

    def _clear_frame(self, frame):
        for w in frame.winfo_children():
            w.destroy()

    def _scroll_area(self, parent):
        """A vertically scrollable region. Returns (outer, inner): build content
        into `inner`. The scrollbar appears only when content overflows; the
        mouse wheel scrolls when hovering (finger-swipe maps to the same wheel
        events on touch builds later)."""
        outer = ttk.Frame(parent)
        canvas = tk.Canvas(outer, highlightthickness=0, bd=0,
                           background=self.root.cget("background"))
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=vbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        def _update(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(win, width=canvas.winfo_width())
            if inner.winfo_reqheight() > canvas.winfo_height():
                vbar.grid(row=0, column=1, sticky="ns")
            else:
                vbar.grid_remove()
                canvas.yview_moveto(0)
        inner.bind("<Configure>", _update)
        canvas.bind("<Configure>", _update)

        def _wheel(e):
            if inner.winfo_reqheight() <= canvas.winfo_height():
                return
            step = int(-e.delta / 120) if abs(e.delta) >= 120 else (-1 if e.delta > 0 else 1)
            canvas.yview_scroll(step, "units")

        def _wheel_x11(e):
            if inner.winfo_reqheight() <= canvas.winfo_height():
                return
            canvas.yview_scroll(-1 if e.num == 4 else 1, "units")

        def _enter(_):
            canvas.bind_all("<MouseWheel>", _wheel)
            canvas.bind_all("<Button-4>", _wheel_x11)
            canvas.bind_all("<Button-5>", _wheel_x11)

        def _leave(_):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")
        outer.bind("<Enter>", _enter)
        outer.bind("<Leave>", _leave)
        return outer, inner

    def _attach_treeview_scroll(self, tree, container, horizontal=False):
        """Give a Treeview scrollbars that appear only on overflow, plus wheel
        (vertical) and shift-wheel (horizontal) scrolling. Returns an updater to
        call after (re)populating so the bars show/hide correctly."""
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky="nsew")
        vbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vbar.set)
        hbar = None
        if horizontal:
            hbar = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
            tree.configure(xscrollcommand=hbar.set)

        def _update(_e=None):
            if tree.yview() != (0.0, 1.0):
                vbar.grid(row=0, column=1, sticky="ns")
            else:
                vbar.grid_remove()
            if hbar is not None:
                if tree.xview() != (0.0, 1.0):
                    hbar.grid(row=1, column=0, sticky="ew")
                else:
                    hbar.grid_remove()
        tree.bind("<Configure>", _update)

        def _wheel(e):
            step = int(-e.delta / 120) if abs(e.delta) >= 120 else (-1 if e.delta > 0 else 1)
            tree.yview_scroll(step, "units")

        def _shift_wheel(e):
            step = int(-e.delta / 120) if abs(e.delta) >= 120 else (-1 if e.delta > 0 else 1)
            tree.xview_scroll(step, "units")

        def _enter(_):
            tree.bind_all("<MouseWheel>", _wheel)
            if horizontal:
                tree.bind_all("<Shift-MouseWheel>", _shift_wheel)

        def _leave(_):
            tree.unbind_all("<MouseWheel>")
            if horizontal:
                tree.unbind_all("<Shift-MouseWheel>")
        tree.bind("<Enter>", _enter)
        tree.bind("<Leave>", _leave)
        return _update

    def _render_live_board(self, table, legend):
        """Render the live board as an aligned table with column headers, and
        the qualification legend pinned in its own bottom strip."""
        L = LANGUAGES[self.lang]
        fs = self.font_size
        self._clear_frame(table)
        self._clear_frame(legend)
        rows, is_final = self.live_board_data()
        hf = ("Arial", max(9, fs - 2), "bold")
        rf = ("Arial", max(8, fs - 2))
        df = ("Arial", max(8, fs - 3), "italic")
        table.columnconfigure(0, weight=0)   # badge
        table.columnconfigure(1, weight=0)   # place
        table.columnconfigure(2, weight=1)   # name (stretch)
        table.columnconfigure(3, weight=1)   # club
        table.columnconfigure(4, weight=0)   # category
        table.columnconfigure(5, weight=0)   # weight
        r = 0
        ttk.Label(table, text=L["col_pos"], font=hf).grid(row=r, column=1, sticky="e", padx=4, pady=(0, 3))
        ttk.Label(table, text=L["col_name"], font=hf).grid(row=r, column=2, sticky="w", padx=4, pady=(0, 3))
        ttk.Label(table, text=L["table_club"], font=hf).grid(row=r, column=3, sticky="w", padx=4, pady=(0, 3))
        ttk.Label(table, text=L["table_category"], font=hf).grid(row=r, column=4, sticky="w", padx=4, pady=(0, 3))
        ttk.Label(table, text=L["col_weight"], font=hf).grid(row=r, column=5, sticky="e", padx=4, pady=(0, 3))
        r += 1
        if not rows:
            ttk.Label(table, text=L["no_catches_round"], font=df, foreground="#999").grid(
                row=r, column=0, columnspan=6, sticky="w", padx=4, pady=4)
            return
        for (b, place, name, club, cat, wtxt) in rows:
            if not is_final and b:
                bg, fg = self._badge_colours(b)
                self._make_pill(table, b, bg, fg, max(8, fs - 3)).grid(
                    row=r, column=0, padx=(0, 5), pady=2)
            ttk.Label(table, text=f"{place}.", font=rf).grid(row=r, column=1, sticky="e", padx=4)
            ttk.Label(table, text=name, font=rf).grid(row=r, column=2, sticky="w", padx=4)
            ttk.Label(table, text=club, font=rf, foreground=self.WEIGHT_FG).grid(row=r, column=3, sticky="w", padx=4)
            ttk.Label(table, text=cat, font=rf, foreground=self.WEIGHT_FG).grid(row=r, column=4, sticky="w", padx=4)
            ttk.Label(table, text=wtxt, font=rf, foreground=self.WEIGHT_FG).grid(row=r, column=5, sticky="e", padx=4)
            r += 1
        if not is_final:
            c = 0
            for letter in ("Q", "A", "?", "D"):
                bg, fg = self._badge_colours(letter)
                txt = {"Q": L["legend_q"], "A": L["legend_a"], "?": L["legend_tie"], "D": L["legend_d"]}[letter]
                self._make_pill(legend, letter, bg, fg, max(7, fs - 4)).grid(
                    row=0, column=c, padx=(6, 2), pady=2)
                c += 1
                ttk.Label(legend, text=txt.split(" ", 1)[-1] if " " in txt else txt,
                          font=("Arial", max(7, fs - 4))).grid(row=0, column=c, padx=(0, 2))
                c += 1

    def _render_overall(self, table):
        """Render the overall panel: section headers (Overall, then categories)
        with aligned #/Name/Weight columns and the same weight colour as live."""
        L = LANGUAGES[self.lang]
        fs = self.font_size
        self._clear_frame(table)
        items = self.overall_podium_data()
        headf = ("Arial", max(9, fs - 2), "bold")
        subf = ("Arial", max(8, fs - 3), "bold")
        rf = ("Arial", max(8, fs - 2))
        table.columnconfigure(0, weight=0)   # place
        table.columnconfigure(1, weight=1)   # name (stretch)
        table.columnconfigure(2, weight=1)   # club
        table.columnconfigure(3, weight=0)   # weight
        r = 0
        header_added = False
        for it in items:
            if it[0] == "section":
                ttk.Label(table, text=it[1], font=(headf if not header_added else subf)).grid(
                    row=r, column=0, columnspan=4, sticky="w", padx=4,
                    pady=((6, 1) if header_added else (0, 1)))
                r += 1
                if not header_added:
                    ttk.Label(table, text=L["col_pos"], font=subf).grid(row=r, column=0, sticky="e", padx=4)
                    ttk.Label(table, text=L["col_name"], font=subf).grid(row=r, column=1, sticky="w", padx=4)
                    ttk.Label(table, text=L["table_club"], font=subf).grid(row=r, column=2, sticky="w", padx=4)
                    ttk.Label(table, text=L["col_weight"], font=subf).grid(row=r, column=3, sticky="e", padx=4)
                    r += 1
                    header_added = True
            elif it[0] == "empty":
                ttk.Label(table, text=it[1], font=("Arial", max(8, fs - 3), "italic"),
                          foreground="#999").grid(row=r, column=0, columnspan=4, sticky="w", padx=4, pady=4)
                r += 1
            else:
                _, place, name, club, wtxt = it
                ttk.Label(table, text=place, font=rf).grid(row=r, column=0, sticky="e", padx=4)
                ttk.Label(table, text=name, font=rf).grid(row=r, column=1, sticky="w", padx=4)
                ttk.Label(table, text=club, font=rf, foreground=self.WEIGHT_FG).grid(row=r, column=2, sticky="w", padx=4)
                ttk.Label(table, text=wtxt, font=rf, foreground=self.WEIGHT_FG).grid(row=r, column=3, sticky="e", padx=4)
                r += 1

    def refresh_rankings(self):
        if getattr(self, "live_table", None) is not None:
            self._render_live_board(self.live_table, self.live_legend)
        if getattr(self, "overall_table", None) is not None:
            self._render_overall(self.overall_table)


    # -- formatting helper for editable numbers ---------------------
    def num_to_str(self, value):
        if value is None:
            return ""
        try:
            fv = float(value)
        except (TypeError, ValueError):
            return str(value)
        s = str(int(fv)) if fv.is_integer() else repr(fv)
        if self.lang in ["French", "German", "Luxembourgish", "Portuguese"]:
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
            # Always show the header before the recorded group - even when the
            # top (not-yet-recorded) section is empty, so the operator can see
            # at a glance that everyone has already been logged.
            out.append(L["catch_recorded_group"])
            out.extend(has_catch)
        return out

    def _is_catch_separator(self, s):
        return s == LANGUAGES[self.lang]["catch_recorded_group"]

    def on_manche_changed(self, event=None):
        # Multiple pages can carry a round selector (operating screen and the
        # Participants page); read whichever fired, then sync them all.
        disp = None
        if event is not None and getattr(event, "widget", None) is not None:
            try:
                disp = event.widget.get()
            except Exception:
                disp = None
        if disp is None and self.manche_var is not None:
            disp = self.manche_var.get()
        if disp:
            self.current_manche = display_to_key(self.lang, disp)
        self._sync_round_selectors()
        self.refresh_manche_view()
        self._update_combined_state()
        self._update_highlight_state()
        if getattr(self, "_participants_refresh", None) is not None:
            self._participants_refresh()

    def _sync_round_selectors(self):
        """Point every registered round selector at the current round so the
        operating screen and Participants page never drift apart."""
        disp = key_to_display(self.lang, self.current_manche)
        for combo in getattr(self, "_round_selectors", []):
            try:
                combo.set(disp)
            except Exception:
                pass

    def _update_highlight_state(self):
        """Finalist highlighting applies to round reports only, not the final's
        own report. On the Final, the checkbox and colour picker are unchecked
        and disabled; on any round they are restored to the stored setting."""
        chk = getattr(self, "highlight_chk", None)
        combo = getattr(self, "highlight_colour_combo", None)
        if chk is None or combo is None:
            return
        if self.current_manche == "final":
            self.highlight_var.set(False)
            chk.config(state="disabled")
            combo.config(state="disabled")
        else:
            chk.config(state="normal")
            combo.config(state="readonly")
            # Restore the stored preference when leaving the final.
            self.highlight_var.set(self.data.get("report_highlight", True))

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
        if self._raise_open_panel():
            return
        L = LANGUAGES[self.lang]
        # If the event/config is not yet locked, run the freeze gate first.
        if not self.data.get("config_locked", False):
            if not self.check_event_details():
                return
            cfg = self._read_config_fields()
            if cfg is None:
                return
            total = cfg["num_rounds"] * cfg["xproc"]
            if total > cfg["max_per_round"]:
                if not messagebox.askyesno("", L["cfg_xproc_exceeds"].format(
                        total=total, maxp=cfg["max_per_round"])):
                    return
            if not messagebox.askokcancel("", L["cfg_freeze_q"]):
                return
            self.data["config"] = cfg
            self.data["config_locked"] = True
            # Apply the (possibly changed) round count: point SESSION_KEYS at
            # the new shape and rebuild the sessions dict to match. Safe here
            # because no catches exist yet - the roster is assigned afterwards.
            set_session_keys(cfg["num_rounds"])
            self._rebuild_sessions_for_config()
            # Persist the (now frozen) event + config and lock the widgets, then
            # refresh the main screen so the round dropdown reflects the count.
            self.update_event()
            self.build_main_ui()
            return self.open_participants_manager()
        if not self.check_event_details():
            return
        self.update_event()  # lock event details once we touch the roster
        L = LANGUAGES[self.lang]

        win = Toplevel(self.root)
        win.title(L["manage_participants"])
        win.transient(self.root)
        win.update_idletasks()  # macOS: ensure window is mapped before grabbing
        win.grab_set()
        self._center(win, 980, 560)
        self._register_panel(win)

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
            # Group B: enforce the configured max participants per round.
            max_per = self.data.get("config", {}).get("max_per_round", 30)
            current = len(sess["participants"])
            to_add = [n for n in sel if n not in sess["participants"]]
            if current + len(to_add) > max_per:
                room = max(max_per - current, 0)
                messagebox.showwarning("", L["cfg_round_full"].format(
                    rnd=key_to_display(self.lang, self.current_manche),
                    maxp=max_per, room=room))
                if room == 0:
                    return
                to_add = to_add[:room]
            added = False
            for name in to_add:
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

        def suggest_finalists():
            # Only meaningful when arranging the final's roster.
            if self.current_manche != "final":
                messagebox.showinfo(L["manage_participants"], L["qual_only_final"])
                return

            def tie_resolver(round_key, names, slots):
                return self._ask_tie_choice(win, round_key, names, slots)

            result = self.compute_qualifiers(tie_resolver=tie_resolver)
            qualified = result["qualified"]
            if not qualified:
                messagebox.showinfo(L["manage_participants"], L["qual_none"])
                return
            sess = self.data["sessions"]["final"]
            added = 0
            for name in sorted(qualified, key=str.lower):
                if name not in sess["participants"]:
                    sess["participants"].append(name)
                    sess["catches"].setdefault(name, [])
                    added += 1
            self.update_event()
            refresh_panes()
            self.refresh_manche_view()
            messagebox.showinfo(L["manage_participants"], L["qual_done"].format(n=added))

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
        ttk.Button(mid, text=L["suggest_finalists"], command=suggest_finalists).pack(pady=(20, 4), fill="x")
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
        self._center(dlg, 440, 320)

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
        if self._raise_open_panel():
            return
        if not self.check_event_details():
            return
        L = LANGUAGES[self.lang]
        win = Toplevel(self.root)
        win.title(f'{L["edit_catches"]} - {key_to_display(self.lang, self.current_manche)}')
        win.transient(self.root)
        win.update_idletasks()  # macOS: ensure window is mapped before grabbing
        win.grab_set()
        self._center(win, 820, 480)

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
        self._center(dlg, 420, 320)

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

    def _compute_detail_lines(self, rt, recipient, unit_price):
        """Breakdown rows for a detailed invoice, as [desc, qty, amount].

        Individual -> one row per round the participant is in (qty 1 each).
        Club       -> one row per member, qty = that member's round count.
        Either way the rows sum to the invoice's quantity x unit price.
        """
        lines = []
        if rt == "individual":
            for sk in SESSION_KEYS:
                if recipient in self.data["sessions"][sk]["participants"]:
                    lines.append([key_to_display(self.lang, sk), 1, round(unit_price, 2)])
        else:  # club
            target = (recipient or "").strip().casefold()
            counts = {}
            for sk in SESSION_KEYS:
                for n in self.data["sessions"][sk]["participants"]:
                    info = self.data["participants"].get(n, {})
                    if (info.get("club") or "").strip().casefold() == target:
                        counts[n] = counts.get(n, 0) + 1
            for n in sorted(counts, key=str.lower):
                lines.append([n, counts[n], round(counts[n] * unit_price, 2)])
        return lines

    def _invoice_detail_lines(self, invoice):
        """Rows to render on the invoice. Detailed invoices use the stored
        breakdown (so reprints are stable); otherwise a single summary row."""
        if invoice.get("detailed") and invoice.get("detail_lines"):
            return [(d, q, a) for d, q, a in invoice["detail_lines"]]
        return [(invoice.get("description", ""), invoice.get("quantity", ""),
                 invoice.get("amount", 0))]

    def _is_separator_label(self, s):
        L = LANGUAGES[self.lang]
        return s in (L["inv_individuals_group"], L["inv_others_group"],
                     L["inv_separator"], L["inv_already_invoiced_group"])

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
        if self.lang in ["French", "German", "Luxembourgish", "Portuguese"]:
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

    @staticmethod
    def open_file_external(path):
        """Open a file with the OS default application (cross-platform).

        Returns True on success, False otherwise (errors are logged, not raised:
        a viewer problem must never break the invoicing flow)."""
        try:
            path = os.path.abspath(path)
            if sys.platform.startswith("darwin"):
                subprocess.Popen(["open", path])
            elif os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", path])
            return True
        except Exception as e:
            logging.error(f"open_file_external failed for {path}: {e}")
            return False

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
        self._center(dlg, 540, 620)
        self._register_panel(dlg)
        # NOTE: no grab_set() on this form, and no Toplevel-level ButtonPress
        # bindings either. Both have been tried and both break the tkcalendar
        # popup and/or the recipient combobox popdown on macOS (a bind on a
        # Toplevel fires for clicks on EVERY child widget, so a "re-grab on
        # click" fights the popups the user is trying to open). The form is
        # transient (stays above the main window); the main window's action
        # buttons are guarded separately while any panel is open.

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

        # Date (defaults to event date, editable). Plain entry + picker dialog;
        # see open_date_picker for why no DateEntry drop-down is used here.
        ttk.Label(frame, text=L["inv_date"], font=("Arial", self.font_size)).grid(row=row, column=0, sticky="w", pady=4)
        date_row = ttk.Frame(frame)
        date_row.grid(row=row, column=1, pady=4, sticky="w")
        init_date = (existing.get("date") if editing else self.data["event"].get("date")) or ""
        try:
            datetime.strptime(init_date, "%d/%m/%Y")
        except (ValueError, TypeError):
            init_date = datetime.now().strftime("%d/%m/%Y")
        date_var = tk.StringVar(value=init_date)
        date_field = ttk.Entry(date_row, textvariable=date_var,
                               font=("Arial", self.font_size), width=12)
        date_field.pack(side="left")

        def pick_date():
            chosen = self.open_date_picker(dlg, date_var.get())
            if chosen:
                date_var.set(chosen)

        ttk.Button(date_row, text="\U0001F4C5", width=3, command=pick_date).pack(side="left", padx=(6, 0))
        row += 1

        # Recipient type radios. Frozen in Edit mode: an invoice's identity is
        # its recipient - to change who an invoice is for, delete it and issue
        # a new one (the number is not recycled, keeping the sequence honest).
        ttk.Label(frame, text=L["inv_recipient_type"], font=("Arial", self.font_size)).grid(row=row, column=0, sticky="w", pady=4)
        type_var = tk.StringVar(value=(existing.get("recipient_type", "club") if editing else "club"))
        rt_frame = ttk.Frame(frame)
        rt_frame.grid(row=row, column=1, pady=4, sticky="w")
        rb_state = "disabled" if editing else "normal"
        ttk.Radiobutton(rt_frame, text=L["inv_recipient_club"], variable=type_var, value="club",
                        state=rb_state,
                        command=lambda: rebuild_recipient()).pack(side="left", padx=(0, 14))
        ttk.Radiobutton(rt_frame, text=L["inv_recipient_individual"], variable=type_var, value="individual",
                        state=rb_state,
                        command=lambda: rebuild_recipient()).pack(side="left")
        row += 1

        # Recipient dropdown (rebuilt when type changes). Also frozen in Edit.
        rec_label = ttk.Label(frame, text=L["inv_select_club"], font=("Arial", self.font_size))
        rec_label.grid(row=row, column=0, sticky="w", pady=4)
        recipient_var = tk.StringVar(value=existing.get("recipient_name", "") if editing else "")
        recipient_combo = ttk.Combobox(frame, textvariable=recipient_var, font=("Arial", self.font_size),
                                       width=28, state=("disabled" if editing else "readonly"))
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
            desc_entry.insert(0, f"{ev_name} {ev_date}".strip())
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

        # Detailed-invoice toggle (default off): per-round lines for an
        # individual, per-member lines for a club.
        detailed_var = tk.BooleanVar(value=bool(existing.get("detailed", False)) if editing else False)
        ttk.Checkbutton(frame, text=L["inv_detailed"], variable=detailed_var).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 2))
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
            # on_recipient_picked refills the quantity with the live suggestion;
            # for an existing invoice the saved quantity is authoritative.
            qty_entry.delete(0, tk.END)
            qty_entry.insert(0, str(existing.get("quantity", 1)))

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
            if rt == "individual":
                max_sessions = self.data.get("config", {}).get("num_rounds", 3) + 1
                if qty > max_sessions:
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

            date_str = date_var.get().strip()
            try:
                date_str = datetime.strptime(date_str, "%d/%m/%Y").strftime("%d/%m/%Y")
            except ValueError:
                messagebox.showerror("Error", L["inv_invalid_date"])
                return
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
                "detailed": bool(detailed_var.get()),
            }
            # For a detailed invoice, freeze the breakdown now so reprints are
            # stable even if the event roster changes later.
            if invoice["detailed"]:
                invoice["detail_lines"] = self._compute_detail_lines(rt, recipient, price)

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
            if messagebox.askyesno("", L["inv_saved_open_q"]):
                self.open_file_external(self._invoice_pdf_path(invoice))
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

    def _invoice_banner(self):
        """(fill_rgb_or_None, text_rgb) for the invoice header/footer banner.

        Uses the same palette as the report highlight colours; "none" draws no
        banner (white) with dark text. The palette tints are light, so banner
        text is always dark for readability."""
        key = CONFIG.get("invoice_banner_colour", "blue")
        if key == "none":
            return None, self.INV_TEXT_DARK
        rgb = self.REPORT_HIGHLIGHT_COLOURS.get(key, self.REPORT_HIGHLIGHT_COLOURS["blue"])
        return rgb, self.INV_TEXT_DARK

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

        amount_total = invoice.get("amount", 0)
        amount_str = self._fmt_invoice_amount(amount_total)
        rows = self._invoice_detail_lines(invoice)

        col_desc_x = 40
        col_qty_x = 360
        col_tva_x = 440
        col_amt_x = W - 40   # right-aligned

        # Pre-format the date / number once for reuse on every page.
        try:
            inv_dt = datetime.strptime(invoice["date"], "%d/%m/%Y")
            date_str = self.format_french_date(inv_dt)
        except (ValueError, KeyError):
            date_str = invoice.get("date", "")
        full_number = invoice.get("number", "")
        if not full_number:
            seq = invoice.get("seq", "")
            try:
                full_number = f"{int(seq):02d}"
            except (TypeError, ValueError):
                full_number = str(seq)

        page_state = {"n": 0}

        def draw_page_top():
            """Draw the per-page chrome (watermark, banner, client, table
            header) and return the y of the first line-item row."""
            page_state["n"] += 1
            # --- watermark (behind everything) ---
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
            # --- top banner (colour from Settings; dark text on light tint) ---
            banner_h = 180
            banner_fill, banner_text = self._invoice_banner()
            if banner_fill is not None:
                c.setFillColorRGB(*banner_fill)
                c.rect(0, H - banner_h, W, banner_h, stroke=0, fill=1)
            c.setFillColorRGB(*banner_text)
            c.setFont("Helvetica-Bold", 70)
            c.drawString(40, H - banner_h + 60, "FACTURE")
            c.setFont("Helvetica", 12)
            c.drawRightString(W - 40, H - banner_h + 110, date_str)
            c.setFont("Helvetica-Bold", 13)
            c.drawRightString(W - 40, H - banner_h + 88, "Num\u00e9ro de facture")
            c.setFont("Helvetica", 12)
            c.drawRightString(W - 40, H - banner_h + 70, full_number)
            # --- white body: CLIENT + table header ---
            body_top = H - banner_h - 30
            c.setFillColorRGB(*self.INV_TEXT_DARK)
            c.setFont("Helvetica-Bold", 14)
            label = "CLIENT" if page_state["n"] == 1 else f'CLIENT  {LANGUAGES[self.lang]["inv_page_suite"]}'
            c.drawString(40, body_top, label)
            c.setFont("Helvetica", 12)
            c.drawString(40, body_top - 22, invoice.get("recipient_name", ""))
            sep_y = body_top - 56
            c.setStrokeColorRGB(0.6, 0.6, 0.6)
            c.setLineWidth(0.6)
            c.line(40, sep_y, W - 40, sep_y)
            # Event name + location, in the gap between CLIENT and the table.
            ev = self.data.get("event", {})
            ev_name = (ev.get("name") or "").strip()
            ev_loc = (ev.get("location") or "").strip()
            c.setFillColorRGB(*self.INV_TEXT_DARK)
            ev_y = sep_y - 30
            if ev_name:
                c.setFont("Helvetica-Bold", 13)
                c.drawString(40, ev_y, ev_name)
            if ev_loc:
                c.setFont("Helvetica", 11)
                c.drawString(40, ev_y - 18, ev_loc)
            header_y = sep_y - 90
            c.setFillColorRGB(*self.INV_TEXT_DARK)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(col_desc_x, header_y, "Description")
            c.drawString(col_qty_x, header_y, "Quantit\u00e9")
            c.drawString(col_tva_x, header_y, "TVA")
            c.drawRightString(col_amt_x, header_y, "Amount")
            c.setLineWidth(0.4)
            c.line(40, header_y - 6, W - 40, header_y - 6)
            return header_y - 30

        def draw_footer():
            foot_h = 160
            banner_fill, banner_text = self._invoice_banner()
            if banner_fill is not None:
                c.setFillColorRGB(*banner_fill)
                c.rect(0, 0, W, foot_h, stroke=0, fill=1)
            c.setFillColorRGB(*banner_text)
            header_y = foot_h - 28
            line_step = 16
            content_y = header_y - 30
            lx = 40
            c.setFont("Helvetica-Bold", 13)
            c.drawString(lx, header_y, "INFORMATIONS DE PAIEMENT")
            ly = content_y
            c.setFont("Helvetica", 10)
            c.drawString(lx, ly, f"Nom: {CONFIG.get('bank_account_holder', '')}")
            ly -= line_step
            c.drawString(lx, ly, f"Banque : {CONFIG.get('bank_name', '')}")
            ly -= line_step
            c.drawString(lx, ly, "Num\u00e9ro de compte :")
            ly -= line_step
            c.drawString(lx, ly, " ".join(CONFIG.get("iban_groups", [])))
            rx = W / 2 - 10
            line1, line2 = self._split_legal_name(CONFIG.get("issuer_legal_name", ""))
            c.setFont("Helvetica-Bold", 13)
            c.drawString(rx, header_y, line1.upper())
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

        # ---- layout: split rows into pages, then render ----
        FOOTER_H = 160
        LINE_STEP = 20
        FIRST_Y = (H - 180 - 30 - 56 - 90 - 30)   # first row y (see draw_page_top)
        LINE_BOTTOM = FOOTER_H + 60               # lowest a row may sit
        TOTALS_TERMS_H = 150                      # room totals + terms need

        def _rows_capacity(from_y):
            n = 0
            y = from_y
            while y >= LINE_BOTTOM:
                n += 1
                y -= LINE_STEP
            return n

        # Phase 1: page-break decisions (no drawing), mirroring the renderer.
        pages = []          # each page: list of rows
        cur = []
        y = FIRST_Y
        for r in rows:
            if y < LINE_BOTTOM:
                pages.append(cur)
                cur = []
                y = FIRST_Y
            cur.append(r)
            last_y = y
            y -= LINE_STEP
        pages.append(cur)
        # Totals + terms go under the last row; if they don't fit, add a page.
        last_y = FIRST_Y - LINE_STEP * (len(pages[-1]) - 1) if pages[-1] else FIRST_Y
        totals_on_new_page = (last_y - 28 < FOOTER_H + TOTALS_TERMS_H)
        if totals_on_new_page:
            pages.append([])
        total_pages = len(pages)

        def draw_page_number(idx):
            c.saveState()
            c.setFillColorRGB(*self.INV_TEXT_DARK)
            c.setFont("Helvetica", 9)
            c.drawCentredString(W / 2, FOOTER_H + 18, f"{idx} / {total_pages}")
            c.restoreState()

        # Phase 2: render.
        for pidx, page_rows in enumerate(pages, start=1):
            line_y = draw_page_top()
            c.setFillColorRGB(*self.INV_TEXT_DARK)
            c.setFont("Helvetica", 11)
            row_y = line_y
            for (ldesc, lqty, lamt) in page_rows:
                c.drawString(col_desc_x, row_y, str(ldesc))
                c.drawString(col_qty_x, row_y, str(lqty))
                c.drawString(col_tva_x, row_y, "0%")
                c.drawRightString(col_amt_x, row_y, self._fmt_invoice_amount(lamt))
                last_row_y = row_y
                row_y -= LINE_STEP
            if not page_rows:
                last_row_y = line_y  # totals-only final page

            # Totals + terms only on the last page.
            if pidx == total_pages:
                ly = last_row_y
                c.setLineWidth(0.4)
                c.line(40, ly - 14, W - 40, ly - 14)
                totals = [
                    ("Sous-total", amount_str, False),
                    ("TVA", "0\u20ac", False),
                    ("Total", amount_str, True),
                ]
                tot_y = ly - 38
                for label, value, bold in totals:
                    c.setFont("Helvetica-Bold" if bold else "Helvetica", 12 if bold else 11)
                    c.drawRightString(col_tva_x + 28, tot_y, label)
                    c.drawRightString(col_amt_x, tot_y, value)
                    tot_y -= 22
                c.setLineWidth(0.4)
                c.line(40, ly - 28, W - 40, ly - 28)

                days = CONFIG.get("payment_terms_days", 30)
                legal = CONFIG.get("issuer_legal_name", "")
                terms = (f"\u00c0 transf\u00e9rer sur le compte courant de {legal} dans un "
                         f"d\u00e9lai de {days} jours calendaires \u00e0 compter de la date d'\u00e9mission")
                c.setFont("Helvetica", 10)
                terms_y = tot_y - 30
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

            # Footer + page number on EVERY page.
            draw_footer()
            draw_page_number(pidx)
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

    # ---- Branding assets (Group E) ------------------------------------
    # Canonical filenames the app reads elsewhere; max upload size; and the
    # standard fitted output size for each (so varied source dimensions all
    # render consistently).
    ASSET_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per image
    ASSET_SPECS = {
        # which: (canonical_path, fit_box, kind)
        "logo":      ("logo.png", (400, 400), "png"),
        "watermark": ("watermark.png", (1000, 1000), "png"),
        "icon":      ("logo.ico", (256, 256), "ico"),
    }

    def _asset_present(self, which):
        path = self.ASSET_SPECS[which][0]
        return os.path.exists(path)

    def _import_asset(self, which, src_path):
        """Validate + normalise + save a branding image to its canonical file.
        Returns True on success; shows a clear message and returns False on any
        problem (bad type, too large, unreadable)."""
        L = LANGUAGES[self.lang]
        canonical, fit_box, kind = self.ASSET_SPECS[which]
        ext = os.path.splitext(src_path)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg"):
            messagebox.showerror("Error", L["asset_bad_type"])
            return False
        try:
            size = os.path.getsize(src_path)
        except OSError as e:
            messagebox.showerror("Error", L["asset_load_failed"].format(err=str(e)))
            return False
        if size > self.ASSET_MAX_BYTES:
            messagebox.showerror("Error", L["asset_too_big"].format(
                size=self._human_size(size), max=self._human_size(self.ASSET_MAX_BYTES)))
            return False
        try:
            from PIL import Image as PILImage
            img = PILImage.open(src_path)
            img.load()
            # Fit within the standard box, preserving aspect ratio. Keep
            # transparency for PNG/ICO; flatten onto white for opaque sources.
            if kind == "ico":
                img = img.convert("RGBA")
                img.thumbnail(fit_box, PILImage.LANCZOS)
                img.save(canonical, format="ICO",
                         sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
            else:
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")
                img.thumbnail(fit_box, PILImage.LANCZOS)
                img.save(canonical, format="PNG")
        except Exception as e:
            logging.error(f"import asset {which} failed: {e}")
            messagebox.showerror("Error", L["asset_load_failed"].format(err=str(e)))
            return False
        return True

    def _remove_asset(self, which):
        canonical = self.ASSET_SPECS[which][0]
        try:
            if os.path.exists(canonical):
                os.remove(canonical)
            return True
        except OSError as e:
            logging.error(f"remove asset {which} failed: {e}")
            messagebox.showerror("Error", str(e))
            return False

    def open_settings_dialog(self):
        if self._raise_open_panel():
            return
        L = LANGUAGES[self.lang]
        dlg = Toplevel(self.root)
        dlg.title(L["settings_title"])
        dlg.transient(self.root)
        dlg.update_idletasks()  # macOS: ensure window is mapped before grabbing
        dlg.grab_set()
        self._center(dlg, 640, 680)
        dlg.minsize(560, 480)
        dlg.resizable(True, True)
        self._register_panel(dlg)

        outer = ttk.Frame(dlg, padding=12)
        outer.pack(fill="both", expand=True)
        # Stable button bar at the bottom.
        btn_bar = ttk.Frame(outer)
        btn_bar.pack(side="bottom", fill="x", pady=(8, 0))

        # Master-detail: a category list on the left raises one detail pane on
        # the right. Order: Branding -> Events -> Reports -> Invoices (system
        # settings would slot in first, ahead of Branding, when they exist).
        main = ttk.Frame(outer)
        main.pack(side="top", fill="both", expand=True)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)
        nav = ttk.Treeview(main, show="tree", selectmode="browse", height=10)
        nav.column("#0", width=160, stretch=False)
        nav.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        detail = ttk.Frame(main)
        detail.grid(row=0, column=1, sticky="nsew")
        detail.rowconfigure(0, weight=1)
        detail.columnconfigure(0, weight=1)

        groups = {}

        def add_group(key, title):
            o, inner = self._scroll_area(detail)
            o.grid(row=0, column=0, sticky="nsew")
            inner.columnconfigure(1, weight=1)
            nav.insert("", "end", iid=key, text="  " + title)
            groups[key] = o
            return inner

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

        # ---- Branding ----
        g_brand = add_group("branding", L["settings_group_branding"])
        ttk.Label(g_brand, text=L["asset_note"].format(max=self._human_size(self.ASSET_MAX_BYTES)),
                  font=("Arial", self.font_size - 3), foreground="#555").grid(
                      row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        status_labels = {}

        def refresh_status(which):
            present = self._asset_present(which)
            status_labels[which].config(
                text=L["asset_present"] if present else L["asset_absent"],
                foreground="#2e7d32" if present else "#999")

        def make_asset_row(r, which, label_key):
            ttk.Label(g_brand, text=L[label_key], font=("Arial", self.font_size)).grid(
                row=r, column=0, sticky="w", pady=3, padx=(0, 8))
            st = ttk.Label(g_brand, font=("Arial", self.font_size - 2))
            st.grid(row=r, column=1, sticky="w")
            status_labels[which] = st
            bf = ttk.Frame(g_brand)
            bf.grid(row=r, column=2, sticky="e")

            def upload():
                src = filedialog.askopenfilename(
                    title=L["asset_upload"],
                    filetypes=[("Images", "*.png *.jpg *.jpeg"), ("PNG", "*.png"),
                               ("JPEG", "*.jpg *.jpeg")])
                if not src:
                    return
                if self._import_asset(which, src):
                    refresh_status(which)
                    messagebox.showinfo("", L["asset_saved"].format(which=L[label_key]))

            def remove():
                if not self._asset_present(which):
                    return
                if messagebox.askyesno("", L["asset_remove_q"].format(which=L[label_key])):
                    if self._remove_asset(which):
                        refresh_status(which)
                        messagebox.showinfo("", L["asset_removed"].format(which=L[label_key]))

            ttk.Button(bf, text=L["asset_upload"], command=upload).pack(side="left", padx=2)
            ttk.Button(bf, text=L["asset_remove"], command=remove).pack(side="left", padx=2)
            refresh_status(which)

        make_asset_row(1, "logo", "asset_logo")
        make_asset_row(2, "watermark", "asset_watermark")
        make_asset_row(3, "icon", "asset_icon")
        ttk.Label(g_brand, text=L["settings_branding_restart_note"],
                  font=("Arial", max(8, self.font_size - 3)), foreground="#888",
                  wraplength=420, justify="left").grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

        # ---- Events (competition ceilings + event default) ----
        g_events = add_group("events", L["settings_group_events"])
        ttk.Label(g_events, text=L["settings_field_max_rounds"], font=("Arial", self.font_size)).grid(
            row=0, column=0, sticky="w", pady=3, padx=(0, 8))
        max_rounds_entry = ttk.Entry(g_events, font=("Arial", self.font_size), width=6, validate="key",
                                     validatecommand=(self.root.register(self.validate_round_ceiling), "%P"))
        max_rounds_entry.grid(row=0, column=1, sticky="w")
        max_rounds_entry.insert(0, str(CONFIG.get("max_round_count", DEFAULT_MAX_ROUNDS)))
        ttk.Label(g_events, text=L["settings_field_max_participants"], font=("Arial", self.font_size)).grid(
            row=1, column=0, sticky="w", pady=3, padx=(0, 8))
        max_parts_entry = ttk.Entry(g_events, font=("Arial", self.font_size), width=6, validate="key",
                                    validatecommand=(self.root.register(self.validate_participants_ceiling), "%P"))
        max_parts_entry.grid(row=1, column=1, sticky="w")
        max_parts_entry.insert(0, str(CONFIG.get("max_participants_count", DEFAULT_MAX_PARTICIPANTS)))
        def_track = tk.BooleanVar(value=bool(CONFIG.get("default_track_details", False)))
        ttk.Checkbutton(g_events, text=L["settings_default_track"], variable=def_track).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 1))

        # ---- Reports (new-event report defaults) ----
        g_reports = add_group("reports", L["settings_group_reports"])
        def_highlight = tk.BooleanVar(value=bool(CONFIG.get("default_report_highlight", True)))
        def_individual = tk.BooleanVar(value=bool(CONFIG.get("default_individual_reports", False)))
        def_combined = tk.BooleanVar(value=bool(CONFIG.get("default_combined_ranking", False)))
        _restart = f'  ({L["settings_restart_note"]})'
        ttk.Checkbutton(g_reports, text=L["settings_default_highlight"], variable=def_highlight).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=1)
        indiv_row = ttk.Frame(g_reports)
        indiv_row.grid(row=1, column=0, columnspan=2, sticky="w", pady=1)
        ttk.Checkbutton(indiv_row, text=L["settings_default_individual"], variable=def_individual).pack(side="left")
        ttk.Label(indiv_row, text=_restart, font=("Arial", max(8, self.font_size - 2)), foreground="#888").pack(side="left")
        comb_row = ttk.Frame(g_reports)
        comb_row.grid(row=2, column=0, columnspan=2, sticky="w", pady=1)
        combined_default_chk = ttk.Checkbutton(comb_row, text=L["settings_default_combined"], variable=def_combined)
        combined_default_chk.pack(side="left")
        ttk.Label(comb_row, text=_restart, font=("Arial", max(8, self.font_size - 2)), foreground="#888").pack(side="left")

        def _sync_combined_default(*_a):
            if def_individual.get():
                combined_default_chk.state(["!disabled"])
            else:
                def_combined.set(False)
                combined_default_chk.state(["disabled"])
        def_individual.trace_add("write", _sync_combined_default)
        _sync_combined_default()

        # ---- Invoices (issuer + banner colour + bank) ----
        g_inv = add_group("invoices", L["settings_group_invoices"])
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
            add_row(g_inv, k, L[lk])
        _bc_row = g_inv.grid_size()[1]
        ttk.Label(g_inv, text=L["settings_field_banner_colour"], font=("Arial", self.font_size)).grid(
            row=_bc_row, column=0, sticky="w", pady=3, padx=(0, 8))
        banner_labels = [(L["colour_none"], "none"), (L["col_green"], "green"),
                         (L["col_yellow"], "yellow"), (L["col_blue"], "blue"),
                         (L["col_grey"], "grey"), (L["col_red"], "red")]
        banner_label_to_key = {lbl: key for lbl, key in banner_labels}
        banner_key_to_label = {key: lbl for lbl, key in banner_labels}
        banner_combo = ttk.Combobox(g_inv, state="readonly", width=12,
                                    values=[lbl for lbl, _ in banner_labels],
                                    font=("Arial", self.font_size))
        banner_combo.grid(row=_bc_row, column=1, sticky="w", pady=3)
        banner_combo.set(banner_key_to_label.get(CONFIG.get("invoice_banner_colour", "blue"),
                                                 banner_key_to_label["blue"]))
        _bk_row = g_inv.grid_size()[1]
        ttk.Label(g_inv, text=L["settings_bank_section"], font=("Arial", self.font_size, "bold")).grid(
            row=_bk_row, column=0, columnspan=2, sticky="w", pady=(12, 2))
        for k, lk in [
            ("bank_account_holder", "settings_field_bank_account_holder"),
            ("bank_name", "settings_field_bank_name"),
            ("iban_groups", "settings_field_iban"),
            ("payment_terms_days", "settings_field_payment_terms"),
        ]:
            add_row(g_inv, k, L[lk])

        def show_group(key):
            if key in groups:
                groups[key].tkraise()
        nav.bind("<<TreeviewSelect>>",
                 lambda _e: show_group(nav.selection()[0]) if nav.selection() else None)
        nav.selection_set("branding")
        show_group("branding")

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
            # max round count (app-wide ceiling) -> int, clamped 1..99
            try:
                mrc = int(max_rounds_entry.get().strip())
            except ValueError:
                mrc = DEFAULT_MAX_ROUNDS
            new_cfg["max_round_count"] = max(1, min(mrc, ROUND_CEILING_HARD_MAX))
            # max participants/round (app-wide ceiling) -> int, clamped 1..999
            try:
                mpc = int(max_parts_entry.get().strip())
            except ValueError:
                mpc = DEFAULT_MAX_PARTICIPANTS
            new_cfg["max_participants_count"] = max(1, min(mpc, PARTICIPANTS_CEILING_HARD_MAX))
            # invoice header/footer colour
            new_cfg["invoice_banner_colour"] = banner_label_to_key.get(banner_combo.get(), "blue")
            # new-event defaults
            new_cfg["default_track_details"] = bool(def_track.get())
            new_cfg["default_report_highlight"] = bool(def_highlight.get())
            new_cfg["default_individual_reports"] = bool(def_individual.get())
            new_cfg["default_combined_ranking"] = bool(def_combined.get() and def_individual.get())
            if save_config(new_cfg):
                messagebox.showinfo("", L["settings_saved"])
                dlg.destroy()

        ttk.Button(btn_bar, text=L["settings_save"], command=do_save).pack(side="left", padx=4)
        ttk.Button(btn_bar, text=L["close"], command=dlg.destroy).pack(side="right", padx=4)
        dlg.update_idletasks()
        dlg.wait_window()

    # Light, print-friendly highlight tones - dark text stays readable on all.
    REPORT_HIGHLIGHT_COLOURS = {
        "green":  (0.82, 0.93, 0.80),
        "yellow": (0.99, 0.96, 0.78),
        "blue":   (0.81, 0.89, 0.97),
        "grey":   (0.89, 0.89, 0.89),
        "red":    (0.98, 0.84, 0.82),
    }

    def _report_highlight_colour(self):
        from reportlab.lib.colors import Color
        key = self.data.get("report_highlight_colour", "green")
        rgb = self.REPORT_HIGHLIGHT_COLOURS.get(key, self.REPORT_HIGHLIGHT_COLOURS["green"])
        return Color(*rgb)

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
                # Fit the logo inside a 1-inch box, preserving aspect ratio so
                # rectangular logos are not distorted into a square.
                box = 1 * inch
                lw, lh = box, box
                try:
                    from PIL import Image as _PILImage
                    with _PILImage.open(logo_path) as _im:
                        iw, ih = _im.size
                    if iw and ih:
                        scale = min(box / iw, box / ih)
                        lw, lh = iw * scale, ih * scale
                except Exception as _e:
                    logging.warning(f"logo aspect read failed: {_e}")
                logo = Image(logo_path, width=lw, height=lh)
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
            # Qualifiers proceeding to the final FROM this round (Group C).
            # Highlighted only on round reports, never on the final's own report.
            highlight_rows = []
            highlight_colour = None
            if sk != "final" and self.data.get("report_highlight", True):
                try:
                    qres = self.compute_qualifiers()
                    qualified_here = set(qres["per_round"].get(sk, {}).get("qualified", []))
                    highlight_colour = self._report_highlight_colour()
                except Exception as e:
                    logging.error(f"highlight computation failed: {e}")
                    qualified_here = set()
            else:
                qualified_here = set()
            for rank_i, name in enumerate(sorted_names, 1):
                catches = sess["catches"].get(name, [])
                total_catches = sum(c["num_catches"] for c in catches) if catches else 0
                total_weight = sum(c["weight"] for c in catches) if catches else 0
                longest = max((c["length"] for c in catches if c["length"] is not None), default=0) if catches else 0
                sess_total_catches += total_catches
                sess_total_weight += total_weight
                info = self.data["participants"].get(name, {})
                cat_disp = L["category_options"].get(info.get("category", ""), info.get("category", ""))
                if name in qualified_here:
                    highlight_rows.append(len(table))  # current row index in `table`
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
            summary_style = list(common_style)
            if highlight_colour is not None:
                for r in highlight_rows:
                    summary_style.append(("BACKGROUND", (0, r), (-1, r), highlight_colour))
            story.append(Table(table, colWidths=sum_widths, style=summary_style, repeatRows=1))
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
            if getattr(self, "_reports_reload", None) is not None:
                self._reports_reload()
            if messagebox.askyesno("", L["report_open_q"]):
                self.open_file_external(filename)
        except Exception as e:
            logging.error(f"generate_report failed: {e}")
            messagebox.showerror("Error", f"Report generation failed: {type(e).__name__}: {e}")

    def _event_report_files(self):
        """Report PDFs for the current event: list of (label, path), round
        order then any extras. Reports live only in the event folder."""
        L = LANGUAGES[self.lang]
        ev = self.data.get("event", {})
        name_file = str(ev.get("name", "event")).replace(" ", "_")
        date = str(ev.get("date", ""))
        try:
            date_str = datetime.strptime(date, "%d/%m/%Y").strftime("%Y%m%d")
        except ValueError:
            return []
        folder = f"{date_str}_{name_file}"
        if not os.path.isdir(folder):
            return []
        out = []
        # Known per-round/final report files, in round order.
        for sk in SESSION_KEYS:
            fn = os.path.join(folder, f"{folder}_{sk}.pdf")
            if os.path.exists(fn):
                out.append((key_to_display(self.lang, sk), fn))
        return out

    def custom_dialog(self, title, message, buttons):
        dialog = Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.update_idletasks()  # macOS: ensure window is mapped before grabbing
        dialog.grab_set()
        text_length = len(message)
        width = max(300, min(600, text_length * 8))
        height = max(150, 100 + (text_length // 50) * 30)
        self._center(dialog, int(width), int(height))

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
            self.current_manche = "manche1"   # back to Round 1 for the fresh event
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
        # Export the CURRENT (open) event - a manual save/checkpoint available
        # any time the mandatory fields pass validation. Acts on self.data, not
        # on a list selection. Saves to the canonical event folder by default,
        # but the operator may choose any location for a portable copy.
        if hasattr(self, "event_name"):
            self.data.setdefault("event", {})
            self.data["event"]["name"] = self.event_name.get().strip()
            self.data["event"]["location"] = self.location.get().strip()
            self.data["event"]["date"] = self.date.get()
        ev = self.data.get("event", {})
        if not ev.get("name") or not ev.get("location"):
            messagebox.showerror("Error", LANGUAGES[self.lang]["export_blocked_fields"])
            return
        folder_name = get_event_folder(ev)
        try:
            os.makedirs(folder_name, exist_ok=True)
        except PermissionError:
            messagebox.showerror("Error", LANGUAGES[self.lang]["permission_error"].replace("[folder]", folder_name))
            return
        # Always keep the canonical copy current (this is the "save now" the
        # operator wants), then offer to place a portable copy anywhere.
        canonical = os.path.join(folder_name, f"{folder_name}.json")
        try:
            with open(canonical, 'w', encoding='utf-8') as file:
                json.dump(self.data, file, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"export_event canonical save failed: {str(e)}")
            messagebox.showerror("Error", f"Export failed: {str(e)}")
            return
        # Ask only for a destination FOLDER (a save-file dialog re-prompts to
        # confirm overwrite on macOS regardless of confirmoverwrite, which is
        # noise here since the app saves to the canonical copy continuously).
        # The portable copy is written into the chosen folder under the event's
        # own filename, overwriting silently if present.
        dest_dir = filedialog.askdirectory(
            title=LANGUAGES[self.lang]["export_event"],
            initialdir=os.path.abspath(folder_name),
            mustexist=True)
        if not dest_dir or os.path.abspath(dest_dir) == os.path.abspath(folder_name):
            # Cancelled, or chose the canonical folder itself - already saved.
            messagebox.showinfo(LANGUAGES[self.lang]["saved"],
                                LANGUAGES[self.lang]["export_success"].format(filename=os.path.abspath(canonical)))
            return
        dest = os.path.join(dest_dir, f"{folder_name}.json")
        try:
            with open(dest, 'w', encoding='utf-8') as file:
                json.dump(self.data, file, indent=4, ensure_ascii=False)
            messagebox.showinfo(LANGUAGES[self.lang]["saved"],
                                LANGUAGES[self.lang]["export_success"].format(filename=os.path.abspath(dest)))
        except Exception as e:
            logging.error(f"export_event copy failed: {str(e)}")
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def _scan_local_events(self):
        """Find event JSON files in the application folder.

        Events are stored as <folder>/<folder>.json where folder is
        YYYYMMDD_EventName. Rather than parse the folder name (which cannot
        tell a user's underscore from one inserted for a space), we read each
        JSON and take the real event name and date from inside it.

        Returns a list of dicts: {path, name, date, date_sort} sorted by date
        descending (most recent first).
        """
        events = []
        try:
            base = os.getcwd()
            for entry in os.listdir(base):
                folder = os.path.join(base, entry)
                if not os.path.isdir(folder):
                    continue
                data_file = os.path.join(folder, f"{entry}.json")
                if not os.path.exists(data_file):
                    continue
                try:
                    with open(data_file, 'r', encoding='utf-8') as fh:
                        d = json.load(fh)
                    ev = d.get("event", {}) if isinstance(d, dict) else {}
                    name = (ev.get("name") or entry).strip()
                    date = (ev.get("date") or "").strip()
                    try:
                        date_sort = datetime.strptime(date, "%d/%m/%Y")
                    except ValueError:
                        date_sort = datetime.min
                    invoices = d.get("invoices", []) if isinstance(d, dict) else []
                    inv_count = len(invoices) if isinstance(invoices, list) else 0
                    # Folder size + file count (recursive).
                    total_bytes, file_count = 0, 0
                    for root, _dirs, files in os.walk(folder):
                        for f in files:
                            file_count += 1
                            try:
                                total_bytes += os.path.getsize(os.path.join(root, f))
                            except OSError:
                                pass
                    events.append({"path": data_file, "folder": folder, "name": name,
                                   "date": date, "date_sort": date_sort,
                                   "invoices": inv_count, "bytes": total_bytes,
                                   "files": file_count})
                except Exception as e:
                    logging.error(f"scan event {data_file} failed: {e}")
        except Exception as e:
            logging.error(f"_scan_local_events failed: {e}")
        events.sort(key=lambda e: e["date_sort"], reverse=True)
        return events

    def _human_size(self, n):
        size = float(n)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"

    def _prompt_text(self, parent, title, message):
        """Small modal asking for a line of text. Returns the string or None."""
        L = LANGUAGES[self.lang]
        top = Toplevel(parent)
        top.title(title)
        top.transient(parent)
        top.update_idletasks()
        top.grab_set()
        self._center(top, 440, 180)
        frame = ttk.Frame(top, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=message, wraplength=400, justify="left").pack(anchor="w", pady=(0, 8))
        var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=var, font=("Arial", self.font_size), width=36)
        entry.pack(fill="x")
        entry.focus_set()
        result = {"value": None}
        def ok():
            result["value"] = var.get()
            top.destroy()
        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="OK", command=ok).pack(side="right", padx=4)
        ttk.Button(btns, text=L["cancel"], command=top.destroy).pack(side="right", padx=4)
        top.bind("<Return>", lambda e: ok())
        top.wait_window()
        return result["value"]

    def open_manage_events_panel(self):
        if self._raise_open_panel():
            return
        L = LANGUAGES[self.lang]
        # Flush the current event to its folder first, so it appears in the
        # list and can be exported. Quiet (no dialogs); only if it has the
        # mandatory fields. This is the same write the app does on auto-save.
        try:
            ev = self.data.get("event", {})
            if ev.get("name") and ev.get("location"):
                folder = get_event_folder(ev)
                os.makedirs(folder, exist_ok=True)
                with open(os.path.join(folder, f"{folder}.json"), "w", encoding="utf-8") as fh:
                    json.dump(self.data, fh, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"flush current event before manage panel failed: {e}")

        win = Toplevel(self.root)
        win.title(L["manage_events_title"])
        win.transient(self.root)
        win.update_idletasks()
        win.grab_set()
        self._center(win, 720, 440)
        self._register_panel(win)

        outer = ttk.Frame(win, padding=10)
        outer.pack(fill="both", expand=True)
        btns = ttk.Frame(outer)
        btns.pack(side="bottom", fill="x", pady=(8, 0))

        cols = ("date", "title", "invoices", "size")
        tv = ttk.Treeview(outer, columns=cols, show="headings", height=13)
        tv.heading("date", text=L["events_col_date"])
        tv.heading("title", text=L["events_col_title"])
        tv.heading("invoices", text=L["events_col_invoices"])
        tv.heading("size", text=L["events_col_size"])
        tv.column("date", width=90, anchor="center")
        tv.column("title", width=380, anchor="w")
        tv.column("invoices", width=80, anchor="center")
        tv.column("size", width=90, anchor="e")
        sb = ttk.Scrollbar(outer, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="top", fill="both", expand=True)

        state = {"events": []}

        def reload_list():
            state["events"] = self._scan_local_events()
            tv.delete(*tv.get_children())
            if state["events"]:
                for idx, ev in enumerate(state["events"]):
                    tv.insert("", "end", iid=str(idx),
                              values=(ev["date"], ev["name"], ev["invoices"],
                                      self._human_size(ev["bytes"])))
            else:
                tv.insert("", "end", values=("", L["events_no_events"], "", ""))

        def selected():
            sel = tv.selection()
            if not sel:
                messagebox.showinfo(L["manage_events_title"], L["events_select_row"])
                return None
            try:
                return state["events"][int(sel[0])]
            except (ValueError, IndexError):
                return None

        def open_selected(_evt=None):
            ev = selected()
            if not ev:
                return
            win.destroy()
            try:
                self._load_event_file(ev["path"])
            except Exception as e:
                logging.error(f"manage_events open failed: {e}")
                messagebox.showerror(L["error"], str(e))

        def browse():
            win.destroy()
            self._browse_import()

        def delete_selected():
            ev = selected()
            if not ev:
                return
            # Never delete the event currently open in the app.
            cur = self.data.get("event", {})
            if cur.get("name"):
                cur_folder = get_event_folder(cur)
                if os.path.basename(ev["folder"]) == cur_folder:
                    messagebox.showwarning(L["manage_events_title"], L["events_del_current_blocked"])
                    return
            # Step 1: named confirmation listing what will be removed.
            if not messagebox.askyesno("", L["events_del_confirm1"].format(
                    name=ev["name"], date=ev["date"], files=ev["files"], inv=ev["invoices"])):
                return
            # Step 2: if invoices exist (financial records), require typing the name.
            if ev["invoices"] > 0:
                typed = self._prompt_text(win, L["events_delete"],
                                          L["events_del_confirm2_invoices"].format(inv=ev["invoices"]))
                if typed is None:
                    return
                if typed.strip() != ev["name"]:
                    messagebox.showinfo(L["events_delete"], L["events_del_name_mismatch"])
                    return
            try:
                import shutil
                shutil.rmtree(ev["folder"])
                messagebox.showinfo(L["manage_events_title"], L["events_del_done"].format(name=ev["name"]))
                reload_list()
            except Exception as e:
                logging.error(f"delete event failed: {e}")
                messagebox.showerror(L["error"], str(e))

        tv.bind("<Double-1>", open_selected)
        ttk.Button(btns, text=L["events_open"], command=open_selected).pack(side="left", padx=3)
        ttk.Button(btns, text=L["events_delete"], command=delete_selected).pack(side="left", padx=3)
        ttk.Button(btns, text=L["events_browse"], command=browse).pack(side="left", padx=3)
        ttk.Button(btns, text=L["cancel"], command=win.destroy).pack(side="right", padx=3)

        reload_list()

    def _load_event_file(self, file_path):
        """Validate and load an event JSON file into the app."""
        with open(file_path, 'r', encoding='utf-8') as file:
            imported_data = json.load(file)
        if (not isinstance(imported_data, dict) or "event" not in imported_data
                or "participants" not in imported_data):
            raise ValueError("Invalid event data format")
        self.data = migrate_data(imported_data)
        self.root.title(LANGUAGES[self.lang]["title"])
        self.build_main_ui()
        messagebox.showinfo(LANGUAGES[self.lang]["saved"],
                            LANGUAGES[self.lang]["import_success"])

    def _browse_import(self):
        """File-dialog import (any location): archives, emailed files, etc."""
        try:
            file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
            if not file_path:
                return False
            self._load_event_file(file_path)
            return True
        except Exception as e:
            logging.error(f"browse import failed: {str(e)}")
            messagebox.showerror(LANGUAGES[self.lang]["error"],
                                 f"Failed to import event: {str(e)}")
            return False

    def open_date_picker(self, parent, initial_str=None):
        """Modal dialog with an inline tkcalendar Calendar. Returns the chosen
        date as 'dd/mm/yyyy', or None on cancel.

        Used instead of tkcalendar's DateEntry drop-down inside Toplevel forms:
        the drop-down is a borderless popup with its own global grab and is
        unreliable on macOS there (blank/flashing calendar, freezes). An
        ordinary modal dialog with the inline Calendar widget behaves like
        every other panel in the app, which all work.
        """
        L = LANGUAGES[self.lang]
        try:
            init = datetime.strptime((initial_str or "").strip(), "%d/%m/%Y")
        except (ValueError, TypeError):
            init = datetime.now()
        top = Toplevel(parent)
        top.title(L["inv_pick_date"])
        top.transient(parent)
        top.update_idletasks()
        top.grab_set()
        cal = Calendar(top, selectmode="day", date_pattern="dd/mm/yyyy",
                       year=init.year, month=init.month, day=init.day)
        cal.pack(padx=10, pady=10, fill="both", expand=True)
        result = {"value": None}

        def ok():
            result["value"] = cal.get_date()
            top.destroy()

        btns = ttk.Frame(top)
        btns.pack(pady=(0, 10))
        ttk.Button(btns, text="OK", command=ok).pack(side="left", padx=6)
        ttk.Button(btns, text=L["cancel"], command=top.destroy).pack(side="left", padx=6)
        cal.bind("<Double-1>", lambda e: ok())
        top.bind("<Return>", lambda e: ok())
        top.wait_window()
        return result["value"]

    def _ask_tie_choice(self, parent, round_key, names, slots):
        """Modal multi-select: operator picks exactly `slots` of the tied
        `names` to proceed to the final. Returns the chosen list, or [] if
        cancelled (cancel leaves those final slots unfilled)."""
        L = LANGUAGES[self.lang]
        top = Toplevel(parent)
        top.title(L["qual_tie_title"])
        top.transient(parent)
        top.update_idletasks()
        top.grab_set()
        self._center(top, 420, 380)
        frame = ttk.Frame(top, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, wraplength=380, justify="left",
                  text=L["qual_tie_prompt"].format(
                      rnd=key_to_display(self.lang, round_key),
                      n=len(names), slots=slots)).pack(anchor="w", pady=(0, 8))
        lb = tk.Listbox(frame, selectmode="multiple", height=10,
                        font=("Arial", self.font_size), exportselection=False)
        for nm in names:
            lb.insert(tk.END, nm)
        lb.pack(fill="both", expand=True)
        chosen = {"value": []}

        def confirm():
            picks = [names[i] for i in lb.curselection()]
            if len(picks) != slots:
                messagebox.showwarning("", L["qual_pick_count"].format(slots=slots))
                return
            chosen["value"] = picks
            top.destroy()

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="OK", command=confirm).pack(side="right", padx=4)
        ttk.Button(btns, text=L["cancel"], command=top.destroy).pack(side="right", padx=4)
        top.wait_window()
        return chosen["value"]

    def _raise_open_panel(self):
        """If a working panel is already open, raise it and return True.

        Main-window action buttons call this first. Normally a panel's modal
        grab blocks the main window anyway; this guard covers the one gap
        where no grab is held (while the invoice form is open) so a second
        manager/settings/etc. can never be stacked on top.
        """
        panels = [w for w in self._open_panels if w.winfo_exists()]
        self._open_panels = panels
        if panels:
            try:
                panels[-1].lift()
                panels[-1].focus_force()
                self.root.bell()
            except tk.TclError:
                pass
            return True
        return False

    def _register_panel(self, win):
        """Track an open working panel so the app refuses to quit under it."""
        self._open_panels.append(win)

        def _gone(evt):
            if evt.widget is win and win in self._open_panels:
                self._open_panels.remove(win)

        win.bind("<Destroy>", _gone, add="+")

    def on_closing(self):
        # 1) The confirm dialog is already up: ignore repeated close clicks
        #    (they used to stack one popup per click during UI lag).
        if self._close_confirm_open:
            return
        # 2) A working panel is open: raise it instead of quitting under it.
        panels = [w for w in self._open_panels if w.winfo_exists()]
        self._open_panels = panels
        if panels:
            try:
                panels[-1].lift()
                panels[-1].focus_force()
                self.root.bell()
            except tk.TclError:
                pass
            return
        # 3) Normal confirmed close.
        self._close_confirm_open = True
        try:
            if self.custom_dialog(LANGUAGES[self.lang]["close"], LANGUAGES[self.lang]["confirm_close"], [(LANGUAGES[self.lang]["yes"], True), (LANGUAGES[self.lang]["no"], False)]):
                try:
                    save_data(self.data, self.data["event"])
                except Exception as e:
                    logging.error(f"on_closing save failed: {str(e)}")
                    messagebox.showerror("Error", LANGUAGES[self.lang]["error"])
                self.root.destroy()
        finally:
            self._close_confirm_open = False

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = FishingApp(root)
        root.mainloop()
    except Exception as e:
        logging.error(f"Main loop error: {str(e)}")
        messagebox.showerror("Error", f"Application failed: {str(e)}")

