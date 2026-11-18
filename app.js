(() => {
  const $ = id => document.getElementById(id);
  const API = (window.HAMASA_CONFIG?.API_URL || "").replace(/\/$/, "");
  let conversations = JSON.parse(localStorage.getItem("hamasa_conversations") || "[]");
  let current = {id: crypto.randomUUID(), title:"محادثة جديدة", messages:[]};
  let recognition = null, listening = false;
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
  async function send(text){
    const content=(text||input.value).trim();if(!content)return;
    input.value="";input.style.height="auto";addMessage("user",content);
    const placeholder={role:"assistant",content:""};
    const row=document.createElement("div");row.className="message assistant";row.innerHTML='<div class="message-avatar">ح</div><div class="bubble">حماصة بيفكر...</div>';messages.append(row);
    try{
      if(!API||API.includes("YOUR-RAILWAY"))throw new Error("لسه السيرفر مش متوصل. اربط Backend حماصة واضبط API_URL في config.js.");
      const response=await fetch(API+"/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({messages:current.messages.map(m=>({role:m.role,content:m.content}))})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"حصل خطأ في الاتصال.");
      placeholder.content=data.reply;current.messages.push(placeholder);saveCurrent();renderMessages();
      if($("speakToggle").checked)speak(data.reply);
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
  function chooseArabicVoice(lang){
    const voices=speechSynthesis.getVoices()||[];
    const base=(lang||"ar-EG").toLowerCase();
    const arabic=voices.filter(v=>(v.lang||"").toLowerCase().startsWith("ar"));
    return arabic.find(v=>(v.lang||"").toLowerCase()===base)
      ||arabic.find(v=>(v.lang||"").toLowerCase().startsWith("ar-eg"))
      ||arabic.find(v=>v.default)
      ||arabic[0]
      ||null;
  }
  function speak(text){
    if(!("speechSynthesis" in window))return;
    const clean=cleanSpeechText(text);
    if(!clean)return;
    speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance(clean);
    u.lang=$("languageSelect").value||"ar-EG";
    const voice=chooseArabicVoice(u.lang);
    if(voice)u.voice=voice;
    u.rate=.88;
    u.pitch=1;
    u.volume=1;
    speechSynthesis.speak(u);
  }
  if("speechSynthesis" in window){
    speechSynthesis.getVoices();
    speechSynthesis.addEventListener?.("voiceschanged",()=>speechSynthesis.getVoices());
  }
  function setupRecognition(){
    const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!SR){alert("التعرف على الصوت غير مدعوم في المتصفح ده. جرّب Chrome أو Edge.");return null;}
    const r=new SR();r.lang=$("languageSelect").value;r.interimResults=true;r.continuous=false;
    r.onstart=()=>{listening=true;$("micButton").classList.add("listening");$("voiceMic").classList.add("listening");$("voiceStatus").textContent="سامعك... اتكلم";};
    r.onresult=e=>{let final="",interim="";for(let i=e.resultIndex;i<e.results.length;i++){if(e.results[i].isFinal)final+=e.results[i][0].transcript;else interim+=e.results[i][0].transcript;}input.value=final||interim;};
    r.onerror=e=>{$("voiceStatus").textContent=e.error==="not-allowed"?"اسمح للمتصفح باستخدام المايك":"الصوت مش واضح، جرّب تاني";};
    r.onend=()=>{listening=false;$("micButton").classList.remove("listening");$("voiceMic").classList.remove("listening");$("voiceStatus").textContent="أنا سامعك";if(input.value.trim())send();};
    return r;
  }
  function toggleMic(){if(listening){recognition?.stop();return;}recognition=setupRecognition();if(recognition)recognition.start();}
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
  renderHistory();renderMessages();
})();
