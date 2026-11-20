(() => {
  "use strict";
  if (window.__HAMASA_VOICE_MODE__) return;
  window.__HAMASA_VOICE_MODE__ = true;
  const $ = id => document.getElementById(id);
  const openButton = $("voice-mode-open");
  if (!openButton) return;
  const apiBase = String(window.HAMASA_CONFIG?.API_URL || "https://hamasa-api-production.up.railway.app").replace(/\/+$/, "");
  let recorder=null, stream=null, chunks=[], busy=false, active=false, audioContext=null, analyser=null, raf=0;
  let speechStarted=0, lastVoice=0, segmentHasSpeech=false, segmentStarted=0, lastReply="";
  let speechButton=null;
  const dialog=document.createElement("section");
  dialog.id="hamasaVoiceDialog";
  dialog.setAttribute("role","dialog"); dialog.setAttribute("aria-modal","true"); dialog.setAttribute("aria-labelledby","hvTitle");
  dialog.innerHTML=`
    <div class="hv-panel">
      <div class="hv-topbar"><h2 id="hvTitle">محادثة حماصة المستمرة</h2><button class="hv-close" id="hvClose" type="button" aria-label="إغلاق">×</button></div>
      <div class="hv-stage" aria-hidden="true"><div class="hv-aura"></div><div class="hv-orbit"></div><div class="hv-robot" id="hvRobot"><div class="hv-face"><div class="hv-eyes"><i></i><i></i></div><div class="hv-mouth"></div></div></div></div>
      <div class="hv-status" id="hvStatus" role="status" aria-live="polite">اضغط بدء المحادثة واسمح باستخدام الميكروفون.</div>
      <div class="hv-transcript" id="hvTranscript">حماصة هتسمعك وترد عليك تلقائيًا.</div>
      <div class="hv-controls"><button class="hv-btn primary" id="hvMic" type="button">🎙 ابدأ المحادثة</button><button class="hv-btn" id="hvListen" type="button" disabled>▶ أعد سماع آخر رد</button></div>
      <p class="hv-note">اضغط مرة واحدة للبدء. حماصة تلتقط كلامك بعد سكتة قصيرة، ترد بصوتها، ثم تعود للاستماع. اضغط إيقاف المحادثة لإنهائها.</p>
    </div>`;
  document.body.append(dialog);
  const status=$("hvStatus"), transcript=$("hvTranscript"), robot=$("hvRobot"), mic=$("hvMic"), listen=$("hvListen");
  const setStatus=(message,mode="")=>{status.textContent=message;robot.className="hv-robot "+mode;};
  const mimeType=()=>["audio/mp4","audio/webm;codecs=opus","audio/webm","audio/ogg;codecs=opus"].find(x=>window.MediaRecorder?.isTypeSupported?.(x))||"";
  const stopTracks=()=>{if(stream)stream.getTracks().forEach(t=>t.stop());stream=null;};
  function endSession(){
    active=false; busy=false;
    if(raf)cancelAnimationFrame(raf); raf=0;
    try{if(recorder&&recorder.state!=="inactive"){recorder.onstop=null;recorder.stop();}}catch{}
    recorder=null; stopTracks();
    if(audioContext){audioContext.close().catch(()=>{});audioContext=null;} analyser=null;
    mic.disabled=false;mic.textContent="🎙 ابدأ المحادثة";mic.classList.remove("primary");
    listen.disabled=!lastReply;setStatus("المحادثة اتوقفت.");
  }
  const close=()=>{endSession();dialog.classList.remove("open");};
  async function transcribe(blob){
    if(!blob||blob.size<1200)return "";
    if(blob.size>11*1024*1024)throw new Error("التسجيل طويل جدًا؛ حاول تقسم كلامك.");
    const raw=(blob.type||"audio/webm").split(";")[0].toLowerCase();
    const mime=raw==="audio/x-m4a"?"audio/mp4":raw;
    const dataUrl=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(new Error("تعذرت قراءة التسجيل."));reader.onload=()=>resolve(String(reader.result||""));reader.readAsDataURL(blob);});
    const comma=dataUrl.indexOf(",");
    const response=await fetch(apiBase+"/api/transcribe",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json","X-Hamasa-Request":"1"},body:JSON.stringify({audio:dataUrl.slice(comma+1),mime_type:mime}),signal:AbortSignal.timeout?AbortSignal.timeout(120000):undefined});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(data.detail||"خدمة تحويل الصوت لنص غير متاحة.");
    return String(data.transcript||"").trim();
  }
  async function speak(text){
    const bridge=window.HAMASA_VOICE_BRIDGE;
    if(!bridge?.speakAndWait)throw new Error("تشغيل الرد الصوتي غير جاهز.");
    if(!speechButton){speechButton=document.createElement("button");speechButton.type="button";speechButton.style.cssText="position:fixed;left:-9999px";document.body.append(speechButton);}
    await bridge.speakAndWait(text,speechButton);
  }
  function startSegment(){
    if(!active||busy||!stream)return;
    const mime=mimeType();
    recorder=mime?new MediaRecorder(stream,{mimeType:mime}):new MediaRecorder(stream);
    const current=recorder; chunks=[];speechStarted=0;lastVoice=0;segmentHasSpeech=false;segmentStarted=performance.now();
    current.ondataavailable=e=>{if(e.data?.size)chunks.push(e.data);};
    current.onerror=()=>{setStatus("حصل خطأ في التقاط الصوت. بحاول أكمل…");};
    current.onstop=async()=>{
      const blob=new Blob(chunks,{type:current.mimeType||mime||"audio/webm"});
      chunks=[];if(recorder===current)recorder=null;
      if(!active)return;
      if(!segmentHasSpeech||blob.size<1200){startSegment();return;}
      busy=true;mic.disabled=true;
      try{
        setStatus("بفهم كلامك…","thinking");
        const text=await transcribe(blob);
        if(!text){setStatus("ماسمعتش كلام واضح. كمل كلامك…","listening");return;}
        transcript.textContent="أنت: "+text+"\n\nحماصة: بتحضّر الرد…";
        setStatus("حماصة بتفكر…","thinking");
        const bridge=window.HAMASA_VOICE_BRIDGE;
        const reply=await bridge?.send?.(text);
        if(!reply)throw new Error("ماوصلنيش رد من حماصة.");
        lastReply=String(reply);listen.disabled=false;
        transcript.textContent="أنت: "+text+"\n\nحماصة: "+lastReply;
        setStatus("حماصة بترد عليك…","talking");
        await speak(lastReply);
        if(active)setStatus("سامعك… كمل كلامك","listening");
      }catch(error){
        setStatus(error?.message||"حصل خطأ أثناء المحادثة.");
      }finally{
        busy=false;mic.disabled=false;
        if(active)startSegment();
      }
    };
    current.start(250);
  }
  function monitor(){
    if(!active||!analyser)return;
    const data=new Uint8Array(analyser.fftSize);analyser.getByteTimeDomainData(data);
    let sum=0;for(let i=0;i<data.length;i++){const v=(data[i]-128)/128;sum+=v*v;}
    const rms=Math.sqrt(sum/data.length), now=performance.now();
    if(!busy&&recorder?.state==="recording"){
      if(rms>0.022){if(!speechStarted)speechStarted=now;lastVoice=now;if(now-speechStarted>300)segmentHasSpeech=true;}
      if(segmentHasSpeech&&lastVoice&&now-lastVoice>1150){try{recorder.stop();}catch{}}
      else if(now-segmentStarted>18000){try{recorder.stop();}catch{}}
    }
    raf=requestAnimationFrame(monitor);
  }
  async function startSession(){
    if(active)return;
    if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){setStatus("المتصفح لا يدعم المحادثة الصوتية.");return;}
    try{
      mic.disabled=true;setStatus("بفتح الميكروفون…","thinking");
      stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      const AudioCtx=window.AudioContext||window.webkitAudioContext;
      if(!AudioCtx)throw new Error("المتصفح لا يدعم تحليل الصوت اللازم للاستماع التلقائي.");
      audioContext=new AudioCtx();await audioContext.resume();
      const source=audioContext.createMediaStreamSource(stream);analyser=audioContext.createAnalyser();analyser.fftSize=1024;source.connect(analyser);
      active=true;mic.disabled=false;mic.textContent="■ إيقاف المحادثة";
      listen.disabled=!lastReply;transcript.textContent="أنا سامعك. اتكلم…";
      setStatus("سامعك… اتكلم براحتك","listening");
      startSegment();monitor();
    }catch(error){endSession();setStatus(error?.name==="NotAllowedError"?"اسمح للمتصفح باستخدام الميكروفون من إعدادات الموقع.":error.message||"تعذر بدء المحادثة.");}
  }
  openButton.addEventListener("click",()=>{dialog.classList.add("open");setStatus("اضغط بدء المحادثة واسمح باستخدام الميكروفون.");mic.focus();});
  $("hvClose").addEventListener("click",close);
  dialog.addEventListener("click",e=>{if(e.target===dialog)close();});
  mic.addEventListener("click",()=>{if(active)endSession();else startSession();});
  listen.addEventListener("click",async()=>{if(lastReply){try{await speak(lastReply);}catch(e){setStatus(e.message||"تعذر تشغيل الرد.");}}});
  document.addEventListener("keydown",e=>{if(e.key==="Escape"&&dialog.classList.contains("open"))close();});
  window.addEventListener("pagehide",endSession);
})();