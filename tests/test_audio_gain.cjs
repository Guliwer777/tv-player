const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let gain,resumeCount=0;
class Context {
  createGain(){gain={gain:{value:1},connect(){return this;}};return gain;}
  createMediaElementSource(){return {connect(node){return node;}};}
  resume(){resumeCount++;return Promise.resolve();}
}
const context={window:{AudioContext:Context}};
vm.runInNewContext(fs.readFileSync('webplayer/audio_gain.js','utf8'),context);
const video={volume:0};
assert.equal(context.window.__tvpAudioGain.set(video,200),200);
assert.equal(video.volume,1);assert.equal(gain.gain.value,2);
assert.equal(context.window.__tvpAudioGain.get(video),200);
context.window.__tvpAudioGain.set(video,70);
assert.equal(video.volume,.7);assert.equal(gain.gain.value,1);
context.window.__tvpAudioGain.resume(video);
assert.equal(resumeCount,3);
console.log('PASS: 0–200% audio gain');
