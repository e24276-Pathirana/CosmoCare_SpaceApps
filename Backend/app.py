import streamlit as st
import logic
import os
import edge_tts
import asyncio
import speech_recognition as sr
import tempfile
import uuid
from pathlib import Path

st.set_page_config(page_title="SpaceStation AI — Command Console", page_icon="🛰️", layout="wide")


@st.cache_resource
def init_system():
    db = logic.DatabaseManager()
    sim = logic.SensorSimulator(db)
    supply = logic.DeepSpaceSupplyEngine(db)
    rad = logic.RadiationMonitorLogic(db)
    alerts_mgr = logic.DangerAlertManager(db, supply, rad)
    routine = logic.RoutineAndSleepTracker(db)
    agent = logic.AstroCompanionAgent(db)
    return db, sim, supply, rad, alerts_mgr, routine, agent


db, sim, supply, rad, alerts_mgr, routine, agent = init_system()

if "authenticated_user" not in st.session_state:
    st.session_state.authenticated_user = None
if "astronaut_id" not in st.session_state:
    st.session_state.astronaut_id = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "active_media" not in st.session_state:
    st.session_state.active_media = None
if "tts_audio_bytes" not in st.session_state:
    st.session_state.tts_audio_bytes = None
if "last_voice_text" not in st.session_state:
    st.session_state.last_voice_text = ""
if "last_audio_bytes" not in st.session_state:
    st.session_state.last_audio_bytes = None
if "announce_alerts_now" not in st.session_state:
    st.session_state.announce_alerts_now = False


