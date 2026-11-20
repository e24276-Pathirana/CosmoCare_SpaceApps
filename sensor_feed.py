import time
import json
import random
import urllib.request
from datetime import datetime, timezone

# ==========================================================
# DEVELOPER TEST VARIABLES (මෙතන අගයන් වෙනස් කරලා Test කරන්න)
# ==========================================================
SERVER_URL = "http://127.0.0.1:8000/api/ingest_telemetry"
ASTRONAUT_ID = "A004"      # A004, A005, හෝ A006
INTERVAL_SECONDS = 2.0     # තත්පර කීයකට සැරයක් data යවන්නද

# Biometric Vitals
BASE_HR = 71.0             # Heart Rate (bpm) -> Arrhythmia test: 108.0
BASE_SBP = 120.0           # Systolic BP (mmHg) -> Hypovolemia test: 100.0
BASE_DBP = 77.0            # Diastolic BP (mmHg)
BASE_HRV = 47.0            # HRV RMSSD (ms) -> Stress/Arrhythmia test: 20.0
ECTOPIC_BEATS = 0          # 0 = Normal, 3+ = MEDICAL HOLD
PAIN_SCORE = 0             # 0 - 10
DIZZY = False              # True / False
HEADACHE = False           # True / False

# Cabin Environment & Radiation
OXYGEN_PERCENT = 20.9      # Normal: 20.6 - 21.2 | Danger: < 19.5
CO2_PPM = 980.0            # Normal: ~1000 | Danger: >= 3800
TEMPERATURE_C = 21.5       # Cabin Temp (°C)
RADIATION_CPS = 11.0       # Normal: 8 - 14 | Spike Danger: >= 45.0

# ස්වභාවිකව පොඩි වෙනස්වීම් (Jitter) එන්න ඕනේ නම් True තියන්න
ENABLE_LIVE_JITTER = True
# ==========================================================


def generate_packet():
    jitter = 1.0 if ENABLE_LIVE_JITTER else 0.0
    return {
        "astronaut_id": ASTRONAUT_ID,
        "hr": round(BASE_HR + random.uniform(-1.5, 1.5) * jitter, 1),
        "sbp": round(BASE_SBP + random.uniform(-1.5, 1.5) * jitter, 1),
        "dbp": round(BASE_DBP + random.uniform(-1.0, 1.0) * jitter, 1),
        "hrv": round(BASE_HRV + random.uniform(-2.0, 2.0) * jitter, 1),
        "ectopic": ECTOPIC_BEATS,
        "pain": PAIN_SCORE,
        "dizzy": DIZZY,
        "headache": HEADACHE,
        "oxygen_percent": round(OXYGEN_PERCENT + random.uniform(-0.05, 0.05) * jitter, 2),
        "co2_ppm": round(CO2_PPM + random.uniform(-15.0, 15.0) * jitter, 1),
        "temperature_c": round(TEMPERATURE_C + random.uniform(-0.1, 0.1) * jitter, 1),
        "radiation_cps": round(RADIATION_CPS + random.uniform(-0.8, 0.8) * jitter, 2),
    }


def main():
    print(f"🛰️ Live Sensor Feed Started for {ASTRONAUT_ID} -> {SERVER_URL}")
    print("Press CTRL+C to stop.\n")
    while True:
        packet = generate_packet()
        data = json.dumps(packet).encode("utf-8")
        req = urllib.request.Request(
            SERVER_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(
                    f"[{ts}] Sent -> HR:{packet['hr']} | BP:{packet['sbp']}/{packet['dbp']} | "
                    f"CO2:{packet['co2_ppm']}ppm | RAD:{packet['radiation_cps']}cps | "
                    f"Alerts: {result.get('alerts_count', 0)}"
                )
        except Exception as e:
            print(f"⚠️ Server connection failed: {e}")

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()