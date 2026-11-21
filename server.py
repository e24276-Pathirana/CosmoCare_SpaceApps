import os
import re
import uuid
import tempfile
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import edge_tts
import logic

app = FastAPI()

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

db = logic.DatabaseManager()
sim = logic.SensorSimulator(db)
supply = logic.DeepSpaceSupplyEngine(db)
rad = logic.RadiationMonitorLogic(db)
alerts_mgr = logic.DangerAlertManager(db, supply, rad)
routine = logic.RoutineAndSleepTracker(db)
agent = logic.AstroCompanionAgent(db)

for aid in ("A004", "A005", "A006"):
    db.ensure_user_media_folders(aid)

logic.MEDIA_DIR.mkdir(parents=True, exist_ok=True)

CURRENT_ENV = sim.generate_environment_reading()


class LoginRequest(BaseModel):
    astronaut_id: str
    password: str


class ChatRequest(BaseModel):
    astronaut_id: str
    message: str
    is_voice_input: bool = False


class SimulateRequest(BaseModel):
    astronaut_id: str
    anomaly: Optional[str] = None


class ClockRequest(BaseModel):
    astronaut_id: str
    ship_time: str
    distance_million_km: Optional[float] = None


class RationRequest(BaseModel):
    astronaut_id: str
    item_id: Optional[int] = None
    item_name: Optional[str] = None
    quantity: float = 1.0


class BiometricsRequest(BaseModel):
    astronaut_id: str
    height_cm: float
    weight_kg: float
    age: int
    fitness_level: str


class PasswordRequest(BaseModel):
    astronaut_id: str
    new_password: str


class TTSRequest(BaseModel):
    text: str


class MediaFinishedRequest(BaseModel):
    astronaut_id: str


class DeleteMediaRequest(BaseModel):
    astronaut_id: str
    file_path: str


class EmergencyRequest(BaseModel):
    astronaut_id: str
    action: str

class TelemetryIngestRequest(BaseModel):
    astronaut_id: str = "A004"
    hr: float = 70.0
    sbp: float = 120.0
    dbp: float = 76.0
    hrv: float = 45.0
    ectopic: int = 0
    pain: int = 0
    dizzy: bool = False
    headache: bool = False
    oxygen_percent: float = 20.9
    co2_ppm: float = 980.0
    temperature_c: float = 21.5
    radiation_cps: float = 11.0


def render_page(filename: str) -> HTMLResponse:
    file_path = TEMPLATES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Missing template: {filename}")
    html = file_path.read_text(encoding="utf-8")
    html = re.sub(r"\{\{DATA:SCREEN:SCREEN_\d+\}\}", "#", html)

    # home.html එකේ cosmo_os.js / cosmo_face.js එක්ක ගැටෙන mock scripts අයින් කරනවා
    html = re.sub(r'<script[^>]*id=["\']cosmo-cam-controller["\'][^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<script[^>]*id=["\']dora-controller-script["\'][^>]*>.*?</script>', '', html, flags=re.DOTALL)

    inject_tag = '<script src="/static/cosmo_os.js"></script><script src="/static/cosmo_face.js"></script></body>'
    if "</body>" in html:
        html = html.replace("</body>", inject_tag, 1)
    else:
        html += '<script src="/static/cosmo_os.js"></script><script src="/static/cosmo_face.js"></script>'
    return HTMLResponse(content=html)

@app.get("/")
def root():
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
def page_login():
    return render_page("login.html")


@app.get("/home", response_class=HTMLResponse)
def page_home():
    return render_page("home.html")


@app.get("/devices", response_class=HTMLResponse)
def page_devices():
    return render_page("devices.html")


@app.get("/statistics", response_class=HTMLResponse)
def page_statistics():
    return render_page("statistics.html")


@app.get("/security", response_class=HTMLResponse)
def page_security():
    return render_page("security.html")


@app.get("/rations", response_class=HTMLResponse)
def page_rations():
    return render_page("rations.html")


@app.get("/profile", response_class=HTMLResponse)
def page_profile():
    return render_page("profile.html")