if st.session_state.authenticated_user is None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: linear-gradient(180deg, #2b4c9b 0%, #4f74c8 55%, #3b5fa8 100%);
    }

    section[data-testid="stSidebar"] {
        display: none !important;
    }

    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    .login-hero-banner {
        width: 100%;
        border-radius: 16px 16px 0 0;
        overflow: hidden;
        box-shadow: 0 12px 30px rgba(10, 22, 58, 0.35);
        margin-bottom: -16px;
        position: relative;
        z-index: 2;
    }

    div[data-testid="stForm"] {
        background: #ffffff !important;
        border-radius: 0 0 16px 16px !important;
        padding: 34px 38px 36px 38px !important;
        border: none !important;
        box-shadow: 0 20px 45px rgba(10, 22, 58, 0.45) !important;
    }

    .login-heading {
        text-align: center;
        color: #162a64;
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        margin-bottom: 18px;
    }

    div[data-testid="stTextInput"] label {
        color: #1e3a8a !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
    }

    div[data-testid="stTextInput"] input {
        background: linear-gradient(90deg, #254b9e 0%, #7da2e8 55%, #c5d8f8 100%) !important;
        color: #ffffff !important;
        border-radius: 25px !important;
        border: none !important;
        padding: 12px 20px !important;
        font-weight: 600 !important;
    }

    div[data-testid="stTextInput"] input::placeholder {
        color: rgba(255, 255, 255, 0.88) !important;
    }

    div[data-testid="stFormSubmitButton"] {
        display: flex;
        justify-content: center;
        margin-top: 14px;
    }

    div[data-testid="stFormSubmitButton"] button {
        background: #1b3d8e !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        padding: 8px 42px !important;
        font-weight: 700 !important;
        border: none !important;
        box-shadow: 0 4px 14px rgba(27, 61, 142, 0.4) !important;
    }

    div[data-testid="stFormSubmitButton"] button:hover {
        background: #122b69 !important;
    }

    .demo-creds-box {
        background: rgba(15, 29, 68, 0.55);
        border: 1px solid rgba(255, 255, 255, 0.22);
        border-radius: 10px;
        padding: 10px 16px;
        color: #e2e8f0;
        font-size: 0.78rem;
        margin-top: 16px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

    _, center_col, _ = st.columns([1.15, 1.3, 1.15])
    with center_col:
        st.markdown("""
        <div class="login-hero-banner">
            <svg viewBox="0 0 500 280" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="display:block;">
                <defs>
                    <linearGradient id="skyGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stop-color="#17377a"/>
                        <stop offset="65%" stop-color="#2855a8"/>
                        <stop offset="100%" stop-color="#152c66"/>
                    </linearGradient>
                    <linearGradient id="lakeGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stop-color="#163273"/>
                        <stop offset="100%" stop-color="#0f2356"/>
                    </linearGradient>
                </defs>
                <rect width="500" height="280" fill="url(#skyGrad)"/>
                <circle cx="95" cy="48" r="1.5" fill="#ffffff" opacity="0.8"/>
                <circle cx="155" cy="30" r="2" fill="#ffffff" opacity="0.9"/>
                <circle cx="240" cy="42" r="1.2" fill="#ffffff" opacity="0.7"/>
                <circle cx="385" cy="65" r="1.8" fill="#ffffff" opacity="0.85"/>
                <circle cx="430" cy="40" r="1.4" fill="#ffffff" opacity="0.7"/>
                <line x1="425" y1="18" x2="310" y2="75" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" opacity="0.9"/>
                <circle cx="285" cy="145" r="46" fill="#a8c5f0" opacity="0.85"/>
                <polygon points="0,195 95,120 215,195" fill="#1e4088"/>
                <polygon points="160,195 295,115 430,195" fill="#183576"/>
                <polygon points="310,195 435,105 500,195" fill="#122a63"/>
                <polygon points="0,195 140,145 270,195" fill="#10255a"/>
                <rect x="0" y="195" width="500" height="85" fill="url(#lakeGrad)"/>
                <ellipse cx="285" cy="215" rx="55" ry="4" fill="#6b96d6" opacity="0.35"/>
                <ellipse cx="285" cy="228" rx="38" ry="3" fill="#6b96d6" opacity="0.25"/>
                <ellipse cx="285" cy="240" rx="22" ry="2.5" fill="#6b96d6" opacity="0.2"/>
                <text x="250" y="96" fill="#ffffff" font-size="22" font-weight="700" font-family="Inter, sans-serif" text-anchor="middle">Welcome to CosmoCare</text>
                <text x="250" y="118" fill="#cbd5e1" font-size="10.5" font-family="Inter, sans-serif" text-anchor="middle">Autonomous Space Station Medical &amp; AI Companion</text>
            </svg>
        </div>
        """, unsafe_allow_html=True)

        with st.form("astronaut_login_form"):
            st.markdown('<div class="login-heading">USER LOGIN</div>', unsafe_allow_html=True)
            input_user = st.text_input("👤 User ID / Astronaut ID", placeholder="Enter ID (e.g., A004, A005, A006)")
            input_pass = st.text_input("🔒 Password", type="password", placeholder="Enter Password")
            c_rem, c_forgot = st.columns(2)
            with c_rem:
                st.checkbox("Remember me", value=True)
            with c_forgot:
                st.markdown('<div style="text-align:right; font-size:0.8rem; color:#3b5fa8; padding-top:6px;">Forgot password?</div>', unsafe_allow_html=True)

            login_Clicked = st.form_submit_button("Log in")
            if login_Clicked:
                auth_user = db.authenticate_user(input_user, input_pass)
                if auth_user:
                    st.session_state.authenticated_user = auth_user
                    st.session_state.astronaut_id = auth_user["astronaut_id"]
                    st.session_state.current_vitals = sim.get_latest_vitals(auth_user["astronaut_id"])
                    st.session_state.current_env = sim.generate_environment_reading()
                    st.session_state.chat_history = []
                    st.rerun()
                else:
                    st.error("Invalid Astronaut ID or Password. Please check credentials below.")

        st.markdown("""
        <div class="demo-creds-box">
            <strong>Crew Login Credentials:</strong><br>
            • <code>A004</code> (Dr. Sarah Mitchell) — Pass: <code>Sarah@2026</code><br>
            • <code>A005</code> (Cmdr. James Holden) — Pass: <code>Holden@2026</code><br>
            • <code>A006</code> (Eng. Elena Rostova) — Pass: <code>Elena@2026</code>
        </div>
        """, unsafe_allow_html=True)

    st.stop()


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #0b0f19;
    color: #e2e8f0;
}

.stApp {
    background: radial-gradient(circle at 15% 15%, #111a2e 0%, #0b0f19 60%, #070a12 100%);
}

section[data-testid="stSidebar"] {
    background-color: #0d1322 !important;
    border-right: 1px solid #1e293b;
}

div[data-testid="stRadio"] > div {
    gap: 6px;
}

div[data-testid="stRadio"] label {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 10px 14px;
    transition: all 0.2s ease;
    width: 100%;
}

div[data-testid="stRadio"] label:hover {
    background-color: rgba(6, 182, 212, 0.08);
    border-color: rgba(6, 182, 212, 0.25);
}

.top-header-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(17, 24, 39, 0.85);
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 14px 22px;
    margin-bottom: 20px;
}

.header-title-wrap {
    display: flex;
    align-items: center;
    gap: 14px;
}

.header-main-title {
    font-size: 1.35rem;
    font-weight: 700;
    color: #f8fafc;
    margin: 0;
}

.badge-nominal {
    background: rgba(16, 185, 129, 0.15);
    color: #10b981;
    border: 1px solid rgba(16, 185, 129, 0.35);
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.06em;
}

.badge-alert {
    background: rgba(239, 68, 68, 0.18);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.45);
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.06em;
}

