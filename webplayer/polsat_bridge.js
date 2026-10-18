/* Official Polsat page controls; no licence handling, ad removal or auth export. */
(() => {
  if(location.origin!=='https://polsatboxgo.pl')return;
  const settings=__SETTINGS__,send=value=>window.tvp_bridge.postMessage(JSON.stringify(value));
  let current=null,loaded=false,lastTracks='',lastTime=-1,lastPause=null,noticeAt=0;
  let audioSwitch=Promise.resolve();
  const requestedStart=Number(settings.polsatStart)||0;
  let startDone=!requestedStart,startClicked=false,startFailed=false,startAt=0,startAttempts=0,startStable=0,startLast=-1;
  let desiredVolume=Math.max(0,Math.min(1,Number(settings.volume)/100));
  const requestedAt=Date.now(),timelineOrigin=Number(settings.polsatOrigin)||0;
  const startTarget=requestedStart-timelineOrigin;
  const restoreVolume=v=>{v.volume=desiredVolume;if(typeof setTimeout==='function')setTimeout(()=>{if(v===current)v.volume=desiredVolume;},300);};
  const resume=async v=>{await v.play();restoreVolume(v);};
  document.addEventListener?.('play',event=>{if(event.target?.tagName==='VIDEO'){restoreVolume(event.target);if(requestedStart&&!startDone)event.target.muted=true;}},true);
  const video=()=>[...document.querySelectorAll('video')].filter(v=>v.readyState>=1&&v.getBoundingClientRect().width>100).sort((a,b)=>b.getBoundingClientRect().width-a.getBoundingClientRect().width)[0];
  const profileOkay=()=>{
    const cookie=document.cookie.split(';').map(v=>v.trim()).find(v=>v.startsWith('profile-id='));
    try{return !!window.__tvpPolsatProfile&&decodeURIComponent(cookie?.slice('profile-id='.length)||'').replace(/^"|"$/g,'')===window.__tvpPolsatProfile;}catch(_){return false;}
  };
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
    if(!v||!profileOkay()){send({event:'player-notice',message:'Brak gotowego odtwarzacza lub potwierdzonego profilu Polsat Box Go.'});return;}
    try{
      const range=bounds(v);
      if(c[0]==='cycle'&&c[1]==='pause'){if(v.paused)await resume(v);else v.pause();}
      else if(c[0]==='set_property'){
        if(c[1]==='pause'){if(c[2])v.pause();else await resume(v);}
        else if(c[1]==='volume'){desiredVolume=Math.max(0,Math.min(1,Number(c[2])/100));v.volume=desiredVolume;}
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
        const value=c[1]==='time-pos'&&range?Math.max(0,v.currentTime-range[0]):c[1]==='duration'&&range?range[1]-range[0]:c[1]==='volume'?v.volume*100:c[1]==='aid'?tracks(v).find(a=>a.selected)?.id:null;
        send({request_id:packet.request_id,error:value==null?'unsupported':'success',data:value});
      }
    }catch(_){send({event:'player-notice',message:'Polsat Box Go nie potwierdził wykonania polecenia. Funkcja może być niedostępna w tym materiale.'});}
  };
  setInterval(()=>{
    const v=video();if(!v){if(requestedStart&&!startFailed&&Date.now()-requestedAt>45000){startFailed=true;send({event:'player-error',message:'Nie uruchomiono początku audycji Polsat Box Go. Wybierz Na żywo lub spróbuj ponownie.'});}return;}
    if(!profileOkay()){
      v.pause();if(Date.now()-noticeAt>10000){noticeAt=Date.now();send({event:'player-error',message:'Profil odtwarzacza nie odpowiada profilowi wybranemu we wtyczce. Zatrzymano odtwarzanie. Wybierz ponownie profil Polsat Box Go.'});}return;
    }
    if(v!==current){current=v;loaded=false;lastTracks='';lastTime=-1;lastPause=null;v.volume=desiredVolume;}
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
            startDone=true;v.volume=desiredVolume;v.muted=false;
            send({event:'player-notice',message:'Polsat Box Go: potwierdzono początek audycji i dalsze odtwarzanie.'});
          }
        }
      }
      if(!startDone&&(now-requestedAt>45000||startClicked&&now-startAt>15000)){
        startFailed=true;v.pause();send({event:'player-error',message:'Polsat Box Go nie potwierdził początku audycji. Zatrzymano odtwarzanie. Możesz wybrać Na żywo.'});
      }
      if(!startDone)return;
    }
    if(!loaded&&!v.paused){loaded=true;send({event:'file-loaded'});}
    if(!loaded)return;
    const all=tracks(v),serialized=JSON.stringify(all);
    if(serialized!==lastTracks){lastTracks=serialized;send({event:'property-change',name:'track-list',data:all});}
    const range=bounds(v);
    if(range){const position=Math.max(0,v.currentTime-range[0]);if(Math.floor(position)!==lastTime){lastTime=Math.floor(position);send({event:'property-change',name:'time-pos',data:position});send({event:'property-change',name:'duration',data:range[1]-range[0]});}}
    if(lastPause!==v.paused){lastPause=v.paused;send({event:'property-change',name:'pause',data:v.paused});}
    send({event:'property-change',name:'volume',data:v.volume*100});
  },500);
})();
