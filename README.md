# WhatsApp Workspace — Phase 1 Foundation

A Windows desktop workspace built with **Python + Eel + HTML/CSS/JavaScript + SQLite**. It provides local group/member records, CSV import/export, a review-first screen OCR workflow, local audit history, and visible operator-supervised WhatsApp Web GUI helpers.

> **Important:** This is an operator-assistance tool, not an unattended WhatsApp bot. It does not bypass WhatsApp security controls, hide automation, send bulk messages, or harvest participant data in the background. Use it only with an account you control and for groups and participant data you are authorized to manage. Obtain any consent required for adding people or processing their details.

## Repository layout

```text
WhatsappAutomation/
└── py.26.09.21/
    └── theme/
        └── WhatsappAutomation_Basic/
            └── User/
                ├── asset/       # SVG and image assets
                ├── component/   # Reusable HTML components
                ├── core/        # Configuration and logging
                ├── css/         # Component CSS + application design system
                ├── data/        # Non-secret settings and defaults
                ├── db/          # SQLite schema and repository layer
                ├── js/          # Modular frontend controllers
                ├── py/          # Python services and Eel API
                ├── Runtime/     # Local logs and runtime files
                ├── template/    # HTML pages
                ├── tests/       # unittest coverage
                ├── web/         # Only index.html (Eel entry point)
                └── main.py      # Desktop entry point
```

## Phase 1 features implemented

- Premium dark-first dashboard, responsive sidebar navigation, theme toggle, reusable components and toast feedback.
- SQLite database with schema version metadata, foreign keys, WAL mode, indexes and repository methods.
- Group directory for local group records (explicitly separate from creating a real WhatsApp group).
- Member directory with CSV import/export, phone validation, deduplication and consent status fields.
- Multi-page visible-screen OCR capture for an operator-opened participant list. The operator manually scrolls between screenshots; candidates from multiple pages are deduplicated in a short-lived in-memory review session.
- Name-only observations and visible phone numbers are stored in a separate `member_observations` table after explicit review. They are not treated as consented contacts and are exported separately from the contact directory.
- Session-scoped operator authorization for GUI group actions and OCR capture/save flows.
- Visible WhatsApp Web launch, OCR-label-driven group creation and add-members sequences, with per-run confirmation and a 20-participant cap.
- Local audit events, automation run records, rotating logs and settings validation.
- Unit tests for contact parsing, SQLite repositories, authorization gates, OCR parsing and GUI input validation.

## Windows setup

1. Install Python 3.10 or newer and Google Chrome.
2. (Optional, for OCR and GUI automation) Install Tesseract OCR for Windows. Note the executable path, commonly `C:\Program Files\Tesseract-OCR\tesseract.exe`.
3. Open a terminal in the repository root and create a virtual environment:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Launch the app:

   ```powershell
   $app = "WhatsappAutomation\py.26.09.21\theme\WhatsappAutomation_Basic\User"
   python "$app\main.py"
   ```

5. Configure the Tesseract path under **Settings** when it is not on `PATH`.

The desktop window uses Chrome through Eel. WhatsApp login is performed manually in the visible browser window. The application does not ask for your WhatsApp password or store QR/session information.

## CSV format

A CSV requires a `phone` column. `name` and `consent` are optional. Consent is marked `granted` only for affirmative values such as `yes`, `true`, `1` or `approved`; other values remain `unknown`.

```csv
phone,name,consent
+919876543210,Aman,yes
+919812345678,Neha,no
```

The app validates international-style phone strings and skips invalid or duplicate rows. A contact marked `unknown` is not proof of consent and must not be treated as opt-in.

## WhatsApp GUI workflow

1. Open **GUI automation** and select **Open WhatsApp Web**.
2. Sign in manually and navigate to the intended screen.
3. Read the authorization statement and explicitly check it.
4. Enter the group name and participant phone numbers, review the confirmation dialog, then start the sequence.
5. Keep the WhatsApp browser visible and do not use the mouse/keyboard while PyAutoGUI is operating.
6. Verify the outcome in WhatsApp. The app records that a sequence was submitted; it cannot guarantee that WhatsApp accepted the action.

