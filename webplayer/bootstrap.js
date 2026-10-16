window.addEventListener('error',event=>{
  const text=String(event.message || 'Nie udało się załadować skryptu odtwarzacza.').replace(/https?:\/\/\S+/g,'[adres]').slice(0,300);
  try{window.tvp_bridge.postMessage(JSON.stringify({event:'player-error',message:'Skrypt odtwarzacza: '+text}));}catch(e){}
},true);
document.addEventListener('securitypolicyviolation',event=>{
  let target='';try{const url=new URL(event.blockedURI);target=url.protocol+'//'+url.hostname;}catch(e){target=String(event.blockedURI).slice(0,40);}
  try{window.tvp_bridge.postMessage(JSON.stringify({event:'player-error',message:'Zasady strony odtwarzacza: '+event.effectiveDirective+' '+target}));}catch(e){}
});
