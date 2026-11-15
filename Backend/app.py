import streamlit as st
import logic
import os
import edge_tts
import asyncio
import speech_recognition as sr
import tempfile
import uuid
from pathlib import Path

st.set_page_config(page_title="CosmoCare Deep Space Medical & AI Suite", page_icon="🚀", layout="wide")


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
    st.session_state.authenticated_user = db.get_astronaut_by_id("A004")
if "astronaut_id" not in st.session_state:
    st.session_state.astronaut_id = "A004"
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
    st.title("🚀 CosmoCare Command")

    with st.expander("🔐 Crew Switch / Authentication", expanded=False):
        login_id = st.selectbox("Select Astronaut ID", ["A004", "A005", "A006"])
        login_pw = st.text_input("Password (Default: Sarah@2026 / Holden@2026 / Elena@2026)", value="Sarah@2026", type="password")
        if st.button("Switch Active Crew", use_container_width=True):
            auth = db.authenticate_user(login_id, login_pw)
            if auth:
                st.session_state.authenticated_user = auth
                st.session_state.astronaut_id = auth["astronaut_id"]
                st.success(f"Logged in: {auth['name']}")
                st.rerun()
            else:
                st.error("Invalid credentials.")

    active_profile = db.get_astronaut_by_id(st.session_state.astronaut_id) or {}
    st.caption(f"👩‍🚀 **Active Crew:** {active_profile.get('name', 'Dr. Sarah Mitchell')} (`{st.session_state.astronaut_id}`) - {active_profile.get('role', '')}")

    mission_state = db.get_mission_state()
    mission_hour = st.slider("Ship Clock (Hours)", 0, 23, 8)
    simulated_time = f"{mission_hour:02d}:00"
    db.set_mission_state("ship_time", simulated_time)
    distance_m_km = st.number_input("Distance from Earth (Million km)", min_value=0.0004, max_value=400.0, value=float(mission_state.get("distance_million_km", 225.0)), step=5.0)
    db.set_mission_state("distance_million_km", str(distance_m_km))
    distance_km = distance_m_km * 1_000_000.0

    clock_event = agent.get_proactive_clock_prompt(simulated_time, active_profile.get("name", "Astronaut"))
    if clock_event:
        if st.button(f"🔔 Trigger {simulated_time} Schedule", use_container_width=True):
            st.session_state.chat_history.append({"role": "AI", "content": clock_event["voice_text"]})
            generate_and_play_tts(clock_event["voice_text"])
            st.rerun()

    st.markdown("---")
    st.subheader("📡 Telemetry & Anomaly Simulator")
    anomaly = st.selectbox("Simulate Condition", ["None", "arrhythmia", "hypovolemia", "high_co2", "radiation_spike"])
    if st.button("⚡ Generate Live Telemetry", use_container_width=True):
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

    st.markdown("---")
    st.subheader("🛌 Sleep & Ration Quick-Log")
    c_s1, c_s2 = st.columns(2)
    with c_s1:
        if st.button("🛌 Start Sleep", use_container_width=True):
            routine.start_sleep_session(st.session_state.astronaut_id)
            st.toast("Sleep timer started in DB!", icon="🛌")
            st.rerun()
    with c_s2:
        if st.button("☀️ Wake Up", use_container_width=True):
            res = routine.confirm_wake_up_and_calculate_sleep(st.session_state.astronaut_id)
            st.session_state.chat_history.append({"role": "AI", "content": res["message"]})
            generate_and_play_tts(res["message"])
            st.rerun()

if "current_vitals" not in st.session_state:
    st.session_state.current_vitals = sim.get_latest_vitals(st.session_state.astronaut_id)
if "current_env" not in st.session_state:
    st.session_state.current_env = sim.generate_environment_reading()

v = st.session_state.current_vitals
env = st.session_state.current_env
active_alerts = alerts_mgr.evaluate_all_dangers(st.session_state.astronaut_id, v, env, distance_km=distance_km)
triage_info = logic.BioAstronauticsLogic.evaluate_triage(v)

st.title("🌌 CosmoCare Autonomous Space Medicine & AI Companion")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("💓 Heart Rate", f"{v.hr} bpm", f"Z: {triage_info['z_scores']['hr']:+.2f}")
m2.metric("🩸 Blood Pressure", f"{v.sbp}/{v.dbp} mmHg", f"MAP: {triage_info['hemodynamics']['map']}")
m3.metric("🧠 HRV (RMSSD)", f"{v.hrv} ms", f"Z: {triage_info['z_scores']['hrv']:+.2f}")
m4.metric("💨 Cabin O2", f"{env['oxygen_percent']}%")
m5.metric("🌫️ Cabin CO2", f"{env['co2_ppm']} ppm")

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

tab_ai, tab_med, tab_supply, tab_bio = st.tabs([
    "💬 AI Voice Companion & Media",
    "🩺 Clinical Triage & Waveforms",
    "📦 Deep Space Supply & Rations",
    "🧬 Biometrics, Schedule & DB Logs"
])

with tab_ai:
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
            st.warning(f"Media file not found at `{raw_path}`. Ensure `assets/media/` contains `.mp3` files.")

    for msg in st.session_state.chat_history:
        with st.chat_message("user" if msg["role"] == "User" else "assistant"):
            st.write(msg["content"])

    user_text = ""
    if hasattr(st, "audio_input"):
        web_audio = st.audio_input("🌐 Tap to Speak (Auto-Corrects & Auto-Sends when you click Stop):")
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

    typed_input = st.chat_input("Speak via mic above or type here (e.g., 'I feel sad', 'I ate 2 Rice rations', 'I am awake')...")
    if typed_input:
        st.session_state.last_voice_text = ""
        user_text = typed_input

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

