const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
(async()=>{
const events=[],keys={};let tick,now=100000;
const v={readyState:3,currentTime:50,duration:1000,volume:.7,paused:false,getBoundingClientRect:()=>({width:900}),play(){this.paused=false;return Promise.resolve();},pause(){this.paused=true;},audioTracks:[{language:'pl',enabled:true},{label:'AD',enabled:false}]};
const context={Date:{now:()=>now},location:{origin:'https://polsatboxgo.pl'},document:{cookie:'profile-id=selected',querySelectorAll:()=>[v]},setInterval(fn){tick=fn;},window:{__tvpPolsatProfile:'selected',tvp_bridge:{postMessage:p=>events.push(JSON.parse(p))},addEventListener:(k,f)=>keys[k]=f}};
const source=fs.readFileSync('webplayer/polsat_bridge.js','utf8').replace('__SETTINGS__',JSON.stringify({volume:70}));
vm.runInNewContext(source,context);tick();assert(events.some(e=>e.event==='file-loaded'));
await context.window.__tvpCommand({command:['seek',30,'relative+exact']});assert.equal(v.currentTime,80);
await context.window.__tvpCommand({command:['cycle','pause']});assert(v.paused);
await context.window.__tvpCommand({command:['set_property','volume',37]});
v.play=function(){this.paused=false;this.volume=1;return Promise.resolve();};
await context.window.__tvpCommand({command:['set_property','pause',false]});assert.equal(v.volume,.37);
await context.window.__tvpCommand({command:['set_property','aid',2]});assert(v.audioTracks[1].enabled);assert(!v.audioTracks[0].enabled);
v.duration=Infinity;v.currentTime=1200;v.seekable={length:1,start:()=>1000,end:()=>1300};
await context.window.__tvpCommand({command:['seek',50,'absolute']});assert.equal(v.currentTime,1050);
await context.window.__tvpCommand({command:['get_property','time-pos'],request_id:1});assert.equal(events.at(-1).data,50);
keys.keydown({key:'ArrowUp',ctrlKey:true,target:{closest:()=>false},preventDefault(){},stopImmediatePropagation(){}});assert.equal(events.at(-1).action,'step-up');
context.window.__tvpPolsatAudio=[{label:'polski',value:{active:true}},{label:'polski (audiodeskrypcja)',value:{active:false}}];
context.window.__tvpPolsatSDK={user:{setPlaybackOptions:async ({audio})=>{context.window.__tvpPolsatAudio.forEach(a=>a.value.active=a.value===audio);}}};
await context.window.__tvpCommand({command:['set_property','aid',2]});
await context.window.__tvpCommand({command:['get_property','aid'],request_id:100});assert.equal(events.at(-1).data,2);
context.document.cookie='profile-id=other';v.paused=false;tick();assert(!v.paused);assert(!events.some(e=>e.event==='player-error'));
now+=10001;tick();assert(v.paused);assert(events.some(e=>e.event==='player-error'));
await context.window.__tvpCommand({command:['cycle','pause']});assert(v.paused);
const foreign={location:{origin:'https://evil.example'}};vm.runInNewContext(source,foreign);assert.equal(foreign.window,undefined);
// A UTC programme start is mapped through the verified DASH timeline, not a UI click.
let clock=3000000;const notices=[];
const replayVideo={...v,paused:false,currentTime:1250,muted:false,duration:Infinity,seekable:{length:1,start:()=>1000,end:()=>1300}};
let replayTick;
const replay={...context,Date:{now:()=>clock},document:{cookie:'profile-id=selected',querySelectorAll:()=>[replayVideo]},window:{__tvpPolsatProfile:'selected',tvp_bridge:{postMessage:p=>notices.push(JSON.parse(p))},addEventListener(){}},setInterval:fn=>replayTick=fn};
const precisionSource=source.replace('"volume":70','"volume":70,"polsatStart":2100,"polsatOrigin":1000');
vm.runInNewContext(precisionSource,replay);replayTick();assert.equal(replayVideo.currentTime,1100);assert(replayVideo.muted);assert(!notices.some(e=>e.event==='file-loaded'));
for(let i=0;i<3;i++){clock+=500;replayVideo.currentTime+=.5;replayTick();}
assert(notices.some(e=>e.event==='file-loaded'));assert(!replayVideo.muted);
const failed=[];replayVideo.currentTime=1250;replayVideo.paused=false;replayVideo.seekable={length:1,start:()=>1200,end:()=>1300};replay.window.tvp_bridge.postMessage=p=>failed.push(JSON.parse(p));
vm.runInNewContext(precisionSource,replay);replayTick();clock+=46000;replayTick();assert(replayVideo.paused);assert(failed.some(e=>e.event==='player-error'));assert(!failed.some(e=>e.event==='file-loaded'));
const missing=[];replayVideo.paused=false;replay.window.tvp_bridge.postMessage=p=>missing.push(JSON.parse(p));
vm.runInNewContext(source.replace('"volume":70','"volume":70,"polsatStart":2100'),replay);replayTick();assert(replayVideo.paused);assert(missing.some(e=>e.event==='player-error'));
// Resume prompt on an already-watched episode is not a purchase/consent action.
for(const tag of ['button','div'])for(const start of [0,120]){
 const clicked=[];let resumeTick;
 const buttons=['Oglądaj dalej','Oglądaj od początku','Kup dostęp','Akceptuj wszystko'].map(text=>({innerText:text,getBoundingClientRect:()=>({width:clicked.length?0:120}),click(){clicked.push(text);}}));
 const prompt={...context,document:{cookie:'profile-id=selected',querySelectorAll:selector=>selector.split(',').includes(tag)?buttons:[]},window:{__tvpPolsatProfile:'selected',tvp_bridge:{postMessage(){}},addEventListener(){}},setInterval:fn=>resumeTick=fn};
 vm.runInNewContext(source.replace('"volume":70','"volume":70,"start":'+start),prompt);resumeTick();resumeTick();
 assert.deepEqual(clicked,[start?'Oglądaj dalej':'Oglądaj od początku']);
}
// A channel without its video element receives only the ordinary Watch action,
// then reports a useful error instead of silently waiting forever.
let liveNow=2000,liveTick;const liveEvents=[],liveClicks=[];
const liveButton={innerText:'Oglądaj',getBoundingClientRect:()=>({width:liveClicks.length?0:120}),click(){liveClicks.push('Oglądaj');}};
const live={Date:{now:()=>liveNow},location:{origin:'https://polsatboxgo.pl'},document:{cookie:'profile-id=selected',querySelectorAll:selector=>selector==='video'?[]:[liveButton]},window:{__tvpPolsatProfile:'selected',tvp_bridge:{postMessage:p=>liveEvents.push(JSON.parse(p))},addEventListener(){}},setInterval:fn=>liveTick=fn};
vm.runInNewContext(source,live);liveTick();assert.deepEqual(liveClicks,['Oglądaj']);
liveNow=48001;liveTick();assert(liveEvents.some(e=>e.event==='player-error'&&e.message.includes('nie uruchomił odtwarzacza')));
// Main-content resume is applied once; an advert and later user seeks stay untouched.
let mainTick,state='PLAYING_LINEAR_AD';const mainVideo={...v,duration:1300,currentTime:262,seeking:false};
const mainContext={...context,location:{origin:'https://polsatboxgo.pl',pathname:'/wideo/serial/1/ogladaj'},document:{cookie:'profile-id=selected',querySelectorAll:selector=>selector==='video'?[mainVideo]:[]},window:{__tvpPolsatProfile:'selected',__tvpPolsatSDK:{getStatus:()=>({state})},tvp_bridge:{postMessage(){}},addEventListener(){}},setInterval:fn=>mainTick=fn};
vm.runInNewContext(source,mainContext);mainTick();assert.equal(mainVideo.currentTime,262);
state='PLAYING_CONTENT';mainTick();assert.equal(mainVideo.currentTime,0);
mainVideo.currentTime=700;mainTick();assert.equal(mainVideo.currentTime,700);
console.log('Polsat bridge: OK');
{
 let now=0,tick;
 const packets=[];
 const page={...live,Date:{now:()=>now},location:{origin:'https://polsatboxgo.pl',pathname:'/kanaly-tv/test/1/ogladaj'},
  document:{cookie:'profile-id=selected',readyState:'complete',body:{innerText:'Przejdź do treści\nPrzejdź do stopki'},querySelector:s=>s==='[role="alert"]'?{}:null,
   querySelectorAll:s=>s.includes('a[href]')?[{getClientRects:()=>[]}]:[]},
  window:{...live.window,tvp_bridge:{postMessage:s=>packets.push(JSON.parse(s))}},setInterval:f=>tick=f};
 vm.runInNewContext(source,page);now=16000;page.document.body.innerText='Wybierz profil';tick();
 assert.equal(packets.length,0);page.document.body.innerText='Przejdź do treści\n\uFFFC';tick();tick();
 assert.deepEqual(packets.map(p=>p.code),['polsat-live-empty-page']);
 packets.length=0;now=0;page.window.__tvpPolsatSDK={};
 vm.runInNewContext(source,page);now=16000;tick();assert.equal(packets.length,0);
 now=21000;tick();tick();
 assert.deepEqual(packets.map(p=>p.code),['polsat-live-empty-page']);
}
{
 let tick, clicks=0;
 const play={getAttribute:k=>k==='aria-label'?'Odtwarzaj':null,getBoundingClientRect:()=>({width:80}),click:()=>clicks++};
 const replay={innerText:'Oglądaj od początku',getBoundingClientRect:()=>({width:80}),click(){throw Error('Unexpected start-over');}};
 const page={...live,location:{origin:'https://polsatboxgo.pl',pathname:'/kanaly-tv/test/1/ogladaj'},
  document:{cookie:'profile-id=selected',querySelectorAll:s=>s.startsWith('[aria-label]')?[play]:s.includes('div')?[replay]:[]},
  window:{...live.window,__tvpPolsatSDK:{}},setInterval:f=>tick=f};
 vm.runInNewContext(source.replace('"volume":70','"volume":70,"pause":true'),page);tick();assert.equal(clicks,0);
 vm.runInNewContext(source,page);tick();tick();assert.equal(clicks,1);
}
// A failed SDK getter must leave HTTP evidence available, and vice versa.
for(const failState of [true,false]){
 let now=0,tick;const reports=[];
 const sdk={getStatus(){if(failState)throw Error();return {state:'IDLE'};}};
 const performance={now:()=>now,getEntriesByType(type){
  if(type==='navigation')return [{type:'reload'}];
  if(!failState)throw Error();
  return [{responseStatus:503}];
 }};
 const page={...live,Date:{now:()=>now},location:{...live.location,pathname:'/kanaly-tv/test/1/ogladaj'},
  document:{cookie:'profile-id=selected',readyState:'complete',body:{innerText:''},addEventListener(){},
   querySelector:s=>s==='[role="alert"]'?{}:null,querySelectorAll:()=>[]},
  window:{...live.window,performance,__tvpPolsatSDK:sdk,tvp_bridge:{postMessage:s=>reports.push(JSON.parse(s))}},
  setInterval:f=>tick=f};
 vm.runInNewContext(source,page);now=21000;tick();
 const summary=reports.find(e=>e.message?.includes('pusta strona; stan SDK='));
 assert(summary.message.includes(failState?'SDK=niedostępny, widoczne błędy HTTP=503':'SDK=IDLE, widoczne błędy HTTP=odczyt niedostępny'));
}
})().catch(e=>{console.error(e);process.exitCode=1;});
