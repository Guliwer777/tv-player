// Offline checks: no network or decryption; exercise only the control bridge.
const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'), vm=require('node:vm');
const messages=[],handlers={}; let poll,videos=[];
const location={origin:'https://vod.tvp.pl',pathname:'/filmy,136/film,123'};
let root=null;
const context={location,window:{addEventListener:(n,f)=>handlers[n]=f,tvp_bridge:{postMessage:x=>messages.push(JSON.parse(x))}},
 document:{querySelector:()=>root,querySelectorAll:()=>videos,addEventListener:(n,f)=>handlers[n]=f},setInterval:f=>{poll=f;},
 Date,setTimeout};
const source=fs.readFileSync(path.join(__dirname,'../webplayer/bridge.js'),'utf8').replace('__SETTINGS__',JSON.stringify({start:125.375,volume:70,pause:true,path:location.pathname}));
vm.runInNewContext(source,context);
videos=[{mediaKeys:null,duration:39,currentTime:12}];poll();assert.equal(messages.length,0,'Do not bookmark a clear trailer');
const events={};
const film={mediaKeys:{},duration:8800,currentTime:0,readyState:4,paused:false,volume:1,
 seekable:{length:1,start:()=>0,end:()=>8800},audioTracks:[{label:'Polski',enabled:true},{label:'Audiodeskrypcja',enabled:false}],
 addEventListener:(n,f)=>events[n]=f,pause(){this.paused=true;},play(){this.paused=false;return Promise.resolve();}};
videos.push(film);poll();assert.equal(messages.filter(m=>m.event==='file-loaded').length,1);
assert.equal(film.currentTime,125.375);assert.equal(film.paused,true);assert.equal(film.volume,.7);
context.window.__tvpCommand({command:['get_property','time-pos'],request_id:7401});assert.equal(messages.at(-1).data,125.375);
context.window.__tvpCommand({command:['seek',10]});assert.equal(film.currentTime,135.375);
events.seeked();assert.equal(messages.at(-1).event,'playback-restart');
context.window.__tvpCommand({command:['cycle','pause']});assert.equal(film.paused,false);
context.window.__tvpCommand({command:['set_property','aid',2]});assert.equal(film.audioTracks[1].enabled,true);
context.window.__tvpCommand({command:['get_property','aid'],request_id:7404});assert.equal(messages.at(-1).data,2);
poll();assert.equal(messages.filter(m=>m.event==='file-loaded').length,1);
location.pathname='/filmy,136/inny,456';const count=messages.length;poll();assert.equal(messages.length,count);
context.window.__tvpCommand({command:['get_property','time-pos'],request_id:7401});assert.equal(messages.at(-1).error,'unavailable');
let stopped=false;handlers.keydown({target:{closest:()=>null},key:'F6',preventDefault(){},stopImmediatePropagation(){stopped=true;}});
assert.equal(stopped,true);assert.equal(messages.at(-1).action,'focus-controls');
// The real TVP player stores tracks in Pinia, not HTMLVideo.audioTracks.
location.pathname='/filmy,136/film,123';
let selectedAudio=null,selectedQuality=null;
const store={playerVideoElement:film,audioTracks:[{id:'pol-main',label:'Polski'},{id:'pol-ad',label:'Audiodeskrypcja'}],
 activeAudioTrack:{id:'pol-main'},videoProfiles:[{bandwidth:500000,shortLabel:'SD'},{bandwidth:2000000,shortLabel:'HD'}],
 playerInstance:{switchAudioTrack(id){selectedAudio=id;store.activeAudioTrack={id};},
   seekTo(t){film.currentTime=t;},pause(){film.paused=true;},play(){film.paused=false;},isPaused(){return film.paused;},
   setVolume(n){film.volume=n/100;},switchProfile(n){selectedQuality=n;}},
 setVideoProfile(){},setIsAutoAdaptationEnabled(){}};
root={__vue_app__:{config:{globalProperties:{$pinia:{_s:new Map([['player',store]])}}}}};
film.audioTracks=[];poll();
assert.equal(messages.filter(m=>m.name==='track-list').at(-1).data[1].title,'Audiodeskrypcja');
context.window.__tvpCommand({command:['set_property','aid',2]});
context.window.__tvpCommand({command:['get_property','aid'],request_id:7404});
assert.equal(selectedAudio,'pol-ad');assert.equal(messages.at(-1).data,2);
handlers.keydown({target:{closest:()=>null},key:'ArrowUp',ctrlKey:true,preventDefault(){},stopImmediatePropagation(){}});
assert.equal(messages.at(-1).action,'step-up');
handlers.keydown({target:{closest:()=>null},key:'ArrowDown',ctrlKey:true,preventDefault(){},stopImmediatePropagation(){}});
assert.equal(messages.at(-1).action,'step-down');
store.isPlayingAdvert=true;
const before=film.currentTime;
context.window.__tvpCommand({command:['seek',10]});
assert.equal(film.currentTime,before,'Commands must not skip advertising');
store.isPlayingAdvert=false;
for(const [quality,wanted] of [['800000',500000],['min',500000],['max',2000000],['auto',null]]) {
  selectedQuality=null;let tick;
  const env={...context,setInterval:f=>{tick=f;}};
  const js=fs.readFileSync(path.join(__dirname,'../webplayer/bridge.js'),'utf8').replace('__SETTINGS__',JSON.stringify({start:0,volume:70,pause:false,path:location.pathname,quality}));
  vm.runInNewContext(js,env);tick();
  assert.equal(selectedQuality,wanted,quality);
}
console.log('PASS: trailer boundary, fractional resume, pause, seek, audio, title boundary, F6');
