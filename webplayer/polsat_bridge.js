/* Official Polsat page controls; no licence handling, ad removal or auth export. */
(() => {
  if(location.origin!=='https://polsatboxgo.pl')return;
  const settings=__SETTINGS__,send=value=>window.tvp_bridge.postMessage(JSON.stringify(value));
  const audio=window.__tvpAudioGain || {set:(video,value)=>video.volume=Math.max(0,Math.min(1,Number(value)/100)),get:video=>video.volume*100};
  let current=null,loaded=false,lastTracks='',lastTime=-1,lastPause=null,noticeAt=0,profileMissingAt=0,autoStartAttempts=0,autoStartAt=0,autoStartFailed=false;
  let audioSwitch=Promise.resolve();
  let resumeAttempts=0,resumeClickedAt=0,watchAttempts=0,watchClickedAt=0,playerMissingReported=false,vodPositionDone=false;
  const requestedStart=Number(settings.polsatStart)||0;
  const liveStartup=location.pathname?.startsWith('/kanaly-tv/')&&!requestedStart;
  let lastStartupTime=null, progressingTicks=0, userPaused=false;
  let livePlayClicked=false;
  let consentVisible=false, consentClosedAt=0;
  let startDone=!requestedStart,startClicked=false,startFailed=false,startAt=0,startAttempts=0,startStable=0,startLast=-1;
  let desiredVolume=Math.max(0,Math.min(200,Number(settings.volume)||0));
  const requestedAt=Date.now(),timelineOrigin=Number(settings.polsatOrigin)||0;
  const startTarget=requestedStart-timelineOrigin;
  const restoreVolume=v=>{audio.set(v,desiredVolume);if(typeof setTimeout==='function')setTimeout(()=>{if(v===current)audio.set(v,desiredVolume);},300);};
  const resume=async v=>{await v.play();restoreVolume(v);};
  document.addEventListener?.('play',event=>{if(event.target?.tagName==='VIDEO'){if(window.__tvpPolsatEnded){event.target.pause();return;}restoreVolume(event.target);if(requestedStart&&!startDone)event.target.muted=true;}},true);
  const video=()=>[...document.querySelectorAll('video')].filter(v=>v.readyState>=1&&v.getBoundingClientRect().width>100).sort((a,b)=>b.getBoundingClientRect().width-a.getBoundingClientRect().width)[0];
  const profileOkay=()=>{
    const cookie=document.cookie.split(';').map(v=>v.trim()).find(v=>v.startsWith('profile-id='));
    try{return !!window.__tvpPolsatProfile&&decodeURIComponent(cookie?.slice('profile-id='.length)||'').replace(/^"|"$/g,'')===window.__tvpPolsatProfile;}catch(_){return false;}
  };
  // Navigation Timing is relative to this document and starts again on reload.
  const timing=liveStartup&&window.performance;
  const seenStages=new Set();
  function stage(name){
    if(!timing||seenStages.has(name))return;
    seenStages.add(name);
    const navigation=timing.getEntriesByType('navigation')[0];
    const kind=navigation?.type==='reload'?'przeładowanie':'otwarcie';
    send({event:'player-diagnostic',message:'Polsat LIVE ['+kind+' +'+Math.round(timing.now())+' ms]: '+name});
  }
  let observedSDK=null;
  function observeSDK(sdk){
    if(!sdk||sdk===observedSDK)return;
    observedSDK=sdk;
    stage('utworzono SDK');
    try{
      const ready=sdk.ready;
      if(typeof ready?.then!=='function'){stage('SDK bez sygnału ready');return;}
      stage('oczekiwanie na ready SDK');
      ready.then(()=>{if(observedSDK===sdk)stage('SDK zgłosił gotowość');},
                 ()=>{if(observedSDK===sdk)stage('SDK odrzucił gotowość');});
    }catch(_){stage('sygnał ready niedostępny');}
  }
  function startupSummary(outcome){
    if(!timing)return;
    let state='niedostępny',http='odczyt niedostępny';
    try{
      const rawState=window.__tvpPolsatSDK?.getStatus?.()?.state;
      if(typeof rawState==='string'&&/^[A-Z_]{2,32}$/.test(rawState))state=rawState;
    }catch(_){/* Some SDK instances cannot report a state before ready. */}
    try{
      const statuses=timing.getEntriesByType('resource').map(entry=>entry.responseStatus)
        .filter(code=>Number.isInteger(code)&&code>=100&&code<=599);
      const errors=[...new Set(statuses.filter(code=>code>=400))].sort();
      http=errors.join(',')||(statuses.length?'brak w dostępnych odpowiedziach':'brak widocznych statusów');
    }catch(_){/* Resource Timing may be unavailable independently of the SDK. */}
    stage(outcome+'; stan SDK='+state+', widoczne błędy HTTP='+http);
  }
  if(timing){
    document.addEventListener('DOMContentLoaded',()=>stage('DOM gotowy'),{once:true});
    window.addEventListener('load',()=>stage('strona załadowana'),{once:true});
    stage('inicjalizacja dokumentu');
    if(window.__tvpPolsatReloadDecision)stage(window.__tvpPolsatReloadDecision);
  }
  const bounds=v=>{
    if(Number.isFinite(v.duration)&&v.duration<10000000)return [0,v.duration];
    if(v.seekable?.length){const a=v.seekable.start(0),b=v.seekable.end(v.seekable.length-1);if(Number.isFinite(a)&&Number.isFinite(b)&&b-a<172800)return [a,b];}
    return null;
  };
  const sdkAudio=()=>Array.isArray(window.__tvpPolsatAudio)?window.__tvpPolsatAudio:[];
  const tracks=v=>sdkAudio().length?sdkAudio().map((a,i)=>({type:'audio',id:i+1,title:a.label||a.value?.label||a.value?.lang||('Ścieżka '+(i+1)),selected:a.value?.active===true})):Array.from(v.audioTracks||[]).map((a,i)=>({type:'audio',id:i+1,title:a.label||a.language||('Ścieżka '+(i+1)),selected:!!a.enabled}));
  window.addEventListener('keydown',event=>{
    if(event.target?.closest('input,textarea,[contenteditable="true"]'))return;
    const key=event.key.toLowerCase();
    const action=key==='f6'?'focus-controls':event.ctrlKey&&!event.altKey?(event.shiftKey?{arrowup:'volume-up',arrowdown:'volume-down'}[key]:{' ':'pause',p:'focus-player',t:'time',arrowleft:'back',arrowright:'forward',arrowup:'step-up',arrowdown:'step-down','1':'audio-1','2':'audio-2','3':'audio-3'}[key]):null;
    if(action){event.preventDefault();event.stopImmediatePropagation();send({event:'addon-command',action});}
  },true);
  window.__tvpCommand=async packet=>{
    const v=video(),c=packet.command||[];
    if(!v||!profileOkay()){
      if(c[0]==='get_property' && packet.request_id)send({request_id:packet.request_id,error:'unavailable',data:null});
      return;
    }
    try{
      const range=bounds(v);
      if(liveStartup&&c[0]==='cycle'&&c[1]==='pause')userPaused=!v.paused;
      if(liveStartup&&c[0]==='set_property'&&c[1]==='pause')userPaused=Boolean(c[2]);
      if(c[0]==='cycle'&&c[1]==='pause'){if(v.paused)await resume(v);else v.pause();}
      else if(c[0]==='set_property'){
        if(c[1]==='pause'){if(c[2])v.pause();else await resume(v);}
        else if(c[1]==='volume'){desiredVolume=Math.max(0,Math.min(200,Number(c[2])||0));audio.set(v,desiredVolume);}
        else if(c[1]==='aid'){
          const sdk=sdkAudio(),index=Number(c[2])-1;
          if(sdk.length){
            if(!sdk[index]||!window.__tvpPolsatSDK?.user?.setPlaybackOptions)throw new Error();
            audioSwitch=audioSwitch.catch(()=>{}).then(async()=>{
              await window.__tvpPolsatSDK.user.setPlaybackOptions({audio:sdk[index].value});
              for(let n=0;n<25;n++){if(sdkAudio()[index]?.value?.active===true)return;await new Promise(r=>setTimeout(r,100));}
              throw new Error('Audio not confirmed');
            });
            await audioSwitch;return;
          }
          const all=Array.from(v.audioTracks||[]);
          if(!all[index])throw new Error();
          all.forEach((a,i)=>{a.enabled=i===index;});
          if(!all[index].enabled)throw new Error();
        }
      }else if(c[0]==='seek'){
        if(!range)throw new Error();
        const target=c[2]==='absolute'?range[0]+Number(c[1]):v.currentTime+Number(c[1]);
        v.currentTime=Math.max(range[0],Math.min(range[1],target));
      }else if(c[0]==='get_property'){
        if(c[1]==='aid')await audioSwitch.catch(()=>{});
        const value=c[1]==='time-pos'&&range?Math.max(0,v.currentTime-range[0]):c[1]==='duration'&&range?range[1]-range[0]:c[1]==='volume'?audio.get(v):c[1]==='aid'?tracks(v).find(a=>a.selected)?.id:null;
        send({request_id:packet.request_id,error:value==null?'unsupported':'success',data:value});
      }
    }catch(_){send({event:'player-notice',message:'Polsat Box Go nie potwierdził wykonania polecenia. Funkcja może być niedostępna w tym materiale.'});}
  };
  setInterval(()=>{
    if(liveStartup){
      if(timing&&!loaded){
        if(profileOkay())stage('zgodny profil');
        observeSDK(window.__tvpPolsatSDK);
        if(document.querySelector('video'))stage('element wideo w dokumencie');
      }
      const visibleConsent=[...document.querySelectorAll('button,[role="button"]')].some(button=>
        button.innerText?.trim().toLocaleLowerCase('pl')==='odrzuć wszystko'&&button.getBoundingClientRect().width>0);
      if(visibleConsent){
        if(!consentVisible)send({event:'player-notice',message:'Polsat wyświetlił wybór dotyczący cookies. Wybierz Pokaż obraz i przejdź Tabem do opcji na stronie. Po dokonaniu wyboru kanał spróbuje wystartować.'});
        consentVisible=true;
        return;
      }
      if(consentVisible){
        consentVisible=false;consentClosedAt=Date.now();loaded=false;
        progressingTicks=0;lastStartupTime=null;autoStartAttempts=0;autoStartFailed=false;
      }
    }
    const startupAt=consentClosedAt||requestedAt;
    // The official VOD page may wait for a resume/start-over choice before creating its SDK.
    // These two exact buttons only control our requested material, never consent or purchase.
    if(!liveStartup&&!requestedStart&&!window.__tvpPolsatEnded&&profileOkay()&&resumeAttempts<2&&Date.now()-requestedAt<45000&&Date.now()-resumeClickedAt>1500){
      const wanted=Number(settings.start)>0?'oglądaj dalej':'oglądaj od początku';
      const button=[...document.querySelectorAll('button,a,[role=button],div')].find(b=>b.innerText?.trim().toLocaleLowerCase('pl')===wanted&&b.getBoundingClientRect().width>0);
      if(button){resumeAttempts++;resumeClickedAt=Date.now();button.click();}
    }
    const v=video();
    if(liveStartup&&!loaded&&!settings.pause&&!userPaused&&!livePlayClicked&&profileOkay()&&
       window.__tvpPolsatSDK&&(!v||v.paused||progressingTicks===0)){
      const controls=document.querySelectorAll('[aria-label],[title],button,[role="button"],[tabindex],div,span');
      const play=[...controls].find(el=>{
        const name=el.getAttribute?.('aria-label')||el.getAttribute?.('title')||(!el.childElementCount&&el.textContent);
        return name?.trim?.().toLocaleLowerCase('pl')==='odtwarzaj'&&el.getBoundingClientRect().width>0;
      });
      if(play){
        livePlayClicked=true;
        stage('dostępne Odtwarzaj');
        play.click();
        send({event:'player-diagnostic',message:'Polsat LIVE: wybrano Odtwarzaj na stronie kanału.'});
        return;
      }
    }
    if(!v){
      if(liveStartup&&!loaded&&!settings.pause&&!playerMissingReported&&!userPaused&&profileOkay()&&Date.now()-startupAt>15000&&
         document.readyState==='complete'&&document.querySelector('[role="alert"]')&&
         (!window.__tvpPolsatSDK||Date.now()-startupAt>20000)&&!document.querySelector('video')&&
         !(document.body?.innerText||'').replace(/przejdź do (treści|stopki)|[\uFFFC\u200B]/gi,'').trim()&&
         ![...document.querySelectorAll('button,input,select,textarea,[role="button"],[role="dialog"],a[href]')].some(el=>
           el.getClientRects().length&&!(el.tagName==='A'&&el.pathname===location.pathname&&el.hash))){
        playerMissingReported=true;
        startupSummary('pusta strona');
        send({event:'player-error',code:'polsat-live-empty-page',message:'Strona kanału Polsat Box Go pozostała pusta.'});
        return;
      }
      // This is the ordinary playback action, never purchase, privacy or consent.
      if(!requestedStart&&!window.__tvpPolsatEnded&&profileOkay()&&watchAttempts<2&&Date.now()-startupAt<45000&&Date.now()-watchClickedAt>1500){
        const watch=[...document.querySelectorAll('button,a,[role=button]')].find(button=>['oglądaj','oglądaj na żywo'].includes(button.innerText?.trim().toLocaleLowerCase('pl'))&&button.getBoundingClientRect().width>0);
        if(watch){watchAttempts++;watchClickedAt=Date.now();watch.click();}
      }
      if(requestedStart&&!startFailed&&Date.now()-requestedAt>45000){startFailed=true;send({event:'player-error',message:'Nie uruchomiono początku audycji Polsat Box Go. Wybierz Na żywo lub spróbuj ponownie.'});}
      else if(!playerMissingReported&&Date.now()-startupAt>45000){playerMissingReported=true;
        if(liveStartup)send({event:'player-diagnostic',message:'Polsat LIVE po 45 s: dokument='+document.readyState+', profil='+profileOkay()+', SDK='+Boolean(window.__tvpPolsatSDK)+', elementy wideo='+document.querySelectorAll('video').length+', alerty='+document.querySelectorAll('[role="alert"]').length+'.'});
        send({event:'player-error',message:'Polsat Box Go nie uruchomił odtwarzacza. Wybierz Pokaż obraz, aby sprawdzić logowanie, profil lub komunikat strony.'});}
      return;
    }
    if(window.__tvpPolsatEnded){v.pause();return;}
    if(!profileOkay()){
      if(!profileMissingAt)profileMissingAt=Date.now();
      if(Date.now()-profileMissingAt<10000)return;
      v.pause();if(Date.now()-noticeAt>10000){noticeAt=Date.now();send({event:'player-error',message:'Profil odtwarzacza nie odpowiada profilowi wybranemu we wtyczce. Zatrzymano odtwarzanie. Wybierz ponownie profil Polsat Box Go.'});}return;
    }
    profileMissingAt=0;
    if(v!==current){
      progressingTicks=0;lastStartupTime=null;
      current=v;loaded=false;lastTracks='';lastTime=-1;lastPause=null;autoStartAttempts=0;autoStartAt=0;autoStartFailed=false;restoreVolume(v);
    }
    // The service can silently resume an old position even after a new episode opens.
    // Touch the requested position once, only when its SDK confirms main content (never ads/live).
    if(!requestedStart&&!vodPositionDone&&location.pathname?.startsWith('/wideo/')){
      const state=window.__tvpPolsatSDK?.getStatus?.()?.state;
      if((state==='PLAYING_CONTENT'||state==='PAUSED_CONTENT')&&Number.isFinite(v.duration)&&v.duration>0&&!v.seeking){
        const target=Math.max(0,Math.min(v.duration,Number(settings.start)||0));
        if(Math.abs(v.currentTime-target)>1)v.currentTime=target;
        vodPositionDone=true;
      }
    }
    if(!startDone){
      v.muted=true;
      if(startFailed){v.pause();return;}
      const range=bounds(v),now=Date.now();
      if(!timelineOrigin||!Number.isFinite(startTarget)||startTarget<0){
        startFailed=true;v.pause();send({event:'player-error',message:'Brak potwierdzonej osi czasu Polsatu. Nie uruchomiono początku audycji.'});return;
      }
      if(range&&startTarget>=range[0]&&startTarget<=range[1]){
        if(!startClicked||startAttempts<2&&now-startAt>3000&&Math.abs(v.currentTime-startTarget)>((now-startAt)/1000+3)){
          startClicked=true;startAt=now;startAttempts++;startStable=0;startLast=-1;v.currentTime=startTarget;
        }else if(startClicked){
          const elapsed=(now-startAt)/1000,offset=v.currentTime-startTarget;
          const correct=!v.seeking&&v.readyState>=2&&!v.paused&&offset>=-.5&&offset<=elapsed+1.5;
          startStable=correct&&v.currentTime>startLast?startStable+1:0;startLast=v.currentTime;
          if(startStable>=3&&offset>.2){
            startDone=true;restoreVolume(v);v.muted=false;
            send({event:'player-notice',message:'Polsat Box Go: potwierdzono początek audycji i dalsze odtwarzanie.'});
          }
        }
      }
      if(!startDone&&(now-requestedAt>45000||startClicked&&now-startAt>15000)){
        startFailed=true;v.pause();send({event:'player-error',message:'Polsat Box Go nie potwierdził początku audycji. Zatrzymano odtwarzanie. Możesz wybrać Na żywo.'});
      }
      if(!startDone)return;
    }
    if(!loaded&&!settings.pause&&!userPaused&&v.paused&&autoStartAttempts<6&&Date.now()-autoStartAt>1500){
      autoStartAttempts++;autoStartAt=Date.now();resume(v).catch(()=>{});
    }
    if(!loaded){
      if(liveStartup){
        const delta=v.currentTime-lastStartupTime;
        progressingTicks=!v.paused&&!v.seeking&&v.readyState>=2&&lastStartupTime!==null&&delta>0&&delta<4?progressingTicks+1:0;
        lastStartupTime=v.currentTime;
      }
      if(!v.paused&&(!liveStartup||progressingTicks>=2)){loaded=true;startupSummary('potwierdzony postęp odtwarzania');send({event:'file-loaded'});}
    }
    if(!loaded&&!autoStartFailed&&Date.now()-startupAt>45000){
      autoStartFailed=true;send({event:'player-error',message:'Polsat Box Go utworzył odtwarzacz, ale nie rozpoczął materiału automatycznie. Wybierz Pokaż obraz, aby sprawdzić komunikat strony.'});
    }
    if(!loaded)return;
    const all=tracks(v),serialized=JSON.stringify(all);
    if(serialized!==lastTracks){lastTracks=serialized;send({event:'property-change',name:'track-list',data:all});}
    const range=bounds(v);
    if(range){const position=Math.max(0,v.currentTime-range[0]);if(Math.floor(position)!==lastTime){lastTime=Math.floor(position);send({event:'property-change',name:'time-pos',data:position});send({event:'property-change',name:'duration',data:range[1]-range[0]});}}
    if(lastPause!==v.paused){lastPause=v.paused;send({event:'property-change',name:'pause',data:v.paused});}
    send({event:'property-change',name:'volume',data:audio.get(v)});
  },500);
})();