For adding members to an existing group, open that specific group in WhatsApp first. The add-members action operates on the currently open group, so confirm the group identity before starting.

### Multi-page participant OCR workflow

1. Open the exact WhatsApp group you are authorized to review and navigate to its participant list.
2. In **Members**, enter the group label, check the authorization statement, then start a capture session.
3. Click **Capture visible page**. The app reads the current visible screen only; the screenshot stays in memory and is not written to disk.
4. Review the candidates. Manually scroll the participant list in WhatsApp Web, then click **Capture visible page** again. Repeat for the next visible section. Duplicate visible names/numbers are merged across pages in this session.
5. Select the observations you are permitted to retain and click **Save selected observations**. Saved group observations go into a separate table; they are not added to the consented contact directory.
6. Use **Export observations CSV** to export only the operator-reviewed group observations. **Export contacts CSV** remains a separate export for manually imported/consent-tracked contacts.

The capture session is held in memory for up to 15 minutes and is discarded when saved or manually discarded. No automatic scrolling, hidden browser scraping, background collection, or screenshot retention is performed. Names-only observations are possible when WhatsApp does not visibly show a phone number. OCR can confuse similarly named participants or misread text; manually verify the preview before saving.

### Current GUI limitations

WhatsApp Web changes its DOM, labels and visual layout over time and may use different languages. The current driver uses on-screen OCR labels rather than stable accessibility selectors. If a control cannot be located, the run stops with an error instead of guessing a coordinate. The group creation/add-members sequence must be verified on the exact installed WhatsApp Web version and display scale before real use. These actions are not marked as successful until the operator verifies them in WhatsApp.

## Tests

From the application directory, run the standard-library test suite:

```powershell
$app = "WhatsappAutomation\py.26.09.21\theme\WhatsappAutomation_Basic\User"
$env:PYTHONPATH = (Resolve-Path $app).Path
python -m unittest discover -s "$app\tests" -v
```

No WhatsApp login, network access or desktop interaction is needed for the unit tests.

## Security and privacy notes

- SQLite database and audit logs remain local to the Windows user profile/repository runtime.
- The app does not persist screenshots, browser cookies, QR codes or credentials.
- OCR candidate rows are preview-only until an operator explicitly approves saving.
- Imported records default to `unknown` consent unless the CSV contains an affirmative consent field.
- Sensitive actions require a fresh UI confirmation and a session-scoped authorization acknowledgement.
- PyAutoGUI's fail-safe is enabled; moving the mouse to the top-left corner can abort a GUI run.
- Do not use this application for unsolicited group invitations, unsolicited outreach, covert collection or processing of data without the required authorization.

## Architecture and scale roadmap

**Phase 1** is a single-user Windows desktop application with a local SQLite database. The prompt's future user/hour targets are aspirational architecture targets, not measured capacity or guarantees. They cannot be met by this local application alone.

- **Phase 2:** introduce an authenticated FastAPI service, server-side authorization, MySQL/PostgreSQL, background jobs and telemetry if multi-user operation is required.
- **Phase 3:** evaluate tenant isolation, Redis, queue workers, observability, centralized secrets management and horizontal scaling against measured traffic.
- **Phase 4:** only if justified by actual demand, design multi-region event-driven services, replicated data and disaster recovery.

Do not attempt to reach global scale by adding threads to a desktop GUI automation process. WhatsApp GUI automation itself remains a single visible desktop session and is not a horizontally scalable workload.

## Build a Windows executable

EXE packaging is not yet part of the verified Phase 1 build. A future packaging pass should bundle the app's web assets, verify Chrome/Eel startup, handle the Tesseract dependency separately, and test the output on a clean Windows machine. Do not assume a PyInstaller build is production-ready until those checks pass.

## Project status

This branch contains the Phase 1 desktop foundation and operator-controlled multi-page OCR review workflow. Automated unit/compile checks cover parsing, session deduplication, local observation persistence, contact repositories and GUI input validation. Real WhatsApp group creation/add-members flows and OCR accuracy still require manual acceptance testing on a logged-in test account and the exact Windows display configuration.