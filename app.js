(() => {
  const $ = id => document.getElementById(id);
  const API = (window.HAMASA_CONFIG?.API_URL || "").replace(/\/$/, "");
  let conversations = JSON.parse(localStorage.getItem("hamasa_conversations") || "[]");
  let current = {id: crypto.randomUUID(), title:"محادثة جديدة", messages:[]};
  let recognition = null, listening = false, recognitionSpeaksReply = false;
  let recorder = null, recordedChunks = [];
  let visualMode = localStorage.getItem("hamasa_visual") || "face";

  const translations={
    en:{newChat:"New chat",workspace:"Workspace",chat:"Chat",voiceMode:"Voice mode",settings:"Settings",recent:"Recent",clear:"Clear",historyEmpty:"Your chats will appear here",online:"Online",welcome:"Hi, I’m",welcomeText:"Here to listen, understand, and help you with anything.",voiceEyebrow:"VOICE COMPANION",voiceIdle:"I’m listening",voicePrompt:"Tap the mic and speak naturally",voiceStopHint:"Tap to start or end live conversation",speakReplies:"Speak replies",speakRepliesHint:"Read Hamasa’s replies aloud",voiceEngine:"Voice engine",voiceGender:"Voice",voiceGenderHint:"Change it anytime",memoryTitle:"Hamasa memory",memoryPrivacy:"This memory is sent with your messages to personalize replies.",memoryHint:"Save useful details, projects and preferences. This memory is stored only in this browser.",saveMemory:"Save memory",clearMemory:"Clear memory",speechLanguage:"Speech recognition language",speechLanguageHint:"Language used to recognize speech",assistantLook:"Assistant appearance",assistantLookHint:"Animated visual style",chatPlaceholder:"Message Hamasa...",footer:"Hamasa can make mistakes. Check important information.",thinking:"Hamasa is thinking…",micEmpty:"I couldn’t hear anything clearly. Try again.",transcribing:"Transcribing your voice…",heard:"Got it. Thinking…",recording:"Live voice conversation is active.",recordingEmpty:"No audio was captured. Check microphone permission and try again.",micPermission:"Microphone access was denied. Allow it in Safari settings.",micError:"Could not start microphone: ",memorySaved:"Memory saved on this browser.",memoryCleared:"Saved memory cleared from this browser.",ttsChecking:"Checking voice services…",ttsReady:"Gemini TTS: Ready",ttsMissing:"Add your Gemini API key in Railway.",ttsFailed:"Could not check voice services.",transcriptionFailed:"Voice transcription failed: "},
    ar:{newChat:"محادثة جديدة",workspace:"مساحتك",chat:"المحادثة",voiceMode:"وضع الصوت",settings:"الإعدادات",recent:"الأخيرة",clear:"مسح",historyEmpty:"محادثاتك هتظهر هنا",online:"متصل",welcome:"أهلاً بيك، أنا",welcomeText:"موجود علشان أسمعك، أفهمك، وأساعدك في أي حاجة.",voiceEyebrow:"مرافقك الصوتي",voiceIdle:"أنا سامعك",voicePrompt:"اضغط على المايك واتكلم براحتك",voiceStopHint:"اضغط لبدء المحادثة أو إنهائها",speakReplies:"تشغيل الردود صوتياً",speakRepliesHint:"حماصة يقرأ الردود بصوت مسموع",voiceEngine:"محرك الصوت",voiceGender:"نوع الصوت",voiceGenderHint:"تقدر تغيّره في أي وقت",memoryTitle:"ذاكرة حماصة",memoryPrivacy:"الذاكرة دي بتتبعت مع رسائلك عشان تخصص الردود.",memoryHint:"احفظ معلومات ومشاريع وتفضيلات مهمة. الذاكرة دي بتتحفظ على المتصفح ده فقط.",saveMemory:"حفظ الذاكرة",clearMemory:"مسح الذاكرة",speechLanguage:"لغة التعرف على الكلام",speechLanguageHint:"اللغة المستخدمة لفهم كلامك",assistantLook:"شكل المساعد",assistantLookHint:"المظهر المتحرك",chatPlaceholder:"اكتب لحماصة...",footer:"حماصة ممكن يغلط أحياناً — راجع المعلومات المهمة.",thinking:"حماصة بيفكر…",micEmpty:"ملحقتش أسمع كلام واضح. جرّب تاني.",transcribing:"بحوّل كلامك لنص…",heard:"وصلت، بفكر…",recording:"المحادثة الصوتية المباشرة شغالة.",recordingEmpty:"ملقتش تسجيل صوت. راجع إذن المايك وجرب تاني.",micPermission:"إذن المايك مرفوض. اسمح بيه من إعدادات Safari.",micError:"مش قادر أشغل المايك: ",memorySaved:"اتحفظت الذاكرة على المتصفح ده.",memoryCleared:"اتمسحت الذاكرة المحفوظة من المتصفح ده.",ttsChecking:"جاري فحص خدمات الصوت…",ttsReady:"Gemini TTS: جاهز",ttsMissing:"أضف مفتاح Gemini في Railway.",ttsFailed:"تعذر فحص خدمات الصوت.",transcriptionFailed:"فشل تحويل الصوت لنص: "}
  };
  let locale=localStorage.getItem("hamasa_locale")||"en";
  const tr=k=>translations[locale]?.[k]||translations.en[k]||k;
  function applyLocale(){
    document.documentElement.lang=locale;document.documentElement.dir=locale==="ar"?"rtl":"ltr";
    $("langBtn").textContent=locale==="en"?"عربي":"English";
    $("langBtn").title=locale==="en"?"Switch to Arabic":"Switch to English";
    document.querySelectorAll("[data-i18n]").forEach(el=>{const key=el.dataset.i18n;if(translations[locale][key])el.textContent=translations[locale][key];});
    input.placeholder=tr("chatPlaceholder");input.setAttribute("aria-label",tr("chatPlaceholder"));
    $("clearHistory").textContent=tr("clear");
    $("voiceStatus").textContent=tr("voiceIdle");
    document.querySelector(".composer-foot span").textContent=tr("footer");
    document.querySelectorAll(".suggestion").forEach((b,i)=>{const en=b.dataset.promptEn;const ar=["ساعدني أنظم يومي","اشرحلي موضوع صعب","خلينا نتكلم شوية"][i];b.firstChild.textContent=(locale==="en"?en:ar)+" ";});
    $("newChat").lastChild.textContent=" "+tr("newChat");
    document.querySelector(".top-title").childNodes[1].textContent=" HAMASA ";
    $("ttsGender").options[0].text=locale==="en"?"Male":"رجالي";$("ttsGender").options[1].text=locale==="en"?"Female":"نسائي";
    $("languageSelect").options[0].text=locale==="en"?"Egyptian Arabic":"العربية المصرية";
    $("languageSelect").options[1].text=locale==="en"?"Arabic":"العربية";
    $("languageSelect").options[2].text="English";
    $("visualSelect").options[0].text=locale==="en"?"Hamasa Face":"Face حماصة";
    $("visualSelect").options[1].text="AI Orb";
  }
  $("langBtn").onclick=()=>{locale=locale==="en"?"ar":"en";localStorage.setItem("hamasa_locale",locale);applyLocale();};

  const MEMORY_KEY = "hamasa_personal_memory";
  const getMemory = () => localStorage.getItem(MEMORY_KEY) || "";
  const welcome=$("welcome"), messages=$("messages"), input=$("messageInput");
  const persist=()=>localStorage.setItem("hamasa_conversations",JSON.stringify(conversations));
  function renderHistory(){
    const host=$("historyList"); host.innerHTML="";
    if(!conversations.length){host.innerHTML='<div class="empty-history">'+tr("historyEmpty")+'</div>';return;}
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
    const row=document.createElement("div");row.className="message assistant";row.innerHTML='<div class="message-avatar">ح</div><div class="bubble">'+tr("thinking")+'</div>';messages.append(row);
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
    }catch(e){if($("ttsStatus"))$("ttsStatus").textContent=tr("ttsFailed");}
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
      memoryStatus.textContent = tr("memorySaved");
    };
    $("clearMemoryButton").onclick = () => {
      memoryInput.value = "";
      localStorage.removeItem(MEMORY_KEY);
      memoryStatus.textContent = tr("memoryCleared");
    };
  }
  let liveSocket=null,liveStream=null,liveAudioContext=null,liveProcessor=null,liveSources=[],liveNextTime=0,liveText="",liveReply="",liveReady=false;
  function pcm16Base64(float32){
    const out=new Int16Array(float32.length);
    for(let i=0;i<float32.length;i++){const s=Math.max(-1,Math.min(1,float32[i]));out[i]=s<0?s*32768:s*32767;}
    let binary="";const bytes=new Uint8Array(out.buffer);
    for(let i=0;i<bytes.length;i+=0x8000)binary+=String.fromCharCode(...bytes.subarray(i,Math.min(i+0x8000,bytes.length)));
    return btoa(binary);
  }
  function downsampleTo16k(buffer,inputRate){
    if(inputRate===16000)return buffer;
    const ratio=inputRate/16000, length=Math.floor(buffer.length/ratio), result=new Float32Array(length);
    for(let i=0;i<length;i++){const start=Math.floor(i*ratio),end=Math.min(Math.floor((i+1)*ratio),buffer.length);let sum=0;for(let j=start;j<end;j++)sum+=buffer[j];result[i]=sum/Math.max(1,end-start);}
    return result;
  }
  function stopLivePlayback(){
    for(const source of liveSources){try{source.stop();}catch(_){}}
    liveSources=[];liveNextTime=liveAudioContext?liveAudioContext.currentTime:0;
  }
  function queueLiveAudio(base64){
    if(!liveAudioContext)return;
    const raw=atob(base64),pcm=new Int16Array(raw.length/2);
    for(let i=0;i<pcm.length;i++)pcm[i]=(raw.charCodeAt(i*2)|(raw.charCodeAt(i*2+1)<<8));
    const buffer=liveAudioContext.createBuffer(1,pcm.length,24000),channel=buffer.getChannelData(0);
    for(let i=0;i<pcm.length;i++)channel[i]=pcm[i]/32768;
    const source=liveAudioContext.createBufferSource();source.buffer=buffer;source.connect(liveAudioContext.destination);
    const now=liveAudioContext.currentTime;liveNextTime=Math.max(liveNextTime,now+0.03);source.start(liveNextTime);liveNextTime+=buffer.duration;
    liveSources.push(source);source.onended=()=>{liveSources=liveSources.filter(x=>x!==source);};
  }
  async function startLiveVoice(){
    if(listening){stopLiveVoice();return;}
    try{
      if(!navigator.mediaDevices?.getUserMedia||!window.AudioContext)throw new Error("افتح الموقع في Safari واسمح باستخدام المايك.");
      $("voiceStatus").textContent=locale==="ar"?"بجهّز المحادثة المباشرة...":"Connecting to live voice...";
      liveStream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      liveAudioContext=new (window.AudioContext||window.webkitAudioContext)();
      await liveAudioContext.resume();
      const wsProtocol=API.startsWith("https")?"wss:":"ws:";
      const gender=$("ttsGender")?.value||"male";
      liveSocket=new WebSocket(wsProtocol+"//"+new URL(API).host+"/api/live?gender="+encodeURIComponent(gender));
      liveSocket.onmessage=event=>{
        let packet;try{packet=JSON.parse(event.data);}catch(_){return;}
        if(packet.error){$("voiceStatus").textContent=packet.error;stopLiveVoice();return;}
        if(packet.setupComplete){liveReady=true;$("voiceStatus").textContent=locale==="ar"?"حماصة معاك، اتكلم براحتك":"Hamasa is here. Speak naturally.";return;}
        const content=packet.serverContent||{};
        if(content.interrupted){stopLivePlayback();$("voiceStatus").textContent=locale==="ar"?"سامعك...":"Listening...";}
        if(content.inputTranscription?.text){liveText+=content.inputTranscription.text;}
        if(content.outputTranscription?.text){liveReply+=content.outputTranscription.text;$("voiceStatus").textContent=content.outputTranscription.text.slice(-110);}
        for(const part of (content.modelTurn?.parts||[])){const data=part.inlineData?.data;if(data)queueLiveAudio(data);}
        if(content.turnComplete){
          if(liveText.trim())addMessage("user",liveText.trim());
          if(liveReply.trim())addMessage("assistant",liveReply.trim());
          liveText="";liveReply="";
          if(!content.modelTurn?.parts?.length)$("voiceStatus").textContent=locale==="ar"?"أنا سامعك، كمل":"I'm listening. Go ahead.";
        }
      };
      liveSocket.onerror=()=>{$("voiceStatus").textContent=locale==="ar"?"اتعذر الاتصال بالصوت المباشر. راجع إعدادات Gemini Live في Railway.":"Live voice connection failed. Check Gemini Live settings in Railway.";};
      liveSocket.onclose=()=>{if(listening)stopLiveVoice(false);};
      await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(new Error("انتهت مهلة الاتصال بالصوت المباشر.")),15000);liveSocket.addEventListener("open",()=>{clearTimeout(timeout);resolve();},{once:true});liveSocket.addEventListener("error",()=>{clearTimeout(timeout);reject(new Error("فشل فتح اتصال Gemini Live."));},{once:true});});
      const source=liveAudioContext.createMediaStreamSource(liveStream);
      liveProcessor=liveAudioContext.createScriptProcessor(4096,1,1);
      liveProcessor.onaudioprocess=e=>{
        if(!liveReady||!liveSocket||liveSocket.readyState!==WebSocket.OPEN)return;
        const pcm=downsampleTo16k(e.inputBuffer.getChannelData(0),liveAudioContext.sampleRate);
        liveSocket.send(JSON.stringify({realtimeInput:{audio:{mimeType:"audio/pcm;rate=16000",data:pcm16Base64(pcm)}}}));
      };
      source.connect(liveProcessor);liveProcessor.connect(liveAudioContext.destination);
      listening=true;$("voiceMic").classList.add("listening");$("micButton").classList.add("listening");
      $("voiceStatus").textContent=locale==="ar"?"حماصة معاك، اتكلم براحتك":"Hamasa is here. Speak naturally";
    }catch(e){stopLiveVoice();$("voiceStatus").textContent=e.message||"Could not start live voice.";}
  }
  function stopLiveVoice(closeSocket=true){
    listening=false;liveReady=false;
    $("voiceMic")?.classList.remove("listening");$("micButton")?.classList.remove("listening");
    if(liveProcessor){try{liveProcessor.disconnect();}catch(_){}liveProcessor=null;}
    if(liveStream){liveStream.getTracks().forEach(t=>t.stop());liveStream=null;}
    stopLivePlayback();
    if(closeSocket&&liveSocket){try{liveSocket.close();}catch(_){}}
    liveSocket=null;
    if(liveAudioContext){liveAudioContext.close().catch(()=>{});liveAudioContext=null;}
    if($("voiceStatus"))$("voiceStatus").textContent=locale==="ar"?"المحادثة انتهت":"Voice chat ended";
  }
  async function toggleMic(){
    const voiceMode=!$("voiceView").classList.contains("hidden");
    if(voiceMode){await startLiveVoice();return;}
    if(listening){stopLiveVoice();return;}
    const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(SR){recognition=new SR();recognition.lang=$("languageSelect").value;recognition.interimResults=true;recognition.continuous=false;
      recognition.onstart=()=>{listening=true;$("micButton").classList.add("listening");};
      recognition.onresult=e=>{let result="";for(let i=e.resultIndex;i<e.results.length;i++)if(e.results[i].isFinal)result+=e.results[i][0].transcript;input.value=result||input.value;};
      recognition.onerror=()=>{listening=false;$("micButton").classList.remove("listening");};
      recognition.onend=()=>{listening=false;$("micButton").classList.remove("listening");if(input.value.trim())send();};
      recognition.start();return;
    }
    $("voiceStatus").textContent=locale==="ar"?"استخدم وضع المحادثة الصوتية للمحادثة المباشرة":"Use Voice mode for live conversation.";
  }
  function view(name){
    if(name!=="voice"&&listening)stopLiveVoice();
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
  const savedTheme=localStorage.getItem("hamasa_theme")||"dark";document.body.classList.toggle("light",savedTheme==="light");$("themeBtn").onclick=()=>{const light=document.body.classList.toggle("light");localStorage.setItem("hamasa_theme",light?"light":"dark");};
  $("settingsBtn").onclick=()=>view("settings");
  document.querySelectorAll(".nav-item").forEach(b=>b.onclick=()=>view(b.dataset.view));
  document.querySelectorAll(".suggestion").forEach(b=>b.onclick=()=>{input.value=b.textContent.replace("↗","").trim();send();});
  $("languageSelect").onchange=()=>{if(recognition)recognition.lang=$("languageSelect").value;};
  document.querySelectorAll(".hamasa-face").forEach(el=>el.classList.toggle("face-hidden",visualMode!=="face"));
  const visualSelect=$("visualSelect");
  if(visualSelect){visualSelect.value=visualMode;visualSelect.onchange=()=>{visualMode=visualSelect.value;localStorage.setItem("hamasa_visual",visualMode);document.querySelectorAll(".hamasa-face").forEach(el=>el.classList.toggle("face-hidden",visualMode!=="face"));document.querySelectorAll(".orb").forEach(el=>el.classList.toggle("orb-hidden",visualMode==="face"));};}
  document.querySelectorAll(".orb").forEach(el=>el.classList.toggle("orb-hidden",visualMode==="face"));
  applyLocale();
  const updateViewport=()=>{const vv=window.visualViewport;const h=vv?vv.height:window.innerHeight;document.documentElement.style.setProperty("--app-height",Math.round(h)+"px");if(document.activeElement===input){requestAnimationFrame(()=>{$("chatView").scrollTop=$("chatView").scrollHeight;});}};
  updateViewport();window.addEventListener("resize",updateViewport);if(window.visualViewport){window.visualViewport.addEventListener("resize",updateViewport);window.visualViewport.addEventListener("scroll",updateViewport);}
  input.addEventListener("focus",()=>setTimeout(updateViewport,250));input.addEventListener("blur",()=>setTimeout(updateViewport,250));
  renderHistory();renderMessages();
})();
