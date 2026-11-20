(() => {
  "use strict";
  if (window.__HAMASA_VOICE_MODE__) return;
  window.__HAMASA_VOICE_MODE__ = true;
  const $ = (id) => document.getElementById(id);
  const openButton = $("voice-mode-open");
  if (!openButton) return;
  const apiBase = String(window.HAMASA_CONFIG?.API_URL || "https://hamasa-api-production.up.railway.app").replace(/\/+$/, "");
  let recorder = null, stream = null, chunks = [], busy = false, lastReply = "", speechButton = null;
  const dialog = document.createElement("section");
  dialog.id = "hamasaVoiceDialog";
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-labelledby", "hvTitle");
  dialog.innerHTML = `
    <div class="hv-panel">
      <div class="hv-topbar"><h2 id="hvTitle">محادثة حماصة الصوتية</h2><button class="hv-close" id="hvClose" type="button" aria-label="إغلاق">×</button></div>
      <div class="hv-stage" aria-hidden="true">
        <div class="hv-aura"></div><div class="hv-orbit"></div>
        <div class="hv-robot" id="hvRobot"><div class="hv-face"><div class="hv-eyes"><i></i><i></i></div><div class="hv-mouth"></div></div></div>
      </div>
      <div class="hv-status" id="hvStatus" role="status" aria-live="polite">اضغط على الميكروفون وابدأ كلامك</div>
      <div class="hv-transcript" id="hvTranscript">هنا هيظهر كلامك ورد حماصة.</div>
      <div class="hv-controls">
        <button class="hv-btn primary" id="hvMic" type="button">🎙 ابدأ الكلام</button>
        <button class="hv-btn" id="hvListen" type="button" disabled>▶ اسمع رد حماصة</button>
      </div>
      <p class="hv-note">المحادثة بتستخدم الميكروفون بعد إذنك. اضغط مرة للتسجيل ومرة للإيقاف والإرسال. تشغيل الرد الصوتي بيبدأ لما تضغط «اسمع رد حماصة».</p>
    </div>`;
  document.body.append(dialog);
  const status = $("hvStatus"), transcript = $("hvTranscript"), robot = $("hvRobot"), mic = $("hvMic"), listen = $("hvListen");
  const setStatus = (message, mode = "") => { status.textContent = message; robot.className = "hv-robot " + mode; };
  const stopTracks = () => { if (stream) stream.getTracks().forEach(track => track.stop()); stream = null; };
  const close = () => {
    if (recorder && recorder.state === "recording") { recorder.onstop = null; recorder.stop(); }
    stopTracks(); dialog.classList.remove("open"); setStatus("اضغط على الميكروفون وابدأ كلامك");
  };
  const chooseMime = () => {
    if (!window.MediaRecorder) return "";
    return ["audio/mp4","audio/webm;codecs=opus","audio/webm","audio/ogg;codecs=opus"].find(type => MediaRecorder.isTypeSupported?.(type)) || "";
  };
  async function transcribe(blob) {
    if (!blob || blob.size < 1200) throw new Error("التسجيل قصير جدًا. جرّب تتكلم لمدة ثانية على الأقل.");
    if (blob.size > 11 * 1024 * 1024) throw new Error("التسجيل كبير. جرّب رسالة أقصر.");
    const raw = (blob.type || "audio/webm").split(";")[0].toLowerCase();
    const mime = raw === "audio/x-m4a" ? "audio/mp4" : raw;
    const dataUrl = await new Promise((resolve,reject) => {
      const reader = new FileReader(); reader.onerror = () => reject(new Error("تعذرت قراءة التسجيل."));
      reader.onload = () => resolve(String(reader.result || "")); reader.readAsDataURL(blob);
    });
    const comma = dataUrl.indexOf(",");
    const response = await fetch(apiBase + "/api/transcribe", {
      method:"POST", credentials:"include",
      headers:{"Content-Type":"application/json","X-Hamasa-Request":"1"},
      body:JSON.stringify({audio:dataUrl.slice(comma+1),mime_type:mime}),
      signal:AbortSignal.timeout ? AbortSignal.timeout(120000) : undefined
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "خدمة تحويل الصوت لنص غير متاحة حاليًا.");
    const text = String(data.transcript || "").trim();
    if (!text) throw new Error("مش سامع كلام واضح. جرّب تاني.");
    return text;
  }
  async function beginRecording() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error("المتصفح لا يدعم التسجيل الصوتي. افتح الموقع في Safari أو Chrome مع HTTPS.");
    stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
    const mime = chooseMime();
    recorder = mime ? new MediaRecorder(stream,{mimeType:mime}) : new MediaRecorder(stream);
    chunks = [];
    recorder.ondataavailable = event => { if(event.data?.size) chunks.push(event.data); };
    recorder.onstop = async () => {
      const blob = new Blob(chunks,{type:recorder?.mimeType || mime || "audio/webm"});
      stopTracks(); recorder = null; mic.disabled = true;
      try {
        setStatus("بحوّل كلامك لنص…","thinking");
        const text = await transcribe(blob);
        transcript.textContent = "أنت: " + text + String.fromCharCode(10,10) + "حماصة: " + lastReply;
        setStatus("حماصة بتفكر في ردك…","thinking");
        const bridge = window.HAMASA_VOICE_BRIDGE;
        if (!bridge?.send) throw new Error("واجهة المحادثة غير جاهزة. حدّث الصفحة وجرب تاني.");
        const reply = await bridge.send(text);
        if (!reply) throw new Error("ماوصلنيش رد من حماصة. جرّب تبعت كلامك تاني.");
        lastReply = String(reply);
        transcript.textContent = "أنت: " + text + String.fromCharCode(10,10) + "حماصة: " + lastReply;
        listen.disabled = false;
        setStatus("حماصة ردّت عليك. اضغط لسماع الرد.","talking");
      } catch(error) { setStatus(error.message || "حصل خطأ أثناء المحادثة."); }
      finally { mic.disabled = false; mic.textContent = "🎙 ابدأ الكلام"; busy = false; }
    };
    recorder.start(250);
    mic.textContent = "■ إيقاف وإرسال";
    setStatus("سامعك… اتكلم براحتك","listening");
    transcript.textContent = "جاري التسجيل…";
  }
  openButton.addEventListener("click",() => {
    dialog.classList.add("open");
    setStatus("اضغط على الميكروفون وابدأ كلامك");
    $("hvMic").focus();
  });
  $("hvClose").addEventListener("click",close);
  dialog.addEventListener("click",event => { if(event.target === dialog) close(); });
  mic.addEventListener("click",async() => {
    if (busy) return;
    if (recorder?.state === "recording") { busy = true; mic.disabled = true; setStatus("بجهّز التسجيل…","thinking"); recorder.stop(); return; }
    try { busy = true; listen.disabled = true; await beginRecording(); busy = false; }
    catch(error) { stopTracks(); recorder = null; busy = false; mic.disabled = false; setStatus(error.name === "NotAllowedError" ? "اسمح للمتصفح باستخدام الميكروفون من إعدادات الموقع." : (error.message || "تعذر بدء التسجيل.")); }
  });
  listen.addEventListener("click",async() => {
    if (!lastReply) return;
    const bridge = window.HAMASA_VOICE_BRIDGE;
    if (!bridge?.speak) { setStatus("تشغيل الصوت غير جاهز."); return; }
    if (!speechButton) {
      speechButton = document.createElement("button");
      speechButton.type = "button"; speechButton.className = "msg-tool";
      speechButton.style.position = "fixed"; speechButton.style.left = "-9999px";
      document.body.append(speechButton);
    }
    setStatus("بجهّز صوت حماصة…","talking");
    await bridge.speak(lastReply,speechButton);
    setStatus("لو الصوت ما اشتغلش، اضغط اسمع الرد مرة تانية.","talking");
  });
  document.addEventListener("keydown",event => { if(event.key === "Escape" && dialog.classList.contains("open")) close(); });
  window.addEventListener("pagehide",stopTracks);
})();