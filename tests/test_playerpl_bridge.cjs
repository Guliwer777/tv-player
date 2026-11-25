const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync('webplayer/playerpl_bridge.js','utf8');
async function run(live=false){
 const packets=[],intervals=[];let advert=false;
 const v={readyState:4,duration:100,currentTime:20,volume:1,paused:false,seekable:{length:1,start:()=>10,end:()=>90},getBoundingClientRect:()=>({width:500}),audioTracks:[{label:'Polski',enabled:true},{label:'Opis',enabled:false}],pause(){this.paused=true},async play(){this.paused=false;this.volume=1}};
 const context={location:{origin:'https://player.pl'},window:{tvp_bridge:{postMessage:s=>packets.push(JSON.parse(s))},addEventListener(){}},document:{querySelectorAll:()=>[v],querySelector:()=>advert?{}:null,addEventListener(){}},setInterval:f=>intervals.push(f),setTimeout:f=>f(),Date,Number,Math,Array,JSON,Error};
 vm.runInNewContext(code.replace('__SETTINGS__',JSON.stringify({volume:37,pause:false,quality:'auto',playerplLive:live})),context);
 intervals[0]();assert(packets.some(p=>p.event==='file-loaded'));assert.equal(v.volume,.37);
 const command=async c=>context.window.__tvpCommand({command:c,request_id:5});
 await command(['cycle','pause']);assert(v.paused);await command(['cycle','pause']);assert(!v.paused);assert.equal(v.volume,.37);
 await command(['seek',500,'relative']);assert.equal(v.currentTime,live?90:100);
 advert=true;await command(['seek',-10,'relative']);assert.equal(v.currentTime,live?90:100);advert=false;
 await command(['seek',0,'absolute']);assert.equal(v.currentTime,live?10:0);
 await command(['set_property','aid',2]);assert(v.audioTracks[1].enabled);assert(!v.audioTracks[0].enabled);
 await command(['get_property','duration']);assert.equal(packets.at(-1).data,live?80:100);
 const sdkTracks=[{id:'pl',label:'Polski'},{id:'ad',label:'Polski (audiodeskrypcja)'}];let selected=sdkTracks[0];
 context.window.__tvpPlayerSDK={getAudioTracks:()=>sdkTracks,getCurrentAudioTrack:()=>selected,setAudioTrack:async t=>{selected=t;}};
 await command(['set_property','aid',2]);await command(['get_property','aid']);assert.equal(packets.at(-1).data,2);
 assert(!packets.some(p=>p.event==='end-file'||p.event==='watched'));
}
function startup(privacy){
 const packets=[],timers=[];let clicks=0;
 const visible={getBoundingClientRect:()=>({width:500,height:200})};
 const buttons=[{...visible,innerText:'Wykup dostęp',click(){throw Error('Must not purchase')}},{...visible,innerText:'Oglądaj',click(){clicks++}}];
 const context={location:{origin:'https://player.pl'},window:{tvp_bridge:{postMessage:s=>packets.push(JSON.parse(s))},addEventListener(){}},document:{querySelectorAll:s=>s==='video'?[]:buttons,querySelector:s=>s.startsWith('#onetrust')&&privacy?visible:null,addEventListener(){}},setInterval:f=>timers.push(f),setTimeout(){},Date,Number,Math,Array,JSON,Error};
 vm.runInNewContext(code.replace('__SETTINGS__',JSON.stringify({volume:0,quality:'auto'})),context);timers[0]();
 assert.equal(clicks,privacy?0:1);
 if(privacy)assert(packets.some(p=>p.message?.includes('prywatności')));
}
function loginWall(){
 const packets=[],timers=[],events={},session=new Map(),saved=new Map();
 const storage=m=>({getItem:k=>m.get(k),setItem:(k,v)=>m.set(k,v),removeItem:k=>m.delete(k)});
 const login={innerText:'Zaloguj się, by oglądać bez opłat',getBoundingClientRect:()=>({width:300}),click(){throw Error('Automatic sign-in');}};
 let video;
 const context={location:{origin:'https://player.pl',pathname:'/live'},sessionStorage:storage(session),localStorage:storage(saved),
   window:{tvp_bridge:{postMessage:s=>packets.push(JSON.parse(s))},addEventListener:(n,f)=>events[n]=f},
   document:{querySelectorAll:s=>s==='video'?(video?[video]:[]):[login],querySelector:()=>null,addEventListener:(n,f)=>events[n]=f},
   setInterval:f=>timers.push(f),setTimeout(){},Date,Number,Math,Array,JSON,Error};
 const load=()=>vm.runInNewContext(code.replace('__SETTINGS__',JSON.stringify({path:'/live',quality:'auto'})),context);
 load();timers[0]();timers[0]();
 assert.equal(packets.filter(p=>p.message?.includes('wymaga zalogowania')).length,1);
 assert.equal(session.size,0);
 events.click({target:{closest:()=>login}});
 assert.equal(session.get('tvPlayer.signingIn'),'1');
 load();timers[1]();
 assert.equal(saved.size,0);
 video={readyState:3,paused:false,duration:40,currentTime:1,getBoundingClientRect:()=>({width:500})};
 timers[1]();
 assert.equal(saved.get('tvPlayer.signedInOnSite'),'1');
 assert.equal(session.size,0);
 const back={key:'Backspace',preventDefault(){},stopImmediatePropagation(){}};
 events.keydown({...back,target:{closest:()=>true}});
 assert(!packets.some(p=>p.action==='catalog-back'));
 events.keydown(back);
 assert.equal(packets.at(-1).action,'catalog-back');
}
(async()=>{await run();await run(true);startup(false);startup(true);loginWall();console.log('PASS: Player controls, live/VOD clocks, website login, startup Watch, no automatic privacy/purchase actions');})().catch(e=>{console.error(e);process.exitCode=1});
