/* Player's official page handles access, ads and DRM. No licence interception. */
(() => {
  if(location.origin!=='https://player.pl')return;
  const settings=__SETTINGS__,send=p=>window.tvp_bridge.postMessage(JSON.stringify(p));
  let current=null,loaded=false,lastTime=-1,lastPause=null,lastTracks='',warned=false,privacyNotice=false,watchAttempts=0,watchAt=0;
  let volume=Math.max(0,Math.min(1,Number(settings.volume)/100));
  const started=Date.now();
  let profileClicked=false;
  let audioSwitch=Promise.resolve();
  const video=()=>[...document.querySelectorAll('video')].filter(v=>v.readyState>=1).sort((a,b)=>b.getBoundingClientRect().width-a.getBoundingClientRect().width)[0];
  const live=()=>settings.playerplLive===true;
  const bounds=v=>live()?(v.seekable?.length?[v.seekable.start(0),v.seekable.end(v.seekable.length-1)]:null):(Number.isFinite(v.duration)&&v.duration>0?[0,v.duration]:null);
  const ads=()=>!!document.querySelector('.ad-showing,.bmpui-ui-admessage-label:not(.bmpui-hidden),.videoAdUi:not([hidden])');
  const sdkAudio=()=>{try{return window.__tvpPlayerSDK?.getAudioTracks()||[];}catch(_){return [];}};
  const trackKey=t=>t?.id??t?.uid??t?.index;
  const tracks=v=>{
    const audio=sdkAudio();
    if(audio.length){
      const selected=window.__tvpPlayerSDK.getCurrentAudioTrack();
      return audio.map((t,i)=>({type:'audio',id:i+1,title:t.label||t.name||t.language||('Ścieżka '+(i+1)),selected:t===selected||(trackKey(t)!=null&&trackKey(t)===trackKey(selected))}));
    }
    return Array.from(v.audioTracks||[]).map((t,i)=>({type:'audio',id:i+1,title:t.label||t.language||('Ścieżka '+(i+1)),selected:!!t.enabled}));
  };
  const notice=message=>send({event:'player-notice',message});
  const restore=v=>{v.volume=volume;setTimeout(()=>{if(current===v)v.volume=volume;},300);};
  const resume=async v=>{await v.play();restore(v);};
  document.addEventListener('play',e=>{if(e.target?.tagName==='VIDEO')restore(e.target);},true);
  window.addEventListener('keydown',e=>{
    if(e.target?.closest('input,textarea,[contenteditable="true"]'))return;
    const key=e.key.toLowerCase();
    const action=key==='f6'?'focus-controls':e.ctrlKey&&!e.altKey?(e.shiftKey?{arrowup:'volume-up',arrowdown:'volume-down'}[key]:{' ':'pause',p:'focus-player',t:'time',arrowleft:'back',arrowright:'forward',arrowup:'step-up',arrowdown:'step-down','1':'audio-1','2':'audio-2','3':'audio-3'}[key]):null;
    if(action){e.preventDefault();e.stopImmediatePropagation();send({event:'addon-command',action});}
  },true);
  window.__tvpCommand=async packet=>{
    const v=video(),c=packet.command||[];
    if(!v){notice('Player: materiał nie został uruchomiony. Może wymagać logowania, zatwierdzenia ustawień strony lub pakietu. Użyj Pokaż obraz.');return;}
    try{
      if(c[0]==='cycle'&&c[1]==='pause'){if(v.paused)await resume(v);else v.pause();}
      else if(c[0]==='set_property'){
        if(c[1]==='pause'){if(c[2])v.pause();else await resume(v);}
        else if(c[1]==='volume'){volume=Math.max(0,Math.min(1,Number(c[2])/100));restore(v);}
        else if(c[1]==='aid'){
          const sdk=sdkAudio(),index=Number(c[2])-1;
          if(sdk.length){
            if(!sdk[index])throw Error();
            audioSwitch=audioSwitch.catch(()=>{}).then(async()=>{
              await window.__tvpPlayerSDK.setAudioTrack(sdk[index]);
              for(let n=0;n<25;n++){if(tracks(v)[index]?.selected===true)return;await new Promise(r=>setTimeout(r,100));}
              throw Error('Audio not confirmed');
            });
            await audioSwitch;return;
          }
          const all=Array.from(v.audioTracks||[]);
          if(!all[index])throw Error();all.forEach((a,i)=>a.enabled=i===index);
          if(!all[index].enabled)throw Error();
        }else throw Error();
      }else if(c[0]==='seek'){
        if(ads())throw Error();
        const range=bounds(v);if(!range)throw Error();
        v.currentTime=Math.max(range[0],Math.min(range[1],c[2]==='absolute'?range[0]+Number(c[1]):v.currentTime+Number(c[1])));
      }else if(c[0]==='get_property'){
        if(c[1]==='aid')await audioSwitch.catch(()=>{});
        const range=bounds(v),value=c[1]==='time-pos'&&range?v.currentTime-range[0]:c[1]==='duration'&&range?range[1]-range[0]:c[1]==='volume'?v.volume*100:c[1]==='aid'?tracks(v).find(t=>t.selected)?.id:null;
        send({request_id:packet.request_id,error:value==null?'unsupported':'success',data:value});
      }
    }catch(_){notice('Player nie potwierdził polecenia. Funkcja może być niedostępna w tym materiale lub podczas reklam.');}
  };
  setInterval(()=>{
    if(window.__tvpPlayerEnded){const v=video();if(v)v.pause();return;}
    const v=video();
    if(!v){
      const manager=document.querySelector('.profile-manager'),expected=window.__tvpPlayerProfile;
      if(manager&&!profileClicked&&manager.getBoundingClientRect().width>0&&manager.getBoundingClientRect().height>0){
        if(expected&&!profileClicked){
          const matches=[...manager.querySelectorAll('.profile-name')].filter(e=>e.textContent.trim()===expected.name);
          if(matches.length===1){profileClicked=true;watchAttempts=0;watchAt=Date.now();matches[0].click();}
          else if(!warned){warned=true;notice('Player wymaga wyboru profilu. Wybierz Pokaż obraz i wskaż profil zapisany we wtyczce.');}
        }
        return;
      }
      const privacy=document.querySelector('#onetrust-banner-sdk,#onetrust-pc-sdk');
      if(privacy&&privacy.getBoundingClientRect().width>0&&privacy.getBoundingClientRect().height>0){
        if(!privacyNotice){privacyNotice=true;notice('Player wymaga wyboru ustawień prywatności. Wybierz Pokaż obraz i ustaw zgody na stronie.');}
        return;
      }
      if(watchAttempts<3&&Date.now()-watchAt>4000){
        // A normal Watch action, never a purchase, subscription or privacy button.
        const watch=[...document.querySelectorAll('button,a')].find(b=>b.innerText?.trim()==='Oglądaj'&&b.getBoundingClientRect().width>0);
        if(watch){watchAttempts++;watchAt=Date.now();watch.click();}
      }
      if(!loaded&&!warned&&Date.now()-started>30000){warned=true;notice('Player czeka na uruchomienie. Wybierz Pokaż obraz, aby sprawdzić logowanie, zgody lub komunikat o dostępie.');}
      return;
    }
    if(v!==current){current=v;restore(v);lastTracks='';lastTime=-1;lastPause=null;}
    if(!loaded&&!v.paused&&v.readyState>=2){loaded=true;send({event:'file-loaded'});if(settings.pause)v.pause();if(settings.quality!=='auto')notice('Player: używana jest automatyczna jakość dostawcy. Wybór jakości z ustawień wtyczki nie jest jeszcze potwierdzony dla Playera.');}
    if(!loaded)return;
    const all=tracks(v),serialized=JSON.stringify(all);
    if(serialized!==lastTracks){lastTracks=serialized;send({event:'property-change',name:'track-list',data:all});}
    const range=bounds(v);
    if(range&&Math.floor(v.currentTime-range[0])!==lastTime){lastTime=Math.floor(v.currentTime-range[0]);send({event:'property-change',name:'time-pos',data:Math.max(0,v.currentTime-range[0])});send({event:'property-change',name:'duration',data:range[1]-range[0]});}
    if(lastPause!==v.paused){lastPause=v.paused;send({event:'property-change',name:'pause',data:v.paused});}
    send({event:'property-change',name:'volume',data:v.volume*100});
  },500);
})();