.header-sub {
    font-size: 0.8rem;
    color: #94a3b8;
    margin-top: 4px;
}

.pill-group {
    display: flex;
    align-items: center;
    gap: 10px;
}

.env-pill {
    background: #131c2e;
    border: 1px solid #263554;
    border-radius: 20px;
    padding: 6px 14px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: #cbd5e1;
}

.ai-pill-badge {
    background: linear-gradient(135deg, #0891b2 0%, #06b6d4 100%);
    color: #04131a;
    font-weight: 700;
    border-radius: 20px;
    padding: 6px 16px;
    font-size: 0.8rem;
    box-shadow: 0 0 15px rgba(6, 182, 212, 0.35);
}

.metric-card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 12px;
    padding: 18px 20px;
    position: relative;
    transition: border-color 0.2s;
}

.metric-card:hover {
    border-color: #06b6d4;
}

.metric-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    color: #64748b;
    text-transform: uppercase;
}

.metric-icon {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.95rem;
    background: rgba(6, 182, 212, 0.12);
    color: #22d3ee;
    border: 1px solid rgba(6, 182, 212, 0.25);
}

.metric-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.65rem;
    font-weight: 700;
    color: #f8fafc;
    margin: 8px 0 4px 0;
}

.metric-sub {
    font-size: 0.78rem;
    color: #64748b;
}

.console-panel {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 16px;
}

.panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid #1e293b;
}

.panel-title {
    font-size: 1.02rem;
    font-weight: 700;
    color: #f1f5f9;
}

.panel-subtitle {
    font-size: 0.76rem;
    color: #64748b;
}

.timeline-item {
    display: flex;
    gap: 14px;
    margin-bottom: 12px;
    align-items: flex-start;
}

.timeline-time {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: #38bdf8;
    min-width: 52px;
    padding-top: 10px;
}

.timeline-box {
    flex: 1;
    background: #161f33;
    border: 1px solid #263554;
    border-radius: 10px;
    padding: 12px 16px;
}

.timeline-box-active {
    flex: 1;
    background: rgba(6, 182, 212, 0.09);
    border: 1px solid #06b6d4;
    border-radius: 10px;
    padding: 12px 16px;
    box-shadow: 0 0 18px rgba(6, 182, 212, 0.12);
}

.timeline-title {
    font-weight: 600;
    font-size: 0.9rem;
    color: #f1f5f9;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.tag-meal {
    background: rgba(245, 158, 11, 0.16);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.35);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 700;
}

.tag-rest {
    background: rgba(168, 85, 247, 0.16);
    color: #c084fc;
    border: 1px solid rgba(168, 85, 247, 0.35);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 700;
}

.crew-footer {
    background: #131c2e;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 10px 12px;
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 14px;
    margin-bottom: 10px;
}

