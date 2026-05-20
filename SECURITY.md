# Security Policy

## Supported Versions

Security fixes target the latest public release of Koplyx.

## Reporting a Vulnerability

Please do not open a public issue for a suspected security vulnerability.

Report it privately by opening a GitHub security advisory on the repository when available, or by contacting the maintainer through the repository owner profile.

Useful details:

- Koplyx version and installation method.
- Linux distribution and desktop session.
- Steps to reproduce.
- Impact on clipboard contents, encryption keys, local storage, or autostart/raccourci configuration.

Koplyx stores clipboard history locally and does not provide cloud sync. Clipboard payloads are encrypted locally before being written to SQLite. Since version 0.2.2, newly stored previews are non-sensitive metadata instead of copied text. Since version 0.2.4, real text previews, image thumbnails and file names are decrypted only in memory for the application UI and are not written back to SQLite as plaintext previews. Histories created before 0.2.2 may still contain plaintext previews and should be purged before public/stable testing with real data.

The app may use `xdotool`, `wtype` or `ydotool` to send `Ctrl+V` to the active window for auto-paste. Report any issue that causes clipboard contents, encryption keys, local database contents or unintended paste targets to be exposed.