@app.post("/api/login")
def api_login(req: LoginRequest):
    user = db.authenticate_user(req.astronaut_id, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid Astronaut ID or Password")
    return {"success": True, "user": user}


def map_alert_route(category: str, title: str = "") -> str:
    cat = (category or "").upper()
    t = (title or "").lower()
    if "HEALTH" in cat or "triage" in t or "heart" in t or "electrolyte" in t:
        return "/statistics"
    if "ENVIRONMENT" in cat or "cabin" in t or "co2" in t or "airlock" in t:
        return "/devices"
    if "RADIATION" in cat or "SECURITY" in cat or "solar" in t or "distress" in t or "OTHER_CREW" in cat:
        return "/security"
    if "STOCK" in cat or "ration" in t or "sleep" in t:
        return "/rations"
    if "profile" in t or "biometric" in t or "credential" in t:
        return "/profile"
    return "/security"


@app.get("/api/state/{astronaut_id}")
def api_state(astronaut_id: str):
    profile = db.get_astronaut_by_id(astronaut_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Astronaut not found")

    mission_state = db.get_mission_state()
    distance_m_km = float(mission_state.get("distance_million_km", 225.0))
    distance_km = distance_m_km * 1_000_000.0
    vitals = sim.get_latest_vitals(astronaut_id)
    triage = logic.BioAstronauticsLogic.evaluate_triage(vitals)
    derived = db.calculate_derived_biometrics(profile)
    inv_eval = supply.evaluate_inventory_and_trigger(distance_km)
    rad_status = rad.analyze_recent_readings()
    schedules = db.get_schedules()
    notifications = db.get_notifications(astronaut_id, limit=20)
    for n in notifications:
        n["target_route"] = map_alert_route(n.get("severity", ""), n.get("title", ""))

    conn = db.get_connection()
    sleep_logs = [dict(r) for r in conn.execute(
        "SELECT * FROM sleep_sessions WHERE astronaut_id = ? ORDER BY session_id DESC LIMIT 8",
        (astronaut_id,)
    ).fetchall()]
    alert_logs = [dict(r) for r in conn.execute(
        "SELECT * FROM crew_danger_alerts ORDER BY alert_id DESC LIMIT 12"
    ).fetchall()]
    tx_logs = [dict(r) for r in conn.execute(
        "SELECT * FROM reorder_transmissions ORDER BY transmission_id DESC LIMIT 8"
    ).fetchall()]
    chat_rows = [dict(r) for r in conn.execute(
        "SELECT sender, message_text, timestamp FROM ai_chat_history WHERE astronaut_id = ? ORDER BY message_id DESC LIMIT 20",
        (astronaut_id,)
    ).fetchall()]
    vitals_history = [dict(r) for r in conn.execute(
        "SELECT flight_day, heart_rate_bpm, systolic_mmhg, diastolic_mmhg, hrv_rmssd FROM live_vitals_telemetry WHERE astronaut_id = ? ORDER BY telemetry_id DESC LIMIT 7",
        (astronaut_id,)
    ).fetchall()]
    conn.close()

    media_map = db.get_user_media_list(astronaut_id)
    user_media = {
        k: [{"name": p.name, "path": str(p), "size_kb": round(p.stat().st_size / 1024, 1)} for p in v]
        for k, v in media_map.items()
    }

    return {
        "profile": profile,
        "derived": derived,
        "vitals": vitals.__dict__,
        "env": CURRENT_ENV,
        "triage": triage,
        "radiation": rad_status,
        "mission_state": mission_state,
        "schedules": schedules,
        "inventory": inv_eval,
        "sleep_logs": sleep_logs,
        "alert_logs": alert_logs,
        "transmissions": tx_logs,
        "notifications": notifications,
        "chat_history": list(reversed(chat_rows)),
        "vitals_history": list(reversed(vitals_history)),
        "user_media": user_media,
    }


@app.get("/api/waveforms/{astronaut_id}")
def api_waveforms(astronaut_id: str):
    vitals = sim.get_latest_vitals(astronaut_id)
    samples = [logic.BioAstronauticsLogic.sample_bio_waveforms(t * 0.03, vitals) for t in range(120)]
    return {"samples": samples, "hr": vitals.hr, "ectopic": vitals.ectopic}


@app.post("/api/simulate")
def api_simulate(req: SimulateRequest):
    global CURRENT_ENV
    anomaly = None if req.anomaly in (None, "", "None") else req.anomaly
    vitals = sim.generate_live_vitals(
        req.astronaut_id,
        anomaly_mode=anomaly if anomaly in ("arrhythmia", "hypovolemia", "high_co2") else None
    )
    CURRENT_ENV = sim.generate_environment_reading(
        anomaly_mode="cabin_danger" if anomaly == "high_co2" else None
    )
    sim.generate_radiation_reading(spike=(anomaly == "radiation_spike"))
    mission_state = db.get_mission_state()
    distance_km = float(mission_state.get("distance_million_km", 225.0)) * 1_000_000.0
    active_alerts = alerts_mgr.evaluate_all_dangers(req.astronaut_id, vitals, CURRENT_ENV, distance_km=distance_km)
    for a in active_alerts:
        a["target_route"] = map_alert_route(a.get("category", ""), a.get("title", ""))

    voice_announcement = " ".join([a["voice_announcement"] for a in active_alerts if a.get("voice_announcement")])
    return {
        "vitals": vitals.__dict__,
        "env": CURRENT_ENV,
        "alerts": active_alerts,
        "voice_announcement": voice_announcement,
    }


@app.post("/api/clock")
def api_clock(req: ClockRequest):
    db.set_mission_state("ship_time", req.ship_time)
    if req.distance_million_km is not None:
        db.set_mission_state("distance_million_km", str(req.distance_million_km))
    profile = db.get_astronaut_by_id(req.astronaut_id) or {}
    prompt = agent.get_proactive_clock_prompt(req.ship_time, profile.get("name", "Astronaut"))
    if prompt:
        conn = db.get_connection()
        conn.execute(
            "INSERT INTO ai_chat_history (astronaut_id, sender, message_text) VALUES (?, 'AI', ?)",
            (req.astronaut_id, prompt["voice_text"])
        )
        conn.commit()
        conn.close()
        db.add_notification(req.astronaut_id, "INFO", prompt["event"], prompt["voice_text"])
    return {"ship_time": req.ship_time, "prompt": prompt}


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    mission_state = db.get_mission_state()
    sim_time = mission_state.get("ship_time", "08:00")
    distance_km = float(mission_state.get("distance_million_km", 225.0)) * 1_000_000.0
    vitals = sim.get_latest_vitals(req.astronaut_id)
    active_alerts = alerts_mgr.evaluate_all_dangers(req.astronaut_id, vitals, CURRENT_ENV, distance_km=distance_km)
    resp = agent.chat(
        req.astronaut_id,
        req.message,
        is_voice_input=req.is_voice_input,
        active_alerts=active_alerts,
        simulated_time=sim_time,
        vitals=vitals,
    )
    ai_text = resp.get("ai_text") or ""
    resp["auto_open_chat"] = bool("?" in ai_text or resp.get("ask_media_permission"))
    return resp


@app.post("/api/media_finished")
def api_media_finished(req: MediaFinishedRequest):
    followup = "How did that feel? Did the music help you relax a bit? Are you feeling a little happier now, or still down?"
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO ai_chat_history (astronaut_id, sender, message_text) VALUES (?, 'AI', ?)",
        (req.astronaut_id, followup)
    )
    conn.commit()
    conn.close()
    return {"ai_text": followup, "auto_open_chat": True}


@app.post("/api/tts")
async def api_tts(req: TTSRequest):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")
    temp_file = os.path.join(tempfile.gettempdir(), f"cosmo_tts_{uuid.uuid4().hex}.mp3")
    try:
        communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
        await communicate.save(temp_file)
        audio_bytes = Path(temp_file).read_bytes()
        os.remove(temp_file)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as exc:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/sleep/start")
def api_sleep_start(req: MediaFinishedRequest):
    res = routine.start_sleep_session(req.astronaut_id)
    db.add_notification(req.astronaut_id, "INFO", "Sleep Cycle Initiated", "Circadian sleep pod timer started.")
    return res


@app.post("/api/sleep/wake")
def api_sleep_wake(req: MediaFinishedRequest):
    res = routine.confirm_wake_up_and_calculate_sleep(req.astronaut_id)
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO ai_chat_history (astronaut_id, sender, message_text) VALUES (?, 'AI', ?)",
        (req.astronaut_id, res["message"])
    )
    conn.commit()
    conn.close()
    db.add_notification(req.astronaut_id, "INFO", "Wake-Up Confirmed", res["message"])
    return res


