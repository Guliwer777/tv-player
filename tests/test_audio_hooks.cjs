const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('webplayer/audio_hooks.js','utf8');
const polsat={location:{origin:'https://polsatboxgo.pl'},window:{}};vm.runInNewContext(source,polsat);
let listener;
class Player{constructor(value){assert.equal(value,'unchanged');this.onPlaybackOptionsUpdated={attach:fn=>listener=fn};}}
polsat.window.CyfrowyPlayer={Player};const p=new polsat.window.CyfrowyPlayer.Player('unchanged');
assert.equal(polsat.window.__tvpPolsatSDK,p);listener({audio:[{label:'polski (audiodeskrypcja)',value:{active:true}}]});assert.equal(polsat.window.__tvpPolsatAudio.length,1);
assert(p instanceof Player);
const player={location:{origin:'https://player.pl'},window:{}};vm.runInNewContext(source,player);
const native={getAudioTracks:()=>[]},namespace={};Object.defineProperty(namespace,'init',{enumerable:true,get:()=>()=>native});player.window.nuvi=namespace;
assert.equal(player.window.nuvi.init(),native);assert.equal(player.window.__tvpPlayerSDK,native);
const foreign={location:{origin:'https://other.example'},window:{}};vm.runInNewContext(source,foreign);assert(!Object.hasOwn(foreign.window,'nuvi'));
// Only the official content-ended signal finishes a VOD; repeated/ad events do not.
const finished=[],vod={location:{origin:'https://polsatboxgo.pl',pathname:'/wideo/samo-zycie/9272/ogladaj'},window:{tvp_bridge:{postMessage:p=>finished.push(JSON.parse(p))}},document:{querySelectorAll:()=>[{pause(){}}]}};
let end,controllerEnd;
class VodPlayer{constructor(){this.onVideoComplete={attach:fn=>end=fn};this.onPlaybackEnded={attach:fn=>controllerEnd=fn};}}
vm.runInNewContext(source,vod);vod.window.CyfrowyPlayer={Player:VodPlayer};new vod.window.CyfrowyPlayer.Player();
// Controller replacement is not an episode ending.
controllerEnd?.();assert.equal(finished.length,0);
end();end();assert.equal(finished.length,1);assert.equal(finished[0].content_end,true);
vod.location.pathname='/kanaly-tv/kanal/1/ogladaj';new vod.window.CyfrowyPlayer.Player();end();assert.equal(finished.length,1);
// Nuvi distinguishes the main film from an advert with a boolean payload.
let nuviEnd;const nuviEvents=[];
const nuviInstance={on:(name,callback)=>{assert.equal(name,'mainMaterialEnded');nuviEnd=callback;}};
const nuvi={location:{origin:'https://player.pl',pathname:'/seriale/test'},window:{tvp_bridge:{postMessage:p=>nuviEvents.push(JSON.parse(p))}},document:{querySelectorAll:()=>[]}};
vm.runInNewContext(source,nuvi);nuvi.window.nuvi={init:()=>nuviInstance};nuvi.window.nuvi.init();
nuviEnd(false);assert.equal(nuviEvents.length,0);nuviEnd(true);nuviEnd(true);assert.equal(nuviEvents.length,1);
nuvi.location.pathname='/live';nuvi.window.nuvi.init();nuviEnd(true);assert.equal(nuviEvents.length,1);
console.log('PASS: official SDK capture, original instances/arguments and origin restrictions');

// Rebuilding the official controls may detach every listener. Restore only our own.
let keepAlive;const listeners=new Set(),emitted=[];
class RebuiltPlayer{constructor(){this.onVideoComplete={attach:fn=>listeners.add(fn),detach:fn=>fn?listeners.delete(fn):listeners.clear()};}}
const rebuilt={location:{origin:'https://polsatboxgo.pl',pathname:'/wideo/serial/1/ogladaj'},window:{tvp_bridge:{postMessage:p=>emitted.push(JSON.parse(p))}},setInterval:fn=>keepAlive=fn};
vm.runInNewContext(source,rebuilt);rebuilt.window.CyfrowyPlayer={Player:RebuiltPlayer};const rebuiltSDK=new rebuilt.window.CyfrowyPlayer.Player();
const official=()=>{};rebuiltSDK.onVideoComplete.detach();rebuiltSDK.onVideoComplete.attach(official);keepAlive();keepAlive();assert.equal(listeners.size,2);assert(listeners.has(official));
for(const callback of listeners)callback();assert.equal(emitted.length,1);

// Native next-episode middleware cannot start another film under the old add-on title.
const blockedEvents=[],middleware=new Map();
class NativeNextPlayer{registerMiddleware(name,fn){middleware.set(name,fn);}}
const blocked={location:{origin:'https://polsatboxgo.pl',pathname:'/wideo/serial-odcinek-1310/id1310/ogladaj'},window:{tvp_bridge:{postMessage:p=>blockedEvents.push(JSON.parse(p))}}};
vm.runInNewContext(source,blocked);blocked.window.CyfrowyPlayer={Player:NativeNextPlayer};new blocked.window.CyfrowyPlayer.Player();
assert(middleware.has('waitForNext'));assert(middleware.has('playNext'));
const pending=middleware.get('waitForNext')();assert.equal(typeof pending.then,'function');middleware.get('playNext')();assert.equal(blockedEvents.length,1);
