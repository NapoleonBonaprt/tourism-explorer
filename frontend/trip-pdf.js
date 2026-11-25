/* Offline-capable traveller-facing guide. Matches the server's trip_guide.py. */
(() => {
  "use strict";
  const C={ink:"#203B35",green:"#315C4D",muted:"#53665D",paper:"#F8F6EF",white:"#FFFFFF",gold:"#E7B96B",soft:"#E8EFE6",pale:"#DCE8D8"};
  const plain=v=>String(v??"").replace(/[\u2013\u2014]/g,"-").replace(/[\u2018\u2019]/g,"'").replace(/[\u201C\u201D]/g,'"').replace(/\s+/g," ").trim();
  const finite=v=>typeof v==="number"&&Number.isFinite(v);
  const approx=v=>Math.floor(v+.5)+"°C";
  const dateText=(v,weekday=false,monthOnly=false)=>{
    const d=new Date(v+"T12:00:00Z");
    if(!Number.isFinite(d.getTime()))return plain(v);
    return d.toLocaleDateString("en-GB",{timeZone:"UTC",year:"numeric",month:monthOnly?"long":"short",...(monthOnly?{}:{day:"numeric"}),...(weekday?{weekday:"short"}:{})});
  };
  const preference=k=>({indoor:"Indoor escapes",outdoor:"Outdoor discoveries",mixed:"Flexible sightseeing"}[k]||"Explore at your pace");
  function monthlySummary(f){
    const vals=Object.fromEntries((f.monthly_weather?.variables||[]).map(v=>[v.label,v.prediction]));
    const t=vals["Mean temperature"],rain=vals["Monthly rainfall"],score=f.predicted_tci;
    const mood=score>=70?"Great for sightseeing":score>=50?"A good time to explore":"Plan for indoor breaks";
    let tip=finite(t)&&t<15?"Bring warm layers.":finite(t)&&t>=28?"Pack light clothes and sun protection.":"Pack light layers.";
    if(finite(rain)&&rain>=60)tip+=" Consider a compact umbrella.";
    return [mood+(finite(t)?" | Around "+approx(t)+" on average":""),tip];
  }
  function dailySummary(w){
    const parts=[];
    if(finite(w.temperature_2m_max))parts.push("High near "+approx(w.temperature_2m_max));
    if(finite(w.precipitation_sum))parts.push(w.precipitation_sum>=3?"Rain expected":w.precipitation_sum>=.5?"Possible light rain":"Little rain expected");
    if(finite(w.wind_speed_10m_max)&&w.wind_speed_10m_max>=30)parts.push("Windy");
    return parts.join(" | ")||"Check local weather before heading out";
  }
  const available=()=>Boolean(window.jspdf&&typeof window.jspdf.jsPDF==="function");
  const coverCache=new Map();
  const requiredPhotos=new Set(["cairo","lisbon","paris","rome","tokyo","madrid","barcelona"]);
  const cityKey=city=>plain(city).toLowerCase();
  async function fetchCover(url, localPhoto=false){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),7000);
    try {
      const r=await fetch(url,{signal:controller.signal});
      if(!r.ok)throw Error("Cover unavailable");
      const blob=await r.blob();
      if(!blob.size)throw Error("Empty cover");
      if(!localPhoto)return {data:new Uint8Array(await blob.arrayBuffer()),kind:r.headers.get("X-Guide-Cover")};
      const image=await createImageBitmap(blob);
      try {
        const canvas=document.createElement("canvas");
        canvas.width=900;canvas.height=560;
        const scale=Math.max(canvas.width/image.width,canvas.height/image.height);
        const w=image.width*scale,h=image.height*scale;
        canvas.getContext("2d").drawImage(image,(canvas.width-w)/2,(canvas.height-h)*.46,w,h);
        const jpeg=await new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(Error("Cover encoding failed")),"image/jpeg",.86));
        return {data:new Uint8Array(await jpeg.arrayBuffer()),kind:"photo"};
      }finally{image.close();}
    }finally{clearTimeout(timer);}
  }
  function prepareCover(city){
    if(!coverCache.has(city)){
      const key=cityKey(city),required=requiredPhotos.has(key);
      const api=(window.WANDERCLIMATE_API_BASE ||
        (["localhost","127.0.0.1"].includes(location.hostname)&&location.port!=="8000"?"http://127.0.0.1:8000":location.origin)).replace(/\/$/,"");
      const url=api+"/website/guide-cover?city="+encodeURIComponent(city)+"&v=local-photos-v6";
      const pending=(async()=>{
        if(required){
          try{return await fetchCover(new URL("assets/cities/"+key+".jpg",location.href).href,true);}
          catch(error){/* Same-origin API can supply the cropped local photograph instead. */}
        }
        const cover=await fetchCover(url);
        if(required&&cover.kind!=="photo")throw Error("Destination photograph unavailable");
        return cover;
      })().catch(()=>{coverCache.delete(city);return null;});
      coverCache.set(city,pending);
      if(coverCache.size>8)coverCache.delete(coverCache.keys().next().value);
    }
    return coverCache.get(city);
  }
  async function download(plan){
    if(!available()||!plan?.days?.length)throw new Error("Build a trip before exporting.");
    const cover=await prepareCover(plan.city);
    if(requiredPhotos.has(cityKey(plan.city))&&cover?.kind!=="photo")throw Error("Destination photograph unavailable");
    const pdf=new window.jspdf.jsPDF({orientation:"portrait",unit:"pt",format:"a4",compress:true});
    const W=pdf.internal.pageSize.getWidth(),H=pdf.internal.pageSize.getHeight(),M=38,CW=W-2*M,bottom=H-54;
    const days=plan.days,monthly=plan.monthly_forecasts||[],changed=new Set((plan.changes||[]).map(c=>String(c.date)));
    const byMonth=new Map(monthly.map(f=>[f.target_month,f]));
    let page=0,y=0;
    pdf.setProperties({title:"WanderClimate | "+plain(plan.city)+" travel guide",author:"WanderClimate"});
    function rect(x,t,w,h,color,r=0){pdf.setFillColor(color);if(r)pdf.roundedRect(x,t,w,h,r,r,"F");else pdf.rect(x,t,w,h,"F");}
    function font(size,bold=false){pdf.setFont("helvetica",bold?"bold":"normal");pdf.setFontSize(size);}
    function text(v,x,t,size=11,color=C.ink,bold=false){font(size,bold);pdf.setTextColor(color);pdf.text(plain(v),x,t+size);}
    function wrap(v,width,size=11,bold=false){font(size,bold);return pdf.splitTextToSize(plain(v),width);}
    function lines(v,x,t,width,size=11,color=C.ink,bold=false,leading=15){
      const rows=wrap(v,width,size,bold);rows.forEach((l,i)=>text(l,x,t+i*leading,size,color,bold));return rows.length*leading;
    }
    function circle(x,t,r,color){pdf.setFillColor(color);pdf.circle(x,t,r,"F");}
    function footer(){text("Check opening hours, local weather and travel times before you go.",M,H-39,8.5,C.muted);font(8.5);pdf.setTextColor(C.muted);pdf.text(String(page).padStart(2,"0"),W-M,H-29,{align:"right"});}
    function newPage(){
      if(page){footer();pdf.addPage();}
      page++;
      rect(0,0,W,H,C.paper);
      rect(0,0,W,page===1?174:87,C.ink);
      if(page===1&&cover){
        const iw=279.64;
        pdf.addImage(cover.data,"JPEG",W-iw,0,iw,174);
        rect(W-iw-3,0,3,174,C.gold);
        if(cover.kind==="illustration"){
          rect(W-iw+9,151,79,15,C.ink,4);
          text("CITY ILLUSTRATION",W-iw+14,154,6.5,C.white,true);
        }
      }else{
        circle(W-77,50,27,C.gold);
        if(page===1){pdf.setFillColor(C.green);pdf.triangle(W-205,174,W-110,78,W-38,174,"F");}
      }
      text("WANDERCLIMATE  /  YOUR TRAVEL GUIDE",M,23,9,C.pale,true);
      const title=page===1?"Discover "+plain(plan.city):plain(plan.city)+" | Your itinerary";
      let size=page===1?32:19;font(size,true);
      const titleWidth=page===1?W-280-M-12:CW-88;
      while(pdf.getTextWidth(title)>titleWidth&&size>10){size--;font(size,true);}
      text(title,M,43,size,C.white,true);
      if(page===1){
        lines(dateText(days[0].date)+" - "+dateText(days[days.length-1].date),M,94,titleWidth,11,C.white,false,15);
        const count=days.reduce((n,d)=>n+d.stops.length,0);
        text(days.length+(days.length===1?" day":" days")+"  /  "+count+" places to discover",M,132,10,C.pale);
        y=188;
      }else y=103;
    }
    function room(h){if(y+h>bottom)newPage();}
    newPage();
    y+=lines(monthly.length?"Early trip plan: monthly estimates, not daily weather. Rebuild within seven days of travel.":"Weather-aware plan: check the latest forecast before each day out.",M,y,CW,9.5,C.muted,false,13)+9;
    if(changed.size)y+=lines("Your itinerary was adjusted after a weather re-check.",M,y,CW,10,C.green,true,14)+8;
    for(const day of days){
      const stops=day.stops||[];
      const groups=["morning","afternoon"].map(slot=>[slot,stops.filter(s=>s.slot===slot)]);
      const extra=stops.filter(s=>!["morning","afternoon"].includes(s.slot));if(extra.length)groups.push(["explore",extra]);
      const monthKey=day.date.slice(0,7),forecast=byMonth.get(monthKey);
      const sideWidth=monthly.length?184:0,leftWidth=CW-sideWidth-(monthly.length?12:0),stopWidth=leftWidth-42;
      let sub=preference(day.day_type)+(changed.has(day.date)?" | Updated":"");
      if(!monthly.length)sub+=" | "+dailySummary(day.weather||{});
      const subH=wrap(sub,leftWidth-28,10).length*13;
      const rowsH=groups.filter(([,ss])=>ss.length).reduce((n,[,ss])=>n+14+ss.reduce((m,s)=>m+Math.max(1,wrap(s.name,stopWidth,11,true).length)*14+2,0),0);
      let h=40+subH+rowsH+(stops.length?0:wrap("Free time to explore at your own pace.",leftWidth-28,11).length*15+7)+10;
      let month,headlineParts,tip,sideW;
      if(monthly.length){
        month=dateText(monthKey+"-01",false,true);
        const [headline,clothing]=forecast?monthlySummary(forecast):["Monthly outlook unavailable","Check the weather closer to your trip."];
        headlineParts=headline.split(" | ");tip=clothing;sideW=sideWidth-24;
        const sideRows=headlineParts.reduce((n,p)=>n+wrap(p,sideW,12,true).length,0);
        h=Math.max(h,66+sideRows*15+wrap(tip,sideW,10).length*13);
      }
      room(h+11);
      const start=y;
      rect(M,start,CW,h,C.white,10);rect(M+12,start+12,35,25,C.green,6);
      text("DAY "+day.number,M+17,start+18,9,C.white,true);
      text(dateText(day.date,true),M+58,start+12,15,C.ink,true);
      if(monthly.length){
        const sx=M+CW-sideWidth-9;
        rect(sx,start+12,sideWidth,h-24,C.soft,8);
        text("WHAT TO EXPECT",sx+12,start+21,8.5,C.green,true);
        text(month.toUpperCase()+"  /  MONTHLY",sx+12,start+34,7.5,C.green,true);
        let sy=start+49;
        for(const part of headlineParts)sy+=lines(part,sx+12,sy,sideW,12,C.ink,true,15);
        lines(tip,sx+12,sy+5,sideW,10,C.muted,false,13);
      }
      y=start+38;y+=lines(sub,M+14,y,leftWidth-28,10,C.muted,false,13)+3;
      for(const [slot,ss] of groups){
        if(!ss.length)continue;
        text(slot.toUpperCase(),M+14,y,8.5,C.green,true);y+=14;
        for(const stop of ss){
          circle(M+19,y+7,3,C.gold);
          const n=lines(stop.name,M+30,y,stopWidth,11,C.ink,true,14);
          if(finite(stop.lat)&&finite(stop.lon))pdf.link(M+28,y,leftWidth-38,n,{url:"https://www.google.com/maps/search/?api=1&query="+stop.lat+","+stop.lon});
          y+=n+2;
        }
      }
      if(!stops.length)y+=lines("Free time to explore at your own pace.",M+14,y,leftWidth-28,11,C.muted,false,15);
      y=start+h+11;
    }
    room(29);
    const linkNote=days.some(d=>d.stops.some(s=>finite(s.lat)&&finite(s.lon)))?"Tap a place name to open it on the map. ":"";
    lines(linkNote+"Visit order is a guide, not turn-by-turn directions.",M,y,CW,9,C.muted,false,13);
    footer();
    const slug=plain(plan.city).replace(/[^a-z0-9_-]+/gi,"-").replace(/^-|-$/g,"").slice(0,65)||"Trip";
    pdf.save("WanderClimate-"+slug+"-Travel-Guide.pdf");
  }
  window.WanderClimatePDF={available,download,prepareCover};
})();
