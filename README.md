# Fëscherfrënn Stengefort — Fishing Competition Register

A desktop application for managing fishing competitions for **Fëscherfrënn
Stengefort**: maintaining a roster of participants, assigning them to each
round of the competition, logging catches in real time, generating result
reports, and **issuing invoices**.

It is built with a deliberately simple, large-font interface so that it can be
operated by non-technical users during a live event.

- **Languages:** English, French, German, Luxembourgish (invoices are French)
- **Platform:** Windows (primary), also runs on macOS and Linux from source
- **Version:** 3.1
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
  assigned participants on the right; **the Club field is a drop-down of
  every club already entered**, so adding the second member of a club picks
  the exact same spelling as the first (typing a new club name is still
  allowed)
- Edit Catches window for in-event corrections
- **Round-scoped PDF reports** with a settings panel (Event Summary always
  on; Individual reports and Combined Ranking optional; Combined only on
  Final). Portrait when length/type tracking is off, landscape when on.
- **Invoicing module** (per event):
  - Invoice Manager (New / Edit / Reprint / Delete)
  - Choose Club (distinct clubs of assigned participants, **grouped
    case-insensitively** so "FF Stengefort" and "ff stengefort" are
    invoiced as one) or Individual (true individuals first, separator,
    then every other assigned participant)
  - Quantity suggested automatically (sum of round assignments across all
    case-variants of the same club) and editable
  - Invoice number auto-assigned `PREFIX-NN-YYYY`, read-only on the form;
    the invoice header shows the full number on its own line under the
    "Numéro de facture" label
  - French A4 PDF matching the club's invoice template; supports an
    optional `watermark.png` (~480×480, 12% opacity, centred — skipped
    silently if absent)
- **Settings dialog** (`config.json`): invoice prefix, issuer details, bank,
  IBAN, payment terms — editable in-app with validation.
- **Extended in-app Help** with a left-side section navigator, in English,
  French, German, and Luxembourgish.

---

## Running from source

Requires **Python 3.9+** and these companion files in the same folder:

- `translations.json`, `manual_translations.json`, `config.json`, `help.json`
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
(`.github/workflows/FF-build-release.yml`). Pushing a tag such as `v3.1`
builds the Windows `.exe` and macOS `.app` and drafts a release with both
attached. The workflow already bundles `config.json` and `help.json`. To
build manually with PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onedir --windowed --name Fescherfrenn ^
  --icon logo.ico ^
  --add-data "logo.png;." ^
  --add-data "translations.json;." ^
  --add-data "manual_translations.json;." ^
  --add-data "config.json;." ^
  --add-data "help.json;." ^
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

### v3.1
- Club name is now picked from a drop-down of every club already entered in
  the roster, in both the Add and Edit Participant forms. Typing a brand
  new club name is still allowed for the first member of a new club.
- Invoice "Club" picker and the suggested quantity for a club invoice are
  now case-insensitive: variants like "FF Stengefort" and "ff stengefort"
  are treated as the same club. The display picks the most-used spelling
  (alphabetical tiebreak).
- Invoice form date picker now opens correctly (modal grab on the manager
  is released while the form is open, restored on close — kept the form
  free of its own grab so the calendar popup remains visible).
- Invoice header shows the full invoice number on its own line under the
  "Numéro de facture" label.
- Issuer legal name in the invoice footer splits onto two lines on
  recognised legal-form suffixes (a.s.b.l., S.A., S.à r.l., GmbH, …).
  Layout reserves the second row even for short names, keeping both
  footer columns symmetric.
- Footer banner reduced from 200pt to 160pt now that the layout is
  symmetric and predictable.
- Lighter blues used for invoice header and footer to reduce toner usage
  while keeping white text legible.
- In-app Help redesigned with a left-side section navigator and a
  scrollable reader pane on the right. Sections now live in `help.json`.
- Help content fully translated into French, German, and Luxembourgish
  (10 sections each).

### v3.0
- Invoicing module: Manager + Form + French A4 PDF with optional watermark
  support; per-event invoice numbering; Club / Individual recipients;
  automatic quantity suggestion (editable).
- Application Settings (`config.json`) for issuer details, bank, IBAN,
  invoice prefix and payment terms; in-app Settings dialog with validation.
- Num-catches locked to 1 when length/type tracking is enabled.
- Extended in-app Help in English.

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
