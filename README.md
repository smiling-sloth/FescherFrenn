# Fëscherfrënn Stengefort — Fishing Competition Register

A desktop application for managing fishing competitions for **Fëscherfrënn
Stengefort**: maintaining a roster of participants, assigning them to each
session of the competition, logging catches in real time, and generating
result reports.

It is built with a deliberately simple, large-font interface so that it can be
operated by non-technical users during a live event.

- **Languages:** English, French, German, Luxembourgish
- **Platform:** Windows (primary), also runs on macOS and Linux from source
- **Version:** 2.1
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
- **Manche-scoped PDF reports**, with a settings panel that lets you choose
  what to include:
  - the Event Summary for the selected session (always included)
  - the participant-by-participant detail pages (optional)
  - the Combined Ranking across all four sessions (optional, only available on
    the Final)
- Each session's report is saved to its own PDF, so the per-manche results
  produced on the day are preserved alongside the final wrap-up
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
5. After each Manche, click **Generate Report** to produce a single-session
   PDF; switch the drop-down to the next Manche and repeat.
6. Use **Edit Catches** to correct an erroneous entry.
7. When the Final is over, switch to **Final**, tick **Combined Ranking - All
   Sessions** (and **Individual Reports** if you want each participant's own
   page), then **Generate Report** to produce the wrap-up PDF.

Generated PDFs are named after the session:

```
20260510_Stengefort_Open_manche1.pdf
20260510_Stengefort_Open_manche2.pdf
20260510_Stengefort_Open_manche3.pdf
20260510_Stengefort_Open_final.pdf
```

so a Final report does not overwrite the earlier per-manche files.

---

## Data and backups

- Each event is stored in its own folder named `YYYYMMDD_EventName`, containing
  a JSON file with the same name and the generated PDFs.
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

### v2.1
- **Manche-scoped reports.** Generating the report from Manche 1, 2 or 3
  produces a PDF for just that session. The Final's report covers the Final
  alone unless additional sections are explicitly enabled.
- **Report Settings panel** on the main screen with two toggles:
  *Individual Reports* (off by default) and *Combined Ranking - All Sessions*
  (off by default, available only when the Final is selected). The Event
  Summary is always included.
- **Per-manche output filenames** (`_manche1.pdf`, `_manche2.pdf`,
  `_manche3.pdf`, `_final.pdf`), so the report produced after each session is
  preserved next to the others rather than overwritten.
- **`repeatRows=1`** added to long tables so the column headers reappear on
  every continuation page (matters at 30 participants per session).
- Section order inside a Final report when all options are enabled:
  Event Summary → Combined Ranking → Individual Reports.

### v2.0
- Competition structure of 3 Manches + Final, with a drop-down on the main
  screen that filters the live rankings, the catch log and the participants
  list to the active session.
- Manage Participants window with separate panes for the full roster and the
  participants assigned to the current session. Add, edit, rename and remove
  from either side; selection-and-button rather than drag-and-drop.
- Edit Catches window to correct or delete recorded catches without resetting
  the event.
- Combined ranking across all sessions appended to the PDF report. Each
  person-per-session is a separate row; the table is one pooled list sorted by
  total weight.
- Report layout moved to landscape with wider columns, header shading,
  right-aligned numeric columns and per-session summary blocks.
- Translations now live in `translations.json` rather than inside the source,
  which makes the source file substantially smaller and lets the translations
  be edited without rebuilding.
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