.crew-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: linear-gradient(135deg, #06b6d4, #3b82f6);
    color: #0b0f19;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
}
</style>
""", unsafe_allow_html=True)


def generate_and_play_tts(text):
    if not text or not text.strip():
        return
    voice = "en-US-AriaNeural"
    temp_file = os.path.join(tempfile.gettempdir(), f"tts_{uuid.uuid4().hex}.mp3")

    async def _generate():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_file)

    try:
        asyncio.run(_generate())
        if os.path.exists(temp_file):
            with open(temp_file, "rb") as f:
                st.session_state.tts_audio_bytes = f.read()
            os.remove(temp_file)
    except Exception:
        pass


def resolve_media_path(file_path_str):
    if not file_path_str:
        return None
    p1 = Path(file_path_str)
    if p1.exists():
        return p1
    p2 = Path(__file__).parent / file_path_str
    if p2.exists():
        return p2
    p3 = Path(__file__).parent / "assets" / "media" / p1.name
    if p3.exists():
        return p3
    media_dir = Path(__file__).parent / "assets" / "media"
    if media_dir.exists():
        files = [f for f in media_dir.iterdir() if f.suffix.lower() in ('.mp3', '.mp4', '.wav')]
        if files:
            return files[0]
    return None


def recognize_from_browser_audio(audio_bytes):
    recognizer = sr.Recognizer()
    ts_name = f"voice_log_{uuid.uuid4().hex[:6]}.wav"
    if hasattr(db, "save_user_media_file"):
        db.save_user_media_file(st.session_state.astronaut_id, "voice", ts_name, audio_bytes)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        with sr.AudioFile(tmp_path) as source:
            audio_data = recognizer.record(source)
            raw_text = recognizer.recognize_google(audio_data)
            return agent.voice_corrector.clean_transcript(raw_text)
    except Exception:
        return "ERROR: Could not transcribe browser audio."
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


if "current_vitals" not in st.session_state:
    st.session_state.current_vitals = sim.get_latest_vitals(st.session_state.astronaut_id)
if "current_env" not in st.session_state:
    st.session_state.current_env = sim.generate_environment_reading()

active_profile = db.get_astronaut_by_id(st.session_state.astronaut_id) or {}
mission_state = db.get_mission_state()

with st.sidebar:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:12px; padding-bottom:14px; border-bottom:1px solid #1e293b; margin-bottom:14px;">
        <div style="width:38px; height:38px; border-radius:10px; background:linear-gradient(135deg,#06b6d4,#2563eb); display:flex; align-items:center; justify-content:center; font-size:1.2rem;">🛰️</div>
        <div>
            <div style="font-weight:700; font-size:1.05rem; color:#f8fafc;">SpaceStation AI</div>
            <div style="font-size:0.7rem; color:#64748b; font-family:'JetBrains Mono',monospace;">CS-OS v4.2 • COSMOCARE</div>
        </div>
    </div>
    <div style="font-size:0.68rem; font-weight:700; color:#475569; letter-spacing:0.1em; margin-bottom:8px;">OPERATIONS CONSOLE</div>
    """, unsafe_allow_html=True)

    nav_page = st.radio(
        "Navigation",
        [
            "🎛️ Command Overview",
            "📅 Daily Schedule & Exercise",
            "🍽️ Diet, Hydration & Supply",
            "🌙 Sleep Timer & Alarm",
            "🩺 Medical Triage & Waveforms",
            "💬 Mental Health & Voice AI",
            "🔐 Crew Profile & Media Vault"
        ],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.caption("⚡ **QUICK TELEMETRY & CLOCK CONTROLS**")
    mission_hour = st.slider("Ship Clock (UTC Hours)", 0, 23, int(mission_state.get("ship_time", "08:00").split(":")[0]))
    simulated_time = f"{mission_hour:02d}:00"
    db.set_mission_state("ship_time", simulated_time)

    distance_m_km = st.number_input("Distance (Million km)", min_value=0.0004, max_value=400.0, value=float(mission_state.get("distance_million_km", 225.0)), step=5.0)
    db.set_mission_state("distance_million_km", str(distance_m_km))
    distance_km = distance_m_km * 1_000_000.0

    anomaly = st.selectbox("Simulate Condition", ["None", "arrhythmia", "hypovolemia", "high_co2", "radiation_spike"])
    if st.button("⚡ Pulse Live Telemetry", use_container_width=True):
        st.session_state.current_vitals = sim.generate_live_vitals(
            st.session_state.astronaut_id,
            anomaly_mode=anomaly if anomaly in ("arrhythmia", "hypovolemia", "high_co2") else None
        )
        st.session_state.current_env = sim.generate_environment_reading(
            anomaly_mode="cabin_danger" if anomaly == "high_co2" else None
        )
        sim.generate_radiation_reading(spike=(anomaly == "radiation_spike"))
        st.session_state.announce_alerts_now = True
        st.rerun()

    initials = "".join([p[0] for p in active_profile.get("name", "S M").split()[:2]])
    st.markdown(f"""
    <div class="crew-footer">
        <div class="crew-avatar">{initials}</div>
        <div>
            <div style="font-weight:600; font-size:0.85rem; color:#f1f5f9;">{active_profile.get('name', 'Dr. Sarah Mitchell')}</div>
            <div style="font-size:0.72rem; color:#64748b;">{st.session_state.astronaut_id} • {active_profile.get('role', '')}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Log Out", use_container_width=True):
        st.session_state.authenticated_user = None
        st.session_state.astronaut_id = None
        st.rerun()

v = st.session_state.current_vitals
env = st.session_state.current_env
active_alerts = alerts_mgr.evaluate_all_dangers(st.session_state.astronaut_id, v, env, distance_km=distance_km)
triage_info = logic.BioAstronauticsLogic.evaluate_triage(v)

status_badge_html = (
    '<span class="badge-nominal">EXPEDITION 73 • NOMINAL</span>'
    if not active_alerts
    else f'<span class="badge-alert">ALERT ACTIVE • {len(active_alerts)} WARNINGS</span>'
)

st.markdown(f"""
<div class="top-header-bar">
    <div>
        <div class="header-title-wrap">
            <h1 class="header-main-title">Space Station Command Console</h1>
            {status_badge_html}
        </div>
        <div class="header-sub">
            Logged in: <strong style="color:#e2e8f0;">{active_profile.get('name', 'Dr. Sarah Mitchell')}</strong> • 
            ID: <strong style="color:#38bdf8;">{st.session_state.astronaut_id}</strong> • 
            Role: <strong style="color:#cbd5e1;">{active_profile.get('role', 'Mission Specialist')}</strong> • 
            Fitness: <strong style="color:#10b981;">{active_profile.get('fitness_level', 'High')}</strong> • 
            Ship Time: <strong style="color:#f8fafc;">{simulated_time} UTC</strong>
        </div>
    </div>
    <div class="pill-group">
        <div class="env-pill"><span style="color:#10b981;">●</span> O₂ {env['oxygen_percent']}%</div>
        <div class="env-pill"><span style="color:#38bdf8;">●</span> Cabin {env['pressure_kpa']} kPa</div>
        <div class="env-pill"><span style="color:#f59e0b;">●</span> CO₂ {env['co2_ppm']} ppm</div>
        <div class="ai-pill-badge">💬 Mental Health AI</div>
    </div>
</div>
""", unsafe_allow_html=True)

mc1, mc2, mc3, mc4 = st.columns(4)
with mc1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-top"><span>EXPEDITION 73</span><div class="metric-icon">📅</div></div>
        <div class="metric-val">DAY {v.flight_day}</div>
        <div class="metric-sub">Day of the Mission (MET)</div>
    </div>
    """, unsafe_allow_html=True)
with mc2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-top"><span>DEEP SPACE TRANSIT</span><div class="metric-icon">🛰️</div></div>
        <div class="metric-val">{distance_m_km:.1f}M km</div>
        <div class="metric-sub">Distance from Earth</div>
    </div>
    """, unsafe_allow_html=True)
with mc3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-top"><span>CARDIO TELEMETRY</span><div class="metric-icon">💓</div></div>
        <div class="metric-val">{v.hr} bpm</div>
        <div class="metric-sub">BP: {v.sbp}/{v.dbp} mmHg • HRV: {v.hrv} ms</div>
    </div>
    """, unsafe_allow_html=True)
