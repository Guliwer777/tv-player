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
(async()=>{await run();await run(true);startup(false);startup(true);console.log('PASS: Player controls, live/VOD clocks, bounded seek, startup Watch, no automatic privacy/purchase actions');})().catch(e=>{console.error(e);process.exitCode=1});
