(() => {
  "use strict";
  const button = document.getElementById("attach");
  if (!button || window.__HAMASA_ATTACHMENTS_READY__) return;
  window.__HAMASA_ATTACHMENTS_READY__ = true;

  const MAX_FILES = 8;
  const MAX_BYTES = 64 * 1024 * 1024;
  const allowedExtensions = new Set([
    "jpg","jpeg","png","webp","pdf","docx","xlsx","pptx",
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
    txt:"text/plain", md:"text/markdown", csv:"text/csv", json:"application/json",
    xml:"application/xml", html:"text/html", htm:"text/html", css:"text/css"
  };
  const selected = [];
  const picker = document.createElement("input");
  picker.type = "file";
  picker.multiple = true;
  picker.accept = "image/jpeg,image/png,image/webp,.pdf,.docx,.xlsx,.pptx,.txt,.md,.csv,.json,.xml,.log,.py,.js,.ts,.jsx,.tsx,.html,.htm,.css,.scss,.yaml,.yml,.toml,.ini,.cfg,.conf,.sql,.sh,.bash,.java,.c,.h,.cpp,.hpp,.cs,.go,.rs,.php,.rb,.swift,.kt,.dart,.vue,.svelte,.ipynb";
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
      return { ...payload, attachments: await Promise.all(selected.map(readFile)) };
    },
    clear() {
      selected.splice(0, selected.length);
      render();
    },
    count() { return selected.length; }
  };
})();
