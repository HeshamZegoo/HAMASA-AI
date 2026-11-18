(() => {
  "use strict";
  const button = document.getElementById("attach");
  if (!button || window.__HAMASA_ATTACHMENTS_READY__) return;
  window.__HAMASA_ATTACHMENTS_READY__ = true;

  const allowed = new Set([
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain", "text/markdown", "text/csv", "application/json",
    "application/xml"
  ]);
  const maxBytes = 64 * 1024 * 1024;
  const selected = [];
  const picker = document.createElement("input");
  picker.type = "file";
  picker.multiple = true;
  picker.accept = "image/*,.pdf,.docx,.txt,.md,.csv,.json,.xml";
  picker.hidden = true;
  document.body.appendChild(picker);

  const tray = document.createElement("div");
  tray.id = "hamasaAttachmentTray";
  tray.style.cssText = "display:none;max-width:760px;margin:0 auto 8px;padding:0 8px;display:flex;flex-wrap:wrap;gap:7px";
  const composer = document.querySelector(".comp");
  composer.insertBefore(tray, composer.firstChild);

  function render() {
    tray.innerHTML = "";
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

  function readFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("تعذرت قراءة الملف: " + file.name));
      reader.onload = () => {
        const value = String(reader.result || "");
        const comma = value.indexOf(",");
        if (comma < 0) return reject(new Error("صيغة الملف غير صالحة."));
        resolve({ name: file.name, mime_type: file.type || "application/octet-stream", data: value.slice(comma + 1) });
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
    for (const file of files) {
      const mime = file.type || "";
      const ext = file.name.split(".").pop().toLowerCase();
      const extensionAllowed = ["txt","md","csv","json","xml","pdf","docx"].includes(ext);
      if (!(allowed.has(mime) || extensionAllowed)) {
        window.alert("نوع الملف غير مدعوم: " + file.name);
        continue;
      }
      if (file.size > maxBytes) {
        window.alert("حجم الملف أكبر من الحد التقني (64 ميجابايت): " + file.name);
        continue;
      }
      if (selected.length >= 5) {
        window.alert("مسموح بإرفاق 5 ملفات كحد أقصى.");
        break;
      }
      if (!selected.some(item => item.file === file || item.file.name === file.name && item.file.size === file.size)) selected.push({ file });
    }
    picker.value = "";
    render();
  });

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input && input.url;
    if (!url || !url.endsWith("/api/chat") || !selected.length || !init.body) {
      return originalFetch(input, init);
    }
    let payload;
    try { payload = JSON.parse(init.body); }
    catch { return originalFetch(input, init); }
    payload.attachments = await Promise.all(selected.map(item => readFile(item.file)));
    const response = await originalFetch(input, { ...init, body: JSON.stringify(payload) });
    if (response.ok) {
      selected.splice(0, selected.length);
      render();
    }
    return response;
  };
})();
