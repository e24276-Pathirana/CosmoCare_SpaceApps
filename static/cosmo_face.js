(async function () {
  const PATH = window.location.pathname;
  if (PATH === "/login" || PATH === "/") return;

  const LABELS = ["neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt"];
  const UPSET_LABELS = ["sadness", "anger", "fear"];
  const MP_WASM = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";
  const MP_MODEL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite";
  const LOCAL_ONNX = "/static/models/emotion-ferplus-8.onnx";
  const HF_ONNX = "https://huggingface.co/onnxmodelzoo/emotion-ferplus-8/resolve/main/emotion-ferplus-8.onnx";

  const SAD_STREAK_SECONDS = 6;       // තත්පර 6ක් sad වෙලා හිටියොත් DORA අහනවා
  const COOLDOWN_MS = 180 * 1000;     // විනාඩි 3ක cooldown (දිගටම spam නොවෙන්න)
  const CONFIDENCE_THRESHOLD = 0.55;

  let detector = null;
  let session = null;
  let stream = null;
  let running = false;
  let busy = false;
  let lastExprAt = 0;
  let upsetStreak = 0;
  let lastTriggerAt = 0;

  // Stitch UI එකේ button එක නැති වුණත් fallback විදිහට UI එක හදනවා
  function ensureCameraWidgetUI() {
    if (!document.getElementById("cosmo-cam-trigger")) {
      const wrap = document.createElement("div");
      wrap.id = "cosmo-cam-wrapper";
      wrap.className = "fixed left-6 bottom-14 z-40 flex flex-col items-start select-none";
      wrap.innerHTML = `
        <div id="cosmo-cam-panel" class="hidden mb-3 w-72 rounded-2xl border border-cyan-400/40 bg-slate-950/95 backdrop-blur-2xl p-3 shadow-[0_0_28px_rgba(0,240,255,0.22)]">
          <div class="flex items-center justify-between pb-2 border-b border-cyan-500/20">
            <span class="text-[10px] font-mono font-bold tracking-widest text-cyan-300">OPTICAL MOOD MONITOR</span>
            <button id="cosmo-cam-close" type="button" class="text-slate-400 hover:text-white text-xs px-1 cursor-pointer">✕</button>
          </div>
          <div class="relative mt-2 rounded-xl overflow-hidden bg-black aspect-[16/10] border border-cyan-500/25">
            <video id="cosmo-cam-video" muted playsinline class="w-full h-full object-cover" style="transform: scaleX(-1);"></video>
            <div id="cosmo-cam-status-overlay" class="absolute inset-0 flex items-center justify-center bg-slate-950/80 text-[10px] font-mono text-cyan-300 text-center px-3">
              Initializing optical sensor...
            </div>
          </div>
          <div class="mt-2.5 flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-slate-900/90 border border-white/10">
            <span id="cosmo-mood-badge" class="text-[11px] font-mono font-bold text-cyan-300">● SCANNING...</span>
            <span id="cosmo-mood-conf" class="text-[10px] font-mono text-slate-400">--%</span>
          </div>
          <p class="mt-1.5 text-[9px] font-mono text-slate-500 text-center">On-device processing • Video never uploaded</p>
        </div>

        <button id="cosmo-cam-trigger" type="button" title="View Face & Mood Status"
          class="relative w-12 h-12 rounded-full border border-cyan-400/60 bg-slate-950/90 backdrop-blur-xl flex items-center justify-center text-cyan-300 hover:text-white hover:border-cyan-300 hover:scale-105 transition-all shadow-[0_0_18px_rgba(6,182,212,0.35)] cursor-pointer">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"
              d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/>
          </svg>
          <span id="cosmo-cam-dot" class="absolute top-0.5 right-0.5 w-2.5 h-2.5 rounded-full bg-amber-400 ring-2 ring-slate-950"></span>
        </button>
      `;
      document.body.appendChild(wrap);
    }

    if (!document.getElementById("cosmo-cam-canvas")) {
      const c = document.createElement("canvas");
      c.id = "cosmo-cam-canvas";
      c.width = 64;
      c.height = 64;
      c.hidden = true;
      document.body.appendChild(c);
    }

    const trigger = document.getElementById("cosmo-cam-trigger");
    const panel = document.getElementById("cosmo-cam-panel");
    const closeBtn = document.getElementById("cosmo-cam-close");

    if (trigger && panel) {
      trigger.onclick = () => {
        panel.classList.toggle("hidden");
        if (!running) startBackgroundCamera();
      };
    }
    if (closeBtn && panel) {
      closeBtn.onclick = () => panel.classList.add("hidden");
    }
  }

  function setStatusUI(label, score, overlayText = "") {
    const badge = document.getElementById("cosmo-mood-badge");
    const conf = document.getElementById("cosmo-mood-conf");
    const overlay = document.getElementById("cosmo-cam-status-overlay");
    const dot = document.getElementById("cosmo-cam-dot");

    if (overlay) {
      if (overlayText) {
        overlay.textContent = overlayText;
        overlay.classList.remove("hidden");
      } else {
        overlay.classList.add("hidden");
      }
    }

    if (dot && running) {
      dot.className = "absolute top-0.5 right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 ring-2 ring-slate-950 shadow-[0_0_6px_#10b981]";
    }

    if (!badge || !label) return;
    const prettyMap = {
      happiness: { text: "● STATUS: HAPPY", cls: "text-emerald-400" },
      sadness: { text: "● STATUS: SAD", cls: "text-rose-400" },
      anger: { text: "● STATUS: UPSET", cls: "text-amber-400" },
      fear: { text: "● STATUS: STRESSED", cls: "text-amber-300" },
      surprise: { text: "● STATUS: SURPRISED", cls: "text-sky-300" },
      neutral: { text: "● STATUS: NEUTRAL", cls: "text-cyan-300" },
      disgust: { text: "● STATUS: DISCOMFORT", cls: "text-amber-300" },
      contempt: { text: "● STATUS: TENSE", cls: "text-amber-300" }
    };
    const info = prettyMap[label] || { text: `● STATUS: ${label.toUpperCase()}`, cls: "text-cyan-300" };
    badge.className = `text-[11px] font-mono font-bold ${info.cls}`;
    badge.textContent = info.text;
    if (conf) conf.textContent = `${Math.round(score * 100)}%`;
  }

  async function loadModels() {
    if (!window.ort) {
      await new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/ort.min.js";
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
      });
    }

    if (!detector) {
      const vision = await import("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs");
      const fs = await vision.FilesetResolver.forVisionTasks(MP_WASM);
      detector = await vision.FaceDetector.createFromOptions(fs, {
        baseOptions: { modelAssetPath: MP_MODEL, delegate: "CPU" },
        runningMode: "VIDEO",
        minDetectionConfidence: 0.6
      });
    }

    if (!session) {
      window.ort.env.wasm.wasmPaths = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/";
      window.ort.env.wasm.numThreads = 1;
      for (const url of [LOCAL_ONNX, HF_ONNX]) {
        try {
          session = await window.ort.InferenceSession.create(url, { executionProviders: ["wasm"] });
          break;
        } catch (e) {}
      }
      if (!session) throw new Error("Expression ONNX model failed to load.");
    }
  }

  async function classifyFace(video, box) {
    const canvas = document.getElementById("cosmo-cam-canvas");
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const pad = 0.1;
    const sx = Math.max(0, box.originX - box.width * pad);
    const sy = Math.max(0, box.originY - box.height * pad);
    const sw = Math.min(video.videoWidth - sx, box.width * (1 + 2 * pad));
    const sh = Math.min(video.videoHeight - sy, box.height * (1 + 2 * pad));

    ctx.drawImage(video, sx, sy, sw, sh, 0, 0, 64, 64);
    const d = ctx.getImageData(0, 0, 64, 64).data;
    const input = new Float32Array(4096);
    for (let i = 0; i < 4096; i++) {
      input[i] = 0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2];
    }
    const out = await session.run({ [session.inputNames[0]]: new window.ort.Tensor("float32", input, [1, 1, 64, 64]) });
    const logits = Array.from(out[session.outputNames[0]].data);
    const mx = Math.max(...logits);
    const ex = logits.map((v) => Math.exp(v - mx));
    const sum = ex.reduce((a, b) => a + b, 0);
    const probs = ex.map((v) => v / sum);
    const best = probs.indexOf(Math.max(...probs));
    return { label: LABELS[best], score: probs[best] };
  }

  async function triggerDoraMoodCheckin(detectedLabel) {
    if (typeof window.cosmoTriggerMoodCheckin === "function") {
      window.cosmoTriggerMoodCheckin(detectedLabel);
    }
  }

  async function detectionLoop() {
    if (!running) return;
    const video = document.getElementById("cosmo-cam-video");
    const now = performance.now();

    try {
      if (video && video.readyState >= 2 && detector && session) {
        const det = detector.detectForVideo(video, now).detections[0];
        if (det && !busy && now - lastExprAt >= 500) {
          busy = true;
          const dt = lastExprAt ? (now - lastExprAt) / 1000 : 0.5;
          lastExprAt = now;
          try {
            const expr = await classifyFace(video, det.boundingBox);
            setStatusUI(expr.label, expr.score, "");

            const isUpset = UPSET_LABELS.includes(expr.label) && expr.score >= CONFIDENCE_THRESHOLD;
            if (isUpset) {
              upsetStreak += dt;
            } else {
              upsetStreak = 0;
            }

            const cooldownPassed = lastTriggerAt === 0 || (Date.now() - lastTriggerAt >= COOLDOWN_MS);
            if (upsetStreak >= SAD_STREAK_SECONDS && cooldownPassed) {
              lastTriggerAt = Date.now();
              upsetStreak = 0;
              triggerDoraMoodCheckin(expr.label);
            }
          } finally {
            busy = false;
          }
        } else if (!det) {
          upsetStreak = 0;
        }
      }
    } catch (e) {}

    setTimeout(detectionLoop, 180);
  }

  async function startBackgroundCamera() {
    if (running || busy) return;
    const video = document.getElementById("cosmo-cam-video");
    setStatusUI(null, 0, "Requesting camera access...");
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 480, height: 360, facingMode: "user" },
        audio: false
      });
      if (video) {
        video.srcObject = stream;
        await video.play();
      }
      setStatusUI(null, 0, "Loading expression models...");
      await loadModels();
      running = true;
      lastExprAt = performance.now();
      setStatusUI("neutral", 1.0, "");
      detectionLoop();
    } catch (err) {
      setStatusUI(null, 0, "Camera blocked. Allow camera permission & click icon.");
    }
  }

  window.addEventListener("DOMContentLoaded", () => {
    ensureCameraWidgetUI();
    // Homepage එකට enter වුණ ගමන් background එකෙන් camera access ගන්නවා
    startBackgroundCamera();
  });
})();