/* Retain the official page's own player instance; never inspect constructor arguments. */
(() => {
  const polsat=location.origin==='https://polsatboxgo.pl',player=location.origin==='https://player.pl';
  if(!polsat&&!player)return;
  const key=polsat?'CyfrowyPlayer':'nuvi',member=polsat?'Player':'init';
  const namespaces=new WeakMap(),functions=new WeakMap();
  function capture(instance){
    if(!instance)return;
    if(polsat){
      window.__tvpPolsatSDK=instance;window.__tvpPolsatAudio=[];
      instance.onPlaybackOptionsUpdated?.attach(options=>{
        if(window.__tvpPolsatSDK===instance&&Array.isArray(options?.audio))window.__tvpPolsatAudio=options.audio;
      });
    }else window.__tvpPlayerSDK=instance;
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
