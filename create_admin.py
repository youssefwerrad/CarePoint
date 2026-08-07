"""
One-off script to create an admin user.

Admin accounts aren't self-registerable through /register on purpose —
anyone could otherwise sign up with elevated access. Run this manually
whenever you need to create (or promote) an admin.

Usage:
    python3 create_admin.py
"""

import sqlite3
from werkzeug.security import generate_password_hash

name = input("Admin name: ")
email = input("Admin email: ")
password = input("Admin password: ")

conn = sqlite3.connect("clinic.db")
cur = conn.cursor()

existing = cur.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
if existing:
    print(f"A user with email {email} already exists (id={existing[0]}).")
else:
    hash_ = generate_password_hash(password)
    cur.execute(
        "INSERT INTO users (name, email, hash, role) VALUES (?, ?, ?, 'admin')",
        (name, email, hash_),
    )
    conn.commit()
    print(f"Admin account created: {email}")

conn.close()
