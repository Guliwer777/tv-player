'use strict';
(() => {
  const video=document.getElementById('video'),status=document.getElementById('status');
  const send=message=>window.tvp_bridge.postMessage(JSON.stringify(message));
  let player,config,loaded=false,audios=[],ended=false,pendingAudioId=null,timeBase=0;
  const safe=n=>Number.isFinite(n)?n:0;
  function failure(error) {
    const code=error?.code || error?.name || 'nieznany';
    status.textContent='Błąd odtwarzacza: '+code;
    const detail=String(error?.message||'').replace(/https?:\/\/\S+/g,'[adres]').slice(0,250);
    const type=code===1003?error?.data?.[1]:error?.data?.[2];
    send({event:error?.severity===1?'player-notice':'player-error',message:'Odtwarzacz TV Player: '+code+(Number.isInteger(type)?' (żądanie '+type+')':'')+(detail?' — '+detail:'')});
  }
  function audioList() {
    const raw=typeof player.getAudioTracks==='function'?player.getAudioTracks():[];
    if(raw.length) {
      audios=raw;
      return raw.map((t,i)=>({id:i+1,type:'audio',selected:!!t.active,
        title:String(t.label || (t.language && t.language!=='und'?t.language:`Ścieżka ${i+1}`)).slice(0,300)+(t.roles?.some(r=>/description|visually/.test(r))?' — audiodeskrypcja':'')}));
    }
    const variants=player.getVariantTracks();
    audios=[...new Map(variants.map(t=>[t.audioId??t.language,t])).values()];
    return audios.map((t,i)=>({id:i+1,type:'audio',selected:variants.some(v=>v.active && v.audioId===t.audioId),title:String(t.label||t.language||`Ścieżka ${i+1}`).slice(0,300)}));
  }
  function property(name) {
    if(!loaded)throw new Error('loading');
    if(name==='time-pos')return Math.max(0,safe(video.currentTime-timeBase));
    if(name==='duration')return config.isLive?Math.max(0,safe(player.seekRange().end-timeBase)):safe(video.duration);
    if(name==='pause')return video.paused;
    if(name==='volume')return video.volume*100;
    if(name==='track-list')return audioList();
    if(name==='aid')return audioList().find(t=>t.selected)?.id || null;
    throw new Error('unknown-property');
  }
  window.__tvpCommand=async packet=>{
    const [action,...args]=packet.command||[];
    try {
      if(!loaded)throw new Error('loading');
      let data=null;
      if(action==='get_property' && args[0]==='aid' && pendingAudioId!==null) {
        const wanted=pendingAudioId,deadline=Date.now()+4000;
        const check=()=>{
          const actual=property('aid');
          if(actual===wanted || Date.now()>=deadline) {
            pendingAudioId=null;send({request_id:packet.request_id,error:actual===wanted?'success':'unavailable',data:actual});
          } else setTimeout(check,100);
        };
        check();return;
      } else if(action==='get_property')data=property(args[0]);
      else if(action==='seek') {
        const range=typeof player.seekRange==='function'?player.seekRange():{start:0,end:video.duration};
        video.currentTime=Math.max(range.start,Math.min(range.end,video.currentTime+Number(args[0])));
      }
      else if(action==='cycle' && args[0]==='pause') {if(video.paused)await video.play();else video.pause();}
      else if(action==='set_property') {
        const [name,value]=args;
        if(name==='pause') {if(value)video.pause();else await video.play();}
        else if(name==='volume')video.volume=Math.max(0,Math.min(1,Number(value)/100));
        else if(name==='aid') {
          audioList();const track=audios[Number(value)-1];
          if(!track)throw new Error('missing-audio');
          pendingAudioId=Number(value);
          if(typeof player.selectAudioTrack==='function')player.selectAudioTrack(track);
          else player.selectVariantTrack(track,true);
        } else throw new Error('unknown-property');
      } else throw new Error('unknown-command');
      if(packet.request_id)send({request_id:packet.request_id,error:'success',data});
    }catch(error){
      if(packet.request_id)send({request_id:packet.request_id,error:'unavailable',data:null});
      else failure(error);
    }
  };
  window.addEventListener('keydown',event=>{
    const key=event.key.toLowerCase();let action;
    if(event.ctrlKey && !event.altKey)action=event.shiftKey?{arrowup:'volume-up',arrowdown:'volume-down'}[key]:
      {' ':'pause',p:'focus-player',t:'time',z:'bookmark',u:'favorite',arrowleft:'back',arrowright:'forward',arrowup:'step-up',arrowdown:'step-down','1':'audio-1','2':'audio-2','3':'audio-3'}[key];
    else if(!event.altKey && !event.shiftKey)action={f6:'focus-controls',f1:'help',escape:'catalog-home',backspace:'catalog-back'}[key];
    if(action){event.preventDefault();event.stopImmediatePropagation();send({event:'addon-command',action});}
  },true);
  async function init(){
    config=await (await fetch('config.json')).json();
    if(typeof shaka==='undefined')throw new Error('Nie załadowano biblioteki Shaka Player.');
    shaka.polyfill.installAll();
    if(!shaka.Player.isBrowserSupported())throw new Error('unsupported-browser');
    player=new shaka.Player();await player.attach(video);
    player.addEventListener('error',event=>failure(event.detail));
    if(config.relay) {
      const relay=new URL(config.relay,location.href).href;
      let networkSequence=0;
      shaka.net.NetworkingEngine.registerScheme('https',(uri,request,type,progress,headersReceived,pluginConfig)=>{
        const sequence=++networkSequence;
        const diagnostic=stage=>send({event:'direct-network',stage,sequence,type});
        diagnostic('fetch');
        return shaka.net.HttpXHRPlugin.parse(
          relay+'?u='+encodeURIComponent(uri),request,type,progress,headersReceived,pluginConfig
        ).chain(response=>{
          diagnostic('body');
          response.uri=uri;response.originalUri=uri;
          return response;
        });
      },shaka.net.NetworkingEngine.PluginPriority.APPLICATION,true);
    }
    const settings={drm:{servers:config.servers,preferredKeySystems:['com.widevine.alpha','com.microsoft.playready']}};
    if(Number(config.quality)>0)settings.abr={restrictions:{maxBandwidth:Number(config.quality)},defaultBandwidthEstimate:Number(config.quality),useNetworkInformation:false};
    player.configure(settings);
    await player.load(config.manifest,config.isLive?undefined:Number(config.start)||0);
    if(config.isLive)timeBase=player.seekRange().start;
    if(config.quality==='min' || config.quality==='max') {
      const all=player.getVariantTracks(),active=all.find(t=>t.active);
      const variants=all.filter(t=>!active || t.audioId===active.audioId).sort((a,b)=>a.bandwidth-b.bandwidth);
      if(variants.length) {
        player.configure({abr:{enabled:false}});
        player.selectVariantTrack(config.quality==='min'?variants[0]:variants.at(-1),true);
      }
    }
    video.volume=Math.max(0,Math.min(1,Number(config.volume)/100));
    loaded=true;status.textContent='';
    send({event:'file-loaded'});
    if(!config.pause)try{await video.play();}catch(error){
      if(error?.name==='NotAllowedError')send({event:'player-notice',message:'Materiał gotowy. Naciśnij Ctrl+Spacja, aby rozpocząć.'});
      else if(error?.name!=='AbortError')failure(error);
    }
    send({event:'property-change',name:'track-list',data:audioList()});
  }
  video.addEventListener('seeked',()=>send({event:'playback-restart'}));
  video.addEventListener('ended',()=>{if(!ended){ended=true;send({event:'end-file',reason:'eof'});}});
  setInterval(()=>{
    if(!loaded)return;
    if(config.diagnostics) {
      const variant=player.getVariantTracks().find(t=>t.active);
      send({event:'direct-network',stage:'playback',position:video.currentTime,paused:video.paused,
        readyState:video.readyState,seeking:video.seeking,error:video.error?.code,
        buffers:typeof player.getBufferedInfo==='function'?player.getBufferedInfo():null,
        buffered:Array.from({length:video.buffered.length},(_,i)=>[video.buffered.start(i),video.buffered.end(i)]),
        variant:variant?{width:variant.width,height:variant.height,bandwidth:variant.bandwidth}:null});
    }
    for(const name of ['time-pos','duration','pause','volume','track-list'])send({event:'property-change',name,data:property(name)});
  },500);
  init().catch(failure);
})();

