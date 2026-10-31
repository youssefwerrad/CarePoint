# CarePoint

A clinic management system built with Flask, SQLite, and vanilla JavaScript. CarePoint lets patients book appointments with real-time availability checking, lets doctors manage their schedule and issue prescriptions, and gives admins a system-wide view of clinic activity.

## Why I built this

Most of my earlier projects (Dealer Rate, AssetOS) were CRUD-heavy — good practice for auth and database design, but not much beyond that. CarePoint was an exercise in modeling a genuinely relational problem: overlapping schedules, role-based permissions across three distinct user types, and data that different roles are allowed to see in different amounts (a patient sees their own prescriptions; a doctor sees a patient's allergies but not their address; an admin sees aggregate stats but not individual medical notes).

## Features

**Patients**
- Register and book appointments with a live availability picker — the time dropdown is populated via a `fetch()` call to the backend, showing only slots the doctor has marked available and that aren't already booked
- Search doctors by name or specialty, filtered live as you type
- View appointment history, including prescriptions and visit notes from completed visits
- Cancel their own upcoming appointments
- Maintain a personal profile (contact info, allergies/medical notes) that doctors can see during a visit

**Doctors**
- Set weekly working hours per day, which directly constrains what patients can book
- View their schedule as a weekly calendar (Monday–Sunday), with today visually highlighted
- Open any appointment to add visit notes, mark it complete, or issue one or more prescriptions
- View a patient's self-reported allergies before a visit
- Browse a history of completed appointments separately from the active weekly schedule

**Admins**
- Dashboard showing total patients/doctors, appointments this week, cancellation rate, and busiest doctors by appointment volume
- Full user directory with live search by name or email

## Design decisions worth mentioning

- **Ownership checks are inline, not just role-based.** Every route that touches a specific appointment (view, complete, prescribe, cancel) re-checks that the record actually belongs to the logged-in user, rather than trusting the URL. A doctor can't view another doctor's appointment by guessing an ID, even though both are authenticated as "doctor."
- **Availability-aware booking, not just conflict-checking.** Booking validates against two things: (1) is this exact slot already taken, and (2) is the doctor even working that day/hour at all, based on their own configured hours. Both checks happen server-side, since the JS-populated dropdown is a UX convenience, not a security boundary.
- **SQLite `PRAGMA foreign_keys = ON`** is set explicitly on every connection, since SQLite ignores foreign key constraints by default — an easy thing to miss.
- **Patients and providers extend `users`** via a shared primary key rather than duplicating name/email, avoiding a common normalization mistake.

## Tech stack

- **Backend:** Python, Flask, Flask-Session
- **Database:** SQLite (raw `sqlite3`, no ORM)
- **Frontend:** Jinja2 templates, vanilla JavaScript (`fetch` API), no frontend framework
- **Auth:** Session-based, password hashing via Werkzeug

## Project structure

```
project/
├── app.py                    # All routes
├── helpers.py                  # login_required, role_required, apology
├── schema.sql                    # Database schema
├── create_admin.py                 # One-off script to create an admin account
├── static/
│   ├── css/styles.css               # Design tokens + all component styles
│   └── js/
│       ├── booking.js                 # Live availability slot picker + doctor search
│       └── search.js                    # Admin user search
└── templates/                             # One template per page, extending layout.html
```

## Running it locally

```bash
pip install -r requirements.txt

python3 -c "
import sqlite3
conn = sqlite3.connect('clinic.db')
with open('schema.sql') as f:
    conn.executescript(f.read())
conn.commit()
conn.close()
"

python3 create_admin.py   # create your first admin login

flask run
```

Then register a doctor and a patient account through the UI. The doctor will need to set availability hours (`/doctor/availability`) before patients can book with them.

## UI refresh

The app has been refreshed with a more modern clinical dashboard style: brighter gradients, soft card surfaces, a sticky navigation bar, responsive layouts, and clearer status treatments.

## What I'd add next

- A real notification system (currently just a login-time flash message)
- Recurring availability templates instead of adding one day at a time
- Deployment (Render/Railway)
