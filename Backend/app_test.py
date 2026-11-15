import streamlit as st
import logic
import os
import edge_tts
import asyncio
import base64
import speech_recognition as sr
import tempfile
import uuid
from pathlib import Path

st.set_page_config(page_title="CosmoCare Space Dashboard", layout="wide")


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

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "astronaut_id" not in st.session_state:
    st.session_state.astronaut_id = "A004"
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


with st.sidebar:
    st.title("⚙️ Mission Controls")
    mission_hour = st.slider("Select Time (Hours)", 0, 23, 7)
    simulated_time = f"{mission_hour:02d}:00"
    st.info(f"Current Ship Time: **{simulated_time}**")

    clock_event = agent.get_proactive_clock_prompt(simulated_time, "Dr. Sarah Mitchell")
    if clock_event:
        if st.button(f"🔔 Trigger {simulated_time} Event"):
            st.session_state.chat_history.append({"role": "AI", "content": clock_event['voice_text']})
            generate_and_play_tts(clock_event['voice_text'])
            st.rerun()

    st.markdown("---")
    anomaly = st.selectbox("Trigger Anomaly", ["None", "arrhythmia", "hypovolemia", "high_co2", "radiation_spike"])
    if st.button("Generate Telemetry"):
        st.session_state.current_vitals = sim.generate_live_vitals(
            st.session_state.astronaut_id,
            anomaly_mode=anomaly if anomaly in ("arrhythmia", "hypovolemia", "high_co2") else None
        )
        st.session_state.current_env = sim.generate_environment_reading(
            anomaly_mode="cabin_danger" if anomaly == "high_co2" else None
        )
        sim.generate_radiation_reading(spike=(anomaly == "radiation_spike"))
        st.session_state.announce_alerts_now = True
        st.success("Telemetry Generated!")

st.title("🚀 CosmoCare Medical & AI Dashboard")

active_alerts = None
if "current_vitals" in st.session_state:
    v = st.session_state.current_vitals
    env = st.session_state.current_env
    active_alerts = alerts_mgr.evaluate_all_dangers(st.session_state.astronaut_id, v, env)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💓 HR", f"{v.hr} bpm")
    c2.metric("🩸 BP", f"{v.sbp}/{v.dbp}")
    c3.metric("💨 O2", f"{env['oxygen_percent']}%")
    c4.metric("🌫️ CO2", f"{env['co2_ppm']} ppm")

    if active_alerts:
        combined_voice_alerts = []
        for alert in active_alerts:
            st.error(f"**{alert['severity']} ALERT:** {alert['title']} - {alert['message']}")
            if alert.get('voice_announcement'):
                combined_voice_alerts.append(alert['voice_announcement'])

        if st.session_state.announce_alerts_now and combined_voice_alerts:
            full_alert_speech = " ".join(combined_voice_alerts)
            st.session_state.chat_history.append({"role": "AI", "content": f"🚨 {full_alert_speech}"})
            generate_and_play_tts(full_alert_speech)
            st.session_state.announce_alerts_now = False

if st.session_state.tts_audio_bytes:
    st.audio(st.session_state.tts_audio_bytes, format="audio/mp3", autoplay=True)
    st.session_state.tts_audio_bytes = None

st.markdown("---")
st.subheader("💬 AI Companion (Auto-Send Voice & Text)")

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

        if st.button("✅ Song Finished (Trigger AI Check-in)"):
            st.session_state.active_media = None
            followup = "How did that feel? Did the music help you relax? Are you feeling a bit happier now, or still down?"
            st.session_state.chat_history.append({"role": "AI", "content": followup})
            generate_and_play_tts(followup)
            st.rerun()
    else:
        st.warning(f"Media file not found at `{raw_path}`. Ensure `assets/media/` with `.mp3` files is uploaded to GitHub.")

for msg in st.session_state.chat_history:
    with st.chat_message("user" if msg["role"] == "User" else "assistant"):
        st.write(msg["content"])

user_text = ""

if hasattr(st, "audio_input"):
    web_audio = st.audio_input("🌐 Tap to Speak (Auto-Sends when you click Stop):")
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

typed_input = st.chat_input("Or type your message here and press Enter...")
if typed_input:
    st.session_state.last_voice_text = ""
    user_text = typed_input

if user_text:
    st.session_state.chat_history.append({"role": "User", "content": user_text})
    with st.spinner("AI is responding..."):
        response = agent.chat(
            st.session_state.astronaut_id,
            user_text,
            is_voice_input=True,
            active_alerts=active_alerts,
            simulated_time=simulated_time
        )

        ai_reply = response["ai_text"]
        if ai_reply:
            st.session_state.chat_history.append({"role": "AI", "content": ai_reply})
            generate_and_play_tts(ai_reply)

        if response.get("play_media_now"):
            st.session_state.tts_audio_bytes = None
            st.session_state.active_media = response.get("media_file")

    st.rerun()
