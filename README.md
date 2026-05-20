# Fëscherfrënn Stengefort — Fishing Competition Register

A desktop application for managing fishing competitions for **Fëscherfrënn
Stengefort**: maintaining a roster of participants, assigning them to each
round of the competition, logging catches in real time, and generating
result reports.

It is built with a deliberately simple, large-font interface so that it can be
operated by non-technical users during a live event.

- **Languages:** English, French, German, Luxembourgish
- **Platform:** Windows (primary), also runs on macOS and Linux from source
- **Version:** 2.2
- **License:** MIT

---

## Features

- Single-screen workflow with a round selector
  (**Round 1 / 2 / 3 / Final**, localised per language)
- Live rankings shown in two panels: the **current round** on the left and the
  **overall standings across all rounds** (pooled per participant) on the right
- Ranking categories, in order: Total Weight, Most Catches, Longest Fish,
  Heaviest Fish
- **Optional length & type tracking** (event-level setting, off by default).
  When off, the length/type inputs are locked, the Longest/Heaviest rankings
  are shown greyed out and not counted, and the reports use portrait layout.
  When on, the reports switch to landscape and include the extra columns.
- Pre-load the full **competition roster** with each participant's
  optional club, category (Senior, Master, Veteran, Lady, U20, U15, U10) and
  remark, then assign them to whichever rounds they actually fish
- Manage Participants window: add, edit, rename and remove. Names already
  assigned to the current round are hidden from the roster list, so each
  person is assigned once per round.
- Edit Catches window to correct or delete a recorded catch (weight, count,
  and — when tracked — length and type; participant and time stay fixed)
- **Round-scoped PDF reports** with a settings panel:
  - Event Summary for the selected round (always included)
  - Individual participant pages (optional)
  - Combined Ranking across all rounds (optional, Final only)
- Per-round output filenames, so each round's report is preserved
- Export / import an event as a JSON file
- Automatic backups on every save (`~/FescherfrennData/backups`)
- Built-in multilingual user manual (**Help** button)
- All translatable strings live in `translations.json`

---

## Running from source

Requires **Python 3.9+** and these companion files in the same folder:

- `translations.json`, `manual_translations.json`
- `logo.png` (optional `logo.ico` for the Windows icon)

```bash
pip install tkcalendar reportlab
python fescherfrenn.py
```

`tkinter` ships with the standard Python installer on Windows and macOS. On
Linux you may need `sudo apt install python3-tk`.

---

## Building the executables

Builds are produced automatically by GitHub Actions
(`.github/workflows/FF-build-release.yml`). Pushing a tag such as `v2.2`
builds the Windows `.exe` and macOS `.app`, then drafts a release with both
attached. To build manually with PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onedir --windowed --name Fescherfrenn ^
  --icon logo.ico ^
  --add-data "logo.png;." ^
  --add-data "translations.json;." ^
  --add-data "manual_translations.json;." ^
  --hidden-import babel.numbers ^
  fescherfrenn.py
```

(`--onedir` for fast startup; on macOS/Linux replace `;` with `:` and drop
`--icon logo.ico`.)

---

## Workflow

1. Enter the event name, location and date. Decide whether to tick
   **Record fish length & type** — this is fixed once the event locks.
2. Click **Manage Participants** to load the roster (event details lock here).
3. With a round selected, move participants from the roster into that round.
4. Log catches for the selected round (weight in grams; length/type only if
   enabled).
5. After each round, **Generate Report** for a single-round PDF; switch the
   round drop-down and repeat.
6. Use **Edit Catches** to fix an erroneous entry.
7. On the Final, optionally tick **Combined Ranking - All Rounds** and/or
   **Individual Reports**, then generate the wrap-up PDF.

Output filenames: `YYYYMMDD_Event_manche1.pdf` … `_final.pdf`.

---

## Data and backups

- Each event lives in its own `YYYYMMDD_EventName` folder (JSON + PDFs).
- Every save also writes a timestamped backup to `~/FescherfrennData/backups`.
- Errors are logged to `fescherfrenn.log`.
- Old v1.x events still open (their catches fold into Round 1).

---

## Changelog

### v2.2
- **Fixed:** Edit Catches, and the Manage Participants buttons, were
  effectively invisible due to a Tkinter pack-ordering issue (an expanding
  widget was packed before the button bar). Catches are now editable.
- **Optional length & type** tracking as an event-level setting (default off):
  locks the inputs, greys out and excludes Longest/Heaviest rankings, and
  switches reports between portrait (off) and landscape (on).
- **Overall standings panel** added next to the per-round live rankings,
  pooled per participant across all rounds.
- Ranking order standardised to Total Weight -> Most Catches -> Longest Fish
  -> Heaviest Fish, in both the app and the reports.
- **"Manche" localised**: Round (EN), Manche (FR), Runde (DE), Manche (LB),
  everywhere including reports.
- Assigning a participant to a round now hides them from the roster list
  (one assignment per round) instead of allowing repeats.
- Removed the duplicate Remove button in Manage Participants; fixed the
  unlabelled/clipped Close button.
- Edit / Log Catch buttons swapped per request.
- Version number shown bottom-left in the app (not in reports).
- Copyright line corrected to a running span with the organisation name:
  `© 2025 - <current year> Fëscherfrënn Stengefort 2010`, app and reports.
- French: "compétition" -> "concours" throughout.

### v2.1
- Round-scoped reports; Report Settings panel (Individual / Combined toggles);
  per-round output filenames; repeating table headers on long tables.

### v2.0
- 3 Rounds + Final structure; Manage Participants window; Edit Catches window;
  combined ranking in the PDF; landscape report layout; translations extracted
  to `translations.json`.

### v1.2
- Weight unit kg -> g; category display fixed in reports; copyright year fix.

### v1.1
- Participant club / category / remark fields, multilingual manual,
  export/import, automatic backups, per-event folders.

---

## License

Released under the [MIT License](LICENSE).

## Contact

Robert Androvics — fescherfrenn@outlook.com
