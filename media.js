(() => {
  "use strict";
  const dialog=document.getElementById("imageDlg"),openButton=document.getElementById("imageLab");
  if(!dialog||!openButton||window.__HAMASA_IMAGE_LAB_READY__)return;
  window.__HAMASA_IMAGE_LAB_READY__=true;
  const $=id=>document.getElementById(id);
  let generatedUrl="";
  function setStatus(text){$("imageStatus").textContent=text;}
  function clearResult(){const img=$("imageResult");img.hidden=true;img.removeAttribute("src");$("imageDownload").hidden=true;if(generatedUrl.startsWith("blob:"))URL.revokeObjectURL(generatedUrl);generatedUrl="";}
  openButton.addEventListener("click",()=>{dialog.showModal();clearResult();setStatus("اكتب وصف الصورة. لو اخترت صورة مرجعية، هيتحول الطلب لتعديل الصورة.");});
  $("imageClose").addEventListener("click",()=>dialog.close());
  $("imageGenerate").addEventListener("click",async()=>{
    const prompt=$("imagePrompt").value.trim(),file=$("imageReference").files?.[0],button=$("imageGenerate");
    if(prompt.length<3){setStatus("اكتب وصفاً أوضح للصورة.");return;}
    if(file&&(!["image/png","image/jpeg","image/webp"].includes(file.type)||file.size>10*1024*1024)){setStatus("الصورة المرجعية لازم تكون PNG أو JPG أو WebP وأقل من 10 ميجابايت.");return;}
    button.disabled=true;clearResult();setStatus(file?"جاري إرسال الصورة المرجعية للتعديل…":"جاري إنشاء الصورة…");
    try{
      let imageData="";
      if(file){const dataUrl=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(new Error("تعذرت قراءة الصورة."));reader.onload=()=>resolve(String(reader.result||""));reader.readAsDataURL(file);});const comma=dataUrl.indexOf(",");if(comma<0)throw new Error("صيغة الصورة غير صالحة.");imageData=dataUrl.slice(comma+1);}
      const base=String(window.HAMASA_CONFIG?.API_URL||"https://hamasa-api-production.up.railway.app").replace(/\/+$/,"");
      const response=await fetch(base+"/api/images/generate",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({prompt,size:$("imageSize").value,image_data:imageData,mime_type:file?.type||"image/png"})});
      const data=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(data.detail||"تعذر إنشاء الصورة.");
      if(data.data_url)generatedUrl=data.data_url;else if(data.image_url)generatedUrl=data.image_url;else throw new Error("مزود الصور لم يرجع صورة قابلة للعرض.");
      $("imageResult").src=generatedUrl;$("imageResult").hidden=false;$("imageDownload").hidden=false;
      $("imageDownload").href=generatedUrl;$("imageDownload").download="hamasa-generated-image.png";
      setStatus(data.revised_prompt?"تم إنشاء الصورة. وصف المزود المحسّن: "+data.revised_prompt:"تم إنشاء الصورة بنجاح.");
    }catch(error){setStatus(error.message||"حصل خطأ أثناء إنشاء الصورة.");}
    finally{button.disabled=false;}
  });
  dialog.addEventListener("close",()=>{});
})();