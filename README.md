# AeroBooks Online

CFI invoicing for independent instructors and flight schools. Sign-in, per-person (or per-school) books, invoices, hours, expenses.

The original desktop AeroBooks program is unchanged. Restore a desktop backup zip in **Settings → Data** after you sign in.

## Put it online (Streamlit Community Cloud)

This repo is set up for [share.streamlit.io](https://share.streamlit.io), the same way as Range Wall Architect.

1. Open [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. **Create app** → **Yup, I have an app**.
3. Repository: `HaVoKzzX/aerobooks-online` · Branch: `main` · Main file: `streamlit_app.py`.
4. Optional: set the app URL to `aerobooks-online`.
5. **Advanced settings**
   - Python version: **3.12**
   - **Secrets** — paste:

```toml
AEROBOOKS_DATA_KEY = "replace-with-a-long-random-passphrase"
AEROBOOKS_ADMIN_USERNAME = "admin"
AEROBOOKS_ADMIN_PASSWORD = "change-me-8-chars-min"
AEROBOOKS_ADMIN_NAME = "Your Name"
```

6. **Deploy**.

Sign in with the admin username and password from Secrets. Instructors request access; you approve them. Restore a desktop AeroBooks backup under **Settings → Data**.

The live app is phone-friendly (stacked cards, large tap targets, hamburger nav).

Community Cloud can reboot the server and wipe local files. After you have real books in the app, download a backup zip from Settings and keep it. If the app resets, sign in and restore that zip.

## Run it locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Or double-click `Start Streamlit.bat`. Open **http://127.0.0.1:8501**.

## Accounts

| Role | How they get in | What they see |
|---|---|---|
| **Administrator** (you) | Created from Streamlit secrets (Cloud) or first-run setup (local) | Approve or reject account requests, disable users, reset passwords |
| **Independent instructor** | Requests access; you approve | Private students, hours, invoices, expenses |
| **Flight school manager** | Requests access; you approve | School-wide books, plus instructor logins they create themselves |
| **School instructor** | Manager creates username/password | Only *their* students. Invoice **business name** is locked to the school |

## Switch from desktop AeroBooks

Backups are the same zip (`AeroBooks-backup-*.zip`).

1. In desktop AeroBooks, save a backup (or use `Documents\AeroBooks Backups`).
2. Sign in to the Streamlit app.
3. **Settings → Data** → upload that zip.

A backup you download from the online app also restores in the original desktop program.

## Encryption

Databases, invoice PDFs, QR codes, and server-side backups are encrypted with AES-256-GCM. On Streamlit Cloud the key is `AEROBOOKS_DATA_KEY` in Secrets — keep that passphrase. If you change it, old files cannot be decrypted.

## Data (local runs)

| What | Location |
|---|---|
| Logins | `data/auth.db.enc` |
| Each instructor or school | `data/tenants/<id>/` |
| Encryption key (Windows) | `data/master.key.dpapi` |

Do not commit the `data/` folder. It is gitignored.
