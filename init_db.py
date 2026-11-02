"""Create the database from schema.sql if it doesn't exist yet, and optionally
create an admin from ADMIN_NAME / ADMIN_EMAIL / ADMIN_PASSWORD env vars.
Safe to run on every deploy."""
import os
import sqlite3

from werkzeug.security import generate_password_hash

conn = sqlite3.connect("clinic.db")
has_users = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
).fetchone()
if not has_users:
    with open("schema.sql") as f:
        conn.executescript(f.read())
    print("Database created from schema.sql")

email = os.getenv("ADMIN_EMAIL")
password = os.getenv("ADMIN_PASSWORD")
if email and password:
    exists = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO users (name, email, hash, role) VALUES (?, ?, ?, 'admin')",
            (name := os.getenv("ADMIN_NAME", "Admin"), email, generate_password_hash(password)),
        )
        print(f"Admin created: {email}")
conn.commit()
conn.close()
