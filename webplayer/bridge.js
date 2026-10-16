/* Control only the encrypted main video in the official TVP page.
   No licence interception, key extraction, consent changes or ad skipping. */
(() => {
  if (location.origin !== 'https://vod.tvp.pl') return;
  const send = value => window.tvp_bridge.postMessage(JSON.stringify(value));
  const settings = __SETTINGS__;
  const isMaterial = () => location.pathname === settings.path || location.pathname.startsWith(settings.path+'/');
  const actionForKey = event => {
    const key=event.key.toLowerCase();
    if(key!=='f6' && event.target?.closest('input:not([type="range"]):not([type="checkbox"]):not([type="radio"]):not([type="button"]),textarea,[contenteditable="true"]')) return null;
    let action=null;
    if(key==='f6') action='focus-controls';
    else if(!event.altKey && event.ctrlKey) {
      if(event.shiftKey) action={arrowup:'volume-up',arrowdown:'volume-down'}[key];
      else action={' ':'pause',t:'time',z:'bookmark',arrowleft:'back',arrowright:'forward',
        arrowup:'step-up',arrowdown:'step-down','1':'audio-1','2':'audio-2','3':'audio-3'}[key];
    } else if(!event.altKey && !event.shiftKey) {
      if(event.target?.closest('.ui-player-gui-slider--video')) {
        action={arrowleft:'back',arrowright:'forward',arrowup:'step-up',arrowdown:'step-down'}[key];
      }
      action=action || {escape:'catalog-home',backspace:'catalog-back',f1:'help'}[key];
    }
    return action;
  };
  // Window capture precedes the website's document/player handlers. In
  // particular Ctrl+Up/Down must change our step, not the TVP volume.
  window.addEventListener('keydown', event => {
    const action=actionForKey(event);
    if(action) {event.preventDefault();event.stopImmediatePropagation();send({event:'addon-command',action});}
  },true);
  window.addEventListener('keyup',event=>{
    if(actionForKey(event)) {event.preventDefault();event.stopImmediatePropagation();}
  },true);
  let video = null, loaded = false, restored = false, lastTracks = '', pendingAudioId=null, qualityApplied=false, qualitySince=0, qualityWarned=false;
  const finite = n => Number.isFinite(n) ? n : 0;
  function tvpStore() {
    const root=document.querySelector('#app') || document.querySelector('[data-v-app]');
    const pinia=root?.__vue_app__?.config?.globalProperties?.$pinia;
    if(!pinia?._s?.values) return null;
    for(const store of pinia._s.values()) {
      if(store.playerInstance && store.playerVideoElement===video) return store;
    }
    return null;
  }
  function tracks(v) {
    const store=tvpStore();
    if(store && Array.isArray(store.audioTracks) && store.audioTracks.length) {
      return store.audioTracks.map((t,i)=>({id:i+1,type:'audio',
        title:String(t.label || t.lang || `Ścieżka ${i+1}`).slice(0,300),
        selected:store.activeAudioTrack?.id===t.id}));
    }
    return Array.from(v.audioTracks || []).map((t,i) => ({id:i+1,type:'audio',
      title:t.label || t.language || `Ścieżka ${i+1}`,selected:t.enabled}));
  }
  function property(name) {
    if (!video) throw new Error('Poczekaj na uruchomienie filmu w odtwarzaczu TVP.');
    switch(name) {
      case 'time-pos': return finite(video.currentTime);
      case 'duration': return finite(video.duration);
      case 'pause': return typeof tvpStore()?.playerInstance?.isPaused==='function' ? tvpStore().playerInstance.isPaused() : video.paused;
      case 'volume': return video.volume*100;
      case 'track-list': return tracks(video);
      case 'aid': return tracks(video).find(t=>t.selected)?.id || null;
    }
    throw new Error('Nieobsługiwana właściwość.');
  }
  function change(name,data) {
    if (!video) throw new Error('Najpierw uruchom film przyciskiem Odtwórz na stronie TVP.');
    const store=tvpStore(), player=store?.playerInstance;
    if(store?.isPlayingAdvert) throw new Error('Trwa reklama TVP. Sterowanie filmem będzie dostępne po jej zakończeniu.');
    if (name === 'pause') {
      if(player && typeof player.pause==='function' && typeof player.play==='function') {
        if(data) player.pause(); else player.play();
      } else if (data) video.pause();
      else video.play().catch(()=>send({event:'player-error',message:'TVP wymaga uruchomienia filmu na stronie odtwarzacza.'}));
    } else if (name === 'volume') {
      if(typeof player?.setVolume==='function') player.setVolume(Math.max(0,Math.min(100,Number(data))));
      else video.volume=Math.max(0,Math.min(1,Number(data)/100));
    }
    else if (name === 'aid') {
      if(store && typeof player?.switchAudioTrack==='function' && store.audioTracks?.[Number(data)-1]) {
        pendingAudioId=Number(data);
        player.switchAudioTrack(store.audioTracks[Number(data)-1].id);
        return;
      }
      const list=Array.from(video.audioTracks || []);
      if (!list[Number(data)-1]) throw new Error('Wybierz ścieżkę w ustawieniach oficjalnego odtwarzacza TVP.');
      list.forEach((t,i)=>t.enabled=(i===Number(data)-1));
    } else throw new Error('Nieobsługiwane polecenie.');
  }
  window.__tvpCommand = packet => {
    const [action,...args]=packet.command || [];
    try {
      if(!isMaterial()) throw new Error('Wróć do strony wybranego materiału TVP.');
      let data=null;
      if (action==='get_property' && args[0]==='aid' && pendingAudioId!==null) {
        const wanted=pendingAudioId;
        const deadline=Date.now()+4000;
        const check=()=>{
          const actual=property('aid');
          if(actual===wanted || Date.now()>=deadline) {
            pendingAudioId=null;
            send({request_id:packet.request_id,error:actual===wanted?'success':'unavailable',data:actual});
          } else setTimeout(check,100);
        };
        check(); return;
      } else if (action==='get_property') data=property(args[0]);
      else if (action==='cycle' && args[0]==='pause') change('pause',!property('pause'));
      else if (action==='set_property') change(args[0],args[1]);
      else if (action==='seek') {
        const store=tvpStore();
        if(store?.isPlayingAdvert) throw new Error('Trwa reklama TVP. Przewijanie filmu będzie dostępne po jej zakończeniu.');
        if (!video || !video.seekable.length) throw new Error('Przewijanie jest jeszcze niedostępne.');
        const target=Math.max(0,Math.min(video.duration,video.currentTime+Number(args[0])));
        if(typeof store?.playerInstance?.seekTo==='function') store.playerInstance.seekTo(target);
        else video.currentTime=Math.max(video.seekable.start(0),Math.min(video.seekable.end(video.seekable.length-1),target));
      } else throw new Error('Nieobsługiwane polecenie.');
      if (packet.request_id) send({request_id:packet.request_id,error:'success',data});
    } catch(e) {
      if (packet.request_id) send({request_id:packet.request_id,error:'unavailable',data:null});
      else send({event:'player-error',message:e.message});
    }
  };
  setInterval(() => {
    if(!isMaterial()) return;
    // Trailers and advertisements are not the bookmarked feature film.
    const candidate=Array.from(document.querySelectorAll('video')).find(v=>v.mediaKeys);
    if (!candidate) return;
    if (video!==candidate) {
      video=candidate;
      video.addEventListener('seeked',()=>send({event:'playback-restart'}));
      video.addEventListener('ended',()=>send({event:'end-file',reason:'eof'}));
      video.addEventListener('error',()=>send({event:'player-error',message:'Oficjalny odtwarzacz TVP zgłosił błąd filmu lub licencji DRM.'}));
    }
    const store=tvpStore();
    if (store?.isPlayingAdvert || video.readyState < 2 || !Number.isFinite(video.duration)) return;
    if (!loaded) {
      loaded=true;
      qualitySince=Date.now();
      send({event:'file-loaded'});
      change('volume',settings.volume);
    }
    if (!restored && video.seekable.length) {
      restored=true;
      if (settings.start>0) {
        const start=Math.min(settings.start,Math.max(0,video.duration-.1));
        if(typeof store?.playerInstance?.seekTo==='function') store.playerInstance.seekTo(start);
        else video.currentTime=start;
      }
      if(settings.pause) change('pause',true);
    }
    if(!qualityApplied && settings.quality && settings.quality!=='auto' && store?.videoProfiles?.length && typeof store.playerInstance?.switchProfile==='function') {
      const list=store.videoProfiles.filter(p=>Number.isFinite(Number(p.bandwidth)) && Number(p.bandwidth)>0).slice().sort((a,b)=>Number(a.bandwidth)-Number(b.bandwidth));
      if(list.length) {
        const limit=Number(settings.quality);
        const selected=settings.quality==='min'?list[0]:settings.quality==='max'?list.at(-1):list.filter(p=>Number(p.bandwidth)<=limit).at(-1)||list[0];
        store.setVideoProfile?.(selected);
        store.setIsAutoAdaptationEnabled?.(false);
        store.playerInstance.switchProfile(selected.bandwidth);
        qualityApplied=true;
        send({event:'player-notice',message:'Jakość odtwarzania: '+String(selected.shortLabel||selected.label||Math.round(Number(selected.bandwidth)/1000)+' kb/s')});
      }
    }
    if(settings.quality && settings.quality!=='auto' && !qualityApplied && !qualityWarned && Date.now()-qualitySince>15000) {
      qualityWarned=true;
      send({event:'player-notice',message:'Nie udało się zastosować wybranej jakości. Wybierz ją w ustawieniach strony TVP.'});
    }
    for (const name of ['time-pos','duration','pause','volume']) {
      send({event:'property-change',name,data:property(name)});
    }
    const list=tracks(video), encoded=JSON.stringify(list);
    if(encoded!==lastTracks) {
      lastTracks=encoded;
      send({event:'property-change',name:'track-list',data:list});
    }
  },500);
})();
