import sqlite3
from datetime import date, timedelta

from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, role_required

# --- App setup ---
app = Flask(__name__)

# Server-side sessions (not client-side cookies) — same reasoning as CS50 Finance:
# keeps session data off the client and lets us store more than a signed cookie allows.
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


def get_db():
    """Open a new database connection with row access by column name."""
    conn = sqlite3.connect("clinic.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --- Auth routes ---

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    confirmation = request.form.get("confirmation")
    role = request.form.get("role")  # "patient" or "doctor" (admin created manually)

    # --- Validation ---
    if not name or not email or not password:
        return apology("must provide name, email, and password", 400)
    if password != confirmation:
        return apology("passwords do not match", 400)
    if role not in ("patient", "doctor"):
        return apology("invalid role", 400)

    db = get_db()

    # Check email isn't already taken
    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        db.close()
        return apology("email already registered", 400)

    # Insert into users, then into the role-specific table
    hash_ = generate_password_hash(password)
    cursor = db.execute(
        "INSERT INTO users (name, email, hash, role) VALUES (?, ?, ?, ?)",
        (name, email, hash_, role),
    )
    user_id = cursor.lastrowid

    if role == "patient":
        db.execute("INSERT INTO patients (user_id) VALUES (?)", (user_id,))
    elif role == "doctor":
        db.execute("INSERT INTO providers (user_id) VALUES (?)", (user_id,))

    db.commit()
    db.close()

    flash("Registered successfully. Please log in.")
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email")
    password = request.form.get("password")

    if not email or not password:
        return apology("must provide email and password", 400)

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    db.close()

    if user is None or not check_password_hash(user["hash"], password):
        return apology("invalid email and/or password", 403)

    session["user_id"] = user["id"]
    session["name"] = user["name"]
    session["role"] = user["role"]

    # Notify about today's appointments, if any
    if user["role"] in ("patient", "doctor"):
        db = get_db()
        column = "patient_id" if user["role"] == "patient" else "provider_id"
        today_count = db.execute(
            f"""
            SELECT COUNT(*) AS n FROM appointments
            WHERE {column} = ? AND date(appointment_datetime) = date('now') AND status = 'scheduled'
            """,
            (user["id"],),
        ).fetchone()["n"]
        db.close()

        if today_count == 1:
            flash("You have 1 appointment today.")
        elif today_count > 1:
            flash(f"You have {today_count} appointments today.")

    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# --- Root route: redirect based on role ---

@app.route("/")
@login_required
def index():
    role = session.get("role")
    if role == "patient":
        return redirect("/patient/dashboard")
    elif role == "doctor":
        return redirect("/doctor/dashboard")
    elif role == "admin":
        return redirect("/admin/dashboard")
    return apology("unknown role", 400)


# --- Patient routes ---

@app.route("/patient/dashboard")
@role_required("patient")
def patient_dashboard():
    db = get_db()
    appointments = db.execute(
        """
        SELECT appointments.id, appointments.appointment_datetime, appointments.status,
               users.name AS provider_name, providers.specialty
        FROM appointments
        JOIN providers ON appointments.provider_id = providers.user_id
        JOIN users ON providers.user_id = users.id
        WHERE appointments.patient_id = ?
        ORDER BY appointments.appointment_datetime ASC
        """,
        (session["user_id"],),
    ).fetchall()
    db.close()

    return render_template("patient_dashboard.html", appointments=appointments)


@app.route("/patient/profile", methods=["GET", "POST"])
@role_required("patient")
def patient_profile():
    db = get_db()

    if request.method == "POST":
        phone = request.form.get("phone", "")
        address = request.form.get("address", "")
        date_of_birth = request.form.get("date_of_birth") or None
        allergies = request.form.get("allergies", "")

        db.execute(
            "UPDATE patients SET phone = ?, address = ?, date_of_birth = ?, allergies = ? WHERE user_id = ?",
            (phone, address, date_of_birth, allergies, session["user_id"]),
        )
        db.commit()
        flash("Profile updated.")

    patient = db.execute(
        "SELECT * FROM patients WHERE user_id = ?", (session["user_id"],)
    ).fetchone()
    db.close()

    return render_template("patient_profile.html", patient=patient)


@app.route("/patient/appointment/<int:appointment_id>")
@role_required("patient")
def patient_appointment_detail(appointment_id):
    db = get_db()

    appt = db.execute(
        """
        SELECT appointments.*, users.name AS provider_name, providers.specialty
        FROM appointments
        JOIN providers ON appointments.provider_id = providers.user_id
        JOIN users ON providers.user_id = users.id
        WHERE appointments.id = ?
        """,
        (appointment_id,),
    ).fetchone()

    if appt is None:
        db.close()
        return apology("appointment not found", 404)

    # Ownership check: this appointment must belong to the logged-in patient
    if appt["patient_id"] != session["user_id"]:
        db.close()
        return apology("access denied", 403)

    prescriptions = db.execute(
        "SELECT * FROM prescriptions WHERE appointment_id = ? ORDER BY issued_date DESC",
        (appointment_id,),
    ).fetchall()
    db.close()

    return render_template("patient_appointment_detail.html", appt=appt, prescriptions=prescriptions)


@app.route("/patient/appointment/<int:appointment_id>/cancel", methods=["POST"])
@role_required("patient")
def cancel_appointment(appointment_id):
    db = get_db()

    appt = db.execute("SELECT patient_id, status FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    if appt is None:
        db.close()
        return apology("appointment not found", 404)
    if appt["patient_id"] != session["user_id"]:
        db.close()
        return apology("access denied", 403)
    if appt["status"] != "scheduled":
        db.close()
        return apology("only scheduled appointments can be cancelled", 400)

    db.execute("UPDATE appointments SET status = 'cancelled' WHERE id = ?", (appointment_id,))
    db.commit()
    db.close()

    flash("Appointment cancelled.")
    return redirect("/patient/dashboard")


@app.route("/api/availability/<int:provider_id>")
@role_required("patient")
def api_availability(provider_id):
    """Return open 30-minute time slots for a provider on a given date.

    Computed as: the provider's availability windows for that day of week,
    minus any times already booked (excluding cancelled appointments).
    """
    date_str = request.args.get("date")
    if not date_str:
        return jsonify({"error": "date is required"}), 400

    try:
        parsed_date = date.fromisoformat(date_str)
    except ValueError:
        return jsonify({"error": "invalid date"}), 400

    day_of_week = parsed_date.weekday()
    db = get_db()

    windows = db.execute(
        "SELECT start_time, end_time FROM availability WHERE provider_id = ? AND day_of_week = ?",
        (provider_id, day_of_week),
    ).fetchall()

    booked_rows = db.execute(
        """
        SELECT appointment_datetime FROM appointments
        WHERE provider_id = ? AND date(appointment_datetime) = ? AND status != 'cancelled'
        """,
        (provider_id, date_str),
    ).fetchall()
    db.close()

    booked_times = {row["appointment_datetime"].split(" ")[1] for row in booked_rows}

    slot_minutes = 30
    slots = []
    for window in windows:
        start_h, start_m = map(int, window["start_time"].split(":"))
        end_h, end_m = map(int, window["end_time"].split(":"))
        current = start_h * 60 + start_m
        end = end_h * 60 + end_m
        while current + slot_minutes <= end:
            hh, mm = divmod(current, 60)
            time_str = f"{hh:02d}:{mm:02d}"
            if time_str not in booked_times:
                slots.append(time_str)
            current += slot_minutes

    return jsonify({"slots": slots})


@app.route("/api/doctors/search")
@role_required("patient")
def api_doctors_search():
    query = request.args.get("q", "").strip()
    db = get_db()

    if query:
        like_pattern = f"%{query}%"
        rows = db.execute(
            "SELECT users.id, users.name, providers.specialty "
            "FROM providers JOIN users ON providers.user_id = users.id "
            "WHERE users.name LIKE ? OR providers.specialty LIKE ? "
            "ORDER BY users.name",
            (like_pattern, like_pattern),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT users.id, users.name, providers.specialty "
            "FROM providers JOIN users ON providers.user_id = users.id "
            "ORDER BY users.name"
        ).fetchall()
    db.close()

    return jsonify({"doctors": [dict(row) for row in rows]})


@app.route("/patient/book", methods=["GET", "POST"])
@role_required("patient")
def book_appointment():
    db = get_db()

    if request.method == "GET":
        # List all doctors to choose from
        doctors = db.execute(
            "SELECT users.id, users.name, providers.specialty "
            "FROM providers JOIN users ON providers.user_id = users.id"
        ).fetchall()
        db.close()
        return render_template("book_appointment.html", doctors=doctors)

    # --- POST: create the appointment ---
    provider_id = request.form.get("provider_id")
    date_str = request.form.get("date")   # e.g. "2026-08-05"
    time_str = request.form.get("time")   # e.g. "10:00"

    if not provider_id or not date_str or not time_str:
        db.close()
        return apology("must select a doctor, date, and time", 400)

    # Validate the date is well-formed and get its day of week (0=Monday)
    try:
        parsed_date = date.fromisoformat(date_str)
    except ValueError:
        db.close()
        return apology("invalid date", 400)

    day_of_week = parsed_date.weekday()

    # Check the doctor is actually available on this day, at this time
    availability = db.execute(
        """
        SELECT id FROM availability
        WHERE provider_id = ?
          AND day_of_week = ?
          AND start_time <= ?
          AND end_time > ?
        """,
        (provider_id, day_of_week, time_str, time_str),
    ).fetchone()

    if availability is None:
        db.close()
        return apology("doctor is not available at that day/time", 400)

    appointment_datetime = f"{date_str} {time_str}"

    # Conflict check: does this provider already have an appointment
    # at this exact date/time that hasn't been cancelled?
    conflict = db.execute(
        """
        SELECT id FROM appointments
        WHERE provider_id = ?
          AND appointment_datetime = ?
          AND status != 'cancelled'
        """,
        (provider_id, appointment_datetime),
    ).fetchone()

    if conflict:
        db.close()
        return apology("that time slot is no longer available", 400)

    db.execute(
        "INSERT INTO appointments (patient_id, provider_id, appointment_datetime, status) "
        "VALUES (?, ?, ?, 'scheduled')",
        (session["user_id"], provider_id, appointment_datetime),
    )
    db.commit()
    db.close()

    flash("Appointment booked successfully.")
    return redirect("/patient/dashboard")


# --- Doctor routes ---

@app.route("/doctor/availability", methods=["GET", "POST"])
@role_required("doctor")
def manage_availability():
    db = get_db()

    if request.method == "POST":
        day_of_week = request.form.get("day_of_week")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")

        if day_of_week is None or not start_time or not end_time:
            db.close()
            return apology("must provide day, start time, and end time", 400)

        if start_time >= end_time:
            db.close()
            return apology("start time must be before end time", 400)

        db.execute(
            "INSERT INTO availability (provider_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, ?)",
            (session["user_id"], day_of_week, start_time, end_time),
        )
        db.commit()
        flash("Availability added.")

    slots = db.execute(
        "SELECT * FROM availability WHERE provider_id = ? ORDER BY day_of_week, start_time",
        (session["user_id"],),
    ).fetchall()
    db.close()

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return render_template("doctor_availability.html", slots=slots, day_names=day_names)


@app.route("/doctor/availability/<int:availability_id>/delete", methods=["POST"])
@role_required("doctor")
def delete_availability(availability_id):
    db = get_db()

    slot = db.execute("SELECT provider_id FROM availability WHERE id = ?", (availability_id,)).fetchone()
    if slot is None:
        db.close()
        return apology("availability slot not found", 404)
    if slot["provider_id"] != session["user_id"]:
        db.close()
        return apology("access denied", 403)

    db.execute("DELETE FROM availability WHERE id = ?", (availability_id,))
    db.commit()
    db.close()

    flash("Availability removed.")
    return redirect("/doctor/availability")


@app.route("/doctor/dashboard")
@role_required("doctor")
def doctor_dashboard():
    db = get_db()

    # Compute this week's Monday through Sunday
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)              # Sunday

    rows = db.execute(
        """
        SELECT appointments.id, appointments.appointment_datetime, appointments.status,
               users.name AS patient_name
        FROM appointments
        JOIN patients ON appointments.patient_id = patients.user_id
        JOIN users ON patients.user_id = users.id
        WHERE appointments.provider_id = ?
          AND date(appointments.appointment_datetime) BETWEEN ? AND ?
          AND appointments.status = 'scheduled'
        ORDER BY appointments.appointment_datetime ASC
        """,
        (session["user_id"], week_start.isoformat(), week_end.isoformat()),
    ).fetchall()
    db.close()

    # Build one column per day of the week, even if empty, so the calendar
    # grid always shows all 7 days.
    days = []
    for i in range(7):
        day_date = week_start + timedelta(days=i)
        day_appointments = [
            row for row in rows
            if row["appointment_datetime"].startswith(day_date.isoformat())
        ]
        days.append({
            "date": day_date,
            "label": day_date.strftime("%a"),      # "Mon", "Tue", ...
            "is_today": day_date == today,
            "appointments": day_appointments,
        })

    today_appointment_count = sum(
        row["appointment_datetime"].startswith(today.isoformat()) for row in rows
    )
    active_days_count = sum(bool(day["appointments"]) for day in days)

    return render_template(
        "doctor_dashboard.html",
        days=days,
        week_start=week_start,
        week_end=week_end,
        weekly_appointment_count=len(rows),
        today_appointment_count=today_appointment_count,
        active_days_count=active_days_count,
    )


@app.route("/doctor/history")
@role_required("doctor")
def doctor_history():
    db = get_db()
    appointments = db.execute(
        """
        SELECT appointments.id, appointments.appointment_datetime, appointments.notes,
               users.name AS patient_name
        FROM appointments
        JOIN patients ON appointments.patient_id = patients.user_id
        JOIN users ON patients.user_id = users.id
        WHERE appointments.provider_id = ?
          AND appointments.status = 'completed'
        ORDER BY appointments.appointment_datetime DESC
        """,
        (session["user_id"],),
    ).fetchall()
    db.close()

    return render_template("doctor_history.html", appointments=appointments)


@app.route("/doctor/appointment/<int:appointment_id>")
@role_required("doctor")
def appointment_detail(appointment_id):
    db = get_db()

    appt = db.execute(
        """
        SELECT appointments.*, users.name AS patient_name, users.email AS patient_email,
               patients.allergies AS patient_allergies
        FROM appointments
        JOIN patients ON appointments.patient_id = patients.user_id
        JOIN users ON patients.user_id = users.id
        WHERE appointments.id = ?
        """,
        (appointment_id,),
    ).fetchone()

    if appt is None:
        db.close()
        return apology("appointment not found", 404)

    # Ownership check: this appointment must belong to the logged-in doctor
    if appt["provider_id"] != session["user_id"]:
        db.close()
        return apology("access denied", 403)

    prescriptions = db.execute(
        "SELECT * FROM prescriptions WHERE appointment_id = ? ORDER BY issued_date DESC",
        (appointment_id,),
    ).fetchall()
    db.close()

    return render_template("appointment_detail.html", appt=appt, prescriptions=prescriptions)


@app.route("/doctor/appointment/<int:appointment_id>/complete", methods=["POST"])
@role_required("doctor")
def complete_appointment(appointment_id):
    db = get_db()

    appt = db.execute("SELECT provider_id FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    if appt is None:
        db.close()
        return apology("appointment not found", 404)
    if appt["provider_id"] != session["user_id"]:
        db.close()
        return apology("access denied", 403)

    notes = request.form.get("notes", "")
    db.execute(
        "UPDATE appointments SET status = 'completed', notes = ? WHERE id = ?",
        (notes, appointment_id),
    )
    db.commit()
    db.close()

    flash("Appointment marked as completed.")
    return redirect(f"/doctor/appointment/{appointment_id}")


@app.route("/doctor/appointment/<int:appointment_id>/cancel", methods=["POST"])
@role_required("doctor")
def doctor_cancel_appointment(appointment_id):
    db = get_db()

    appt = db.execute("SELECT provider_id, status FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    if appt is None:
        db.close()
        return apology("appointment not found", 404)
    if appt["provider_id"] != session["user_id"]:
        db.close()
        return apology("access denied", 403)
    if appt["status"] != "scheduled":
        db.close()
        return apology("only scheduled appointments can be cancelled", 400)

    db.execute("UPDATE appointments SET status = 'cancelled' WHERE id = ?", (appointment_id,))
    db.commit()
    db.close()

    flash("Appointment cancelled.")
    return redirect("/doctor/dashboard")


@app.route("/doctor/appointment/<int:appointment_id>/prescribe", methods=["POST"])
@role_required("doctor")
def prescribe(appointment_id):
    db = get_db()

    appt = db.execute("SELECT provider_id FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    if appt is None:
        db.close()
        return apology("appointment not found", 404)
    if appt["provider_id"] != session["user_id"]:
        db.close()
        return apology("access denied", 403)

    medication = request.form.get("medication")
    dosage = request.form.get("dosage")
    instructions = request.form.get("instructions", "")

    if not medication or not dosage:
        db.close()
        return apology("must provide medication and dosage", 400)

    db.execute(
        "INSERT INTO prescriptions (appointment_id, medication, dosage, instructions) VALUES (?, ?, ?, ?)",
        (appointment_id, medication, dosage, instructions),
    )
    db.commit()
    db.close()

    flash("Prescription added.")
    return redirect(f"/doctor/appointment/{appointment_id}")


# --- Admin routes ---

@app.route("/admin")
@role_required("admin")
def admin_root():
    return redirect("/admin/dashboard")


@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    db = get_db()

    total_patients = db.execute("SELECT COUNT(*) AS n FROM patients").fetchone()["n"]
    total_doctors = db.execute("SELECT COUNT(*) AS n FROM providers").fetchone()["n"]

    status_counts = db.execute(
        "SELECT status, COUNT(*) AS n FROM appointments GROUP BY status"
    ).fetchall()
    status_map = {row["status"]: row["n"] for row in status_counts}
    total_appointments = sum(status_map.values())

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    this_week_count = db.execute(
        "SELECT COUNT(*) AS n FROM appointments WHERE date(appointment_datetime) BETWEEN ? AND ?",
        (week_start.isoformat(), week_end.isoformat()),
    ).fetchone()["n"]

    # Cancellation rate: cancelled / total, guarding against divide-by-zero
    cancelled = status_map.get("cancelled", 0)
    cancellation_rate = round((cancelled / total_appointments) * 100, 1) if total_appointments else 0

    top_doctors = db.execute(
        """
        SELECT users.name, COUNT(*) AS appointment_count
        FROM appointments
        JOIN providers ON appointments.provider_id = providers.user_id
        JOIN users ON providers.user_id = users.id
        GROUP BY appointments.provider_id
        ORDER BY appointment_count DESC
        LIMIT 5
        """
    ).fetchall()

    db.close()

    return render_template(
        "admin_dashboard.html",
        total_patients=total_patients,
        total_doctors=total_doctors,
        total_appointments=total_appointments,
        this_week_count=this_week_count,
        status_map=status_map,
        cancellation_rate=cancellation_rate,
        top_doctors=top_doctors,
        week_start=week_start,
        week_end=week_end,
    )


@app.route("/admin/users")
@role_required("admin")
def admin_users():
    db = get_db()
    users = db.execute("SELECT id, name, email, role FROM users ORDER BY role, name").fetchall()
    db.close()
    return render_template("admin_users.html", users=users)


@app.route("/api/admin/users/search")
@role_required("admin")
def api_admin_users_search():
    query = request.args.get("q", "").strip()
    db = get_db()

    if query:
        like_pattern = f"%{query}%"
        rows = db.execute(
            "SELECT id, name, email, role FROM users "
            "WHERE name LIKE ? OR email LIKE ? ORDER BY role, name",
            (like_pattern, like_pattern),
        ).fetchall()
    else:
        rows = db.execute("SELECT id, name, email, role FROM users ORDER BY role, name").fetchall()
    db.close()

    return jsonify({"users": [dict(row) for row in rows]})


if __name__ == "__main__":
    app.run(debug=True)
