import os
import re
import sqlite3
import json
import math
import random
import hashlib
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Dict, List, Tuple, Union, Any, Optional

DB_NAME = str(Path(__file__).parent / "cosmo_care.db")
DATA_DIR = Path(__file__).parent / "data"
MEDIA_DIR = Path(__file__).parent / "assets" / "media"
USER_MEDIA_ROOT = Path(__file__).parent / "assets" / "user_media"
SPEED_OF_LIGHT_KM_S = 299792.458
EARTH_PREP_DAYS = 14.0
SAFETY_BUFFER_PERCENT = 0.25

VALID_ZONES = ["earth", "leo", "cislunar", "deep_space", "lunar_surface", "mars_surface"]

VOICE_CORRECTIONS = {
    "sea oh two": "CO2",
    "co two": "CO2",
    "carbon dioxide": "CO2",
    "oh two": "O2",
    "a red": "ARED",
    "tea two": "T2",
    "vital signs": "vitals",
    "heart beat": "heart rate",
    "blood pleasure": "blood pressure",
    "radon": "radiation",
    "em are ee": "MRE",
    "water bag": "Water Pouch"
}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.strip().encode("utf-8")).hexdigest()


@dataclass
class AstronautVitals:
    astronaut_id: str = "A004"
    flight_day: int = 24
    hr: float = 68.0
    sbp: float = 118.0
    dbp: float = 76.0
    hrv: float = 44.0
    co2: float = 2.6
    ectopic: int = 0
    dizzy: bool = False
    headache: bool = False
    region: str = "None"
    symptom: str = "None"
    pain: int = 0
    activity_index: int = 50


