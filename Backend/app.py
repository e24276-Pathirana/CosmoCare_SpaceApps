import streamlit as st
import logic
import os
import edge_tts
import asyncio
import speech_recognition as sr
import tempfile
import uuid
from pathlib import Path

st.set_page_config(page_title="CosmoCare Smart Space Habitat", page_icon="🚀", layout="wide")


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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

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
                <text x="250" y="96" fill="#ffffff" font-size="22" font-weight="700" font-family="Inter, sans-serif" text-anchor="middle">Welcome to CosmoCare</text>
                <text x="250" y="118" fill="#cbd5e1" font-size="10.5" font-family="Inter, sans-serif" text-anchor="middle">Autonomous Space Station Medical &amp; AI Companion</text>
            </svg>
        </div>
        """, unsafe_allow_html=True)

        with st.form("astronaut_login_form"):
            st.markdown('<div class="login-heading">USER LOGIN</div>', unsafe_allow_html=True)
            input_user = st.text_input("👤 User name / Astronaut ID", placeholder="Enter ID (e.g., A004, A005, A006)")
            input_pass = st.text_input("🔒 Password", type="password", placeholder="Enter Password")
            c_rem, c_forgot = st.columns(2)
            with c_rem:
                st.checkbox("Remember me", value=True)
            with c_forgot:
                st.markdown('<div style="text-align:right; font-size:0.8rem; color:#3b5fa8; padding-top:6px;">Forgot password?</div>', unsafe_allow_html=True)

            login_clicked = st.form_submit_button("Log in")
            if login_clicked:
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
            • <code>A004</code> (Dr. Sarah Mitchell - Female) — Pass: <code>Sarah@2026</code><br>
            • <code>A005</code> (Cmdr. James Holden - Male) — Pass: <code>Holden@2026</code><br>
            • <code>A006</code> (Eng. Elena Rostova - Female) — Pass: <code>Elena@2026</code>
        </div>
        """, unsafe_allow_html=True)

    st.stop()


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Nunito', sans-serif;
    color: #334155;
}

.stApp {
    background: linear-gradient(135deg, #e0eafc 0%, #f5f7fb 55%, #e9f0ff 100%);
    padding-bottom: 90px;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0088cc 0%, #0099dd 55%, #0077b6 100%) !important;
    border-right: none !important;
    box-shadow: 6px 0 24px rgba(0, 119, 182, 0.18);
}

section[data-testid="stSidebar"] * {
    color: #ffffff !important;
}

div[data-testid="stRadio"] > div {
    gap: 8px;
}

div[data-testid="stRadio"] label {
    background: rgba(255, 255, 255, 0.12) !important;
    border-radius: 12px !important;
    padding: 12px 16px !important;
    font-weight: 700 !important;
    transition: all 0.2s ease;
    border: 1px solid rgba(255, 255, 255, 0.18) !important;
}

div[data-testid="stRadio"] label:hover {
    background: rgba(255, 255, 255, 0.28) !important;
    transform: translateX(3px);
}

section[data-testid="stSidebar"] button {
    background: rgba(255, 255, 255, 0.2) !important;
    border: 1px solid rgba(255, 255, 255, 0.4) !important;
    border-radius: 12px !important;
    color: #ffffff !important;
    font-weight: 700 !important;
}

.top-search-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #ffffff;
    border-radius: 20px;
    padding: 12px 24px;
    box-shadow: 0 6px 20px rgba(148, 163, 184, 0.15);
    margin-bottom: 22px;
    border: 1px solid #e2e8f0;
}

.search-pill {
    background: #f8fafc;
    border: 1.5px solid #cbd5e1;
    border-radius: 25px;
    padding: 8px 28px;
    width: 340px;
    text-align: center;
    color: #0284c7;
    font-weight: 800;
    letter-spacing: 0.08em;
    font-size: 0.85rem;
}

.top-icons {
    display: flex;
    align-items: center;
    gap: 18px;
}

.icon-badge {
    background: #f1f5f9;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.15rem;
    position: relative;
    box-shadow: 0 3px 10px rgba(0,0,0,0.06);
}

.badge-dot {
    position: absolute;
    top: -3px;
    right: -3px;
    background: #f59e0b;
    color: #ffffff;
    font-size: 0.65rem;
    font-weight: 800;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
}

