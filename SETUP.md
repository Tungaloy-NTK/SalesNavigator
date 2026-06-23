# Tungaloy-NTK Sales Navigator — Setup Guide

## Prerequisites
You need Python installed. Download from https://www.python.org/downloads/ (tick "Add to PATH" during install).

---

## Step 1 — Install dependencies

Open a Command Prompt or PowerShell, navigate to this folder, then run:

```
pip install -r requirements.txt
```

---

## Step 2 — Run the app

```
streamlit run app.py
```

The app will open in your browser at http://localhost:8501

---

## Step 3 — First login

| Username | Full Name | Default Password |
|---|---|---|
| rob.werhun | Rob Werhun (Admin) | Tungaloy2024! |
| phil.irvine | Phil Irvine (Regional Manager) | Tungaloy2024! |
| simon.turnock | Simon Turnock | Tungaloy2024! |
| graeme.brash | Graeme Brash | Tungaloy2024! |
| duncan.boyle | Duncan Boyle | Tungaloy2024! |
| rhys.danby | Rhys Danby | Tungaloy2024! |
| simon.huxtable | Simon Huxtable | Tungaloy2024! |
| james.gittoes | James Gittoes | Tungaloy2024! |
| ashley.hitchens | Ashley Hitchens | Tungaloy2024! |
| kevin.hamilton | Kevin Hamilton | Tungaloy2024! |
| chris.gibson | Chris Gibson | Tungaloy2024! |
| sylwia.dubij | Sylwia Dubij (Marketing) | Tungaloy2024! |

Each user will be prompted to change their password on first login.

---

## Step 4 — Configure email

1. Log in as **rob.werhun**
2. Go to **Admin → Email Config**
3. Enter your `Rob.Werhun@tungaloyuk.co.uk` email address
4. Enter your password (or App Password if MFA is enabled)
5. Click **Send Test Email** to confirm it works

> **Note on App Passwords:** If your Microsoft 365 account has Multi-Factor Authentication enabled,
> you need to create an App Password in your Microsoft account settings:
> Account Security → Advanced Security → App Passwords

---

## Step 5 — Upload your GP data

1. Log in as **rob.werhun**
2. Go to **Upload Data**
3. Upload `GP report Jan-Mar26.xlsx`
4. Click **Confirm Import**

The app will automatically populate all customers and assign them to the correct rep.

---

## Monthly workflow

At the end of each month:
1. Go to **Upload Data**
2. Upload the new monthly GP report
3. The app adds new transactions without deleting old ones (duplicates are skipped)

---

## Alert emails

Alerts are triggered in two ways:
- **Manually**: Admin or any user can click "Run Alerts Now" on the Alerts page
- **Scheduled**: To run alerts automatically each day, see the section below

### Setting up daily scheduled alerts (Windows Task Scheduler)

1. Open **Task Scheduler** (search in Start menu)
2. Create a Basic Task
3. Set trigger: Daily at 08:00
4. Set action: Start a program
   - Program: `python`
   - Arguments: `-c "import sys; sys.path.insert(0,'C:\\path\\to\\SalesNavigator'); import database as db; import auth; import alert_engine as ae; db.init_db(); auth.seed_users(); ae.run_alerts(send_emails=True, digest_mode=True)"`
5. Save the task

---

## File locations

- App files: This folder
- Database: `sales_navigator.db` (created automatically in this folder)
- Do not delete `sales_navigator.db` — it contains all visit history and user data

---

## Hosting for the whole team (optional)

To let the full team access the app without running it on their own machines,
deploy to **Streamlit Community Cloud** (free):

1. Push this folder to a GitHub repository (private)
2. Go to https://share.streamlit.io
3. Connect your GitHub repo and deploy `app.py`
4. Share the URL with your team

> **Important**: Streamlit Cloud does not persist the SQLite database between restarts.
> For cloud hosting, contact your IT team to set up a PostgreSQL database (e.g. Supabase free tier)
> and we can update the database layer to use it.
