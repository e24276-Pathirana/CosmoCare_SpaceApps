(function () {
  const PATH = window.location.pathname;
  const IS_LOGIN = PATH === "/login" || PATH === "/";

  function getUserId() {
    return localStorage.getItem("cosmo_user_id");
  }

  if (!IS_LOGIN && !getUserId()) {
    window.location.href = "/login";
    return;
  }

  let currentTTSAudio = null;
  let autoVoiceEnabled = localStorage.getItem("cosmo_auto_voice") !== "false";
  let isRecordingVoice = false;
  let recognitionObj = null;
  let mediaRecorderObj = null;
  let recordedChunks = [];

  async function speakText(text) {
    if (!text || !text.trim() || !autoVoiceEnabled) return;
    stopTTS();
    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        currentTTSAudio = new Audio(url);
        currentTTSAudio.onended = () => URL.revokeObjectURL(url);
        await currentTTSAudio.play();
        return;
      }
    } catch (e) {}
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.rate = 1.03;
      window.speechSynthesis.speak(u);
    }
  }

  function stopTTS() {
    if (currentTTSAudio) {
      currentTTSAudio.pause();
      currentTTSAudio = null;
    }
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  }

  function wireLoginPage() {
    const form = document.getElementById("login-form");
    if (!form) return;
    form.onsubmit = async function (e) {
      e.preventDefault();
      const uid = (document.getElementById("username")?.value || "").trim();
      const pwd = (document.getElementById("password")?.value || "").trim();
      const banner = document.getElementById("form-error-banner");
      const bannerMsg = document.getElementById("form-error-message");
      const btnText = document.getElementById("button-text");
      const spinner = document.getElementById("loading-spinner");

      if (!uid || !pwd) {
        if (banner && bannerMsg) {
          bannerMsg.textContent = "Please enter Astronaut ID (A004/A005/A006) and Password.";
          banner.classList.remove("hidden");
        }
        return;
      }

      if (btnText) btnText.textContent = "AUTHENTICATING...";
      if (spinner) spinner.classList.remove("hidden");

      try {
        const res = await fetch("/api/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ astronaut_id: uid, password: pwd })
        });
        if (!res.ok) {
          throw new Error("Invalid Astronaut ID or Passkey");
        }
        const data = await res.json();
        localStorage.setItem("cosmo_user_id", data.user.astronaut_id);
        localStorage.setItem("cosmo_user_name", data.user.name);
        window.location.href = "/home";
      } catch (err) {
        if (banner && bannerMsg) {
          bannerMsg.textContent = err.message;
          banner.classList.remove("hidden");
        }
        if (btnText) btnText.textContent = "LOGIN NOW";
        if (spinner) spinner.classList.add("hidden");
      }
    };
  }

  function rewireAllNavigationLinks() {
    document.querySelectorAll("a, button").forEach((el) => {
      const txt = (el.textContent || "").toUpperCase();
      if (el.tagName === "A") {
        if (txt.includes("COSMO") && txt.includes("CARE")) {
          el.setAttribute("href", "/home");
          el.onclick = null;
        } else if (txt.includes("01") || txt.trim() === "HOME") {
          el.setAttribute("href", "/home");
          el.onclick = null;
        } else if (txt.includes("02") || txt.includes("DEVICES")) {
          el.setAttribute("href", "/devices");
          el.onclick = null;
        } else if (txt.includes("03") || txt.includes("STATISTICS") || txt.includes("SYSTEM OVERVIEW")) {
          el.setAttribute("href", "/statistics");
          el.onclick = null;
        } else if (txt.includes("04") || txt.includes("SECURITY")) {
          el.setAttribute("href", "/security");
          el.onclick = null;
        } else if (txt.includes("05") || txt.includes("SLEEP") || txt.includes("RATIONS")) {
          el.setAttribute("href", "/rations");
          el.onclick = null;
        } else if (txt.includes("CHANGE PROFILE SETTINGS") || el.id === "crew-profile-link") {
          el.setAttribute("href", "/profile");
          el.onclick = null;
        } else if (txt.includes("CREW MEDICAL RECORDS")) {
          el.setAttribute("href", "/statistics");
          el.onclick = null;
        }
      }
      if (txt.includes("LOCK TERMINAL")) {
        el.onclick = function (e) {
          e.preventDefault();
          localStorage.removeItem("cosmo_user_id");
          window.location.href = "/login";
        };
      }
    });
  }

  function ensureFloatingDoraAndMediaBar() {
    if (!document.getElementById("cosmo-media-bar")) {
      const bar = document.createElement("div");
      bar.id = "cosmo-media-bar";
      bar.className = "hidden fixed left-24 md:left-32 bottom-14 z-50 w-96 max-w-[90vw] rounded-2xl border border-cyan-400/50 bg-slate-950/95 backdrop-blur-2xl p-3.5 shadow-[0_0_30px_rgba(0,240,255,0.3)]";      bar.innerHTML = `
        <div class="flex items-center justify-between pb-2 border-b border-cyan-500/20">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
            <span class="text-xs font-mono font-bold text-cyan-300 tracking-wider">PERSONAL MUSIC & VIDEO</span>
          </div>
          <button id="cosmo-media-close" class="text-slate-400 hover:text-white text-xs font-mono px-2">✕</button>
        </div>
        <div id="cosmo-media-title" class="text-xs font-mono text-white mt-2 truncate">Ready</div>
        <div id="cosmo-media-player-slot" class="mt-2"></div>
      `;
      document.body.appendChild(bar);
      document.getElementById("cosmo-media-close").onclick = () => {
        bar.classList.add("hidden");
        document.getElementById("cosmo-media-player-slot").innerHTML = "";
      };
    }

    if (!document.getElementById("cosmo-sim-bar")) {
      const simBar = document.createElement("div");
      simBar.id = "cosmo-sim-bar";
      simBar.className = "fixed left-1/2 -translate-x-1/2 bottom-12 z-40 flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-950/90 border border-cyan-500/30 backdrop-blur-xl text-[10px] font-mono text-cyan-200 shadow-lg";
      simBar.innerHTML = `
        <select id="cosmo-clock-select" class="bg-slate-900 border border-cyan-500/30 rounded-full px-2 py-0.5 text-[10px] text-cyan-300">
          <option value="07:00">07:00 Wake</option>
          <option value="08:00" selected>08:00 Breakfast</option>
          <option value="10:30">10:30 ARED</option>
          <option value="13:00">13:00 Lunch</option>
          <option value="19:00">19:00 Dinner</option>
          <option value="22:00">22:00 Sleep</option>
        </select>
        <button id="cosmo-clock-trigger" class="px-2 py-0.5 rounded-full bg-cyan-500/20 border border-cyan-400/50 hover:bg-cyan-500/40 text-cyan-200">CLOCK</button>
        <select id="cosmo-anomaly-select" class="bg-slate-900 border border-amber-500/30 rounded-full px-2 py-0.5 text-[10px] text-amber-300">
          <option value="None">Nominal</option>
          <option value="arrhythmia">Arrhythmia</option>
          <option value="hypovolemia">Hypovolemia</option>
          <option value="high_co2">High CO2</option>
          <option value="radiation_spike">Radiation Spike</option>
        </select>
        <button id="cosmo-sim-trigger" class="px-2 py-0.5 rounded-full bg-amber-500/20 border border-amber-400/50 hover:bg-amber-500/40 text-amber-200">PULSE</button>
      `;
      document.body.appendChild(simBar);

      document.getElementById("cosmo-clock-trigger").onclick = async () => {
        const aid = getUserId();
        const t = document.getElementById("cosmo-clock-select").value;
        const res = await fetch("/api/clock", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ astronaut_id: aid, ship_time: t })
        });
        const data = await res.json();
        if (data.prompt && data.prompt.voice_text) {
          speakText(data.prompt.voice_text);
          appendDoraMessage(data.prompt.voice_text, false);
          if (data.prompt.voice_text.includes("?")) openDoraDrawer();
        }
        syncFullState();
      };

      document.getElementById("cosmo-sim-trigger").onclick = async () => {
        const aid = getUserId();
        const anom = document.getElementById("cosmo-anomaly-select").value;
        const res = await fetch("/api/simulate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ astronaut_id: aid, anomaly: anom })
        });
        const data = await res.json();
        if (data.voice_announcement) {
          speakText(data.voice_announcement);
          showGlobalAlertToast(data.alerts[0]);
        }
        syncFullState();
      };
    }

    if (!document.getElementById("dora-ai-container")) {
      const container = document.createElement("div");
      container.id = "dora-ai-container";
      container.className = "fixed right-6 bottom-14 z-50 flex flex-col items-end";
      container.innerHTML = `
        <button id="dora-trigger-btn" type="button" class="flex items-center gap-3 pl-2 pr-5 py-2 rounded-full border border-cyan-400 bg-slate-950/95 text-cyan-100 shadow-[0_0_20px_rgba(6,182,212,0.55)] cursor-pointer">
          <div class="w-10 h-10 rounded-full bg-cyan-500/30 border border-cyan-300 flex items-center justify-center font-bold text-white">⚡</div>
          <span class="font-mono font-bold text-lg tracking-widest">DORA</span>
          <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
        </button>
        <div id="dora-chat-drawer" class="hidden absolute right-0 bottom-16 w-96 max-w-[92vw] h-[480px] rounded-2xl border border-cyan-500/40 bg-slate-950/95 backdrop-blur-2xl flex flex-col shadow-2xl">
          <div class="p-3 border-b border-white/10 flex items-center justify-between">
            <span class="text-xs font-mono font-bold text-cyan-300 tracking-widest">DORA // COSMOCARE VOICE AI</span>
            <div class="flex items-center gap-2">
              <button id="dora-auto-voice-toggle" type="button" class="text-[10px] font-mono px-2 py-0.5 rounded border border-cyan-400/40 text-cyan-300"><span id="auto-voice-state">VOICE: ON</span></button>
              <button id="dora-close-btn" type="button" class="text-slate-400 hover:text-white px-1">✕</button>
            </div>
          </div>
          <div id="dora-messages-container" class="flex-1 p-3 overflow-y-auto flex flex-col gap-2.5 text-xs"></div>
          <div class="p-3 border-t border-white/10">
            <form id="dora-chat-form" class="flex items-center gap-2">
              <div class="relative flex-1">
                <input id="dora-chat-input" type="text" placeholder="Type or tap mic to speak..." class="w-full bg-slate-900 border border-cyan-500/30 rounded-xl px-3 py-2 pr-9 text-xs text-white focus:outline-none focus:border-cyan-400" />
                <button id="dora-mic-btn" type="button" class="absolute right-2 top-1/2 -translate-y-1/2 text-cyan-300 hover:text-white text-sm">🎙️</button>
              </div>
              <button id="dora-send-btn" type="submit" class="px-3 py-2 rounded-xl bg-cyan-500/25 border border-cyan-400/50 text-cyan-200 font-bold text-xs">➤</button>
            </form>
          </div>
        </div>
      `;
      document.body.appendChild(container);
    }

    bindDoraEvents();
  }

  function openDoraDrawer() {
    const drawer = document.getElementById("dora-chat-drawer");
    if (drawer) drawer.classList.remove("hidden");
  }

  function appendDoraMessage(text, isUser) {
    const box = document.getElementById("dora-messages-container");
    if (!box || !text) return;
    const div = document.createElement("div");
    div.className = isUser ? "flex justify-end" : "flex justify-start";
    div.innerHTML = isUser
      ? `<div class="px-3 py-2 rounded-xl bg-cyan-500/20 border border-cyan-400/40 text-cyan-100 max-w-[85%] text-xs">${text}</div>`
      : `<div class="px-3 py-2 rounded-xl bg-slate-900/90 border border-cyan-500/25 text-slate-100 max-w-[88%] text-xs">${text}</div>`;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  function openPersonalMediaPlayer(filePath, title) {
    stopTTS();
    const bar = document.getElementById("cosmo-media-bar");
    const titleEl = document.getElementById("cosmo-media-title");
    const slot = document.getElementById("cosmo-media-player-slot");
    if (!bar || !slot) return;

    bar.classList.remove("hidden");
    titleEl.textContent = title || filePath.split(/[\\/]/).pop();
    const streamUrl = `/api/media/stream?path=${encodeURIComponent(filePath)}`;
    const isVideo = filePath.toLowerCase().endsWith(".mp4");

    const oldMedia = document.getElementById("cosmo-active-media");
    if (oldMedia) { oldMedia.pause(); oldMedia.src = ""; }
    
    slot.innerHTML = isVideo
      ? `<video id="cosmo-active-media" src="${streamUrl}" controls autoplay class="w-full rounded-lg max-h-44"></video>`
      : `<audio id="cosmo-active-media" src="${streamUrl}" controls autoplay class="w-full"></audio>`;

    const player = document.getElementById("cosmo-active-media");
    if (player) {
      player.onended = async () => {
        const res = await fetch("/api/media_finished", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ astronaut_id: getUserId() })
        });
        const data = await res.json();
        if (data.ai_text) {
          openDoraDrawer();
          appendDoraMessage(data.ai_text, false);
          speakText(data.ai_text);
        }
      };
    }
  }

  async function sendToDora(text, isVoice) {
    if (!text || !text.trim()) return;
    appendDoraMessage(text, true);
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        astronaut_id: getUserId(),
        message: text.trim(),
        is_voice_input: !!isVoice
      })
    });
    const data = await res.json();

    if (data.play_media_now && data.media_file && data.media_file.file_path) {
      openPersonalMediaPlayer(data.media_file.file_path, data.media_file.title);
    } else if (data.ai_text) {
      if (data.auto_open_chat) openDoraDrawer();
      appendDoraMessage(data.ai_text, false);
      if (data.speak_aloud) speakText(data.ai_text);
    }

    if (data.db_updates && data.db_updates.length > 0) {
      syncFullState();
    }
  }

  function bindDoraEvents() {
    const trigger = document.getElementById("dora-trigger-btn");
    const drawer = document.getElementById("dora-chat-drawer");
    const closeBtn = document.getElementById("dora-close-btn");
    const form = document.getElementById("dora-chat-form");
    const input = document.getElementById("dora-chat-input");
    const micBtn = document.getElementById("dora-mic-btn");
    const voiceToggle = document.getElementById("dora-auto-voice-toggle");
    const voiceState = document.getElementById("auto-voice-state");

    if (trigger && drawer) {
      trigger.onclick = (e) => {
        e.stopPropagation();
        drawer.classList.toggle("hidden");
        if (!drawer.classList.contains("hidden") && input) input.focus();
      };
    }
    if (closeBtn && drawer) {
      closeBtn.onclick = (e) => {
        e.stopPropagation();
        drawer.classList.add("hidden");
      };
    }
    if (voiceToggle && voiceState) {
      voiceState.textContent = autoVoiceEnabled ? "VOICE: ON" : "VOICE: OFF";
      voiceToggle.onclick = (e) => {
        e.stopPropagation();
        autoVoiceEnabled = !autoVoiceEnabled;
        localStorage.setItem("cosmo_auto_voice", String(autoVoiceEnabled));
        voiceState.textContent = autoVoiceEnabled ? "VOICE: ON" : "VOICE: OFF";
        if (!autoVoiceEnabled) stopTTS();
      };
    }
    if (form && input) {
      const clonedForm = form.cloneNode(true);
      form.parentNode.replaceChild(clonedForm, form);
      const newInput = document.getElementById("dora-chat-input");
      const newMic = document.getElementById("dora-mic-btn");
      clonedForm.onsubmit = (e) => {
        e.preventDefault();
        const val = newInput.value.trim();
        if (!val) return;
        newInput.value = "";
        sendToDora(val, false);
      };
      if (newMic) {
        newMic.onclick = () => toggleVoiceTyping(newMic, newInput);
      }
    } else if (micBtn && input) {
      micBtn.onclick = () => toggleVoiceTyping(micBtn, input);
    }

    document.querySelectorAll(".dora-suggestion").forEach((sBtn) => {
      sBtn.onclick = (e) => {
        e.stopPropagation();
        sendToDora(sBtn.textContent.trim(), false);
      };
    });

    const clearBtn = document.getElementById("dora-clear-btn");
    if (clearBtn) {
      clearBtn.onclick = () => {
        const box = document.getElementById("dora-messages-container");
        if (box) box.innerHTML = "";
      };
    }

    if (!window._cosmoDoraOutsideBound) {
      window._cosmoDoraOutsideBound = true;
      document.addEventListener("click", (e) => {
        const doraContainer = document.getElementById("dora-ai-container");
        const doraDrawer = document.getElementById("dora-chat-drawer");
        if (doraDrawer && !doraDrawer.classList.contains("hidden") && doraContainer && !doraContainer.contains(e.target)) {
          doraDrawer.classList.add("hidden");
        }
      });
    }
    
  }

  async function toggleVoiceTyping(micBtn, inputEl) {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      alert("Browser Speech Recognition not supported. Please use Chrome or Edge.");
      return;
    }

    if (!isRecordingVoice) {
      isRecordingVoice = true;
      micBtn.classList.add("text-rose-400", "animate-pulse");
      if (inputEl) inputEl.placeholder = "Listening... Tap mic again to send";

      let finalTranscript = "";
      recognitionObj = new SpeechRec();
      recognitionObj.lang = "en-US";
      recognitionObj.continuous = true;
      recognitionObj.interimResults = true;

      recognitionObj.onresult = (event) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript + " ";
          } else {
            interim += event.results[i][0].transcript;
          }
        }
        if (inputEl) inputEl.value = (finalTranscript + interim).trim();
      };

      recognitionObj.onend = () => {
        const textToSend = (inputEl?.value || finalTranscript).trim();
        if (inputEl) {
          inputEl.value = "";
          inputEl.placeholder = "Ask Dora or tap mic...";
        }
        micBtn.classList.remove("text-rose-400", "animate-pulse");
        isRecordingVoice = false;
        if (textToSend) sendToDora(textToSend, true);
      };

      recognitionObj.start();

      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        recordedChunks = [];
        mediaRecorderObj = new MediaRecorder(stream);
        mediaRecorderObj.ondataavailable = (ev) => {
          if (ev.data.size > 0) recordedChunks.push(ev.data);
        };
        mediaRecorderObj.onstop = async () => {
          const blob = new Blob(recordedChunks, { type: "audio/webm" });
          const fd = new FormData();
          fd.append("astronaut_id", getUserId());
          fd.append("category", "voice");
          fd.append("file", blob, `voice_${Date.now()}.webm`);
          fetch("/api/media/upload", { method: "POST", body: fd }).catch(() => {});
          stream.getTracks().forEach((t) => t.stop());
        };
        mediaRecorderObj.start();
      } catch (e) {}
    } else {
      isRecordingVoice = false;
      if (recognitionObj) recognitionObj.stop();
      if (mediaRecorderObj && mediaRecorderObj.state !== "inactive") mediaRecorderObj.stop();
    }
  }

  function showGlobalAlertToast(alertObj) {
    if (!alertObj) return;
    let toast = document.getElementById("cosmo-global-alert-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "cosmo-global-alert-toast";
      toast.className = "fixed top-20 right-6 z-50 w-96 rounded-xl border p-3.5 backdrop-blur-xl shadow-2xl cursor-pointer transition-all";
      document.body.appendChild(toast);
    }
    const isCrit = alertObj.severity === "CRITICAL";
    toast.className = `fixed top-20 right-6 z-50 w-96 rounded-xl border p-3.5 backdrop-blur-xl shadow-2xl cursor-pointer ${
      isCrit ? "bg-rose-950/90 border-rose-400 text-rose-100" : "bg-amber-950/90 border-amber-400 text-amber-100"
    }`;
    toast.innerHTML = `
      <div class="text-xs font-mono font-bold">${alertObj.severity}: ${alertObj.title}</div>
      <div class="text-[11px] mt-1 opacity-90">${alertObj.message}</div>
      <div class="text-[9px] font-mono mt-1.5 text-cyan-300">CLICK TO OPEN TARGET MODULE →</div>
    `;
    toast.onclick = () => {
      window.location.href = alertObj.target_route || "/security";
    };
    setTimeout(() => {
      if (toast) toast.remove();
    }, 7000);
  }

  function syncNotificationDrawers(notifications) {
    const unread = notifications.filter((n) => !n.is_read).length;
    const badge = document.getElementById("notif-badge") || document.getElementById("notif-ping") || document.getElementById("notif-ping-dot") || document.getElementById("bell-dot");
    if (badge) badge.style.display = unread > 0 ? "" : "none";

    const listContainers = [
      document.querySelector("#notification-drawer .overflow-y-auto"),
      document.querySelector("#notif-drawer .overflow-y-auto"),
      document.getElementById("notif-list")
    ].filter(Boolean);

    listContainers.forEach((container) => {
      container.innerHTML = notifications.slice(0, 8).map((n) => {
        const borderCls = n.severity === "CRITICAL" ? "border-rose-500/50 bg-rose-950/30" : (n.severity === "WARNING" ? "border-amber-500/40 bg-amber-950/25" : "border-cyan-500/25 bg-slate-900/50");
        return `
          <a href="${n.target_route}" class="block p-2.5 rounded-xl border ${borderCls} hover:border-cyan-400 transition-all mb-1.5">
            <div class="flex items-center justify-between text-[10px] font-mono">
              <span class="font-bold text-cyan-200">${n.title}</span>
              <span class="text-slate-400">${n.severity}</span>
            </div>
            <p class="text-[10px] text-slate-300 mt-1">${n.message}</p>
          </a>
        `;
      }).join("");
    });

    window.markAllRead = window.markAllNotificationsRead = async function () {
      await fetch("/api/notifications/read", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ astronaut_id: getUserId() })
      });
      syncFullState();
    };
  }

  let _waveAnimFrame = null;
  let _wavePhase = 0;
  let _liveHR = 71.4;
  let _liveSBP = 120;
  let _liveDBP = 77;
  let _liveHRV = 47.4;
  let _liveEctopic = 0;
  let _vitalsPollTimer = null;

  function sampleRealtimeWave(tSec, hr, sbp, dbp, ectopic) {
    const freq = hr / 60.0;
    const beatNum = Math.floor(tSec * freq);
    const phase = (tSec * freq) % 1.0;
    const tWaveAmp = ectopic >= 3 ? 0.08 : 0.28;
    const isPvc = ectopic > 0 && (beatNum % Math.max(2, Math.round(13 / Math.max(1, ectopic))) === 0);

    let ecg = 0;
    if (isPvc) {
      ecg = 1.45 * Math.exp(-Math.pow((phase - 0.24) / 0.045, 2))
          - 0.65 * Math.exp(-Math.pow((phase - 0.36) / 0.055, 2));
    } else {
      ecg = 0.15 * Math.exp(-Math.pow((phase - 0.18) / 0.035, 2))
          - 0.15 * Math.exp(-Math.pow((phase - 0.28) / 0.012, 2))
          + 1.15 * Math.exp(-Math.pow((phase - 0.30) / 0.015, 2))
          - 0.25 * Math.exp(-Math.pow((phase - 0.32) / 0.012, 2))
          + tWaveAmp * Math.exp(-Math.pow((phase - 0.52) / 0.055, 2));
    }

    const ppScale = Math.max(0.3, (sbp - dbp) / 42.0);
    const ppg = ppScale * (
      0.85 * Math.exp(-Math.pow((phase - 0.38) / 0.09, 2)) +
      0.38 * Math.exp(-Math.pow((phase - 0.56) / 0.11, 2))
    );

    return { ecg, ppg };
  }

  function updateStatisticsKPIs() {
    if (PATH !== "/statistics") return;
    const kpiValues = document.querySelectorAll("section.grid-cols-4 .text-2xl.font-orbitron");
    if (kpiValues.length >= 4) {
      kpiValues[0].textContent = _liveHR.toFixed(1);
      kpiValues[1].textContent = `${Math.round(_liveSBP)} / ${Math.round(_liveDBP)}`;
      kpiValues[2].textContent = _liveHRV.toFixed(1);
      kpiValues[3].textContent = String(_liveEctopic);
    }
  }

  function drawWave(canvasId, values, color) {
    const c = document.getElementById(canvasId);
    if (!c || !values.length) return;
    const ctx = c.getContext("2d");
    const w = c.clientWidth || 500;
    const h = c.clientHeight || 90;
    if (c.width !== w) c.width = w;
    if (c.height !== h) c.height = h;

    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.shadowColor = color;
    ctx.shadowBlur = 6;
    ctx.beginPath();

    const min = canvasId.includes("ecg") ? -0.7 : 0.0;
    const max = canvasId.includes("ecg") ? 1.5 : 1.3;
    const span = max - min;

    values.forEach((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - 10 - ((v - min) / span) * (h - 20);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  function startLiveWaveAnimation() {
    if (_waveAnimFrame) cancelAnimationFrame(_waveAnimFrame);
    function renderLoop() {
      if (PATH !== "/statistics") return;
      _wavePhase += 0.016;
      const ecgPts = [];
      const ppgPts = [];
      for (let i = 0; i < 160; i++) {
        const t = _wavePhase + i * 0.02;
        const s = sampleRealtimeWave(t, _liveHR, _liveSBP, _liveDBP, _liveEctopic);
        ecgPts.push(s.ecg);
        ppgPts.push(s.ppg);
      }
      drawWave("cosmo-ecg-canvas", ecgPts, "#00f0ff");
      drawWave("cosmo-ppg-canvas", ppgPts, "#10b981");
      _waveAnimFrame = requestAnimationFrame(renderLoop);
    }
    _waveAnimFrame = requestAnimationFrame(renderLoop);
  }

  function syncStatisticsWaveforms(aid) {
    if (PATH !== "/statistics") return;
    const leftTopPanel = document.querySelector(".col-span-8 > div:first-child");
    if (leftTopPanel && !document.getElementById("cosmo-ecg-canvas")) {
      leftTopPanel.innerHTML = `
        <div class="flex items-center justify-between border-b border-cyan-500/20 pb-2 mb-2">
          <span class="text-xs font-orbitron font-bold text-cyan-300">LIVE 3-LEAD ECG & OPTICAL PPG WAVEFORMS</span>
          <span class="text-[10px] font-mono text-emerald-400 animate-pulse">● STREAMING LIVE</span>
        </div>
        <div class="flex-1 flex flex-col gap-2 min-h-0">
          <div class="flex-1 bg-black/60 rounded-lg border border-cyan-500/20 p-2 relative">
            <span class="text-[9px] font-mono text-cyan-400 absolute top-1 left-2">3-LEAD ECG (mV)</span>
            <canvas id="cosmo-ecg-canvas" class="w-full h-full"></canvas>
          </div>
          <div class="flex-1 bg-black/60 rounded-lg border border-emerald-500/20 p-2 relative">
            <span class="text-[9px] font-mono text-emerald-400 absolute top-1 left-2">OPTICAL PPG PULSE</span>
            <canvas id="cosmo-ppg-canvas" class="w-full h-full"></canvas>
          </div>
        </div>
      `;
    }

    if (!_vitalsPollTimer) {
      const fetchLiveVitals = async () => {
        try {
          const r = await fetch(`/api/state/${aid}`);
          if (!r.ok) return;
          const st = await r.json();
          if (st.vitals) {
            _liveHR = Number(st.vitals.hr);
            _liveSBP = Number(st.vitals.sbp);
            _liveDBP = Number(st.vitals.dbp);
            _liveHRV = Number(st.vitals.hrv);
            _liveEctopic = Number(st.vitals.ectopic || 0);
            updateStatisticsKPIs();
          }
        } catch (e) {}
      };
      fetchLiveVitals();
      _vitalsPollTimer = setInterval(fetchLiveVitals, 2000);
    }

    startLiveWaveAnimation();
  }

  function wirePageActions(state) {
    const aid = state.profile.astronaut_id;

    if (PATH === "/devices") {
      window.triggerAction = async (actionName) => {
        if (actionName.includes("SLEEP")) {
          await fetch("/api/sleep/start", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ astronaut_id: aid }) });
        } else if (actionName.includes("WAKE")) {
          const r = await fetch("/api/sleep/wake", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ astronaut_id: aid }) });
          const d = await r.json();
          if (d.message) speakText(d.message);
        } else if (actionName.includes("RATION")) {
          await fetch("/api/ration/consume", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ astronaut_id: aid, item_id: 1, quantity: 1 }) });
        }
        syncFullState();
      };
    }

    if (PATH === "/rations") {
      const btnSleep = document.getElementById("btn-start-sleep");
      const btnWake = document.getElementById("btn-confirm-wake");
      const btnDeduct = document.getElementById("btn-deduct-log");
      if (btnSleep) {
        btnSleep.onclick = async () => {
          await fetch("/api/sleep/start", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ astronaut_id: aid }) });
          syncFullState();
        };
      }
      if (btnWake) {
        btnWake.onclick = async () => {
          const r = await fetch("/api/sleep/wake", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ astronaut_id: aid }) });
          const d = await r.json();
          if (d.message) speakText(d.message);
          syncFullState();
        };
      }
      if (btnDeduct) {
        btnDeduct.onclick = async () => {
          const item = document.getElementById("ration-select-item")?.value || "Rice";
          const qty = parseFloat(document.getElementById("stepper-val")?.textContent || "1.0");
          await fetch("/api/ration/consume", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ astronaut_id: aid, item_name: item, quantity: qty })
          });
          syncFullState();
        };
      }
      const invBody = document.getElementById("inventory-table-body");
      if (invBody && state.inventory && state.inventory.items) {
        invBody.innerHTML = state.inventory.items.map((it) => `
          <div class="grid grid-cols-12 px-3.5 py-2 items-center hover:bg-slate-900/40">
            <div class="col-span-4 text-white font-medium truncate">${it.item_name}</div>
            <div class="col-span-2 text-right text-cyan-200 font-semibold">${it.current_stock} ${it.unit}</div>
            <div class="col-span-2 text-right text-slate-400">${it.burn_rate}/day</div>
            <div class="col-span-2 text-right ${it.is_critical ? "text-rose-400" : "text-emerald-400"} font-semibold">${it.days_remaining} d</div>
            <div class="col-span-2 text-right">
              <span class="px-2 py-0.5 rounded text-[9px] ${it.is_critical ? "bg-rose-500/20 text-rose-300 border border-rose-400/40" : "bg-emerald-500/20 text-emerald-300 border border-emerald-400/40"}">${it.is_critical ? "REORDER" : "NOMINAL"}</span>
            </div>
          </div>
        `).join("");
      }
    }

    if (PATH === "/security") {
      window.triggerEmergencyAction = async (type) => {
        const r = await fetch("/api/emergency", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ astronaut_id: aid, action: type })
        });
        const d = await r.json();
        if (d.alert && d.alert.voice_announcement) {
          speakText(d.alert.voice_announcement);
          showGlobalAlertToast(d.alert);
        }
        syncFullState();
      };
    }

    if (PATH === "/profile") {
      const h1 = document.querySelector("h1");
      if (h1) h1.textContent = state.profile.name.toUpperCase();

      const numInputs = document.querySelectorAll('input[type="number"]');
      if (numInputs.length >= 3 && !window._cosmoBioBound) {
        numInputs[0].value = state.profile.height_cm;
        numInputs[1].value = state.profile.weight_kg;
        numInputs[2].value = state.profile.age;
        window._cosmoBioBound = true;
      }

      document.querySelectorAll("button").forEach((b) => {
        const t = b.textContent.toUpperCase();
        if (t.includes("SAVE BIOMETRICS")) {
          b.onclick = async () => {
            const fit = document.querySelector("select")?.value || "High";
            await fetch("/api/profile/biometrics", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                astronaut_id: aid,
                height_cm: parseFloat(numInputs[0].value),
                weight_kg: parseFloat(numInputs[1].value),
                age: parseInt(numInputs[2].value, 10),
                fitness_level: fit.includes("HIGH") || fit.includes("ELITE") ? "High" : "Moderate"
              })
            });
            syncFullState();
          };
        } else if (t.includes("UPDATE CREDENTIALS")) {
          b.onclick = async () => {
            const pwInputs = document.querySelectorAll('input[type="password"]');
            const newPw = pwInputs[1]?.value || "";
            if (newPw.length < 4) return;
            await fetch("/api/profile/password", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ astronaut_id: aid, new_password: newPw })
            });
            pwInputs[1].value = "";
            syncFullState();
          };
        } else if (t.includes("UPLOAD TO VAULT")) {
          b.onclick = () => {
            const picker = document.createElement("input");
            picker.type = "file";
            picker.accept = ".mp3,.wav,.mp4,.webm";
            picker.onchange = async () => {
              if (!picker.files[0]) return;
              const fd = new FormData();
              fd.append("astronaut_id", aid);
              fd.append("category", "auto");
              fd.append("file", picker.files[0]);
              await fetch("/api/media/upload", { method: "POST", body: fd });
              syncFullState();
            };
            picker.click();
          };
        }
      });

      const subPanels = document.querySelectorAll(".space-y-1\\.5");
      if (subPanels.length >= 2 && state.user_media) {
        const voiceFiles = state.user_media.voice || [];
        const mediaFiles = [...(state.user_media.music || []), ...(state.user_media.video || [])];

        subPanels[0].innerHTML = voiceFiles.length
          ? voiceFiles.slice(0, 5).map((f) => `
              <div class="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-slate-900/70 border border-slate-800">
                <button onclick="window._cosmoPlay('${f.path.replace(/\\/g, "\\\\")}','${f.name}')" class="text-xs font-mono text-cyan-300 truncate">▶ ${f.name}</button>
                <button onclick="window._cosmoDel('${f.path.replace(/\\/g, "\\\\")}')" class="text-rose-400 text-xs">🗑</button>
              </div>`).join("")
          : '<div class="text-[10px] font-mono text-slate-500 p-2">No voice recordings yet.</div>';

        subPanels[1].innerHTML = mediaFiles.length
          ? mediaFiles.slice(0, 6).map((f) => `
              <div class="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-slate-900/70 border border-slate-800">
                <button onclick="window._cosmoPlay('${f.path.replace(/\\/g, "\\\\")}','${f.name}')" class="text-xs font-mono text-indigo-300 truncate">▶ ${f.name}</button>
                <button onclick="window._cosmoDel('${f.path.replace(/\\/g, "\\\\")}')" class="text-rose-400 text-xs">🗑</button>
              </div>`).join("")
          : '<div class="text-[10px] font-mono text-slate-500 p-2">Upload personal .mp3 or .mp4 files above.</div>';
      }

      window._cosmoPlay = (path, name) => openPersonalMediaPlayer(path, name);
      window._cosmoDel = async (path) => {
        await fetch("/api/media/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ astronaut_id: aid, file_path: path })
        });
        syncFullState();
      };
    }
  }

  async function syncFullState() {
    const aid = getUserId();
    if (!aid) return;
    try {
      const res = await fetch(`/api/state/${aid}`);
      if (!res.ok) return;
      const state = await res.json();

      syncNotificationDrawers(state.notifications || []);
      wirePageActions(state);
      syncStatisticsWaveforms(aid);

      const chatBox = document.getElementById("dora-messages-container");
      if (chatBox && !chatBox.dataset.hydrated) {
        chatBox.dataset.hydrated = "true";
        chatBox.innerHTML = "";
        (state.chat_history || []).forEach((m) => {
          appendDoraMessage(m.message_text, m.sender === "User");
        });
      }
    } catch (e) {}
  }

  window.cosmoTriggerMoodCheckin = async function (moodLabel) {
    const aid = getUserId();
    if (!aid) return;
    try {
      const res = await fetch("/api/mood_checkin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ astronaut_id: aid, mood_label: moodLabel })
      });
      const data = await res.json();
      if (data.ai_text) {
        openDoraDrawer();
        appendDoraMessage(data.ai_text, false);
        if (data.speak_aloud) speakText(data.ai_text);
      }
    } catch (e) {}
  };
  
  window.addEventListener("DOMContentLoaded", () => {
    if (IS_LOGIN) {
      wireLoginPage();
    } else {
      rewireAllNavigationLinks();
      ensureFloatingDoraAndMediaBar();
      syncFullState();

      if (typeof window.toggleNotifDrawer !== "function") {
        window.toggleNotifDrawer = () => {
          const d = document.getElementById("notif-drawer") || document.getElementById("notification-drawer");
          if (d) d.classList.toggle("hidden");
        };
      }

      ["hud-back-to-top", "back-to-top-hud"].forEach((id) => {
        const b = document.getElementById(id);
        if (b) { b.style.bottom = "8.5rem"; }
      });
      document.querySelectorAll('button[aria-label="Back to top"]').forEach((b) => {
        b.style.bottom = "8.5rem";
      });
    }
  });
})();
