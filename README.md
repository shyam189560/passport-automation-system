# Passport Automation System

A full-stack demo web application for applying for a passport online — application forms,
document upload, appointment booking, real-time status tracking, and an admin back-office —
built with Flask, SQLite, and vanilla HTML/CSS/JavaScript.

> This is a demonstration platform. It is **not** connected to any real government passport
> service and does not perform real identity verification, payments, or police checks.

---

## Features

**Public**
- Modern landing page (hero, services, how-it-works, FAQ)
- Application tracking by Application ID — no login required

**User dashboard (after login)**
- Application status card with live progress bar
- 5-step application wizard: Personal Info → Address → Passport Type → Document Upload → Review & Submit
- Document upload with preview/remove and verification status
- Appointment booking (office, date, time slot)
- In-app notifications

**Admin panel**
- Dashboard with key stats and simple charts (applications/month, status breakdown)
- Application search & filtering, per-application detail & status updates
- Document verification
- Appointments, Users, Reports and Settings pages

---

## Tech stack

| Layer      | Technology                     |
|------------|---------------------------------|
| Frontend   | HTML5, CSS3, vanilla JavaScript (Jinja2 templates) |
| Backend    | Python 3, Flask                |
| Database   | SQLite (file: `database.db`)   |
| Auth       | Session-based, password hashing via Werkzeug |

---

## Project structure

```
passport-automation-system/
├── app.py                  # Flask app: routes, models, REST API, seed data
├── requirements.txt
├── database.db              # created automatically on first run
├── static/
│   ├── css/style.css        # design system
│   ├── js/                  # main.js, application.js, tracking.js, appointment.js
│   └── uploads/              # uploaded document files land here
└── templates/
    ├── base.html, index.html, login.html, register.html
    ├── app_base.html, dashboard.html, application.html, tracking.html, appointment.html
    └── admin/
        ├── base.html, dashboard.html, applications.html, application_detail.html
        ├── appointments.html, users.html, documents.html, reports.html, settings.html
```

---

## Setup & run

```bash
cd passport-automation-system
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

The SQLite database (`database.db`) and a handful of sample applications, users, and
appointments are created automatically the first time you run the app.

---

## Demo credentials

| Role  | Email                 | Password   |
|-------|------------------------|------------|
| User  | demo@passport.gov      | demo1234   |
| Admin | admin@passport.gov     | admin1234  |

A ready-made sample application (`PAS-2026-001245`) is attached to the demo user account so
you can explore the dashboard, tracking page, and admin panel immediately — or register a new
account and run through the whole flow yourself.

To try the tracking page without logging in, visit **Track Application** and search for
`PAS-2026-001245`.

---

## Resetting demo data

Admin → Settings → **Reset Demo Data** wipes `database.db` and reseeds it with fresh sample
data. You can also do this manually:

```bash
rm database.db
python app.py
```

---

## Notes

- Uploaded documents are stored on disk under `static/uploads/` and referenced by filename in
  the `documents` table — this is a demo setup and is not intended for production file storage.
- All "verification", "police verification", and "passport printing/dispatch" stages are
  simulated by the admin manually moving an application's status forward; there is no real
  government integration.
- Session secret key and demo passwords are hard-coded for convenience — change these before
  deploying anywhere beyond local development.
