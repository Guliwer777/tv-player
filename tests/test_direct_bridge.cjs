const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
(async()=>{
 const events=[],handlers={},network={registerScheme(scheme,plugin){assert.equal(scheme,'https');this.plugin=plugin;},PluginPriority:{APPLICATION:3}};
 let tick,configuration;
 const video={currentTime:0,duration:8842.661,volume:1,paused:true,addEventListener(n,f){handlers[n]=f;},play(){this.paused=false;return Promise.resolve();},pause(){this.paused=true;}};
 const tracks=[{id:20,active:true,language:'pl'},{id:99,active:false,language:'pl',label:'Audiodeskrypcja',roles:['description']}];
 class Player{
  attach(){return Promise.resolve();}addEventListener(){}getNetworkingEngine(){return network;}
  configure(c){configuration=c;}load(url,start){video.currentTime=start;return Promise.resolve();}
  getAudioTracks(){return tracks;}getVariantTracks(){return [];}
  selectAudioTrack(track){setTimeout(()=>tracks.forEach(t=>t.active=t.id===track.id),20);}
 }
 Player.isBrowserSupported=()=>true;
 let relayRequest;
 const context={URL,Date,Number,Promise,AbortController,performance,setTimeout,setInterval:f=>{tick=f;},location:{href:'http://127.0.0.1:123/token/index.html'},
  window:{tvp_bridge:{postMessage:s=>events.push(JSON.parse(s))},addEventListener(n,f){handlers[n]=f;}},
  document:{getElementById:id=>id==='video'?video:{textContent:''}},
  fetch:async(url,options)=>{
   if(url==='config.json')return {json:async()=>({manifest:'https://cdn.example/manifest.mpd',servers:{'com.widevine.alpha':'https://vod.tvp.pl/licence'},relay:'relay',start:125.375,volume:70,pause:false,quality:'800000'})};
   relayRequest={url,options};return {ok:true,status:200,headers:new Map(),arrayBuffer:async()=>new Uint8Array([1,2,3]).buffer};
  },
  shaka:{Player,net:{NetworkingEngine:network,HttpXHRPlugin:{parse(url,request,type,progress,headers,pluginConfig){
   assert.equal(pluginConfig.minBytesForProgressEvents,1000);
   relayRequest={url,options:request};progress(1,3,0);
   return {chain:callback=>({promise:Promise.resolve(callback({uri:url,data:new Uint8Array([1,2,3]).buffer}))})};
  }}},polyfill:{installAll(){}}}};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../webplayer/direct.js'),'utf8'),context);
 await new Promise(setImmediate);tick();
 assert.equal(video.currentTime,125.375);assert.equal(video.paused,false);
 assert.equal(configuration.abr.restrictions.maxBandwidth,800000);
 assert.ok(events.some(e=>e.event==='file-loaded'));
 await context.window.__tvpCommand({command:['set_property','pause',true]});assert.equal(video.paused,true);
 await context.window.__tvpCommand({command:['seek',15]});assert.equal(video.currentTime,140.375);
 await context.window.__tvpCommand({command:['get_property','time-pos'],request_id:7401});assert.equal(events.at(-1).data,140.375);
 await context.window.__tvpCommand({command:['set_property','aid',2]});
 await context.window.__tvpCommand({command:['get_property','aid'],request_id:7404});
 await new Promise(r=>setTimeout(r,150));assert.equal(events.at(-1).data,2);
 let progressBytes=0;
 const remote='https://cdn.example/file.m4s';
 const response=await network.plugin(remote,{method:'GET',headers:{}},1,(elapsed,bytes)=>{progressBytes+=bytes;},()=>{},{minBytesForProgressEvents:1000}).promise;
 assert.ok(relayRequest.url.startsWith('http://127.0.0.1:123/token/relay?'));
 assert.equal(response.uri,remote);assert.equal(response.data.byteLength,3);assert.equal(progressBytes,3);
 Player.prototype.seekRange=()=>({start:10000,end:10120});
 Player.prototype.load=(url,start)=>{assert.equal(start,undefined);video.currentTime=10110;return Promise.resolve();};
 video.duration=Infinity;
 context.fetch=async()=>({json:async()=>({manifest:remote,isLive:true,volume:70,pause:false,quality:'auto'})});
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../webplayer/direct.js'),'utf8'),context);
 await new Promise(setImmediate);
 await context.window.__tvpCommand({command:['get_property','time-pos'],request_id:7401});assert.equal(events.at(-1).data,110);
 await context.window.__tvpCommand({command:['get_property','duration'],request_id:7402});assert.equal(events.at(-1).data,120);
 await context.window.__tvpCommand({command:['seek',100]});assert.equal(video.currentTime,10120);
 console.log('PASS: direct EME bridge resume, pause, seek, audio, quality, routing and live window bounds');
})().catch(e=>{console.error(e);process.exitCode=1;});
