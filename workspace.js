(() => {
  "use strict";
  const dialog=document.getElementById("workspaceDlg"),openButton=document.getElementById("workspaceOpen");
  if(!dialog||!openButton||window.__HAMASA_WORKSPACE_READY__)return;
  window.__HAMASA_WORKSPACE_READY__=true;
  const $=id=>document.getElementById(id);
  const editor=$("workspaceEditor"),tabs=$("workspaceTabs"),output=$("workspaceOutput"),preview=$("workspacePreview");
  const language=$("workspaceLanguage"),filename=$("workspaceFilename"),KEY="hamasa.workspace.files.v1";
  const seed=[{name:"index.html",language:"html",content:"<!doctype html>\n<html lang=\"ar\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>مشروعي</title><body><h1>أهلاً بيك في مساحة عمل حماصة</h1><p>عدّل الكود واضغط معاينة.</p></body></html>"}];
  let files=[],active=0,capability=null;
  try{const saved=JSON.parse(localStorage.getItem(KEY)||"null");files=Array.isArray(saved)&&saved.length?saved:seed;}catch{files=seed;}
  files=files.filter(f=>f&&typeof f.name==="string"&&typeof f.content==="string").slice(0,30);if(!files.length)files=seed;
  const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(files));}catch{status("مساحة التخزين ممتلئة؛ نزّل ملفاتك للاحتفاظ بنسخة.");}};
  function status(text){output.textContent=text;}
  function inferLanguage(name){const ext=name.split(".").pop().toLowerCase();return({html:"html",htm:"html",js:"javascript",mjs:"javascript",py:"python",css:"css",md:"markdown",json:"json",txt:"text"})[ext]||"text";}
  function renderTabs(){tabs.replaceChildren();files.forEach((file,index)=>{const b=document.createElement("button");b.type="button";b.textContent=file.name;b.className=index===active?"active":"";b.addEventListener("click",()=>{sync();active=index;load();});tabs.append(b);});}
  function sync(){if(!files[active])return;files[active].name=filename.value.trim()||"untitled.txt";files[active].language=language.value;files[active].content=editor.value;save();}
  function load(){const file=files[active];if(!file)return;filename.value=file.name;language.value=file.language||inferLanguage(file.name);editor.value=file.content;renderTabs();preview.hidden=true;status("الملف محفوظ تلقائياً على هذا الجهاز.");}
  function addFile(){sync();if(files.length>=30){status("وصلت للحد الأقصى: 30 ملفاً.");return;}const name=window.prompt("اسم الملف الجديد (مثال: app.py):","new-file.js");if(!name)return;if(!/^[\p{L}\p{N}_.-]{1,100}$/u.test(name)){status("اسم الملف غير صالح.");return;}if(files.some(f=>f.name===name)){status("الملف موجود بالفعل.");return;}files.push({name,language:inferLanguage(name),content:""});active=files.length-1;save();load();}
  function download(){sync();const file=files[active],blob=new Blob([file.content],{type:"text/plain;charset=utf-8"}),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=file.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  async function getCapabilities(){if(capability)return capability;const base=String(window.HAMASA_CONFIG?.API_URL||"https://hamasa-api-production.up.railway.app").replace(/\/+$/,"");const response=await fetch(base+"/api/capabilities",{credentials:"include"}),data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.detail||"تعذر التحقق من قدرات الخادم.");capability=data.capabilities||{};return capability;}
  async function run(){sync();const file=files[active],lang=file.language;if(lang==="html"){preview.hidden=false;preview.srcdoc=file.content;status("معاينة HTML داخل إطار معزول. لا يتم تحميل ملفات محلية تلقائياً.");return;}if(lang!=="python"&&lang!=="javascript"){status("التشغيل متاح حالياً لـ Python وJavaScript. استخدم معاينة HTML لملفات HTML.");return;}const button=$("workspaceRun");button.disabled=true;status("جاري التحقق من مشغّل الأكواد…");try{const caps=await getCapabilities();if(!caps.code_execution){status("تشغيل الأكواد غير مفعّل على الخادم حالياً. الكود محفوظ ويمكن تنزيله.");return;}const base=String(window.HAMASA_CONFIG?.API_URL||"https://hamasa-api-production.up.railway.app").replace(/\/+$/,""),fence=String.fromCharCode(96).repeat(3),tag=lang==="python"?"python":"javascript";const response=await fetch(base+"/api/chat",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({messages:[{role:"user",content:fence+tag+"\n"+file.content+"\n"+fence}]})});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.detail||"فشل تشغيل الكود.");status(String(data.reply||"لم يرجع الخادم نتيجة."));}catch(error){status(error.message||"تعذر تشغيل الكود.");}finally{button.disabled=false;}}
  openButton.addEventListener("click",async()=>{dialog.showModal();load();try{await getCapabilities();}catch{}});
  $("workspaceClose").addEventListener("click",()=>{sync();dialog.close();});
  $("workspaceAdd").addEventListener("click",addFile);$("workspaceDownload").addEventListener("click",download);$("workspaceRun").addEventListener("click",run);
  $("workspaceDelete").addEventListener("click",()=>{if(files.length<=1){status("لازم تسيب ملف واحد على الأقل.");return;}files.splice(active,1);active=Math.max(0,active-1);save();load();});
  editor.addEventListener("input",sync);filename.addEventListener("change",()=>{sync();renderTabs();});language.addEventListener("change",sync);dialog.addEventListener("close",sync);load();
})();