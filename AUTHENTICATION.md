# Local sign-in and sign-up

The desktop app starts at a local account screen. The first launch offers **Create account**. After the first account is created, the app only offers **Sign in**. A signed-in user can sign out from the top bar.

## Included

- First-run local account registration with full name, email, password and confirmation.
- One local account per workspace in this version; subsequent sign-up attempts are rejected by the backend.
- Email normalization and uniqueness checks.
- Passwords are stored as PBKDF2-HMAC-SHA256 hashes with a random 16-byte salt and 600,000 iterations; plaintext passwords are not stored.
- Five consecutive failed sign-in attempts trigger a 60-second cooldown.
- Python/Eel bridge endpoints require an authenticated in-memory local session.
- Closing the desktop application clears that in-memory session.

## Limitations

This is a **local desktop sign-in gate**, not a hosted identity service. There is no email verification, email-based password recovery, cross-device sync or SQLite database encryption. Anyone with access to the Windows user account and local application data may be able to access the database outside the app.

This version is a single-user local workspace. It does not provide multi-user accounts, per-user data isolation or remote multi-user access. Back up the local SQLite database securely. There is no built-in password reset flow.
