# Fëscherfrënn Stengefort — Fishing Competition Register

A desktop application for managing fishing competitions for **Fëscherfrënn
Stengefort**: maintaining a roster of participants, assigning them to each
session of the competition, logging catches in real time, and generating
result reports.

It is built with a deliberately simple, large-font interface so that it can be
operated by non-technical users during a live event.

- **Languages:** English, French, German, Luxembourgish
- **Platform:** Windows (primary), also runs on macOS and Linux from source
- **Version:** 2.0
- **License:** MIT

---

## Features

- Single-screen workflow with a session selector (**Manche 1 / 2 / 3 / Final**)
- Live rankings update for the currently selected session
- Pre-load the full **competition roster** with each participant's
  optional club, category (Senior, Master, Veteran, Lady, U20, U15, U10) and
  remark, then assign them to whichever sessions they actually fish
- Add, edit and remove participants from a dedicated **Manage Participants**
  window
- Edit or delete any catch record after the fact, from a dedicated
  **Edit Catches** window — no need to reset the event to fix a typo
- PDF reports (landscape) include:
  - a summary table per session, sorted by total weight
  - an individual page per person, per session
  - a final **combined ranking across all sessions**, where each
    person-per-session is its own ranked row
- Export / import an event as a JSON file
- Automatic backups on every save (`~/FescherfrennData/backups`)
- Built-in multilingual user manual (**Help** button)
- All translatable strings live in `translations.json` — translations can be
  fixed or expanded without rebuilding

---

## Running from source

Requires **Python 3.9+** and the following companion files in the same folder:

- `translations.json` (app UI strings)
- `manual_translations.json` (PDF manual strings, used by `generate_manuals.py`)
- `logo.png` (UI logo)
- `logo.ico` (Windows app icon, optional)

```bash
pip install tkcalendar reportlab
python fescherfrenn.py
```

`tkinter` ships with the standard Python installer on Windows and macOS. On
Linux you may need to install it separately (e.g. `sudo apt install python3-tk`).

---

## Building the Windows executable

The application is distributed as a standalone build produced with
[PyInstaller](https://pyinstaller.org/).

```bash
pip install pyinstaller
pyinstaller --onedir --windowed --name Fescherfrenn ^
  --icon logo.ico ^
  --add-data "logo.png;." ^
  --add-data "logo.ico;." ^
  --add-data "translations.json;." ^
  --add-data "manual_translations.json;." ^
  --hidden-import babel.numbers ^
  fescherfrenn.py
```

Notes:

- `--onedir` (instead of `--onefile`) gives a **much faster startup**, because
  the app does not unpack itself to a temp folder on every launch. Distribute
  the resulting `dist/Fescherfrenn` folder as a ZIP file or a release asset.
- `--hidden-import babel.numbers` is needed because `tkcalendar` depends on it.
- On macOS/Linux, replace the `;` in `--add-data` arguments with `:`.

---

## Workflow

1. Enter the event name, location and date. These lock once you start
   managing participants.
2. Click **Manage Participants** to add the competitors — typically you load
   the full roster ahead of the event.
3. Still in the manager, with the desired **Manche** selected in the main
   screen drop-down, move participants from the roster into the session.
4. Back on the main screen, with the desired Manche still selected, log
   catches as they come in (weight in grams; length and fish type optional).
5. After each session, switch the Manche drop-down to the next one and
   repeat.
6. Use **Edit Catches** to correct an erroneous entry.
7. When the event is over (including the Final), click **Generate Report**.

---

## Data and backups

- Each event is stored in its own folder named `YYYYMMDD_EventName`, containing
  a JSON file with the same name.
- Every save also writes a timestamped backup to
  `~/FescherfrennData/backups`.
- Errors are logged to `fescherfrenn.log` next to the application.
- Old v1.x events open without issue: catches recorded in the previous flat
  schema are folded into Manche 1.

---

## Repository contents

| File | Purpose |
|------|---------|
| `fescherfrenn.py` | The main application |
| `translations.json` | UI strings in all four languages |
| `generate_manuals.py` | Stand-alone script that exports the user manual as PDF in all four languages |
| `manual_translations.json` | Manual strings for the above |
| `logo.png` | UI logo (provide your own) |
| `logo.ico` | Windows app icon (optional) |
| `LICENSE` | MIT licence |

---

## Changelog

### v2.0
- **Competition structure of 3 Manches + Final.** A drop-down on the main
  screen selects the active session; the live rankings, catch log and
  participants list filter to that session.
- **Manage Participants window** with separate panes for the full roster and
  the participants assigned to the current session. Add, edit, rename and
  remove from either side; selection-and-button rather than drag-and-drop.
- **Edit Catches window** to correct or delete recorded catches without
  resetting the event.
- **Combined ranking across all sessions** appended to the PDF report. Each
  person-per-session is a separate row; the table is one pooled list sorted by
  total weight.
- **Report layout** moved to landscape with wider columns, header shading,
  right-aligned numeric columns and per-session summary blocks.
- **Translations now live in `translations.json`** rather than inside the
  source, which makes the source file substantially smaller and lets the
  translations be edited without rebuilding.
- The `.json` data files use UTF-8 with native characters (no `\u00e9`-style
  escapes), so they are easier to read and edit by hand.

### v1.2
- Weight unit changed from kilograms to grams throughout the interface and
  the PDF reports. Note: event files created with v1.1 stored weights in
  kilograms and are **not** automatically converted — start new events with
  v1.2 or later.
- Fixed: participant category (Master, Lady, Veteran, …) now appears
  correctly in reports in every language.
- Corrected the copyright/footer year to 2010.

### v1.1
- Participant club / category / remark fields, multilingual manual,
  export/import, automatic backups, per-event folders.

---

## License

This project is released under the [MIT License](LICENSE).

---

## Contact

Robert Androvics — fescherfrenn@outlook.com
