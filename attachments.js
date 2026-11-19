(() => {
  "use strict";
  const button = document.getElementById("attach");
  if (!button || window.__HAMASA_ATTACHMENTS_READY__) return;
  window.__HAMASA_ATTACHMENTS_READY__ = true;

  const MAX_FILES = 8;
  const MAX_BYTES = 64 * 1024 * 1024;
  const MAX_AUDIO_BYTES = 11 * 1024 * 1024;
  const allowedExtensions = new Set([
    "jpg","jpeg","png","webp","pdf","docx","xlsx","pptx","mp3","wav","m4a","aac","ogg","webm",
    "txt","md","csv","json","xml","log","py","js","ts","jsx","tsx",
    "html","htm","css","scss","yaml","yml","toml","ini","cfg","conf",
    "sql","sh","bash","java","c","h","cpp","hpp","cs","go","rs",
    "php","rb","swift","kt","dart","vue","svelte","ipynb"
  ]);
  const mimeByExtension = {
    jpg:"image/jpeg", jpeg:"image/jpeg", png:"image/png", webp:"image/webp",
    pdf:"application/pdf",
    docx:"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    xlsx:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    pptx:"application/vnd.openxmlformats-officedocument.presentationml.presentation",
    mp3:"audio/mpeg", wav:"audio/wav", m4a:"audio/mp4", aac:"audio/aac", ogg:"audio/ogg", webm:"audio/webm",
    txt:"text/plain", md:"text/markdown", csv:"text/csv", json:"application/json",
    xml:"application/xml", html:"text/html", htm:"text/html", css:"text/css"
  };
  const selected = [];
  const picker = document.createElement("input");
  picker.type = "file";
  picker.multiple = true;
  picker.accept = "image/jpeg,image/png,image/webp,.pdf,.docx,.xlsx,.pptx,.mp3,.wav,.m4a,.aac,.ogg,.webm,.txt,.md,.csv,.json,.xml,.log,.py,.js,.ts,.jsx,.tsx,.html,.htm,.css,.scss,.yaml,.yml,.toml,.ini,.cfg,.conf,.sql,.sh,.bash,.java,.c,.h,.cpp,.hpp,.cs,.go,.rs,.php,.rb,.swift,.kt,.dart,.vue,.svelte,.ipynb";
  picker.hidden = true;
  document.body.appendChild(picker);

  const tray = document.createElement("div");
  tray.id = "hamasaAttachmentTray";
  tray.style.cssText = "display:none;max-width:760px;margin:0 auto 8px;padding:0 8px;flex-wrap:wrap;gap:7px";
  const composer = document.querySelector(".comp");
  if (composer) composer.insertBefore(tray, composer.firstChild);

  function render() {
    tray.replaceChildren();
    tray.style.display = selected.length ? "flex" : "none";
    selected.forEach((file, index) => {
      const chip = document.createElement("span");
      chip.style.cssText = "display:inline-flex;align-items:center;gap:7px;max-width:100%;padding:7px 10px;border:1px solid var(--line);border-radius:12px;background:var(--glass);font-size:12px;color:var(--fg)";
      const name = document.createElement("span");
      name.textContent = file.name;
      name.style.cssText = "overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:190px";
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "×";
      remove.setAttribute("aria-label", "Remove " + file.name);
      remove.style.cssText = "font-size:18px;color:var(--mut);padding:0 2px";
      remove.addEventListener("click", () => { selected.splice(index, 1); render(); });
      chip.append(name, remove);
      tray.append(chip);
    });
  }

  function isAudioFile(file) {
    const ext = file.name.includes(".") ? file.name.split(".").pop().toLowerCase() : "";
    return ["mp3","wav","m4a","aac","ogg","webm"].includes(ext) || String(file.type || "").startsWith("audio/");
  }

  function readFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("تعذرت قراءة الملف: " + file.name));
      reader.onload = () => {
        const value = String(reader.result || "");
        const comma = value.indexOf(",");
        if (comma < 0) return reject(new Error("صيغة الملف غير صالحة: " + file.name));
        const ext = file.name.split(".").pop().toLowerCase();
        resolve({
          name: file.name,
          mime_type: file.type || mimeByExtension[ext] || "application/octet-stream",
          data: value.slice(comma + 1)
        });
      };
      reader.readAsDataURL(file);
    });
  }

  button.addEventListener("click", event => {
    event.preventDefault();
    picker.click();
  });

  picker.addEventListener("change", () => {
    const files = Array.from(picker.files || []);
    let total = selected.reduce((sum, item) => sum + item.size, 0);
    for (const file of files) {
      const ext = file.name.includes(".") ? file.name.split(".").pop().toLowerCase() : "";
      if (!allowedExtensions.has(ext)) {
        window.alert("نوع الملف غير مدعوم حالياً: " + file.name);
        continue;
      }
      if (isAudioFile(file) && file.size > MAX_AUDIO_BYTES) {
        window.alert("حجم الملف الصوتي كبير. الحد الأقصى 11 ميجابايت لكل تسجيل.");
        continue;
      }
      if (file.size > MAX_BYTES || total + file.size > MAX_BYTES) {
        window.alert("إجمالي حجم المرفقات لا يمكن أن يتجاوز 64 ميجابايت.");
        continue;
      }
      if (selected.length >= MAX_FILES) {
        window.alert("تقدر ترفق 8 ملفات كحد أقصى في الرسالة الواحدة.");
        break;
      }
      if (selected.some(item => item.name === file.name && item.size === file.size)) continue;
      selected.push(file);
      total += file.size;
    }
    picker.value = "";
    render();
  });

  window.HAMASA_ATTACHMENTS = {
    async addToPayload(payload) {
      if (!selected.length) return payload;
      const audioFiles = selected.filter(isAudioFile);
      const documentFiles = selected.filter(file => !isAudioFile(file));
      const nextPayload = { ...payload };
      if (documentFiles.length) {
        nextPayload.attachments = await Promise.all(documentFiles.map(readFile));
      }
      if (audioFiles.length) {
        const apiBase = String(window.HAMASA_CONFIG?.API_URL || "https://hamasa-api-production.up.railway.app").replace(/\\/+$/, "");
        const messages = Array.isArray(payload.messages) ? payload.messages.map(message => ({ ...message })) : [];
        const last = messages[messages.length - 1];
        if (!last || last.role !== "user" || typeof last.content !== "string") {
          throw new Error("ابعت رسالة مع الملف الصوتي عشان حماصة يعرف المطلوب.");
        }
        const transcripts = [];
        for (const file of audioFiles) {
          const encoded = await readFile(file);
          const response = await fetch(apiBase + "/api/transcribe", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ audio: encoded.data, mime_type: encoded.mime_type })
          });
          const result = await response.json().catch(() => ({}));
          if (!response.ok) throw new Error(result.detail || "تعذر تحويل الملف الصوتي إلى نص.");
          const transcript = String(result.transcript || "").trim();
          transcripts.push(transcript
            ? "[تفريغ الملف الصوتي " + file.name + "]: " + transcript
            : "[لم يتم التعرف على كلام واضح في الملف الصوتي " + file.name + "]");
        }
        last.content += "\\n\\n" + transcripts.join("\\n\\n");
        nextPayload.messages = messages;
      }
      return nextPayload;
    },
    clear() {
      selected.splice(0, selected.length);
      render();
    },
    count() { return selected.length; }
  };
})();
