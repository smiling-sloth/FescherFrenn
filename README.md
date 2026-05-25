# Fëscherfrënn Stengefort — Fishing Competition Register

A desktop application for managing fishing competitions for **Fëscherfrënn
Stengefort**: maintaining a roster of participants, assigning them to each
round of the competition, logging catches in real time, generating result
reports, and **issuing invoices**.

It is built with a deliberately simple, large-font interface so that it can be
operated by non-technical users during a live event.

- **Languages:** English, French, German, Luxembourgish (invoices are French)
- **Platform:** Windows (primary), also runs on macOS and Linux from source
- **Version:** 3.0
- **License:** MIT

---

## Features

- Single-screen workflow with a round selector
  (**Round 1 / 2 / 3 / Final**, localised per language)
- Two-panel live rankings: current round + overall pooled standings
- Ranking categories, in order: Total Weight, Most Catches, Longest Fish,
  Heaviest Fish (Longest/Heaviest greyed out when length/type tracking is off)
- Optional length & type tracking (event-level toggle, locks once the event
  is locked). When enabled, num-catches is locked to 1 per row.
- Manage Participants window with full roster on the left and the round's
  assigned participants on the right
- Edit Catches window for in-event corrections
- **Round-scoped PDF reports** with a settings panel (Event Summary always
  on; Individual reports and Combined Ranking optional; Combined only on
  Final). Portrait when length/type tracking is off, landscape when on.

### New in v3.0

- **Invoicing module**:
  - Invoice Manager (New / Edit / Reprint / Delete) per event
  - Choose Club (distinct clubs of assigned participants) or Individual
    (true individuals first, then a non-selectable separator, then every
    other assigned participant)
  - Quantity suggested automatically (sum of round assignments) and editable
  - Invoice number auto-assigned `PREFIX-NN-YYYY`, read-only on the form,
    starts from a value set on the first invoice of the event
  - French A4 PDF matching the club's invoice template; supports an
    optional `watermark.png` (~480×480, 12% opacity, centred — skipped
    silently if absent)
  - Invoices saved to `{event_folder}/invoices/`
- **Settings dialog** (`config.json`): invoice prefix, issuer details, bank,
  IBAN, payment terms. Editable in-app, with validation, or by hand.
- **Extended in-app Help** in English (other-language translations planned
  for a follow-up release).
- **Num-catches lock**: when length/type is enabled, num-catches is forced
  to 1 in both Log Catch and Edit Catches.

---

## Running from source

Requires **Python 3.9+** and these companion files in the same folder:

- `translations.json`, `manual_translations.json`, `config.json`
- `logo.png` (optional `logo.ico` on Windows, optional `watermark.png` on
  invoices)

```bash
pip install tkcalendar reportlab
python fescherfrenn.py
```

`tkinter` ships with the standard Python installer on Windows and macOS. On
Linux you may need `sudo apt install python3-tk`.

---

## Building the executables

Builds are produced automatically by GitHub Actions
(`.github/workflows/FF-build-release.yml`). Pushing a tag such as `v3.0`
builds the Windows `.exe` and macOS `.app` and drafts a release with both
attached. **Update the workflow once for v3.0 to bundle the new
`config.json`:** add `--add-data "config.json;."` (or `:`) alongside the
other `--add-data` lines.

To build manually with PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onedir --windowed --name Fescherfrenn ^
  --icon logo.ico ^
  --add-data "logo.png;." ^
  --add-data "translations.json;." ^
  --add-data "manual_translations.json;." ^
  --add-data "config.json;." ^
  --hidden-import babel.numbers ^
  fescherfrenn.py
```

(On macOS/Linux, `;` becomes `:` in `--add-data` and drop `--icon`.)

---

## Workflow

1. Enter event name, location, date. Tick **Record fish length & type** if
   you want to track that detail. Open **Manage Participants** — event
   details lock here.
2. Move participants from the roster into the relevant rounds.
3. Log catches per round, generate per-round reports as you go.
4. Use **Edit Catches** to fix any erroneous entry.
5. On the Final, enable the optional report sections you want.
6. Click **Invoices** to issue invoices (per club or per individual).

Output naming:
- Reports: `YYYYMMDD_Event_manche1.pdf` … `_final.pdf`
- Invoices: `YYYYMMDD_Event/invoices/PREFIX-NN-YYYY.pdf`

---

## Changelog

### v3.0
- Invoicing module: Manager + Form + French A4 PDF with optional watermark
  support; per-event invoice numbering; Club / Individual recipients;
  automatic quantity suggestion (editable).
- Application Settings (`config.json`) for issuer details, bank, IBAN,
  invoice prefix and payment terms; in-app Settings dialog with validation.
- Num-catches locked to 1 when length/type tracking is enabled.
- Extended in-app Help in English; other languages flagged for a follow-up.

### v2.2
- Fixed an invisible-button bug in Edit Catches and Manage Participants
  (Tkinter pack ordering).
- Event-level optional length & type tracking with portrait/landscape
  reports.
- Overall standings panel pooled across all rounds.
- "Manche" localised: Round (EN), Manche (FR), Runde (DE), Manche (LB).
- Move-not-copy in the manager.
- Copyright line as a running year span with the organisation name.

### v2.1
- Round-scoped reports, Report Settings panel, per-round filenames,
  repeating table headers on long tables.

### v2.0
- 3 rounds + Final structure, Manage Participants window, Edit Catches
  window, combined ranking in the PDF, landscape report layout,
  translations extracted to `translations.json`.

### v1.2
- Weight unit kg -> g, category display fix in reports, copyright year fix.

### v1.1
- Participant club / category / remark fields, multilingual manual,
  export/import, automatic backups, per-event folders.

---

## License

Released under the [MIT License](LICENSE).

## Contact

Robert Androvics — fescherfrenn@outlook.com
