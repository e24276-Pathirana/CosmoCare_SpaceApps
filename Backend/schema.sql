PRAGMA foreign_keys = ON;

CREATE TABLE astronauts (
    astronaut_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER NOT NULL,
    sex TEXT NOT NULL,
    height_cm REAL NOT NULL,
    weight_kg REAL NOT NULL,
    fitness_level TEXT NOT NULL,
    mission_duration_days INTEGER NOT NULL
);

CREATE TABLE astronaut_attributes (
    attribute_id INTEGER PRIMARY KEY AUTOINCREMENT,
    astronaut_id TEXT NOT NULL,
    attribute_type TEXT NOT NULL,
    attribute_value TEXT NOT NULL,
    FOREIGN KEY (astronaut_id) REFERENCES astronauts(astronaut_id) ON DELETE CASCADE
);

CREATE TABLE inventory (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    unit_mass_kg REAL NOT NULL,
    expiration_date TEXT NOT NULL
);

CREATE TABLE nutritional_metadata (
    meta_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    calories_per_unit REAL DEFAULT 0.0,
    protein_g_per_unit REAL DEFAULT 0.0,
    carbs_g_per_unit REAL DEFAULT 0.0,
    fat_g_per_unit REAL DEFAULT 0.0,
    water_ml_per_unit REAL DEFAULT 0.0,
    FOREIGN KEY (item_id) REFERENCES inventory(item_id) ON DELETE CASCADE
);

CREATE TABLE consumption_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    astronaut_id TEXT NOT NULL,
    quantity_consumed REAL NOT NULL,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES inventory(item_id) ON DELETE CASCADE,
    FOREIGN KEY (astronaut_id) REFERENCES astronauts(astronaut_id) ON DELETE CASCADE
);

CREATE TABLE reorder_transmissions (
    transmission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    transmitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    distance_km REAL NOT NULL,
    light_delay_hours REAL NOT NULL,
    transit_time_days REAL NOT NULL,
    total_lead_time_days REAL NOT NULL,
    payload_summary TEXT NOT NULL,
    status TEXT DEFAULT 'QUEUED'
);

CREATE TABLE live_vitals_telemetry (
    telemetry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    astronaut_id TEXT NOT NULL,
    heart_rate_bpm REAL,
    systolic_mmhg REAL,
    diastolic_mmhg REAL,
    hrv_rmssd REAL,
    flight_day INTEGER,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (astronaut_id) REFERENCES astronauts(astronaut_id) ON DELETE CASCADE
);

CREATE TABLE symptom_and_mood_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    astronaut_id TEXT NOT NULL,
    sleep_hours REAL,
    mood_score INTEGER,
    nausea_score INTEGER,
    dizziness_score INTEGER,
    headache BOOLEAN,
    cramp_region TEXT,
    pain_score INTEGER,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (astronaut_id) REFERENCES astronauts(astronaut_id) ON DELETE CASCADE
);

CREATE TABLE environment_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    oxygen_percent REAL,
    co2_ppm REAL,
    temperature_c REAL,
    humidity_percent REAL,
    pressure_kpa REAL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE radiation_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    detector_id TEXT NOT NULL,
    radiation_type TEXT,
    count_rate_cps REAL,
    sensor_status TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE media_preferences (
    preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
    astronaut_id TEXT NOT NULL,
    media_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    mood_category TEXT,
    FOREIGN KEY (astronaut_id) REFERENCES astronauts(astronaut_id) ON DELETE CASCADE
);

CREATE TABLE ai_chat_history (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    astronaut_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    message_text TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (astronaut_id) REFERENCES astronauts(astronaut_id) ON DELETE CASCADE
);