with mc4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-top"><span>BIOMETRIC PROFILE</span><div class="metric-icon">🧬</div></div>
        <div class="metric-val">{active_profile.get('weight_kg', 65.0)} kg</div>
        <div class="metric-sub">Height: {active_profile.get('height_cm', 170.5)} cm • Blood: {active_profile.get('blood_type', 'O+')}</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

if active_alerts:
    combined_voice_alerts = []
    for alert in active_alerts:
        st.error(f"🚨 **{alert['severity']} [{alert['category']}]: {alert['title']}** — {alert['message']}")
        if alert.get("voice_announcement"):
            combined_voice_alerts.append(alert["voice_announcement"])

    if st.session_state.announce_alerts_now and combined_voice_alerts:
        full_alert_speech = " ".join(combined_voice_alerts)
        st.session_state.chat_history.append({"role": "AI", "content": f"🚨 {full_alert_speech}"})
        generate_and_play_tts(full_alert_speech)
        st.session_state.announce_alerts_now = False

if st.session_state.tts_audio_bytes:
    st.audio(st.session_state.tts_audio_bytes, format="audio/mp3", autoplay=True)
    st.session_state.tts_audio_bytes = None

schedules = db.get_schedules()
derived_bio = db.calculate_derived_biometrics(active_profile)

