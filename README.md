# Fëscherfrënn Stengefort — Fishing Competition Register

A desktop application for managing fishing competitions for **Fëscherfrënn
Stengefort**: maintaining a roster of participants, assigning them to each
round of the competition, logging catches in real time, generating result
reports, and **issuing invoices**.

It is built with a deliberately simple, large-font interface so that it can be
operated by non-technical users during a live event.

- **Languages:** English, French, German, Luxembourgish (invoices are French)
- **Platform:** Windows (primary), also runs on macOS and Linux from source
- **Version:** 3.11
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
  assigned participants on the right; the Club field is a drop-down of
  every club already entered, so adding the second member of a club picks
  the exact same spelling as the first (typing a new club name is still
  allowed)
- Edit Catches window for in-event corrections
- **Round-scoped PDF reports** with a settings panel (Event Summary always
  on; Individual reports and Combined Ranking optional; Combined only on
  Final). Portrait when length/type tracking is off, landscape when on.
- **Invoicing module** (per event):
  - Invoice Manager (New / Edit / Reprint / Delete)
  - Choose Club (distinct clubs of assigned participants, grouped
    case-insensitively so "FF Stengefort" and "ff stengefort" are
    invoiced as one) or Individual (true individuals first, separator,
    then every other assigned participant). Recipients who have already
    been invoiced are demoted to a final "Already Invoiced" section -
    still pickable for corrective invoices, but visually separated so the
    operator doesn't double-bill by accident.
  - Quantity suggested automatically (sum of round assignments across all
    case-variants of the same club); reduced for clubs whose members
    have already been invoiced individually, with a warning on the form.
    Picking a club or individual that has already been invoiced also
    raises a warning.
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
- `logo.png` (optional `logo.ico` on Windows, optional `logo.icns` on macOS,
  optional `watermark.png` for invoices)

```bash
pip install tkcalendar reportlab
python fescherfrenn.py
```

`tkinter` ships with the standard Python installer on Windows and macOS. On
Linux you may need `sudo apt install python3-tk`.

---

## Building the executables

Builds are produced automatically by GitHub Actions
(`.github/workflows/FF-build-release.yml`). Pushing a tag such as `v3.11`
builds the Windows `.exe` and macOS `.app` and drafts a release with both
attached. The workflow bundles `config.json` and `help.json` already; if you
keep `watermark.png` and `logo.icns` in the repo, add them to the workflow's
`--add-data` loop too.

To build manually with PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onedir --windowed --name Fescherfrenn ^
  --icon logo.ico ^
  --add-data "logo.png;." ^
  --add-data "translations.json;." ^
  --add-data "manual_translations.json;." ^
  --add-data "config.json;." ^
  --add-data "help.json;." ^
  --add-data "watermark.png;." ^
  fescherfrenn.py
```

On macOS/Linux, replace each `;` with `:` in `--add-data`, drop the
`--icon logo.ico` flag, and add `--add-data "logo.icns:."` if you have a
macOS icon file:

```bash
pyinstaller --onedir --windowed --name Fescherfrenn \
  --add-data "logo.png:." \
  --add-data "translations.json:." \
  --add-data "manual_translations.json:." \
  --add-data "config.json:." \
  --add-data "help.json:." \
  --add-data "watermark.png:." \
  --add-data "logo.icns:." \
  fescherfrenn.py