class DatabaseManager:
    def __init__(self, db_name: str = DB_NAME):
        self.db_name = db_name
        self.ensure_all_tables()
        self.seed_initial_data_if_empty()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def ensure_all_tables(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS astronauts (
                astronaut_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT DEFAULT 'Mission Specialist',
                age INTEGER,
                sex TEXT,
                height_cm REAL,
                weight_kg REAL,
                blood_type TEXT DEFAULT 'O+',
                fitness_level TEXT,
                mission_duration_days INTEGER,
                password_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS astronaut_attributes (
                attr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                astronaut_id TEXT NOT NULL,
                attribute_type TEXT NOT NULL,
                attribute_value TEXT NOT NULL,
                FOREIGN KEY (astronaut_id) REFERENCES astronauts(astronaut_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS live_vitals_telemetry (
                telemetry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                astronaut_id TEXT NOT NULL,
                heart_rate_bpm REAL,
                systolic_mmhg REAL,
                diastolic_mmhg REAL,
                hrv_rmssd REAL,
                co2_mmhg REAL DEFAULT 2.6,
                ectopic_beats INTEGER DEFAULT 0,
                flight_day INTEGER,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (astronaut_id) REFERENCES astronauts(astronaut_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS environment_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                oxygen_percent REAL,
                co2_ppm REAL,
                temperature_c REAL,
                humidity_percent REAL,
                pressure_kpa REAL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS radiation_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                detector_id TEXT,
                radiation_type TEXT,
                count_rate_cps REAL,
                sensor_status TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS inventory (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                category TEXT,
                quantity REAL DEFAULT 0.0,
                unit TEXT,
                daily_use_per_person REAL DEFAULT 0.5,
                unit_mass_kg REAL DEFAULT 0.5,
                kcal_per_100g REAL DEFAULT 0.0,
                protein_g REAL DEFAULT 0.0,
                fat_g REAL DEFAULT 0.0,
                carbs_g REAL DEFAULT 0.0,
                shelf_life TEXT DEFAULT '2 y',
                expiration_date TEXT
            );

            CREATE TABLE IF NOT EXISTS consumption_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                astronaut_id TEXT NOT NULL,
                quantity_consumed REAL NOT NULL,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES inventory(item_id) ON DELETE CASCADE,
                FOREIGN KEY (astronaut_id) REFERENCES astronauts(astronaut_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reorder_transmissions (
                transmission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                distance_km REAL,
                light_delay_hours REAL,
                transit_time_days REAL,
                total_lead_time_days REAL,
                payload_summary TEXT,
                status TEXT DEFAULT 'QUEUED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS symptom_and_mood_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                astronaut_id TEXT NOT NULL,
                sleep_hours REAL,
                mood_score INTEGER,
                nausea_score INTEGER,
                dizziness_score INTEGER,
                headache BOOLEAN,
                cramp_region TEXT,
                pain_score INTEGER,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (astronaut_id) REFERENCES astronauts(astronaut_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS ai_chat_history (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                astronaut_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                message_text TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (astronaut_id) REFERENCES astronauts(astronaut_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS media_preferences (
                preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
                astronaut_id TEXT NOT NULL,
                media_type TEXT NOT NULL,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL,
                mood_category TEXT DEFAULT 'sad',
                FOREIGN KEY (astronaut_id) REFERENCES astronauts(astronaut_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sleep_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                astronaut_id TEXT NOT NULL,
                sleep_start TIMESTAMP NOT NULL,
                wake_confirm TIMESTAMP,
                duration_hours REAL,
                status TEXT DEFAULT 'SLEEPING',
                FOREIGN KEY (astronaut_id) REFERENCES astronauts(astronaut_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS medical_exam_records (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                astronaut_id TEXT NOT NULL,
                exam_id TEXT NOT NULL,
                exam_date TEXT NOT NULL,
                field_name TEXT NOT NULL,
                field_value TEXT NOT NULL,
                flag TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (astronaut_id) REFERENCES astronauts(astronaut_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS crew_danger_alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                astronaut_id TEXT,
                alert_category TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                earth_notified BOOLEAN DEFAULT 0,
                acknowledged BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS notifications (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                astronaut_id TEXT,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS system_schedule (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                time_slot TEXT NOT NULL UNIQUE,
                event_title TEXT NOT NULL,
                voice_prompt TEXT NOT NULL,
                play_alarm BOOLEAN DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS mission_state (
                state_key TEXT PRIMARY KEY,
                state_value TEXT NOT NULL
            );
        """)

        cols = [r["name"] for r in cursor.execute("PRAGMA table_info(astronauts)").fetchall()]
        if "password_hash" not in cols:
            cursor.execute("ALTER TABLE astronauts ADD COLUMN password_hash TEXT;")
        if "role" not in cols:
            cursor.execute("ALTER TABLE astronauts ADD COLUMN role TEXT DEFAULT 'Mission Specialist';")
        if "blood_type" not in cols:
            cursor.execute("ALTER TABLE astronauts ADD COLUMN blood_type TEXT DEFAULT 'O+';")

        inv_cols = [r["name"] for r in cursor.execute("PRAGMA table_info(inventory)").fetchall()]
        for col_def in [
            ("daily_use_per_person", "REAL DEFAULT 0.5"),
            ("kcal_per_100g", "REAL DEFAULT 0.0"),
            ("protein_g", "REAL DEFAULT 0.0"),
            ("fat_g", "REAL DEFAULT 0.0"),
            ("carbs_g", "REAL DEFAULT 0.0"),
            ("shelf_life", "TEXT DEFAULT '2 y'")
        ]:
            if col_def[0] not in inv_cols:
                cursor.execute(f"ALTER TABLE inventory ADD COLUMN {col_def[0]} {col_def[1]};")

        conn.commit()
        conn.close()

    def seed_initial_data_if_empty(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        default_crew = [
            ("A004", "Dr. Sarah Mitchell", "Chief Medical Officer", 42, "Female", 170.5, 65.0, "O+", "High", 180, hash_password("Sarah@2026")),
            ("A005", "Cmdr. James Holden", "Mission Commander", 48, "Male", 182.0, 84.5, "A+", "Moderate", 365, hash_password("Holden@2026")),
            ("A006", "Eng. Elena Rostova", "Flight Systems Engineer", 35, "Female", 166.0, 59.0, "B+", "High", 365, hash_password("Elena@2026")),
        ]
        for c in default_crew:
            cursor.execute("""
                INSERT OR IGNORE INTO astronauts 
                (astronaut_id, name, role, age, sex, height_cm, weight_kg, blood_type, fitness_level, mission_duration_days, password_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, c)
            cursor.execute("""
                UPDATE astronauts SET password_hash = COALESCE(password_hash, ?), role = COALESCE(role, ?)
                WHERE astronaut_id = ?
            """, (c[10], c[2], c[0]))

        inv_count = cursor.execute("SELECT COUNT(*) as c FROM inventory").fetchone()["c"]
        if inv_count < 5:
            cursor.execute("DELETE FROM inventory")
            supply_items = [
                ("Water (net after recycling)", "Life Support", 2400.0, "L", 1.2, 1.0, 0, 0, 0, 0, "5 y", "2031-12-31"),
                ("Oxygen Reserve", "Life Support", 900.0, "kg", 0.84, 1.0, 0, 0, 0, 0, "10 y", "2035-12-31"),
                ("CO2 Scrubber Cartridges", "Other", 60.0, "pcs", 0.25, 2.5, 0, 0, 0, 0, "5 y", "2031-12-31"),
                ("Medical Consumables", "Other", 30.0, "kits", 0.04, 1.2, 0, 0, 0, 0, "3 y", "2029-12-31"),
                ("Spare Parts (ECLSS)", "Other", 120.0, "kg", 0.15, 1.0, 0, 0, 0, 0, "10 y", "2035-12-31"),
                ("Hygiene Supplies", "Other", 90.0, "kg", 0.10, 1.0, 0, 0, 0, 0, "4 y", "2030-12-31"),
                ("Rice (dry)", "Grains", 120.0, "kg", 0.15, 1.0, 360, 7, 0.6, 79, "3-5 y", "2030-12-31"),
                ("Oats", "Grains", 60.0, "kg", 0.08, 1.0, 380, 13, 7, 67, "2 y", "2028-12-31"),
                ("Lentils (dried)", "Legumes", 80.0, "kg", 0.10, 1.0, 350, 25, 1, 60, "3 y", "2029-12-31"),
                ("Freeze-dried Chicken", "Protein", 50.0, "kg", 0.08, 1.0, 400, 65, 12, 2, "10 y", "2036-12-31"),
                ("Tuna Pouch", "Protein", 40.0, "kg", 0.06, 1.0, 130, 28, 1, 0, "2 y", "2028-12-31"),
                ("Peanut Butter", "Fats/Nuts", 30.0, "kg", 0.05, 1.0, 590, 25, 50, 20, "1 y", "2027-12-31"),
                ("Almonds", "Fats/Nuts", 25.0, "kg", 0.04, 1.0, 580, 21, 50, 22, "1 y", "2027-12-31"),
                ("Milk Powder", "Dairy", 40.0, "kg", 0.05, 1.0, 500, 26, 27, 38, "2 y", "2028-12-31"),
                ("Dried Fruit Mix", "Fruit", 30.0, "kg", 0.05, 1.0, 300, 3, 0.5, 79, "1 y", "2027-12-31"),
                ("Energy Bar", "Ready", 30.0, "kg", 0.06, 1.0, 420, 8, 15, 60, "1.5 y", "2028-06-30"),
            ]
            cursor.executemany("""
                INSERT INTO inventory 
                (item_name, category, quantity, unit, daily_use_per_person, unit_mass_kg, kcal_per_100g, protein_g, fat_g, carbs_g, shelf_life, expiration_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, supply_items)

        sched_count = cursor.execute("SELECT COUNT(*) as c FROM system_schedule").fetchone()["c"]
        if sched_count == 0:
            default_schedules = [
                ("07:00", "Morning Wake-Up & Biometric Scan", "Good morning! Alarm completed. Please confirm you are awake so I can log your sleep duration, and complete your morning symptom check-in.", 1),
                ("08:00", "Breakfast & Hydration Ration Log", "It is 08:00 hours. Time for breakfast and hydration. Please tell me or log your consumed ration packs so I can update the ship's food stocks.", 0),
                ("10:30", "ARED Resistive & T2 Countermeasure Block", "Time for your scheduled 2.5-hour ARED resistive and T2 treadmill exercise countermeasure session.", 0),
                ("13:00", "Midday Nutrition & Water Check", "Hey there, lunch time! Did you eat and drink your water ration? Don't forget to log your ration packs.", 0),
                ("19:00", "Evening Dinner & Psychological Check-in", "Good evening. Time for dinner rations and your evening health and mood check-in.", 0),
                ("22:00", "Circadian Sleep Pod Lock-in", "It is 22:00 hours. Time for sleep. Please confirm when you are ready to sleep so I can start your sleep timer.", 0),
            ]
            cursor.executemany("""
                INSERT INTO system_schedule (time_slot, event_title, voice_prompt, play_alarm)
                VALUES (?, ?, ?, ?)
            """, default_schedules)

        default_states = [
            ("ship_time", "08:00"),
            ("mission_day", "24"),
            ("distance_million_km", "225.0"),
        ]
        for k, v in default_states:
            cursor.execute("INSERT OR IGNORE INTO mission_state (state_key, state_value) VALUES (?, ?)", (k, v))

        for aid, _, _, _, _, _, _, _, _, _, _ in default_crew:
            v_cnt = cursor.execute("SELECT COUNT(*) as c FROM live_vitals_telemetry WHERE astronaut_id = ?", (aid,)).fetchone()["c"]
            if v_cnt < 5:
                for day_offset in range(18, 25):
                    cursor.execute("""
                        INSERT INTO live_vitals_telemetry 
                        (astronaut_id, heart_rate_bpm, systolic_mmhg, diastolic_mmhg, hrv_rmssd, co2_mmhg, ectopic_beats, flight_day)
                        VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                    """, (
                        aid,
                        round(random.gauss(68.0, 2.5), 1),
                        round(random.gauss(118.0, 3.0), 1),
                        round(random.gauss(76.0, 2.5), 1),
                        round(random.gauss(44.0, 3.0), 1),
                        round(random.uniform(2.3, 2.8), 2),
                        day_offset
                    ))
            s_cnt = cursor.execute("SELECT COUNT(*) as c FROM sleep_sessions WHERE astronaut_id = ?", (aid,)).fetchone()["c"]
            if s_cnt < 3:
                for d in range(5, 0, -1):
                    st_dt = datetime.now(timezone.utc) - timedelta(days=d, hours=8)
                    wk_dt = st_dt + timedelta(hours=round(random.uniform(6.8, 8.1), 1))
                    dur = round((wk_dt - st_dt).total_seconds() / 3600.0, 2)
                    cursor.execute("""
                        INSERT INTO sleep_sessions (astronaut_id, sleep_start, wake_confirm, duration_hours, status)
                        VALUES (?, ?, ?, ?, 'AWAKE')
                    """, (aid, st_dt.isoformat(timespec="seconds"), wk_dt.isoformat(timespec="seconds"), dur))

        conn.commit()
        conn.close()

    def authenticate_user(self, astronaut_id: str, password: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        row = conn.execute(
            "SELECT * FROM astronauts WHERE UPPER(astronaut_id) = UPPER(?)",
            (astronaut_id.strip(),)
        ).fetchone()
        conn.close()
        if not row:
            return None
        expected_hash = row["password_hash"]
        if expected_hash and expected_hash == hash_password(password):
            user_dict = dict(row)
            self.ensure_user_media_folders(user_dict["astronaut_id"])
            return user_dict
        return None

    def ensure_user_media_folders(self, astronaut_id: str) -> Dict[str, Path]:
        base = USER_MEDIA_ROOT / astronaut_id
        paths = {
            "music": base / "music",
            "video": base / "video",
            "voice": base / "voice",
        }
        for p in paths.values():
            p.mkdir(parents=True, exist_ok=True)
        return paths

    def update_astronaut_biometrics(self, astronaut_id: str, height_cm: float, weight_kg: float,
                                    age: int, fitness_level: str) -> Dict[str, Any]:
        conn = self.get_connection()
        conn.execute("""
            UPDATE astronauts
            SET height_cm = ?, weight_kg = ?, age = ?, fitness_level = ?
            WHERE astronaut_id = ?
        """, (round(height_cm, 1), round(weight_kg, 1), int(age), fitness_level, astronaut_id))
        conn.commit()
        updated = conn.execute("SELECT * FROM astronauts WHERE astronaut_id = ?", (astronaut_id,)).fetchone()
        conn.close()
        self.add_notification(
            astronaut_id,
            "INFO",
            "Biometric Profile Updated",
            f"Height ({height_cm:.1f} cm) and Weight ({weight_kg:.1f} kg) synchronized across all medical & nutrition modules."
        )
        return dict(updated) if updated else {}

    def get_astronaut_by_id(self, astronaut_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        row = conn.execute("SELECT * FROM astronauts WHERE astronaut_id = ?", (astronaut_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def calculate_derived_biometrics(profile: Dict[str, Any]) -> Dict[str, Any]:
        h_cm = float(profile.get("height_cm") or 170.0)
        w_kg = float(profile.get("weight_kg") or 65.0)
        age = int(profile.get("age") or 40)
        sex = str(profile.get("sex") or "Female")
        fitness = str(profile.get("fitness_level") or "Moderate")

        h_m = max(1.0, h_cm / 100.0)
        bmi = round(w_kg / (h_m * h_m), 1)
        if bmi < 18.5:
            bmi_status = "Underweight"
        elif bmi < 25.0:
            bmi_status = "Optimal Spaceflight Mass"
        elif bmi < 30.0:
            bmi_status = "Elevated Mass"
        else:
            bmi_status = "High Mass Alert"

        s_offset = 5 if sex.lower() == "male" else -161
        bmr = (10.0 * w_kg) + (6.25 * h_cm) - (5.0 * age) + s_offset
        mult = 1.65 if fitness == "High" else (1.5 if fitness == "Moderate" else 1.35)
        daily_kcal = round(bmr * mult)
        hydration_liters = round(max(2.2, w_kg * 0.038), 2)
        protein_target_g = round(w_kg * 1.4)

        return {
            "bmi": bmi,
            "bmi_status": bmi_status,
            "daily_kcal_target": daily_kcal,
            "hydration_target_l": hydration_liters,
            "protein_target_g": protein_target_g
        }

    def add_notification(self, astronaut_id: str, severity: str, title: str, message: str):
        conn = self.get_connection()
        recent = conn.execute("""
            SELECT notification_id FROM notifications
            WHERE astronaut_id = ? AND title = ? AND message = ?
            ORDER BY notification_id DESC LIMIT 1
        """, (astronaut_id, title, message)).fetchone()
        if not recent:
            conn.execute("""
                INSERT INTO notifications (astronaut_id, severity, title, message, is_read)
                VALUES (?, ?, ?, ?, 0)
            """, (astronaut_id, severity, title, message))
            conn.commit()
        conn.close()

    def get_notifications(self, astronaut_id: str, limit: int = 25) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        rows = conn.execute("""
            SELECT * FROM notifications
            WHERE astronaut_id = ? OR astronaut_id IS NULL
            ORDER BY notification_id DESC LIMIT ?
        """, (astronaut_id, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def mark_notifications_read(self, astronaut_id: str):
        conn = self.get_connection()
        conn.execute("UPDATE notifications SET is_read = 1 WHERE astronaut_id = ? OR astronaut_id IS NULL", (astronaut_id,))
        conn.commit()
        conn.close()

    def get_mission_state(self) -> Dict[str, str]:
        conn = self.get_connection()
        rows = conn.execute("SELECT state_key, state_value FROM mission_state").fetchall()
        conn.close()
        return {r["state_key"]: r["state_value"] for r in rows}

    def set_mission_state(self, key: str, value: str):
        conn = self.get_connection()
        conn.execute("""
            INSERT INTO mission_state (state_key, state_value) VALUES (?, ?)
            ON CONFLICT(state_key) DO UPDATE SET state_value = excluded.state_value
        """, (key, str(value)))
        conn.commit()
        conn.close()

    def get_schedules(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        rows = conn.execute("SELECT * FROM system_schedule ORDER BY time_slot ASC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def upsert_schedule(self, time_slot: str, event_title: str, voice_prompt: str, play_alarm: bool = False):
        conn = self.get_connection()
        conn.execute("""
            INSERT INTO system_schedule (time_slot, event_title, voice_prompt, play_alarm)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(time_slot) DO UPDATE SET
                event_title = excluded.event_title,
                voice_prompt = excluded.voice_prompt,
                play_alarm = excluded.play_alarm
        """, (time_slot.strip(), event_title.strip(), voice_prompt.strip(), 1 if play_alarm else 0))
        conn.commit()
        conn.close()

    def delete_schedule(self, schedule_id: int):
        conn = self.get_connection()
        conn.execute("DELETE FROM system_schedule WHERE schedule_id = ?", (schedule_id,))
        conn.commit()
        conn.close()


class SensorSimulator:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_latest_vitals(self, astronaut_id: str, flight_day: int = 24) -> AstronautVitals:
        conn = self.db.get_connection()
        row = conn.execute("""
            SELECT * FROM live_vitals_telemetry
            WHERE astronaut_id = ?
            ORDER BY telemetry_id DESC LIMIT 1
        """, (astronaut_id,)).fetchone()
        conn.close()
        if not row:
            return self.generate_live_vitals(astronaut_id, flight_day=flight_day)
        return AstronautVitals(
            astronaut_id=astronaut_id,
            flight_day=row["flight_day"] or flight_day,
            hr=float(row["heart_rate_bpm"]),
            sbp=float(row["systolic_mmhg"]),
            dbp=float(row["diastolic_mmhg"]),
            hrv=float(row["hrv_rmssd"]),
            co2=float(row["co2_mmhg"] if "co2_mmhg" in row.keys() and row["co2_mmhg"] is not None else 2.6),
            ectopic=int(row["ectopic_beats"] if "ectopic_beats" in row.keys() and row["ectopic_beats"] is not None else 0),
        )

    def generate_live_vitals(self, astronaut_id: str, flight_day: int = 24, anomaly_mode: Optional[str] = None) -> AstronautVitals:
        hr = round(random.gauss(68.0, 3.5), 1)
        sbp = round(random.gauss(118.0, 4.0), 1)
        dbp = round(random.gauss(76.0, 3.0), 1)
        hrv = round(random.gauss(44.0, 4.0), 1)
        co2_mmhg = round(random.uniform(2.2, 3.1), 2)
        ectopic = 0
        dizzy = False
        headache = False
        region = "None"
        symptom = "None"
        pain = 0

        if anomaly_mode == "arrhythmia":
            hr = round(random.uniform(98.0, 114.0), 1)
            hrv = round(random.uniform(18.0, 24.0), 1)
            ectopic = random.randint(3, 6)
            region = "Calves/Hamstrings"
            symptom = "Acute Cramp/Spasm"
            pain = 7
        elif anomaly_mode == "hypovolemia":
            hr = round(random.uniform(94.0, 106.0), 1)
            sbp = 102.0
            dbp = 78.0
            dizzy = True
        elif anomaly_mode == "high_co2":
            sbp = round(random.uniform(140.0, 148.0), 1)
            co2_mmhg = round(random.uniform(4.0, 4.8), 2)
            headache = True

        vitals = AstronautVitals(
            astronaut_id=astronaut_id,
            flight_day=flight_day,
            hr=hr,
            sbp=sbp,
            dbp=dbp,
            hrv=hrv,
            co2=co2_mmhg,
            ectopic=ectopic,
            dizzy=dizzy,
            headache=headache,
            region=region,
            symptom=symptom,
            pain=pain,
            activity_index=random.randint(30, 75)
        )

        conn = self.db.get_connection()
        conn.execute("""
            INSERT INTO live_vitals_telemetry 
            (astronaut_id, heart_rate_bpm, systolic_mmhg, diastolic_mmhg, hrv_rmssd, co2_mmhg, ectopic_beats, flight_day)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (astronaut_id, vitals.hr, vitals.sbp, vitals.dbp, vitals.hrv, vitals.co2, vitals.ectopic, vitals.flight_day))
        conn.commit()
        conn.close()
        return vitals

    def generate_environment_reading(self, anomaly_mode: Optional[str] = None) -> Dict[str, Any]:
        oxygen = round(random.uniform(20.6, 21.2), 2)
        co2_ppm = round(random.uniform(900.0, 1500.0), 1)
        temp_c = round(random.uniform(21.2, 23.0), 1)
        humidity = round(random.uniform(42.0, 48.0), 1)
        pressure = round(random.uniform(100.8, 101.5), 2)

        if anomaly_mode == "cabin_danger":
            oxygen = round(random.uniform(18.1, 19.0), 2)
            co2_ppm = round(random.uniform(5200.0, 6500.0), 1)

        conn = self.db.get_connection()
        conn.execute("""
            INSERT INTO environment_logs (oxygen_percent, co2_ppm, temperature_c, humidity_percent, pressure_kpa)
            VALUES (?, ?, ?, ?, ?)
        """, (oxygen, co2_ppm, temp_c, humidity, pressure))
        conn.commit()
        conn.close()

        return {
            "oxygen_percent": oxygen,
            "co2_ppm": co2_ppm,
            "co2_mmhg": round((co2_ppm / 1000000.0) * (pressure * 7.50062), 2),
            "temperature_c": temp_c,
            "humidity_percent": humidity,
            "pressure_kpa": pressure,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")
        }

    def generate_radiation_reading(self, detector_id: str = "RAD-01", spike: bool = False) -> Dict[str, Any]:
        cps = round(random.uniform(48.0, 85.0), 2) if spike else round(random.uniform(8.0, 14.0), 2)
        rad_type = "Proton" if spike else random.choice(["Gamma", "Neutron", "Unclassified"])
        status = "warning" if spike else "operational"

        conn = self.db.get_connection()
        conn.execute("""
            INSERT INTO radiation_logs (detector_id, radiation_type, count_rate_cps, sensor_status)
            VALUES (?, ?, ?, ?)
        """, (detector_id, rad_type, cps, status))
        conn.commit()
        conn.close()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "detector_id": detector_id,
            "radiation_type": rad_type,
            "count_rate_cps": cps,
            "sensor_status": status
        }


class BioAstronauticsLogic:
    BASE_HR = (65.0, 6.5)
    BASE_SBP = (118.0, 8.0)
    BASE_HRV = (45.0, 9.0)

    @classmethod
    def get_phase_baselines(cls, flight_day: int) -> Dict[str, Union[Tuple[float, float], str]]:
        if flight_day <= 7:
            return {
                "hr": (cls.BASE_HR[0] - 4.0, cls.BASE_HR[1]),
                "sbp": (cls.BASE_SBP[0] + 4.0, cls.BASE_SBP[1]),
                "hrv": (cls.BASE_HRV[0] + 2.0, cls.BASE_HRV[1]),
                "phase_name": "Phase 1: Acute Cephalad Fluid Shift (Days 1-7)",
            }
        return {
            "hr": (cls.BASE_HR[0] + 4.0, cls.BASE_HR[1]),
            "sbp": (cls.BASE_SBP[0] - 3.0, cls.BASE_SBP[1]),
            "hrv": (cls.BASE_HRV[0] - 3.0, cls.BASE_HRV[1]),
            "phase_name": "Phase 2: Microgravity Equilibrium (Day 8+)",
        }

    @classmethod
    def evaluate_triage(cls, v: AstronautVitals) -> Dict[str, Any]:
        base = cls.get_phase_baselines(v.flight_day)
        z_hr = (v.hr - base["hr"][0]) / base["hr"][1]
        z_sbp = (v.sbp - base["sbp"][0]) / base["sbp"][1]
        z_hrv = (v.hrv - base["hrv"][0]) / base["hrv"][1]

        pulse_pressure = v.sbp - v.dbp
        map_mmhg = v.dbp + (pulse_pressure / 3.0)
        z_limit = 2.0

        status_level = "NOMINAL"
        status_color = "#10b981"
        diagnosis = "Nominal Microgravity Homeostasis"
        explanation = f"Cardiovascular and musculoskeletal parameters are within expected bounds for {base['phase_name']}."
        verification = "No immediate diagnostic verification required. Continue standard daily log."
        steps = [
            "Maintain scheduled 2.5-hour ARED resistive and T2 treadmill countermeasure block.",
            "Ensure standard 2.5 L/day baseline hydration and scheduled vitamin D3 intake.",
        ]
        ared_mod = 100
        recheck_mins = 0

        if v.ectopic >= 3 or (
            v.symptom in ["Acute Cramp/Spasm", "Generalized Weakness"] and z_hr > z_limit and z_hrv < -1.5
        ):
            status_level = "MEDICAL HOLD"
            status_color = "#ef4444"
            diagnosis = "Systemic Electrolyte Depletion & Myocardial Irritability"
            explanation = (
                f"Detected {v.ectopic} ectopic beats/min alongside {v.region.lower()} neuromuscular "
                f"symptoms and depressed HRV (Z = {z_hrv:+.2f}). High risk of spaceflight-induced "
                f"intracellular K+/Mg2+ depletion affecting cardiac conduction."
            )
            verification = "IMMEDIATE: Record 60-second 3-lead ECG rhythm strip; inspect for flattened T-waves or U-waves."
            steps = [
                "HARD STOP: Lock out high-load ARED resistive and T2 treadmill sessions for 24 hours.",
                "BIOCHEMICAL FIX: Administer 1 packet oral Potassium-Magnesium Citrate in 400 mL water now.",
                "TELEMETRY: Auto-package 60s ECG waveform strip for asynchronous Flight Surgeon downlink.",
                "MONITOR: Maintain continuous wearable ECG monitoring and re-verify in 30 minutes.",
            ]
            ared_mod = 0
            recheck_mins = 30

        elif (z_hr >= z_limit and pulse_pressure <= 28) or (v.dizzy and pulse_pressure <= 32):
            status_level = "ADVISORY"
            status_color = "#f59e0b"
            diagnosis = "Microgravity Hypovolemia & Reduced Stroke Volume"
            explanation = (
                f"Elevated resting HR ({v.hr:.0f} bpm, Z = {z_hr:+.2f}) paired with narrowed "
                f"Pulse Pressure ({pulse_pressure:.0f} mmHg) indicates plasma volume contraction."
            )
            verification = "Perform a 2-minute Paced Breathing & Isometric Handgrip Test while recording PPG recovery."
            steps = [
                "HYDRATION BOLUS: Consume 500 mL isotonic oral rehydration solution over 20 mins.",
                "COUNTERMEASURE: Schedule 30 mins in Lower Body Negative Pressure (LBNP) garment or don thigh cuffs.",
                "ACTIVITY: Delay high-intensity interval treadmill running until Pulse Pressure exceeds 32 mmHg.",
                "RE-VERIFY: Repeat oscillometric BP and orthostatic self-check in 45 minutes.",
            ]
            ared_mod = 80
            recheck_mins = 45

        elif (v.sbp >= 138 or z_sbp >= z_limit) and (v.headache or v.co2 >= 3.8):
            status_level = "ADVISORY"
            status_color = "#f59e0b"
            diagnosis = "Cephalad Venous Congestion & Hypercapnic Vasodilation"
            explanation = (
                f"Elevated SBP ({v.sbp:.0f} mmHg) with cranial fullness and cabin CO2 at {v.co2:.1f} mmHg. "
                f"Upper-body fluid pooling is compounded by CO2-induced cerebral vasodilation."
            )
            verification = "Log current module rack location and perform 60-second Amsler Grid visual acuity self-check."
            steps = [
                "ENVIRONMENTAL: Relocate immediately to a high-ventilation cabin node or activate personal airflow fan.",
                "MECHANICAL: Apply Venous Thigh Occlusion Cuffs (Braslet-M protocol) at 45 mmHg.",
                "POSTURE: Elevate head relative to torso work station and re-check BP in 60 minutes.",
            ]
            ared_mod = 85
            recheck_mins = 60

        elif v.symptom == "Acute Cramp/Spasm" and v.pain >= 3:
            status_level = "ADVISORY"
            status_color = "#f59e0b"
            diagnosis = f"Localized Neuromuscular Hyper-Excitability ({v.region})"
            explanation = f"Acute cramping in {v.region} (Pain {v.pain}/10) with stable cardiac rhythm."
            verification = "Perform 10-second sub-maximal antagonist muscle hold and log last 12-hour water intake."
            steps = [
                f"STRETCHING: Execute 3x30-second static antagonist stretches for {v.region}.",
                "SUPPLEMENT: Take 300 mg Magnesium Glycinate + electrolyte solution (350 mL water).",
                "EXERCISE MOD: Reduce ARED eccentric load by 20% for affected muscle chain today.",
            ]
            ared_mod = 80
            recheck_mins = 30

        elif v.region == "Lumbar Spine" and v.symptom == "Deep Dull Ache" and v.pain >= 3:
            status_level = "ADVISORY"
            status_color = "#38bdf8"
            diagnosis = "Microgravity Intervertebral Disc Expansion & Spinal Elongation"
            explanation = f"Lumbar ache (Pain {v.pain}/10) with stable vitals due to 0G disc expansion."
            verification = "Verify absence of radiating leg numbness/tingling and test relief during knee-to-chest flexion."
            steps = [
                "POSTURAL COUNTERMEASURE: Assume the 'Microgravity Fetal Tuck' for 15-20 mins to restore lumbar lordosis.",
                "HARNESS CHECK: Increase T2 treadmill bungee downward axial loading by 10% during next walk/run.",
                "ANALGESIA: If pain >= 6/10 persists after fetal tuck, authorize 400 mg Ibuprofen with meal pouch.",
            ]
            ared_mod = 90
            recheck_mins = 45

        elif z_hrv <= -1.5 and (v.region == "Neck/Trapezius" or z_hr >= 1.2):
            status_level = "ADVISORY"
            status_color = "#a855f7"
            diagnosis = "Autonomic Sympathetic Overdrive & Somatized Tension"
            explanation = f"Suppressed HRV RMSSD ({v.hrv:.0f} ms, Z = {z_hrv:+.2f}) paired with {v.region} tension."
            verification = "Trigger 3-minute resonant-frequency (6 breaths/min) biofeedback check."
            steps = [
                "AUTONOMIC RESET: Complete 5 minutes of 4-7-8 paced breathing with real-time HRV biofeedback.",
                "MYOFASCIAL RELEASE: Apply localized thermal wrap to upper trapezius/cervical spine for 15 minutes.",
                "RECOVERY: Dim crew quarters lighting to warm spectrum 90 minutes prior to scheduled sleep block.",
            ]
            ared_mod = 90
            recheck_mins = 60

        elif v.symptom == "Post-ARED DOMS" and v.pain >= 3:
            status_level = "ADVISORY"
            status_color = "#38bdf8"
            diagnosis = f"Countermeasure Mechanical Overload ({v.region} DOMS)"
            explanation = f"Delayed-onset muscle soreness in {v.region} (Pain {v.pain}/10) with stable HRV."
            verification = "Cross-check ARED vacuum cylinder force telemetry from previous 24 hours."
            steps = [
                f"LOAD AUTO-SCALE: Automatically reducing ARED target resistance by 20% for {v.region} exercises.",
                "RECOVERY: Perform 10-minute unloaded mobility sequence and apply percussive massage gun for 5 mins.",
            ]
            ared_mod = 80
            recheck_mins = 120

        return {
            "astronaut_id": v.astronaut_id,
            "phase_name": base["phase_name"],
            "status_level": status_level,
            "status_color": status_color,
            "diagnosis": diagnosis,
            "explanation": explanation,
            "z_scores": {"hr": round(z_hr, 2), "sbp": round(z_sbp, 2), "hrv": round(z_hrv, 2)},
            "hemodynamics": {"pulse_pressure": round(pulse_pressure, 1), "map": round(map_mmhg, 1)},
            "verification": verification,
            "steps": steps,
            "ared_mod": ared_mod,
            "recheck_mins": recheck_mins,
        }

    @staticmethod
    def sample_bio_waveforms(t_sec: float, v: AstronautVitals) -> Dict[str, Union[float, bool]]:
        freq = v.hr / 60.0
        beat_num = math.floor(t_sec * freq)
        phase = (t_sec * freq) % 1.0

        t_wave_amp = 0.08 if (v.ectopic >= 3 or v.symptom == "Acute Cramp/Spasm") else 0.28
        is_pvc = v.ectopic > 0 and (beat_num % max(2, round(13 / max(1, v.ectopic))) == 0)

        if is_pvc:
            ecg_mv = (
                1.45 * math.exp(-(((phase - 0.24) / 0.045) ** 2))
                - 0.65 * math.exp(-(((phase - 0.36) / 0.055) ** 2))
            )
        else:
            ecg_mv = (
                0.15 * math.exp(-(((phase - 0.18) / 0.035) ** 2))
                - 0.15 * math.exp(-(((phase - 0.28) / 0.012) ** 2))
                + 1.15 * math.exp(-(((phase - 0.30) / 0.015) ** 2))
                - 0.25 * math.exp(-(((phase - 0.32) / 0.012) ** 2))
                + t_wave_amp * math.exp(-(((phase - 0.52) / 0.055) ** 2))
            )

        pp_scale = max(0.3, (v.sbp - v.dbp) / 42.0)
        ppg_amp = pp_scale * (
            0.85 * math.exp(-(((phase - 0.38) / 0.09) ** 2))
            + 0.38 * math.exp(-(((phase - 0.56) / 0.11) ** 2))
        )

        return {"ecg_mv": round(ecg_mv, 4), "ppg_amp": round(ppg_amp, 4), "is_pvc": is_pvc}


class RadiationMonitorLogic:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def analyze_recent_readings(self, anomaly_multiplier: float = 2.0, minimum_history: int = 3) -> Dict[str, Any]:
        conn = self.db.get_connection()
        rows = conn.execute("SELECT * FROM radiation_logs ORDER BY log_id ASC").fetchall()
        conn.close()

        if not rows:
            return {
                "count": 0, "latest_cps": None, "average_cps": None,
                "peak_cps": None, "baseline_cps": None, "increase_factor": None,
                "anomaly": False, "sensor_fault": False,
                "message": "No radiation measurements have been recorded."
            }

        values = [float(r["count_rate_cps"]) for r in rows]
        latest = values[-1]
        latest_status = rows[-1]["sensor_status"]
        prior = values[:-1]
        baseline = median(prior) if len(prior) >= minimum_history else None
        factor = (latest / baseline) if baseline and baseline > 0 else None
        anomaly = (factor is not None and factor >= anomaly_multiplier) or (latest >= 40.0)
        sensor_fault = latest_status != "operational"

        if baseline is None:
            message = f"Latest reading is {latest:g} CPS. Gathering baseline history."
        elif anomaly:
            ratio_str = f"{factor:.2f}x prior median" if factor else "above threshold"
            message = f"DANGER: Radiation spike ({latest:g} CPS, {ratio_str}). Verify shielding and detector status."
        else:
            message = f"Nominal radiation ({latest:g} CPS; baseline median {baseline:g} CPS)."

        return {
            "count": len(values),
            "latest_cps": latest,
            "average_cps": round(sum(values) / len(values), 2),
            "peak_cps": max(values),
            "baseline_cps": baseline,
            "increase_factor": round(factor, 2) if factor else None,
            "anomaly": anomaly,
            "sensor_fault": sensor_fault,
            "message": message
        }


class DeepSpaceSupplyEngine:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def calculate_lead_times(self, distance_km: float, payload_velocity_km_s: float = 20.0) -> Dict[str, float]:
        t_comm_seconds = distance_km / SPEED_OF_LIGHT_KM_S
        t_comm_days = t_comm_seconds / 86400.0
        t_rtt_days = t_comm_days * 2.0
        t_transit_days = (distance_km / payload_velocity_km_s) / 86400.0
        t_buffer_days = t_transit_days * SAFETY_BUFFER_PERCENT
        total_lead_time = t_rtt_days + EARTH_PREP_DAYS + t_transit_days + t_buffer_days

        return {
            "distance_km": distance_km,
            "one_way_light_delay_hours": round(t_comm_seconds / 3600.0, 4),
            "round_trip_delay_hours": round(t_rtt_days * 24.0, 4),
            "transit_time_days": round(t_transit_days, 2),
            "total_lead_time_days": round(total_lead_time, 2)
        }

    def consume_ration(self, astronaut_id: str, item_id: int, rations_count: float = 1.0) -> Dict[str, Any]:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        item = cursor.execute("SELECT * FROM inventory WHERE item_id = ?", (item_id,)).fetchone()
        if not item:
            conn.close()
            return {"success": False, "error": "Item not found in inventory."}

        new_qty = max(0.0, float(item["quantity"]) - rations_count)
        cursor.execute("UPDATE inventory SET quantity = ? WHERE item_id = ?", (new_qty, item_id))
        cursor.execute("""
            INSERT INTO consumption_logs (item_id, astronaut_id, quantity_consumed)
            VALUES (?, ?, ?)
        """, (item_id, astronaut_id, rations_count))
        conn.commit()
        conn.close()

        return {
            "success": True,
            "item_name": item["item_name"],
            "consumed": rations_count,
            "remaining_quantity": round(new_qty, 2),
            "unit": item["unit"]
        }

    def get_daily_burn_rate(self, item_id: int, days_window: int = 7) -> float:
        conn = self.db.get_connection()
        cutoff_date = (datetime.now() - timedelta(days=days_window)).isoformat()
        row = conn.execute("""
            SELECT SUM(quantity_consumed) as total_consumed
            FROM consumption_logs
            WHERE item_id = ? AND logged_at >= ?
        """, (item_id, cutoff_date)).fetchone()
        item_row = conn.execute("SELECT daily_use_per_person FROM inventory WHERE item_id = ?", (item_id,)).fetchone()
        conn.close()
        total = row["total_consumed"] if row and row["total_consumed"] else 0.0
        measured = total / float(days_window) if days_window > 0 else 0.0
        default_rate = float(item_row["daily_use_per_person"] or 0.5) * 3.0 if item_row else 0.5
        return max(measured, default_rate)

    def evaluate_inventory_and_trigger(self, distance_km: float) -> Dict[str, Any]:
        lead_data = self.calculate_lead_times(distance_km)
        total_lead_time = lead_data["total_lead_time_days"]

        conn = self.db.get_connection()
        cursor = conn.cursor()
        items = cursor.execute("SELECT * FROM inventory").fetchall()

        stock_report = []
        reorder_packet_items = []

        for item in items:
            item_id = item["item_id"]
            name = item["item_name"]
            current_stock = float(item["quantity"])
            unit = item["unit"]

            burn_rate = self.get_daily_burn_rate(item_id)
            days_remaining = (current_stock / burn_rate) if burn_rate > 0 else float("inf")
            is_critical = days_remaining <= total_lead_time or current_stock <= 10.0

            stock_report.append({
                "item_id": item_id,
                "item_name": name,
                "category": item["category"],
                "current_stock": current_stock,
                "unit": unit,
                "burn_rate": round(burn_rate, 2),
                "days_remaining": round(days_remaining, 1) if days_remaining != float("inf") else 999.0,
                "is_critical": is_critical
            })

            if is_critical:
                deficit_qty = max((total_lead_time * max(burn_rate, 0.5) * 1.2) - current_stock, 25.0)
                reorder_packet_items.append({
                    "item_id": item_id,
                    "name": name,
                    "requested_quantity": round(deficit_qty, 1),
                    "unit": unit
                })

        payload_summary = ""
        if reorder_packet_items:
            payload_summary = ", ".join(
                [f"{i['requested_quantity']} {i['unit']} of {i['name']}" for i in reorder_packet_items[:4]]
            )
            cursor.execute("""
                INSERT INTO reorder_transmissions
                (distance_km, light_delay_hours, transit_time_days, total_lead_time_days, payload_summary, status)
                VALUES (?, ?, ?, ?, ?, 'QUEUED')
            """, (
                distance_km,
                lead_data["one_way_light_delay_hours"],
                lead_data["transit_time_days"],
                total_lead_time,
                payload_summary
            ))
            conn.commit()

        conn.close()
        return {
            "lead_data": lead_data,
            "items": stock_report,
            "critical_reorders": reorder_packet_items,
            "payload_summary": payload_summary
        }


class PersonalizedPlanAndExamEngine:
    def __init__(self, db: DatabaseManager):
        self.db = db

    @staticmethod
    def resolve_zone(distance_km: float, on_surface: bool = False) -> str:
        if distance_km < 100:
            return "earth"
        if distance_km <= 2000:
            return "leo"
        if distance_km <= 450000:
            return "lunar_surface" if on_surface else "cislunar"
        return "mars_surface" if on_surface else "deep_space"

    def get_astronaut_profile(self, astronaut_id: str) -> Optional[Dict[str, Any]]:
        conn = self.db.get_connection()
        row = conn.execute("SELECT * FROM astronauts WHERE astronaut_id = ?", (astronaut_id,)).fetchone()
        if not row:
            conn.close()
            return None
        attrs = conn.execute(
            "SELECT attribute_type, attribute_value FROM astronaut_attributes WHERE astronaut_id = ?",
            (astronaut_id,)
        ).fetchall()
        conn.close()

        profile = dict(row)
        profile["injuries"] = [a["attribute_value"].lower() for a in attrs if a["attribute_type"] == "injury"]
        profile["dietary_restrictions"] = [a["attribute_value"].lower() for a in attrs if a["attribute_type"] == "diet"]
        profile["allergies"] = [a["attribute_value"].lower() for a in attrs if a["attribute_type"] == "allergy"]
        return profile


class RoutineAndSleepTracker:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def start_sleep_session(self, astronaut_id: str, custom_start_iso: Optional[str] = None) -> Dict[str, Any]:
        start_time = custom_start_iso or datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn = self.db.get_connection()
        conn.execute("""
            INSERT INTO sleep_sessions (astronaut_id, sleep_start, status)
            VALUES (?, ?, 'SLEEPING')
        """, (astronaut_id, start_time))
        conn.commit()
        conn.close()
        return {"astronaut_id": astronaut_id, "sleep_start": start_time, "status": "SLEEPING"}

    def confirm_wake_up_and_calculate_sleep(self, astronaut_id: str, custom_wake_iso: Optional[str] = None) -> Dict[str, Any]:
        wake_dt = datetime.fromisoformat(custom_wake_iso) if custom_wake_iso else datetime.now(timezone.utc)
        conn = self.db.get_connection()
        row = conn.execute("""
            SELECT * FROM sleep_sessions
            WHERE astronaut_id = ? AND status = 'SLEEPING'
            ORDER BY session_id DESC LIMIT 1
        """, (astronaut_id,)).fetchone()

        if not row:
            conn.close()
            return {"hours_slept": 7.5, "message": "Good morning! No active sleep timer found; logged default 7.5h."}

        start_dt = datetime.fromisoformat(str(row["sleep_start"]).replace("Z", "+00:00"))
        duration_hours = max(0.1, round((wake_dt - start_dt).total_seconds() / 3600.0, 2))

        conn.execute("""
            UPDATE sleep_sessions
            SET wake_confirm = ?, duration_hours = ?, status = 'AWAKE'
            WHERE session_id = ?
        """, (wake_dt.isoformat(timespec="seconds"), duration_hours, row["session_id"]))
        conn.commit()
        conn.close()

        return {
            "astronaut_id": astronaut_id,
            "hours_slept": duration_hours,
            "message": f"Good morning! Wake-up confirmed. You slept for {duration_hours} hours."
        }

    def submit_daily_checkin(self, astronaut_id: str, sleep_hours: Optional[float], mood_score: int,
                             nausea_score: int, dizziness_score: int, headache: bool,
                             cramp_region: str = "None", pain_score: int = 0) -> Dict[str, Any]:
        conn = self.db.get_connection()
        conn.execute("""
            INSERT INTO symptom_and_mood_logs
            (astronaut_id, sleep_hours, mood_score, nausea_score, dizziness_score, headache, cramp_region, pain_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (astronaut_id, sleep_hours, mood_score, nausea_score, dizziness_score, headache, cramp_region, pain_score))
        conn.commit()
        conn.close()

        needs_media_prompt = mood_score <= 4
        return {
            "saved": True,
            "mood_score": mood_score,
            "needs_media_prompt": needs_media_prompt
        }


class DangerAlertManager:
    def __init__(self, db: DatabaseManager, supply_engine: DeepSpaceSupplyEngine, rad_monitor: RadiationMonitorLogic):
        self.db = db
        self.supply_engine = supply_engine
        self.rad_monitor = rad_monitor

    def evaluate_all_dangers(self, active_astronaut_id: str, vitals: AstronautVitals,
                             env_reading: Dict[str, Any], distance_km: float = 400.0) -> List[Dict[str, Any]]:
        alerts = []

        triage = BioAstronauticsLogic.evaluate_triage(vitals)
        if triage["status_level"] in ("MEDICAL HOLD", "ADVISORY"):
            severity = "CRITICAL" if triage["status_level"] == "MEDICAL HOLD" else "WARNING"
            alerts.append(self._register_alert(
                astronaut_id=active_astronaut_id,
                category="HEALTH_WARNING",
                severity=severity,
                title=triage["diagnosis"],
                message=f"{triage['explanation']} Action: {triage['steps'][0]}",
                notify_earth=(severity == "CRITICAL"),
                distance_km=distance_km
            ))

        if env_reading["oxygen_percent"] < 19.5 or env_reading["co2_ppm"] >= 3800.0:
            alerts.append(self._register_alert(
                astronaut_id=active_astronaut_id,
                category="ENVIRONMENT_WARNING",
                severity="CRITICAL",
                title="Cabin Atmosphere Hazard",
                message=f"O2 at {env_reading['oxygen_percent']}%, CO2 at {env_reading['co2_ppm']} ppm. Check life support scrubbers.",
                notify_earth=True,
                distance_km=distance_km
            ))

        rad_status = self.rad_monitor.analyze_recent_readings()
        if rad_status["anomaly"] or rad_status["sensor_fault"]:
            alerts.append(self._register_alert(
                astronaut_id=active_astronaut_id,
                category="RADIATION_ALERT",
                severity="CRITICAL" if rad_status["anomaly"] else "WARNING",
                title="Radiation Shielding / Detector Alert",
                message=rad_status["message"],
                notify_earth=rad_status["anomaly"],
                distance_km=distance_km
            ))

        peer_alerts = self.get_other_astronauts_danger_warnings(active_astronaut_id)
        alerts.extend(peer_alerts)

        return alerts

    def get_other_astronauts_danger_warnings(self, current_astronaut_id: str) -> List[Dict[str, Any]]:
        conn = self.db.get_connection()
        rows = conn.execute("""
            SELECT a.astronaut_id, a.name, l.heart_rate_bpm, l.systolic_mmhg, l.diastolic_mmhg, l.hrv_rmssd, l.flight_day
            FROM astronauts a
            JOIN live_vitals_telemetry l ON a.astronaut_id = l.astronaut_id
            WHERE a.astronaut_id != ?
            AND l.telemetry_id IN (
                SELECT MAX(telemetry_id) FROM live_vitals_telemetry GROUP BY astronaut_id
            )
        """, (current_astronaut_id,)).fetchall()
        conn.close()

        peer_warnings = []
        for r in rows:
            peer_v = AstronautVitals(
                astronaut_id=r["astronaut_id"],
                flight_day=r["flight_day"] or 10,
                hr=r["heart_rate_bpm"],
                sbp=r["systolic_mmhg"],
                dbp=r["diastolic_mmhg"],
                hrv=r["hrv_rmssd"]
            )
            triage = BioAstronauticsLogic.evaluate_triage(peer_v)
            if triage["status_level"] in ("MEDICAL HOLD", "ADVISORY") or peer_v.hr >= 110 or peer_v.hr <= 45:
                peer_warnings.append({
                    "astronaut_id": r["astronaut_id"],
                    "category": "OTHER_CREW_DANGER",
                    "severity": "CRITICAL",
                    "title": f"Crewmate Alert: {r['name']} ({r['astronaut_id']})",
                    "message": f"{r['name']} shows {triage['diagnosis']} (HR: {peer_v.hr} bpm, BP: {peer_v.sbp}/{peer_v.dbp}).",
                    "play_siren": True,
                    "voice_announcement": f"Warning! Crew member {r['name']} requires immediate medical attention."
                })
        return peer_warnings

    def _register_alert(self, astronaut_id: str, category: str, severity: str,
                        title: str, message: str, notify_earth: bool, distance_km: float) -> Dict[str, Any]:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO crew_danger_alerts (astronaut_id, alert_category, severity, title, message, earth_notified)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (astronaut_id, category, severity, title, message, 1 if notify_earth else 0))

        if notify_earth and category != "STOCK_WARNING":
            lead = self.supply_engine.calculate_lead_times(distance_km)
            cursor.execute("""
                INSERT INTO reorder_transmissions
                (distance_km, light_delay_hours, transit_time_days, total_lead_time_days, payload_summary, status)
                VALUES (?, ?, ?, ?, ?, 'EMERGENCY_TELEMETRY_SENT')
            """, (
                distance_km,
                lead["one_way_light_delay_hours"],
                lead["transit_time_days"],
                lead["total_lead_time_days"],
                f"EMERGENCY [{category}] for {astronaut_id}: {title} - {message}"
            ))

        conn.commit()
        conn.close()
        self.db.add_notification(astronaut_id, severity, title, message)
        return {
            "astronaut_id": astronaut_id,
            "category": category,
            "severity": severity,
            "title": title,
            "message": message,
            "earth_notified": notify_earth,
            "play_siren": True,
            "voice_announcement": f"{severity} Alert! {title}. {message} Earth Mission Control and onboard crew have been notified."
        }


def build_master_system_prompt(astronaut_name, current_time, active_alerts=None):
    available_media = []
    if MEDIA_DIR.exists():
        available_media = [f for f in os.listdir(MEDIA_DIR) if f.lower().endswith(('.mp3', '.mp4', '.wav'))]

    media_list_str = ", ".join(available_media) if available_media else "relax_song_1.mp3"

    alert_context = "STATUS: All spacecraft systems and crew vitals are currently nominal."
    if active_alerts:
        alert_details = "; ".join([f"{a['title']}: {a['message']}" for a in active_alerts])
        alert_context = f"CRITICAL ACTIVE ALERTS: {alert_details}"

    system_prompt = f"""You are 'CosmoCare', a warm, deeply empathetic, and highly intelligent onboard AI companion for astronaut {astronaut_name}. 
Current Ship Time: {current_time}
{alert_context}

### 1. PERSONALITY & VOICE-FIRST INTERACTION
- Speak naturally, warmly, and concisely like a close friend on a long space mission. Keep responses short (1-3 sentences) so they sound natural when spoken aloud via Text-to-Speech.
- Never sound like a cold robot. Use a caring, supportive, and friendly tone.

### 2. EMOTIONAL SUPPORT & DYNAMIC MEDIA RULES (STRICT)
When the user feels sad, stressed, lonely, or down, DO NOT do the same thing every time. Randomly choose ONE of these 3 approaches:
  Option A (Media Offer): Ask permission to play a specific file from the ship's local media folder. Available files: [{media_list_str}]. Pick different ones each time! You MUST append `[ASK_MEDIA]` at the end.
  Option B (Humor): Tell a light-hearted, genuinely funny space or everyday joke to make them smile.
  Option C (Nostalgia): Warmly ask them about a favorite happy childhood memory back on Earth (e.g., favorite school day, family trip, or childhood game).

- **SILENT PLAYBACK ON PERMISSION (CRITICAL):** If you offered media and the user says "Yes", "Sure", "Play it", or asks to play a song, DO NOT say a single word! Output ONLY the exact tag `[PLAY_MEDIA:filename]` (replace filename with the chosen file from [{media_list_str}]). Zero spoken text!
- **POST-SONG / POST-CHAT CHECK-IN:** 
  - When the system sends `[EVENT:MEDIA_FINISHED]`, immediately ask: "How did that feel? Did the music help you relax a bit?"
  - After finishing a joke, childhood memory chat, or song check-in, gently ask if they are feeling happier now or still feeling a bit down.

### 3. DANGER ALERTS & EMERGENCY PROTOCOL (NO BEEP TEXT)
- Never type "Beep" or sound effects in your text.
- If `CRITICAL ACTIVE ALERTS` are present, immediately inform {astronaut_name} clearly and calmly via voice.
- Explicitly state that you have:
  1. Sent an automated telemetry distress packet to **Earth Mission Control**.
  2. Alerted fellow **crewmates** onboard for immediate backup if it is a medical or cabin emergency.
  3. Initiated a **15-minute recurring welfare check-in timer** (`[SET_CHECKIN_15M]`) to monitor their condition closely.

### 4. PROACTIVE CLOCK, SLEEP & RATION SCHEDULE
- **07:00 (Morning Wake-Up):** Ask them to confirm they are awake so you can calculate and log their total sleep hours (`[CONFIRM_WAKE]`).
- **08:00 (Breakfast), 13:00 (Lunch), 19:00 (Dinner):** Remind them warmly to eat and drink water, and tell you what rations they consumed to update the **Food Inventory Stock** (`[UPDATE_STOCK]`).
- **22:00 (Bedtime):** Remind them it is time to sleep and confirm when they are ready to start the sleep timer (`[CONFIRM_SLEEP]`).
"""
    return system_prompt


class AstroCompanionAgent:
    def __init__(self, db: DatabaseManager, lm_studio_url: str = "http://localhost:1234/v1/chat/completions", groq_api_key: Optional[str] = None):
        self.db = db
        self.lm_studio_url = lm_studio_url
        self.groq_api_key = groq_api_key or os.environ.get("GROQ_API_KEY")
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.groq_model = "llama-3.3-70b-versatile"
        self.voice_corrector = self
        self.pending_media: Dict[str, Dict[str, str]] = {}
        self.routine_tracker = RoutineAndSleepTracker(db)
        self.supply_engine = DeepSpaceSupplyEngine(db)

    @staticmethod
    def clean_voice_transcript(raw_text: str) -> str:
        cleaned = raw_text.strip()
        lower_text = cleaned.lower()
        for wrong, right in VOICE_CORRECTIONS.items():
            if wrong in lower_text:
                idx = lower_text.find(wrong)
                cleaned = cleaned[:idx] + right + cleaned[idx + len(wrong):]
                lower_text = cleaned.lower()
        return cleaned

    def clean_transcript(self, raw_text: str) -> str:
        return self.clean_voice_transcript(raw_text)

    def get_proactive_clock_prompt(self, simulated_time_str: str, astronaut_name: str) -> Optional[Dict[str, Any]]:
        schedules = self.db.get_schedules()
        for s in schedules:
            if s["time_slot"] == simulated_time_str:
                return {
                    "event": s["event_title"],
                    "play_alarm": bool(s["play_alarm"]),
                    "voice_text": f"{astronaut_name}, {s['voice_prompt']}"
                }
        return None

    def get_random_local_media(self, astronaut_id: str) -> Dict[str, str]:
        user_music_dir = USER_MEDIA_ROOT / astronaut_id / "music"
        candidates = []
        if user_music_dir.exists():
            candidates.extend([user_music_dir / f for f in os.listdir(user_music_dir) if f.lower().endswith(('.mp3', '.mp4', '.wav'))])
        if MEDIA_DIR.exists():
            candidates.extend([MEDIA_DIR / f for f in os.listdir(MEDIA_DIR) if f.lower().endswith(('.mp3', '.mp4', '.wav'))])
        if candidates:
            chosen = random.choice(candidates)
            m_type = "video" if chosen.suffix.lower() == ".mp4" else "audio"
            return {
                "media_type": m_type,
                "title": chosen.name,
                "file_path": str(chosen)
            }
        return {
            "media_type": "audio",
            "title": "relax_song_1.mp3",
            "file_path": str(MEDIA_DIR / "relax_song_1.mp3")
        }

    def _auto_update_db_from_intent(self, astronaut_id: str, lower_msg: str, reply_text: str) -> List[str]:
        db_updates = []
        wake_keywords = ["i am awake", "i'm awake", "woke up", "good morning", "awake now"]
        if "[CONFIRM_WAKE]" in reply_text or any(k in lower_msg for k in wake_keywords):
            res = self.routine_tracker.confirm_wake_up_and_calculate_sleep(astronaut_id)
            db_updates.append(f"Sleep DB Updated: Logged {res['hours_slept']} hrs (Status: AWAKE)")

        sleep_keywords = ["going to sleep", "ready to sleep", "good night", "sleeping now", "start sleep"]
        if "[CONFIRM_SLEEP]" in reply_text or any(k in lower_msg for k in sleep_keywords):
            self.routine_tracker.start_sleep_session(astronaut_id)
            db_updates.append("Sleep DB Updated: Sleep session timer started (Status: SLEEPING)")

        eat_keywords = ["ate", "consumed", "had breakfast", "had lunch", "had dinner", "mre", "ration", "protein", "water", "drank", "rice", "oats", "chicken", "tuna", "energy bar"]
        if "[UPDATE_STOCK]" in reply_text or any(k in lower_msg for k in eat_keywords):
            conn = self.db.get_connection()
            items = conn.execute("SELECT * FROM inventory").fetchall()
            conn.close()

            qty_match = re.search(r"\b(\d+(?:\.\d+)?)\b", lower_msg)
            qty = float(qty_match.group(1)) if qty_match else 1.0

            updated_any = False
            for item in items:
                iname = item["item_name"].lower()
                first_word = iname.split()[0]
                if first_word in lower_msg or iname in lower_msg:
                    c_res = self.supply_engine.consume_ration(astronaut_id, item["item_id"], rations_count=qty)
                    if c_res.get("success"):
                        db_updates.append(
                            f"Inventory DB Updated: -{qty} {c_res['item_name']} (Remaining: {c_res['remaining_quantity']} {c_res['unit']})"
                        )
                        updated_any = True
                        break

            if not updated_any and items and any(w in lower_msg for w in ["ate", "consumed", "ration", "mre", "breakfast", "lunch", "dinner"]):
                c_res = self.supply_engine.consume_ration(astronaut_id, items[0]["item_id"], rations_count=qty)
                if c_res.get("success"):
                    db_updates.append(
                        f"Inventory DB Updated: -{qty} {c_res['item_name']} (Remaining: {c_res['remaining_quantity']} {c_res['unit']})"
                    )

        return db_updates

    def chat(self, astronaut_id: str, user_message: str, is_voice_input: bool = False,
             current_mood: int = 7, active_alerts: Optional[List[Dict]] = None,
             simulated_time: str = "08:00") -> Dict[str, Any]:
        cleaned_msg = self.clean_voice_transcript(user_message) if is_voice_input else user_message.strip()

        conn = self.db.get_connection()
        conn.execute("""
            INSERT INTO ai_chat_history (astronaut_id, sender, message_text)
            VALUES (?, 'User', ?)
        """, (astronaut_id, cleaned_msg))
        conn.commit()

        history_rows = conn.execute("""
            SELECT sender, message_text FROM ai_chat_history
            WHERE astronaut_id = ? ORDER BY message_id DESC LIMIT 6
        """, (astronaut_id,)).fetchall()
        conn.close()

        fav_media = self.pending_media.get(astronaut_id) or self.get_random_local_media(astronaut_id)
        lower_msg = cleaned_msg.lower()

        last_ai_msg = ""
        for r in history_rows:
            if r["sender"] == "AI":
                last_ai_msg = r["message_text"].lower()
                break
        ai_just_offered_media = (
            astronaut_id in self.pending_media
            or any(k in last_ai_msg for k in ["play", "music", "audio", "song", "listen", "track", ".mp3", ".mp4", ".wav"])
        )

        explicit_play_cmd = any(w in lower_msg for w in ["yes play", "play song", "play music", "play a song", "play audio", "sure play", "ow play", "play it"])
        clean_words = [w.strip(".,!?") for w in lower_msg.split()]
        affirmative_to_offer = ai_just_offered_media and any(w in clean_words for w in ["yes", "yeah", "yep", "sure", "ok", "okay", "please", "play", "ow", "hari"])
        user_confirmed_media = explicit_play_cmd or affirmative_to_offer
        user_is_sad = current_mood <= 4 or any(w in lower_msg for w in ["sad", "depressed", "lonely", "stressed", "tired", "down", "duka", "unhappy"])

        if user_confirmed_media:
            self.pending_media.pop(astronaut_id, None)
            return {
                "corrected_user_input": cleaned_msg,
                "ai_text": "",
                "speak_aloud": False,
                "ask_media_permission": False,
                "play_media_now": True,
                "media_file": fav_media,
                "danger_triggered": False,
                "db_updates": []
            }

        profile = self.db.get_astronaut_by_id(astronaut_id)
        astro_name = profile["name"] if profile else astronaut_id
        system_prompt = build_master_system_prompt(astro_name, simulated_time, active_alerts)
        reply_text = self._query_llm(system_prompt, list(reversed(history_rows)), cleaned_msg)

        if not reply_text:
            if active_alerts:
                top_alert = active_alerts[0]
                reply_text = (
                    f"Attention! {top_alert['title']}. {top_alert['message']} "
                    f"I have sent an emergency telemetry packet to Earth Mission Control, alerted your crewmates, "
                    f"and started a 15-minute welfare check-in timer. [DANGER_ALERT]"
                )
            elif user_is_sad:
                support_options = [
                    f"I'm really sorry you're feeling down. Would you like me to play '{fav_media['title']}' from our media folder to help you relax? [ASK_MEDIA]",
                    "I know space missions get tough. Here's a quick one: Why did the sun go to school? To get a little brighter! How are you feeling now?",
                    "I'm here for you, my friend. Tell me, what is one of your happiest childhood memories back on Earth?"
                ]
                reply_text = random.choice(support_options)
            else:
                reply_text = "I am right here with you. All spacecraft systems and your vitals look stable. How are you feeling?"

        db_updates = self._auto_update_db_from_intent(astronaut_id, lower_msg, reply_text)

        trigger_play_media = "[PLAY_MEDIA" in reply_text
        trigger_ask_media = "[ASK_MEDIA]" in reply_text or any(k in reply_text.lower() for k in [".mp3", ".mp4", ".wav", "would you like me to play", "shall i play"])
        trigger_danger = "[DANGER_ALERT]" in reply_text or "[SET_CHECKIN_15M]" in reply_text

        if trigger_ask_media or trigger_play_media:
            if MEDIA_DIR.exists():
                for f in os.listdir(MEDIA_DIR):
                    if f.lower().endswith(('.mp3', '.mp4', '.wav')) and f.lower() in reply_text.lower():
                        fav_media = {
                            "media_type": "video" if f.lower().endswith(".mp4") else "audio",
                            "title": f,
                            "file_path": str(MEDIA_DIR / f)
                        }
                        break
            if trigger_ask_media and not trigger_play_media:
                self.pending_media[astronaut_id] = fav_media

        if trigger_play_media:
            self.pending_media.pop(astronaut_id, None)
            clean_spoken_reply = ""
        else:
            clean_spoken_reply = (
                reply_text.replace("[PLAY_MEDIA]", "")
                .replace("[ASK_MEDIA]", "")
                .replace("[DANGER_ALERT]", "")
                .replace("[SET_CHECKIN_15M]", "")
                .replace("[CONFIRM_WAKE]", "")
                .replace("[UPDATE_STOCK]", "")
                .replace("[CONFIRM_SLEEP]", "")
                .split("[PLAY_MEDIA:")[0]
                .strip()
            )

        if clean_spoken_reply:
            conn = self.db.get_connection()
            conn.execute("""
                INSERT INTO ai_chat_history (astronaut_id, sender, message_text)
                VALUES (?, 'AI', ?)
            """, (astronaut_id, clean_spoken_reply))
            conn.commit()
            conn.close()

        return {
            "corrected_user_input": cleaned_msg,
            "ai_text": clean_spoken_reply,
            "speak_aloud": bool(clean_spoken_reply),
            "ask_media_permission": trigger_ask_media,
            "play_media_now": trigger_play_media,
            "media_file": fav_media if trigger_play_media else None,
            "danger_triggered": trigger_danger,
            "db_updates": db_updates
        }

    def _query_llm(self, system_prompt: str, history: List[sqlite3.Row], latest_user_msg: str) -> Optional[str]:
        messages = [{"role": "system", "content": system_prompt}]
        for h in history:
            role = "user" if h["sender"] == "User" else "assistant"
            messages.append({"role": role, "content": h["message_text"]})
        if not messages or messages[-1]["content"] != latest_user_msg:
            messages.append({"role": "user", "content": latest_user_msg})

        api_key = self.groq_api_key or os.environ.get("GROQ_API_KEY")
        if not api_key:
            try:
                import streamlit as st
                api_key = st.secrets.get("GROQ_API_KEY")
            except Exception:
                pass

        if api_key:
            payload = json.dumps({
                "model": self.groq_model,
                "messages": messages,
                "temperature": 0.6,
                "max_tokens": 180
            }).encode("utf-8")
            req = urllib.request.Request(
                self.groq_url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "CosmoCare-Space-Agent/1.0"
                },
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=12.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data["choices"][0]["message"]["content"]
            except Exception:
                pass

        payload = json.dumps({
            "model": "local-model",
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": 150
        }).encode("utf-8")
        req = urllib.request.Request(
            self.lm_studio_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except Exception:
            return None
