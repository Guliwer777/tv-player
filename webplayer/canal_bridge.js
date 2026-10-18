/* Initial CANAL+ bridge: official client handles login, entitlement and DRM.
   Never reads credentials, cookies, network responses, or licence data. */
(() => {
  if (location.origin !== 'https://www.canalplus.com') return;
  const send=p=>window.tvp_bridge.postMessage(JSON.stringify(p));
  let current=null,loaded=false,lastTime=-1,lastPause=null,lastTracks='',audioSwitch=Promise.resolve(),restartCheck=0;
  const official=()=>window.__tvpCanalPlayer;
  const languages=()=>{try{return official()?.getAvailableLanguages()||[];}catch(_){return [];}};
  const selected=()=>{try{const now=official()?.getCurrentLanguage();return languages().findIndex(a=>a.id===now?.id)+1;}catch(_){return 0;}};
  const video=()=>{
    const items=[...document.querySelectorAll('video')].filter(v=>v.readyState>=1 && !v.muted && v.getBoundingClientRect().width>100);
    return items.find(v=>!v.paused)||items[0]||null;
  };
  const live=v=>location.hash?.startsWith('#tvp-player-channel=') || !Number.isFinite(v.duration) || v.duration>10000000;
  const timing=v=>{
    if(!live(v)||!official())return null;
    try{
      const current=official().getCurrentTime(),start=official().getStartTime(),end=official().getLiveTime();
      if([current,start,end].some(d=>typeof d?.getTime!=='function'||!Number.isFinite(d.getTime())))return null;
      return {position:Math.max(0,(current.getTime()-start.getTime())/1000),duration:Math.max(0,(end.getTime()-start.getTime())/1000)};
    }catch(_){return null;}
  };
  const base=v=>{const t=timing(v);return t?v.currentTime-t.position:!live(v)?0:(v.seekable.length?v.seekable.start(0):0);};
  const length=v=>{const t=timing(v);return t?t.duration:!live(v)?v.duration:(v.seekable.length?Math.max(0,v.seekable.end(v.seekable.length-1)-base(v)):0);};
  const editable=e=>e.target?.closest('input,textarea,[contenteditable="true"]');
  window.addEventListener('keydown',e=>{
    if(editable(e))return;
    let action=e.key==='F6'?'focus-controls':null;
    if(e.ctrlKey && !e.altKey)action=e.shiftKey?({ArrowUp:'volume-up',ArrowDown:'volume-down'}[e.key]):({' ':'pause',p:'focus-player',t:'time',ArrowLeft:'back',ArrowRight:'forward',ArrowUp:'step-up',ArrowDown:'step-down'}[e.key]);
    if(action){e.preventDefault();e.stopImmediatePropagation();send({event:'addon-command',action});}
  },true);
  function notice(message){send({event:'player-notice',message});}
  window.__tvpCommand=async packet=>{
    const v=video(),c=packet.command||[];
    if(!v){notice('CANAL+: zaloguj się i wybierz Oglądaj w oficjalnym oknie. Nie wykryto aktywnego materiału.');return;}
    try {
      if(c[0]==='replay-probe'){
        const target=Number(c[1]),p=official();
        if(!Number.isFinite(target)||target<=0||!p?.seekTo){send({event:'replay-probe',target,available:false});return;}
        p.seekTo(new Date(target*1000));
        let checks=0;
        const verify=()=>{
          let offset=null,program=null;
          try{offset=(p.getCurrentTime().getTime()/1000)-target;program=p.getCurrentProgram();}catch(_){}
          const authorised=program?.isStartOverAuthorized===true||program?.isStartOverOnCurrentAuthorized===true;
          if(offset!==null&&offset>=-1&&offset<=4+(checks+1)*.25&&authorised&&v.readyState>=2&&!v.paused){send({event:'replay-probe',target,available:true});return;}
          if(++checks>=48){send({event:'replay-probe',target,available:false});return;}
          setTimeout(verify,250);
        };
        setTimeout(verify,250);
      } else if(c[0]==='get_property'){
        if(c[1]==='aid')await audioSwitch;
        const value=c[1]==='time-pos'?Math.max(0,v.currentTime-base(v)):c[1]==='duration'?length(v):c[1]==='volume'?v.volume*100:c[1]==='aid'?selected():null;
        send({request_id:packet.request_id,error:value===null?'unsupported':'success',data:value});
      } else if(c[0]==='cycle' && c[1]==='pause'){if(v.paused)await v.play();else v.pause();}
      else if(c[0]==='seek'){
        ++restartCheck;
        // Ask the official media element to seek only within its reported range.
        if(!v.seekable.length){notice('CANAL+: przewijanie nie jest teraz dostępne.');return;}
        const target=c[2]==='absolute'?base(v)+Number(c[1]):v.currentTime+Number(c[1]);
        const start=timing(v)?Math.max(v.seekable.start(0),base(v)):v.seekable.start(0);
        const end=timing(v)?Math.min(v.seekable.end(v.seekable.length-1),base(v)+length(v)):v.seekable.end(v.seekable.length-1);
        v.currentTime=Math.min(end,Math.max(start,target));
        send({event:'playback-restart'});
      } else if(c[0]==='restart'){
        if(!official()?.restart){notice('Oglądanie od początku nie jest dostępne dla tego kanału.');return;}
        const player=official(),token=++restartCheck;
        let start=null;try{start=player.getStartTime?.()?.getTime();}catch(_){}
        player.restart();send({event:'playback-restart'});
        if(!Number.isFinite(start)){notice('Zlecono oglądanie od początku. Odtwarzacz nie podał czasu pozwalającego potwierdzić pozycję.');return;}
        let checks=0;
        const verify=()=>{
          if(token!==restartCheck||official()!==player)return;
          let now=null;try{now=player.getCurrentTime?.()?.getTime();}catch(_){}
          const offset=Number.isFinite(now)?Math.max(0,(now-start)/1000):null;
          if(offset!==null&&offset<=5){notice('Powrót do początku audycji potwierdzony przez odtwarzacz.');return;}
          if(++checks>=8){notice(offset===null?'Nie udało się potwierdzić powrotu do początku.':'Nie potwierdzono początku audycji. Pozycja odtwarzacza: '+Math.floor(offset)+' sekund od jej początku. Dostępny zakres cofania zależy od kanału.');return;}
          setTimeout(verify,1000);
        };
        setTimeout(verify,1000);
      } else if(c[0]==='set_property' && c[1]==='aid'){
        const track=languages()[Number(c[2])-1];
        if(!track || !official()?.setLanguage){notice('Nie ma wybranej ścieżki dźwiękowej.');return;}
        official().setLanguage(track);
        audioSwitch=new Promise(resolve=>{let attempts=0;const check=()=>{if(selected()===Number(c[2])||++attempts>=40)resolve();else setTimeout(check,100);};check();});
      } else if(c[0]==='set_property' && c[1]==='volume')v.volume=Math.max(0,Math.min(1,Number(c[2])/100));
      else if(c[0]==='set_property' && c[1]==='pause'){if(c[2])v.pause();else await v.play();}
      else if(c[0]==='add' && c[1]==='volume')v.volume=Math.max(0,Math.min(1,v.volume+Number(c[2])/100));
      else notice('CANAL+: ta funkcja nie jest jeszcze obsługiwana przez integrację. Użyj opcji oficjalnego odtwarzacza.');
    }catch(_){notice('CANAL+ nie wykonał polecenia. Sprawdź stan oficjalnego odtwarzacza.');}
  };
  setInterval(()=>{
    const v=video();if(!v)return;
    if(v!==current){current=v;loaded=false;lastPause=null;lastTime=-1;}
    if(!loaded && !v.paused){loaded=true;send({event:'file-loaded'});}
    if(!loaded)return;
    const tracks=languages().map((a,i)=>({type:'audio',id:i+1,lang:a.language||a.normalized||'',title:(a.label||a.name||({pl:'Polski',pol:'Polski',qaa:'Język oryginalny (oznaczenie CANAL+)'}[a.language])||a.language||a.normalized||('Ścieżka '+(i+1)))+((a.audioDescription===true||a.normalized==='qad')?' — audiodeskrypcja (oznaczenie CANAL+)':''),selected:i+1===selected()}));
    const serialized=JSON.stringify(tracks);
    if(serialized!==lastTracks){lastTracks=serialized;send({event:'property-change',name:'track-list',data:tracks});}
    if(Math.floor(v.currentTime)!==lastTime){lastTime=Math.floor(v.currentTime);send({event:'property-change',name:'time-pos',data:Math.max(0,v.currentTime-base(v))});}
    send({event:'property-change',name:'duration',data:length(v)});
    send({event:'property-change',name:'volume',data:v.volume*100});
    if(v.paused!==lastPause){lastPause=v.paused;send({event:'property-change',name:'pause',data:v.paused});}
    // No automatic watched marking: a finished trailer/advert is not the main film.
  },1000);
})();