```

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

### v3.11
- Pop-ups and panels now open at a stable, centred position over the main
  window. Previously a dialog (e.g. the participant editor) could drift to a
  different part of the screen depending on the window behind it.
- Invoices: the header/footer colour is configurable in Settings (same
  palette as the report highlight colours, plus "No colour"), applied to both
  banners, with dark text for readability. Cross-event (config.json).
- Invalid keystrokes (e.g. a dot in an integer-only field) now give a short
  system beep, app-wide.
- Event configuration: the round-count and max-participants fields show a
  small remark with the current app-wide ceiling from Settings.
- New Settings value: maximum participants per round (default 100, capped at
  999), mirroring the maximum-rounds ceiling. The per-event field blocks
  anything above it as you type.
- New Settings section "Report & event defaults": set the starting value for
  new events of Record fish length & type, Highlight finalists (and its
  colour), Generate individual reports, and Combined ranking. The combined
  ranking default is only enabled when individual reports default is on.



### v3.10.2 (configurable round ceiling)
- New "Competition defaults" setting: the maximum number of rounds an event
  may use is now an app-wide value in Settings (saved in config.json, shared
  across events, default 12, hard-capped at 99). The per-event default stays
  at 3 in the event configuration.
- The round-count field in the event configuration now blocks, as you type,
  anything above the configured ceiling (e.g. with a ceiling of 5 you cannot
  type 6 or 55) - digits only, no dots or commas.

### v3.10.1 (fixes)
- Finalist qualification: weight totals are now rounded before ranking, so
  anglers with equal totals are correctly detected as tied. Previously,
  floating-point noise from summing decimal weights (e.g. 333.33 + 666.67)
  could split a genuine tie and skip the "who proceeds" prompt at the
  proceeding boundary.
- Export no longer triggers the operating system's "file already exists,
  replace?" confirmation (the app saves to that location continuously
  anyway).

### v3.10 (dynamic number of rounds)
- The number of rounds is now configurable (1-12, excluding the final),
  not fixed at 3. Set it in the event configuration before locking the
  event; the round selector, rankings, qualification, reports and invoices
  all follow the chosen count automatically.
- The round count is validated and frozen together with the other config
  values when the event is configured (it cannot change once a roster or
  catches exist). Changing it before locking rebuilds the session set.
- Existing 3-round events open unchanged. Older events are never silently
  truncated: if stored data uses more rounds than the configuration says,
  the count is raised to fit the data.
- Round labels are generated for any count ("Round 1..N" / "Manche 1..N" /
  "Runde 1..N") in all four languages.
- Note: the in-app help/manual still describes earlier versions; a full
  documentation refresh is the remaining part of this milestone.

### v3.9.1 (fixes & invoice polish)
- Invoice footer (payment information) now repeats on every page, like the
  header; previously it appeared only on the last page.
- Every invoice shows a page number ("1 / 1", "1 / 2", "2 / 2", ...),
  including single-page invoices.
- Export: the Save-As dialog now defaults to the event's own folder (not
  Downloads), and the confirmation shows the full path including that
  folder.
- Catch log: adding a name that is not in the participant list now says so
  ("not in the participant list") instead of the wrong "already exists";
  a name not added to the current round gets its own clear message.
- Report logo keeps its aspect ratio (rectangular logos are no longer
  squashed into a square). Uploaded logos/watermarks are fitted within a
  size box with aspect ratio preserved - never stretched.
- Invoices now show the event name and location between the client block
  and the line-item table, on every page (previously the event was only
  implied by the description line, which detailed invoices replace).

### v3.9 (Group D - invoicing enhancements)
- Detailed invoice option (checkbox in the invoice form, off by default).
  For an individual it itemises one line per round entered (Round 1,
  Round 2, ..., Final); for a club it lists each member with their round
  count. Line amounts sum to the same total as the simple invoice.
- The detailed breakdown is frozen onto the invoice when saved, so
  reprinting reproduces exactly what was billed even if the roster later
  changes.
- Invoices now paginate cleanly: long member lists flow onto further pages
  with a "CLIENT (continued)" header repeated, and the totals, payment
  terms and the payment-information footer appear once, on the last page.
  Simple one-line invoices look exactly as before.
- The "high quantity" warning on an individual invoice now triggers above
  number-of-rounds + 1 (from the event configuration) instead of a fixed 4.

### v3.8 (Package 3 - event management + branding assets)
- Import Event and Manage Events are merged into a single "Events" panel
  (those two were the real duplicates). It lists every saved event with
  its date, name, invoice count and size on disk, and offers: Open (load
  it), Delete (remove the whole event folder to free space), and Browse...
  (load an event JSON from elsewhere - archives, emailed files).
- Export Event stays a separate button that acts on the CURRENT open event
  (not a list selection): a manual save/checkpoint available any time the
  mandatory fields pass validation. It writes the canonical copy and then
  offers a Save-As so you can place a portable copy anywhere.
- Deletion safeguards: a named confirmation spelling out what will be
  removed; events that contain invoices require typing the event name to
  confirm (financial records get extra friction); the event currently
  open cannot be deleted.
- Report Settings: on the Final, "Highlight finalists" and its colour
  picker are unticked and greyed out automatically (finalists are not
  highlighted on the final's own report); they return to the stored
  setting on any round.
- Settings gains a "Branding & icons" section: upload, replace or remove the
  logo, the invoice watermark and the application icon. Accepts PNG/JPG/JPEG
  up to 5 MB each; images are resized automatically (aspect ratio preserved)
  and saved in the format the app needs (logo.png, watermark.png, logo.ico).
  Oversized files and unsupported types are rejected with a clear message.
  The report/invoice images apply on the next generated PDF; the live window
  icon and main-screen logo refresh when the app is next started.
- Fixed the Export confirmation to show the full (absolute) path, including
  the event's own folder, instead of a relative path.

### v3.7 (Group C - ranking, qualification & reports)
- Qualification engine: computes who proceeds to the final, round by round.
  Within a round, eligible anglers (those who caught at least one fish, and
  not already qualified in an earlier round) are ranked by total weight and
  the top "proceed-to-final" (Xproc) qualify. A round contributes fewer than
  Xproc when fewer eligible anglers caught a fish - empty slots are never
  filled by a zero-catch angler.
- Tie ranking (1224 style): equal totals share a place and the next place
  jumps by the group size (three tied at 5th -> next is 8th).
- Tie for the last proceeding place: a dialog asks the operator to pick
  exactly who proceeds.
- "Suggest finalists" button in the Participants Manager (on the Final
  round) adds all qualifiers to the final's participants as an editable
  suggestion.
- Config integer fields (max per round, proceed-to-final) normalise leading
  zeros on lock ("0004" -> "4").
- Round reports highlight the participants who proceed to the final (never
  on the final's own report), in a readable, print-friendly colour chosen
  from the Report Settings panel (green / yellow / blue / grey / red).
  Highlighting can be switched off.
- Generate Report now asks whether to open the PDF (Yes/No), like invoices.
- New "Open Report" panel lists the report PDFs that exist for the current
  event; double-click or Open to view. No Browse - reports stay within the
  event folder.
- Fixed a doubled word ("Round Round 1") in the tie and round-limit
  messages; both now name the round once.

### v3.6
- Event configuration added (foundation of the new competition rules):
  number of rounds, max participants per round (default 30), and how many
  proceed to the final per round / "Xproc" (default 10). All are validated
  as whole numbers. Number of rounds is shown but fixed at 3 for now -
  making the round count variable is a separate structural change.
- Freeze-on-configure: opening Manage Participants now locks the event AND
  its configuration behind an acknowledged, cancellable confirmation. A
  separate notice appears (and must be acknowledged) if rounds x Xproc
  exceeds max participants per round.
- Roster enforcement: a round cannot exceed its max participants; adding
  past the limit warns and fills only the remaining room.
- Export is blocked unless the event has a name and location (date always
  defaults to today). Closing the app still just closes without saving an
  empty event.

### v3.5
- Import Event now opens a panel listing every event found in the
  application folder, in a two-column grid (date, event name) sorted with
  the most recent first. Double-click a row or use Open to load it; Cancel
  closes the panel; Browse... opens the previous file dialog for events
  stored elsewhere (archives, emailed files, moved copies). The displayed
  date and name are read from inside each event's JSON, so they show exactly
  what was typed - real spaces and any user-entered underscores are kept,
  with no folder-name guesswork.

### v3.4.2
- Invoice PDFs can now be opened from inside the app: double-click an
  invoice in the Invoice Manager to open its PDF with the system viewer.
- After saving an invoice (new or edit) and after a Reprint, the app asks
  whether to open the freshly generated PDF (Yes/No), replacing the plain
  "saved" confirmation.
- If a double-clicked invoice's PDF file is missing on disk (e.g. the event
  was imported on another machine), a hint suggests using Reprint.

### v3.4.1
- Fixed a freeze on macOS caused by button tooltips. Tooltips were borderless
  always-on-top windows positioned over the button; clicking one (instead of
  the button) could freeze the app. Tooltips are now created on hover, shown
  below the widget so they never cover the click target, and dismissed on any
  click.
- The catch-logging participant drop-down now refreshes immediately after a
  catch is logged, so the participant moves to the "Already recorded" section
  without needing to save/reload the event.

### v3.4
- **Critical fix:** invoices created in a brand-new event (one started via
  Reset or first launch, rather than imported) silently failed to save and
  the invoice counter ran away (advancing on every failed attempt). Root
  cause: fresh events were built without an `invoices` list. Every fresh
  event now carries the complete schema, the invoice list is always present,
  and the counter only advances after an invoice is successfully written -
  so a failure never burns a number.
- Unit price set on the first invoice of an event is now remembered and
  suggested on every following invoice (editable each time), the same way
  the quantity is suggested.
- Catch-logging participant drop-down now partitions: participants with no
  catch yet in the current round appear on top, then a separator, then those
  who already have a catch recorded. Both groups alphabetical; all selectable.
- Invoicing an individual for more than 4 sessions is now allowed (e.g. a
  caretaker paying for a minor's rounds); it shows an informational note
  instead of blocking. Quantities below 1 or non-integer are still rejected.

### v3.3
- Invoice picker now partitions already-invoiced recipients into their own
  "Already Invoiced" section at the bottom of the drop-down list, under a
  non-selectable separator. Still pickable (for corrective invoices), but
  visually demoted so the operator does not double-bill by accident.
  Applied to both the Club picker and the Individual picker.
- Picking a club that has already been invoiced raises a warning below the
  form, symmetric with the existing warnings for individuals.
- Edit mode: the invoice currently being edited does not see itself in the
  "Already Invoiced" partition or in any of the cross-warnings.

### v3.2
- When invoicing a club, the suggested quantity is automatically reduced
  by the rounds of any members who have already been invoiced
  individually. The quantity stays editable; a remark below the form
  shows how many members and how many rounds were excluded.
- When invoicing an individual whose club has already been invoiced, a
  remark warns the operator before saving.
- When picking an individual who was already invoiced individually, a
  remark warns about that too.
- Build instructions updated to bundle `watermark.png` and the optional
  macOS `logo.icns`.

### v3.1
- Club name is now picked from a drop-down of every club already entered
  in the roster, in both the Add and Edit Participant forms. Typing a
  brand new club name is still allowed for the first member of a new club.
- Invoice "Club" picker and the suggested quantity for a club invoice are
  now case-insensitive: variants like "FF Stengefort" and "ff stengefort"
  are treated as the same club. The display picks the most-used spelling
  (alphabetical tiebreak).
- Invoice form date picker now opens correctly (modal grab on the manager
  is released while the form is open, restored on close).
- Invoice header shows the full invoice number on its own line under the
  "Numéro de facture" label.
- Issuer legal name in the invoice footer splits onto two lines on
  recognised legal-form suffixes.
- Footer banner shortened; lighter blues used for invoice header and
  footer to reduce toner usage.
- In-app Help redesigned with a left-side section navigator. Content
  fully translated into French, German, and Luxembourgish.

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
