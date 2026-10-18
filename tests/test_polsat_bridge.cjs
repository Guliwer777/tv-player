const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
(async()=>{
const events=[],keys={};let tick;
const v={readyState:3,currentTime:50,duration:1000,volume:.7,paused:false,getBoundingClientRect:()=>({width:900}),play(){this.paused=false;return Promise.resolve();},pause(){this.paused=true;},audioTracks:[{language:'pl',enabled:true},{label:'AD',enabled:false}]};
const context={location:{origin:'https://polsatboxgo.pl'},document:{cookie:'profile-id=selected',querySelectorAll:()=>[v]},setInterval(fn){tick=fn;},window:{__tvpPolsatProfile:'selected',tvp_bridge:{postMessage:p=>events.push(JSON.parse(p))},addEventListener:(k,f)=>keys[k]=f}};
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
context.document.cookie='profile-id=other';v.paused=false;tick();assert(v.paused);assert(events.some(e=>e.event==='player-error'));
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
console.log('Polsat bridge: OK');
})().catch(e=>{console.error(e);process.exitCode=1;});
