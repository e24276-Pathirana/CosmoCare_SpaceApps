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
        schedules = {
            "07:00": {
                "event": "MORNING_WAKEUP_ALARM",
                "play_alarm": True,
                "voice_text": f"Good morning {astronaut_name}! Alarm completed. Please confirm you are awake so I can log your sleep duration, and complete your morning symptom check-in."
            },
            "08:00": {
                "event": "BREAKFAST_AND_STOCK_REMINDER",
                "play_alarm": False,
                "voice_text": f"Hello {astronaut_name}, it is time for breakfast and hydration. Please select your consumed ration packs so I can update the ship's food stocks."
            },
            "13:00": {
                "event": "LUNCH_AND_STOCK_REMINDER",
                "play_alarm": False,
                "voice_text": f"Hey {astronaut_name}, lunch time! Did you eat and drink your water ration? Don't forget to log your ration packs."
            },
            "19:00": {
                "event": "EVENING_CHECKIN_AND_DINNER",
                "play_alarm": False,
                "voice_text": f"Good evening {astronaut_name}. Time for dinner rations and your evening health and mood check-in."
            },
            "22:00": {
                "event": "SLEEP_TIME_REMINDER",
                "play_alarm": False,
                "voice_text": f"It is 2200 hours, {astronaut_name}. Time for sleep. Please confirm when you are ready to sleep so I can start your sleep timer."
            }
        }
        return schedules.get(simulated_time_str)

    def get_random_local_media(self, astronaut_id: str) -> Dict[str, str]:
        if MEDIA_DIR.exists():
            files = [f for f in os.listdir(MEDIA_DIR) if f.lower().endswith(('.mp3', '.mp4', '.wav'))]
            if files:
                chosen = random.choice(files)
                m_type = "video" if chosen.lower().endswith(".mp4") else "audio"
                return {
                    "media_type": m_type,
                    "title": chosen,
                    "file_path": str(MEDIA_DIR / chosen)
                }
        return {
            "media_type": "audio",
            "title": "relax_song_1.mp3",
            "file_path": str(MEDIA_DIR / "relax_song_1.mp3")
        }

    def _auto_update_db_from_intent(self, astronaut_id: str, lower_msg: str, reply_text: str) -> List[str]:
        db_updates = []

        # 1. අවදි වීම තහවුරු කිරීම (Confirm Wake-Up -> Update sleep_sessions)
        wake_keywords = ["i am awake", "i'm awake", "woke up", "good morning", "awake now"]
        if "[CONFIRM_WAKE]" in reply_text or any(k in lower_msg for k in wake_keywords):
            res = self.routine_tracker.confirm_wake_up_and_calculate_sleep(astronaut_id)
            db_updates.append(f"Sleep DB Updated: Logged {res['hours_slept']} hrs (Status: AWAKE)")

        # 2. නින්දට යාම තහවුරු කිරීම (Start Sleep -> Insert into sleep_sessions)
        sleep_keywords = ["going to sleep", "ready to sleep", "good night", "sleeping now", "start sleep"]
        if "[CONFIRM_SLEEP]" in reply_text or any(k in lower_msg for k in sleep_keywords):
            self.routine_tracker.start_sleep_session(astronaut_id)
            db_updates.append("Sleep DB Updated: Sleep session timer started (Status: SLEEPING)")

        # 3. ආහාර සහ ජලය පරිභෝජනය (Update Inventory & Consumption Logs)
        eat_keywords = ["ate", "consumed", "had breakfast", "had lunch", "had dinner", "mre", "ration", "protein", "water pouch", "drank"]
        if "[UPDATE_STOCK]" in reply_text or any(k in lower_msg for k in eat_keywords):
            conn = self.db.get_connection()
            items = conn.execute("SELECT * FROM inventory").fetchall()
            conn.close()

            import re
            qty_match = re.search(r"\b(\d+(?:\.\d+)?)\b", lower_msg)
            qty = float(qty_match.group(1)) if qty_match else 1.0

            updated_any = False
            for item in items:
                iname = item["item_name"].lower()
                if ("water" in lower_msg and "water" in iname) or (
                    any(w in lower_msg for w in ["mre", "food", "ration", "protein", "ate", "breakfast", "lunch", "dinner"]) and "ration" in iname
                ):
                    c_res = self.supply_engine.consume_ration(astronaut_id, item["item_id"], rations_count=qty)
                    if c_res.get("success"):
                        db_updates.append(
                            f"Inventory DB Updated: -{qty} {c_res['item_name']} (Remaining: {c_res['remaining_quantity']} {c_res['unit']})"
                        )
                        updated_any = True

            if not updated_any and items and any(w in lower_msg for w in ["ate", "consumed", "ration", "mre"]):
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

        system_prompt = build_master_system_prompt(astronaut_id, simulated_time, active_alerts)
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
