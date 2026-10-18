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
console.log('PASS: official SDK capture, original instances/arguments and origin restrictions');
