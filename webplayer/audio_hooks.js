/* Retain the official page's own player instance; never inspect constructor arguments. */
(() => {
  const polsat=location.origin==='https://polsatboxgo.pl',player=location.origin==='https://player.pl';
  if(!polsat&&!player)return;
  if(polsat){
    let lastFault='';
    const reportFault=value=>{
      // Page failures occasionally carry a signed address.  Report only a
      // short human-readable message, never an address, cookies or tokens.
      const text=String(value||'').replace(/https?:\/\/\S+/gi,'[adres ukryty]').replace(/\s+/g,' ').trim().slice(0,500);
      if(!text||text===lastFault)return;
      lastFault=text;
      window.tvp_bridge?.postMessage(JSON.stringify({event:'player-error',message:'Polsat Box Go: '+text}));
    };
    window.addEventListener?.('error',event=>{
      // A cross-origin script exposes only this opaque browser message.  The
      // official player can continue normally, so it is not useful to NVDA.
      const message=String(event?.message||'').trim();
      if(/^script error\.?$/i.test(message))return;
      if(!message&&location.pathname?.startsWith('/kanaly-tv/')&&event?.target?.tagName){
        const tag=String(event.target.tagName).toUpperCase();
        const kind=['SCRIPT','LINK','IMG','VIDEO','SOURCE','IFRAME'].includes(tag)?tag:'inny';
        window.tvp_bridge?.postMessage(JSON.stringify({event:'player-diagnostic',message:'Polsat LIVE: błąd ładowania elementu '+kind+'.'}));
        return;
      }
      reportFault(message||'strona zgłosiła nieokreślony błąd podczas uruchamiania.');
    },true);
    window.addEventListener?.('unhandledrejection',event=>reportFault(event?.reason?.message||event?.reason||'strona odrzuciła żądanie podczas uruchamiania.'),true);
    if(typeof window.alert==='function'){
    window.alert=message=>{
      const text=String(message||'').replace(/\s+/g,' ').trim().slice(0,800);
      reportFault(text||'strona wyświetliła pusty komunikat podczas uruchamiania.');
    };
    }
  }
  const key=polsat?'CyfrowyPlayer':'nuvi',member=polsat?'Player':'init';
  const namespaces=new WeakMap(),functions=new WeakMap();
  function capture(instance){
    if(!instance)return;
    if(polsat){
      window.__tvpPolsatSDK=instance;window.__tvpPolsatAudio=[];window.__tvpPolsatEnded=false;
      // onPlaybackEnded also fires when Polsat replaces a playback controller.
      // onVideoComplete is the official completion of the main video, not an advert.
      const completed=()=>{
        if(window.__tvpPolsatSDK!==instance||!location.pathname?.startsWith('/wideo/')||window.__tvpPolsatEnded)return;
        window.__tvpPolsatEnded=true;
        if(typeof document!=='undefined')document.querySelectorAll('video').forEach(v=>v.pause());
        window.tvp_bridge?.postMessage(JSON.stringify({event:'end-file',reason:'eof',content_end:true}));
      };
      // A provider's automatic next film can replace the SDK underneath the add-on.
      // Keep next-episode ownership in Python. The SDK's public middleware is per instance.
      if(location.pathname?.startsWith('/wideo/')&&instance.registerMiddleware){
        const blockNativeNext=()=>{completed();return new Promise(()=>{});};
        const install=()=>{
          if(window.__tvpPolsatSDK!==instance)return;
          instance.registerMiddleware('waitForNext',blockNativeNext);
          instance.registerMiddleware('playNext',blockNativeNext);
        };
        if(instance.ready?.then)instance.ready.then(install).catch(()=>{});else install();
      }
      let lastTitle='';
      const started=info=>{
        const title=info?.video_title;
        if(window.__tvpPolsatSDK!==instance||!location.pathname?.startsWith('/wideo/')||typeof title!=='string'||!title||title===lastTitle)return;
        lastTitle=title;
        window.tvp_bridge?.postMessage(JSON.stringify({event:'content-start',title:title.slice(0,500)}));
      };
      const startEvent=instance.onVideoStart;
      startEvent?.attach(started);
      const completionEvent=instance.onVideoComplete;
      completionEvent?.attach(completed);
      // The page clears all completion listeners when rebuilding its controls.
      // Re-register only our own handler; leave all official handlers in place.
      if(completionEvent?.detach&&typeof setInterval==='function')setInterval(()=>{
        if(window.__tvpPolsatSDK===instance&&!window.__tvpPolsatEnded){
          completionEvent.detach(completed);completionEvent.attach(completed);
          if(startEvent?.detach){startEvent.detach(started);startEvent.attach(started);}
        }
      },1000);
      instance.onPlaybackOptionsUpdated?.attach(options=>{
        if(window.__tvpPolsatSDK===instance&&Array.isArray(options?.audio))window.__tvpPolsatAudio=options.audio;
      });
    }else{
      window.__tvpPlayerSDK=instance;window.__tvpPlayerEnded=false;
      // Nuvi's public event explicitly distinguishes main content from advertising.
      instance.on?.('mainMaterialEnded',main=>{
        if(main!==true||window.__tvpPlayerSDK!==instance||location.pathname==='/live'||window.__tvpPlayerEnded)return;
        window.__tvpPlayerEnded=true;
        if(typeof document!=='undefined')document.querySelectorAll('video').forEach(v=>v.pause());
        window.tvp_bridge?.postMessage(JSON.stringify({event:'end-file',reason:'eof',content_end:true}));
      });
    }
  }
  function wrap(namespace){
    if(!namespace||!['object','function'].includes(typeof namespace))return namespace;
    if(namespaces.has(namespace))return namespaces.get(namespace);
    const proxy=new Proxy(namespace,{get(target,name,receiver){
      const value=Reflect.get(target,name,receiver);
      if(name!==member||typeof value!=='function')return value;
      const descriptor=Object.getOwnPropertyDescriptor(target,name);
      if(descriptor&&!descriptor.configurable&&descriptor.writable===false)return value;
      if(functions.has(value))return functions.get(value);
      const wrapped=new Proxy(value,polsat?{construct(t,args,newTarget){const p=Reflect.construct(t,args,newTarget);capture(p);return p;}}:{apply(t,receiver,args){const p=Reflect.apply(t,receiver,args);capture(p);return p;}});
      functions.set(value,wrapped);return wrapped;
    }});
    namespaces.set(namespace,proxy);namespaces.set(proxy,proxy);return proxy;
  }
  const descriptor=Object.getOwnPropertyDescriptor(window,key);
  if(descriptor&&!descriptor.configurable)return;
  let value=wrap(window[key]);
  Object.defineProperty(window,key,{configurable:true,enumerable:true,get:()=>value,set:v=>{value=wrap(v);}});
})();