@app.post("/api/ration/consume")
def api_ration_consume(req: RationRequest):
    item_id = req.item_id
    if not item_id and req.item_name:
        conn = db.get_connection()
        rows = conn.execute("SELECT item_id, item_name FROM inventory").fetchall()
        conn.close()
        target = req.item_name.lower()
        for r in rows:
            if target in r["item_name"].lower() or r["item_name"].lower().split()[0] in target:
                item_id = r["item_id"]
                break
        if not item_id and rows:
            item_id = rows[0]["item_id"]
    if not item_id:
        item_id = 1
    res = supply.consume_ration(req.astronaut_id, int(item_id), req.quantity)
    if res.get("success"):
        db.add_notification(
            req.astronaut_id,
            "INFO",
            "Ration Logged",
            f"Consumed {req.quantity} {res['unit']} of {res['item_name']}. Remaining: {res['remaining_quantity']} {res['unit']}"
        )
    return res


@app.post("/api/profile/biometrics")
def api_update_biometrics(req: BiometricsRequest):
    updated = db.update_astronaut_biometrics(
        req.astronaut_id, req.height_cm, req.weight_kg, req.age, req.fitness_level
    )
    return {"success": True, "profile": updated, "derived": db.calculate_derived_biometrics(updated)}


@app.post("/api/profile/password")
def api_update_password(req: PasswordRequest):
    ok = db.update_astronaut_password(req.astronaut_id, req.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    return {"success": True}


@app.post("/api/media/upload")
async def api_media_upload(
    astronaut_id: str = Form(...),
    category: str = Form("music"),
    file: UploadFile = File(...)
):
    content = await file.read()
    filename = file.filename or f"media_{uuid.uuid4().hex[:6]}.mp3"
    if category == "auto":
        category = "video" if filename.lower().endswith(".mp4") else "music"
    saved_path = db.save_user_media_file(astronaut_id, category, filename, content)
    return {"success": True, "path": saved_path, "name": Path(saved_path).name}


@app.post("/api/media/delete")
def api_media_delete(req: DeleteMediaRequest):
    db.delete_user_media_file(req.astronaut_id, req.file_path)
    return {"success": True}


@app.get("/api/media/stream")
def api_media_stream(path: str):
    p = Path(path)
    if not p.exists():
        alt = logic.MEDIA_DIR / p.name
        if alt.exists():
            p = alt
        else:
            raise HTTPException(status_code=404, detail="Media file not found")
    return FileResponse(str(p))


@app.post("/api/notifications/read")
def api_notifications_read(req: MediaFinishedRequest):
    db.mark_notifications_read(req.astronaut_id)
    return {"success": True}


@app.post("/api/emergency")
def api_emergency(req: EmergencyRequest):
    mission_state = db.get_mission_state()
    distance_km = float(mission_state.get("distance_million_km", 225.0)) * 1_000_000.0
    titles = {
        "airlocks": ("ENVIRONMENT_WARNING", "CRITICAL", "Emergency Airlock Lockdown", "All 6 habitat airlocks hermetically sealed."),
        "shelter": ("RADIATION_ALERT", "CRITICAL", "Radiation Storm Shelter Active", "Magnetic deflection boosted to 4.95 Tesla."),
        "distress": ("SECURITY_DISTRESS", "CRITICAL", "Earth Distress Beacon Transmitted", "Priority-1 Mayday telemetry packet dispatched to Earth Mission Control.")
    }
    cat, sev, title, msg = titles.get(req.action, ("SECURITY_ALERT", "WARNING", "Override Triggered", f"Action {req.action} executed."))
    alert = alerts_mgr._register_alert(req.astronaut_id, cat, sev, title, msg, notify_earth=True, distance_km=distance_km)
    return {"success": True, "alert": alert}


@app.post("/api/ingest_telemetry")
def api_ingest_telemetry(req: TelemetryIngestRequest):
    global CURRENT_ENV
    pressure_kpa = 101.3
    co2_mmhg = round((req.co2_ppm / 1_000_000.0) * (pressure_kpa * 7.50062), 2)

    conn = db.get_connection()
    conn.execute("""
        INSERT INTO live_vitals_telemetry
        (astronaut_id, heart_rate_bpm, systolic_mmhg, diastolic_mmhg, hrv_rmssd, co2_mmhg, ectopic_beats, flight_day)
        VALUES (?, ?, ?, ?, ?, ?, ?, 24)
    """, (req.astronaut_id, req.hr, req.sbp, req.dbp, req.hrv, co2_mmhg, req.ectopic))

    conn.execute("""
        INSERT INTO environment_logs (oxygen_percent, co2_ppm, temperature_c, humidity_percent, pressure_kpa)
        VALUES (?, ?, ?, 45.0, ?)
    """, (req.oxygen_percent, req.co2_ppm, req.temperature_c, pressure_kpa))

    rad_status = "warning" if req.radiation_cps >= 40.0 else "operational"
    conn.execute("""
        INSERT INTO radiation_logs (detector_id, radiation_type, count_rate_cps, sensor_status)
        VALUES ('RAD-01', 'Proton', ?, ?)
    """, (req.radiation_cps, rad_status))
    conn.commit()
    conn.close()

    CURRENT_ENV = {
        "oxygen_percent": req.oxygen_percent,
        "co2_ppm": req.co2_ppm,
        "co2_mmhg": co2_mmhg,
        "temperature_c": req.temperature_c,
        "humidity_percent": 45.0,
        "pressure_kpa": pressure_kpa,
    }

    vitals = logic.AstronautVitals(
        astronaut_id=req.astronaut_id,
        flight_day=24,
        hr=req.hr,
        sbp=req.sbp,
        dbp=req.dbp,
        hrv=req.hrv,
        co2=co2_mmhg,
        ectopic=req.ectopic,
        dizzy=req.dizzy,
        headache=req.headache,
        pain=req.pain,
    )

    mission_state = db.get_mission_state()
    distance_km = float(mission_state.get("distance_million_km", 225.0)) * 1_000_000.0
    active_alerts = alerts_mgr.evaluate_all_dangers(req.astronaut_id, vitals, CURRENT_ENV, distance_km=distance_km)

    return {"status": "ingested", "alerts_count": len(active_alerts)}

class MoodCheckinRequest(BaseModel):
    astronaut_id: str
    mood_label: str = "sadness"

@app.get("/api/llm_status")
def api_llm_status():
    key = agent.groq_api_key or os.environ.get("GROQ_API_KEY")
    return {
        "groq_key_configured": bool(key),
        "groq_key_prefix": (key[:7] + "...") if key else None,
        "active_model": agent.groq_model,
        "last_error": agent.last_llm_error,
    }


@app.post("/api/mood_checkin")
def api_mood_checkin(req: MoodCheckinRequest):
    mission_state = db.get_mission_state()
    sim_time = mission_state.get("ship_time", "08:00")
    vitals = sim.get_latest_vitals(req.astronaut_id)
    internal_prompt = (
        f"[SYSTEM EVENT: Optical camera just detected the astronaut looks {req.mood_label}.] "
        f"Speak directly to them as a caring friend. Gently mention you noticed they look a bit {req.mood_label} "
        f"and ask what is on their mind. Also offer ONE uplifting option (ask if they'd like a track from their "
        f"music folder and append [ASK_MEDIA], OR share a warm short joke, OR ask about a happy Earth memory)."
    )
    resp = agent.chat(
        req.astronaut_id,
        internal_prompt,
        is_voice_input=False,
        current_mood=2,
        simulated_time=sim_time,
        vitals=vitals,
        save_user_msg=False,
    )
    resp["auto_open_chat"] = True
    return resp