.welcome-banner {
    background: linear-gradient(95deg, #2cb5e8 0%, #7f8ce8 52%, #b86de6 100%);
    border-radius: 22px;
    padding: 24px 28px 0 28px;
    color: #ffffff;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    box-shadow: 0 12px 28px rgba(127, 140, 232, 0.32);
    margin-bottom: 22px;
    min-height: 195px;
    overflow: hidden;
}

.welcome-text-block {
    padding-bottom: 24px;
    max-width: 62%;
}

.welcome-title {
    font-size: 1.7rem;
    font-weight: 800;
    line-height: 1.2;
    letter-spacing: 0.03em;
    margin-bottom: 10px;
    color: #ffffff;
    text-transform: uppercase;
}

.welcome-sub {
    font-size: 0.86rem;
    color: rgba(255, 255, 255, 0.92);
    line-height: 1.45;
}

.soft-card {
    background: #ffffff;
    border-radius: 22px;
    padding: 20px;
    border: 1.5px solid #e2e8f0;
    box-shadow: 0 8px 22px rgba(148, 163, 184, 0.12);
    text-align: center;
    margin-bottom: 18px;
}

.soft-card-title {
    font-size: 0.82rem;
    font-weight: 800;
    color: #0284c7;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 14px;
}

.temp-circle {
    width: 138px;
    height: 138px;
    border-radius: 50%;
    margin: 0 auto 14px auto;
    background: #ffffff;
    border: 10px solid #f1f5f9;
    box-shadow: inset 0 4px 12px rgba(0,0,0,0.06), 0 6px 16px rgba(127, 140, 232, 0.18);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}

.temp-val {
    font-size: 2.0rem;
    font-weight: 800;
    color: #6366f1;
}

.pie-circle {
    width: 138px;
    height: 138px;
    border-radius: 50%;
    margin: 0 auto 14px auto;
    background: conic-gradient(
        #f97316 0% 10%,
        #facc15 10% 25%,
        #a855f7 25% 50%,
        #22b8cf 50% 100%
    );
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 6px 16px rgba(148, 163, 184, 0.25);
    position: relative;
}

.pie-legend {
    display: flex;
    justify-content: space-around;
    font-size: 0.72rem;
    font-weight: 700;
    color: #64748b;
    margin-top: 8px;
}

.section-heading {
    font-size: 1.15rem;
    font-weight: 800;
    color: #0284c7;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 12px;
}

.device-card {
    background: #ffffff;
    border-radius: 20px;
    padding: 16px 18px;
    border: 1.5px solid #e2e8f0;
    box-shadow: 0 6px 18px rgba(148, 163, 184, 0.11);
    margin-bottom: 14px;
    text-align: center;
}

.device-title {
    font-size: 0.78rem;
    font-weight: 800;
    color: #0284c7;
    letter-spacing: 0.06em;
    margin-bottom: 8px;
}

.toggle-pill {
    display: inline-flex;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.7rem;
    font-weight: 800;
    background: linear-gradient(90deg, #a855f7 50%, #e2e8f0 50%);
    color: #ffffff;
    gap: 10px;
    margin-top: 6px;
}

.room-grid {
    background: #ffffff;
    border-radius: 22px;
    padding: 18px;
    border: 1.5px solid #e2e8f0;
    box-shadow: 0 8px 22px rgba(148, 163, 184, 0.12);
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}

.room-pill-active {
    background: linear-gradient(90deg, #0284c7, #a855f7);
    color: #ffffff;
    border-radius: 20px;
    padding: 9px 14px;
    text-align: center;
    font-size: 0.75rem;
    font-weight: 800;
    letter-spacing: 0.05em;
}

.room-pill-soft {
    background: linear-gradient(90deg, #bae6fd, #e9d5ff);
    color: #0369a1;
    border-radius: 20px;
    padding: 9px 14px;
    text-align: center;
    font-size: 0.75rem;
    font-weight: 800;
    letter-spacing: 0.05em;
}

div[data-testid="stHorizontalBlock"]:has(#floating-ai-anchor) {
    position: fixed !important;
    bottom: 24px !important;
    right: 28px !important;
    width: auto !important;
    z-index: 99999 !important;
    display: flex !important;
    align-items: center !important;
    gap: 12px !important;
    background: transparent !important;
}

div[data-testid="stHorizontalBlock"]:has(#floating-ai-anchor) > div {
    width: auto !important;
    flex: 0 0 auto !important;
}

div[data-testid="stHorizontalBlock"]:has(#floating-ai-anchor) > div:nth-child(1) div[data-testid="stPopover"] > div > button {
    width: 54px !important;
    height: 54px !important;
    min-width: 54px !important;
    border-radius: 50% !important;
    background: linear-gradient(135deg, #00c6ff 0%, #7f8ce8 55%, #9b5de5 100%) !important;
    color: #ffffff !important;
    border: 2px solid rgba(255, 255, 255, 0.85) !important;
    box-shadow: 0 6px 18px rgba(127, 140, 232, 0.45) !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-size: 1.35rem !important;
    transition: none !important;
    animation: none !important;
}

div[data-testid="stHorizontalBlock"]:has(#floating-ai-anchor) > div:nth-child(1) div[data-testid="stPopover"] > div > button svg {
    display: none !important;
}

div[data-testid="stHorizontalBlock"]:has(#floating-ai-anchor) > div:nth-child(2) div[data-testid="stPopover"] > div > button {
    height: 54px !important;
    border-radius: 30px !important;
    background: linear-gradient(95deg, #00d2ff 0%, #6366f1 55%, #9b5de5 100%) !important;
    color: #ffffff !important;
    border: 2px solid rgba(255, 255, 255, 0.85) !important;
    padding: 0 24px !important;
    font-weight: 800 !important;
    font-size: 0.95rem !important;
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.45) !important;
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
}

div[data-testid="stHorizontalBlock"]:has(#floating-ai-anchor) > div:nth-child(2) div[data-testid="stPopover"] > div > button svg {
    display: none !important;
}

div[data-testid="stPopoverBody"] {
    background: #0f172a !important;
    border: 1px solid #334155 !important;
    border-radius: 18px !important;
    color: #f8fafc !important;
    width: 390px !important;
    max-width: 92vw !important;
    box-shadow: 0 20px 45px rgba(2, 6, 23, 0.65) !important;
    padding: 16px !important;
}

div[data-testid="stPopoverBody"] * {
    color: #f1f5f9 !important;
}

div[data-testid="stPopoverBody"] div[data-testid="stTextInput"] input {
    background: #1e293b !important;
    color: #ffffff !important;
    border: 1px solid #06b6d4 !important;
    border-radius: 12px !important;
}
</style>
""", unsafe_allow_html=True)


def get_gender_cartoon_svg(sex_str: str) -> str:
    if str(sex_str).strip().lower() == "female":
        return """
        <svg width="165" height="175" viewBox="0 0 180 190" xmlns="http://www.w3.org/2000/svg" style="display:block;">
            <path d="M42,88 C38,40 142,40 138,88 C144,128 148,155 135,172 L45,172 C32,155 36,128 42,88 Z" fill="#2d1b4e"/>
            <circle cx="90" cy="30" r="20" fill="#2d1b4e"/>
            <path d="M35,190 C38,142 142,142 145,190 Z" fill="#0284c7"/>
            <path d="M68,145 L90,168 L112,145 Z" fill="#e0f2fe"/>
            <rect x="79" y="116" width="22" height="32" rx="10" fill="#ffcdb2"/>
            <ellipse cx="90" cy="86" rx="34" ry="38" fill="#ffddd2"/>
            <path d="M54,75 C62,48 118,48 126,75 C115,60 65,60 54,75 Z" fill="#2d1b4e"/>
            <circle cx="76" cy="84" r="3.8" fill="#1e293b"/>
            <circle cx="104" cy="84" r="3.8" fill="#1e293b"/>
            <path d="M72,74 Q76,70 81,74" stroke="#2d1b4e" stroke-width="2.5" fill="none" stroke-linecap="round"/>
            <path d="M99,74 Q104,70 108,74" stroke="#2d1b4e" stroke-width="2.5" fill="none" stroke-linecap="round"/>
            <ellipse cx="67" cy="94" rx="6" ry="3.5" fill="#f43f5e" opacity="0.35"/>
            <ellipse cx="113" cy="94" rx="6" ry="3.5" fill="#f43f5e" opacity="0.35"/>
            <path d="M81,101 Q90,110 99,101" stroke="#e11d48" stroke-width="3" fill="none" stroke-linecap="round"/>
            <circle cx="55" cy="92" r="4" fill="#fbbf24"/>
            <circle cx="125" cy="92" r="4" fill="#fbbf24"/>
        </svg>
        """
    return """
    <svg width="165" height="175" viewBox="0 0 180 190" xmlns="http://www.w3.org/2000/svg" style="display:block;">
        <path d="M32,190 C36,140 144,140 148,190 Z" fill="#0369a1"/>
        <path d="M72,144 L90,164 L108,144 Z" fill="#38bdf8"/>
        <rect x="78" y="116" width="24" height="32" rx="10" fill="#f5ebe0"/>
        <ellipse cx="54" cy="88" rx="6" ry="10" fill="#f5cbb7"/>
        <ellipse cx="126" cy="88" rx="6" ry="10" fill="#f5cbb7"/>
        <ellipse cx="90" cy="86" rx="35" ry="39" fill="#ffddd2"/>
        <path d="M53,78 C50,42 130,38 127,78 C122,56 95,52 68,58 C58,60 55,68 53,78 Z" fill="#1e1b4b"/>
        <circle cx="76" cy="85" r="3.8" fill="#1e293b"/>
        <circle cx="104" cy="85" r="3.8" fill="#1e293b"/>
        <path d="M70,74 Q76,71 82,74" stroke="#1e1b4b" stroke-width="3" fill="none" stroke-linecap="round"/>
        <path d="M98,74 Q104,71 110,74" stroke="#1e1b4b" stroke-width="3" fill="none" stroke-linecap="round"/>
        <ellipse cx="67" cy="94" rx="5.5" ry="3" fill="#fb7185" opacity="0.35"/>
        <ellipse cx="113" cy="94" rx="5.5" ry="3" fill="#fb7185" opacity="0.35"/>
        <path d="M80,102 Q90,110 100,102" stroke="#e11d48" stroke-width="2.8" fill="none" stroke-linecap="round"/>
    </svg>
    """


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
    st.markdown("<h3 style='text-align:center; margin-bottom:14px;'>🛰️ COSMOCARE</h3>", unsafe_allow_html=True)

    nav_page = st.radio(
        "Menu",
        [
            "🏠 HOME",
            "📊 STATISTICS & TRIAGE",
            "🛡️ SECURITY & ALERTS",
            "👥 MEMBERS & PROFILE",
            "💡 LIGHTS, SLEEP & RATIONS"
        ],
        index=0,
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.caption("⚙️ **SIMULATION CONTROLS**")
    mission_hour = st.slider("Ship Clock (Hours)", 0, 23, int(mission_state.get("ship_time", "08:00").split(":")[0]))
    simulated_time = f"{mission_hour:02d}:00"
    db.set_mission_state("ship_time", simulated_time)

    distance_m_km = st.number_input("Distance (Million km)", min_value=0.0004, max_value=400.0, value=float(mission_state.get("distance_million_km", 225.0)), step=5.0)
    db.set_mission_state("distance_million_km", str(distance_m_km))
    distance_km = distance_m_km * 1_000_000.0

    anomaly = st.selectbox("Trigger Anomaly", ["None", "arrhythmia", "hypovolemia", "high_co2", "radiation_spike"])
    if st.button("⚡ Pulse Telemetry", use_container_width=True):
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

    clock_event = agent.get_proactive_clock_prompt(simulated_time, active_profile.get("name", "Astronaut"))
    if clock_event:
        if st.button(f"🔔 Trigger {simulated_time} Prompt", use_container_width=True):
            st.session_state.chat_history.append({"role": "AI", "content": clock_event["voice_text"]})
            generate_and_play_tts(clock_event["voice_text"])
            st.rerun()

    st.markdown("---")
    if st.button("🚪 LOG OUT", use_container_width=True):
        st.session_state.authenticated_user = None
        st.session_state.astronaut_id = None
        st.rerun()

v = st.session_state.current_vitals
env = st.session_state.current_env
active_alerts = alerts_mgr.evaluate_all_dangers(st.session_state.astronaut_id, v, env, distance_km=distance_km)
triage_info = logic.BioAstronauticsLogic.evaluate_triage(v)
derived_bio = db.calculate_derived_biometrics(active_profile)

alert_count = len(active_alerts) if active_alerts else 1
first_name = active_profile.get("name", "Brandon").split()[-1].upper()
sex_val = active_profile.get("sex", "Female")
avatar_svg = get_gender_cartoon_svg(sex_val)

st.markdown(f"""
<div class="top-search-bar">
    <div style="display:flex; align-items:center; gap:10px;">
        <div class="search-pill">SEARCH • {st.session_state.astronaut_id} ({simulated_time})</div>
        <span style="font-size:1.3rem;">🔍</span>
    </div>
    <div class="top-icons">
        <div class="icon-badge">👤<div class="badge-dot" style="background:#0ea5e9;">3</div></div>
        <div class="icon-badge">🔔<div class="badge-dot">{alert_count}</div></div>
        <div class="icon-badge">☰</div>
    </div>
</div>
""", unsafe_allow_html=True)

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

if nav_page == "🏠 HOME":
    left_main, right_main = st.columns([1.15, 1.05], gap="large")

    with left_main:
        st.markdown(f"""
        <div class="welcome-banner">
            <div class="welcome-text-block">
                <div class="welcome-title">WELCOME<br>BACK, {first_name}</div>
                <div class="welcome-sub">
                    Role: <strong>{active_profile.get('role', 'Mission Specialist')}</strong> ({sex_val})<br>
                    Heart Rate: <strong>{v.hr} bpm</strong> • BP: <strong>{v.sbp}/{v.dbp} mmHg</strong><br>
                    BMI: <strong>{derived_bio['bmi']}</strong> • Target: <strong>{derived_bio['daily_kcal_target']} kcal/day</strong>
                </div>
            </div>
            <div>{avatar_svg}</div>
        </div>
        """, unsafe_allow_html=True)

        c_temp, c_stat = st.columns(2)
        with c_temp:
            st.markdown(f"""
            <div class="soft-card">
                <div class="soft-card-title">TEMPERATURE &amp; O₂</div>
                <div class="temp-circle">
                    <div class="temp-val">{env['temperature_c']}°C</div>
                    <div style="font-size:0.72rem; color:#94a3b8; font-weight:700;">O₂: {env['oxygen_percent']}%</div>
                </div>
                <div style="font-size:0.78rem; color:#64748b; font-weight:700;">— ───●─── +</div>
            </div>
            """, unsafe_allow_html=True)

        with c_stat:
            st.markdown(f"""
            <div class="soft-card">
                <div class="soft-card-title">STATISTICS</div>
                <div class="pie-circle">
                    <div style="color:#ffffff; font-weight:800; font-size:0.85rem; text-shadow:0 1px 4px rgba(0,0,0,0.4);">50% | 25%</div>
                </div>
                <div class="pie-legend">
                    <span><span style="color:#22b8cf;">■</span> OXYGEN</span>
                    <span><span style="color:#facc15;">■</span> POWER</span>
                </div>
                <div class="pie-legend">
                    <span><span style="color:#f97316;">■</span> RATIONS</span>
                    <span><span style="color:#a855f7;">■</span> WATER</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        c_door1, c_door2 = st.columns(2)
        with c_door1:
            st.markdown("""
            <div class="soft-card" style="padding:14px;">
                <div class="soft-card-title" style="margin-bottom:8px;">FRONT AIRLOCK</div>
                <div style="display:flex; justify-content:center; gap:14px; font-size:1.1rem;">
                    <span style="background:#e0f2fe; padding:6px 12px; border-radius:10px;">🔒</span>
                    <span style="background:#f3e8ff; padding:6px 12px; border-radius:10px;">🔓</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with c_door2:
            st.markdown("""
            <div class="soft-card" style="padding:14px;">
                <div class="soft-card-title" style="margin-bottom:8px;">DOCKING HATCH</div>
                <div style="display:flex; justify-content:center; gap:14px; font-size:1.1rem;">
                    <span style="background:#e0f2fe; padding:6px 12px; border-radius:10px;">🔒</span>
                    <span style="background:#f3e8ff; padding:6px 12px; border-radius:10px;">🔓</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with right_main:
        st.markdown('<div class="section-heading">MY DEVICES &amp; LIFE SUPPORT</div>', unsafe_allow_html=True)
        d_col1, d_col2, d_col3 = st.columns([1.2, 1.2, 0.65])
        with d_col1:
            st.markdown(f"""
            <div class="device-card">
                <div class="device-title">CO₂ SCRUBBER</div>
                <div style="font-size:1.7rem; margin:6px 0;">🌬️</div>
                <div style="font-size:0.72rem; color:#64748b;">{env['co2_ppm']} ppm</div>
                <div class="toggle-pill"><span>ON</span><span style="color:#64748b;">OFF</span></div>
            </div>
            <div class="device-card">
                <div class="device-title">WATER RECYCLER</div>
                <div style="font-size:1.7rem; margin:6px 0;">💧</div>
                <div style="font-size:0.72rem; color:#64748b;">Target: {derived_bio['hydration_target_l']} L</div>
                <div class="toggle-pill"><span>ON</span><span style="color:#64748b;">OFF</span></div>
            </div>
            """, unsafe_allow_html=True)

        with d_col2:
            st.markdown(f"""
            <div class="device-card">
                <div class="device-title">BIOMETRIC MONITOR</div>
                <div style="font-size:1.7rem; margin:6px 0;">🖥️</div>
                <div style="font-size:0.72rem; color:#64748b;">HRV: {v.hrv} ms</div>
                <div class="toggle-pill"><span>ON</span><span style="color:#64748b;">OFF</span></div>
            </div>
            <div class="device-card">
                <div class="device-title">CIRCADIAN LAMP</div>
                <div style="font-size:1.7rem; margin:6px 0;">🛋️</div>
                <div style="font-size:0.72rem; color:#64748b;">ARED: {triage_info['ared_mod']}%</div>
                <div class="toggle-pill"><span>ON</span><span style="color:#64748b;">OFF</span></div>
            </div>
            """, unsafe_allow_html=True)

        with d_col3:
            if st.button("➕\nSLEEP", use_container_width=True):
                routine.start_sleep_session(st.session_state.astronaut_id)
                st.toast("Sleep session started!", icon="🛌")
            if st.button("➕\nWAKE", use_container_width=True):
                res = routine.confirm_wake_up_and_calculate_sleep(st.session_state.astronaut_id)
                st.session_state.chat_history.append({"role": "AI", "content": res["message"]})
                generate_and_play_tts(res["message"])
                st.rerun()
            if st.button("➕\nRATION", use_container_width=True):
                supply.consume_ration(st.session_state.astronaut_id, 1, 1.0)
                st.toast("Logged 1 ration pack!", icon="🍽️")

        st.markdown('<div class="section-heading" style="margin-top:8px;">MY ROOMS &amp; HABITAT MODULES</div>', unsafe_allow_html=True)
        r_col1, r_col2 = st.columns([1.55, 1])
        with r_col1:
            st.markdown("""
            <div class="room-grid">
                <div class="room-pill-active">LIVING QUARTERS</div>
                <div class="room-pill-soft">COMMAND DECK</div>
                <div class="room-pill-soft">SLEEP POD BAY</div>
                <div class="room-pill-active">MEDICAL BAY</div>
                <div class="room-pill-soft">GALLEY RATIONS</div>
                <div class="room-pill-active">ARED GYM LAB</div>
            </div>
            """, unsafe_allow_html=True)
        with r_col2:
            st.markdown("""
            <div class="soft-card" style="padding:14px;">
                <div class="soft-card-title" style="margin-bottom:6px;">LIGHT INTENSITY</div>
                <div style="font-size:1.35rem; font-weight:800; color:#7c3aed; margin:8px 0;">76%</div>
                <div style="font-size:0.72rem; color:#64748b;">— ────●── +</div>
                <div class="toggle-pill"><span>ON</span><span style="color:#64748b;">OFF</span></div>
            </div>
            """, unsafe_allow_html=True)

elif nav_page == "📊 STATISTICS & TRIAGE":
    st.subheader(f"📊 Clinical Status ({active_profile.get('name')}): {triage_info['status_level']} — {triage_info['diagnosis']}")
    st.info(f"**Phase:** {triage_info['phase_name']} | **Explanation:** {triage_info['explanation']}")
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

elif nav_page == "🛡️ SECURITY & ALERTS":
    st.subheader("🛡️ Spacecraft Security & Danger Alert Logs")
    conn = db.get_connection()
    alert_rows = [dict(r) for r in conn.execute("SELECT * FROM crew_danger_alerts ORDER BY alert_id DESC LIMIT 15").fetchall()]
    tx_rows = [dict(r) for r in conn.execute("SELECT * FROM reorder_transmissions ORDER BY transmission_id DESC LIMIT 10").fetchall()]
    conn.close()
    st.caption("Recent Crew & Habitat Danger Alerts (`crew_danger_alerts`):")
    st.dataframe(alert_rows, use_container_width=True)
    st.caption("Automated Earth Mission Control Transmissions (`reorder_transmissions`):")
    st.dataframe(tx_rows, use_container_width=True)

elif nav_page == "👥 MEMBERS & PROFILE":
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

elif nav_page == "💡 LIGHTS, SLEEP & RATIONS":
    inv_eval = supply.evaluate_inventory_and_trigger(distance_km)
    conn = db.get_connection()
    inv_rows = [dict(r) for r in conn.execute("SELECT * FROM inventory").fetchall()]
    sleep_logs = [dict(r) for r in conn.execute("SELECT session_id, sleep_start, wake_confirm, duration_hours, status FROM sleep_sessions WHERE astronaut_id = ? ORDER BY session_id DESC LIMIT 8", (st.session_state.astronaut_id,)).fetchall()]
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
    st.caption("Recent Sleep Sessions (`sleep_sessions` table):")
    st.dataframe(sleep_logs, use_container_width=True)

user_text = ""
voice_col, chat_col = st.columns([1, 1])

with voice_col:
    st.markdown('<div id="floating-ai-anchor"></div>', unsafe_allow_html=True)
    with st.popover("🎙️"):
        st.markdown("**🎙️ Voice Channel — Speak to CosmoCare AI**")
        if hasattr(st, "audio_input"):
            web_audio = st.audio_input("Tap Mic & Speak (Auto-Sends on Stop):", label_visibility="collapsed")
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
            st.caption(f"✨ Sent: `{st.session_state.last_voice_text}`")

with chat_col:
    with st.popover("💬 Mental Health AI"):
        st.markdown("""
        <div style="border-bottom:1px solid #334155; padding-bottom:8px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;">
            <span style="font-weight:800; color:#38bdf8;">💬 Mental Health AI</span>
            <span style="font-size:0.7rem; color:#10b981;">● Encrypted Channel</span>
        </div>
        """, unsafe_allow_html=True)

        chat_box = st.container(height=280)
        with chat_box:
            if not st.session_state.chat_history:
                st.caption("Hello! I am CosmoCare. Type a message or use the circular mic icon to speak with me.")
            for msg in st.session_state.chat_history:
                align = "right" if msg["role"] == "User" else "left"
                bg = "linear-gradient(135deg, #00c6ff, #0072ff)" if msg["role"] == "User" else "#1e293b"
                st.markdown(f"""
                <div style="text-align:{align}; margin-bottom:8px;">
                    <div style="display:inline-block; background:{bg}; color:#ffffff; padding:8px 13px; border-radius:14px; max-width:85%; text-align:left; font-size:0.84rem;">
                        {msg['content']}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with st.form("popup_chat_form", clear_on_submit=True):
            c_in, c_send = st.columns([4.2, 1])
            with c_in:
                typed_msg = st.text_input("Message", placeholder="Test dialogue message...", label_visibility="collapsed")
            with c_send:
                send_btn = st.form_submit_button("➤")
            if send_btn and typed_msg.strip():
                st.session_state.last_voice_text = ""
                user_text = typed_msg.strip()

        st.markdown('<div style="font-size:0.68rem; color:#64748b; margin-top:6px;">🛡️ Encrypted Psychological Channel • Mission Medical Rule 4.12</div>', unsafe_allow_html=True)

if user_text:
    st.session_state.chat_history.append({"role": "User", "content": user_text})
    with st.spinner("CosmoCare AI is responding..."):
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
