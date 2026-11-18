(() => {
  const $ = id => document.getElementById(id);
  const API = (window.HAMASA_CONFIG?.API_URL || "").replace(/\/$/, "");
  let conversations = JSON.parse(localStorage.getItem("hamasa_conversations") || "[]");
  let current = {id: crypto.randomUUID(), title:"محادثة جديدة", messages:[]};
  let recognition = null, listening = false, recognitionSpeaksReply = false;
  let recorder = null, recordedChunks = [];
  let visualMode = localStorage.getItem("hamasa_visual") || "face";
  const MEMORY_KEY = "hamasa_personal_memory";
  const getMemory = () => localStorage.getItem(MEMORY_KEY) || "";
  const welcome=$("welcome"), messages=$("messages"), input=$("messageInput");
  const persist=()=>localStorage.setItem("hamasa_conversations",JSON.stringify(conversations));
  function renderHistory(){
    const host=$("historyList"); host.innerHTML="";
    if(!conversations.length){host.innerHTML='<div class="empty-history">محادثاتك هتظهر هنا</div>';return;}
    conversations.slice().reverse().forEach(c=>{const b=document.createElement("button");b.className="history-entry";b.textContent=c.title;b.onclick=()=>{current=c;renderMessages();};host.append(b);});
  }
  function saveCurrent(){
    if(!current.messages.length)return;
    const i=conversations.findIndex(c=>c.id===current.id);
    if(i>=0)conversations[i]=current;else conversations.push(current);
    persist();renderHistory();
  }
  function addMessage(role,content){
    current.messages.push({role,content}); if(current.messages.length===1)current.title=content.slice(0,32);
    renderMessages();saveCurrent();
  }
  function renderMessages(){
    messages.innerHTML="";welcome.classList.toggle("hidden",current.messages.length>0);
    current.messages.forEach(m=>{
      const row=document.createElement("div");row.className="message "+(m.role==="user"?"user":"assistant");
      const avatar=document.createElement("div");avatar.className="message-avatar";avatar.textContent=m.role==="user"?"أنت":"ح";
      const bubble=document.createElement("div");bubble.className="bubble";bubble.textContent=m.content;
      row.append(avatar,bubble);messages.append(row);
    });
    $("chatView").scrollTop=$("chatView").scrollHeight;
  }
  async function send(text,{speakResponse=false}={}){
    const content=(text||input.value).trim();if(!content)return;
    input.value="";input.style.height="auto";addMessage("user",content);
    const placeholder={role:"assistant",content:""};
    const row=document.createElement("div");row.className="message assistant";row.innerHTML='<div class="message-avatar">ح</div><div class="bubble">حماصة بيفكر...</div>';messages.append(row);
    try{
      if(!API||API.includes("YOUR-RAILWAY"))throw new Error("لسه السيرفر مش متوصل. اربط Backend حماصة واضبط API_URL في config.js.");
      const response=await fetch(API+"/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({messages:current.messages.slice(-30).map(m=>({role:m.role,content:m.content})),memory:getMemory()})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"حصل خطأ في الاتصال.");
      placeholder.content=data.reply;current.messages.push(placeholder);saveCurrent();renderMessages();
      if(speakResponse && $("speakToggle").checked) await speak(data.reply);
    }catch(e){row.querySelector(".bubble").textContent=e.message;row.querySelector(".bubble").style.color="#ffadbd";}
  }
  function cleanSpeechText(text){
    return String(text||"")
      .replace(/\x60\x60\x60[\s\S]*?\x60\x60\x60/g," ")
      .replace(/\[([^\]]+)\]\([^)]+\)/g,"$1")
      .replace(/https?:\/\/\S+/g," ")
      .replace(/\x60([^\x60]+)\x60/g,"$1")
      .replace(/<[^>]*>/g," ")
      .replace(/[*_~#>|]/g," ")
      .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}]/gu," ")
      .replace(/[\u200D\uFE0F\u{1F3FB}-\u{1F3FF}]/gu,"")
      .replace(/[→↗↘←↑↓•▪◈⌁]/g," ")
      .replace(/\\n/g," ")
      .replace(/[\t\r]+/g," ")
      .replace(/\n{2,}/g,". ")
      .replace(/\s+([،؛.!؟])/g,"$1")
      .replace(/([،؛.!؟])(?=\S)/g,"$1 ")
      .replace(/\s{2,}/g," ")
      .trim();
  }
  async function speak(text){
    const clean=cleanSpeechText(text);
    if(!clean)return;
    const gender=$("ttsGender")?.value||"male";
    try{
      if(!API)throw new Error("رابط السيرفر غير مضبوط.");
      const response=await fetch(API+"/api/tts",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text:clean,gender})});
      const data=await response.json();
      if(!response.ok)throw new Error(data.detail||"تعذر تشغيل Gemini TTS");
      const raw=atob(data.audio),bytes=new Uint8Array(raw.length);
      for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);
      const blob=new Blob([bytes],{type:data.mime_type||"audio/wav"});
      const url=URL.createObjectURL(blob),audio=new Audio(url);
      audio.onended=()=>URL.revokeObjectURL(url);
      audio.onerror=()=>{URL.revokeObjectURL(url);if($("ttsStatus"))$("ttsStatus").textContent="Gemini رجّع ملف صوت غير قابل للتشغيل.";};
      await audio.play();
    }catch(e){
      console.error("Gemini TTS error:",e);
      if($("ttsStatus"))$("ttsStatus").textContent="Gemini TTS مش شغال: "+e.message;
    }
  }
  async function checkTTSStatus(){
    if(!API)return;
    try{
      const r=await fetch(API+"/api/tts/status"),s=await r.json();
      if($("ttsStatus")){
        $("ttsStatus").textContent="حالة Gemini TTS: "+(s.gemini_configured?"جاهز":"أضف مفتاح Gemini في Railway");
      }
    }catch(e){if($("ttsStatus"))$("ttsStatus").textContent="تعذر فحص خدمات الصوت حالياً.";}
  }
  ["ttsGender"].forEach(id=>{
    const el=$(id);if(el){const saved=localStorage.getItem("hamasa_"+id);if(saved)el.value=saved;el.onchange=()=>localStorage.setItem("hamasa_"+id,el.value);}
  });
  checkTTSStatus();
  const memoryInput = $("memoryInput");
  const memoryStatus = $("memoryStatus");
  if (memoryInput) {
    memoryInput.value = getMemory();
    $("saveMemoryButton").onclick = () => {
      localStorage.setItem(MEMORY_KEY, memoryInput.value.trim().slice(0, 6000));
      memoryStatus.textContent = "اتحفظت ذاكرة حماصة على الجهاز ده.";
    };
    $("clearMemoryButton").onclick = () => {
      memoryInput.value = "";
      localStorage.removeItem(MEMORY_KEY);
      memoryStatus.textContent = "اتمسحت الذاكرة المحفوظة على الجهاز ده.";
    };
  }
  async function transcribeRecordedAudio(blob){
    try{
      $("voiceStatus").textContent="بحوّل كلامك لنص...";
      const dataUrl=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(",")[1]);reader.onerror=reject;reader.readAsDataURL(blob);});
      const response=await fetch(API+"/api/transcribe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({audio:dataUrl,mime_type:blob.type||"audio/mp4"})});
      const data=await response.json();
      if(!response.ok)throw new Error(data.detail||"تعذر فهم التسجيل");
      input.value=(data.transcript||"").trim();
      if(!input.value){$("voiceStatus").textContent="ملحقتش أسمع كلام واضح، جرّب تاني";return;}
      $("voiceStatus").textContent="وصلت، بفكر...";
      await send(undefined,{speakResponse:true});
    }catch(e){$("voiceStatus").textContent="حصلت مشكلة في تحويل الصوت: "+e.message;}
  }
  async function toggleMic(){
    if(listening){
      if(recorder&&recorder.state!=="inactive")recorder.stop();
      else if(recognition)recognition.stop();
      return;
    }
    const voiceMode=!$("voiceView").classList.contains("hidden");
    recognitionSpeaksReply=voiceMode;
    // Native speech recognition is preferred when available; MediaRecorder + Gemini is the iPhone/Safari fallback.
    const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(SR){
      try{
        recognition=new SR();recognition.lang=$("languageSelect").value;recognition.interimResults=true;recognition.continuous=false;
        recognition.onstart=()=>{listening=true;$("micButton").classList.add("listening");$("voiceMic").classList.add("listening");$("voiceStatus").textContent="سامعك... اتكلم";};
        recognition.onresult=e=>{let final="",interim="";for(let i=e.resultIndex;i<e.results.length;i++){if(e.results[i].isFinal)final+=e.results[i][0].transcript;else interim+=e.results[i][0].transcript;}input.value=final||interim;};
        recognition.onerror=e=>{if(e.error==="not-allowed")$("voiceStatus").textContent="اسمح للمتصفح باستخدام المايك";else $("voiceStatus").textContent="هحوّل لطريقة تسجيل بديلة...";};
        recognition.onend=()=>{listening=false;$("micButton").classList.remove("listening");$("voiceMic").classList.remove("listening");const shouldSpeak=recognitionSpeaksReply;recognitionSpeaksReply=false;if(input.value.trim())send(undefined,{speakResponse:shouldSpeak});};
        recognition.start();return;
      }catch(e){recognition=null;}
    }
    try{
      if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder)throw new Error("المتصفح لا يدعم تسجيل الصوت. افتح الموقع في Safari واضغط Allow للمايك.");
      const stream=await navigator.mediaDevices.getUserMedia({audio:true});
      const types=["audio/mp4","audio/webm;codecs=opus","audio/webm","audio/ogg;codecs=opus"];
      const mime=types.find(t=>MediaRecorder.isTypeSupported?.(t));
      recorder=new MediaRecorder(stream,mime?{mimeType:mime}:undefined);recordedChunks=[];
      recorder.ondataavailable=e=>{if(e.data&&e.data.size)recordedChunks.push(e.data);};
      recorder.onerror=()=>{$("voiceStatus").textContent="تعذر تسجيل الصوت. جرّب تاني.";stream.getTracks().forEach(t=>t.stop());listening=false;};
      recorder.onstop=()=>{listening=false;$("micButton").classList.remove("listening");$("voiceMic").classList.remove("listening");stream.getTracks().forEach(t=>t.stop());const blob=new Blob(recordedChunks,{type:recorder.mimeType||"audio/mp4"});if(blob.size)transcribeRecordedAudio(blob);else $("voiceStatus").textContent="التسجيل فاضي، جرّب تاني";};
      recorder.start();listening=true;$("micButton").classList.add("listening");$("voiceMic").classList.add("listening");$("voiceStatus").textContent="سامعك... اضغط تاني لما تخلص";
    }catch(e){$("voiceStatus").textContent=e.message||"مش قادر أفتح المايك";listening=false;}
  }
  function view(name){
    $("chatView").classList.toggle("hidden",name!=="chat");$("composerWrap").classList.toggle("hidden",name!=="chat");
    $("voiceView").classList.toggle("hidden",name!=="voice");$("settingsView").classList.toggle("hidden",name!=="settings");
    document.querySelectorAll(".nav-item").forEach(b=>b.classList.toggle("active",b.dataset.view===name));
    $("sidebar").classList.remove("open");
  }
  $("sendButton").onclick=()=>send();input.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send();}});
  input.addEventListener("input",()=>{input.style.height="auto";input.style.height=Math.min(input.scrollHeight,140)+"px";});
  $("micButton").onclick=toggleMic;$("voiceMic").onclick=toggleMic;
  $("newChat").onclick=()=>{saveCurrent();current={id:crypto.randomUUID(),title:"محادثة جديدة",messages:[]};renderMessages();view("chat");};
  $("clearHistory").onclick=()=>{if(confirm("تمسح سجل المحادثات المحفوظ؟")){conversations=[];persist();renderHistory();}};
  $("menuBtn").onclick=()=>$("sidebar").classList.toggle("open");
  $("themeBtn").onclick=()=>document.body.classList.toggle("light");
  $("settingsBtn").onclick=()=>view("settings");
  document.querySelectorAll(".nav-item").forEach(b=>b.onclick=()=>view(b.dataset.view));
  document.querySelectorAll(".suggestion").forEach(b=>b.onclick=()=>{input.value=b.textContent.replace("↗","").trim();send();});
  $("languageSelect").onchange=()=>{if(recognition)recognition.lang=$("languageSelect").value;};
  document.querySelectorAll(".hamasa-face").forEach(el=>el.classList.toggle("face-hidden",visualMode!=="face"));
  const visualSelect=$("visualSelect");
  if(visualSelect){visualSelect.value=visualMode;visualSelect.onchange=()=>{visualMode=visualSelect.value;localStorage.setItem("hamasa_visual",visualMode);document.querySelectorAll(".hamasa-face").forEach(el=>el.classList.toggle("face-hidden",visualMode!=="face"));document.querySelectorAll(".orb").forEach(el=>el.classList.toggle("orb-hidden",visualMode==="face"));};}
  document.querySelectorAll(".orb").forEach(el=>el.classList.toggle("orb-hidden",visualMode==="face"));
  renderHistory();renderMessages();
})();