if nav_page in ("🎛️ Command Overview", "📅 Daily Schedule & Exercise"):
    col_left, col_right = st.columns([1.05, 1])

    with col_left:
        st.markdown("""
        <div class="console-panel">
            <div class="panel-header">
                <div>
                    <div class="panel-title">📅 Daily Mission Timeline</div>
                    <div class="panel-subtitle">Coordinated Universal Time (UTC) • Proactive Voice Schedule</div>
                </div>
                <span class="badge-nominal">ALL EVENTS</span>
            </div>
        """, unsafe_allow_html=True)

        for s in schedules:
            is_now = s["time_slot"].startswith(f"{mission_hour:02d}:")
            box_cls = "timeline-box-active" if is_now else "timeline-box"
            tag_cls = "tag-meal" if any(k in s["event_title"].lower() for k in ["breakfast", "lunch", "dinner", "nutrition"]) else "tag-rest"
            tag_label = "MEAL" if tag_cls == "tag-meal" else "ROUTINE"
            status_dot = '<div style="color:#10b981; font-size:0.7rem; font-weight:700; margin-top:6px;">● IN PROGRESS NOW</div>' if is_now else ""

            st.markdown(f"""
            <div class="timeline-item">
                <div class="timeline-time">{s['time_slot']}</div>
                <div class="{box_cls}">
                    <div class="timeline-title">
                        <span>{s['event_title']}</span>
                        <span class="{tag_cls}">{tag_label}</span>
                    </div>
                    <div style="font-size:0.78rem; color:#94a3b8; margin-top:4px;">{s['voice_prompt']}</div>
                    {status_dot}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        clock_event = agent.get_proactive_clock_prompt(simulated_time, active_profile.get("name", "Astronaut"))
        if clock_event:
            if st.button(f"🔔 Announce {simulated_time} Scheduled Voice Prompt", use_container_width=True):
                st.session_state.chat_history.append({"role": "AI", "content": clock_event["voice_text"]})
                generate_and_play_tts(clock_event["voice_text"])
                st.rerun()

    with col_right:
        st.markdown(f"""
        <div class="console-panel">
            <div class="panel-header">
                <div>
                    <div class="panel-title">🏋️ Exercise Routine & Countermeasures</div>
                    <div class="panel-subtitle">ARED Resistive & CEVIS / T2 Aerobic • Target Load: {triage_info['ared_mod']}%</div>
                </div>
                <span class="badge-nominal">ACTIVE PROTOCOL</span>
            </div>
        """, unsafe_allow_html=True)

        ex_done_1 = st.checkbox("CEVIS Cycle Ergometer (Cardio) — 30 min interval training (Target HR: 145 bpm)", value=True)
        ex_done_2 = st.checkbox("T2 Treadmill Vibration-Isolated Run — 30 min bungee harness running (8.5 km/h)", value=False)
        ex_done_3 = st.checkbox("ARED Bench Press & Squat — 4 sets × 10 reps (Upper/Lower axial loading)", value=False)
        ex_done_4 = st.checkbox("Core Microgravity Stabilization — 15 min anti-rotation & postural bracing", value=False)

        pct = int((sum([ex_done_1, ex_done_2, ex_done_3, ex_done_4]) / 4.0) * 100)
        st.progress(pct / 100.0, text=f"Daily Microgravity Countermeasure Target: {pct}% Complete")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(f"""
        <div class="console-panel">
            <div class="panel-header">
                <div class="panel-title">🥗 Personalized Diet & Nutritional Flight Plan ({active_profile.get('name')})</div>
                <span style="color:#fbbf24; font-family:'JetBrains Mono',monospace; font-size:0.85rem;">~{derived_bio['daily_kcal_target']} kcal Target</span>
            </div>
            <div style="font-size:0.84rem; color:#cbd5e1;">
                • <strong>BMI:</strong> {derived_bio['bmi']} ({derived_bio['bmi_status']})<br>
                • <strong>Hydration Target:</strong> {derived_bio['hydration_target_l']} L/day<br>
                • <strong>Protein Target:</strong> {derived_bio['protein_target_g']} g/day
            </div>
        </div>
        """, unsafe_allow_html=True)

if nav_page in ("🎛️ Command Overview", "💬 Mental Health & Voice AI"):
    st.markdown("""
    <div class="console-panel">
        <div class="panel-header">
            <div>
                <div class="panel-title">💬 CosmoCare Mental Health & Voice AI Companion</div>
                <div class="panel-subtitle">Auto-Correcting Voice Input • Permission-Based Silent Media Playback • Live DB Sync</div>
            </div>
            <span class="ai-pill-badge">ONLINE • LLAMA 3.3 70B</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.active_media:
        raw_path = st.session_state.active_media.get("file_path", "")
        resolved_path = resolve_media_path(raw_path)
        if resolved_path and resolved_path.exists():
            st.success(f"🎵 Playing silently as requested: **{resolved_path.name}**")
            with open(resolved_path, "rb") as media_f:
                media_bytes = media_f.read()
            if resolved_path.suffix.lower() == ".mp4":
                st.video(media_bytes, autoplay=True)
            else:
                st.audio(media_bytes, format="audio/mp3", autoplay=True)

            if st.button("✅ Song Finished (Trigger AI Welfare Check-in)"):
                st.session_state.active_media = None
                followup = "How did that feel? Did the music help you relax? Are you feeling a bit happier now, or still down?"
                st.session_state.chat_history.append({"role": "AI", "content": followup})
                generate_and_play_tts(followup)
                st.rerun()
        else:
            st.warning(f"Media file not found at `{raw_path}`. Upload `.mp3` files in the Media Vault.")

    for msg in st.session_state.chat_history:
        with st.chat_message("user" if msg["role"] == "User" else "assistant"):
            st.write(msg["content"])

    user_text = ""
    if hasattr(st, "audio_input"):
        web_audio = st.audio_input("🎙️ Tap to Speak (Auto-Corrects & Auto-Sends when you click Stop):")
        if web_audio is not None:
            audio_bytes = web_audio.getvalue()
            if audio_bytes != st.session_state.last_audio_bytes:
                st.session_state.last_audio_bytes = audio_bytes
                result = recognize_from_browser_audio(audio_bytes)
                if result.startswith("ERROR:"):
                    st.error(result)
                else:
                    st.session_state.last_voice_text = result
                    user_text = result

    if st.session_state.last_voice_text:
        st.caption(f"✨ **Auto-Corrected Voice Transcript Sent:** `{st.session_state.last_voice_text}`")

    typed_input = st.chat_input("Speak via mic or type here (e.g., 'I feel sad', 'I ate 2 Rice rations', 'I am awake')...")
    if typed_input:
        st.session_state.last_voice_text = ""
        user_text = typed_input

    if user_text:
        st.session_state.chat_history.append({"role": "User", "content": user_text})
        with st.spinner("CosmoCare AI is analyzing..."):
            response = agent.chat(
                st.session_state.astronaut_id,
                user_text,
                is_voice_input=True,
                active_alerts=active_alerts,
                simulated_time=simulated_time
            )
            if response.get("db_updates"):
                for upd in response["db_updates"]:
                    st.toast(f"🗄️ {upd}", icon="✅")

            ai_reply = response["ai_text"]
            if ai_reply:
                st.session_state.chat_history.append({"role": "AI", "content": ai_reply})
                generate_and_play_tts(ai_reply)

            if response.get("play_media_now"):
                st.session_state.tts_audio_bytes = None
                st.session_state.active_media = response.get("media_file")
        st.rerun()

elif nav_page == "🍽️ Diet, Hydration & Supply":
    inv_eval = supply.evaluate_inventory_and_trigger(distance_km)
    lead = inv_eval["lead_data"]
    l1, l2, l3 = st.columns(3)
    l1.metric("One-Way Light Delay", f"{lead['one_way_light_delay_hours']} hrs")
    l2.metric("Resupply Transit Time", f"{lead['transit_time_days']} days")
    l3.metric("Total Resupply Lead Threshold", f"{lead['total_lead_time_days']} days")

    conn = db.get_connection()
    inv_rows = [dict(r) for r in conn.execute("SELECT * FROM inventory").fetchall()]
    conn.close()

    col_sel, col_qty, col_btn = st.columns([2, 1, 1])
    with col_sel:
        chosen_item = st.selectbox("Select Ration / Supply Item", inv_rows, format_func=lambda x: f"{x['item_name']} ({x['quantity']} {x['unit']})")
    with col_qty:
        consume_qty = st.number_input("Quantity Consumed", min_value=0.1, max_value=50.0, value=1.0, step=0.5)
    with col_btn:
        st.write("")
        st.write("")
        if st.button("🍽️ Deduct & Log Stock", use_container_width=True):
            res = supply.consume_ration(st.session_state.astronaut_id, chosen_item["item_id"], consume_qty)
            st.success(f"Logged {consume_qty} {res['unit']} of {res['item_name']}. Remaining: {res['remaining_quantity']} {res['unit']}")
            st.rerun()

    st.dataframe(inv_eval["items"], use_container_width=True)

elif nav_page == "🌙 Sleep Timer & Alarm":
    st.subheader(f"🌙 Circadian Sleep Pod & Wake Alarm Tracker — {active_profile.get('name')}")
    c_s1, c_s2 = st.columns(2)
    with c_s1:
        if st.button("🛌 Start Sleep Session Now", use_container_width=True):
            routine.start_sleep_session(st.session_state.astronaut_id)
            st.success("Sleep timer started in SQLite DB!")
            st.rerun()
    with c_s2:
        if st.button("☀️ Confirm Wake-Up & Calculate Sleep", use_container_width=True):
            res = routine.confirm_wake_up_and_calculate_sleep(st.session_state.astronaut_id)
            st.session_state.chat_history.append({"role": "AI", "content": res["message"]})
            generate_and_play_tts(res["message"])
            st.success(res["message"])
            st.rerun()

    conn = db.get_connection()
    sleep_logs = [dict(r) for r in conn.execute("SELECT session_id, sleep_start, wake_confirm, duration_hours, status FROM sleep_sessions WHERE astronaut_id = ? ORDER BY session_id DESC LIMIT 10", (st.session_state.astronaut_id,)).fetchall()]
    conn.close()
    st.dataframe(sleep_logs, use_container_width=True)

elif nav_page == "🩺 Medical Triage & Waveforms":
    st.subheader(f"🩺 Clinical Status ({active_profile.get('name')}): {triage_info['status_level']} — {triage_info['diagnosis']}")
    st.info(f"**Phase:** {triage_info['phase_name']} | **Explanation:** {triage_info['explanation']}")
    st.write(f"**Verification Protocol:** {triage_info['verification']}")
    for s in triage_info["steps"]:
        st.markdown(f"- {s}")

    wave_samples = [logic.BioAstronauticsLogic.sample_bio_waveforms(t * 0.04, v) for t in range(100)]
    c_w1, c_w2 = st.columns(2)
    with c_w1:
        st.caption("📈 Simulated 3-Lead ECG Waveform (mV)")
        st.line_chart([w["ecg_mv"] for w in wave_samples])
    with c_w2:
        st.caption("📉 Simulated Optical PPG Pulse Waveform")
        st.line_chart([w["ppg_amp"] for w in wave_samples])

elif nav_page == "🔐 Crew Profile & Media Vault":
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.subheader(f"🧬 Update Biometrics ({active_profile.get('name')})")
        with st.form("biometrics_form"):
            new_h = st.number_input("Height (cm)", value=float(active_profile.get("height_cm", 170.5)))
            new_w = st.number_input("Weight (kg)", value=float(active_profile.get("weight_kg", 65.0)))
            new_age = st.number_input("Age", value=int(active_profile.get("age", 42)))
            new_fit = st.selectbox("Fitness Level", ["High", "Moderate", "Low"], index=0)
            if st.form_submit_button("💾 Save Biometrics to DB"):
                db.update_astronaut_biometrics(st.session_state.astronaut_id, new_h, new_w, new_age, new_fit)
                st.success("Biometrics updated in SQLite DB!")
                st.rerun()

        if hasattr(db, "update_astronaut_password"):
            with st.form("pw_update_form"):
                new_pw = st.text_input("New Password for " + st.session_state.astronaut_id, type="password")
                if st.form_submit_button("🔒 Update Password in DB"):
                    if db.update_astronaut_password(st.session_state.astronaut_id, new_pw):
                        st.success("Password updated in SQLite Database!")
                    else:
                        st.error("Password must be at least 4 characters.")

    with col_b2:
        st.subheader("🎵 Personal Media & Voice Recordings Vault")
        if hasattr(db, "save_user_media_file"):
            uploaded_media = st.file_uploader("Upload Custom Song (.mp3/.wav) or Video (.mp4)", type=["mp3", "wav", "mp4"])
            if uploaded_media is not None:
                cat = "video" if uploaded_media.name.lower().endswith(".mp4") else "music"
                if st.button("⬆️ Save Media to Astronaut Folder & DB"):
                    saved_p = db.save_user_media_file(st.session_state.astronaut_id, cat, uploaded_media.name, uploaded_media.getvalue())
                    st.success(f"Saved to `{saved_p}`!")
                    st.rerun()

            user_files = db.get_user_media_list(st.session_state.astronaut_id)
            st.caption("🎙️ **Saved User Voice Recordings:**")
            for vf in user_files.get("voice", [])[:5]:
                c_v1, c_v2 = st.columns([4, 1])
                c_v1.audio(str(vf))
                if c_v2.button("🗑️", key=f"del_{vf.name}"):
                    db.delete_user_media_file(st.session_state.astronaut_id, str(vf))
                    st.rerun()

            st.caption("🎶 **Uploaded Personal Music & Videos:**")
            for mf in (user_files.get("music", []) + user_files.get("video", [])):
                c_m1, c_m2 = st.columns([4, 1])
                c_m1.write(f"• `{mf.name}`")
                if c_m2.button("🗑️", key=f"del_m_{mf.name}"):
                    db.delete_user_media_file(st.session_state.astronaut_id, str(mf))
                    st.rerun()
