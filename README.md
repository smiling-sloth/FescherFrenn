# Fëscherfrënn Stengefort — Fishing Competition Register

A desktop application for registering participants, logging catches, and generating
result reports for the fishing competitions of **Fëscherfrënn Stengefort**.

It is built with a deliberately simple, large-font interface so that it can be
operated comfortably by non-technical users during a live event.

- **Languages:** English, French, German, Luxembourgish
- **Platform:** Windows (primary), also runs on macOS/Linux from source
- **Version:** 1.2

---

## Features

- Single-screen workflow: event details, catch logging, and live rankings on one page
- Participant records with optional **club**, **category** (Senior, Master, Veteran,
  Lady, U20, U15, U10) and **remark**
- Catch logging with weight, number of catches, length and fish type
- Live rankings (total weight, longest fish, heaviest fish, most catches)
- PDF report generation: event summary table plus an individual page per participant
- Export / import an event as a JSON file
- Automatic backups on every save (`~/FescherfrennData/backups`)
- Built-in multilingual user manual (**Help** button)

---

## Screenshots

_Add screenshots here once the repository is public, e.g.:_

```
docs/screenshot-main.png
docs/screenshot-report.png
```

---

## Running from source

Requires **Python 3.9+**.

```bash
pip install tkcalendar reportlab
python fescherfrenn.py
```

`tkinter` ships with the standard Python installer on Windows and macOS. On Linux you
may need to install it separately (e.g. `sudo apt install python3-tk`).

Place `logo.png` (UI logo) and, optionally, `logo.ico` (Windows app icon) in the same
folder as the script.

---

## Building the Windows executable

The application is distributed as a standalone `.exe` built with
[PyInstaller](https://pyinstaller.org/).

```bash
pip install pyinstaller
pyinstaller --onedir --windowed --name Fescherfrenn ^
  --icon logo.ico ^
  --add-data "logo.png;." ^
  --add-data "logo.ico;." ^
  --hidden-import babel.numbers ^
  fescherfrenn.py
```

Notes:

- `--onedir` (instead of `--onefile`) gives a **much faster startup**, because the
  app does not have to unpack itself to a temp folder on every launch. The trade-off
  is that the program is a folder rather than a single file — distribute it as a ZIP.
- `--hidden-import babel.numbers` is needed because `tkcalendar` depends on it.
- On macOS/Linux, replace the `;` in `--add-data` with `:`.

---

## Data and backups

- Each event is stored in its own folder named `YYYYMMDD_EventName`, containing a
  JSON file of the same name.
- Every save also writes a timestamped backup to `~/FescherfrennData/backups`.
- Errors are logged to `fescherfrenn.log` next to the application.

---

## Repository contents

| File | Purpose |
|------|---------|
| `fescherfrenn.py` | The main application |
| `generate_manuals.py` | Stand-alone script that exports the user manual as PDF in all four languages |
| `logo.png` | UI logo (not included — add your own) |
| `logo.ico` | Windows application icon (optional) |

---

## Changelog

### v1.2
- **Weight unit changed from kilograms to grams** throughout the interface and the
  PDF reports. Note: event files created with v1.1 stored weights in kilograms and
  are **not** automatically converted — start new events with v1.2.
- **Fixed:** participant category (Master, Lady, Veteran, …) now appears correctly in
  reports in every language. Previously, only categories whose name happened to be
  identical across languages (U10/U15/U20) were saved and displayed.
- Corrected the copyright/footer year to **2010**.
- Internal cleanup: weight formatting consolidated into a single helper.

### v1.1
- Participant club / category / remark fields, multilingual manual, export/import,
  automatic backups, per-event folders.

---

## Roadmap (v2.0)

Planned restructuring and features:

- Translation strings moved out of the source file for a smaller, faster-starting app
- Competition structure of **3 manches + a final**, selectable from a drop-down
- A dedicated participant-management window (add / edit / remove) feeding a per-manche
  selection window
- Editable catch records (correct an erroneous entry without restarting)
- Improved report layout for longer names, plus a combined end-of-competition
  ranking across all four sessions

---

## License

No license file is included yet. An **OSI-approved open-source license** (for example
MIT or GPL-3.0) is required before applying for free code signing through
[SignPath Foundation](https://signpath.org/) or [OSSign](https://ossign.org/).
Add a `LICENSE` file and update this section accordingly.

---

## Contact

Robert Androvics — fescherfrenn@outlook.com
