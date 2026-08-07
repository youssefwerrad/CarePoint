CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('patient', 'doctor', 'admin'))
);

CREATE TABLE patients (
    user_id INTEGER PRIMARY KEY,
    date_of_birth DATE,
    phone TEXT,
    address TEXT,
    allergies TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE providers (
    user_id INTEGER PRIMARY KEY,
    specialty TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE availability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,  -- 0=Monday ... 6=Sunday
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    FOREIGN KEY (provider_id) REFERENCES providers(user_id)
);

CREATE TABLE appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    provider_id INTEGER NOT NULL,
    appointment_datetime DATETIME NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK(status IN ('scheduled', 'completed', 'cancelled')),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(user_id),
    FOREIGN KEY (provider_id) REFERENCES providers(user_id)
);

CREATE TABLE prescriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER NOT NULL,
    medication TEXT NOT NULL,
    dosage TEXT NOT NULL,
    instructions TEXT,
    issued_date DATE DEFAULT CURRENT_DATE,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id)
);

-- Indexes to speed up the two most common lookups:
-- 1. "Is this provider free at this time?" (conflict checking)
-- 2. "Show me this patient's appointment history"
CREATE INDEX idx_appointments_provider_time ON appointments(provider_id, appointment_datetime);
CREATE INDEX idx_appointments_patient ON appointments(patient_id);