with tab_med:
    st.subheader(f"Clinical Status: {triage_info['status_level']} — {triage_info['diagnosis']}")
    st.info(f"**Phase:** {triage_info['phase_name']} | **Explanation:** {triage_info['explanation']}")
    st.write(f"**Verification Protocol:** {triage_info['verification']}")
    st.write("**Countermeasure Action Steps:**")
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

with tab_supply:
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
        chosen_item = st.selectbox("Select Supply / Ration Item", inv_rows, format_func=lambda x: f"{x['item_name']} ({x['quantity']} {x['unit']})")
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

with tab_bio:
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.subheader("🧬 Astronaut Biometrics & Targets")
        derived = db.calculate_derived_biometrics(active_profile)
        st.write(f"**BMI:** `{derived['bmi']}` ({derived['bmi_status']}) | **Daily Calorie Target:** `{derived['daily_kcal_target']} kcal` | **Water Target:** `{derived['hydration_target_l']} L/day`")
        with st.form("biometrics_form"):
            new_h = st.number_input("Height (cm)", value=float(active_profile.get("height_cm", 170.5)))
            new_w = st.number_input("Weight (kg)", value=float(active_profile.get("weight_kg", 65.0)))
            new_age = st.number_input("Age", value=int(active_profile.get("age", 42)))
            new_fit = st.selectbox("Fitness Level", ["High", "Moderate", "Low"], index=0)
            if st.form_submit_button("💾 Save Biometrics to DB"):
                db.update_astronaut_biometrics(st.session_state.astronaut_id, new_h, new_w, new_age, new_fit)
                st.success("Biometrics updated in SQLite DB!")
                st.rerun()


    with col_b2:
        st.subheader("🗄️ Live Sleep Sessions & Notifications DB")
        conn = db.get_connection()
        sleep_logs = [dict(r) for r in conn.execute("SELECT session_id, sleep_start, wake_confirm, duration_hours, status FROM sleep_sessions WHERE astronaut_id = ? ORDER BY session_id DESC LIMIT 5", (st.session_state.astronaut_id,)).fetchall()]
        cons_logs = [dict(r) for r in conn.execute("SELECT c.log_id, i.item_name, c.quantity_consumed, c.logged_at FROM consumption_logs c JOIN inventory i ON c.item_id = i.item_id WHERE c.astronaut_id = ? ORDER BY c.log_id DESC LIMIT 5", (st.session_state.astronaut_id,)).fetchall()]
        conn.close()
        st.caption("Recent Sleep Sessions (`sleep_sessions` table):")
        st.dataframe(sleep_logs, use_container_width=True)
        st.caption("Recent Ration Consumption (`consumption_logs` table):")
        st.dataframe(cons_logs, use_container_width=True)

    st.markdown("---")
    col_sec, col_med_mgr = st.columns(2)

    with col_sec:
        st.subheader("🔑 Update Crew Password & Schedule")
        with st.form("pw_update_form"):
            new_pw = st.text_input("New Password for " + st.session_state.astronaut_id, type="password")
            if st.form_submit_button("🔒 Update Password in DB"):
                if db.update_astronaut_password(st.session_state.astronaut_id, new_pw):
                    st.success("Password updated in SQLite Database!")
                else:
                    st.error("Password must be at least 4 characters.")

        with st.form("schedule_update_form"):
            st.caption("Add or Update Proactive Clock Schedule (`system_schedule` table):")
            s_time = st.text_input("Time Slot (24h format, e.g., 15:00)", value="15:00")
            s_title = st.text_input("Event Title", value="Afternoon Hydration & Stretch")
            s_prompt = st.text_area("AI Voice Prompt", value="Time for your afternoon water pouch and lumbar stretch.")
            s_alarm = st.checkbox("Play Wake/Alert Alarm")
            if st.form_submit_button("⏰ Save Schedule to DB"):
                db.upsert_schedule(s_time, s_title, s_prompt, s_alarm)
                st.success(f"Schedule for {s_time} saved to DB!")
                st.rerun()

    with col_med_mgr:
        st.subheader("🎵 Personal Media & Voice Recordings Vault")
        uploaded_media = st.file_uploader("Upload Custom Song (.mp3/.wav) or Video (.mp4) for AI Playback", type=["mp3", "wav", "mp4"])
        if uploaded_media is not None:
            cat = "video" if uploaded_media.name.lower().endswith(".mp4") else "music"
            if st.button("⬆️ Save Media to Astronaut Folder & DB"):
                saved_p = db.save_user_media_file(st.session_state.astronaut_id, cat, uploaded_media.name, uploaded_media.getvalue())
                st.success(f"Saved to `{saved_p}` and linked in DB! AI can now play this track.")
                st.rerun()

        user_files = db.get_user_media_list(st.session_state.astronaut_id)
        st.caption("🎙️ **Saved User Voice Recordings (`voice` folder):**")
        if user_files.get("voice"):
            for vf in user_files["voice"][:5]:
                c_v1, c_v2 = st.columns([4, 1])
                with c_v1:
                    st.audio(str(vf))
                with c_v2:
                    if st.button("🗑️", key=f"del_{vf.name}"):
                        db.delete_user_media_file(st.session_state.astronaut_id, str(vf))
                        st.rerun()
        else:
            st.info("No voice recordings saved yet. Speak into the Browser Mic to auto-save logs!")

        st.caption("🎶 **Uploaded Personal Music & Videos (`media_preferences` DB):**")
        for mf in (user_files.get("music", []) + user_files.get("video", [])):
            c_m1, c_m2 = st.columns([4, 1])
            c_m1.write(f"• `{mf.name}`")
            if c_m2.button("🗑️", key=f"del_m_{mf.name}"):
                db.delete_user_media_file(st.session_state.astronaut_id, str(mf))
                st.rerun()
