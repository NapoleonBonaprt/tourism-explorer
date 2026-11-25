/* Shared travel-date calendar for city and dashboard pages. */
(() => {
  "use strict";
  const MONTHS=["January","February","March","April","May","June","July","August","September","October","November","December"];
  // One shared, dependency-free calendar; the native date input remains the
  // form's source of truth and still supports keyboard editing/validation.
  function enhanceDatePicker(input) {
    if(input.dataset.calendarReady || !input.min || !input.max) return;
    input.dataset.calendarReady="true";
    const label=document.querySelector('label[for="'+input.id+'"]')?.textContent||"Travel date";
    const icon='<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 10h18m-12 4h2m3 0h2"/></svg>';
    const chevron='<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m7 10 5 5 5-5"/></svg>';
    const wrap=document.createElement("div");
    wrap.className="wc-date-field";
    input.before(wrap);
    wrap.append(input);
    const trigger=document.createElement("button");
    trigger.type="button";
    trigger.className="wc-date-trigger";
    trigger.setAttribute("aria-label","Choose "+label.toLowerCase());
    trigger.setAttribute("aria-haspopup","dialog");
    trigger.setAttribute("aria-expanded","false");
    trigger.setAttribute("aria-controls",input.id+"Calendar");
    trigger.innerHTML=icon+chevron;
    wrap.append(trigger);
    const pop=document.createElement("div");
    pop.className="wc-calendar";
    pop.id=input.id+"Calendar";
    pop.hidden=true;
    pop.setAttribute("role","dialog");
    pop.setAttribute("aria-label","Choose "+label.toLowerCase());
    pop.innerHTML='<div class="wc-cal-heading"><div><span class="wc-cal-kicker">TRAVEL DATE</span><strong>Choose your date</strong></div><button type="button" class="wc-cal-close" aria-label="Close calendar">&times;</button></div>'+
      '<div class="wc-cal-nav"><button type="button" class="wc-cal-prev" aria-label="Previous month"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 6-6 6 6 6"/></svg></button>'+
      '<select class="wc-cal-month" aria-label="Month"></select><select class="wc-cal-year" aria-label="Year"></select>'+
      '<button type="button" class="wc-cal-next" aria-label="Next month"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></button></div>'+
      '<div class="wc-cal-week" aria-hidden="true">'+["Mo","Tu","We","Th","Fr","Sa","Su"].map(d=>"<span>"+d+"</span>").join("")+'</div>'+
      '<div class="wc-cal-days" role="group" aria-label="Days of the month"></div>'+
      '<div class="wc-cal-footer"><button type="button" class="wc-cal-today">Today</button><span>Choose any available day</span></div>';
    document.body.append(pop);
    const q=s=>pop.querySelector(s);
    const month=q(".wc-cal-month"),year=q(".wc-cal-year"),grid=q(".wc-cal-days");
    const prev=q(".wc-cal-prev"),next=q(".wc-cal-next"),todayButton=q(".wc-cal-today");
    const fromISO=s=>new Date(s+"T00:00:00Z");
    const iso=d=>d.toISOString().slice(0,10);
    const localToday=()=>{const d=new Date();return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,10);};
    const first=d=>new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth(),1));
    const shift=(d,n)=>new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+n,1));
    const plusDays=(d,n)=>new Date(d.getTime()+n*86400000);
    const clamp=s=>s<input.min?input.min:s>input.max?input.max:s;
    const allowed=s=>s>=input.min&&s<=input.max;
    let view=first(fromISO(clamp(input.value||localToday())));
    let focusDate=input.value||localToday();
    const minMonth=()=>first(fromISO(input.min));
    const maxMonth=()=>first(fromISO(input.max));
    function position(){
      if(pop.hidden)return;
      const r=wrap.getBoundingClientRect();
      const width=Math.min(340,window.innerWidth-24);
      pop.style.width=width+"px";
      pop.style.left=Math.max(12,Math.min(r.left,window.innerWidth-width-12))+"px";
      const h=pop.offsetHeight;
      const below=window.innerHeight-r.bottom-12,above=r.top-12;
      const top=below>=h||below>=above?r.bottom+8:r.top-h-8;
      pop.style.top=Math.max(8,Math.min(top,window.innerHeight-h-8))+"px";
    }
    function render(focus=false){
      if(view<minMonth())view=minMonth();
      if(view>maxMonth())view=maxMonth();
      const y=view.getUTCFullYear(),m=view.getUTCMonth();
      const minY=minMonth().getUTCFullYear(),maxY=maxMonth().getUTCFullYear();
      year.replaceChildren(...Array.from({length:maxY-minY+1},(_,i)=>new Option(String(minY+i),String(minY+i),false,minY+i===y)));
      month.replaceChildren(...MONTHS.map((name,i)=>{
        const o=new Option(name,String(i),false,i===m),v=new Date(Date.UTC(y,i,1));
        o.disabled=v<minMonth()||v>maxMonth();return o;
      }));
      prev.disabled=view<=minMonth();next.disabled=view>=maxMonth();
      grid.replaceChildren();
      const blanks=(view.getUTCDay()+6)%7;
      for(let i=0;i<blanks;i++){const spacer=document.createElement("span");spacer.setAttribute("aria-hidden","true");grid.append(spacer);}
      const count=new Date(Date.UTC(y,m+1,0)).getUTCDate();
      const today=localToday();
      const focusInMonth=focusDate.slice(0,7)===iso(view).slice(0,7)&&allowed(focusDate);
      const defaultFocus=focusInMonth?focusDate:clamp(iso(view));
      for(let n=1;n<=count;n++){
        const d=new Date(Date.UTC(y,m,n)),key=iso(d),button=document.createElement("button");
        button.type="button";button.className="wc-cal-day";button.dataset.date=key;
        button.textContent=n;button.disabled=!allowed(key);
        button.setAttribute("aria-label",d.toLocaleDateString("en-GB",{day:"numeric",month:"long",year:"numeric",timeZone:"UTC"}));
        button.setAttribute("aria-pressed",String(key===input.value));
        if(key===today)button.setAttribute("aria-current","date");
        button.tabIndex=key===defaultFocus&&!button.disabled?0:-1;
        button.addEventListener("click",()=>choose(key));
        grid.append(button);
      }
      todayButton.disabled=!allowed(today);
      position();
      if(focus){(grid.querySelector('button[tabindex="0"]:not(:disabled)')||grid.querySelector("button:not(:disabled)")||month).focus({preventScroll:true});}
    }
    function close(restore=false){
      if(pop.hidden)return;
      pop.hidden=true;trigger.setAttribute("aria-expanded","false");
      if(restore)trigger.focus({preventScroll:true});
    }
    function open(){
      if(input.disabled||!input.min||!input.max)return;
      focusDate=clamp(input.value||localToday());view=first(fromISO(focusDate));
      pop.hidden=false;trigger.setAttribute("aria-expanded","true");render(true);
    }
    function choose(key){
      if(!allowed(key))return;
      const old=input.value;input.value=key;close(true);
      if(old!==key){
        input.dispatchEvent(new Event("input",{bubbles:true}));
        input.dispatchEvent(new Event("change",{bubbles:true}));
      }
    }
    trigger.addEventListener("click",()=>pop.hidden?open():close(true));
    // Clicking the date itself opens the same styled calendar as the icon.
    // Keyboard entry into the native field remains available.
    input.addEventListener("pointerdown",e=>{if(e.button===0&&!input.disabled){e.preventDefault();open();}});
    input.addEventListener("keydown",e=>{if((e.altKey&&e.key==="ArrowDown")||e.key==="F4"){e.preventDefault();open();}});
    input.addEventListener("change",()=>{if(!pop.hidden)close();});
    q(".wc-cal-close").addEventListener("click",()=>close(true));
    prev.addEventListener("click",()=>{view=shift(view,-1);focusDate=clamp(iso(view));render();});
    next.addEventListener("click",()=>{view=shift(view,1);focusDate=clamp(iso(view));render();});
    month.addEventListener("change",()=>{view=new Date(Date.UTC(+year.value,+month.value,1));focusDate=clamp(iso(view));render();});
    year.addEventListener("change",()=>{
      view=new Date(Date.UTC(+year.value,+month.value,1));
      if(view<minMonth())view=minMonth();if(view>maxMonth())view=maxMonth();
      focusDate=clamp(iso(view));render();
    });
    todayButton.addEventListener("click",()=>choose(localToday()));
    pop.addEventListener("keydown",e=>{
      if(e.key==="Escape"){e.preventDefault();close(true);return;}
      const key=e.target.dataset?.date;
      if(!key)return;
      const d=fromISO(key),weekday=(d.getUTCDay()+6)%7;
      const delta={ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7,Home:-weekday,End:6-weekday}[e.key];
      if(delta===undefined)return;
      e.preventDefault();focusDate=clamp(iso(plusDays(d,delta)));view=first(fromISO(focusDate));render(true);
    });
    document.addEventListener("pointerdown",e=>{if(!pop.hidden&&!pop.contains(e.target)&&!wrap.contains(e.target))close();});
    document.addEventListener("focusin",e=>{if(!pop.hidden&&!pop.contains(e.target)&&!wrap.contains(e.target))close();});
    window.addEventListener("resize",position);
    window.addEventListener("scroll",position,{passive:true});
  }

  window.WanderClimateCalendar={enhance:enhanceDatePicker};
})();
